"""Tests for loading the player pool, against the real 2026-27 / 2025-26 files and small synthetic ones."""

from pathlib import Path

import pandas as pd
import pytest

from fantasy_draft.data import COUNTING_STATS, load_players, slugify


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
    # rates are left as they are
    assert jokic["fg_pct"] == pytest.approx(0.574)


def test_per_game_values_are_plausible(players: pd.DataFrame) -> None:
    assert players["pts"].between(5, 35).all()
    assert players["to"].between(0.5, 4.5).all()


def test_last_season_is_joined_and_blank_when_missing(players: pd.DataFrame) -> None:
    jokic = players[players["player"] == "Nikola Jokic"].iloc[0]
    assert jokic["pts_ly"] == pytest.approx(27.7)
    assert jokic["gp_ly"] == 65
    haliburton = players[players["player"] == "Tyrese Haliburton"].iloc[0]
    assert haliburton[[f"{stat}_ly" for stat in COUNTING_STATS]].isna().all()
    assert players["pts_ly"].isna().sum() == 8


def test_positions_are_parsed(players: pd.DataFrame) -> None:
    giannis = players[players["player"] == "Giannis Antetokounmpo"].iloc[0]
    assert giannis["pos_list"] == ["PF", "C"]


def test_slugify_handles_punctuation() -> None:
    assert slugify("Jaren Jackson Jr.") == "jaren-jackson-jr"
    assert slugify("Kel'el Ware") == "kel-el-ware"
    assert slugify("Shai Gilgeous-Alexander") == "shai-gilgeous-alexander"


def _write(path: Path, rows: str, header: str) -> Path:
    path.write_text(header + "\n" + rows + "\n")
    return path


PROJECTIONS_HEADER = "xrank,rank,adp,player,team,positions,status,gp,fg_pct,ft_pct,3ptm,pts,reb,ast,st,blk,to"
AVERAGES_HEADER = "xrank,rank,adp,player,team,positions,status,gp,fg_pct,ft_pct,3ptm,pts,reb,ast,st,blk,to"


def test_player_name_mismatch_between_files_is_an_error(tmp_path: Path) -> None:
    projections = _write(tmp_path / "p.csv", '1,1,1.0,Player A,AAA,"PG,SG",,70,0.5,0.8,100,1400,300,300,70,30,150', PROJECTIONS_HEADER)
    averages = _write(tmp_path / "a.csv", '1,1,1.0,Player B,AAA,"PG,SG",,70,0.5,0.8,1.4,20.0,4.3,4.3,1.0,0.4,2.1', AVERAGES_HEADER)
    with pytest.raises(ValueError, match="disagree"):
        load_players(projections, averages)


def test_zero_projected_games_is_an_error(tmp_path: Path) -> None:
    projections = _write(tmp_path / "p.csv", '1,1,1.0,Player A,AAA,PG,,0,0.5,0.8,100,1400,300,300,70,30,150', PROJECTIONS_HEADER)
    averages = _write(tmp_path / "a.csv", "1,1,1.0,Player A,AAA,PG,,,,,,,,,,,", AVERAGES_HEADER)
    with pytest.raises(ValueError, match="positive"):
        load_players(projections, averages)
