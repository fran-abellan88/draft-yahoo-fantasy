"""run_dashboard.py gives the real draft and the mock draft each their own saved file, so neither can replace the other."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(*args: str) -> "subprocess.CompletedProcess[str]":
    return subprocess.run([sys.executable, "run_dashboard.py", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)


def test_both_draft_files_can_be_chosen_and_are_documented() -> None:
    result = _run("--help")
    assert result.returncode == 0 and "--draft-file" in result.stdout and "--mock-file" in result.stdout
    source = (ROOT / "run_dashboard.py").read_text()
    assert "SavedDraft(args.draft_file)" in source and "SavedDraft(args.mock_file)" in source
    assert "rehearsal=True" in source and "--rehearsal" not in source


def test_the_mock_draft_cannot_share_the_real_draft_file(tmp_path: Path) -> None:
    same = str(tmp_path / "one.json")
    result = _run("--no-browser", "--draft-file", same, "--mock-file", same)
    assert result.returncode != 0 and "needs its own file" in result.stderr
    assert not (tmp_path / "one.json").exists()


@pytest.mark.parametrize("default", ["saved_draft.json", "saved_mock_draft.json"])
def test_the_default_files_are_not_tracked_by_git(default: str) -> None:
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert default in ignored
