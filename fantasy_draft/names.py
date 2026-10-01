"""Name helpers shared by the loader and the Yahoo scraper (no third-party dependencies)."""

import re
import unicodedata


def normalize_name(name: str) -> str:
    """Accent-free lower-case key for matching names across sources, e.g. "Jokić" -> "jokic"."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_name.lower())


def slugify(name: str) -> str:
    """Return a stable ASCII id for a player name, e.g. "Jaren Jackson Jr." -> "jaren-jackson-jr"."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
