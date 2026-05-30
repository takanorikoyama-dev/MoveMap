"""OSM Overpass API クライアント(非日常スポット情報の取得).

OpenStreetMap の POI(Points of Interest)を Overpass API 経由で取得.
完全無料、レート制限あり(Fair Use Policy: 1秒数リクエスト程度).

カテゴリ:
    - attraction(観光名所)
    - viewpoint(展望スポット)
    - castle(城・城跡)
    - shrine_temple(神社・寺院)
    - onsen(温泉・公衆浴場)
    - park(公園)
    - waterfall(滝)
    - museum(博物館)

利用規約:
    OpenStreetMap データは ODbL(Open Database License).
    UI 上で「© OpenStreetMap contributors」明示.

参照: https://wiki.openstreetmap.org/wiki/Overpass_API
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from app.shared.logger import get_logger

logger = get_logger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "MoveMap/0.1 (https://github.com/takanorikoyama-dev/MoveMap)"


@dataclass(frozen=True, slots=True)
class POI:
    """Point of Interest(地理上の興味地点)."""
    name: str
    category: str  # attraction, viewpoint, castle, shrine_temple, onsen, park, waterfall, museum, other
    lat: float
    lon: float
    osm_id: str


# カテゴリ → Overpass フィルタ式
CATEGORY_FILTERS: dict[str, str] = {
    "attraction": '["tourism"="attraction"]',
    "viewpoint": '["tourism"="viewpoint"]',
    "castle": '["historic"~"castle|castle_ruins"]',
    # 神社仏閣: 一般的な信仰施設(神道・仏教)+ 歴史的タグもカバー
    "shrine_temple": '["amenity"="place_of_worship"]["religion"~"shinto|buddhist"]',
    "onsen": '["amenity"~"public_bath|onsen"]',
    "park": '["leisure"="park"]',
    "waterfall": '["waterway"="waterfall"]',
    "museum": '["tourism"="museum"]',
}

# 表示用ラベルとアイコン
CATEGORY_LABELS: dict[str, tuple[str, str, str]] = {
    "attraction": ("🎡", "観光名所", "#e91e63"),  # ピンク
    "viewpoint": ("🌄", "展望スポット", "#ff9800"),  # オレンジ
    "castle": ("🏯", "城・城跡", "#795548"),  # ブラウン
    "shrine_temple": ("⛩️", "神社仏閣", "#9c27b0"),  # 紫
    "onsen": ("♨️", "温泉", "#f44336"),  # 赤
    "park": ("🌳", "公園", "#4caf50"),  # 緑
    "waterfall": ("💦", "滝", "#03a9f4"),  # 水色
    "museum": ("🎨", "博物館・美術館", "#673ab7"),  # 深紫
}


def fetch_pois(
    bbox: tuple[float, float, float, float],
    categories: list[str] | tuple[str, ...],
    limit: int = 50,
    overpass_timeout: int = 25,
    http_timeout: float = 35.0,
) -> list[POI]:
    """指定 bbox 内のカテゴリ別 POI を取得.

    Args:
        bbox: (south, west, north, east) = (lat_min, lon_min, lat_max, lon_max).
        categories: 取得対象カテゴリ名のリスト(CATEGORY_FILTERS のキー).
        limit: 1 カテゴリあたり上限件数.
        overpass_timeout: Overpass 内部タイムアウト(秒).
        http_timeout: HTTP リクエストタイムアウト(秒).

    Returns:
        POI リスト. 失敗時は空.
    """
    valid_cats = [c for c in categories if c in CATEGORY_FILTERS]
    if not valid_cats:
        return []

    s, w, n, e = bbox
    statements = []
    for cat in valid_cats:
        f = CATEGORY_FILTERS[cat]
        # name タグがあるもの + node(レスポンス軽量化)に限定
        statements.append(f'  node{f}["name"]({s},{w},{n},{e});')

    query = (
        f"[out:json][timeout:{overpass_timeout}];\n"
        f"(\n{chr(10).join(statements)}\n);\n"
        f"out body {limit};"
    )

    # Overpass は POST + data=... 形式が確実(GET だと URL 長制限に当たることもある)
    try:
        r = httpx.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=http_timeout,
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code != 200:
            logger.warning(f"Overpass HTTP {r.status_code}")
            return []
        payload = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Overpass fetch error: {exc}")
        return []

    # remark にエラーが含まれることがある(タイムアウト等)
    remark = payload.get("remark")
    if remark and ("timed out" in str(remark) or "error" in str(remark)):
        logger.info(f"Overpass remark: {remark}")

    pois: list[POI] = []
    seen: set[str] = set()
    for el in payload.get("elements") or []:
        if not isinstance(el, dict):
            continue
        tags = el.get("tags") or {}
        name = (
            tags.get("name:ja")
            or tags.get("name")
            or tags.get("alt_name")
        )
        if not name or not isinstance(name, str):
            continue
        # ノードは lat/lon、ウェイ/リレーションは center
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            continue
        osm_id = f"{el.get('type', '?')}/{el.get('id', '?')}"
        # 重複除去(同じ場所が複数タグでマッチした場合)
        dedup_key = f"{name}-{round(float(lat), 4)}-{round(float(lon), 4)}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        cat = _classify(tags)
        pois.append(
            POI(
                name=str(name),
                category=cat,
                lat=float(lat),
                lon=float(lon),
                osm_id=osm_id,
            )
        )
    return pois


def _classify(tags: dict[str, Any]) -> str:
    """OSM タグから本アプリのカテゴリへ分類."""
    historic = tags.get("historic", "")
    amenity = tags.get("amenity", "")
    religion = tags.get("religion", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    waterway = tags.get("waterway", "")

    if historic in ("castle", "castle_ruins"):
        return "castle"
    if amenity == "place_of_worship" and religion in ("shinto", "buddhist"):
        return "shrine_temple"
    if historic in ("shrine", "temple"):
        return "shrine_temple"
    if amenity in ("public_bath", "onsen"):
        return "onsen"
    if waterway == "waterfall":
        return "waterfall"
    if tourism == "viewpoint":
        return "viewpoint"
    if tourism == "museum":
        return "museum"
    if leisure == "park":
        return "park"
    if tourism == "attraction":
        return "attraction"
    return "other"


def get_prefecture_bbox(
    pref_code: str, margin: float = 0.35
) -> tuple[float, float, float, float] | None:
    """都道府県の主要都市座標から bbox を算出(±約 55km 四方).

    geojson 全体から bbox を取ると、離島(沖ノ鳥島・南鳥島 等)を含む県で
    範囲が膨大になり Overpass がタイムアウトする. 主要都市中心 + margin で
    都市圏の POI に焦点を絞る.

    Args:
        pref_code: '01'〜'47' の JIS X 0401 コード.
        margin: 中心からの度数(0.55 ≒ 約 60km).

    Returns:
        (south, west, north, east). 失敗時は None.
    """
    # 遅延 import(循環回避)
    from app.features.map_view.regions import PREFECTURE_CITY_CENTERS

    center = PREFECTURE_CITY_CENTERS.get(pref_code)
    if not center:
        return None
    lat, lon = center
    return (lat - margin, lon - margin, lat + margin, lon + margin)


__all__ = [
    "CATEGORY_FILTERS",
    "CATEGORY_LABELS",
    "POI",
    "fetch_pois",
    "get_prefecture_bbox",
]
