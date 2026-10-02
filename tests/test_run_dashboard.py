"""run_dashboard.py lets every trial use its own saved draft, so a test instance cannot replace the real one."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_draft_file_can_be_chosen_and_is_documented() -> None:
    result = subprocess.run([sys.executable, "run_dashboard.py", "--help"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0 and "--draft-file" in result.stdout
    source = (ROOT / "run_dashboard.py").read_text()
    assert "Saving the draft in" in source and "SavedDraft(args.draft_file)" in source
