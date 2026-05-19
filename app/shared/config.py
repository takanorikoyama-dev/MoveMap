"""アプリ全体の設定値.

環境変数 → .env ファイル → デフォルト値 の優先順で解決する.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    db_path: Path
    seeds_dir: Path
    log_level: str
    estat_app_id: str | None
    # 追加 API キー(後方互換のため None デフォルト)
    reinfolib_api_key: str | None = None
    waqi_token: str | None = None


def load_config() -> Config:
    db_path_str = os.getenv("MOVEMAP_DB_PATH", "data/movemap.duckdb")
    db_path = PROJECT_ROOT / db_path_str if not Path(db_path_str).is_absolute() else Path(db_path_str)

    return Config(
        db_path=db_path,
        seeds_dir=PROJECT_ROOT / "seeds",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        estat_app_id=os.getenv("ESTAT_APP_ID") or None,
        reinfolib_api_key=os.getenv("REINFOLIB_API_KEY") or None,
        waqi_token=os.getenv("WAQI_TOKEN") or None,
    )
