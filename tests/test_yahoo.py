"""Tests for parsing Yahoo's player-list page, using fragments saved from the real page."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from bs4 import BeautifulSoup

from fantasy_draft.yahoo import NAME_ALIASES, _made_attempted, _minutes, page_url, parse_players_page, parse_view

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _cell(text: str):
    return BeautifulSoup(f"<table><tr><td>{text}</td></tr></table>", "lxml").td


def test_parses_a_projection_row_with_attempts() -> None:
    players = parse_players_page(_fixture("yahoo_projections_sample.html")).set_index("player")
    jokic = players.loc["Nikola Jokić"]
    assert jokic["yahoo_id"] == 5352
    assert (jokic["team"], jokic["positions"]) == ("DEN", "C")
    assert (jokic["fgm"], jokic["fga"], jokic["ftm"], jokic["fta"]) == (736, 1283, 386, 471)
    assert (jokic["gp"], jokic["pts"], jokic["reb"], jokic["ast"], jokic["to"]) == (71, 1978, 927, 717, 242)
    assert jokic["fg_pct"] == pytest.approx(0.574)
    assert jokic["status"] == ""


def test_injury_tag_is_read_from_the_player_cell() -> None:
    players = parse_players_page(_fixture("yahoo_projections_sample.html")).set_index("player")
    assert players.loc["Trae Young", "status"] == "P"


def test_a_player_with_no_stats_gets_blanks_not_an_error() -> None:
    players = parse_players_page(_fixture("yahoo_totals_nodata_sample.html"))
    row = players.iloc[0]
    assert row["player"] == "Tyrese Haliburton"
    assert row[["gp", "fgm", "fga", "pts", "to"]].isna().all()
    assert row["positions"] == "PG,SG"


def test_a_page_without_the_table_is_reported_clearly() -> None:
    with pytest.raises(ValueError, match="login"):
        parse_players_page("<html><body>Sign in to continue</body></html>")


def test_the_same_player_on_two_pages_is_an_error() -> None:
    page = _fixture("yahoo_projections_sample.html")
    with pytest.raises(ValueError, match="appears on two pages"):
        parse_view([page, page])


@pytest.mark.parametrize(
    "text, expected",
    [("736/1,283", (736.0, 1283.0)), ("11.3/19.8", (11.3, 19.8)), ("-/-", (np.nan, np.nan)), ("-", (np.nan, np.nan))],
)
def test_made_attempted(text: str, expected: tuple) -> None:
    result = _made_attempted(_cell(text))
    assert result == pytest.approx(expected, nan_ok=True)


@pytest.mark.parametrize("text, expected", [("34:51", 34 + 51 / 60), ("-", np.nan), ("28.4", 28.4)])
def test_minutes(text: str, expected: float) -> None:
    assert _minutes(_cell(text)) == pytest.approx(expected, nan_ok=True)


def test_page_url_pages_by_offset() -> None:
    url = page_url("123", "S_PSR", 50)
    assert "/123/players" in url and "stat1=S_PSR" in url and url.endswith("count=50")


def test_alias_for_the_abbreviated_name_points_at_the_full_name() -> None:
    assert NAME_ALIASES["N. Alexander-Walker"] == "Nickeil Alexander-Walker"
    frame = pd.DataFrame({"player": ["N. Alexander-Walker"]})
    assert frame["player"].replace(NAME_ALIASES).iloc[0] == "Nickeil Alexander-Walker"
