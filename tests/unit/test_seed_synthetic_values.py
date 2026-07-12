"""scripts/seed.py の合成データ生成ロジックの単体テスト.

2026-07-12: net_migration が全都道府県で 0.0 になるデータ品質バグを発見・修正.
原因は `offset = (hash - 0.5) * 0.4 * base` という相対オフセット計算で、
net_migration の base=0.0(転入超過率は0付近で変動する指標のため)のとき
offset が恒常的に 0 になっていた. 絶対幅ベースの計算に修正し、再発防止の
ため本テストを追加する.
"""

from __future__ import annotations

from scripts.seed import (
    NON_PREDICTABLE_RANGES,
    _hash_unit,
    _non_predictable_offset_spread,
)


def test_non_predictable_offset_spread_net_migration_is_nonzero() -> None:
    """net_migration は base=0.0 でもオフセット幅が 0 にならない(2026-07-12 バグ修正の回帰防止)."""
    base = NON_PREDICTABLE_RANGES["net_migration"]
    assert base == 0.0, "この前提(base=0.0)が変わったら本テストの意図を見直すこと"
    spread = _non_predictable_offset_spread("net_migration", base)
    assert spread > 0.0, "net_migration のオフセット幅が 0 のままだと全県 0.0 に戻ってしまう"


def test_non_predictable_offset_spread_others_scale_with_base() -> None:
    """net_migration 以外の指標は、従来通り base に比例したオフセット幅になる."""
    for ind in ("air_quality", "disaster_risk", "transport_access", "public_safety"):
        base = NON_PREDICTABLE_RANGES[ind]
        spread = _non_predictable_offset_spread(ind, base)
        assert spread == base * 0.2, f"{ind}: base 比例(±20%)から逸脱している"


def test_seed_synthetic_current_net_migration_has_variation() -> None:
    """47 都道府県の net_migration 合成値が、全て同じ値(0.0 等)に潰れていない.

    _hash_unit による都道府県別の決定論的な分散が機能していることを、
    実際に current_values 相当の計算式を通して確認する(2026-07-12 回帰防止).
    """
    base = NON_PREDICTABLE_RANGES["net_migration"]
    spread = _non_predictable_offset_spread("net_migration", base)

    pref_codes = [f"{i:02d}" for i in range(1, 48)]
    values = [
        base + (_hash_unit("net_migration", pref) - 0.5) * 2 * spread
        for pref in pref_codes
    ]

    assert len(set(values)) > 1, "全 47 都道府県の値が同一(バグ再発の疑い)"
    assert not all(v == 0.0 for v in values), "全 47 都道府県が 0.0(バグ再発)"
    # ±spread の範囲に収まっていること
    assert all(-spread <= v <= spread for v in values)
