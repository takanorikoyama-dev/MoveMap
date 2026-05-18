"""SF-021 ShowDataSources の単体テスト."""

from __future__ import annotations

import pytest

from app.features.compliance.show_data_sources import show_data_sources


def test_show_data_sources_none_branch_is_callable() -> None:
    """indicator_id=None 経路は Streamlit caption のみで例外を起こさない."""
    # Streamlit がインポート可能なら呼出は通る(実 caption 描画は smoke で別途)
    show_data_sources(con=None, indicator_id=None)  # type: ignore[arg-type]


def test_show_data_sources_with_indicator_id_raises_not_implemented() -> None:
    """指標別出典は Phase 7 続セッションで未実装."""
    with pytest.raises(NotImplementedError):
        show_data_sources(con=None, indicator_id="price_index")  # type: ignore[arg-type]
