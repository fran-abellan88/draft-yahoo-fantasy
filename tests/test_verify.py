"""Tests for the snapshot-vs-Yahoo verification, including that it catches a corrupted value."""

from pathlib import Path

import pandas as pd

from fantasy_draft.verify import compare_with_yahoo

DATA = Path(__file__).parent.parent / "data"
PERCENT = {"fg_pct": 0.0006, "ft_pct": 0.0006}


def _frames() -> tuple:
    snapshot = pd.read_csv(DATA / "2026-27" / "projections.csv", keep_default_na=False, na_values=[""])
    yahoo = pd.read_csv(DATA / "2026-27" / "yahoo_projections.csv", keep_default_na=False, na_values=[""])
    return snapshot, yahoo


def _real(differences: pd.DataFrame) -> pd.DataFrame:
    """Drop injury-tag drift, which exists in the real data and is expected."""
    return differences[differences["kind"] != "volatile"].reset_index(drop=True)


def test_the_committed_snapshot_matches_yahoo() -> None:
    snapshot, yahoo = _frames()
    assert _real(compare_with_yahoo(snapshot, yahoo, PERCENT)).empty


def test_a_corrupted_digit_is_caught() -> None:
    snapshot, yahoo = _frames()
    corrupted = snapshot.copy()
    row = corrupted.index[corrupted["player"] == "Nikola Jokic"][0]
    corrupted.loc[row, "pts"] = 1978 + 10  # a misread digit
    differences = _real(compare_with_yahoo(corrupted, yahoo, PERCENT))
    assert len(differences) == 1
    only = differences.iloc[0]
    assert (only["player"], only["column"], only["kind"]) == ("Nikola Jokic", "pts", "stat")
    assert (only["snapshot"], only["yahoo"]) == (1988, 1978)


def test_a_wrong_team_or_position_is_caught() -> None:
    snapshot, yahoo = _frames()
    corrupted = snapshot.copy()
    corrupted.loc[0, "team"] = "XXX"
    corrupted.loc[1, "positions"] = "PG"
    kinds = _real(compare_with_yahoo(corrupted, yahoo, PERCENT))
    assert sorted(kinds["column"]) == ["positions", "team"]
    assert set(kinds["kind"]) == {"text"}


def test_a_player_missing_from_yahoo_is_caught() -> None:
    snapshot, yahoo = _frames()
    differences = _real(compare_with_yahoo(snapshot, yahoo[yahoo["player"] != "Nikola Jokić"], PERCENT))
    assert differences["kind"].tolist() == ["missing"]


def test_rounding_inside_the_tolerance_is_not_a_difference() -> None:
    snapshot, yahoo = _frames()
    nudged = snapshot.copy()
    nudged.loc[0, "fg_pct"] = nudged.loc[0, "fg_pct"] + 0.0004
    assert _real(compare_with_yahoo(nudged, yahoo, PERCENT)).empty


def test_a_difference_beyond_the_tolerance_is_a_difference() -> None:
    snapshot, yahoo = _frames()
    off = snapshot.copy()
    off.loc[0, "fg_pct"] = off.loc[0, "fg_pct"] + 0.01
    assert _real(compare_with_yahoo(off, yahoo, PERCENT))["column"].tolist() == ["fg_pct"]
