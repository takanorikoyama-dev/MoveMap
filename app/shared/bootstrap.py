"""アプリ起動時のブートストラップ.

Streamlit Cloud のような ephemeral 環境で、`data/movemap.duckdb` が
存在しない場合に自動初期化する.

優先順位:
    1. seeds/movemap_sample.duckdb がコミットされていれば copy(高速)
    2. それも無ければ seeds CSV + 合成データから初期化(seed.py を呼ぶ)
    3. それも失敗すれば data_provider が dummy にフォールバック(既存挙動)

設計判断:
    - Streamlit Cloud のコールドスタートで毎回走るため、副作用は最小化
    - 既に DB がある(ローカル開発・キャッシュヒット)なら即 return
    - 例外を握りつぶさず logger に出すが、UI 起動は止めない
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.shared.config import PROJECT_ROOT, load_config
from app.shared.logger import get_logger

logger = get_logger(__name__)

SAMPLE_DB_PATH = PROJECT_ROOT / "seeds" / "movemap_sample.duckdb"


def ensure_db_initialized() -> None:
    """DB ファイルが無ければ初期化する(idempotent).

    既に DB が存在すれば何もしない. 失敗しても例外を投げない
    (data_provider 側で dummy にフォールバックするため).
    """
    cfg = load_config()
    db_path: Path = cfg.db_path

    if db_path.exists() and db_path.stat().st_size > 0:
        return  # 既に存在 — 何もしない

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"data ディレクトリ作成失敗: {e}")
        return

    # 1) サンプル DB を copy(コールドスタートで高速)
    if SAMPLE_DB_PATH.exists() and SAMPLE_DB_PATH.stat().st_size > 0:
        try:
            shutil.copy2(SAMPLE_DB_PATH, db_path)
            logger.info(
                f"サンプル DB を復元しました: {SAMPLE_DB_PATH.name} -> {db_path}"
            )
            return
        except OSError as e:
            logger.warning(f"サンプル DB copy 失敗、seed にフォールバック: {e}")

    # 2) seed.py で合成データ生成(フォールバック)
    try:
        from scripts import seed as seed_module

        rc = seed_module.main(["--with-synthetic-history", "--with-synthetic-current"])
        if rc == 0:
            logger.info("seed.py で合成データを生成しました(初回起動)")
        else:
            logger.warning(f"seed.py が非ゼロ終了: rc={rc}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"seed.py 実行失敗: {e}. data_provider が dummy にフォールバックします")


__all__ = ["ensure_db_initialized"]
