"""The scoring categories of the league and how each one is scored."""

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class Category:
    """One head-to-head scoring category."""

    key: str
    label: str
    lower_is_better: bool = False
    # Percentages cannot be averaged across players, so they are scored on a volume-weighted value
    # (makes above the pool's baseline, per game) held in `column`. That needs attempts.
    needs_attempts: bool = False
    # Column of the player table that is actually scored; defaults to the key.
    column: str = ""

    def __post_init__(self) -> None:
        if not self.column:
            object.__setattr__(self, "column", self.key)


CATEGORIES: Dict[str, Category] = {
    category.key: category
    for category in (
        Category("fg_pct", "FG%", needs_attempts=True, column="fg_impact"),
        Category("ft_pct", "FT%", needs_attempts=True, column="ft_impact"),
        Category("3ptm", "3PTM"),
        Category("pts", "PTS"),
        Category("reb", "REB"),
        Category("ast", "AST"),
        Category("st", "ST"),
        Category("blk", "BLK"),
        Category("to", "TO", lower_is_better=True),
    )
}


def categories_in(columns: Iterable[str]) -> List[str]:
    """Return the category keys whose scored column exists, in display order."""
    available = set(columns)
    return [key for key, category in CATEGORIES.items() if category.column in available]
