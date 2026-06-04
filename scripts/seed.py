"""DuckDB を初期化し、seeds CSV からマスタを投入する(冪等).

`--with-synthetic-history` フラグで主要4指標 × 47都道府県 × 24ヶ月の合成履歴を投入し、
API キーなしでも `RunBatch` / UI 動作確認が可能になる.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import date
from pathlib import Path

from app.shared.config import load_config
from app.shared.db import connect, initialize_schema
from app.shared.logger import get_logger

logger = get_logger(__name__)

PREDICTABLE_INDICATORS = ("price_index", "land_price", "rent_index", "birth_count")
INDICATOR_BASE_VALUES: dict[str, float] = {
    # 各指標を「実 API 取得時の単位」と揃える(display 側の /10000 スケーリングと整合).
    "price_index": 100.0,        # 物価指数(無次元、全国 100 基準)
    "land_price": 250_000.0,     # 地価(円/㎡、display で /10000 → 万円/㎡)
    "rent_index": 80_000.0,      # 賃料(円/月、display で /10000 → 万円/月、東京 ~9 万 / 鹿児島 ~4 万 を意識)
    "birth_count": 70_000.0,     # 出生数(人/年、display で /10000 → 万人/年、全国合計 70 万人前後)
}
SYNTHETIC_MONTHS = 24


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _row_exists(con, table: str, key_column: str, key_value: str) -> bool:  # type: ignore[no-untyped-def]
    (cnt,) = con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {key_column} = $1",  # noqa: S608 - table/column は内部定数
        [key_value],
    ).fetchone()
    return int(cnt) > 0


def seed_data_sources(con) -> int:  # type: ignore[no-untyped-def]
    """マスタ投入(冪等). DuckDB の FK 厳格制約により、INSERT は存在チェック後のみ実行."""
    config = load_config()
    rows = _read_csv(config.seeds_dir / "data_sources.csv")
    for r in rows:
        if _row_exists(con, "data_sources", "id", r["id"]):
            continue
        con.execute(
            """
            INSERT INTO data_sources (id, name, url, license, update_frequency)
            VALUES ($1,$2,$3,$4,$5)
            """,
            [r["id"], r["name"], r["url"], r["license"], r["update_frequency"]],
        )
    return len(rows)


def seed_indicators(con) -> int:  # type: ignore[no-untyped-def]
    config = load_config()
    rows = _read_csv(config.seeds_dir / "indicators.csv")
    for r in rows:
        if _row_exists(con, "indicators", "id", r["id"]):
            continue
        is_predictable = r["is_predictable"].strip().lower() == "true"
        con.execute(
            """
            INSERT INTO indicators (id, name_ja, name_en, unit, category, is_predictable, source_id)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            """,
            [r["id"], r["name_ja"], r["name_en"], r["unit"], r["category"], is_predictable, r["source_id"]],
        )
    return len(rows)


def seed_prefectures(con) -> int:  # type: ignore[no-untyped-def]
    config = load_config()
    rows = _read_csv(config.seeds_dir / "prefectures.csv")
    for r in rows:
        if _row_exists(con, "prefectures", "code", r["code"]):
            continue
        con.execute(
            """
            INSERT INTO prefectures (code, name_ja, name_en, region, centroid_lat, centroid_lon)
            VALUES ($1,$2,$3,$4,$5,$6)
            """,
            [r["code"], r["name_ja"], r["name_en"], r["region"], float(r["centroid_lat"]), float(r["centroid_lon"])],
        )
    return len(rows)


def _hash_unit(*parts: str) -> float:
    """文字列を [0, 1) にハッシュ."""
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _synthetic_value(indicator_id: str, prefecture_code: str, month_index: int) -> float:
    """都道府県・指標・月インデックスから合成値を生成(deterministic)."""
    base = INDICATOR_BASE_VALUES[indicator_id]
    pref_offset = (_hash_unit(indicator_id, prefecture_code) - 0.5) * 0.2 * base  # ±10%
    trend = month_index * 0.005 * base  # 月あたり 0.5% の上昇トレンド
    noise = (_hash_unit(indicator_id, prefecture_code, str(month_index)) - 0.5) * 0.02 * base
    return base + pref_offset + trend + noise


def seed_synthetic_history(con, months: int = SYNTHETIC_MONTHS) -> int:  # type: ignore[no-untyped-def]
    """主要4指標 × 47都道府県 × N ヶ月の合成履歴を historical_values に投入する.

    冪等: 既に historical_values が存在する場合は再投入を行わない.
    """
    (existing,) = con.execute("SELECT COUNT(*) FROM historical_values").fetchone()
    if existing > 0:
        logger.info(f"historical_values 既存 {existing} 行のため合成 seed をスキップ")
        return 0

    pref_codes = [row[0] for row in con.execute("SELECT code FROM prefectures ORDER BY code").fetchall()]
    rows: list[tuple] = []  # type: ignore[type-arg]
    for indicator_id in PREDICTABLE_INDICATORS:
        for pref in pref_codes:
            for m in range(months):
                year = 2024 + m // 12
                mon = m % 12 + 1
                value = _synthetic_value(indicator_id, pref, m)
                rows.append((pref, indicator_id, value, date(year, mon, 1)))

    con.executemany(
        """
        INSERT INTO historical_values (prefecture_code, indicator_id, value, measured_at)
        VALUES ($1, $2, $3, $4)
        """,
        rows,
    )
    logger.info(f"合成履歴データ投入: {len(rows)} 行({len(PREDICTABLE_INDICATORS)} 指標 × {len(pref_codes)} 都道府県 × {months} ヶ月)")
    return len(rows)


# 予測対象外指標の合成値レンジ(現在値用、demo モードで使用)
NON_PREDICTABLE_RANGES: dict[str, float] = {
    "air_quality": 12.0,        # PM2.5 μg/m³ の典型値
    "disaster_risk": 3.0,       # 1〜5 スコア中央
    "transport_access": 3.5,    # 1〜5 スコア中央
    "public_safety": 7.0,       # 刑法犯認知件数 / 人口千人(全国平均約 5〜10/千人)
    "net_migration": 0.0,       # 転入超過率(‰)。0 周辺で県別オフセット ±数 ‰
}


def seed_synthetic_current(con) -> int:  # type: ignore[no-untyped-def]
    """全 7 指標 × 47 都道府県の current_values を合成値で埋める.

    冪等: 既に current_values が存在する場合はスキップ.
    UI を実データ風に見せる demo 用. 本番運用では run_batch で上書きされる.
    """
    (existing,) = con.execute("SELECT COUNT(*) FROM current_values").fetchone()
    if existing > 0:
        logger.info(f"current_values 既存 {existing} 行のため合成 current をスキップ")
        return 0

    pref_codes = [row[0] for row in con.execute("SELECT code FROM prefectures ORDER BY code").fetchall()]
    indicator_rows = con.execute("SELECT id, is_predictable FROM indicators ORDER BY id").fetchall()

    rows: list[tuple] = []  # type: ignore[type-arg]
    today = date.today()
    for ind, is_predictable in indicator_rows:
        for pref in pref_codes:
            if is_predictable:
                # 最新月インデックスの値を採用(履歴の最終時点と整合)
                value = _synthetic_value(ind, pref, SYNTHETIC_MONTHS - 1)
            else:
                # 予測対象外: 中央値の周辺で都道府県別オフセット
                base = NON_PREDICTABLE_RANGES.get(ind, 1.0)
                offset = (_hash_unit(ind, pref) - 0.5) * 0.4 * base  # ±20%
                value = base + offset
            rows.append((pref, ind, value, today))

    con.executemany(
        """
        INSERT INTO current_values (prefecture_code, indicator_id, value, measured_at, status)
        VALUES ($1, $2, $3, $4, 'active')
        """,
        rows,
    )
    logger.info(f"合成現在値データ投入: {len(rows)} 行({len(indicator_rows)} 指標 × {len(pref_codes)} 都道府県)")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--with-synthetic-history",
        action="store_true",
        help="主要4指標の合成履歴データ(24ヶ月)を投入(API キーなしのデモ用)",
    )
    parser.add_argument(
        "--with-synthetic-current",
        action="store_true",
        help="7指標 × 47都道府県の現在値を合成値で投入(demo モード)",
    )
    args = parser.parse_args(argv)

    logger.info("DuckDB を初期化し seeds を投入します")
    con = connect(protect_history=False)  # 履歴初回投入のため protection なしで接続
    try:
        initialize_schema(con)
        ds = seed_data_sources(con)
        ind = seed_indicators(con)
        pref = seed_prefectures(con)
        logger.info(f"seeds 投入完了: data_sources={ds}, indicators={ind}, prefectures={pref}")

        # INV-BIZ-001: prefectures は 47 件でなければならない
        (count,) = con.execute("SELECT COUNT(*) FROM prefectures").fetchone()
        if count != 47:
            raise RuntimeError(f"INV-BIZ-001 違反: prefectures は 47 件であるべきだが {count} 件")
        logger.info("INV-BIZ-001 (prefectures = 47) OK")

        if args.with_synthetic_history:
            seed_synthetic_history(con)
        if args.with_synthetic_current:
            seed_synthetic_current(con)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
