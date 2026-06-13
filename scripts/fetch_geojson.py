"""47都道府県の GeoJSON を取得し seeds/japan_prefectures.geojson に保存する.

公開オープンデータの一例として dataofjapan を利用する.
ライセンス: パブリックドメイン (https://github.com/dataofjapan/land).
他に国土地理院の GeoJSON も利用可。Phase 5/6 で LEGAL-01 として整理.
"""

from __future__ import annotations

import sys

from app.shared.config import PROJECT_ROOT
from app.shared.http_client import HttpRetryExhausted, get_json
from app.shared.logger import get_logger

logger = get_logger(__name__)

JAPAN_GEOJSON_URL = "https://raw.githubusercontent.com/dataofjapan/land/master/japan.geojson"
LOCAL_PATH = PROJECT_ROOT / "seeds" / "japan_prefectures.geojson"


def main() -> int:
    if LOCAL_PATH.exists():
        logger.info(f"既存ファイルあり: {LOCAL_PATH}")
        return 0

    logger.info(f"GeoJSON を取得: {JAPAN_GEOJSON_URL}")
    try:
        payload = get_json(JAPAN_GEOJSON_URL)
    except HttpRetryExhausted:
        logger.exception("GeoJSON 取得失敗。手動で配置してください")
        return 1

    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import json

    LOCAL_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(f"保存完了: {LOCAL_PATH} ({LOCAL_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
