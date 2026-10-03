"""Tests for the last-season and availability flags."""

import pandas as pd
import pytest

from fantasy_draft.categories import categories_in
from fantasy_draft.data import REFERENCE_POOL, load_players
from fantasy_draft.flags import build_flags
from fantasy_draft.scoring import compute_bounds

BOUNDS = {"pts": (0.0, 20.0)}


def _players(rows: list) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["player"] = [f"p{i}" for i in range(len(frame))]
    return frame


def test_missing_last_season_is_flagged_and_nothing_else() -> None:
    players = _players([{"pts": 10.0, "gp": 70, "pts_ly": float("nan"), "gp_ly": float("nan")}])
    flags = build_flags(players, ["pts"], BOUNDS)
    row = flags.iloc[0]
    assert row["flag_ly_missing"]
    assert not row["flag_ly_small_sample"] and not row["flag_ly_diverges"]
    assert pd.isna(row["ly_composite"])


def test_small_sample_explains_a_divergence_instead_of_raising_it() -> None:
    players = _players([{"pts": 10.0, "gp": 70, "pts_ly": 20.0, "gp_ly": 5}])
    row = build_flags(players, ["pts"], BOUNDS).iloc[0]
    assert row["flag_ly_small_sample"]
    assert not row["flag_ly_diverges"]


def test_divergence_is_flagged_for_a_real_sample() -> None:
    players = _players(
        [
            {"pts": 10.0, "gp": 70, "pts_ly": 16.0, "gp_ly": 70},  # 30 points apart
            {"pts": 10.0, "gp": 70, "pts_ly": 11.0, "gp_ly": 70},  # 5 points apart
        ]
    )
    flags = build_flags(players, ["pts"], BOUNDS)
    assert flags["flag_ly_diverges"].tolist() == [True, False]
    assert flags["ly_delta"].iloc[0] == pytest.approx(-30.0)


def test_divergence_threshold_is_inclusive() -> None:
    players = _players([{"pts": 10.0, "gp": 70, "pts_ly": 12.0, "gp_ly": 70}])  # exactly 10 points
    assert build_flags(players, ["pts"], BOUNDS).iloc[0]["flag_ly_diverges"]


def test_low_projected_games_is_flagged() -> None:
    players = _players(
        [
            {"pts": 10.0, "gp": 49, "pts_ly": 10.0, "gp_ly": 70},
            {"pts": 10.0, "gp": 60, "pts_ly": 10.0, "gp_ly": 70},
        ]
    )
    assert build_flags(players, ["pts"], BOUNDS)["flag_low_projected_gp"].tolist() == [True, False]


def test_flags_on_the_real_pool_are_a_usable_minority() -> None:
    players = load_players()
    keys = categories_in(players.columns)
    assert len(keys) == 9
    flags = build_flags(players, keys, compute_bounds(players[players["xrank"] <= REFERENCE_POOL], keys))
    assert flags["flag_ly_missing"].sum() == 16, "8 in the first 150 and 8 deeper"
    named = players.assign(**flags.to_dict("series")).set_index("player")
    assert named.loc["Joel Embiid", "flag_low_projected_gp"]
    assert named.loc["Walker Kessler", "flag_ly_small_sample"]
    # the flags are only useful if they stay selective
    diverging = flags["flag_ly_diverges"].mean()
    assert 0.02 < diverging < 0.30, f"{diverging:.0%} of players diverge; the threshold needs revisiting"
