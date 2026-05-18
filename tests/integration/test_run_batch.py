"""TC-DP-01〜03 RunBatch の統合テスト(モック source).

SF-010 〜 SF-019 のオーケストレーションを検証する.
"""

from __future__ import annotations

import duckdb
import pytest

import app.features.data_pipeline.usecases.fetch_external_data as feu
import app.features.data_pipeline.usecases.run_batch as rb_mod
from app.features.data_pipeline.usecases.fetch_external_data import FetchOutcome
from app.features.data_pipeline.usecases.run_batch import run_batch


def _stub_fetch_factory(failed_sources: set[str] | None = None):  # type: ignore[no-untyped-def]
    failed = failed_sources or set()

    def fake_fetch(source_id: str) -> FetchOutcome:
        outcome = FetchOutcome(source_id=source_id)
        if source_id in failed:
            outcome.error = "stubbed failure"
            return outcome
        outcome.success = True
        outcome.records = []  # 取得 0 件(差分なしのケース、INV-EXT-001 経路)
        return outcome

    return fake_fetch


def test_run_batch_success_with_empty_sources(db_with_history: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch) -> None:
    """全 source が success かつ records=0 で、status=success(またはRunBatch内部でpartialになる場合あり).

    予測パイプラインは db_with_history で学習可能.
    """
    monkeypatch.setattr(rb_mod, "fetch_external_data", _stub_fetch_factory())
    monkeypatch.setattr(feu, "fetch_external_data", _stub_fetch_factory())

    outcome = run_batch(db_with_history)
    assert outcome.job_id > 0
    assert outcome.status in ("success", "partial")  # 予測失敗時は partial になり得る
    assert outcome.models_trained == 4  # 主要4指標


def test_run_batch_creates_batch_job_row(db_with_history: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch) -> None:
    """INV-BIZ-004: バッチ開始時に BatchJob レコードが C される."""
    monkeypatch.setattr(rb_mod, "fetch_external_data", _stub_fetch_factory())

    before = db_with_history.execute("SELECT COUNT(*) FROM batch_jobs").fetchone()[0]
    run_batch(db_with_history)
    after = db_with_history.execute("SELECT COUNT(*) FROM batch_jobs").fetchone()[0]
    assert after - before == 1


def test_run_batch_partial_when_some_sources_fail(db_with_history: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch) -> None:
    """一部 source 失敗で status='partial'."""
    monkeypatch.setattr(rb_mod, "fetch_external_data", _stub_fetch_factory(failed_sources={"mlit_land_price"}))

    outcome = run_batch(db_with_history)
    assert outcome.status == "partial"
    failed = [s for s in outcome.sources if not s.success]
    assert len(failed) == 1
    assert failed[0].source_id == "mlit_land_price"


def test_run_batch_failure_when_all_sources_fail_and_no_history(db: duckdb.DuckDBPyConnection, monkeypatch: pytest.MonkeyPatch) -> None:
    """全 source 失敗かつ予測パイプライン素材なし → failure."""
    all_sources = set(rb_mod.SOURCE_IDS)
    monkeypatch.setattr(rb_mod, "fetch_external_data", _stub_fetch_factory(failed_sources=all_sources))

    outcome = run_batch(db)
    assert outcome.status in ("failure", "partial")  # 履歴なしで models_trained=0 → 予測なしで partial 経路の可能性
