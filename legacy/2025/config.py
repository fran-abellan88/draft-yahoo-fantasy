"""
Central configuration file for NBA Fantasy Draft Optimizer.
This serves as the single source of truth for all configurable parameters.
"""

# Number of draft picks to include in analysis
NUM_PICKS = 8

# CSV file path
CSV_PATH = "/Users/a0844243/FranHome/WorkArea/Projects/Personal/draft-yahoo-fantasy/Draft NBA Yahoo Fantasy 2025 - Picks.csv"

# Output file paths
OUTPUT_TEAMS_JSON = "teams_data.json"
OUTPUT_PLAYERS_JSON = "players_data.json"
OUTPUT_MINMAX_CSV = "top_teams_minmax.csv"
OUTPUT_ZSCORE_CSV = "top_teams_zscore.csv"

# Statistical categories used in scoring (excludes FG%, FT%, and TO)
SCORING_STAT_COLS = [
    "team_3ptm",
    "team_pts",
    "team_reb",
    "team_ast",
    "team_st",
    "team_blk",
]

# All statistical categories (for storage)
ALL_STAT_COLS = [
    "fg%",
    "ft%",
    "3ptm",
    "pts",
    "reb",
    "ast",
    "st",
    "blk",
    "to",
]

# Position definitions
POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# Processing parameters
DEFAULT_BATCH_SIZE = 50000
DEFAULT_MAX_OUTPUT_TEAMS = 300000
