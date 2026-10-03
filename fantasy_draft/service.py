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

from fantasy_draft.autopick import next_for_clock, project, startable
from fantasy_draft.availability import AdpWindow, AvailabilityRule, NormalAdpModel
from fantasy_draft.categories import CATEGORIES, categories_in
from fantasy_draft.data import REFERENCE_POOL
from fantasy_draft.draft import MY_SLOT, PICK_KINDS, ROSTER_SIZE, TEAM_NAMES, TEAMS, DraftState, Pick, my_picks, slot_of_pick
from fantasy_draft.flags import build_flags
from fantasy_draft.lineup import ALL_MASK, POSITION_BIT, STARTING_SLOTS, assign_slots, position_mask
from fantasy_draft.league import league_table, rosters_by_slot
from fantasy_draft.needs import category_weights
from fantasy_draft.optimizer import FLEXIBILITY_BONUS, FirstPickOption, Plan, Recommendation, fill_picks, plan_picks, team_profile
from fantasy_draft.scoring import METHODS, Bounds, category_scores, composite_score, compute_bounds, last_season_scores

MAX_TOP_K = 50
DEFAULT_TOP_K = 10
PLANS_SHOWN = 5
RIVAL_ROUNDS = 8  # how many rounds another team plans ahead; its later picks are filled in (searching them all would be slow)
TIE_SCORE = 0.05  # roster-score gap below which two plans read as the same score (the page uses the same value)
ALTERNATIVES_SHOWN = 4
LOOK_FIRST_SHOWN = 3
LOOK_FIRST_FLOOR = 0.10  # below this chance a player is treated as gone and not suggested
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
    rounds: int = 10  # rounds planned exactly; the rest of the roster (ROSTER_SIZE) is filled in by score
    teams: int = TEAMS
    rehearsal: bool = False  # the mock draft: the other teams may pick automatically
    keys: List[str] = field(init=False)
    bounds: Bounds = field(init=False)
    method_bounds: Dict[str, Bounds] = field(init=False)

    def __post_init__(self) -> None:
        self.keys = categories_in(self.players.columns)
        # Bounds cover every category so toggling one never moves the scores of the others
        reference = self.players[self.players["xrank"] <= REFERENCE_POOL]  # the scale does not move when the pool grows
        self.bounds = compute_bounds(reference, self.keys)
        self.method_bounds = {method: compute_bounds(reference, self.keys, method=method) for method in METHODS}
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
            "league": {
                "teams": self.teams,
                "slot": self.slot,
                "rounds": self.rounds,
                "rosterSize": ROSTER_SIZE,
                "teamNames": list(TEAM_NAMES),
            },
            "rehearsal": self.rehearsal,
            "myPicks": my_picks(self.slot, ROSTER_SIZE, self.teams),
            "categories": [
                {"key": key, "label": CATEGORIES[key].label, "lowerIsBetter": CATEGORIES[key].lower_is_better} for key in self.keys
            ],
            "players": players,
        }

    def analyze(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Everything the page shows for one draft state and one choice of categories and availability rule."""
        keys, picks, rule, method, games_adjusted = self._parse_settings(request)
        top_k = int(_bounded(request, "topK", DEFAULT_TOP_K, 1, MAX_TOP_K))

        mine_numbers = set(my_picks(self.slot, ROSTER_SIZE, self.teams))
        numbered = list(enumerate(picks, start=1))
        state = self._state_for(self.slot, picks)
        clock = self._clock(state)

        needs_on = request.get("needs", False)
        if not isinstance(needs_on, bool):
            raise RequestError("needs must be true or false")
        weights: Optional[Dict[str, float]] = None
        ramp = 0.0
        if needs_on:
            rounds_done = len(picks) // self.teams
            so_far = league_table(self.players, rosters_by_slot(picks, self.teams), keys, rounds_done, self.slot, TEAM_NAMES)
            weights, ramp = category_weights(so_far["standing"], keys, rounds_done)
        scores = composite_score(self.players, keys, self.method_bounds[method], games_adjusted, method, weights)
        last_season = last_season_scores(self.players, keys, self.method_bounds[method], games_adjusted, method, weights)
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
                    weights=weights,
                    flexibility=FLEXIBILITY_BONUS,
                )
            except ValueError as error:
                raise RequestError(str(error)) from error
        plans = recommendation_result.plans

        adp = self.players["adp_est"].to_numpy(dtype=float)
        next_mine = clock["nextMyPick"] if clock["nextMyPick"] is not None and clock["nextMyPick"] <= self._horizon_last() else None
        next_mine_probability = rule.probability(adp, next_mine, state.picks_made, state.unseen) if next_mine is not None else None

        pool = self._pool_rows(scores, last_season, category, flags, drafted, next_mine_probability)
        self._add_unseen_risk(pool, adp, state)
        later_pick = self._later_pick(clock)
        self._add_later(pool, adp, state, rule, later_pick)
        best = plans[0] if plans else None
        fills = {id(plan): self._fill_plan(plan, state, keys, rule, method, games_adjusted, weights) for plan in plans[:PLANS_SHOWN]}
        return {
            "clock": clock,
            "pool": pool,
            "plans": [self._plan_payload(plan, rule, state, fills[id(plan)]) for plan in plans[:PLANS_SHOWN]],
            "alternatives": self._alternatives(recommendation_result.options, best, rule, state),
            "alternativesMode": "gone" if recommendation_result.assumed_gone else "instead",
            "search": {
                "truncated": recommendation_result.truncated,
                "nodes": recommendation_result.nodes,
                "mainNodes": recommendation_result.main_nodes,
                "maxOptionNodes": recommendation_result.max_option_nodes,
            },
            "recommendation": self._recommendation(best, next_mine),
            "laterPick": later_pick,
            "lineup": self._lineup(picks, mine_numbers),
            "bestAvailable": self._best_available(pool, picks, mine_numbers),
            "lookFirst": self._look_first(pool, best, rule, clock, state),
            "roster": [{"id": pick.player_id, "kind": pick.kind, "pick": number} for number, pick in numbered if number in mine_numbers],
            "log": [
                {
                    "pick": number,
                    "kind": pick.kind,
                    "id": pick.player_id,
                    "mine": number in mine_numbers,
                    "slot": slot_of_pick(number, self.teams),
                    "team": TEAM_NAMES[slot_of_pick(number, self.teams) - 1],
                }
                for number, pick in numbered
            ],
            "profile": {
                "roster": self._profile(list(state.mine), keys),
                "plan": self._profile(list(state.mine) + list(best.player_ids), keys) if best else None,
            },
            "horizonDone": next_mine is None,
            "league": self._league(picks, keys, list(best.player_ids) + [pid for _, pid in fills[id(best)]] if best else []),
            "needs": {
                "on": needs_on,
                "ramp": round(ramp, 2),
                "weights": None if weights is None else {key: round(value, 2) for key, value in weights.items()},
            },
        }

    def _parse_settings(self, request: Dict[str, Any]) -> Tuple[List[str], List[Pick], AvailabilityRule, str, bool]:
        """The choices every analysis shares: categories, the pick log, the availability rule, the score method and games."""
        keys = self._parse_categories(request.get("categories"))
        picks = self._parse_picks(request.get("picks"))
        rule = parse_rule(request.get("rule"))
        method = request.get("method", "capped")
        if method not in METHODS:
            raise RequestError(f"method must be one of {list(METHODS)}")
        games_adjusted = request.get("gamesAdjusted", False)
        if not isinstance(games_adjusted, bool):
            raise RequestError("gamesAdjusted must be true or false")
        return keys, picks, rule, method, games_adjusted

    def _state_for(self, slot: int, picks: List[Pick]) -> DraftState:
        """The draft as team `slot` sees it: its own players, everyone else's picks, and the picks nobody reported."""
        numbers = set(my_picks(slot, ROSTER_SIZE, self.teams))
        numbered = list(enumerate(picks, start=1))
        return DraftState(
            taken=frozenset(pick.player_id for number, pick in numbered if number not in numbers and pick.player_id is not None),
            mine=tuple(pick.player_id for number, pick in numbered if number in numbers and pick.player_id is not None),
            mine_outside=sum(1 for number, pick in numbered if number in numbers and pick.kind == "outside"),
            other_outside=sum(1 for number, pick in numbered if number not in numbers and pick.kind == "outside"),
            unseen=tuple(number for number, pick in numbered if pick.kind == "unseen"),
        )

    def project_league(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Every team completed by the same planner: what well-informed teams would end up with from this log.

        In snake order each team takes the first player of its own best plan (the same search the recommendation uses,
        for its slot), given every pick so far including the ones this projection made. So a poor logged pick lowers
        its team's projection and leaves more for the others, and nobody is first by construction. It is a pessimistic
        picture of a league of well-informed managers, not a forecast of this one. The need weights are not used.
        A team whose search finds no plan takes the best-ADP player that fits (`fallbacks` counts them).
        Slow at the start of the draft (about 0.1 s per pick still to make), so the page asks for it apart from `analyze`.
        """
        keys, picks, rule, method, games_adjusted = self._parse_settings(request)
        rosters = rosters_by_slot(picks, self.teams)
        simulated = list(picks)
        fallbacks = 0
        for number in range(len(picks) + 1, ROSTER_SIZE * self.teams + 1):
            slot = slot_of_pick(number, self.teams)
            chosen = self._planner_choice(slot, simulated, keys, rule, method, games_adjusted)
            if chosen is None:
                chosen = next_for_clock(self.players, simulated, self.teams)
                fallbacks += 1
            if chosen is None:
                break
            simulated.append(Pick("player", chosen))
            rosters[slot].append(chosen)
        table = league_table(self.players, rosters, keys, ROSTER_SIZE, self.slot, TEAM_NAMES)
        table["basis"] = f"projected, every team completed by the same planner, {ROSTER_SIZE} players each"
        table["fallbacks"] = fallbacks
        table["simulated"] = [pick.player_id for pick in simulated[len(picks):]]
        table["myPlayers"] = [pid for pid in rosters[self.slot] if pid is not None]  # the team this projection gives the user
        added: Dict[int, List[str]] = {slot: [] for slot in range(1, self.teams + 1)}
        for number, pick in enumerate(simulated[len(picks):], start=len(picks) + 1):
            if pick.player_id is not None:
                added[slot_of_pick(number, self.teams)].append(pick.player_id)
        table["rosters"] = self._team_rosters(picks, added)
        return table

    def _planner_choice(
        self, slot: int, picks: List[Pick], keys: List[str], rule: AvailabilityRule, method: str, games_adjusted: bool
    ) -> Optional[str]:
        """The first player of team `slot`'s best plan after `picks`: what the recommendation would say for that team.

        None when the search finds no plan (nobody fits). Only my team plans for the ticked categories (`keys`, my
        strategy); every other team plans for all of them. A team plans `rounds` rounds ahead (RIVAL_ROUNDS for the
        others); past that the pick is filled in by score, as in my own plan.
        """
        team_keys = keys if slot == self.slot else self.keys
        horizon = self.rounds if slot == self.slot else RIVAL_ROUNDS
        number = len(picks) + 1
        if not any(pick >= number for pick in my_picks(slot, horizon, self.teams)):
            filled = fill_picks(
                self.players, self._state_for(slot, picks), team_keys, self.method_bounds[method], rule, [number],
                games_adjusted=games_adjusted, method=method, flexibility=FLEXIBILITY_BONUS,
            )
            return filled[0][1] if filled else None
        try:
            found = plan_picks(
                self.players,
                self._state_for(slot, picks),
                team_keys,
                self.method_bounds[method],
                rule,
                slot,
                horizon,
                top_k=DEFAULT_TOP_K,
                games_adjusted=games_adjusted,
                method=method,
                option_count=0,
                flexibility=FLEXIBILITY_BONUS,
            )
        except ValueError:
            return None
        return found.plans[0].player_ids[0] if found.plans and found.plans[0].player_ids else None

    def predict_picks(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """What each other team should have picked, and what the team on the clock should pick, compared with what was logged.

        "Should" is given two ways, because they answer different questions: the planner (the first player of that team's
        own best plan for the ticked categories, the search the recommendation uses) and ADP (the best-ADP player who keeps
        that team's lineup startable). A pick that differs from them is not a mistake: the managers may be drafting for
        other categories or by Yahoo's ranking. The comparison is made from the log alone, each pick against the picks
        before it, so editing the log keeps it consistent. Only the real draft: in the mock draft the other teams pick by
        ADP, so the comparison says nothing. Unseen, gone and outside picks and my own picks are not compared.
        """
        if self.rehearsal:
            raise RequestError("Pick predictions are only available in the real draft")
        keys, picks, rule, method, games_adjusted = self._parse_settings(request)
        # The picks compared are other teams' picks, so their rank is by all categories, not by my ticked ones.
        scores = composite_score(self.players, self.keys, self.method_bounds[method], games_adjusted, method).to_numpy(dtype=float)
        adp = self.players["adp_est"].to_numpy(dtype=float)
        index = {pid: position for position, pid in enumerate(self.players["player_id"])}
        available = np.ones(len(index), dtype=bool)
        horizon = ROSTER_SIZE * self.teams
        rows: List[Dict[str, Any]] = []
        for number, pick in enumerate(picks, start=1):
            slot = slot_of_pick(number, self.teams)
            if pick.kind == "player" and pick.player_id is not None and slot != self.slot:
                before = picks[: number - 1]
                planner = self._planner_choice(slot, before, keys, rule, method, games_adjusted) if number <= horizon else None
                crowd = next_for_clock(self.players, before, self.teams)
                position = index[pick.player_id]
                rows.append(
                    {
                        "pick": number,
                        "slot": slot,
                        "id": pick.player_id,
                        "planner": planner,
                        "adp": crowd,
                        "matchPlanner": planner is not None and planner == pick.player_id,
                        "matchAdp": crowd is not None and crowd == pick.player_id,
                        "reach": _num(adp[position] - number, 1),  # positive: taken that many picks before his ADP
                        "scoreRank": int(1 + (scores[available] > scores[position]).sum()),
                    }
                )
            if pick.player_id is not None:
                available[index[pick.player_id]] = False
        number = len(picks) + 1
        clock: Optional[Dict[str, Any]] = None
        slot = slot_of_pick(number, self.teams)
        if number <= self.teams * ROSTER_SIZE and slot != self.slot:
            clock = {
                "pick": number,
                "slot": slot,
                "planner": self._planner_choice(slot, picks, keys, rule, method, games_adjusted) if number <= horizon else None,
                "adp": next_for_clock(self.players, picks, self.teams),
            }
        return {"clock": clock, "picks": rows, "summary": self._prediction_summary(rows)}

    def _prediction_summary(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """How often the compared picks matched the planner or ADP, and how early or late players went, overall and per team."""

        def tally(group: List[Dict[str, Any]]) -> Dict[str, Any]:
            reaches = [row["reach"] for row in group if row["reach"] is not None]
            return {
                "counted": len(group),
                "planner": sum(1 for row in group if row["matchPlanner"]),
                "adp": sum(1 for row in group if row["matchAdp"]),
                "either": sum(1 for row in group if row["matchPlanner"] or row["matchAdp"]),
                "meanReach": _num(sum(reaches) / len(reaches), 1) if reaches else None,
            }

        teams = [
            {"slot": slot, "name": TEAM_NAMES[slot - 1], **tally([row for row in rows if row["slot"] == slot])}
            for slot in range(1, self.teams + 1)
            if slot != self.slot
        ]
        return {**tally(rows), "teams": teams}

    def _league(self, picks: List[Pick], keys: List[str], planned: List[str]) -> Dict[str, Any]:
        """All 14 teams: the picks so far, and projected to a full roster.

        "So far" updates with every pick: it compares the first n picks of each team, n being the round now in progress,
        and a team that has not made its n-th pick yet is scaled up (see league.py), so it never looks weak only because
        its turn has not come.

        The projection keeps every logged pick, adds my best plan to my team and fills the other teams' missing picks
        automatically (autopick.py), protecting the players my plan counts on. It answers "what will the league look
        like", not "who will be available".
        """
        size = -(-len(picks) // self.teams)
        rosters = rosters_by_slot(picks, self.teams)
        table = league_table(self.players, rosters, keys, size, self.slot, TEAM_NAMES)
        table["basis"] = "so far"
        table["rosters"] = self._team_rosters(picks)
        added = project(self.players, picks, self.teams, ROSTER_SIZE * self.teams, self.slot, set(planned))
        projected_rosters = {slot: rosters[slot] + (planned if slot == self.slot else added[slot]) for slot in rosters}
        projected = league_table(self.players, projected_rosters, keys, ROSTER_SIZE, self.slot, TEAM_NAMES)
        projected["basis"] = f"projected, {ROSTER_SIZE} players each"
        projected["rosters"] = self._team_rosters(picks, {slot: (planned if slot == self.slot else added[slot]) for slot in rosters})
        table["projected"] = projected
        return table

    def autopick(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """The pick the team on the clock would make, for rehearsal: ADP with lineup limits, optionally blurred and seeded."""
        if not self.rehearsal:
            raise RequestError("Automatic picks are only available in the mock draft (open /mock): the real draft never picks for others")
        picks = self._parse_picks(request.get("picks"))
        if len(picks) >= self.teams * ROSTER_SIZE:
            raise RequestError("The draft is complete")
        seed = request.get("seed")
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            raise RequestError("seed must be a whole number")
        noise = request.get("noise", False)
        if not isinstance(noise, bool):
            raise RequestError("noise must be true or false")
        chosen = next_for_clock(self.players, picks, self.teams, seed, noise)
        if chosen is None:
            raise RequestError("Nobody left fits that team's lineup")
        return {"id": chosen, "pick": len(picks) + 1}

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
            "teamOnClock": TEAM_NAMES[on_clock - 1],
            "reversed": round_number % 2 == 0,
            "isMine": on_clock == self.slot,
            "nextMyPick": next_mine,
            "picksUntilMine": None if next_mine is None else next_mine - number,
            "draftComplete": number > total,
        }

    def _pool_rows(
        self,
        scores: pd.Series,
        last_season: pd.Series,
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
                    "lastSeasonScore": _num(last_season[index], 1),
                    "lastSeasonDelta": _num(scores[index] - last_season[index], 1),
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

    def _fill_plan(
        self,
        plan: Plan,
        state: DraftState,
        keys: List[str],
        rule: AvailabilityRule,
        method: str,
        games_adjusted: bool,
        weights: Optional[Dict[str, float]],
    ) -> List[Tuple[int, str]]:
        """The picks after the plan's horizon, up to a full roster, filled in by score (see `fill_picks`)."""
        last = plan.pick_numbers[-1] if plan.pick_numbers else 0
        numbers = [number for number in my_picks(self.slot, ROSTER_SIZE, self.teams) if number > last]
        if not numbers:
            return []
        return fill_picks(
            self.players, state, keys, self.method_bounds[method], rule, numbers, plan.player_ids, games_adjusted, method, weights,
            FLEXIBILITY_BONUS,
        )

    def _plan_payload(self, plan: Plan, rule: AvailabilityRule, state: DraftState, filled: List[Tuple[int, str]]) -> Dict[str, Any]:
        steps = []
        for pick, pid, is_filled in [(n, p, False) for n, p in zip(plan.pick_numbers, plan.player_ids)] + [(n, p, True) for n, p in filled]:
            adp = float(self._by_id.loc[pid, "adp_est"])
            odds = rule.probability(np.array([adp]), pick, state.picks_made, state.unseen)[0]
            steps.append({"pick": pick, "id": pid, "availability": _num(odds, 3), "filled": is_filled})
        return {"steps": steps, "totalScore": _num(plan.total_score, 1), "survival": _num(plan.survival, 3)}

    def _alternatives(
        self, options: List[FirstPickOption], best: Optional[Plan], rule: AvailabilityRule, state: DraftState
    ) -> List[Dict[str, Any]]:
        """The best plan for each other first pick and how far behind the best plan it is (see `plan_picks` for the two modes).

        When such a plan takes the recommended player at my next pick instead (the same team in the other order), `then`
        names him and his chance of lasting that long, so "same" is not mistaken for "no difference".
        """
        if best is None:
            return []
        # `behind` is the gap in roster score, the number the page shows as "Roster score", and is not clamped at 0:
        # plans are ranked by roster score plus the position bonus, so an option can be level or ahead on roster score
        # and still rank lower. `byPositions` marks exactly that, so the page can say the bonus decided it. Float
        # noise around zero is rounded away.
        shown: List[Dict[str, Any]] = []
        for option in options[:ALTERNATIVES_SHOWN]:
            gap = best.total_score - option.plan.total_score
            item: Dict[str, Any] = {"id": option.player_id, "behind": 0.0 if abs(gap) < 1e-9 else _num(gap, 1)}
            # Only when the best plan carries the larger bonus: with equal bonuses a tiny roster lead decided it
            bonus_edge = (best.value - best.total_score) - (option.plan.value - option.plan.total_score)
            if bonus_edge > 1e-9 and gap < TIE_SCORE:
                item["byPositions"] = True
            if len(option.plan.player_ids) > 1 and option.plan.player_ids[1] == best.player_ids[0]:
                adp = float(self._by_id.loc[best.player_ids[0], "adp_est"])
                odds = rule.probability(np.array([adp]), option.plan.pick_numbers[1], state.picks_made, state.unseen)[0]
                item["then"] = {"id": best.player_ids[0], "pick": option.plan.pick_numbers[1], "availability": _num(odds, 3)}
            shown.append(item)
        return shown

    def _later_pick(self, clock: Dict[str, Any]) -> Optional[int]:
        """On my turn, the pick after it that is also mine (and planned): "if I pass on him now, is he there then?"."""
        if not clock["isMine"] or clock["draftComplete"]:
            return None
        later = [number for number in my_picks(self.slot, self.rounds, self.teams) if number > clock["pick"]]
        return later[0] if later else None

    def _add_later(
        self, pool: List[Dict[str, Any]], adp: np.ndarray, state: DraftState, rule: AvailabilityRule, later_pick: Optional[int]
    ) -> None:
        """Per row, his chance of being there at my following pick (None unless it is my turn and another pick is planned)."""
        if later_pick is None:
            for row in pool:
                row["later"] = None
            return
        position = {pid: index for index, pid in enumerate(self.players["player_id"])}
        odds = rule.probability(adp, later_pick, state.picks_made, state.unseen)
        for row in pool:
            row["later"] = _num(odds[position[row["id"]]], 3)

    def _add_unseen_risk(self, pool: List[Dict[str, Any]], adp: np.ndarray, state: DraftState) -> None:
        """Per row, the chance he was taken at one of the unseen picks (0 with none), so Gone shows only where it matters."""
        if not state.unseen:
            for row in pool:
                row["unseenRisk"] = 0.0
            return
        position = {pid: index for index, pid in enumerate(self.players["player_id"])}
        survive = NormalAdpModel().probability(adp, state.next_pick, state.picks_made, state.unseen)
        for row in pool:
            row["unseenRisk"] = _num(1.0 - survive[position[row["id"]]], 3)

    def _roster_masks(self, picks: List[Pick], mine_numbers: set) -> List[Tuple[int, str]]:
        """My roster in pick order as (position mask, id or "" for a pick of a player outside the list)."""
        entries: List[Tuple[int, str]] = []
        for number, pick in enumerate(picks, start=1):
            if number not in mine_numbers:
                continue
            if pick.kind == "player" and pick.player_id is not None:
                entries.append((position_mask(self._by_id.loc[pick.player_id, "pos_list"]), pick.player_id))
            elif pick.kind == "outside":
                entries.append((ALL_MASK, ""))
        return entries

    def _lineup(self, picks: List[Pick], mine_numbers: set) -> Dict[str, Any]:
        """Who starts in each of the ten slots, who sits, and which positions one more player could still start at."""
        return self._lineup_of([mask for mask, _ in self._roster_masks(picks, mine_numbers)])

    @staticmethod
    def _lineup_of(masks: List[int]) -> Dict[str, Any]:
        """The lineup for any roster, given each player's position mask (indices refer to that list)."""
        owners = assign_slots(masks)
        started = {owner for owner in owners if owner is not None}
        return {
            "slots": [{"slot": name, "entry": owner} for (name, _), owner in zip(STARTING_SLOTS, owners)],
            "bench": [index for index in range(len(masks)) if index not in started],
            "canAdd": [position for position, bit in POSITION_BIT.items() if startable(masks + [bit])],
        }

    def _team_rosters(self, picks: List[Pick], projected: Optional[Dict[int, List[str]]] = None) -> Dict[int, Dict[str, Any]]:
        """Every team's players with their lineup: the logged picks, then (optionally) the players a projection adds.

        Each entry is `{id, pick, kind, projected}` (`id` is None for a pick not in the list), in pick order, and the lineup
        refers to entries by index, as for my own roster. An unseen pick is a pick whose player nobody reported: it cannot
        be placed, so it is listed apart in `unseen`. A "gone" pick has a player (assumed) and is placed like any other.
        `projected` maps a slot to the ids a projection gives it, which take that team's next picks in snake order.
        """
        entries: Dict[int, List[Dict[str, Any]]] = {slot: [] for slot in range(1, self.teams + 1)}
        unseen: Dict[int, List[int]] = {slot: [] for slot in range(1, self.teams + 1)}
        for number, pick in enumerate(picks, start=1):
            slot = slot_of_pick(number, self.teams)
            if pick.kind == "unseen":
                unseen[slot].append(number)
            else:
                entries[slot].append({"id": pick.player_id, "pick": number, "kind": pick.kind, "projected": False})
        last = ROSTER_SIZE * self.teams
        for slot, ids in (projected or {}).items():
            numbers = [n for n in range(len(picks) + 1, last + 1) if slot_of_pick(n, self.teams) == slot]
            for number, player_id in zip(numbers, ids):
                entries[slot].append({"id": player_id, "pick": number, "kind": "player", "projected": True})
        rosters: Dict[int, Dict[str, Any]] = {}
        for slot, team_entries in entries.items():
            masks = [
                ALL_MASK if entry["id"] is None else position_mask(self._by_id.loc[entry["id"], "pos_list"]) for entry in team_entries
            ]
            rosters[slot] = {"entries": team_entries, "unseen": unseen[slot], **self._lineup_of(masks)}
        return rosters

    def _best_available(self, pool: List[Dict[str, Any]], picks: List[Pick], mine_numbers: set) -> Optional[Dict[str, Any]]:
        """The best-scoring player left whom my lineup can still start, for when no plan covers the pick."""
        masks = [mask for mask, _ in self._roster_masks(picks, mine_numbers)]
        for row in pool:
            if startable(masks + [position_mask(self._by_id.loc[row["id"], "pos_list"])]):
                return {"id": row["id"], "score": row["score"]}
        return None

    def _look_first(
        self, pool: List[Dict[str, Any]], best: Optional[Plan], rule: AvailabilityRule, clock: Dict[str, Any], state: DraftState
    ) -> List[Dict[str, Any]]:
        """On my turn with unseen picks: better-scoring players left out for their odds, who may still be on the board.

        The user can see the draft room, so a player under the threshold but not long gone is worth a look before
        taking the recommendation. Empty when nothing is unseen (the pool is then exactly what is left) or it is not
        my turn.
        """
        if best is None or not clock["isMine"] or not state.unseen:
            return []
        scores = {row["id"]: row for row in pool}
        recommended = scores.get(best.player_ids[0])
        if recommended is None:
            return []
        found = [
            row
            for row in pool
            if row["score"] > recommended["score"]
            and row["availability"] is not None
            and LOOK_FIRST_FLOOR <= row["availability"] < rule.threshold
        ]
        found.sort(key=lambda row: -row["score"])
        return [{"id": row["id"], "availability": row["availability"]} for row in found[:LOOK_FIRST_SHOWN]]

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
