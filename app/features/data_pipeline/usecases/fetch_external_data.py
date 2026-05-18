"""SF-011 FetchExternalData — 外部データソースから取得.

source_id ベースで適切な DataSourceAdapter を選び、 fetch() を呼び出す.

参照: outputs/06_system_design/02_API設計.md (API-EXT-01〜06)
責任: アダプタ選択 + エラーハンドリング(C-01 / C-02 / INV-EXT-001)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.features.data_pipeline.sources._base import DataSourceAdapter
from app.features.data_pipeline.sources.env_soramame import SoramameAdapter
from app.features.data_pipeline.sources.estat import EStatAdapter
from app.features.data_pipeline.sources.gsi_hazard import GsiHazardAdapter
from app.features.data_pipeline.sources.mlit_land_price import MlitLandPriceAdapter
from app.features.data_pipeline.sources.mlit_rent_index import MlitRentIndexAdapter
from app.features.data_pipeline.sources.mlit_transport import MlitTransportAdapter
from app.shared.http_client import HttpRetryExhausted, HttpSchemaError
from app.shared.logger import get_logger

logger = get_logger(__name__)


def _adapter_for(source_id: str) -> DataSourceAdapter:
    mapping = {
        "estat": EStatAdapter,
        "mlit_land_price": MlitLandPriceAdapter,
        "mlit_rent_index": MlitRentIndexAdapter,
        "env_soramame": SoramameAdapter,
        "gsi_hazard": GsiHazardAdapter,
        "mlit_transport": MlitTransportAdapter,
    }
    cls = mapping.get(source_id)
    if cls is None:
        raise ValueError(f"未知の source_id: {source_id}")
    return cls()


class FetchOutcome:
    """fetch_external_data の結果."""

    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.records: list[dict[str, Any]] = []
        self.success: bool = False
        self.error: str | None = None

    def __repr__(self) -> str:
        return f"FetchOutcome(source={self.source_id}, success={self.success}, records={len(self.records)})"


def fetch_external_data(source_id: str) -> FetchOutcome:
    """指定された source_id のデータを取得する.

    Args:
        source_id: data_sources.id.

    Returns:
        FetchOutcome(success=True で records が詰まる、False で error が入る).
    """
    outcome = FetchOutcome(source_id=source_id)
    try:
        adapter = _adapter_for(source_id)
    except ValueError as exc:
        outcome.error = str(exc)
        logger.exception(f"adapter lookup failed: {source_id}")
        return outcome

    try:
        outcome.records = list(adapter.fetch())
        outcome.success = True
        logger.info(f"fetch success: source={source_id} records={len(outcome.records)}")
    except NotImplementedError:
        outcome.error = "not_implemented"
        logger.warning(f"adapter not yet implemented: {source_id}")
    except HttpRetryExhausted as exc:
        # INV-EXT-001: リトライ失敗 → 上流で前回値保持
        outcome.error = f"retry_exhausted: {exc}"
        logger.exception(f"fetch retry exhausted: {source_id}")
    except HttpSchemaError as exc:
        outcome.error = f"schema_error: {exc}"
        logger.exception(f"fetch schema error: {source_id}")
    except Exception as exc:  # noqa: BLE001
        outcome.error = f"unexpected: {exc}"
        logger.exception(f"fetch unexpected error: {source_id}")
    return outcome


def fetch_records(source_id: str) -> Iterator[dict[str, Any]]:
    """既存呼び出し(Iterator 形式)用のシムレイヤー."""
    outcome = fetch_external_data(source_id)
    if not outcome.success:
        return
    yield from outcome.records
