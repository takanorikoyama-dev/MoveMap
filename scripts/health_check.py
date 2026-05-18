"""DB 状態確認 CLI.

運用監視用. 終了コード:
    0: 健全(直近 7 日エラー = 0、最新バッチが success または初回未実行)
    1: 警告(直近 7 日エラーあり or 最新バッチ partial)
    2: 異常(DB 未生成 or 接続不可 or 最新バッチ failure)

使い方:
    python scripts/health_check.py        # 人向けレポート
    python scripts/health_check.py --json # JSON 出力(他システム連携用)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime

from app.features.map_view.data_status import HealthSummary, collect_health
from app.shared.logger import get_logger

logger = get_logger(__name__)


def _evaluate_status(summary: HealthSummary) -> tuple[int, str]:
    """終了コードと健全性ラベルを返す."""
    if not summary.db_exists:
        return 2, "abnormal: DB ファイル未生成"
    if not summary.tables:
        return 2, "abnormal: テーブル取得失敗"

    latest = summary.latest_batch
    if latest and latest.status == "failure":
        return 2, "abnormal: 最新バッチが failure"
    if latest and latest.status == "partial":
        return 1, "warning: 最新バッチが partial"
    if summary.error_count_last_7days > 0:
        return 1, f"warning: 直近 7 日のエラー {summary.error_count_last_7days} 件"
    return 0, "healthy"


def _format_human(summary: HealthSummary, label: str) -> str:
    lines: list[str] = []
    lines.append(f"=== MoveMap 健全性レポート ({label}) ===")
    lines.append(f"DB: {summary.db_path}")
    lines.append(f"DB 存在: {'yes' if summary.db_exists else 'NO'}")

    if not summary.db_exists:
        lines.append("→ scripts/seed.py を実行して DB を初期化してください")
        return "\n".join(lines)

    lines.append("")
    lines.append("--- テーブル件数 ---")
    for t in summary.tables:
        last = t.latest_at.strftime("%Y-%m-%d %H:%M") if t.latest_at else "—"
        lines.append(f"  {t.name:25s}: {t.row_count:>8,d} 行 (最新: {last})")

    lines.append("")
    lines.append("--- 指標別状況 ---")
    lines.append(f"  {'指標':22s} {'現在':>6s} {'履歴':>6s} {'モデル':>6s} {'R²':>6s} {'MAE':>10s}")
    for ind in summary.indicators:
        r2 = f"{ind.r_squared:.3f}" if ind.r_squared is not None else "—"
        mae = f"{ind.mae:.3f}" if ind.mae is not None else "—"
        model = "✓" if ind.has_model else "—"
        lines.append(
            f"  {ind.indicator_id:22s} {ind.current_count:>6d} {ind.history_count:>6d} "
            f"{model:>6s} {r2:>6s} {mae:>10s}"
        )

    lines.append("")
    lines.append("--- 最新バッチ ---")
    if summary.latest_batch and summary.latest_batch.status:
        b = summary.latest_batch
        started = b.started_at.strftime("%Y-%m-%d %H:%M") if b.started_at else "—"
        ended = b.ended_at.strftime("%Y-%m-%d %H:%M") if b.ended_at else "—"
        lines.append(f"  job_id={b.job_id} status={b.status} 開始={started} 終了={ended} 処理件数={b.records_processed}")
        if b.error_details:
            lines.append(f"  エラー詳細: {b.error_details}")
    else:
        lines.append("  バッチ実行履歴なし(scripts/run_batch.py を実行してください)")

    lines.append("")
    lines.append(f"--- 直近 7 日のエラー: {summary.error_count_last_7days} 件 ---")
    return "\n".join(lines)


def _format_json(summary: HealthSummary, label: str, exit_code: int) -> str:
    payload = {
        "evaluated_at": datetime.now().isoformat(),
        "exit_code": exit_code,
        "status_label": label,
        "summary": _dataclass_to_jsonable(asdict(summary)),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _dataclass_to_jsonable(obj):  # type: ignore[no-untyped-def]
    if isinstance(obj, dict):
        return {k: _dataclass_to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_dataclass_to_jsonable(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON で出力")
    args = parser.parse_args(argv)

    try:
        summary = collect_health()
    except Exception as exc:  # noqa: BLE001
        logger.exception("health_check 実行中に予期しない例外")
        if args.json:
            print(json.dumps({"exit_code": 2, "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"異常: {exc}")
        return 2

    exit_code, label = _evaluate_status(summary)
    if args.json:
        print(_format_json(summary, label, exit_code))
    else:
        print(_format_human(summary, label))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
