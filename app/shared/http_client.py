"""共通 HTTP クライアント(httpx + tenacity リトライ).

設計参照: outputs/06_system_design/02_API設計.md「共通 HTTP クライアント」
不変条件: INV-EXT-001 (リトライ失敗で前回値保持), INV-EXT-002 (3回連続失敗で警告)
"""

from __future__ import annotations

from typing import Any

import httpx

# 企業ネットワーク等の自己署名証明書チェーンに対応するため、OS の信頼ストアを利用する.
# truststore 未インストール環境でも httpx 既定の certifi で動作するようにする.
try:
    import truststore  # type: ignore[import-not-found]

    truststore.inject_into_ssl()
except ImportError:
    pass
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.shared.logger import get_logger

logger = get_logger(__name__)

USER_AGENT = "MoveMap/0.1.0 (personal-tool)"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3


class HttpClientError(Exception):
    """HTTP クライアント全般の基底エラー."""


class HttpRetryExhausted(HttpClientError):
    """指数バックオフ後も成功しなかった(C-01 / INV-EXT-001 発動)."""


class HttpSchemaError(HttpClientError):
    """レスポンスが期待スキーマと一致しない(ERR_API_SCHEMA)."""


@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def _do_get(client: httpx.Client, url: str, params: dict[str, Any] | None, headers: dict[str, str] | None) -> httpx.Response:
    response = client.get(url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT_SECONDS)
    if response.status_code == 429:
        # Rate Limit。tenacity に再試行させる
        raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
    response.raise_for_status()
    return response


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """GET → JSON デコード.

    Args:
        url: 取得先 URL.
        params: クエリパラメータ.
        headers: 追加ヘッダー.

    Returns:
        パースされた JSON.

    Raises:
        HttpRetryExhausted: 指数バックオフ後も失敗.
        HttpSchemaError: JSON でない・パース失敗.
    """
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    try:
        with httpx.Client() as client:
            response = _do_get(client, url, params, request_headers)
    except RetryError as exc:
        raise HttpRetryExhausted(f"Retry exhausted for {url}") from exc
    except httpx.TransportError as exc:
        # 最終リトライまで失敗
        raise HttpRetryExhausted(f"Transport error for {url}: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise HttpRetryExhausted(f"HTTP {exc.response.status_code} for {url}") from exc

    try:
        return response.json()
    except (ValueError, httpx.DecodingError) as exc:
        raise HttpSchemaError(f"Invalid JSON from {url}") from exc


def head_last_modified(url: str) -> str | None:
    """HEAD で Last-Modified ヘッダーを取得(差分判定用).

    Returns:
        ISO 形式の更新日時、または None.
    """
    try:
        with httpx.Client() as client:
            response = client.head(url, headers={"User-Agent": USER_AGENT}, timeout=DEFAULT_TIMEOUT_SECONDS)
            if response.is_success:
                return response.headers.get("Last-Modified")
    except httpx.TransportError as exc:
        logger.warning(f"HEAD failed for {url}: {exc}")
    return None
