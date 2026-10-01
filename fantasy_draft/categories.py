"""The scoring categories of the league and how each one is scored."""

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Category:
    """One head-to-head scoring category."""

    key: str
    label: str
    lower_is_better: bool = False
    # Percentages cannot be aggregated across players without attempts, so they are only
    # selectable once the data carries them.
    needs_attempts: bool = False


CATEGORIES: Dict[str, Category] = {
    category.key: category
    for category in (
        Category("fg_pct", "FG%", needs_attempts=True),
        Category("ft_pct", "FT%", needs_attempts=True),
        Category("3ptm", "3PTM"),
        Category("pts", "PTS"),
        Category("reb", "REB"),
        Category("ast", "AST"),
        Category("st", "ST"),
        Category("blk", "BLK"),
        Category("to", "TO", lower_is_better=True),
    )
}


def selectable_categories(has_attempts: bool = False) -> List[str]:
    """Return the category keys a user can score on, in display order."""
    return [key for key, category in CATEGORIES.items() if has_attempts or not category.needs_attempts]
