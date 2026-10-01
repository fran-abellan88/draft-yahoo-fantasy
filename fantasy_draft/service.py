"""
What the dashboard asks of the draft engine, as plain functions over JSON-friendly dicts.

Kept separate from the HTTP server so it can be tested without a socket. The browser keeps the state
(the ordered list of picks) and sends all of it with every request, so the server holds no session.

Picks are logged in the order they happen. Whether each one is mine or somebody else's follows from the
snake order, so the state can never be inconsistent with the draft.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from fantasy_draft.availability import AdpWindow, AvailabilityRule, NormalAdpModel
from fantasy_draft.categories import CATEGORIES, categories_in
from fantasy_draft.draft import MY_SLOT, PICK_KINDS, ROSTER_SIZE, TEAMS, DraftState, Pick, my_picks
from fantasy_draft.flags import build_flags
from fantasy_draft.optimizer import FirstPickOption, Plan, Recommendation, plan_picks, team_profile
from fantasy_draft.scoring import METHODS, Bounds, category_scores, composite_score, compute_bounds

MAX_TOP_K = 50
DEFAULT_TOP_K = 10
PLANS_SHOWN = 5
ALTERNATIVES_SHOWN = 4
DISPLAY_STATS = ["pts", "reb", "ast", "3ptm", "st", "blk", "to", "fg_pct", "ft_pct", "fga", "fta"]


class RequestError(ValueError):
    """The request cannot be served; the message is safe to show to the user."""


# The only place the allowed availability settings are written down: (default, lowest, highest). The page gets them
# from /api/pool, so what it lets the user type and what the server accepts cannot drift apart.
RULE_LIMITS: Dict[str, Tuple[float, float, float]] = {
    "baseSd": (2.0, 0.1, 20.0),
    "sdPerAdp": (0.2, 0.0, 1.0),
    "threshold": (0.5, 0.05, 0.95),
    "slack": (3.0, 0.0, 60.0),
}


def parse_rule(raw: Optional[Dict[str, Any]]) -> AvailabilityRule:
    """Build an availability rule from the request, rejecting nonsense values."""
    raw = raw or {}
    kind = raw.get("type", "probability")
    if kind == "probability":
        return NormalAdpModel(
            base_sd=_bounded(raw, "baseSd", *RULE_LIMITS["baseSd"]),
            sd_per_adp=_bounded(raw, "sdPerAdp", *RULE_LIMITS["sdPerAdp"]),
            threshold=_bounded(raw, "threshold", *RULE_LIMITS["threshold"]),
        )
    if kind == "window":
        return AdpWindow(slack=_bounded(raw, "slack", *RULE_LIMITS["slack"]))
    raise RequestError(f"Unknown availability rule: {kind!r}")


def _bounded(raw: Dict[str, Any], key: str, default: float, low: float, high: float) -> float:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value) or not low <= value <= high:
        raise RequestError(f"{key} must be a number between {low} and {high}")
    return float(value)


def _num(value: Any, digits: int = 3) -> Optional[float]:
    """JSON-safe number: NaN becomes null."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


