"""
Preprocess NBA Fantasy Draft data for web dashboard.
Converts 224MB CSV into efficient JSON format.
"""

import json
from typing import Dict, List

import pandas as pd

from config import CSV_PATH, NUM_PICKS, OUTPUT_PLAYERS_JSON, OUTPUT_TEAMS_JSON


def preprocess_teams_data(csv_path: str, output_path: str) -> None:
    """
    Convert team CSV to optimized JSON structure.

    Input: 2.7M rows (300k teams × 9 players each)
    Output: Compact JSON with team-to-players mapping
    """
    print("Loading CSV...")
    df = pd.read_csv(csv_path)

    print(f"Loaded {len(df):,} rows")

    # Group by team_id to reconstruct teams
    teams = []
    unique_team_ids = df["team_id"].unique()

    print(f"Processing {len(unique_team_ids):,} teams...")

    for team_id in unique_team_ids:
        if team_id % 10000 == 0:
            print(f"  Processed {team_id:,} teams...")

        team_data = df[df["team_id"] == team_id].copy()

        # Extract team-level data (same for all rows)
        first_row = team_data.iloc[0]

        # Extract player list (pick order is important!)
        players = []
        for _, player_row in team_data.sort_values("pick").iterrows():
            players.append(
                {"name": player_row["player"], "pick": int(player_row["pick"]), "position": player_row["position"]}
            )

        team = {
            "id": int(team_id),
            "rank": int(first_row["team_rank"]),
            "stats": {
                "fg%": round(float(first_row["team_fg%"]), 3),
                "ft%": round(float(first_row["team_ft%"]), 3),
                "3ptm": int(first_row["team_3ptm"]),
                "pts": int(first_row["team_pts"]),
                "reb": int(first_row["team_reb"]),
                "ast": int(first_row["team_ast"]),
                "st": int(first_row["team_st"]),
                "blk": int(first_row["team_blk"]),
                "to": int(first_row["team_to"]),
            },
            "score": round(float(first_row["team_cs"]), 3),
            "pos_std": round(float(first_row["pos_std"]), 3),
            "players": players,
        }

        teams.append(team)

    # Also create player-to-teams index for fast filtering
    player_index = {}
    for team in teams:
        for player_info in team["players"]:
            player_name = player_info["name"]
            if player_name not in player_index:
                player_index[player_name] = []
            player_index[player_name].append(team["id"])

    output_data = {"teams": teams, "player_index": player_index}

    print(f"\nWriting JSON to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(output_data, f, separators=(",", ":"))  # Compact JSON

    print("Done!")


def load_players_data(csv_path: str, output_path: str) -> None:
    """Load and process the players CSV."""
    print("\nLoading players CSV...")
    df = pd.read_csv(csv_path)

    # Clean column names
    df.columns = df.columns.str.lower().str.replace(" ", "_")

    # Forward fill pick column
    df["pick"] = df["pick"].ffill()

    # Filter to only first NUM_PICKS picks
    df = df[df["pick"] <= NUM_PICKS].copy()

    players = []
    for _, row in df.iterrows():
        players.append(
            {
                "name": row["player"],
                "pick": int(row["pick"]),
                "position": row["position"],
                "stats": {
                    "fg%": float(row["fg%"]),
                    "ft%": float(row["ft%"]),
                    "3ptm": int(row["3ptm"]),
                    "pts": int(row["pts"]),
                    "reb": int(row["reb"]),
                    "ast": int(row["ast"]),
                    "st": int(row["st"]),
                    "blk": int(row["blk"]),
                    "to": int(row["to"]),
                },
            }
        )

    print(f"Writing {len(players)} players to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(players, f, separators=(",", ":"))

    print("Done!")


if __name__ == "__main__":
    # Process teams data
    preprocess_teams_data("top_teams_minmax.csv", OUTPUT_TEAMS_JSON)

    # Process players data
    load_players_data(CSV_PATH, OUTPUT_PLAYERS_JSON)
