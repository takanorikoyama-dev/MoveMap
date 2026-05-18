"""DB の運用ステータスサマリを取得するモジュール.

`scripts/health_check.py` と `app/main.py` のサイドバーから共用される.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.shared.config import load_config
from app.shared.db import connect, initialize_schema
from app.shared.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TableSummary:
    name: str
    row_count: int
    latest_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class IndicatorStatus:
    indicator_id: str
    current_count: int  # current_values の行数
    history_count: int  # historical_values の行数
    has_model: bool
    latest_evaluated_at: datetime | None = None
    r_squared: float | None = None
    mae: float | None = None


@dataclass(frozen=True, slots=True)
class BatchStatus:
    job_id: int | None
    status: str | None  # success / partial / failure / running / None
    started_at: datetime | None
    ended_at: datetime | None
    records_processed: int | None
    error_details: str | None


@dataclass(frozen=True, slots=True)
class HealthSummary:
    db_exists: bool
    db_path: str
    tables: list[TableSummary] = field(default_factory=list)
    indicators: list[IndicatorStatus] = field(default_factory=list)
    latest_batch: BatchStatus | None = None
    error_count_last_7days: int = 0

    @property
    def has_current_data(self) -> bool:
        return any(ind.current_count > 0 for ind in self.indicators)

    @property
    def has_predictions(self) -> bool:
        return any(ind.has_model for ind in self.indicators)


def collect_health() -> HealthSummary:
    """現在の DB 状態を集計して返す.

    DB ファイル未生成時は `db_exists=False` で他は空.
    """
    config = load_config()
    db_path = Path(config.db_path)
    if not db_path.exists():
        return HealthSummary(db_exists=False, db_path=str(db_path))

    try:
        con = connect(protect_history=True)
    except Exception:  # noqa: BLE001
        logger.exception("DB 接続失敗")
        return HealthSummary(db_exists=True, db_path=str(db_path))

    try:
        initialize_schema(con)

        # 主要テーブル件数
        table_names = (
            "prefectures",
            "indicators",
            "data_sources",
            "current_values",
            "historical_values",
            "prediction_models",
            "model_evaluations",
            "predicted_values",
            "batch_jobs",
            "audit_logs",
        )
        tables: list[TableSummary] = []
        for tname in table_names:
            (cnt,) = con.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()  # noqa: S608
            latest: datetime | None = _table_latest(con, tname)
            tables.append(TableSummary(name=tname, row_count=int(cnt), latest_at=latest))

        # 指標別状況
        indicator_ids = [
            r[0]
            for r in con.execute(
                "SELECT id FROM indicators ORDER BY category, id"
            ).fetchall()
        ]
        indicators: list[IndicatorStatus] = []
        for ind in indicator_ids:
            (cur,) = con.execute(
                "SELECT COUNT(*) FROM current_values WHERE indicator_id = $1", [ind]
            ).fetchone()
            (his,) = con.execute(
                "SELECT COUNT(*) FROM historical_values WHERE indicator_id = $1", [ind]
            ).fetchone()
            model_row = con.execute(
                """
                SELECT pm.id, ev.r_squared, ev.mae, ev.evaluated_at
                FROM prediction_models pm
                LEFT JOIN model_evaluations ev ON ev.model_id = pm.id
                WHERE pm.indicator_id = $1
                ORDER BY pm.trained_at DESC, ev.evaluated_at DESC
                LIMIT 1
                """,
                [ind],
            ).fetchone()
            if model_row:
                _mid, r2, mae, eval_at = model_row
                indicators.append(
                    IndicatorStatus(
                        indicator_id=ind,
                        current_count=int(cur),
                        history_count=int(his),
                        has_model=True,
                        latest_evaluated_at=eval_at,
                        r_squared=float(r2) if r2 is not None else None,
                        mae=float(mae) if mae is not None else None,
                    )
                )
            else:
                indicators.append(
                    IndicatorStatus(
                        indicator_id=ind,
                        current_count=int(cur),
                        history_count=int(his),
                        has_model=False,
                    )
                )

        # 直近の BatchJob
        latest_batch: BatchStatus | None = None
        batch_row = con.execute(
            """
            SELECT id, status, started_at, ended_at, records_processed, error_details
            FROM batch_jobs
            ORDER BY started_at DESC
            LIMIT 1
            """
        ).fetchone()
        if batch_row:
            bid, status, started, ended, rp, err = batch_row
            latest_batch = BatchStatus(
                job_id=int(bid),
                status=str(status) if status else None,
                started_at=started,
                ended_at=ended,
                records_processed=int(rp) if rp is not None else None,
                error_details=err,
            )

        # 直近 7 日のエラーログ件数
        (error_count,) = con.execute(
            """
            SELECT COUNT(*) FROM audit_logs
            WHERE event_type IN ('batch.failure', 'batch.partial')
              AND occurred_at >= now() - INTERVAL 7 DAY
            """
        ).fetchone()

        return HealthSummary(
            db_exists=True,
            db_path=str(db_path),
            tables=tables,
            indicators=indicators,
            latest_batch=latest_batch,
            error_count_last_7days=int(error_count),
        )
    finally:
        con.close()


def _table_latest(con, table: str) -> datetime | None:  # type: ignore[no-untyped-def]
    """テーブルの最新タイムスタンプを返す(列名から自動推定)."""
    candidates = ("updated_at", "recorded_at", "predicted_at", "evaluated_at", "trained_at", "occurred_at", "started_at", "created_at")
    cols = {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}  # noqa: S608
    for col in candidates:
        if col in cols:
            row = con.execute(f"SELECT MAX({col}) FROM {table}").fetchone()  # noqa: S608
            if row and row[0] is not None:
                return row[0]  # type: ignore[no-any-return]
            return None
    return None


__all__ = [
    "BatchStatus",
    "HealthSummary",
    "IndicatorStatus",
    "TableSummary",
    "collect_health",
]
