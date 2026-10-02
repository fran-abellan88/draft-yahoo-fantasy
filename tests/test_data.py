"""Tests for loading the player pool, against the real files and small synthetic ones."""

from pathlib import Path
from typing import Dict, List

import pandas as pd
import pytest

from fantasy_draft.categories import categories_in
from fantasy_draft.data import COUNTING_STATS, load_players
from fantasy_draft.names import normalize_name, slugify


@pytest.fixture(scope="module")
def players() -> pd.DataFrame:
    return load_players()


def test_loads_the_top_150_with_unique_ids(players: pd.DataFrame) -> None:
    assert len(players) == 150
    assert players["xrank"].tolist() == list(range(1, 151))
    assert players["player_id"].is_unique


def test_counting_stats_are_converted_to_per_game(players: pd.DataFrame) -> None:
    jokic = players[players["player"] == "Nikola Jokic"].iloc[0]
    assert jokic["pts"] == pytest.approx(1978 / 71)
    assert jokic["to"] == pytest.approx(242 / 71)
    assert jokic["gp"] == 71
    assert jokic["fga"] == pytest.approx(1283 / 71)
    assert jokic["fg_pct"] == pytest.approx(0.574)


def test_per_game_values_are_plausible(players: pd.DataFrame) -> None:
    assert players["pts"].between(5, 35).all()
    assert players["to"].between(0.5, 4.5).all()
    assert players["fga"].between(2, 25).all()


def test_last_season_is_joined_from_totals_and_blank_when_missing(players: pd.DataFrame) -> None:
    jokic = players[players["player"] == "Nikola Jokic"].iloc[0]
    assert jokic["pts_ly"] == pytest.approx(1799 / 65)
    assert jokic["gp_ly"] == 65
    assert jokic["fga_ly"] == pytest.approx(1132 / 65)
    haliburton = players[players["player"] == "Tyrese Haliburton"].iloc[0]
    assert haliburton[[f"{stat}_ly" for stat in COUNTING_STATS]].isna().all()
    assert players["pts_ly"].isna().sum() == 8


def test_positions_are_parsed(players: pd.DataFrame) -> None:
    giannis = players[players["player"] == "Giannis Antetokounmpo"].iloc[0]
    assert giannis["pos_list"] == ["PF", "C"]


def test_percentage_impact_rewards_volume_and_efficiency(players: pd.DataFrame) -> None:
    by_name = players.set_index("player")
    assert by_name.loc["Nikola Jokic", "fg_impact"] > 0.5  # efficient on 18 attempts a game
    assert by_name.loc["Ja Morant", "fg_impact"] < 0  # below the pool's shooting rate
    # the same efficiency on far fewer attempts is worth much less
    efficient_low_volume = players[(players["fg_pct"] > 0.60) & (players["fga"] < 8)]
    assert (efficient_low_volume["fg_impact"] < by_name.loc["Nikola Jokic", "fg_impact"]).all()


def test_baseline_is_makes_over_attempts_and_impact_sums_to_about_zero(players: pd.DataFrame) -> None:
    baselines = players.attrs["baselines"]
    assert 0.44 < baselines["fg"] < 0.50
    assert 0.75 < baselines["ft"] < 0.85
    # Totals sum to exactly zero; per-game values weight each player by his games, so only roughly
    weighted = (players["fg_impact"] * players["gp"]).sum()
    assert abs(weighted) < 1e-6


def test_all_nine_categories_are_available(players: pd.DataFrame) -> None:
    assert categories_in(players.columns) == ["fg_pct", "ft_pct", "3ptm", "pts", "reb", "ast", "st", "blk", "to"]


def test_slugify_and_normalize_handle_accents_and_punctuation() -> None:
    assert slugify("Jaren Jackson Jr.") == "jaren-jackson-jr"
    assert slugify("Kel'el Ware") == "kel-el-ware"
    assert slugify("Nikola Jokić") == "nikola-jokic"
    assert normalize_name("Alperen Şengün") == "alperensengun"


YAHOO_HEADER = "yahoo_id,player,team,positions,status,gp,pre_rank,mpg,fgm,fga,fg_pct,ftm,fta,ft_pct,3ptm,pts,reb,ast,st,blk,to"


def _yahoo_row(player_id: int, name: str, gp: float, fgm: float = 400, fga: float = 800, ftm: float = 200, fta: float = 250) -> str:
    return f'{player_id},{name},AAA,"PG,SG",,{gp},1,,{fgm},{fga},0.5,{ftm},{fta},0.8,100,1400,300,300,70,30,150'


def _write(tmp_path: Path, name: str, header: str, rows: List[str]) -> Path:
    path = tmp_path / name
    path.write_text(header + "\n" + "\n".join(rows) + "\n")
    return path


def _files(tmp_path: Path, snapshot_rows: List[str], projection_rows: List[str], total_rows: List[str]) -> Dict[str, Path]:
    return {
        "snapshot_path": _write(tmp_path, "snapshot.csv", "xrank,rank,adp,player", snapshot_rows),
        "projections_path": _write(tmp_path, "proj.csv", YAHOO_HEADER, projection_rows),
        "totals_path": _write(tmp_path, "totals.csv", YAHOO_HEADER, total_rows),
    }


def test_impact_math_on_a_tiny_pool(tmp_path: Path) -> None:
    files = _files(
        tmp_path,
        ["1,1,1.0,Player A", "2,2,2.0,Player B"],
        [_yahoo_row(1, "Player A", 80, fgm=500, fga=1000), _yahoo_row(2, "Player B", 40, fgm=100, fga=300)],
        [_yahoo_row(1, "Player A", 80, fgm=400, fga=1000), _yahoo_row(2, "Player B", 0, fgm=0, fga=0)],
    )
    players = load_players(**files).set_index("player")
    baseline = (500 + 100) / (1000 + 300)
    assert players.attrs["baselines"]["fg"] == pytest.approx(baseline)
    assert players.loc["Player A", "fg_impact"] == pytest.approx((500 - baseline * 1000) / 80)
    assert players.loc["Player B", "fg_impact"] == pytest.approx((100 - baseline * 300) / 40)
    # last season is scored against the same projected baseline so the two are comparable
    assert players.loc["Player A", "fg_impact_ly"] == pytest.approx((400 - baseline * 1000) / 80)


def test_a_player_with_no_games_last_season_has_blank_last_season_stats(tmp_path: Path) -> None:
    files = _files(
        tmp_path,
        ["1,1,1.0,Player A"],
        [_yahoo_row(1, "Player A", 80)],
        [_yahoo_row(1, "Player A", 0, fgm=0, fga=0, ftm=0, fta=0)],
    )
    player = load_players(**files).iloc[0]
    assert pd.isna(player["pts_ly"]) and pd.isna(player["fg_impact_ly"])


def test_snapshot_player_missing_from_yahoo_is_an_error(tmp_path: Path) -> None:
    files = _files(tmp_path, ["1,1,1.0,Player A", "2,2,2.0,Player Z"], [_yahoo_row(1, "Player A", 80)], [_yahoo_row(1, "Player A", 80)])
    with pytest.raises(ValueError, match=r"not found.*\[2\]"):
        load_players(**files)


def test_zero_projected_games_is_an_error(tmp_path: Path) -> None:
    files = _files(tmp_path, ["1,1,1.0,Player A"], [_yahoo_row(1, "Player A", 0)], [_yahoo_row(1, "Player A", 80)])
    with pytest.raises(ValueError, match="positive"):
        load_players(**files)
