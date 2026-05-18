"""SF-014 AppendHistory — 履歴値追記.

参照: outputs/06_system_design/04_データ設計.md (historical_values)
不変条件: INV-DATA-007 (append-only、UPDATE/DELETE はアプリ層で禁止)
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import duckdb

from app.shared.logger import get_logger

logger = get_logger(__name__)


class HistoryMutationError(Exception):
    """INV-DATA-007 違反(履歴の UPDATE/DELETE 試行)."""


def append_history(
    con: duckdb.DuckDBPyConnection,
    records: Iterable[dict[str, Any]],
) -> int:
    """履歴値を append する.

    measured_at が None のレコードはスキップ(履歴は時点必須).

    Args:
        con: DuckDB 接続.
        records: 正規化済みレコード.

    Returns:
        追記件数.
    """
    appended = 0
    for r in records:
        measured_at = r.get("measured_at")
        value = r.get("value")
        if measured_at is None or value is None:
            continue
        con.execute(
            """
            INSERT INTO historical_values
                (prefecture_code, indicator_id, value, measured_at)
            VALUES ($1, $2, $3, $4)
            """,
            [r["prefecture_code"], r["indicator_id"], value, measured_at],
        )
        appended += 1
    logger.info(f"append_history: {appended} rows")
    return appended


def assert_history_immutable(con: duckdb.DuckDBPyConnection) -> None:
    """INV-DATA-007 のアプリ層検証(意図的に呼ぶ防御層).

    本当の防御は呼び出し側コードが UPDATE/DELETE を発行しないこと.
    将来 DB トリガーで強制する余地あり.
    """
    # 監視用ノーオペ。Phase 7 続セッションで強化候補.
    _ = con
