"""SF-013 UpsertCurrentValues — 現在値テーブル更新.

参照: outputs/06_system_design/04_データ設計.md (current_values)
不変条件: INV-DATA-001/002 (FK + 一意性、DB 制約で担保)
状態遷移: status='active' を設定.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import duckdb

from app.shared.logger import get_logger

logger = get_logger(__name__)


def upsert_current_values(
    con: duckdb.DuckDBPyConnection,
    records: Iterable[dict[str, Any]],
) -> int:
    """正規化済みレコードを current_values へ upsert する.

    Args:
        con: DuckDB 接続.
        records: NormalizeData 出力 [{prefecture_code, indicator_id, value, measured_at}].

    Returns:
        upsert 件数.
    """
    count = 0
    for r in records:
        con.execute(
            """
            INSERT INTO current_values
                (prefecture_code, indicator_id, value, measured_at, updated_at, status)
            VALUES ($1, $2, $3, $4, now(), 'active')
            ON CONFLICT (prefecture_code, indicator_id) DO UPDATE SET
                value = excluded.value,
                measured_at = excluded.measured_at,
                updated_at = now(),
                status = 'active'
            """,
            [r["prefecture_code"], r["indicator_id"], r.get("value"), r.get("measured_at")],
        )
        count += 1
    logger.info(f"upsert_current_values: {count} rows")
    return count
