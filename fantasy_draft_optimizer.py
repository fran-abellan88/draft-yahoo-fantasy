"""
NBA Fantasy Draft Optimizer - Optimized Version with Progress Tracking

This script uses NumPy vectorization and smart filtering to efficiently
analyze millions of team combinations.
"""

import argparse
import warnings
from itertools import islice, product
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

from config import ALL_STAT_COLS, CSV_PATH, NUM_PICKS, OUTPUT_PLAYERS_JSON, OUTPUT_TEAMS_JSON, SCORING_STAT_COLS

warnings.filterwarnings("ignore")

# Import preprocessing functions (lazy import to avoid circular dependency issues)
try:
    from preprocess_data import load_players_data, preprocess_teams_data
except ImportError:
    preprocess_teams_data = None
    load_players_data = None


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Clean column names: lowercase and remove whitespaces."""
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    return df


def load_and_prepare_data(
    csv_path: str,
) -> Tuple[pd.DataFrame, List[pd.DataFrame], List[np.ndarray], List[List[str]], List[List[str]]]:
    """Load CSV and prepare data structures for fast processing."""
    df = pd.read_csv(csv_path)
    df = clean_column_names(df)

    # Forward fill pick and pick_number columns
    df["pick"] = df["pick"].ffill()
    df["pick_number"] = df["pick_number"].ffill()

    # Fill status column NaN values with "-"
    if "status" in df.columns:
        df["status"] = df["status"].fillna("-")

    # Parse positions
    df["positions"] = df["position"].apply(lambda x: [p.strip() for p in str(x).split(",")] if pd.notna(x) else [])

    # Filter to only first NUM_PICKS picks
    df = df[df["pick"] <= NUM_PICKS].copy()

    # Prepare data structures for vectorized operations
    pick_groups = []
    pick_stats = []
    pick_positions = []
    pick_players = []

    # Use all stat columns from config (includes FG%, FT% and TO for storage only, not used in scoring)
    all_stat_cols = ALL_STAT_COLS

    for pick in sorted(df["pick"].unique()):
        pick_df = df[df["pick"] == pick].reset_index(drop=True)
        pick_groups.append(pick_df)

        # Extract stats as numpy array for fast operations (include TO for storage)
        stats_array = pick_df[all_stat_cols].values
        pick_stats.append(stats_array)

        # Extract positions
        positions_list = pick_df["positions"].tolist()
        pick_positions.append(positions_list)

        # Extract player names
        players_list = pick_df["player"].tolist()
        pick_players.append(players_list)

    return df, pick_groups, pick_stats, pick_positions, pick_players


def check_position_constraint_vectorized(position_matrix: np.ndarray) -> np.ndarray:
    """
    Vectorized position constraint check.

    Args:
        position_matrix: Shape (n_teams, 8, 5) boolean array
                        where position_matrix[i,j,k] = True if player j in team i is eligible for position k

    Returns:
        Boolean array of shape (n_teams,) indicating which teams are valid
    """
    # Sum across players (axis 1) to get position counts per team
    position_counts = position_matrix.sum(axis=1)  # Shape: (n_teams, 5)

    # Check if all positions have at least 2 eligible players AND at most 5 eligible players
    basic_valid = ((position_counts >= 2) & (position_counts <= 5)).all(axis=1)

    # Additional constraint: no more than 3 positions can have exactly 2 players
    positions_with_two = (position_counts == 2).sum(axis=1)  # Count positions with exactly 2 players
    constraint_valid = positions_with_two <= 3

    valid_teams = basic_valid & constraint_valid

    return valid_teams


def count_distinct_positions_vectorized(position_matrix: np.ndarray) -> np.ndarray:
    """
    Count total number of position eligibilities per team.

    Args:
        position_matrix: Shape (n_teams, 8, 5) boolean array

    Returns:
        Array of shape (n_teams,) with distinct position counts
    """
    return position_matrix.sum(axis=(1, 2))


def generate_position_matrix(team_indices_batch: np.ndarray, pick_positions: List[List[str]]) -> np.ndarray:
    """
    Generate position eligibility matrix for a batch of teams.

    Args:
        team_indices_batch: Shape (batch_size, 8) array of player indices
        pick_positions: List of position lists per pick

    Returns:
        Boolean array of shape (batch_size, 8, 5) for positions [PG, SG, SF, PF, C]
    """
    batch_size = team_indices_batch.shape[0]
    num_picks = team_indices_batch.shape[1]
    position_matrix = np.zeros((batch_size, num_picks, 5), dtype=bool)

    position_to_idx = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}

    for team_idx in range(batch_size):
        for pick_idx in range(num_picks):
            player_idx = team_indices_batch[team_idx, pick_idx]
            player_positions = pick_positions[pick_idx][player_idx]

            for pos in player_positions:
                if pos in position_to_idx:
                    position_matrix[team_idx, pick_idx, position_to_idx[pos]] = True

    return position_matrix


def calculate_team_stats_vectorized(team_indices_batch: np.ndarray, pick_stats: List[np.ndarray]) -> np.ndarray:
    """
    Calculate statistics for a batch of teams using vectorized operations.

    Args:
        team_indices_batch: Shape (batch_size, 8) array of player indices
        pick_stats: List of stat arrays per pick

    Returns:
        Array of shape (batch_size, 8) with aggregated stats [FG%, FT%, 3PTM, PTS, REB, AST, ST, BLK, TO]
        Note: FG%, FT% and TO are included for storage but not used in scoring
    """
    batch_size = team_indices_batch.shape[0]
    num_picks = team_indices_batch.shape[1]
    team_stats = np.zeros((batch_size, 9))

    for pick_idx in range(num_picks):
        player_indices = team_indices_batch[:, pick_idx]
        pick_player_stats = pick_stats[pick_idx][player_indices]
        team_stats += pick_player_stats

    # For FG% and FT%, divide by num_picks to get average (they were summed above)
    team_stats[:, 0] /= num_picks  # FG%
    team_stats[:, 1] /= num_picks  # FT% (stored but not used in scoring)

    return team_stats


def process_in_batches(
    pick_stats: List[np.ndarray],
    pick_positions: List[List[str]],
    pick_players: List[List[str]],
    batch_size: int = 50000,
    sample_size: Optional[int] = None,
    target_valid_teams: Optional[int] = None,
) -> pd.DataFrame:
    """
    Process all team combinations in batches for memory efficiency.

    Args:
        pick_stats: List of stat arrays per pick
        pick_positions: List of position lists per pick
        pick_players: List of player names per pick
        batch_size: Number of teams to process at once
        sample_size: If provided, only process this many teams total (for testing)
        target_valid_teams: If provided, keep sampling until this many valid teams are found

    Returns:
        DataFrame with all valid teams and their statistics
    """
    # Generate all possible team index combinations
    pick_sizes = [len(positions) for positions in pick_positions]
    print(f"Pick sizes: {pick_sizes}")
    total_combinations = int(np.prod(pick_sizes))
    print(f"Total raw combinations: {total_combinations:,}")

    # Generate index ranges for each pick
    index_ranges = [range(size) for size in pick_sizes]

    # Create iterator
    combination_iterator = product(*index_ranges)

    # Determine mode
    if target_valid_teams is not None:
        print(f"\n🎯 TARGET MODE: Sampling until {target_valid_teams:,} valid teams are found")
        total_to_process = None  # Unknown
    elif sample_size is not None:
        print(f"\n🔍 SAMPLING MODE: Processing {sample_size:,} teams total")
        combination_iterator = islice(combination_iterator, sample_size)
        total_to_process = sample_size
    else:
        total_to_process = total_combinations

    # Process in batches
    all_valid_teams = []
    total_processed = 0

    print("\nProcessing teams in batches...")

    # Create progress bar
    if total_to_process is not None:
        pbar = tqdm(total=total_to_process, desc="Processing teams", unit="teams")
    else:
        pbar = tqdm(desc="Processing teams", unit="teams")

    batch = []
    for team_indices in combination_iterator:
        batch.append(team_indices)

        if len(batch) >= batch_size:
            # Process this batch
            team_indices_batch = np.array(batch)
            batch_results = process_batch(team_indices_batch, pick_stats, pick_positions, pick_players)

            # If we have a target, only add what we need
            if target_valid_teams is not None:
                remaining_needed = target_valid_teams - len(all_valid_teams)
                all_valid_teams.extend(batch_results[:remaining_needed])
            else:
                all_valid_teams.extend(batch_results)

            total_processed += len(batch)
            pbar.update(len(batch))
            pbar.set_postfix({"Valid teams": f"{len(all_valid_teams):,}"})

            batch = []

            # Check if we've reached target
            if target_valid_teams is not None and len(all_valid_teams) >= target_valid_teams:
                print(
                    f"\n✅ Target reached! Found {target_valid_teams:,} valid teams after processing {total_processed:,} total teams"
                )
                break

    # Process remaining batch (if not already done)
    if batch and (target_valid_teams is None or len(all_valid_teams) < target_valid_teams):
        team_indices_batch = np.array(batch)
        batch_results = process_batch(team_indices_batch, pick_stats, pick_positions, pick_players)

        # If we have a target, only add what we need
        if target_valid_teams is not None:
            remaining_needed = target_valid_teams - len(all_valid_teams)
            all_valid_teams.extend(batch_results[:remaining_needed])
        else:
            all_valid_teams.extend(batch_results)

        total_processed += len(batch)
        pbar.update(len(batch))
        pbar.set_postfix({"Valid teams": f"{len(all_valid_teams):,}"})

    pbar.close()

    print(f"\n✅ Total processed: {total_processed:,}")
    print(f"✅ Valid teams after filtering: {len(all_valid_teams):,}")
    if total_processed > 0:
        print(
            f"✅ Filtering rate: {len(all_valid_teams) / total_processed * 100:.2f}% teams passed position constraints"
        )

    if len(all_valid_teams) == 0:
        raise ValueError("No valid teams found that satisfy position constraints!")

    # Convert to DataFrame
    teams_df = pd.DataFrame(all_valid_teams)

    return teams_df


def process_batch(
    team_indices_batch: np.ndarray,
    pick_stats: List[np.ndarray],
    pick_positions: List[List[str]],
    pick_players: List[List[str]],
) -> List[Dict]:
    """Process a batch of team combinations."""
    # Generate position matrix
    position_matrix = generate_position_matrix(team_indices_batch, pick_positions)

    # Filter by position constraint
    valid_mask = check_position_constraint_vectorized(position_matrix)

    if not valid_mask.any():
        return []

    # Keep only valid teams
    valid_indices = team_indices_batch[valid_mask]
    valid_position_matrix = position_matrix[valid_mask]

    # Calculate stats for valid teams
    team_stats = calculate_team_stats_vectorized(valid_indices, pick_stats)

    # Count distinct positions
    distinct_positions = count_distinct_positions_vectorized(valid_position_matrix)

    # Calculate position counts for each team
    position_counts = valid_position_matrix.sum(axis=1)  # Shape: (n_valid_teams, 5)

    # Calculate position variance (lower = more balanced)
    pos_std = position_counts.std(axis=1)  # Standard deviation across positions

    # Build result list
    results = []
    for i, indices in enumerate(valid_indices):
        # Get player names
        player_names = [pick_players[pick_idx][player_idx] for pick_idx, player_idx in enumerate(indices)]

        results.append(
            {
                "team_indices": tuple(indices),  # Store indices to retrieve player data later
                "players": " | ".join(player_names),
                "team_fg%": team_stats[i, 0],
                "team_ft%": team_stats[i, 1],
                "team_3ptm": team_stats[i, 2],
                "team_pts": team_stats[i, 3],
                "team_reb": team_stats[i, 4],
                "team_ast": team_stats[i, 5],
                "team_st": team_stats[i, 6],
                "team_blk": team_stats[i, 7],
                "team_to": team_stats[i, 8],  # Stored but not used in scoring
                "distinct_positions": int(distinct_positions[i]),
                "pos_std": float(pos_std[i]),
                "pos_pg_count": int(position_counts[i, 0]),
                "pos_sg_count": int(position_counts[i, 1]),
                "pos_sf_count": int(position_counts[i, 2]),
                "pos_pf_count": int(position_counts[i, 3]),
                "pos_c_count": int(position_counts[i, 4]),
            }
        )

    return results


def normalize_and_rank(teams_df: pd.DataFrame, method: str, max_teams: int = 300000) -> pd.DataFrame:
    """
    Normalize statistics and rank teams.

    Args:
        teams_df: DataFrame with team statistics
        method: 'minmax' or 'zscore'
        max_teams: Maximum number of top teams to keep

    Returns:
        Ranked DataFrame with normalized scores
    """
    result_df = teams_df.copy()
    # Use scoring stat columns from config (excludes team_fg%, team_ft% and team_to from scoring)
    stat_cols = SCORING_STAT_COLS

    print(f"\n📊 Applying {method.upper()} normalization...")

    for col in stat_cols:
        values = result_df[col].values

        if method == "minmax":
            min_val = values.min()
            max_val = values.max()
            if max_val == min_val:
                normalized = np.ones_like(values)
            else:
                normalized = (values - min_val) / (max_val - min_val)
        elif method == "zscore":
            mean = values.mean()
            std = values.std()
            if std == 0:
                normalized = np.zeros_like(values)
            else:
                normalized = (values - mean) / std
        else:
            raise ValueError(f"Unknown normalization method: {method}")

        result_df[f"{col}_norm"] = normalized

    # Calculate composite score
    norm_cols = [f"{col}_norm" for col in stat_cols]
    result_df["team_cs"] = result_df[norm_cols].mean(axis=1)

    # Sort by composite score (desc), then by pos_std (asc - lower is better), then by distinct positions (desc)
    result_df = result_df.sort_values(
        by=["team_cs", "pos_std", "distinct_positions"], ascending=[False, True, False]
    ).reset_index(drop=True)

    # Add rank and team_id
    result_df.insert(0, "team_rank", range(1, len(result_df) + 1))
    result_df.insert(0, "team_id", range(1, len(result_df) + 1))

    # Keep top max_teams
    result_df = result_df.head(max_teams)

    print(f"✅ Normalization complete. Top {len(result_df):,} teams ranked.")

    return result_df


def expand_teams_to_players(teams_df: pd.DataFrame, pick_groups: List[pd.DataFrame]) -> pd.DataFrame:
    """
    Expand teams dataframe to have one row per player.

    Args:
        teams_df: DataFrame with one row per team
        pick_groups: List of DataFrames containing original player data per pick

    Returns:
        DataFrame with one row per player
    """
    print("\n📋 Expanding teams to player-level rows...")

    player_rows = []

    for _, team_row in teams_df.iterrows():
        team_indices = team_row["team_indices"]

        # Team-level data (will be repeated for each player)
        team_data = {
            "team_id": team_row["team_id"],
            "team_rank": team_row["team_rank"],
            "team_fg%": team_row["team_fg%"],
            "team_ft%": team_row["team_ft%"],
            "team_3ptm": team_row["team_3ptm"],
            "team_pts": team_row["team_pts"],
            "team_reb": team_row["team_reb"],
            "team_ast": team_row["team_ast"],
            "team_st": team_row["team_st"],
            "team_blk": team_row["team_blk"],
            "team_to": team_row["team_to"],  # Stored for informational purposes only
            "team_cs": round(team_row["team_cs"], 3),
            "pos_std": round(team_row["pos_std"], 3),
            "distinct_positions": team_row["distinct_positions"],
            "pos_pg_count": team_row["pos_pg_count"],
            "pos_sg_count": team_row["pos_sg_count"],
            "pos_sf_count": team_row["pos_sf_count"],
            "pos_pf_count": team_row["pos_pf_count"],
            "pos_c_count": team_row["pos_c_count"],
        }

        # Get each player in the team
        for pick_idx, player_idx in enumerate(team_indices):
            player_original_data = pick_groups[pick_idx].iloc[player_idx]

            # Combine team data with player data
            player_row = {**team_data}

            # Add all original player columns (without prefix)
            for col in player_original_data.index:
                if col == "positions":  # Skip the parsed list
                    continue
                player_row[col] = player_original_data[col]

            player_rows.append(player_row)

    result_df = pd.DataFrame(player_rows)

    print(f"✅ Expanded {len(teams_df):,} teams into {len(result_df):,} player rows")

    return result_df


def save_results(
    minmax_df: Optional[pd.DataFrame],
    zscore_df: Optional[pd.DataFrame],
    pick_groups: List[pd.DataFrame],
    output_dir: str = ".",
    prefix: str = "",
) -> None:
    """Save results to CSV files with player-level rows."""

    print("\n💾 Results saved:")

    # Save minmax if available
    if minmax_df is not None:
        minmax_players = expand_teams_to_players(minmax_df, pick_groups)
        minmax_path = f"{output_dir}/{prefix}top_teams_minmax.csv"
        minmax_players.to_csv(minmax_path, index=False)
        print(f"   • Min-Max normalization: {minmax_path}")

    # Save zscore if available
    if zscore_df is not None:
        zscore_players = expand_teams_to_players(zscore_df, pick_groups)
        zscore_path = f"{output_dir}/{prefix}top_teams_zscore.csv"
        zscore_players.to_csv(zscore_path, index=False)
        print(f"   • Z-Score normalization: {zscore_path}")


def main() -> None:
    """Main execution function."""
    parser = argparse.ArgumentParser(description="NBA Fantasy Draft Optimizer")
    parser.add_argument("--sample", type=int, default=None, help="Process this many teams total (e.g., --sample 1000)")
    parser.add_argument(
        "--valid-teams",
        type=int,
        default=None,
        help="Keep sampling until this many valid teams are found (e.g., --valid-teams 100)",
    )
    parser.add_argument(
        "--max-output", type=int, default=300000, help="Maximum number of top teams to output (default: 300000)"
    )
    parser.add_argument(
        "--method",
        type=str,
        default="both",
        choices=["minmax", "zscore", "both"],
        help="Normalization method to use: 'minmax', 'zscore', or 'both' (default: both)",
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Automatically run preprocessing for dashboard after optimization",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.sample is not None and args.valid_teams is not None:
        print("ERROR: Cannot use both --sample and --valid-teams together. Choose one.")
        return

    # Determine max_output behavior
    max_output = args.max_output
    if (args.sample is not None or args.valid_teams is not None) and args.max_output == 300000:
        # User is sampling but didn't specify max_output, so we'll use all valid teams found
        max_output = None  # Will be set after processing

    csv_path = "/Users/a0844243/FranHome/WorkArea/Projects/Personal/draft-yahoo-fantasy/Draft NBA Yahoo Fantasy 2025 - Picks.csv"

    print("=" * 70)
    print("🏀 NBA Fantasy Draft Optimizer")
    print("=" * 70)

    # Load data
    print("\n📂 Loading data...")
    df, pick_groups, pick_stats, pick_positions, pick_players = load_and_prepare_data(csv_path)
    print(f"✅ Loaded {len(df)} players across {len(pick_stats)} picks")

    # Process all teams
    teams_df = process_in_batches(
        pick_stats, pick_positions, pick_players, sample_size=args.sample, target_valid_teams=args.valid_teams
    )

    # If max_output was not explicitly set and we're sampling, use all valid teams
    if max_output is None:
        max_output = len(teams_df)
        print(f"\n📊 Outputting all {max_output:,} valid teams found")
    elif max_output > len(teams_df):
        max_output = len(teams_df)
        print(f"\n📊 Only {max_output:,} valid teams found (less than max-output)")

    # Normalize and rank based on selected method
    minmax_df = None
    zscore_df = None
    display_cols = ["team_id", "team_rank", "team_cs", "pos_std", "distinct_positions", "players"]

    if args.method in ["minmax", "both"]:
        minmax_df = normalize_and_rank(teams_df, "minmax", max_teams=max_output)
        print("\n" + "=" * 70)
        print("🏆 TOP 10 TEAMS - MIN-MAX NORMALIZATION")
        print("=" * 70)
        print(minmax_df.head(10)[display_cols].to_string(index=False, max_colwidth=50))

    if args.method in ["zscore", "both"]:
        zscore_df = normalize_and_rank(teams_df, "zscore", max_teams=max_output)
        print("\n" + "=" * 70)
        print("🏆 TOP 10 TEAMS - Z-SCORE NORMALIZATION")
        print("=" * 70)
        print(zscore_df.head(10)[display_cols].to_string(index=False, max_colwidth=50))

    # Save results with appropriate prefix
    if args.sample is not None or args.valid_teams is not None:
        prefix = "sample_"
    else:
        prefix = ""
    save_results(minmax_df, zscore_df, pick_groups, prefix=prefix)

    print("\n" + "=" * 70)
    print("✅ Optimization complete!")
    print("=" * 70)

    # Run preprocessing if requested
    if args.preprocess:
        if preprocess_teams_data is None or load_players_data is None:
            print("\n⚠️  WARNING: Could not import preprocessing functions from preprocess_data.py")
            print("Skipping preprocessing step.")
        else:
            print("\n" + "=" * 70)
            print("🔄 Running preprocessing for dashboard...")
            print("=" * 70)
            print()

            # Determine which CSV to preprocess (prefer minmax, fallback to zscore)
            csv_to_preprocess = f"{prefix}top_teams_minmax.csv" if minmax_df is not None else f"{prefix}top_teams_zscore.csv"

            try:
                # Preprocess teams data
                preprocess_teams_data(csv_to_preprocess, OUTPUT_TEAMS_JSON)

                # Preprocess players data
                load_players_data(CSV_PATH, OUTPUT_PLAYERS_JSON)

                print("\n" + "=" * 70)
                print("✅ Preprocessing complete! Dashboard data ready.")
                print("=" * 70)
                print("\n💡 You can now run the dashboard with: python3 run_dashboard.py")
            except Exception as e:
                print(f"\n❌ Error during preprocessing: {e}")
                print("You may need to run preprocess_data.py manually.")


if __name__ == "__main__":
    main()
