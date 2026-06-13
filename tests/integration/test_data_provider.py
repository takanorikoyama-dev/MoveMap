"""map_view/data_provider.py の統合テスト.

DB 存在/空/データあり の 3 ケースで fallback 挙動を検証.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import app.features.map_view.data_provider as dp_mod
import app.shared.config as config_mod
import app.shared.db as db_mod
from app.shared.db import initialize_schema


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """テスト用の Config を差し替え."""
    db_path = tmp_path / "test.duckdb"
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()
    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=seeds_dir,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(db_mod, "load_config", lambda: fake)
    monkeypatch.setattr(dp_mod, "load_config", lambda: fake)
    return fake


def _seed_basic(con: duckdb.DuckDBPyConnection) -> None:
    initialize_schema(con)
    con.execute(
        """
        INSERT INTO data_sources (id, name, url, license, update_frequency)
        VALUES ('estat', 'e-Stat', 'https://x', 'MIT', 'monthly')
        """
    )
    con.execute(
        """
        INSERT INTO indicators (id, name_ja, name_en, unit, category, is_predictable, source_id)
        VALUES ('price_index', '物価指数', 'PriceIndex', 'point', 'must', TRUE, 'estat'),
               ('air_quality', '空気質', 'AirQuality', 'ug/m3', 'must', FALSE, 'estat')
        """
    )
    con.execute(
        """
        INSERT INTO prefectures (code, name_ja, name_en, region, centroid_lat, centroid_lon)
        VALUES ('13', '東京都', 'Tokyo', '関東', 35.68, 139.69)
        """
    )


def test_values_for_returns_dummy_when_db_missing(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """DB ファイルが存在しないと dummy にフォールバック."""
    assert not isolated_config.db_path.exists()
    pack = dp_mod.values_for("price_index", "current")
    assert pack.availability.source == "dummy"
    assert len(pack.values) == 47


def test_values_for_returns_dummy_when_db_empty(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """DB は存在するが current_values が空 → dummy にフォールバック."""
    con = duckdb.connect(str(isolated_config.db_path))
    _seed_basic(con)
    con.close()

    pack = dp_mod.values_for("price_index", "current")
    assert pack.availability.source == "dummy"
    assert "空です" in (pack.availability.note or "")


def test_values_for_returns_db_when_current_populated(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """current_values が埋まっていれば DB ソース."""
    con = duckdb.connect(str(isolated_config.db_path))
    _seed_basic(con)
    con.execute(
        """
        INSERT INTO current_values (prefecture_code, indicator_id, value, status)
        VALUES ('13', 'price_index', 105.5, 'active')
        """
    )
    con.close()

    pack = dp_mod.values_for("price_index", "current")
    assert pack.availability.source == "db"
    assert pack.values["13"] == 105.5
    # 13 以外は None
    assert pack.values["01"] is None
    assert pack.availability.last_updated is not None


def test_values_for_predicted_uses_predicted_values(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """予測 horizon で predicted_values テーブルを参照."""
    con = duckdb.connect(str(isolated_config.db_path))
    _seed_basic(con)
    con.execute(
        """
        INSERT INTO prediction_models (indicator_id, model_type, parameters, features_used, training_data_range)
        VALUES ('price_index', 'arima', '{}', '[]', '{}')
        RETURNING id
        """
    )
    model_id = con.execute("SELECT id FROM prediction_models ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.execute(
        """
        INSERT INTO predicted_values (prefecture_code, indicator_id, horizon_years, value, quality_status, model_id)
        VALUES ('13', 'price_index', 5, 115.0, 'good', $1)
        """,
        [model_id],
    )
    # current_values も入れる(空判定回避用)
    con.execute(
        "INSERT INTO current_values (prefecture_code, indicator_id, value, status) VALUES ('13', 'price_index', 100.0, 'active')"
    )
    con.close()

    pack = dp_mod.values_for("price_index", "5y")
    assert pack.availability.source == "db"
    assert pack.values["13"] == 115.0


def test_values_for_no_prediction_falls_back_to_simple_extrapolation(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """quality_status='no_prediction' のとき、現在値 × 簡易年率で外挿補完.

    AI モデル(ARIMA/Prophet)が R² 不足で no_prediction を出した場合の救済策.
    UX 上「予測タブで全部 None」を避けるための新仕様(2026-05-26).
    """
    con = duckdb.connect(str(isolated_config.db_path))
    _seed_basic(con)
    con.execute(
        """
        INSERT INTO prediction_models (indicator_id, model_type, parameters, features_used, training_data_range)
        VALUES ('price_index', 'arima', '{}', '[]', '{}')
        """
    )
    model_id = con.execute("SELECT id FROM prediction_models ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.execute(
        """
        INSERT INTO predicted_values (prefecture_code, indicator_id, horizon_years, value, quality_status, model_id)
        VALUES ('13', 'price_index', 3, NULL, 'no_prediction', $1)
        """,
        [model_id],
    )
    con.execute(
        "INSERT INTO current_values (prefecture_code, indicator_id, value, status) VALUES ('13', 'price_index', 100.0, 'active')"
    )
    con.close()

    pack = dp_mod.values_for("price_index", "3y")
    assert pack.availability.source == "db"
    # price_index 年率 +0.5%、pref_code='13'(東京・三大都市圏)は補正 ×2.5
    # → 100.0 × (1 + 0.005 × 2.5)^3 = 100.0 × 1.0125^3 ≈ 103.80
    assert pack.values["13"] is not None
    assert abs(pack.values["13"] - 100.0 * (1.0125 ** 3)) < 0.01
    assert pack.availability.note is not None and ("簡易年率" in pack.availability.note or "県別" in pack.availability.note)


def test_values_for_non_predictable_indicator_at_future_uses_scenario_extrapolation(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """予測対象外指標(air_quality)を 5y で取ると、シナリオ外挿で値が変化する.

    旧仕様: 現在値継承で同じ値を返していた
    新仕様: _SIMPLE_FORECAST_RATES に登録された指標は県別の年率トレンドで外挿
    """
    con = duckdb.connect(str(isolated_config.db_path))
    _seed_basic(con)
    con.execute(
        "INSERT INTO current_values (prefecture_code, indicator_id, value, status) VALUES ('13', 'air_quality', 8.0, 'active')"
    )
    con.close()

    pack = dp_mod.values_for("air_quality", "5y")
    assert pack.availability.source == "db"
    # air_quality 年率 -1.0%、pref_code='13'(東京・三大都市圏)は補正 ×1.5
    # → 実年率 -1.5%、5年で 8.0 × (1 - 0.015)^5 ≈ 7.418
    assert pack.values["13"] is not None
    assert abs(pack.values["13"] - 8.0 * (1.0 - 0.015) ** 5) < 0.01
    assert pack.availability.note and ("外挿" in pack.availability.note or "継承" in pack.availability.note)


def test_latest_model_for_returns_dummy_when_no_model(isolated_config) -> None:  # type: ignore[no-untyped-def]
    info = dp_mod.latest_model_for("price_index")
    assert info.availability.source == "dummy"


def test_latest_model_for_returns_db_when_available(isolated_config) -> None:  # type: ignore[no-untyped-def]
    con = duckdb.connect(str(isolated_config.db_path))
    _seed_basic(con)
    con.execute(
        """
        INSERT INTO prediction_models (indicator_id, model_type, parameters, features_used, training_data_range)
        VALUES ('price_index', 'arima', '{"order":[2,1,2]}', '["lag_1"]', '{"from":"2020-01","to":"2024-12"}')
        """
    )
    model_id = con.execute("SELECT id FROM prediction_models ORDER BY id DESC LIMIT 1").fetchone()[0]
    con.execute(
        """
        INSERT INTO model_evaluations (model_id, r_squared, mae, evaluation_period)
        VALUES ($1, 0.78, 1.2, '{"from":"2024-06","to":"2024-12"}')
        """,
        [model_id],
    )
    con.close()

    info = dp_mod.latest_model_for("price_index")
    assert info.availability.source == "db"
    assert info.model_type == "arima"
    assert info.r_squared == 0.78
    assert info.mae == 1.2


def test_latest_model_for_non_predictable_returns_dummy(isolated_config) -> None:  # type: ignore[no-untyped-def]
    info = dp_mod.latest_model_for("air_quality")
    assert info.availability.source == "dummy"


def test_prefecture_full_table_falls_back_to_dummy(isolated_config) -> None:  # type: ignore[no-untyped-def]
    """DB なし時、7指標 × 4時点の表が dummy で埋まる(全指標が外挿で horizon ごとに動く)."""
    table = dp_mod.prefecture_full_table("13")
    assert set(table.keys()) == {
        "price_index", "land_price", "rent_index", "birth_count",
        "air_quality", "disaster_risk", "transport_access",
    }
    # 現在値はすべて埋まる
    for ind in table:
        assert table[ind]["current"] is not None
    # 主要4指標の未来は埋まる
    assert table["price_index"]["5y"] is not None
    # 予測対象外指標も horizon でシナリオ外挿により値が変化(継承ではない)
    assert table["air_quality"]["5y"] != table["air_quality"]["current"]
    assert table["disaster_risk"]["3y"] != table["disaster_risk"]["current"]
    assert table["transport_access"]["10y"] != table["transport_access"]["current"]
