"""DuckDB スナップショット作成スクリプト.

INFRA-P6-01 / OPS-01: 月次バッチ完了後の DB ファイルを `data/snapshots/YYYYMM/` に保存.
直近 12 世代を保持(以前のものは削除).

使い方:
    python scripts/snapshot.py              # 現在の月で snapshot
    python scripts/snapshot.py --tag custom # 任意タグで snapshot
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from app.shared.config import load_config
from app.shared.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RETENTION = 12


def take_snapshot(tag: str | None = None, retention: int = DEFAULT_RETENTION) -> Path:
    """DuckDB ファイルをスナップショットとして保存.

    Args:
        tag: 任意タグ(None なら `YYYYMM`).
        retention: 保持する世代数(古いものから削除).

    Returns:
        作成されたスナップショットファイルのパス.
    """
    config = load_config()
    if not config.db_path.exists():
        raise FileNotFoundError(f"DB ファイルが存在しません: {config.db_path}")

    snapshot_root = config.db_path.parent / "snapshots"
    snapshot_root.mkdir(parents=True, exist_ok=True)

    label = tag if tag is not None else datetime.now().strftime("%Y%m")
    target_dir = snapshot_root / label
    target_dir.mkdir(parents=True, exist_ok=True)

    target = target_dir / config.db_path.name
    shutil.copy2(config.db_path, target)
    logger.info(f"snapshot 作成: {target} ({target.stat().st_size:,} bytes)")

    _enforce_retention(snapshot_root, retention)
    return target


def _enforce_retention(snapshot_root: Path, retention: int) -> None:
    """古い snapshot ディレクトリを削除(retention 世代を残す)."""
    if retention <= 0:
        return
    dirs = sorted(
        (d for d in snapshot_root.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )
    excess = len(dirs) - retention
    for d in dirs[:excess]:
        logger.info(f"古い snapshot を削除: {d}")
        shutil.rmtree(d)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=None, help="snapshot ラベル(既定: YYYYMM)")
    parser.add_argument("--retention", type=int, default=DEFAULT_RETENTION, help="保持世代数")
    args = parser.parse_args(argv)

    try:
        take_snapshot(tag=args.tag, retention=args.retention)
        return 0
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1
    except Exception:
        logger.exception("snapshot 失敗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
