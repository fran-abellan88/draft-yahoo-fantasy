"""Checks on the static page files that a browser would otherwise be the only judge of."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "fantasy_draft" / "web"
CSS = (WEB / "style.css").read_text()


def test_the_hidden_attribute_wins_over_display_rules() -> None:
    # Without this, `.fields { display: grid }` keeps a `hidden` element visible
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", CSS)


def test_the_page_declares_both_colour_schemes() -> None:
    # Otherwise form controls and scrollbars stay light in dark mode
    assert re.search(r"color-scheme:\s*light dark", CSS)
