"""TC-DP-04 / TC-DP-05 FetchExternalData の単体テスト(アダプタ未実装をモック)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

import app.features.data_pipeline.usecases.fetch_external_data as feu
from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.shared.http_client import HttpRetryExhausted, HttpSchemaError


class _SuccessAdapter(DataSourceAdapter):
    source_id = "estat"

    def fetch(self) -> Iterator[dict[str, Any]]:
        yield {"indicator_id": "price_index", "prefecture_code": "13", "value": 105.5, "measured_at": "2024-01-01"}
        yield {"indicator_id": "price_index", "prefecture_code": "01", "value": 99.9, "measured_at": "2024-01-01"}

    def last_updated(self) -> str | None:
        return None


class _RetryExhaustedAdapter(DataSourceAdapter):
    source_id = "estat"

    def fetch(self) -> Iterator[dict[str, Any]]:
        raise HttpRetryExhausted("simulated 3-attempt failure")

    def last_updated(self) -> str | None:
        return None


class _SchemaErrorAdapter(DataSourceAdapter):
    source_id = "estat"

    def fetch(self) -> Iterator[dict[str, Any]]:
        raise HttpSchemaError("simulated bad response shape")

    def last_updated(self) -> str | None:
        return None


def test_fetch_returns_outcome_with_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feu, "_adapter_for", lambda _: _SuccessAdapter())
    outcome = feu.fetch_external_data("estat")
    assert outcome.success
    assert outcome.error is None
    assert len(outcome.records) == 2


def test_fetch_handles_retry_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-DP-05: リトライ失敗時は success=False で error が入る(C-01)."""
    monkeypatch.setattr(feu, "_adapter_for", lambda _: _RetryExhaustedAdapter())
    outcome = feu.fetch_external_data("estat")
    assert outcome.success is False
    assert outcome.error is not None
    assert "retry_exhausted" in outcome.error


def test_fetch_handles_schema_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-DP-06: スキーマ異常時は success=False で error が入る."""
    monkeypatch.setattr(feu, "_adapter_for", lambda _: _SchemaErrorAdapter())
    outcome = feu.fetch_external_data("estat")
    assert outcome.success is False
    assert "schema_error" in (outcome.error or "")


def test_fetch_rejects_unknown_source() -> None:
    outcome = feu.fetch_external_data("unknown_source")
    assert outcome.success is False
    assert outcome.error is not None
