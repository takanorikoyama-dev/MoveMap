"""scripts/demo.py の統合テスト + 合成 current_values の検証.

`demo.py --quick --no-geojson` を実行して、UI が DB 経由でデータを取れる状態になるかを検証.
ARIMA 学習を回さないため数秒で完走する.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import app.features.map_view.data_provider as dp_mod
import app.features.map_view.data_status as ds_mod
import app.shared.config as config_mod
import app.shared.db as db_mod
import scripts.demo as demo_mod
import scripts.health_check as hc_mod
import scripts.seed as seed_mod


@pytest.fixture()
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """seeds はプロジェクト実体を、DB は tmp_path を使う."""
    db_path = tmp_path / "movemap.duckdb"
    project_seeds = Path(__file__).resolve().parents[2] / "seeds"

    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=project_seeds,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(db_mod, "load_config", lambda: fake)
    monkeypatch.setattr(seed_mod, "load_config", lambda: fake)
    monkeypatch.setattr(dp_mod, "load_config", lambda: fake)
    monkeypatch.setattr(ds_mod, "load_config", lambda: fake)
    return fake


def test_seed_with_synthetic_current_populates_current_values(isolated) -> None:  # type: ignore[no-untyped-def]
    rc = seed_mod.main(["--with-synthetic-history", "--with-synthetic-current"])
    assert rc == 0

    con = duckdb.connect(str(isolated.db_path))
    try:
        # 9 指標 × 47 都道府県 = 423 セル(2026-05-26 治安+人口流入追加)
        (count,) = con.execute("SELECT COUNT(*) FROM current_values").fetchone()
        assert count == 9 * 47

        # 主要指標は historical の最新と整合(同じ値)
        (hist_last,) = con.execute(
            """
            SELECT value FROM historical_values
            WHERE prefecture_code = '13' AND indicator_id = 'price_index'
            ORDER BY measured_at DESC LIMIT 1
            """
        ).fetchone()
        (cur,) = con.execute(
            "SELECT value FROM current_values WHERE prefecture_code = '13' AND indicator_id = 'price_index'"
        ).fetchone()
        assert abs(hist_last - cur) < 1e-6
    finally:
        con.close()


def test_seed_with_synthetic_current_is_idempotent(isolated) -> None:  # type: ignore[no-untyped-def]
    seed_mod.main(["--with-synthetic-history", "--with-synthetic-current"])
    seed_mod.main(["--with-synthetic-history", "--with-synthetic-current"])

    con = duckdb.connect(str(isolated.db_path))
    try:
        (count,) = con.execute("SELECT COUNT(*) FROM current_values").fetchone()
        assert count == 9 * 47
    finally:
        con.close()


def test_demo_quick_mode_populates_db(isolated) -> None:  # type: ignore[no-untyped-def]
    """demo --quick --no-geojson で seed + 合成 current/history まで完了."""
    rc = demo_mod.main(["--quick", "--no-geojson"])
    assert rc == 0  # health_check が healthy(0)

    con = duckdb.connect(str(isolated.db_path))
    try:
        (pref,) = con.execute("SELECT COUNT(*) FROM prefectures").fetchone()
        (hist,) = con.execute("SELECT COUNT(*) FROM historical_values").fetchone()
        (cur,) = con.execute("SELECT COUNT(*) FROM current_values").fetchone()
        assert pref == 47
        assert hist == 4 * 47 * 24
        assert cur == 9 * 47  # 9 指標 × 47 都道府県(2026-05-26 治安+人口流入追加)
    finally:
        con.close()


def test_demo_quick_mode_ui_data_provider_reads_db(isolated) -> None:  # type: ignore[no-untyped-def]
    """demo 実行後、data_provider が DB ソースを返す."""
    demo_mod.main(["--quick", "--no-geojson"])

    pack = dp_mod.values_for("price_index", "current")
    assert pack.availability.source == "db"
    assert pack.values["13"] is not None


def test_health_check_after_demo_returns_healthy(isolated, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    """demo 後の health_check は exit code 1(バッチ未実行 = warning 扱いではなく healthy)."""
    demo_mod.main(["--quick", "--no-geojson"])

    rc = hc_mod.main([])
    assert rc == 0  # バッチ履歴なし = healthy(最初の起動と同じ扱い)


def test_demo_no_geojson_flag_skips_fetch(isolated, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """--no-geojson は fetch_geojson を呼ばない."""
    called = {"n": 0}

    def fake_fetch_main() -> int:
        called["n"] += 1
        return 0

    import scripts.fetch_geojson as fg
    monkeypatch.setattr(fg, "main", fake_fetch_main)

    demo_mod.main(["--quick", "--no-geojson"])
    assert called["n"] == 0
