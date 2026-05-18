"""バッチ実行関連エンティティ(Aggregate Root: BatchExecution)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

BatchStatus = Literal["running", "success", "partial", "failure"]


@dataclass(frozen=True, slots=True)
class BatchJob:
    id: int
    job_type: str
    started_at: datetime
    ended_at: datetime | None
    status: BatchStatus
    records_processed: int
    error_details: str | None


@dataclass(frozen=True, slots=True)
class AuditLog:
    """append-only."""

    id: int
    event_type: str
    target: str | None
    actor: str
    occurred_at: datetime
    details: dict[str, Any] | None
