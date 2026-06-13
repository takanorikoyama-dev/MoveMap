"""フルデモ環境を 1 コマンドで構築する.

実行内容:
    1. uv 依存解決確認
    2. seeds + 合成履歴 + 合成現在値 を DuckDB に投入
    3. 日本地図 GeoJSON を取得(未配置時のみ)
    4. mock fetch で run_batch を実行し prediction_models / predicted_values を populate
    5. 健全性チェック

実行後、`streamlit run app/main.py` でフルデータ表示の UI が起動可能.

使い方:
    python scripts/demo.py             # フル(履歴 + 現在 + 予測)
    python scripts/demo.py --quick     # 履歴 + 現在(予測スキップ、ARIMA を回さない高速モード)
"""

from __future__ import annotations

import argparse
import sys

from app.shared.logger import get_logger

logger = get_logger(__name__)


def _step_seed(synthetic: bool = True) -> None:
    import scripts.seed as seed_mod

    args = []
    if synthetic:
        args.extend(["--with-synthetic-history", "--with-synthetic-current"])
    rc = seed_mod.main(args)
    if rc != 0:
        raise RuntimeError(f"seed.py が失敗 (rc={rc})")


def _step_geojson() -> None:

    from app.shared.config import PROJECT_ROOT

    target = PROJECT_ROOT / "seeds" / "japan_prefectures.geojson"
    if target.exists():
        logger.info(f"GeoJSON 既存(skip): {target}")
        return

    import scripts.fetch_geojson as fg

    rc = fg.main()
    if rc != 0:
        logger.warning("GeoJSON 取得失敗。MAP は棒グラフフォールバックになります")


def _step_run_batch_with_mock() -> None:
    """fetch を mock して run_batch を実行(API キー不要).

    Wave 2 ソースは空応答とし、合成履歴から ARIMA 学習 + 予測値生成のみ実行.
    """
    import app.features.data_pipeline.usecases.fetch_external_data as feu
    import app.features.data_pipeline.usecases.run_batch as rb
    from app.features.data_pipeline.usecases.fetch_external_data import FetchOutcome
    from app.shared.db import connect

    def _stub(source_id: str) -> FetchOutcome:
        outcome = FetchOutcome(source_id=source_id)
        outcome.success = True
        outcome.records = []
        return outcome

    original_rb = rb.fetch_external_data
    original_feu = feu.fetch_external_data
    rb.fetch_external_data = _stub  # type: ignore[assignment]
    feu.fetch_external_data = _stub  # type: ignore[assignment]
    try:
        outcome = rb.run_batch(connect(protect_history=True))
        logger.info(f"run_batch: status={outcome.status} models_trained={outcome.models_trained} predictions={outcome.predictions_generated}")
    finally:
        rb.fetch_external_data = original_rb  # type: ignore[assignment]
        feu.fetch_external_data = original_feu  # type: ignore[assignment]


def _step_health_check() -> int:
    import scripts.health_check as hc

    return hc.main([])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="ARIMA 学習をスキップ(履歴 + 現在値のみ、高速)",
    )
    parser.add_argument(
        "--no-geojson",
        action="store_true",
        help="GeoJSON 取得をスキップ(オフライン環境向け)",
    )
    args = parser.parse_args(argv)

    logger.info("=== MoveMap デモ環境構築を開始 ===")

    try:
        logger.info("Step 1/4: seed + 合成データ投入")
        _step_seed(synthetic=True)

        if args.no_geojson:
            logger.info("Step 2/4: GeoJSON 取得(skip)")
        else:
            logger.info("Step 2/4: GeoJSON 取得")
            _step_geojson()

        if args.quick:
            logger.info("Step 3/4: run_batch(skip --quick)")
        else:
            logger.info("Step 3/4: run_batch (mock fetch) → ARIMA 学習 + 予測生成")
            _step_run_batch_with_mock()

        logger.info("Step 4/4: 健全性チェック")
        rc = _step_health_check()
        if rc != 0:
            logger.warning(f"health_check 終了コード = {rc}")

        logger.info("=== デモ環境構築完了 ===")
        logger.info("次: python -m uv run streamlit run app/main.py")
        return 0
    except Exception:
        logger.exception("デモ環境構築中にエラー")
        return 1


if __name__ == "__main__":
    sys.exit(main())
