"""SF-012 NormalizeData — 都道府県コード・単位・型統一.

参照: outputs/06_system_design/06_テスト設計.md (TC-DP-07)
不変条件: 結果の都道府県コードは JIS X 0401 の 01〜47.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from app.shared.logger import get_logger

logger = get_logger(__name__)

VALID_PREF_CODES: frozenset[str] = frozenset(f"{i:02d}" for i in range(1, 48))


class NormalizationError(Exception):
    """正規化できないレコード(指標 ID / 都道府県コードが不正)."""


def normalize_data(
    source_id: str,
    raw_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """生レコードを正規化する.

    Output schema:
        {"prefecture_code": "01".."47", "indicator_id": str, "value": float, "measured_at": date|None}

    Args:
        source_id: data_sources.id(ロギング用).
        raw_records: ETL で取得した生レコード.

    Returns:
        正規化済みレコード(不正な行はスキップ + 警告ログ).
    """
    normalized: list[dict[str, Any]] = []
    skipped = 0
    for r in raw_records:
        try:
            normalized.append(_normalize_one(r))
        except NormalizationError as exc:
            skipped += 1
            logger.warning(f"normalize skip [{source_id}]: {exc} record={r}")
    if skipped:
        logger.info(f"normalize {source_id}: kept={len(normalized)} skipped={skipped}")
    return normalized


def _normalize_one(r: dict[str, Any]) -> dict[str, Any]:
    pref_code = _normalize_prefecture_code(r.get("prefecture_code"))
    if pref_code not in VALID_PREF_CODES:
        raise NormalizationError(f"unknown prefecture_code: {r.get('prefecture_code')}")

    indicator_id = r.get("indicator_id")
    if not isinstance(indicator_id, str) or not indicator_id:
        raise NormalizationError(f"missing indicator_id: {r}")

    value = _normalize_value(r.get("value"))
    measured_at = _normalize_measured_at(r.get("measured_at"))

    return {
        "prefecture_code": pref_code,
        "indicator_id": indicator_id,
        "value": value,
        "measured_at": measured_at,
    }


def _normalize_prefecture_code(code: Any) -> str:
    if isinstance(code, int):
        return f"{code:02d}"
    if isinstance(code, str):
        digits = code.strip()
        if digits.isdigit():
            return f"{int(digits):02d}"
    return ""


def _normalize_value(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise NormalizationError(f"non-numeric value: {value!r}") from exc
    raise NormalizationError(f"unsupported value type: {type(value).__name__}")


def _normalize_measured_at(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError as exc:
            raise NormalizationError(f"invalid date: {value!r}") from exc
    raise NormalizationError(f"unsupported measured_at type: {type(value).__name__}")