@dataclass
class DraftService:
    """The player pool, the league settings and everything computed from them."""

    players: pd.DataFrame
    slot: int = MY_SLOT
    rounds: int = 8
    teams: int = TEAMS
    keys: List[str] = field(init=False)
    bounds: Bounds = field(init=False)
    method_bounds: Dict[str, Bounds] = field(init=False)

    def __post_init__(self) -> None:
        self.keys = categories_in(self.players.columns)
        # Bounds cover every category so toggling one never moves the scores of the others
        self.bounds = compute_bounds(self.players, self.keys)
        self.method_bounds = {method: compute_bounds(self.players, self.keys, method=method) for method in METHODS}
        self._by_id = self.players.set_index("player_id")

    def pool_payload(self) -> Dict[str, Any]:
        """Static data the page needs once: league settings, categories and every player's stat line."""
        last_season_columns = {stat: f"{stat}_ly" for stat in DISPLAY_STATS}
        players: List[Dict[str, Any]] = []
        for _, row in self.players.iterrows():
            has_last_season = not math.isnan(row["gp_ly"])
            players.append(
                {
                    "id": row["player_id"],
                    "name": row["player"],
                    "team": row["team"],
                    "positions": row["pos_list"],
                    "status": row["status"],
                    "xrank": int(row["xrank"]),
                    "adp": _num(row["adp_est"], 1),  # the estimate where Yahoo shows none, flagged below
                    "adpEstimated": bool(row["adp_estimated"]),
                    "gp": int(row["gp"]),
                    "stats": {stat: _num(row[stat]) for stat in DISPLAY_STATS},
                    "lastSeason": (
                        {"gp": int(row["gp_ly"]), **{stat: _num(row[column]) for stat, column in last_season_columns.items()}}
                        if has_last_season
                        else None
                    ),
                }
            )
        return {
            "ruleLimits": {key: {"default": d, "min": low, "max": high} for key, (d, low, high) in RULE_LIMITS.items()},
            "league": {"teams": self.teams, "slot": self.slot, "rounds": self.rounds, "rosterSize": ROSTER_SIZE},
            "myPicks": my_picks(self.slot, ROSTER_SIZE, self.teams),
            "categories": [
                {"key": key, "label": CATEGORIES[key].label, "lowerIsBetter": CATEGORIES[key].lower_is_better} for key in self.keys
            ],
            "players": players,
        }

    def analyze(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Everything the page shows for one draft state and one choice of categories and availability rule."""
        keys = self._parse_categories(request.get("categories"))
        picks = self._parse_picks(request.get("picks"))
        rule = parse_rule(request.get("rule"))
        top_k = int(_bounded(request, "topK", DEFAULT_TOP_K, 1, MAX_TOP_K))
        method = request.get("method", "capped")
        if method not in METHODS:
            raise RequestError(f"method must be one of {list(METHODS)}")
        games_adjusted = request.get("gamesAdjusted", False)
        if not isinstance(games_adjusted, bool):
            raise RequestError("gamesAdjusted must be true or false")

        mine_numbers = set(my_picks(self.slot, ROSTER_SIZE, self.teams))
        numbered = list(enumerate(picks, start=1))
        mine = tuple(pick.player_id for number, pick in numbered if number in mine_numbers and pick.player_id is not None)
        taken = frozenset(pick.player_id for number, pick in numbered if number not in mine_numbers and pick.player_id is not None)
        state = DraftState(
            taken=taken,
            mine=mine,
            mine_outside=sum(1 for number, pick in numbered if number in mine_numbers and pick.kind == "outside"),
            other_outside=sum(1 for number, pick in numbered if number not in mine_numbers and pick.kind == "outside"),
            unseen=tuple(number for number, pick in numbered if pick.kind == "unseen"),
        )
        clock = self._clock(state)

        scores = composite_score(self.players, keys, self.method_bounds[method], games_adjusted, method)
        category = category_scores(self.players, keys, self.bounds) * 100.0  # bars stay on the 0-100 capped scale
        flags = build_flags(self.players, keys, self.bounds)
        drafted = {pick.player_id for pick in picks if pick.player_id is not None}

        recommendation_result = Recommendation([], [], False, 0)
        if not clock["draftComplete"]:
            try:
                recommendation_result = plan_picks(
                    self.players,
                    state,
                    keys,
                    self.method_bounds[method],
                    rule,
                    self.slot,
                    self.rounds,
                    top_k,
                    games_adjusted=games_adjusted,
                    method=method,
                )
            except ValueError as error:
                raise RequestError(str(error)) from error
        plans = recommendation_result.plans

        adp = self.players["adp_est"].to_numpy(dtype=float)
        next_mine = clock["nextMyPick"] if clock["nextMyPick"] is not None and clock["nextMyPick"] <= self._horizon_last() else None
        next_mine_probability = rule.probability(adp, next_mine, state.picks_made, state.unseen) if next_mine is not None else None

        pool = self._pool_rows(scores, category, flags, drafted, next_mine_probability)
        best = plans[0] if plans else None
        return {
            "clock": clock,
            "pool": pool,
            "plans": [self._plan_payload(plan, rule, state) for plan in plans[:PLANS_SHOWN]],
            "alternatives": self._alternatives(recommendation_result.options, best),
            "alternativesMode": "gone" if recommendation_result.assumed_gone else "instead",
            "search": {
                "truncated": recommendation_result.truncated,
                "nodes": recommendation_result.nodes,
                "mainNodes": recommendation_result.main_nodes,
                "maxOptionNodes": recommendation_result.max_option_nodes,
            },
            "recommendation": self._recommendation(best, next_mine),
            "roster": [{"id": pick.player_id, "kind": pick.kind, "pick": number} for number, pick in numbered if number in mine_numbers],
            "log": [{"pick": number, "kind": pick.kind, "id": pick.player_id, "mine": number in mine_numbers} for number, pick in numbered],
            "profile": {
                "roster": self._profile(list(mine), keys),
                "plan": self._profile(list(mine) + list(best.player_ids), keys) if best else None,
            },
            "horizonDone": next_mine is None,
        }

    def _parse_categories(self, raw: Any) -> List[str]:
        if not isinstance(raw, list) or not raw:
            raise RequestError("Select at least one category")
        unknown = [key for key in raw if key not in self.keys]
        if unknown:
            raise RequestError(f"Unknown categories: {unknown}")
        if len(set(raw)) != len(raw):
            raise RequestError("A category was selected twice")
        return [key for key in self.keys if key in raw]  # display order, whatever order the request used

    def _parse_picks(self, raw: Any) -> List[Pick]:
        """Read the pick log. An entry is a plain player id (the first format) or an object like {"kind": "player", "id": ...}."""
        entries = raw if raw is not None else []
        if not isinstance(entries, list):
            raise RequestError("picks must be a list of player ids or pick objects")
        picks = [self._parse_pick(entry, number) for number, entry in enumerate(entries, start=1)]
        ids = [pick.player_id for pick in picks if pick.player_id is not None]
        if len(set(ids)) != len(ids):
            raise RequestError("A player was picked twice")
        if len(picks) > self.teams * ROSTER_SIZE:
            raise RequestError("More picks than the draft has")
        mine_numbers = set(my_picks(self.slot, ROSTER_SIZE, self.teams))
        for number, pick in enumerate(picks, start=1):
            # I always know my own picks, so one of them cannot be a pick I did not see
            if pick.kind in ("unseen", "gone") and number in mine_numbers:
                raise RequestError(f"Pick {number} is yours, so it cannot be {pick.kind}: log your own pick")
        return picks

    def _parse_pick(self, entry: Any, number: int) -> Pick:
        if isinstance(entry, str):
            entry = {"kind": "player", "id": entry}
        if not isinstance(entry, dict):
            raise RequestError("picks must be a list of player ids or pick objects")
        extra = set(entry) - {"kind", "id"}
        kind = entry.get("kind", "player")
        if extra or kind not in PICK_KINDS:
            raise RequestError(f"Pick {number}: a pick has a kind ({', '.join(PICK_KINDS)}) and, for a player, an id")
        player_id = entry.get("id")
        if kind in ("outside", "unseen") and player_id is not None:
            raise RequestError(f"Pick {number}: a pick that is {kind} has no player id")
        if kind in ("player", "gone"):
            if not isinstance(player_id, str):
                raise RequestError(f"Pick {number}: a {kind} pick needs the player's id")
            if player_id not in self._by_id.index:
                raise RequestError(f"Unknown players: {[player_id]}")
        return Pick(kind, player_id)

    def _horizon_last(self) -> int:
        return my_picks(self.slot, self.rounds, self.teams)[-1]

    def _clock(self, state: DraftState) -> Dict[str, Any]:
        number = state.next_pick
        total = self.teams * ROSTER_SIZE
        upcoming = [pick for pick in my_picks(self.slot, ROSTER_SIZE, self.teams) if pick >= number]
        next_mine = upcoming[0] if upcoming else None
        round_number = (number - 1) // self.teams + 1
        position = (number - 1) % self.teams + 1
        on_clock = position if round_number % 2 == 1 else self.teams - position + 1
        return {
            "pick": number,
            "round": round_number,
            "pickInRound": position,
            "slotOnClock": on_clock,
            "reversed": round_number % 2 == 0,
            "isMine": on_clock == self.slot,
            "nextMyPick": next_mine,
            "picksUntilMine": None if next_mine is None else next_mine - number,
            "draftComplete": number > total,
        }

    def _pool_rows(
        self,
        scores: pd.Series,
        category: pd.DataFrame,
        flags: pd.DataFrame,
        drafted: set,
        availability: Optional[Any],
    ) -> List[Dict[str, Any]]:
        order = scores[~self.players["player_id"].isin(drafted)].rank(ascending=False, method="first")
        rows: List[Dict[str, Any]] = []
        for index, row in self.players.iterrows():
            if row["player_id"] in drafted:
                continue
            flag = flags.loc[index]
            rows.append(
                {
                    "id": row["player_id"],
                    "rank": int(order[index]),
                    "score": _num(scores[index], 1),
                    "categoryScores": {key: _num(value, 0) for key, value in category.loc[index].items()},
                    "availability": None if availability is None else _num(availability[index], 3),
                    "lastSeasonScore": _num(flag["ly_composite"], 1),
                    "lastSeasonDelta": _num(flag["ly_delta"], 1),
                    "flags": {
                        "noLastSeason": bool(flag["flag_ly_missing"]),
                        "smallSample": bool(flag["flag_ly_small_sample"]),
                        "diverges": bool(flag["flag_ly_diverges"]),
                        "lowGames": bool(flag["flag_low_projected_gp"]),
                    },
                }
            )
        rows.sort(key=lambda item: item["rank"])
        return rows

    def _plan_payload(self, plan: Plan, rule: AvailabilityRule, state: DraftState) -> Dict[str, Any]:
        steps = []
        for pick, pid in zip(plan.pick_numbers, plan.player_ids):
            adp = float(self._by_id.loc[pid, "adp_est"])
            odds = rule.probability(np.array([adp]), pick, state.picks_made, state.unseen)[0]
            steps.append({"pick": pick, "id": pid, "availability": _num(odds, 3)})
        return {"steps": steps, "totalScore": _num(plan.total_score, 1), "survival": _num(plan.survival, 3)}

    def _alternatives(self, options: List[FirstPickOption], best: Optional[Plan]) -> List[Dict[str, Any]]:
        """The best plan for each other first pick and how far behind the best plan it is (see `plan_picks` for the two modes)."""
        if best is None:
            return []
        # Not clamped at 0: an option can only beat the best plan if the search was cut short, and then the page
        # does not show the line. Float noise around zero is rounded away.
        shown: List[Dict[str, Any]] = []
        for option in options[:ALTERNATIVES_SHOWN]:
            gap = best.total_score - option.plan.total_score
            shown.append({"id": option.player_id, "behind": 0.0 if abs(gap) < 1e-9 else _num(gap, 1)})
        return shown

    def _recommendation(self, best: Optional[Plan], next_mine: Optional[int]) -> Optional[Dict[str, Any]]:
        if best is None or next_mine is None:
            return None
        return {"pick": next_mine, "id": best.player_ids[0]}

    def _profile(self, player_ids: List[str], keys: List[str]) -> Optional[Dict[str, Any]]:
        if not player_ids:
            return None
        profile = team_profile(self.players, player_ids, keys, self.bounds)
        return {
            key: {"total": _num(profile.loc[key, "total_per_game"], 2), "score": _num(profile.loc[key, "mean_score"], 0)} for key in keys
        }
