"""scripts/seed.py の合成履歴投入の統合テスト."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import app.shared.config as config_mod
import app.shared.db as db_mod
import scripts.seed as seed_mod


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """seeds CSV をテスト用に差し替えた config."""
    db_path = tmp_path / "test.duckdb"
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()

    # 最小限の seeds CSV を生成
    (seeds_dir / "data_sources.csv").write_text(
        "id,name,url,license,update_frequency\n"
        "estat,e-Stat,https://x,MIT,monthly\n",
        encoding="utf-8",
    )
    (seeds_dir / "indicators.csv").write_text(
        "id,name_ja,name_en,unit,category,is_predictable,source_id\n"
        "price_index,物価,Price,p,must,true,estat\n"
        "land_price,地価,Land,JPY,must,true,estat\n"
        "rent_index,賃料,Rent,p,must,true,estat\n"
        "birth_count,出生,Birth,n,must,true,estat\n"
        "air_quality,空気,Air,ug,must,false,estat\n",
        encoding="utf-8",
    )
    # prefectures は 47 件必須(INV-BIZ-001)
    pref_lines = ["code,name_ja,name_en,region,centroid_lat,centroid_lon"]
    for i in range(1, 48):
        pref_lines.append(f"{i:02d},名{i},Name{i},R,35.0,139.0")
    (seeds_dir / "prefectures.csv").write_text("\n".join(pref_lines) + "\n", encoding="utf-8")

    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=seeds_dir,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(db_mod, "load_config", lambda: fake)
    monkeypatch.setattr(seed_mod, "load_config", lambda: fake)
    return fake


def test_seed_main_without_synthetic(isolated) -> None:  # type: ignore[no-untyped-def]
    rc = seed_mod.main([])
    assert rc == 0
    con = duckdb.connect(str(isolated.db_path))
    (pref_count,) = con.execute("SELECT COUNT(*) FROM prefectures").fetchone()
    (hist_count,) = con.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    con.close()
    assert pref_count == 47
    assert hist_count == 0


def test_seed_main_with_synthetic(isolated) -> None:  # type: ignore[no-untyped-def]
    rc = seed_mod.main(["--with-synthetic-history"])
    assert rc == 0
    con = duckdb.connect(str(isolated.db_path))
    (hist_count,) = con.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    con.close()
    # 4 指標 × 47 都道府県 × 24 ヶ月 = 4,512
    assert hist_count == 4 * 47 * 24


def test_synthetic_history_is_idempotent(isolated) -> None:  # type: ignore[no-untyped-def]
    """2 回 --with-synthetic-history を実行しても件数は増えない."""
    seed_mod.main(["--with-synthetic-history"])
    seed_mod.main(["--with-synthetic-history"])
    con = duckdb.connect(str(isolated.db_path))
    (hist_count,) = con.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    con.close()
    assert hist_count == 4 * 47 * 24


def test_synthetic_value_is_deterministic() -> None:
    """同じキーは同じ値."""
    a = seed_mod._synthetic_value("price_index", "13", 5)
    b = seed_mod._synthetic_value("price_index", "13", 5)
    assert a == b
    # 異なる都道府県は異なる値
    c = seed_mod._synthetic_value("price_index", "01", 5)
    assert a != c
