"""pytest 共通フィクスチャ."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest

duckdb = pytest.importorskip("duckdb")


@pytest.fixture()
def db() -> Iterator:
    """in-memory DuckDB + DDL 適用済の接続を提供."""
    from app.shared.db import initialize_schema

    con = duckdb.connect(":memory:")
    initialize_schema(con)
    # マスタを軽量に投入(テストに必要な最小限)
    con.execute(
        """
        INSERT INTO data_sources (id, name, url, license, update_frequency)
        VALUES ('estat', 'e-Stat', 'https://example.test', 'MIT', 'monthly')
        """
    )
    con.execute(
        """
        INSERT INTO indicators (id, name_ja, name_en, unit, category, is_predictable, source_id)
        VALUES ('price_index', '物価指数', 'PriceIndex', 'point', 'must', TRUE, 'estat'),
               ('land_price', '地価', 'LandPrice', 'JPY/m2', 'must', TRUE, 'estat'),
               ('rent_index', '賃料相場', 'RentIndex', 'point', 'must', TRUE, 'estat'),
               ('birth_count', '出生数', 'BirthCount', 'per_1000pop', 'must', TRUE, 'estat'),
               ('air_quality', '空気質', 'AirQuality', 'ug/m3', 'must', FALSE, 'estat')
        """
    )
    con.execute(
        """
        INSERT INTO prefectures (code, name_ja, name_en, region, centroid_lat, centroid_lon)
        VALUES ('01', '北海道', 'Hokkaido', '北海道', 43.06, 141.34),
               ('13', '東京都', 'Tokyo', '関東', 35.68, 139.69),
               ('47', '沖縄県', 'Okinawa', '沖縄', 26.21, 127.68)
        """
    )
    try:
        yield con
    finally:
        con.close()


@pytest.fixture()
def db_with_history(db):  # type: ignore[no-untyped-def]
    """予測パイプラインテスト用: db + 主要4指標 × 3都道府県 × 24ヶ月の履歴を投入."""
    indicators = ("price_index", "land_price", "rent_index", "birth_count")
    prefectures = ("01", "13", "47")
    base_value = {"price_index": 100.0, "land_price": 200000.0, "rent_index": 95.0, "birth_count": 7.0}

    rows: list[tuple[str, str, float, date]] = []
    for ind in indicators:
        for pref in prefectures:
            for month in range(24):
                year = 2024 + month // 12
                mon = month % 12 + 1
                # 緩やかな上昇トレンド + 軽微なノイズ(都道府県でオフセット)
                offset = {"01": -2.0, "13": 0.0, "47": -5.0}[pref]
                value = base_value[ind] + offset + month * 0.05 * base_value[ind] / 24
                rows.append((pref, ind, value, date(year, mon, 1)))

    db.executemany(
        """
        INSERT INTO historical_values (prefecture_code, indicator_id, value, measured_at)
        VALUES ($1, $2, $3, $4)
        """,
        rows,
    )
    return db
