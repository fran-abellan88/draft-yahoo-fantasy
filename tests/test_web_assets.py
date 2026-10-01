"""Checks on the static page files that a browser would otherwise be the only judge of."""

import re
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


WEB = Path(__file__).resolve().parent.parent / "fantasy_draft" / "web"
CSS = (WEB / "style.css").read_text()

WCAG_TEXT = 4.5


def _tokens(block: str) -> Dict[str, str]:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", block))


def _themes() -> Dict[str, Dict[str, str]]:
    light_block = re.search(r":root\s*\{(.*?)\n\}", CSS, re.S)
    dark_block = re.search(r"@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{(.*?)\}", CSS, re.S)
    assert light_block and dark_block, "the colour tokens moved; update this test"
    light = _tokens(light_block.group(1))
    return {"light": light, "dark": {**light, **_tokens(dark_block.group(1))}}


def _luminance(colour: str) -> float:
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# (text token, background token, where it is used)
TEXT_PAIRS: List[Tuple[str, str, str]] = [
    ("on-mine", "mine", "primary button and the snake cell for my pick on the clock"),
    ("ink", "line", "snake cells for picks already made"),
    ("mine", "mine-soft", "snake cells for my picks already made"),
    ("mine", "surface", "snake cells for my coming picks, roster pick numbers"),
    ("muted", "surface", "secondary text on cards"),
    ("paper", "ink", "snake cell on the clock, active filter chip"),
]


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("foreground,background,usage", TEXT_PAIRS)
def test_text_colours_are_readable_in_both_themes(theme: str, foreground: str, background: str, usage: str) -> None:
    tokens = _themes()[theme]
    ratio = _contrast(tokens[foreground], tokens[background])
    assert ratio >= WCAG_TEXT, f"{foreground} on {background} is {ratio:.2f}:1 in {theme} mode ({usage})"


def test_the_hidden_attribute_wins_over_display_rules() -> None:
    # Without this, `.fields { display: grid }` keeps a `hidden` element visible
    assert re.search(r"\[hidden\]\s*\{\s*display:\s*none\s*!important", CSS)


def test_the_page_declares_both_colour_schemes() -> None:
    # Otherwise form controls and scrollbars stay light in dark mode
    assert re.search(r"color-scheme:\s*light dark", CSS)
