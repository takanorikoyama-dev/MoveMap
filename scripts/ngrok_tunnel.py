"""Streamlit(localhost:8501) を ngrok 経由で一時公開するスクリプト.

使い方:
    1. NGROK_AUTHTOKEN を .env に設定
    2. 別ターミナルで Streamlit を起動(`streamlit run app/main.py --server.port 8501`)
    3. このスクリプトを実行: `python -m scripts.ngrok_tunnel`
    4. 表示された公開 URL をスマホ等から開く

注意:
    - 公開 URL を知った人は誰でもアクセスできます(認証なし)
    - PC をスリープさせると切れます
    - 無料プランは 1 セッション最大 8 時間 / URL は毎回変わる
    - Ctrl+C でトンネルを停止
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

# Windows コンソール(cp932)で絵文字を出力できるよう UTF-8 化
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

load_dotenv()


def main() -> int:
    token = os.environ.get("NGROK_AUTHTOKEN")
    if not token:
        print("ERROR: NGROK_AUTHTOKEN が未設定です。.env に追記してください。", file=sys.stderr)
        return 1

    try:
        from pyngrok import conf, ngrok
    except ImportError:
        print(
            "ERROR: pyngrok が未インストールです。\n"
            "  `uv pip install pyngrok` または `.venv/Scripts/pip install pyngrok` を実行してください。",
            file=sys.stderr,
        )
        return 1

    conf.get_default().auth_token = token
    tunnel = ngrok.connect(8501, "http")
    public_url = tunnel.public_url

    print()
    print("=" * 60)
    print("🌐 ngrok トンネル起動完了")
    print(f"   公開 URL: {public_url}")
    print("   ローカル: http://localhost:8501")
    print("=" * 60)
    print("📱 スマホでも上記 公開 URL を開けばアクセスできます。")
    print("⚠️ 公開 URL を知った第三者もアクセスできます(認証なし)。")
    print("Ctrl+C で停止します。")
    print()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 トンネルを停止します...")
        ngrok.disconnect(public_url)
        ngrok.kill()
        print("停止しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
