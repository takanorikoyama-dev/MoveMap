"""DuckDB 接続と DDL 定義.

INV-DATA-001..008 を物理スキーマ上の制約として表現する.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb

from app.shared.config import load_config

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS prefectures (
        code         VARCHAR(2)  PRIMARY KEY,
        name_ja      VARCHAR(20) NOT NULL,
        name_en      VARCHAR(40) NOT NULL,
        region       VARCHAR(20) NOT NULL,
        centroid_lat DOUBLE      NOT NULL,
        centroid_lon DOUBLE      NOT NULL,
        created_at   TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_sources (
        id               VARCHAR(20)  PRIMARY KEY,
        name             VARCHAR(80)  NOT NULL,
        url              VARCHAR(200) NOT NULL,
        license          VARCHAR(80)  NOT NULL,
        update_frequency VARCHAR(20)  NOT NULL CHECK (
            update_frequency IN ('monthly','quarterly','yearly','irregular')
        ),
        created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS indicators (
        id              VARCHAR(20)  PRIMARY KEY,
        name_ja         VARCHAR(40)  NOT NULL,
        name_en         VARCHAR(40)  NOT NULL,
        unit            VARCHAR(20)  NOT NULL,
        category        VARCHAR(20)  NOT NULL CHECK (category IN ('must','should','could')),
        is_predictable  BOOLEAN      NOT NULL DEFAULT FALSE,
        source_id       VARCHAR(20)  NOT NULL REFERENCES data_sources(id),
        created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS current_values (
        prefecture_code VARCHAR(2)  NOT NULL REFERENCES prefectures(code),
        indicator_id    VARCHAR(20) NOT NULL REFERENCES indicators(id),
        value           DOUBLE,
        measured_at     DATE,
        updated_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
        status          VARCHAR(10) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','missing','stale')),
        PRIMARY KEY (prefecture_code, indicator_id)
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS seq_historical_values START 1",
    """
    CREATE TABLE IF NOT EXISTS historical_values (
        id              BIGINT      PRIMARY KEY DEFAULT nextval('seq_historical_values'),
        prefecture_code VARCHAR(2)  NOT NULL REFERENCES prefectures(code),
        indicator_id    VARCHAR(20) NOT NULL REFERENCES indicators(id),
        value           DOUBLE      NOT NULL,
        measured_at     DATE        NOT NULL,
        recorded_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS seq_prediction_models START 1",
    """
    CREATE TABLE IF NOT EXISTS prediction_models (
        id                   BIGINT      PRIMARY KEY DEFAULT nextval('seq_prediction_models'),
        indicator_id         VARCHAR(20) NOT NULL REFERENCES indicators(id),
        model_type           VARCHAR(20) NOT NULL CHECK (model_type IN ('arima','sarima','prophet')),
        trained_at           TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
        parameters           JSON        NOT NULL,
        features_used        JSON        NOT NULL,
        training_data_range  JSON        NOT NULL
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS seq_model_evaluations START 1",
    """
    CREATE TABLE IF NOT EXISTS model_evaluations (
        id                BIGINT     PRIMARY KEY DEFAULT nextval('seq_model_evaluations'),
        model_id          BIGINT     NOT NULL REFERENCES prediction_models(id),
        r_squared         DOUBLE     NOT NULL,
        mae               DOUBLE     NOT NULL,
        evaluated_at      TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP,
        evaluation_period JSON       NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS predicted_values (
        prefecture_code VARCHAR(2)   NOT NULL REFERENCES prefectures(code),
        indicator_id    VARCHAR(20)  NOT NULL REFERENCES indicators(id),
        horizon_years   SMALLINT     NOT NULL CHECK (horizon_years IN (3,5,10)),
        value           DOUBLE,
        ci_lower        DOUBLE,
        ci_upper        DOUBLE,
        quality_status  VARCHAR(20)  NOT NULL DEFAULT 'good'
                        CHECK (quality_status IN ('good','no_prediction')),
        model_id        BIGINT       REFERENCES prediction_models(id),
        predicted_at    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (prefecture_code, indicator_id, horizon_years)
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS seq_batch_jobs START 1",
    """
    CREATE TABLE IF NOT EXISTS batch_jobs (
        id                BIGINT      PRIMARY KEY DEFAULT nextval('seq_batch_jobs'),
        job_type          VARCHAR(20) NOT NULL,
        started_at        TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ended_at          TIMESTAMP,
        status            VARCHAR(20) NOT NULL DEFAULT 'running'
                          CHECK (status IN ('running','success','partial','failure')),
        records_processed INTEGER     DEFAULT 0,
        error_details     TEXT
    )
    """,
    "CREATE SEQUENCE IF NOT EXISTS seq_audit_logs START 1",
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id           BIGINT      PRIMARY KEY DEFAULT nextval('seq_audit_logs'),
        event_type   VARCHAR(40) NOT NULL,
        target       VARCHAR(40),
        actor        VARCHAR(20) NOT NULL DEFAULT 'system',
        occurred_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
        details      JSON
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_indicators_source ON indicators(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_current_values_indicator ON current_values(indicator_id)",
    "CREATE INDEX IF NOT EXISTS idx_historical_pref_ind_date ON historical_values(prefecture_code, indicator_id, measured_at)",
    "CREATE INDEX IF NOT EXISTS idx_models_indicator_trained ON prediction_models(indicator_id, trained_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_evaluations_model ON model_evaluations(model_id)",
    "CREATE INDEX IF NOT EXISTS idx_predicted_indicator_horizon ON predicted_values(indicator_id, horizon_years)",
    "CREATE INDEX IF NOT EXISTS idx_batchjobs_started ON batch_jobs(started_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_occurred ON audit_logs(occurred_at DESC)",
]


class HistoryProtectionError(RuntimeError):
    """INV-DATA-007 違反: historical_values への UPDATE/DELETE/TRUNCATE が試行された."""


_HISTORY_FORBIDDEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bUPDATE\s+historical_values\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\s+historical_values\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+(?:TABLE\s+)?historical_values\b", re.IGNORECASE),
)


def _assert_history_immutable(sql: str) -> None:
    """SQL 文字列に historical_values への破壊的操作が含まれていないか確認.

    INV-DATA-007 を DB 層で強制する(DEC-013 対応の第二段階).
    """
    if "historical_values" not in sql.lower():
        return
    for pattern in _HISTORY_FORBIDDEN_PATTERNS:
        if pattern.search(sql):
            preview = " ".join(sql.split())[:200]
            raise HistoryProtectionError(
                f"INV-DATA-007 違反: historical_values への破壊的操作は禁止 — {preview}"
            )


class HistoryProtectedConnection:
    """`historical_values` への UPDATE/DELETE/TRUNCATE を実行時に拒否する DuckDB 接続ラッパー.

    INSERT/SELECT/CREATE 等の他操作は素通し.
    `con.execute(...).fetchone()` のようなチェーン呼出を維持するため、execute は self を返す.
    DuckDB は内部状態で結果を保持するため、後続の `fetchone` は `__getattr__` で内側に委譲される.
    """

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def execute(self, query: str, *args: Any, **kwargs: Any) -> HistoryProtectedConnection:
        _assert_history_immutable(query)
        self._con.execute(query, *args, **kwargs)
        return self

    def executemany(self, query: str, *args: Any, **kwargs: Any) -> HistoryProtectedConnection:
        _assert_history_immutable(query)
        self._con.executemany(query, *args, **kwargs)
        return self

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> HistoryProtectedConnection:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._con, name)


def connect(
    db_path: Path | str | None = None,
    *,
    protect_history: bool = True,
) -> duckdb.DuckDBPyConnection:
    """DuckDB に接続する.

    Args:
        db_path: 省略時は Config から読み込む.
        protect_history: True(既定)で `HistoryProtectedConnection` でラップ.
            DDL 初期化など破壊的操作が必要な内部用途は False で生 connection を返す.

    Returns:
        ラップ済み or 生の DuckDB 接続(API 互換).
    """
    path = Path(db_path) if db_path is not None else load_config().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = duckdb.connect(str(path))
    if not protect_history:
        return raw
    return HistoryProtectedConnection(raw)  # type: ignore[return-value]


def initialize_schema(con: duckdb.DuckDBPyConnection) -> None:
    """DDL を流して全テーブル + 索引を作成する(冪等)."""
    for stmt in DDL_STATEMENTS:
        con.execute(stmt)


@contextmanager
def transaction(con: duckdb.DuckDBPyConnection) -> Iterator[duckdb.DuckDBPyConnection]:
    """トランザクション境界."""
    con.execute("BEGIN TRANSACTION")
    try:
        yield con
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
