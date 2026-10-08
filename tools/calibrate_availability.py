"""
Check the "will he still be there" model against real drafts, from the text of a Yahoo draft board.

    python tools/calibrate_availability.py                       # every file in data/mock_drafts/
    python tools/calibrate_availability.py data/mock_drafts/x.txt
    python tools/calibrate_availability.py --center adp          # judge ADP instead of Yahoo's rank (the default)

Each file is the board as Yahoo's draft results page lists it: "Round N" headings, then lines like
"(3) Robb - Dončić, Luka (LAL - PG,SG)". Players are matched to the pool by name. Reports how far each pick fell from the
player's ADP, how well the model's chance of "taken at this pick, given still there" matches what happened, and the spread
(base + per-ADP) that fits these drafts best. A handful of drafts is a small sample: read the numbers as a direction.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fantasy_draft.availability import NormalAdpModel, _survival  # noqa: E402
from fantasy_draft.data import load_players  # noqa: E402
from fantasy_draft.names import normalize_name  # noqa: E402
from fantasy_draft.service import BASIS_SPREADS  # noqa: E402

LINE = re.compile(r"^\((\d+)\)\s+(.+?)\s+-\s+(.+?)\s+\(([A-Z]{2,3}) - ([A-Z,]+)\)\s*$")
TEAMS = 14
MOCK_DIR = Path(__file__).resolve().parent.parent / "data" / "mock_drafts"


def parse_board(text: str) -> List[Tuple[int, str, str]]:
    """The board as (overall pick, manager, "First Last"), in snake order of the rounds as listed."""
    picks: List[Tuple[int, str, str]] = []
    round_number = 0
    for line in text.splitlines():
        heading = re.match(r"^Round (\d+)$", line.strip())
        if heading:
            round_number = int(heading.group(1))
            continue
        found = LINE.match(line.strip())
        if found:
            seat, manager, name = int(found.group(1)), found.group(2), found.group(3)
            last, _, first = name.partition(", ")
            overall = (round_number - 1) * TEAMS + seat
            picks.append((overall, manager, f"{first} {last}".strip()))
    return sorted(picks)


def load_board(path: Path, players: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Picks matched to the pool: columns pick, manager, player_id, adp. Also the names that did not match."""
    by_name = {normalize_name(row.player): row.player_id for row in players.itertuples()}
    adp = dict(zip(players["player_id"], players["adp_est"]))
    rows, missing = [], []
    for pick, manager, name in parse_board(path.read_text()):
        player_id = by_name.get(normalize_name(name))
        if player_id is None:
            missing.append(f"{pick}: {name}")
        else:
            rows.append({"pick": pick, "manager": manager, "player_id": player_id, "adp": float(adp[player_id])})
    return pd.DataFrame(rows), missing


AUTO_SHARE = 0.6  # a manager who took the best-ranked player left at least this often is counted as autopick


def autopick_share(board: pd.DataFrame, players: pd.DataFrame) -> pd.Series:
    """For each manager, the share of his picks that were exactly the best-ranked (by XRank) player still available.

    Yahoo's autopick takes that player every time, so a manager near 1 abandoned the room or switched on autopick.
    """
    order = players.sort_values("xrank")["player_id"].tolist()
    gone: set = set()
    exact = []
    for _, row in board.sort_values("pick").iterrows():
        best = next(player for player in order if player not in gone)
        exact.append(best == row["player_id"])
        gone.add(row["player_id"])
    return board.assign(exact=exact).groupby("manager")["exact"].mean()


def hazards(board: pd.DataFrame, players: pd.DataFrame, model: NormalAdpModel, last_pick: int) -> pd.DataFrame:
    """For every pick and every player still there before it: the model's chance he is taken now, and whether he was."""
    adp_all = dict(zip(players["player_id"], players["adp_est"]))
    taken_at = dict(zip(board["player_id"], board["pick"]))
    out = []
    for n in range(1, last_pick + 1):
        for player_id, adp in adp_all.items():
            if taken_at.get(player_id, 10**6) < n:
                continue  # already gone
            sd = model.base_sd + model.sd_per_adp * adp
            before = max(float(_survival(n - 0.5, np.array([adp]), np.array([sd]))[0]), 1e-12)
            now = before - float(_survival(n + 0.5, np.array([adp]), np.array([sd]))[0])
            out.append({"pick": n, "predicted": min(1.0, now / before), "taken": float(taken_at.get(player_id) == n)})
    return pd.DataFrame(out)


