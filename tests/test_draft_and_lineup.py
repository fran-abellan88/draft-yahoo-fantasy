"""Tests for snake order and lineup legality."""

from typing import List

import pytest

from fantasy_draft.draft import DraftState, my_picks, snake_pick
from fantasy_draft.lineup import all_can_start, max_starters


def test_slot_two_picks_match_the_yahoo_draft_room() -> None:
    # The Yahoo screenshots labelled these as "YOUR TURN" picks.
    assert my_picks(slot=2, rounds=11) == [2, 27, 30, 55, 58, 83, 86, 111, 114, 139, 142]


def test_snake_reverses_every_other_round() -> None:
    assert [snake_pick(1, r) for r in (1, 2, 3)] == [1, 28, 29]
    assert [snake_pick(14, r) for r in (1, 2, 3)] == [14, 15, 42]


def test_every_pick_is_used_exactly_once_in_a_round() -> None:
    for round_number in (1, 2, 5, 8):
        picks = sorted(snake_pick(slot, round_number) for slot in range(1, 15))
        assert picks == list(range((round_number - 1) * 14 + 1, round_number * 14 + 1))


@pytest.mark.parametrize("slot", [0, 15])
def test_slot_must_be_inside_the_league(slot: int) -> None:
    with pytest.raises(ValueError):
        snake_pick(slot, 1)


def test_draft_state_counts_picks() -> None:
    state = DraftState(taken=frozenset({"a", "b"}), mine=("c",))
    assert state.picks_made == 3
    assert state.next_pick == 4


def _roster(*positions: str) -> List[List[str]]:
    return [position.split("/") for position in positions]


def test_four_centers_can_start_but_five_cannot() -> None:
    # C, C, Util, Util are the only slots a center-only player can take
    assert all_can_start(_roster("C", "C", "C", "C"))
    assert not all_can_start(_roster("C", "C", "C", "C", "C"))


def test_pure_point_guards_are_limited_to_pg_g_and_two_utils() -> None:
    assert all_can_start(_roster("PG", "PG", "PG", "PG"))
    assert not all_can_start(_roster("PG", "PG", "PG", "PG", "PG"))


def test_positional_flexibility_is_used_by_the_matching() -> None:
    # Without flexibility these five could not all start; with it they can
    assert all_can_start(_roster("PG/SG", "PG/SG", "SF/PF", "SF/PF", "C"))


def test_a_full_thirteen_man_roster_starts_ten() -> None:
    thirteen = _roster("PG", "PG", "SG", "SG", "SF", "SF", "PF", "PF", "C", "C", "C", "PG", "SG")
    assert max_starters(thirteen) == 10
    assert not all_can_start(thirteen)


def test_result_does_not_depend_on_order() -> None:
    roster = _roster("C", "PG/SG", "PF", "SF/PF", "C", "SG")
    assert max_starters(roster) == max_starters(list(reversed(roster)))


def test_empty_roster_is_fine() -> None:
    assert all_can_start([])


def test_assign_slots_fills_the_ten_starting_slots_in_order_and_leaves_open_ones() -> None:
    from fantasy_draft.lineup import ALL_MASK, assign_slots, position_mask

    pg, c = position_mask(["PG"]), position_mask(["C"])
    owners = assign_slots([pg, c])
    assert owners[0] == 0 and owners[6] == 1, "PG slot and the first C slot"
    assert owners.count(None) == 8 and len(owners) == 10
    # three centres: C, C and a Util
    owners = assign_slots([c, c, c])
    assert sorted(owner for owner in owners if owner is not None) == [0, 1, 2]
    # a player who can play anywhere goes where he is needed, not blocking a specialist
    owners = assign_slots([ALL_MASK, pg, pg, pg, pg])
    assert sum(owner is not None for owner in owners) == 5


def test_assign_slots_benches_the_players_who_do_not_fit() -> None:
    from fantasy_draft.lineup import assign_slots, position_mask

    centres = [position_mask(["C"])] * 6
    owners = assign_slots(centres)
    assert sum(owner is not None for owner in owners) == 4, "C, C, Util, Util"
