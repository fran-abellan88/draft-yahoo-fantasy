"""Tests for the automatic picks of the other teams."""

from typing import List

import pandas as pd
import pytest

from fantasy_draft.autopick import choose, next_for_clock, project, startable
from fantasy_draft.data import load_players
from fantasy_draft.draft import Pick, slot_of_pick
from fantasy_draft.lineup import position_mask


@pytest.fixture(scope="module")
def players() -> pd.DataFrame:
    return load_players()


def _by_adp(players: pd.DataFrame) -> List[str]:
    return players.sort_values("adp_est")["player_id"].tolist()


def test_without_noise_the_best_adp_left_is_chosen(players: pd.DataFrame) -> None:
    ids = _by_adp(players)
    assert choose(players, set(), []) == ids[0]
    assert choose(players, set(ids[:5]), []) == ids[5]


def test_a_team_never_gets_more_players_than_the_lineup_can_start(players: pd.DataFrame) -> None:
    pos = players.set_index("player_id")["pos_list"]
    centres = [pid for pid in _by_adp(players) if pos[pid] == ["C"]]
    held = [position_mask(["C"])] * 4
    chosen = choose(players, set(centres[:6]), held)
    assert chosen is not None and pos[chosen] != ["C"], "a fifth pure centre would not start"
    assert choose(players, set(centres[:6]), held[:3]) is not None


def test_startable_allows_bench_players_once_ten_start() -> None:
    centres = [position_mask(["C"])]
    assert startable(centres * 4), "C, C and two Util slots"
    assert not startable(centres * 5), "a fifth centre has nowhere to start"
    assert startable([position_mask(["PG", "SG", "SF", "PF", "C"])] * 12), "versatile players fill ten slots, the rest sit"


def test_noise_is_seeded_and_changes_the_order(players: pd.DataFrame) -> None:
    ids = _by_adp(players)
    picks = [Pick("player", pid) for pid in ids[:3]]
    once = next_for_clock(players, picks, 14, seed=1, noise=True)
    again = next_for_clock(players, picks, 14, seed=1, noise=True)
    assert once == again
    runs = {next_for_clock(players, picks, 14, seed=seed, noise=True) for seed in range(30)}
    assert len(runs) > 1, "different seeds give different rehearsals"
    assert next_for_clock(players, picks, 14) == ids[3]


def test_projection_fills_other_teams_only_up_to_the_pick_and_protects_the_plan(players: pd.DataFrame) -> None:
    ids = _by_adp(players)
    picks = [Pick("player", pid) for pid in ids[:5]]
    protect = {ids[6]}
    added = project(players, picks, 14, until_pick=30, my_slot=2, protect=protect)
    flat = [pid for slot_ids in added.values() for pid in slot_ids]
    assert len(flat) == len(set(flat)) and not set(flat) & (set(ids[:5]) | protect)
    assert len(flat) == sum(1 for number in range(6, 31) if slot_of_pick(number, 14) != 2)
    assert all(len(added[slot]) >= 1 for slot in range(1, 15) if slot != 2)
    assert added[2] == [], "my picks come from the plan"


def test_projection_without_a_pick_to_fill_changes_nothing(players: pd.DataFrame) -> None:
    ids = _by_adp(players)
    picks = [Pick("player", pid) for pid in ids[:30]]
    assert all(not added for added in project(players, picks, 14, until_pick=30, my_slot=2, protect=set()).values())
