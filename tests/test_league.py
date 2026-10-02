"""Tests for scoring all 14 teams from the pick log."""

from typing import List

import pandas as pd
import pytest

from fantasy_draft.data import load_players
from fantasy_draft.draft import TEAM_NAMES, Pick
from fantasy_draft.league import league_table, rosters_by_slot


@pytest.fixture(scope="module")
def players() -> pd.DataFrame:
    return load_players()


def _ids(players: pd.DataFrame) -> List[str]:
    return players.sort_values("adp_est")["player_id"].tolist()


def _picks(ids: List[str]) -> List[Pick]:
    return [Pick("player", pid) for pid in ids]


def test_rosters_follow_the_snake_order(players: pd.DataFrame) -> None:
    ids = _ids(players)
    rosters = rosters_by_slot(_picks(ids[:30]), 14)
    assert rosters[1] == [ids[0], ids[27], ids[28]] and rosters[14] == [ids[13], ids[14]]
    assert rosters[2] == [ids[1], ids[26], ids[29]], "the user's slot picks 2, 27, 30"


def test_picks_that_name_no_player_are_not_credited_and_are_counted(players: pd.DataFrame) -> None:
    ids = _ids(players)
    picks = _picks(ids[:28])
    picks[3] = Pick("unseen")
    picks[5] = Pick("outside")
    picks[20] = Pick("gone", ids[20])
    rosters = rosters_by_slot(picks, 14)
    assert rosters[4] == [None, ids[24]] and rosters[6] == [None, ids[22]] and rosters[8] == [ids[7], None]
    table = league_table(players, rosters, ["pts"], 2, 2, TEAM_NAMES)
    assert table["notCounted"] == 3
    assert {row["slot"]: row["notCounted"] for row in table["teams"] if row["notCounted"]} == {4: 1, 6: 1, 8: 1}


def test_counting_totals_add_and_percentages_are_ratios_of_totals(players: pd.DataFrame) -> None:
    ids = _ids(players)
    rosters = rosters_by_slot(_picks(ids[:28]), 14)
    table = league_table(players, rosters, ["pts", "fg_pct", "to"], 2, 2, TEAM_NAMES)
    team = next(row for row in table["teams"] if row["slot"] == 2)
    own = players.set_index("player_id").loc[[ids[1], ids[26]]]
    assert team["totals"]["pts"] == pytest.approx(own["pts"].sum(), abs=1e-3)
    assert team["totals"]["fg_pct"] == pytest.approx(own["fgm"].sum() / own["fga"].sum(), abs=1e-3)
    assert team["totals"]["fg_pct"] != pytest.approx(own["fg_pct"].mean(), abs=1e-6), "never the average of percentages"


def test_the_comparison_uses_the_first_n_picks_of_every_team(players: pd.DataFrame) -> None:
    ids = _ids(players)
    rosters = rosters_by_slot(_picks(ids[:29]), 14)  # slot 1 has three picks, the rest two (or fewer)
    table = league_table(players, rosters, ["pts"], 2, 2, TEAM_NAMES)
    assert {row["players"] for row in table["teams"]} == {2}


def test_rank_one_is_best_and_turnovers_are_reversed(players: pd.DataFrame) -> None:
    ids = _ids(players)
    rosters = rosters_by_slot(_picks(ids[:28]), 14)
    table = league_table(players, rosters, ["pts", "to"], 2, 2, TEAM_NAMES)
    points = {row["slot"]: row["totals"]["pts"] for row in table["teams"]}
    turnovers = {row["slot"]: row["totals"]["to"] for row in table["teams"]}
    best_points = max(points, key=lambda slot: points[slot])
    fewest_turnovers = min(turnovers, key=lambda slot: turnovers[slot])
    ranks = {row["slot"]: row["ranks"] for row in table["teams"]}
    assert ranks[best_points]["pts"] == 1 and ranks[fewest_turnovers]["to"] == 1
    assert sorted(set(row["ranks"]["pts"] for row in table["teams"]))[0] == 1


def test_the_share_beaten_counts_ties_as_half_and_an_empty_league_is_even(players: pd.DataFrame) -> None:
    empty = league_table(players, rosters_by_slot([], 14), ["pts"], 0, 2, TEAM_NAMES)
    assert empty["standing"]["pts"] == {"rank": 1, "beaten": 0.5}, "everyone ties at zero"
    ids = _ids(players)
    table = league_table(players, rosters_by_slot(_picks(ids[:28]), 14), ["pts"], 2, 2, TEAM_NAMES)
    totals = [row["totals"]["pts"] for row in table["teams"]]
    mine = next(row for row in table["teams"] if row["mine"])["totals"]["pts"]
    expected = sum(1.0 if mine > value else 0.0 for value in totals if value is not mine) / 13
    assert table["standing"]["pts"]["beaten"] == pytest.approx(expected, abs=0.01)
