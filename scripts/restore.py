"""DuckDB スナップショット復元スクリプト.

INFRA-P6-01: 不具合発生時に前回スナップショットから復元する.

使い方:
    python scripts/restore.py              # 最新 snapshot から復元
    python scripts/restore.py --tag 202604 # 特定 snapshot から復元
    python scripts/restore.py --list       # snapshot 一覧表示
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from app.shared.config import load_config
from app.shared.logger import get_logger

logger = get_logger(__name__)


def list_snapshots() -> list[Path]:
    config = load_config()
    snapshot_root = config.db_path.parent / "snapshots"
    if not snapshot_root.exists():
        return []
    return sorted(
        (d for d in snapshot_root.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )


def restore_snapshot(tag: str | None = None) -> Path:
    """指定タグ(なければ最新)の snapshot を現行 DB に上書き復元.

    上書き前に現行 DB を `<db>.pre_restore_<timestamp>` にバックアップする.
    """
    from datetime import datetime

    config = load_config()
    snapshots = list_snapshots()
    if not snapshots:
        raise FileNotFoundError("snapshot が 1 つもありません")

    if tag is None:
        target_dir = snapshots[-1]
    else:
        candidates = [d for d in snapshots if d.name == tag]
        if not candidates:
            raise FileNotFoundError(f"snapshot タグ '{tag}' が見つかりません")
        target_dir = candidates[0]

    source = target_dir / config.db_path.name
    if not source.exists():
        raise FileNotFoundError(f"snapshot ディレクトリに DB ファイルなし: {source}")

    # 現行 DB を退避
    if config.db_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = config.db_path.with_name(f"{config.db_path.stem}.pre_restore_{ts}{config.db_path.suffix}")
        shutil.copy2(config.db_path, backup)
        logger.info(f"現行 DB をバックアップ: {backup}")

    shutil.copy2(source, config.db_path)
    logger.info(f"復元完了: {target_dir.name} → {config.db_path}")
    return config.db_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=None, help="snapshot ラベル(既定: 最新)")
    parser.add_argument("--list", action="store_true", help="snapshot 一覧表示")
    args = parser.parse_args(argv)

    if args.list:
        snapshots = list_snapshots()
        if not snapshots:
            logger.info("snapshot なし")
            return 0
        for d in snapshots:
            sizes = [f.stat().st_size for f in d.iterdir() if f.is_file()]
            total = sum(sizes)
            logger.info(f"  {d.name} ({total:,} bytes、{len(sizes)} ファイル)")
        return 0

    try:
        restore_snapshot(tag=args.tag)
        return 0
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1
    except Exception:
        logger.exception("restore 失敗")
        return 1


if __name__ == "__main__":
    sys.exit(main())
