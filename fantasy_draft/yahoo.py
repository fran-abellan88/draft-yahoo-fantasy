"""
Download and parse Yahoo Fantasy's player list.

The league's player list page is public and carries what the draft-room screenshots lack: attempts
(FGM/A, FTM/A), minutes and Yahoo's player id. It does not carry ADP or XRank, which only exist in the
draft room, so those still come from the snapshots.

Each "stat view" is one value of the `stat1` URL parameter:
  S_PSR      projections for the games remaining (the 2026-27 projection before the season starts)
  S_S_2025   2025-26 season totals
  S_AS_2025  2025-26 per-game averages
"""

import re
import ssl
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

import certifi
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag

BASE_URL = "https://basketball.fantasysports.yahoo.com/nba"
PAGE_SIZE = 25
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

VIEWS: Dict[str, str] = {
    "projections": "S_PSR",
    "totals_2025_26": "S_S_2025",
    "averages_2025_26": "S_AS_2025",
}

# header text (without Yahoo's trailing "*" and icon glyphs) -> column name
_COUNTING_HEADERS: Dict[str, str] = {
    "3PTM": "3ptm",
    "PTS": "pts",
    "REB": "reb",
    "AST": "ast",
    "ST": "st",
    "BLK": "blk",
    "TO": "to",
}
_NO_VALUE = {"-", ""}

# Yahoo abbreviates a few long names on the player list. Listed explicitly: a fuzzy match could pair two
# different players without anyone noticing.
NAME_ALIASES: Dict[str, str] = {"N. Alexander-Walker": "Nickeil Alexander-Walker"}


def page_url(league_id: str, view_id: str, offset: int) -> str:
    """URL of one page of 25 players, ordered by pre-season rank."""
    return (
        f"{BASE_URL}/{league_id}/players?status=ALL&pos=P&cut_type=33&stat1={view_id}"
        f"&myteam=0&sort=OR&sdir=1&count={offset}"
    )


def download_view(league_id: str, view_id: str, pages: int, cache_dir: Path, delay: float = 1.5, refresh: bool = False) -> List[str]:
    """Return the HTML of the first `pages` pages of a view, using the on-disk cache unless `refresh`."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    # python.org builds on macOS ship without root certificates; certifi's bundle keeps verification on
    context = ssl.create_default_context(cafile=certifi.where())
    html_pages: List[str] = []
    for page in range(pages):
        offset = page * PAGE_SIZE
        cached = cache_dir / f"{view_id}_{offset:03d}.html"
        if refresh or not cached.exists():
            request = urllib.request.Request(page_url(league_id, view_id, offset), headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60, context=context) as response:
                cached.write_bytes(response.read())
            time.sleep(delay)  # be polite: this is somebody else's server
        html_pages.append(cached.read_text(encoding="utf-8", errors="replace"))
    return html_pages


def parse_players_page(html: str) -> pd.DataFrame:
    """Parse one page of the player list into one row per player."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", class_="Table-interactive")
    if table is None:
        raise ValueError("No player table in the page; Yahoo may have changed its layout or asked for a login")
    header_cells = table.find("thead").find_all("tr")[-1].find_all("th")
    headers = [_clean_header(cell.get_text(" ", strip=True)) for cell in header_cells]

    records: List[Dict[str, object]] = []
    for row in table.find("tbody").find_all("tr"):
        cells = row.find_all("td")
        if len(cells) != len(headers):
            raise ValueError(f"A row has {len(cells)} cells but the header has {len(headers)}")
        records.append(_parse_row(dict(zip(range(len(cells)), cells)), headers))
    return pd.DataFrame(records)


def parse_view(html_pages: List[str]) -> pd.DataFrame:
    """Parse and stack the pages of one view, checking nobody appears twice."""
    players = pd.concat([parse_players_page(html) for html in html_pages], ignore_index=True)
    players["player"] = players["player"].replace(NAME_ALIASES)
    if players["yahoo_id"].duplicated().any():
        raise ValueError("The same player appears on two pages; the ordering shifted while downloading")
    return players


def _clean_header(text: str) -> str:
    """Drop Yahoo's footnote asterisks and private-use icon glyphs from a header."""
    return re.sub(r"[-*]", "", text).strip()


def _parse_row(cells: Dict[int, Tag], headers: List[str]) -> Dict[str, object]:
    by_header: Dict[str, Tag] = {}
    for index, header in enumerate(headers):
        by_header.setdefault(header, cells[index])

    player_cell = by_header["Players"]
    link = player_cell.find("a", class_="name")
    team_and_positions = player_cell.select_one("span.D-b span.Fz-xxs")
    if link is None or team_and_positions is None:
        raise ValueError("A row has no player name or team and positions")
    team, positions = (part.strip() for part in team_and_positions.get_text(strip=True).split(" - ", 1))
    status_tag = player_cell.select_one("span.ysf-player-status span")

    record: Dict[str, object] = {
        "yahoo_id": int(link["data-ys-playerid"]),
        "player": link.get_text(strip=True),
        "team": team,
        "positions": positions.replace(" ", ""),
        "status": status_tag.get_text(strip=True) if status_tag else "",
        "gp": _number(by_header["GP"]),
        "pre_rank": _number(next(cell for header, cell in by_header.items() if header.startswith("Pre-Season"))),
        "mpg": _minutes(by_header["MPG"]),
    }
    record["fgm"], record["fga"] = _made_attempted(by_header["FGM / A"])
    record["fg_pct"] = _number(by_header["FG%"])
    record["ftm"], record["fta"] = _made_attempted(by_header["FTM / A"])
    record["ft_pct"] = _number(by_header["FT%"])
    for header, column in _COUNTING_HEADERS.items():
        record[column] = _number(by_header[header])
    return record


def _text(cell: Tag) -> str:
    return cell.get_text(" ", strip=True).replace(",", "")


def _number(cell: Tag) -> float:
    text = _text(cell)
    return np.nan if text in _NO_VALUE else float(text)


def _made_attempted(cell: Tag) -> Tuple[float, float]:
    text = _text(cell)
    if text in _NO_VALUE:
        return np.nan, np.nan
    made, attempted = (part.strip() for part in text.split("/"))
    if made in _NO_VALUE or attempted in _NO_VALUE:  # players with no stats show "-/-"
        return np.nan, np.nan
    return float(made), float(attempted)


def _minutes(cell: Tag) -> float:
    """Minutes per game: Yahoo writes "34:51" for totals and a plain number elsewhere, "-" if none."""
    text = _text(cell)
    if text in _NO_VALUE:
        return np.nan
    if ":" in text:
        minutes, seconds = text.split(":")
        return int(minutes) + int(seconds) / 60.0
    return float(text)
