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
    assert empty["standing"] == {} and all(row["score"] is None and row["totals"] is None for row in empty["teams"]), "nobody has a player"
    ids = _ids(players)
    table = league_table(players, rosters_by_slot(_picks(ids[:28]), 14), ["pts"], 2, 2, TEAM_NAMES)
    totals = [row["totals"]["pts"] for row in table["teams"]]
    mine = next(row for row in table["teams"] if row["mine"])["totals"]["pts"]
    expected = sum(1.0 if mine > value else 0.0 for value in totals if value is not mine) / 13
    assert table["standing"]["pts"]["beaten"] == pytest.approx(expected, abs=0.01)


def test_a_team_with_an_uncredited_pick_is_scaled_so_the_gap_does_not_make_it_look_weak(players: pd.DataFrame) -> None:
    ids = _ids(players)
    full = rosters_by_slot(_picks(ids[:28]), 14)
    gap_picks = _picks(ids[:28])
    gap_picks[1] = Pick("unseen")  # my pick 2 was never seen
    gap = rosters_by_slot(gap_picks, 14)
    whole = league_table(players, full, ["pts", "fg_pct"], 2, 2, TEAM_NAMES)
    partial = league_table(players, gap, ["pts", "fg_pct"], 2, 2, TEAM_NAMES)
    mine = next(row for row in partial["teams"] if row["mine"])
    one = players.set_index("player_id").loc[ids[26]]
    assert mine["players"] == 1 and mine["totals"]["pts"] == pytest.approx(one["pts"] * 2, abs=1e-3), "one player counted as two"
    assert mine["totals"]["fg_pct"] == pytest.approx(one["fgm"] / one["fga"], abs=1e-3), "a ratio needs no scaling"
    others_whole = {row["slot"]: row["totals"]["pts"] for row in whole["teams"] if not row["mine"]}
    others_partial = {row["slot"]: row["totals"]["pts"] for row in partial["teams"] if not row["mine"]}
    assert others_whole == others_partial, "other teams are untouched"


def test_the_team_score_is_the_expected_categories_won_and_the_rows_come_best_first(players: pd.DataFrame) -> None:
    ids = _ids(players)
    table = league_table(players, rosters_by_slot(_picks(ids[:28]), 14), ["pts", "reb", "to"], 2, 2, TEAM_NAMES)
    scores = [row["score"] for row in table["teams"]]
    assert scores == sorted(scores, reverse=True) and all(0 <= score <= 3 for score in scores)
    assert sum(scores) == pytest.approx(3 * 14 / 2, abs=0.05), "every pair of teams splits one win per category"
    assert table["teams"][0]["place"] == 1 and [row["place"] for row in table["teams"]] == sorted(row["place"] for row in table["teams"])
    mine = next(row for row in table["teams"] if row["mine"])
    assert mine["score"] == pytest.approx(sum(value["beaten"] for value in table["standing"].values()), abs=0.01)


def test_a_team_that_has_not_picked_yet_is_left_out_and_listed_last(players: pd.DataFrame) -> None:
    ids = _ids(players)
    table = league_table(players, rosters_by_slot(_picks(ids[:3]), 14), ["pts", "to"], 1, 2, TEAM_NAMES)
    credited = [row for row in table["teams"] if row["players"]]
    assert len(credited) == 3 and table["teams"][:3] == credited
    assert table["waiting"] == 0 and table["leftOut"] == 11, "teams with no player are left out, not scaled"
    assert all(row["score"] is None and row["ranks"] is None for row in table["teams"][3:])
    assert sorted(row["ranks"]["pts"] for row in credited) == [1, 2, 3], "ranked among the three"


def test_a_team_one_pick_short_in_the_round_in_progress_is_scaled_up(players: pd.DataFrame) -> None:
    ids = _ids(players)
    table = league_table(players, rosters_by_slot(_picks(ids[:15]), 14), ["pts"], 2, 2, TEAM_NAMES)
    short = next(row for row in table["teams"] if row["slot"] == 5)
    one = players.set_index("player_id").loc[ids[4]]
    assert short["players"] == 1 and short["totals"]["pts"] == pytest.approx(one["pts"] * 2, abs=1e-3)
    assert table["waiting"] == 13, "pick 15 went to slot 14, the rest are one short"


def test_a_lone_team_has_no_score_and_no_place(players: pd.DataFrame) -> None:
    ids = _ids(players)
    table = league_table(players, rosters_by_slot(_picks(ids[:1]), 14), ["pts", "to"], 1, 2, TEAM_NAMES)
    assert table["compared"] == 1 and table["leftOut"] == 13
    assert all(row["score"] is None and row["place"] is None for row in table["teams"])
