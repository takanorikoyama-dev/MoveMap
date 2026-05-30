"""業務不変条件の静的検証テスト.

DB トリガーで防御できない不変条件を、コードベース全体の grep ベースで検査する.
これは Phase 7 持ち越し論点 RISK-P7-01 (DEC-013) への対応の第一段階.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"
SCRIPT_ROOT = PROJECT_ROOT / "scripts"

# 「historical_values への UPDATE / DELETE」を許容するファイル(規約上の例外)
# - db.py: DDL 定義
# - append_history.py: 唯一の正規書き込み口(本ファイルも INSERT のみ)
ALLOWED_HISTORY_WRITERS = {
    "app/shared/db.py",
    "app/features/data_pipeline/usecases/append_history.py",
}


def _scan_python_files(root: Path) -> list[tuple[Path, str]]:
    """root 配下の .py ファイル名 + 全文を返す."""
    results: list[tuple[Path, str]] = []
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        results.append((path, path.read_text(encoding="utf-8")))
    return results


def _relpath(path: Path) -> str:
    """プロジェクトルートを起点とした相対パスを返す(POSIX 区切り)."""
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def test_inv_data_007_no_historical_values_update() -> None:
    """INV-DATA-007: historical_values に対する UPDATE 文を禁止(append-only).

    DDL を除く全コードを走査し、`UPDATE historical_values` を検出した場合は失敗.
    """
    pattern = re.compile(r"UPDATE\s+historical_values\b", re.IGNORECASE)
    violations: list[str] = []
    for path, text in _scan_python_files(APP_ROOT) + _scan_python_files(SCRIPT_ROOT):
        rel = _relpath(path)
        if rel in ALLOWED_HISTORY_WRITERS:
            continue
        if pattern.search(text):
            violations.append(rel)
    assert not violations, f"INV-DATA-007 違反(UPDATE): {violations}"


def test_inv_data_007_no_historical_values_delete() -> None:
    """INV-DATA-007: historical_values に対する DELETE 文を禁止."""
    pattern = re.compile(r"DELETE\s+FROM\s+historical_values\b", re.IGNORECASE)
    violations: list[str] = []
    for path, text in _scan_python_files(APP_ROOT) + _scan_python_files(SCRIPT_ROOT):
        rel = _relpath(path)
        if rel in ALLOWED_HISTORY_WRITERS:
            continue
        if pattern.search(text):
            violations.append(rel)
    assert not violations, f"INV-DATA-007 違反(DELETE): {violations}"


def test_inv_data_007_append_history_uses_only_insert() -> None:
    """append_history.py 自身が INSERT 以外の書込みを発行していないことを確認."""
    target = APP_ROOT / "features" / "data_pipeline" / "usecases" / "append_history.py"
    text = target.read_text(encoding="utf-8")

    # UPDATE / DELETE が現れたら違反
    assert not re.search(r"UPDATE\s+historical_values\b", text, re.IGNORECASE)
    assert not re.search(r"DELETE\s+FROM\s+historical_values\b", text, re.IGNORECASE)
    # INSERT は許容
    assert re.search(r"INSERT\s+INTO\s+historical_values\b", text, re.IGNORECASE)


def test_inv_data_007_no_truncate_historical_values() -> None:
    """念のため TRUNCATE もチェック."""
    pattern = re.compile(r"TRUNCATE(?:\s+TABLE)?\s+historical_values\b", re.IGNORECASE)
    violations: list[str] = []
    for path, text in _scan_python_files(APP_ROOT) + _scan_python_files(SCRIPT_ROOT):
        rel = _relpath(path)
        if rel in ALLOWED_HISTORY_WRITERS:
            continue
        if pattern.search(text):
            violations.append(rel)
    assert not violations, f"INV-DATA-007 違反(TRUNCATE): {violations}"


def test_inv_biz_005_disclaimer_invoked_in_main() -> None:
    """INV-BIZ-005: app/main.py で render_disclaimer() が呼ばれる."""
    main = APP_ROOT / "main.py"
    text = main.read_text(encoding="utf-8")
    assert "render_disclaimer" in text, "INV-BIZ-005 違反: app/main.py に render_disclaimer 呼出なし"


def test_inv_biz_008_footer_invoked_in_main() -> None:
    """INV-BIZ-008(DEC-016 派生): app/main.py で render_footer() が呼ばれる(法務リンク導線)."""
    main = APP_ROOT / "main.py"
    text = main.read_text(encoding="utf-8")
    assert "render_footer" in text, "INV-BIZ-008 違反: app/main.py に render_footer 呼出なし"


def test_inv_biz_006_disclaimer_includes_advice_disclaimers() -> None:
    """INV-BIZ-006(DEC-016 派生): 免責文に投資/不動産/移住の助言ではない明示."""
    disclaimer = APP_ROOT / "features" / "compliance" / "disclaimer.py"
    text = disclaimer.read_text(encoding="utf-8")
    assert "投資助言" in text, "INV-BIZ-006 違反: disclaimer.py に「投資助言」明示なし"
    assert "不動産取引助言" in text, "INV-BIZ-006 違反: disclaimer.py に「不動産取引助言」明示なし"
    assert "移住助言" in text, "INV-BIZ-006 違反: disclaimer.py に「移住助言」明示なし"