def fit_spread(boards: List[pd.DataFrame], players: pd.DataFrame, last_pick: int) -> Tuple[float, float]:
    """Spread (base, per place in the ranking) that makes all the drafts most likely, each position Normal(centre, sd).

    Each draft counts on its own. Players in the pool whose centre is inside the drafted range but who were not taken are
    censored in that draft (they went after the last pick).
    """
    centre = players["adp_est"].to_numpy(dtype=float)
    drafts = []
    for board in boards:
        taken = dict(zip(board["player_id"], board["pick"]))
        pos = np.array([taken.get(pid, np.nan) for pid in players["player_id"]], dtype=float)
        drafted = ~np.isnan(pos)
        drafts.append((pos[drafted], centre[drafted], centre[~drafted & (centre < last_pick)]))

    def loss(params: np.ndarray) -> float:
        base, per = params
        total = 0.0
        for position, mid, left_over in drafts:
            sd = np.maximum(base + per * mid, 0.3)
            total += float(np.sum(np.log(sd) + 0.5 * ((position - mid) / sd) ** 2))
            tail = np.maximum(_survival(last_pick + 0.5, left_over, np.maximum(base + per * left_over, 0.3)), 1e-9)
            total -= float(np.sum(np.log(tail)))
        return total

    # A grid is enough for two parameters and keeps the tool to numpy and pandas
    best = min(((loss(np.array([base, per])), base, per) for base in np.arange(0.5, 8.01, 0.25) for per in np.arange(0.0, 0.61, 0.02)))
    return float(best[1]), float(best[2])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path, help="draft board text files (default: everything in data/mock_drafts/)")
    parser.add_argument(
        "--center", choices=("xrank", "adp"), default="xrank", help="the ranking the picks are judged against (default: %(default)s)"
    )
    args = parser.parse_args()
    files = args.files or sorted(MOCK_DIR.glob("*.txt"))
    if not files:
        sys.exit("No draft files found.")
    players = load_players()
    if args.center == "xrank":  # the same trick the dashboard uses: the rank stands in for ADP
        players = players.assign(adp_est=players["xrank"].astype(float))
    boards = []
    for path in files:
        board, missing = load_board(path, players)
        print(f"{path.name}: {len(board)} picks matched" + (f", not in the pool: {', '.join(missing)}" if missing else ""))
        boards.append(board)
    board = pd.concat(boards)
    last = int(board["pick"].max())

    residual = board["pick"] - board["adp"]
    print(f"\nPick minus {args.center} (positive: went later than that): mean {residual.mean():+.2f}, spread (sd) {residual.std():.2f}")
    board = board.assign(residual=residual, band=pd.cut(board["adp"], [0, 14, 28, 56, 84, 126, 200]))
    print(board.groupby("band", observed=True)["residual"].agg(["count", "mean", "std"]).round(2).to_string())

    humans = []
    for each in boards:
        share = autopick_share(each, players)
        humans.append(each[each["manager"].map(share) < AUTO_SHARE])
    total = sum(len(each["manager"].unique()) for each in boards)
    autos = total - sum(len(each["manager"].unique()) for each in humans)
    print(f"\n{autos} of {total} manager-drafts behaved like autopick; the table below is the other managers' picks only")
    human = pd.concat(humans)
    human = human.assign(residual=human["pick"] - human["adp"], band=pd.cut(human["adp"], [0, 14, 28, 56, 84, 126, 200]))
    print(human.groupby("band", observed=True)["residual"].agg(["count", "mean", "std"]).round(2).to_string())

    spreads = BASIS_SPREADS[args.center]
    model = NormalAdpModel(base_sd=spreads["baseSd"], sd_per_adp=spreads["sdPerAdp"])
    frame = pd.concat([hazards(each, players, model, last) for each in boards])
    frame["bin"] = pd.cut(frame["predicted"], [0, 0.02, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0], include_lowest=True)
    print(f"\nChance of being taken at this pick, given still there: model ({model.base_sd} + {model.sd_per_adp} per place) vs actual")
    grouped = frame.groupby("bin", observed=True)
    table = grouped.agg(cases=("taken", "size"), predicted=("predicted", "mean"), actual=("taken", "mean"))
    print(table.round(3).to_string())
    base, per = fit_spread(boards, players, last)
    print(f"\nBest-fitting spread: {base:.2f} + {per:.2f} per place (current {model.base_sd} + {model.sd_per_adp})")
    fitted = [base + per * adp for adp in (10, 40, 100)]
    current = [model.base_sd + model.sd_per_adp * adp for adp in (10, 40, 100)]
    show = lambda values: " / ".join(f"{x:.1f}" for x in values)  # noqa: E731
    print(f"Spread at ADP 10 / 40 / 100: {show(fitted)} (current {show(current)})")


if __name__ == "__main__":
    main()
