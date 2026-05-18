"""エンドツーエンドパイプラインテスト.

シナリオ:
    1. テスト用 DB に seed + synthetic_history を投入
    2. run_batch を mock fetch で実行
    3. 予測パイプライン全段(retrain / evaluate / generate / fallback) が DB を populate
    4. data_provider 経由で UI が DB 実データを取得できる
    5. AuditLog / BatchJob に記録が残っている

ローンチ前の全体動作確認用. fetch は mock するが、それ以外の処理は本物.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

# E2E は ARIMA 学習を 188 回走らせるため重い(約 16 分)。`pytest -m slow` で明示実行.
pytestmark = pytest.mark.slow

import app.features.data_pipeline.usecases.fetch_external_data as feu  # noqa: E402
import app.features.data_pipeline.usecases.run_batch as rb_mod
import app.features.map_view.data_provider as dp_mod
import app.shared.config as config_mod
import app.shared.db as db_mod
import scripts.seed as seed_mod
from app.features.data_pipeline.usecases.fetch_external_data import FetchOutcome


@pytest.fixture()
def launched(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """ローンチ初期状態を模した DB(seed 完了 + 合成履歴投入済) + mock fetch."""
    db_path = tmp_path / "movemap.duckdb"

    # 本物の seeds をテスト用に投入できるよう seeds_dir はプロジェクトの seeds を指す
    project_seeds = Path(__file__).resolve().parents[2] / "seeds"
    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=project_seeds,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(db_mod, "load_config", lambda: fake)
    monkeypatch.setattr(seed_mod, "load_config", lambda: fake)
    monkeypatch.setattr(dp_mod, "load_config", lambda: fake)

    # seed + synthetic_history
    rc = seed_mod.main(["--with-synthetic-history"])
    assert rc == 0

    # 外部 fetch はすべて空成功(差分なし扱い)
    def _stub_fetch(source_id: str) -> FetchOutcome:
        outcome = FetchOutcome(source_id=source_id)
        outcome.success = True
        outcome.records = []
        return outcome

    monkeypatch.setattr(rb_mod, "fetch_external_data", _stub_fetch)
    monkeypatch.setattr(feu, "fetch_external_data", _stub_fetch)

    return fake


def test_e2e_run_batch_creates_predictions(launched) -> None:  # type: ignore[no-untyped-def]
    """run_batch が呼ばれると prediction_models / predicted_values が埋まる."""
    con = duckdb.connect(str(launched.db_path))
    try:
        # 事前状態確認: 合成履歴 4,512 行、prediction_models と predicted_values は空
        (hist,) = con.execute("SELECT COUNT(*) FROM historical_values").fetchone()
        (models_before,) = con.execute("SELECT COUNT(*) FROM prediction_models").fetchone()
        (preds_before,) = con.execute("SELECT COUNT(*) FROM predicted_values").fetchone()
        assert hist == 4 * 47 * 24
        assert models_before == 0
        assert preds_before == 0
    finally:
        con.close()

    outcome = rb_mod.run_batch(db_mod.connect(protect_history=True))
    assert outcome.job_id > 0
    assert outcome.status in ("success", "partial")
    assert outcome.models_trained == 4

    # 事後状態
    con = duckdb.connect(str(launched.db_path))
    try:
        (models_after,) = con.execute("SELECT COUNT(*) FROM prediction_models").fetchone()
        (preds_after,) = con.execute("SELECT COUNT(*) FROM predicted_values").fetchone()
        assert models_after == 4
        # 4 指標 × 47 都道府県 × 3 horizons = 564
        assert preds_after == 4 * 47 * 3

        (batch_jobs,) = con.execute("SELECT COUNT(*) FROM batch_jobs WHERE status != 'running'").fetchone()
        assert batch_jobs >= 1

        (audit,) = con.execute("SELECT COUNT(*) FROM audit_logs WHERE event_type LIKE 'batch.%'").fetchone()
        assert audit >= 1
    finally:
        con.close()


def test_e2e_data_provider_reads_from_db_after_run(launched) -> None:  # type: ignore[no-untyped-def]
    """run_batch 後、data_provider が DB を 1 次取得元として返す.

    予測値が埋まったので horizon='5y' で DB ソースが返ることを確認.
    """
    rb_mod.run_batch(db_mod.connect(protect_history=True))

    # data_provider 経由(future horizon)
    pack = dp_mod.values_for("price_index", "5y")
    assert pack.availability.source == "db"
    # 47 都道府県分の値が dict にある
    assert len(pack.values) == 47


def test_e2e_data_provider_current_values_still_dummy(launched) -> None:  # type: ignore[no-untyped-def]
    """current_values は fetch が空なので埋まらず、dummy にフォールバック.

    予測対象指標の current は dummy、未来 horizon は DB.この混在挙動を検証.
    """
    rb_mod.run_batch(db_mod.connect(protect_history=True))

    current_pack = dp_mod.values_for("price_index", "current")
    # synthetic_history のみで current_values は空 → dummy 経路
    assert current_pack.availability.source == "dummy"


def test_e2e_latest_model_for_returns_db_after_run(launched) -> None:  # type: ignore[no-untyped-def]
    """学習後、最新モデル情報が DB 由来になる."""
    rb_mod.run_batch(db_mod.connect(protect_history=True))

    info = dp_mod.latest_model_for("price_index")
    assert info.availability.source == "db"
    assert info.model_type is not None
    assert info.trained_at is not None
    # 合成データから学習しているので R²/MAE が存在
    assert info.r_squared is not None or info.mae is not None


def test_e2e_idempotency_double_run(launched) -> None:  # type: ignore[no-untyped-def]
    """run_batch を 2 回実行しても unique 制約に違反しない(upsert).

    predicted_values の PK (prefecture_code, indicator_id, horizon_years) で重複しない.
    """
    rb_mod.run_batch(db_mod.connect(protect_history=True))
    rb_mod.run_batch(db_mod.connect(protect_history=True))

    con = duckdb.connect(str(launched.db_path))
    try:
        (preds,) = con.execute("SELECT COUNT(*) FROM predicted_values").fetchone()
        assert preds == 4 * 47 * 3  # 重複なし、upsert で同じ件数
    finally:
        con.close()
