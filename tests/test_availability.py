"""Tests for the two availability rules."""

import math
from typing import List, Sequence

import numpy as np
import pytest

from fantasy_draft.availability import AdpWindow, NormalAdpModel
from fantasy_draft.data import load_players

ADP = np.array([2.0, 10.0, 30.0, 60.0])


def test_current_pick_is_certain_for_everyone() -> None:
    for rule in (NormalAdpModel(), AdpWindow()):
        assert rule.probability(ADP, pick=11, picks_made=10).tolist() == [1.0] * 4


def test_probability_falls_as_the_pick_gets_later() -> None:
    model = NormalAdpModel()
    earlier = model.probability(ADP, pick=15, picks_made=10)
    later = model.probability(ADP, pick=40, picks_made=10)
    assert (later <= earlier).all()
    assert later[0] < 0.01  # a player projected at #2 will not reach pick 40


def test_later_adp_means_more_likely_to_last() -> None:
    probabilities = NormalAdpModel().probability(ADP, pick=35, picks_made=10)
    assert (np.diff(probabilities) >= 0).all()


def test_a_player_going_exactly_at_his_adp_is_a_coin_flip() -> None:
    probability = NormalAdpModel().probability(np.array([30.0]), pick=30, picks_made=10)[0]
    assert probability == pytest.approx(0.5, abs=0.1)


def test_probabilities_are_valid() -> None:
    probabilities = NormalAdpModel().probability(ADP, pick=27, picks_made=3)
    assert ((probabilities >= 0.0) & (probabilities <= 1.0)).all()


def test_early_picks_are_more_predictable_than_late_ones() -> None:
    model = NormalAdpModel()
    # Both are 5 picks past their ADP; the later player's spread is wider so he is more likely to last
    early = model.probability(np.array([20.0]), pick=25, picks_made=10)[0]
    late = model.probability(np.array([100.0]), pick=105, picks_made=10)[0]
    assert late > early


def test_window_is_a_hard_cutoff_with_slack() -> None:
    window = AdpWindow(slack=3.0)
    probabilities = window.probability(np.array([8.0, 9.0, 12.0]), pick=12, picks_made=0)
    assert probabilities.tolist() == [0.0, 1.0, 1.0]


# ---------- unseen picks ----------


def _survives(adp: np.ndarray, pick_number: int, model: NormalAdpModel) -> np.ndarray:
    """Chance of surviving one pick given survival of the one before it, written out pick by pick."""
    sd = model.base_sd + model.sd_per_adp * adp

    def above(position: float) -> np.ndarray:
        return np.array([0.5 * (1 - math.erf((position - m) / (s * math.sqrt(2)))) for m, s in zip(adp, sd)])

    return np.clip(above(pick_number + 0.5) / np.maximum(above(pick_number - 0.5), 1e-12), 0, 1)


def _product(adp: np.ndarray, picks: Sequence[int], model: NormalAdpModel) -> np.ndarray:
    result = np.ones(len(adp))
    for number in picks:
        result *= _survives(adp, number, model)
    return result


def test_with_no_unseen_picks_the_formula_is_unchanged() -> None:
    """The product over the picks still to come is the single ratio the model has always used."""
    model = NormalAdpModel()
    adp = np.array([8.0, 14.0, 22.0, 31.0, 47.0, 80.0])
    for picks_made, pick in ((10, 27), (26, 30), (26, 55), (54, 58)):
        sd = model.base_sd + model.sd_per_adp * adp
        survival = lambda x: 0.5 * (1 - np.vectorize(math.erf)((x - adp) / (sd * math.sqrt(2))))  # noqa: E731
        old = np.clip(survival(pick - 0.5) / np.maximum(survival(picks_made + 0.5), 1e-12), 0, 1)
        assert model.probability(adp, pick, picks_made).tolist() == pytest.approx(old.tolist())
        assert model.probability(adp, pick, picks_made, unseen=()).tolist() == pytest.approx(old.tolist())


@pytest.mark.parametrize(
    "unseen,picks_made,pick",
    [
        ([21, 22, 23, 24, 25, 26], 26, 30),  # unseen picks are the most recent
        ([21, 22, 23, 24, 25, 26], 28, 30),  # pick 27 was seen, 28 is on the clock
        ([10, 11, 15, 16, 17], 20, 27),  # two separate runs with seen picks between and after
        ([5], 5, 6),  # one unseen pick and nothing else before the pick on the clock
    ],
)
def test_the_product_over_unseen_and_future_picks_matches_a_pick_by_pick_calculation(unseen: List[int], picks_made: int, pick: int) -> None:
    model = NormalAdpModel()
    adp = np.array([4.0, 9.0, 14.0, 19.0, 22.0, 26.0, 30.0, 44.0, 70.0])
    expected = _product(adp, unseen + list(range(picks_made + 1, pick)), model)
    # abs: the extreme tails sit at the 1e-12 floor the model uses, where only noise differs
    assert model.probability(adp, pick, picks_made, unseen).tolist() == pytest.approx(expected.tolist(), abs=1e-6)


