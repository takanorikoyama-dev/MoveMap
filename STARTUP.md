# STARTUP — 初回セットアップから動作確認まで

このドキュメントは MoveMap を**何もない状態から動かせる状態**まで持っていく手順をまとめたものです。
所要時間: 約 10〜15 分(uv の依存解決時間込み)。

---

## 1. 前提条件

| 必須 | 内容 |
|------|------|
| OS | Windows 10/11、macOS 11+、Linux(Ubuntu 22.04+) |
| Python | 3.11 以上(3.14 で動作確認済) |
| pip | システム Python に同梱 |
| ネットワーク | 初回のみ依存パッケージ + GeoJSON 取得に必要 |

社内ネットワーク等で SSL 自己署名証明書チェーンが入っている環境でも、本プロジェクトは `truststore` を組み込んでいるため OS 信頼ストアから証明書を自動取得します(別途設定不要)。

---

## 2. インストール手順

### 2-1. uv の導入

```sh
# Windows / macOS / Linux 共通
python -m pip install uv
```

確認:

```sh
python -m uv --version    # uv 0.11.x 以上
```

### 2-2. 依存パッケージのインストール

リポジトリのルート(`MoveMap/`)に `cd` してから:

```sh
python -m uv sync --extra dev
```

これで `.venv/` が作成され、以下が install されます:

- ランタイム: streamlit / plotly / duckdb / pandas / httpx / tenacity / statsmodels / prophet / python-dotenv / **truststore**
- 開発: pytest / pytest-mock / pytest-httpx / freezegun / ruff / mypy

初回は 1〜3 分かかります(prophet が重い)。

### 2-3. 環境変数の準備

`.env.example` を `.env` にコピーし、必要な値を埋めます:

```sh
copy .env.example .env    # Windows
cp .env.example .env      # macOS / Linux
```

| キー | 必須 | 取得方法 |
|------|------|---------|
| `ESTAT_APP_ID` | Wave 1 で必要 | https://www.e-stat.go.jp/api/ で無料登録 |
| `REINFOLIB_API_KEY` | Wave 2 で必要 | https://www.reinfolib.mlit.go.jp/api/ で登録 |
| `MOVEMAP_DB_PATH` | 任意(既定: data/movemap.duckdb) | — |
| `LOG_LEVEL` | 任意(既定: INFO) | DEBUG / INFO / WARNING / ERROR |

API キーがなくても streamlit 起動とダミーデータ表示は動作します(本物データは取り込まれません)。

---

## 3. データ初期化

### 3-1. DuckDB スキーマ + マスタ投入

```sh
python -m uv run python scripts/seed.py
```

期待出力:

```
INFO __main__: DuckDB を初期化し seeds を投入します
INFO __main__: seeds 投入完了: data_sources=6, indicators=7, prefectures=47
INFO __main__: INV-BIZ-001 (prefectures = 47) OK
```

これで `data/movemap.duckdb` が作成され、マスタ(都道府県 47 / 指標 7 / データソース 6)が投入されます。

### 3-2. 日本地図 GeoJSON 取得

```sh
python -m uv run python scripts/fetch_geojson.py
```

`seeds/japan_prefectures.geojson`(約 3.2 MB)が保存されます。
これがない場合、ヒートマップは棒グラフフォールバックになります。

---

## 4. テスト実行

```sh
python -m uv run pytest tests/ -v
```

期待:

```
================ 72 passed, 1 skipped in ~45s ================
```

skip 1 件は `INV-DATA-007` のアプリ層強化が将来課題のため意図的に skip(設計通り)。

各カテゴリ別実行:

```sh
python -m uv run pytest tests/unit -v          # 単体テスト(高速)
python -m uv run pytest tests/integration -v   # 統合テスト(DuckDB in-memory)
python -m uv run pytest tests/smoke -v         # Streamlit AppTest(やや遅い)
```

---

## 5. アプリ起動

### 5-1. 通常起動

```sh
python -m uv run streamlit run app/main.py
```

→ ブラウザで `http://localhost:8501` が自動的に開きます。
ローカル限定推奨(`--server.headless=false` を明示しない限り、新しいタブが開きます)。

### 5-2. ヘッドレス(サーバーのみ)起動

```sh
python -m uv run streamlit run app/main.py `
    --server.headless=true `
    --server.port=8501 `
    --browser.gatherUsageStats=false
