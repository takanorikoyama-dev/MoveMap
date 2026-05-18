"""データソースアダプタの共通インターフェース."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class DataSourceAdapter(ABC):
    """各データソースが実装するアダプタ."""

    source_id: str  # data_sources.id と一致

    @abstractmethod
    def fetch(self) -> Iterator[dict[str, Any]]:
        """生データを取得する.

        Yields:
            raw record(都道府県別 × 指標別).
        """
        ...

    @abstractmethod
    def last_updated(self) -> str | None:
        """データソース側の最終更新日(差分判定用)."""
        ...
