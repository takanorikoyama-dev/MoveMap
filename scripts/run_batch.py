"""月次バッチエントリポイント.

GitHub Actions cron(monthly-batch.yml)から起動される.
本体は app.features.data_pipeline.usecases.run_batch.run_batch().

終了コード:
    0: success または partial(運用上は通常終了)
    1: failure(GitHub Actions の Job 失敗通知が走る)
"""

from __future__ import annotations

import sys

from app.features.data_pipeline.usecases.run_batch import run_batch
from app.shared.db import connect, initialize_schema
from app.shared.logger import get_logger

logger = get_logger(__name__)


def run() -> int:
    """月次バッチを実行する.

    Returns:
        終了コード(0=success/partial、1=failure).
    """
    logger.info("月次バッチを起動")
    con = connect()
    try:
        initialize_schema(con)
        outcome = run_batch(con)
        logger.info(
            f"BatchOutcome: job_id={outcome.job_id} status={outcome.status} "
            f"records={outcome.records_processed} "
            f"sources_ok={sum(1 for s in outcome.sources if s.success)}/{len(outcome.sources)} "
            f"models_trained={outcome.models_trained} "
            f"predictions_generated={outcome.predictions_generated} "
            f"fallbacks={outcome.fallbacks_flagged}"
        )
        return 0 if outcome.status in ("success", "partial") else 1
    except Exception:
        logger.exception("月次バッチで予期しない例外")
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(run())