```

健康チェック:

```sh
curl http://localhost:8501/_stcore/health     # 期待: ok
```

### 5-3. 確認できる UI 要素

- 上部: 「MoveMap — 地方移住MAP」タイトル + ⚠️ 免責バナー(`INV-BIZ-005` を担保)
- サイドバー: 指標選択(7 指標) + 年次選択(現在/3/5/10年)
- 中央: 3 タブ
  - **MAP**: 47 都道府県のヒートマップ(Plotly choropleth、ダミーデータ)
  - **都道府県詳細**: 都道府県を選んで 7 指標 × 4 時点の表
  - **モデル根拠**: ARIMA(2,1,2) ダミー情報 + 過去予測 vs 実測グラフ
- 下部: データ出典キャプション(`SF-021`)

---

## 6. 月次バッチ手動実行(任意)

```sh
python -m uv run python scripts/run_batch.py
```

期待出力:

```
INFO __main__: 月次バッチを起動
INFO __main__: BatchOutcome: job_id=N status=partial records=0 sources_ok=1/6 ...
```

API キー未設定の状態では各 source の fetch が空になるため partial 終了します(意図通り、`INV-EXT-001` で前回値保持の挙動)。

GitHub Actions cron(`.github/workflows/monthly-batch.yml`)は毎月 1 日 02:00 JST に自動実行されます。

---

## 7. Lint / Type check

```sh
python -m uv run ruff check .
python -m uv run mypy app/
```

`mypy` は CI で `continue-on-error: true` です(個人ツールなので段階的に厳しくする方針)。

---

## 8. トラブルシューティング

### 8-1. SSL 証明書エラー

```
httpx.ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] ...
```

- 原因: 社内ネットワーク等の自己署名証明書チェーンが介在
- 対処: `app/shared/http_client.py` の `truststore.inject_into_ssl()` が OS 信頼ストアを利用するため、Windows / macOS は通常自動解決。Linux で発生する場合は環境変数 `SSL_CERT_FILE` で CA バンドルを指定

### 8-2. ポート 8501 が使用中

```
OSError: [WinError 10048] ... port 8501 ...
```

- 対処: 既存の streamlit プロセスを停止するか、別ポートを指定
  ```sh
  python -m uv run streamlit run app/main.py --server.port=8502
  ```

### 8-3. DuckDB DDL エラー

```
_duckdb.CatalogException: Catalog Error: Sequence ... does not exist!
```

- 原因: 古いバージョンの `app/shared/db.py`(Sequence 順序バグ、2026-05-17 修正済)
- 対処: 最新コードに更新後 `data/movemap.duckdb` を一度削除して再実行
  ```sh
  rm data/movemap.duckdb     # 削除前に念のためバックアップ推奨
  python -m uv run python scripts/seed.py
  ```

### 8-4. Prophet のインストールに失敗

- Windows: Visual Studio Build Tools が必要な場合あり
- macOS: Apple Silicon は `pip install prophet` でクリーンに通る
- 対処: 公式手順 https://facebook.github.io/prophet/docs/installation.html を参照

### 8-5. virtualenv 警告

```
warning: VIRTUAL_ENV=... does not match the project environment path .venv ...
```

- 原因: シェルが既に別の venv をアクティベートしている
- 対処: 警告のみで動作は問題なし。気になる場合は `deactivate` 後に再実行

---

## 9. 開発ループ

```sh
# 1. 既存コード変更
# 2. テストを書く / 更新する
python -m uv run pytest tests/ -v

# 3. Lint
python -m uv run ruff check . --fix

# 4. UI で確認
python -m uv run streamlit run app/main.py

# 5. 月次バッチを試す
python -m uv run python scripts/run_batch.py
```

---

## 10. 設計ドキュメントへのリンク

- [課題定義 (Phase 0)](outputs/00_problem.md)
- [要求仕様 (Phase 1)](outputs/01_requirements.md)
- [業務構造 (Phase 2)](outputs/02_business_structure.md)
- [業務フロー (Phase 3)](outputs/03_business_flow.md)
- [システム要件 (Phase 4)](outputs/04_system_requirements.md)
- [アーキテクチャ (Phase 5)](outputs/05_architecture.md)
- [システム設計 (Phase 6)](outputs/06_system_design/)
- [業務不変条件 baseline](outputs/baseline.md)
- [最終レビュー (Phase 8)](outputs/99_review.md)

---

## 11. 次にやることリスト(運用フェーズ)

1. **Wave 2 実 API 検証**(reinfolib API キー登録 → e-Stat 動作確認 → 残り 5 ソース順次)
2. **seeds JSON の本物データ整備**(`seeds/hazard_scores.json` / `seeds/transport_facilities.json`)
3. **GitHub Actions 動作確認**(workflow_dispatch で monthly-batch.yml 試走)
4. **INV-DATA-007 DB 層強制**(DEC-013、現状は静的検証のみ)
5. **公開拡張時の論点整理**(Streamlit Cloud デプロイ / 認証 / 課金 / マルチユーザー)