def test_the_reviewers_example_a_seen_pick_after_unseen_ones() -> None:
    """Picks 21 to 26 unseen, 27 seen, 28 on the clock, my pick at 30: neither 'last logged' nor 'last before the gap'."""
    model = NormalAdpModel()
    odds = model.probability(np.array([22.0, 26.0, 30.0]), pick=30, picks_made=27, unseen=[21, 22, 23, 24, 25, 26])
    assert (odds * 100).round().tolist() == pytest.approx([25.0, 46.0, 64.0], abs=3)
    last_logged = model.probability(np.array([22.0, 26.0, 30.0]), pick=30, picks_made=27)
    before_the_gap = model.probability(np.array([22.0, 26.0, 30.0]), pick=30, picks_made=20)
    assert (last_logged > odds).all() and (before_the_gap < odds).all()


def test_unseen_picks_at_the_end_equal_conditioning_on_the_last_pick_before_them() -> None:
    model = NormalAdpModel()
    adp = np.array([12.0, 24.0, 33.0, 52.0])
    assert model.probability(adp, pick=30, picks_made=26, unseen=[21, 22, 23, 24, 25, 26]).tolist() == pytest.approx(
        model.probability(adp, pick=30, picks_made=20).tolist()
    )


def test_on_the_clock_is_no_longer_certain_when_picks_are_unseen() -> None:
    model = NormalAdpModel()
    adp = np.array([5.0, 24.0, 40.0, 90.0])
    assert model.probability(adp, pick=27, picks_made=26).tolist() == [1.0] * 4
    odds = model.probability(adp, pick=27, picks_made=26, unseen=[24, 25, 26])
    assert odds[0] < 0.05 and odds[1] < 1.0 and (np.diff(odds) >= 0).all()
    assert odds[3] > 0.99  # a player projected far later is almost surely still there


def test_marking_a_player_gone_raises_everyone_elses_odds() -> None:
    """Marking removes one unseen pick from the product, so no one's odds can fall."""
    model = NormalAdpModel()
    adp = np.array([20.0, 27.0, 35.0, 60.0])
    unseen = [21, 22, 23, 24, 25]
    full = model.probability(adp, pick=30, picks_made=25, unseen=unseen)
    for removed in unseen:
        fewer = model.probability(adp, pick=30, picks_made=25, unseen=[n for n in unseen if n != removed])
        assert (fewer >= full - 1e-12).all()
    assert model.probability(adp, pick=30, picks_made=25, unseen=[]).tolist() == pytest.approx(
        model.probability(adp, pick=30, picks_made=25).tolist()
    )


@pytest.mark.parametrize("first,last", [(11, 20), (21, 26), (31, 40), (51, 60), (21, 23)])
def test_the_expected_number_of_players_gone_is_close_to_the_number_of_unseen_picks(first: int, last: int) -> None:
    """Pins one pool (what an ADP-order draft leaves) at the default spread. It does not show the count stays near k.

    Measured there: 5.7 for 6 unseen picks, 9.8 for 10. At spread 1 / 0.1 the same check gives 0.77 times k for picks
    21 to 23, and on drafts drawn from the model the ratio is 1.02 to 1.35, so the sum is not k (see the module notes).
    The band only catches this pool drifting.
    """
    adp = np.sort(load_players()["adp_est"].to_numpy(dtype=float))[first - 1 :]  # the first picks before the run were seen
    unseen = list(range(first, last + 1))
    model = NormalAdpModel()
    gone = float((1 - model.probability(adp, pick=last + 1, picks_made=last, unseen=unseen)).sum())
    assert 0.8 * len(unseen) <= gone <= 1.15 * len(unseen), f"{gone:.2f} players gone for {len(unseen)} unseen picks"


def test_the_window_rule_treats_early_adp_players_as_gone_on_the_clock_only_when_picks_are_unseen() -> None:
    window = AdpWindow(slack=3.0)
    adp = np.array([10.0, 24.0, 40.0])
    assert window.probability(adp, pick=27, picks_made=26).tolist() == [1.0, 1.0, 1.0]
    assert window.probability(adp, pick=27, picks_made=26, unseen=[25, 26]).tolist() == [0.0, 1.0, 1.0]
    assert window.probability(adp, pick=30, picks_made=26, unseen=[25, 26]).tolist() == [0.0, 0.0, 1.0]


def test_the_window_on_the_clock_is_measured_from_the_latest_unseen_pick() -> None:
    """One old unseen pick must not make players who fell far past it count as gone for the rest of the draft."""
    window = AdpWindow(slack=3.0)
    adp = np.array([1.0, 30.0, 45.0, 60.0])
    assert window.probability(adp, pick=55, picks_made=54, unseen=[5]).tolist() == [0.0, 1.0, 1.0, 1.0]
    assert window.probability(adp, pick=55, picks_made=54, unseen=[5, 50]).tolist() == [0.0, 0.0, 0.0, 1.0]
