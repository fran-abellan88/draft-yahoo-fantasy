"""The draft-board reader behind tools/calibrate_availability.py."""

import sys
from pathlib import Path

import pytest

from fantasy_draft.data import load_players

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import calibrate_availability as tool  # noqa: E402

BOARD = Path(__file__).resolve().parent.parent / "data" / "mock_drafts" / "2026-10-07_yahoo_mock_1.txt"


def test_a_board_is_read_in_snake_order_with_names_as_first_last() -> None:
    text = "Round 1\n(1) a - Jokić, Nikola (DEN - C)\n(2) b - Jackson Jr., Jaren (UTA - C,PF)\nRound 2\n(1) b - X, Y (ABC - PG)\n"
    picks = tool.parse_board(text)
    assert picks == [(1, "a", "Nikola Jokić"), (2, "b", "Jaren Jackson Jr."), (15, "b", "Y X")]


def test_the_saved_mock_draft_matches_the_pool() -> None:
    board, missing = tool.load_board(BOARD, load_players())
    assert missing == [] and len(board) == 182
    assert board.iloc[1]["manager"] == "Fran" and board.iloc[1]["player_id"] == "victor-wembanyama"
    assert board["pick"].tolist() == list(range(1, 183))


def test_the_report_runs(capsys: pytest.CaptureFixture) -> None:
    sys.argv = ["calibrate_availability.py", str(BOARD)]
    tool.main()
    out = capsys.readouterr().out
    assert "Best-fitting spread" in out and "182 picks matched" in out


def test_several_drafts_are_judged_one_by_one_and_the_ranking_can_be_chosen(capsys: pytest.CaptureFixture) -> None:
    boards = sorted(BOARD.parent.glob("*.txt"))
    assert len(boards) >= 2
    for center in ("xrank", "adp"):
        sys.argv = ["calibrate_availability.py", "--center", center, *map(str, boards[:2])]
        tool.main()
        out = capsys.readouterr().out
        assert out.count("picks matched") == 2 and f"Pick minus {center}" in out
