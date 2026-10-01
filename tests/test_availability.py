"""Tests for the two availability rules."""

import numpy as np
import pytest

from fantasy_draft.availability import AdpWindow, NormalAdpModel

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
