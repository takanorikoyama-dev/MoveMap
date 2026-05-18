"""seeds JSON を読んで Wave 2 アダプタが期待形式のレコードを返すことを検証.

参照: outputs/06_system_design/02_API設計.md (API-EXT-05/06)
"""

from __future__ import annotations

from app.features.data_pipeline.sources.gsi_hazard import GsiHazardAdapter
from app.features.data_pipeline.sources.mlit_transport import MlitTransportAdapter


def test_gsi_hazard_loads_from_seeds() -> None:
    """seeds/hazard_scores.json から 47 都道府県の合成スコアが取れる."""
    adapter = GsiHazardAdapter()
    records = list(adapter.fetch())
    assert len(records) == 47

    pref_codes = {r["prefecture_code"] for r in records}
    expected = {f"{i:02d}" for i in range(1, 48)}
    assert pref_codes == expected

    for r in records:
        assert r["indicator_id"] == "disaster_risk"
        assert isinstance(r["value"], float)
        # 1.0〜5.0 のサブスコアの平均 → だいたい同じレンジ
        assert 1.0 <= r["value"] <= 5.0


def test_gsi_hazard_ignores_meta_key() -> None:
    """`_meta` キーが含まれていても 47 件だけが yield される(int 変換失敗で skip)."""
    adapter = GsiHazardAdapter()
    records = list(adapter.fetch())
    pref_codes = {r["prefecture_code"] for r in records}
    assert "_meta" not in pref_codes


def test_mlit_transport_loads_from_seeds() -> None:
    """seeds/transport_facilities.json から 47 都道府県のスコアが取れる."""
    adapter = MlitTransportAdapter()
    records = list(adapter.fetch())
    assert len(records) == 47

    pref_codes = {r["prefecture_code"] for r in records}
    expected = {f"{i:02d}" for i in range(1, 48)}
    assert pref_codes == expected

    for r in records:
        assert r["indicator_id"] == "transport_access"
        assert isinstance(r["value"], float)
        # 0〜5 のスコアレンジ
        assert 0.0 <= r["value"] <= 5.0


def test_mlit_transport_metropolitan_scores_higher_than_remote() -> None:
    """東京(13)は北海道(01)よりも交通アクセススコアが高い(主要インフラ密度)."""
    adapter = MlitTransportAdapter()
    records = {r["prefecture_code"]: r["value"] for r in adapter.fetch()}
    assert records["13"] > records["01"]
