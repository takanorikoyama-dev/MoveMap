# MoveMap 🗾

**地方移住検討者向け、全国 47 都道府県の定量比較 + AI 予測ツール**

主に 50-60 代のセカンドキャリア/リタイア前後の層を想定。物価・地価・賃料・出生数の **3年/5年/10年後 AI 予測** をヒートマップで一覧できます。

⚠️ 本ツールは **個人利用を目的とした参考情報** です。投資判断・意思決定の最終責任はユーザーにあります。

---

## 📚 学習ドキュメント(セールス / AI コンサル向け)

| ドキュメント | 内容 |
|---|---|
| [docs/learning/01_executive_summary.md](docs/learning/01_executive_summary.md) | **5 分で全体を語る**エグゼクティブサマリー |
| [docs/learning/02_self_quiz.md](docs/learning/02_self_quiz.md) | 初級/中級/上級 各 10 問の **自己テスト**(解答 + 解説) |
| [docs/learning/03_architecture.md](docs/learning/03_architecture.md) | **Mermaid 図** + 詳細解説のアーキテクチャ |

---

## 主な機能

| 機能 | 内容 |
|------|------|
| 🗾 全国ヒートマップ | 47 都道府県を Plotly choropleth で表示。指標切替・年次切替対応 |
| 📊 7 指標 | 物価指数 / 地価 / 賃料相場 / 出生数 / 空気質 / 災害リスク / 交通アクセス |
| 🔮 AI 予測 | 主要 4 指標について **ARIMA + Prophet** モデルで 3/5/10 年後を推計 |
| 📋 モデル根拠 | 使用変数・R²/MAE・学習日時を UI で透明化 |
| 📅 月次自動更新 | GitHub Actions cron で 6 つの公的データソースを自動取込 |
| 🛡️ 不変条件強制 | INV-BIZ × 5 + INV-DATA × 8 + INV-EXT × 3 + INV-IDEM × 2(計 18 件) |

---

## クイックスタート(5 分でブラウザ表示)

```sh
# 1. 環境セットアップ(uv 必須)
python -m pip install uv
python -m uv sync --extra dev

# 2. DB 初期化 +デモ用合成履歴投入(API キー不要)
python -m uv run python scripts/seed.py --with-synthetic-history

# 3. 日本地図 GeoJSON 取得(初回のみ)
python -m uv run python scripts/fetch_geojson.py

# 4. アプリ起動 → http://localhost:8501
python -m uv run streamlit run app/main.py
```

これでダミーモデルの予測値が UI に表示されます(🟡 ダミー表示)。
**本物データを使う**には reinfolib / e-Stat の API キーを `.env` に設定し、`run_batch.py` を実行してください(🔵 DB 実データに切替)。

詳細は [STARTUP.md](STARTUP.md) を参照。

---

## 動作モード

| モード | データ取得 | データ表示 | 用途 |
|-------|----------|----------|------|
| **デモ**(API キーなし) | dummy.py の合成データ | 🟡 ダミー | UI 動作確認 |
| **合成履歴投入後**(`seed.py --with-synthetic-history`)| historical_values は実値 | 現在値は 🟡 ダミー、AI 予測は 🔵 DB | 予測モデル動作確認 |
| **本番**(API キー設定 + `run_batch.py` 実行) | 6 つの公的データソース | すべて 🔵 DB 実データ | リリース運用 |

---

## 技術スタック

| カテゴリ | 採用 |
|---------|------|
| 言語 | Python 3.11+ |
| UI | Streamlit + Plotly choropleth |
| DB | DuckDB(組み込み、append-only 強制) |
| HTTP | httpx + truststore(社内 SSL 自動対応)+ tenacity(リトライ) |
| ETL | pandas |
| 予測 | statsmodels(ARIMA/SARIMA) + Prophet |
| スケジューラ | GitHub Actions cron(月初 02:00 JST) |
| パッケージ管理 | uv |
| テスト | pytest + streamlit.testing(117 cases、Coverage 100%) |
| Lint | ruff + mypy |

---

## アーキテクチャ

```
┌─────────────────────┐
│   Streamlit UI      │   app/main.py + features/map_view/
│   (3 tabs)          │   - MAP / 都道府県詳細 / モデル根拠
└──────────┬──────────┘
           │  data_provider.py(DB → dummy fallback)
           ▼
┌─────────────────────┐
│  DuckDB(組み込み)  │   data/movemap.duckdb
│  10 tables + INV    │   - 履歴 append-only 強制
└──────────┬──────────┘   - HistoryProtectedConnection
           ▲
           │  run_batch.py(月次)
┌──────────┴──────────────────────────────────┐
│  ETL + 予測パイプライン                      │
│  fetch → normalize → upsert → append        │
│  retrain → evaluate → predict → fallback    │
└──────────┬──────────────────────────────────┘
           │
           ▼
┌─────────────────────┐
│  6 公的データソース  │  e-Stat / 国交省地価 / 不動産価格指数
│                     │  そらまめくん / ハザードマップ / 交通インフラ
└─────────────────────┘
```

詳細: [outputs/05_architecture.md](outputs/05_architecture.md) / [outputs/06_system_design/](outputs/06_system_design/)

---

## ローンチ READY ステータス(2026-05-18 時点)

| 項目 | 状態 |
|------|------|
| 設計フロー Phase 0-8 | ✅ /review 評価 A- |
| 実装(全 17 Usecase) | ✅ impl 17/17 |
| テスト | ✅ **pytest 117 passed / Coverage 100%** |
| Streamlit 起動確認 | ✅ HTTP 200 / health=ok |
| **UI ⇄ DB データ連携** | ✅(dummy フォールバック付き) |
| **API キーなしデモ可能** | ✅(`--with-synthetic-history`) |
| 月次バッチ(GitHub Actions cron)| ✅ ワークフロー定義済 |
| 不変条件強制(静的+DB 層) | ✅ INV-DATA-007 ともに完備 |
| snapshot / restore | ✅(retention 12 世代) |
| 依存脆弱性スキャン | ✅ pip-audit on CI |
| ドキュメント | ✅ STARTUP.md / 99_review.md / 設計書一式 |

**残作業**:
- reinfolib API キー取得 → 本番 ETL 試走(ユーザー作業)
- Streamlit Cloud or ローカル限定 デプロイ判断(→ [outputs/DEPLOYMENT.md](outputs/DEPLOYMENT.md) 参照)

---

## 設計ドキュメント(参照用)

| Phase | ドキュメント |
|-------|------------|
| 0 課題定義 | [outputs/00_problem.md](outputs/00_problem.md) |
| 1 要求仕様 | [outputs/01_requirements.md](outputs/01_requirements.md) |
| 2 業務構造 | [outputs/02_business_structure.md](outputs/02_business_structure.md) |
| 3 業務フロー | [outputs/03_business_flow.md](outputs/03_business_flow.md) |
| 4 システム要件 | [outputs/04_system_requirements.md](outputs/04_system_requirements.md) |
| 5 アーキテクチャ | [outputs/05_architecture.md](outputs/05_architecture.md) |
| 6 システム設計 | [outputs/06_system_design/](outputs/06_system_design/) |
| 7 実装 | `app/`、`scripts/`、`seeds/`、`tests/`、`.github/` |
| 8 最終レビュー | [outputs/99_review.md](outputs/99_review.md) |
| - 業務不変条件 | [outputs/baseline.md](outputs/baseline.md) |
| - 起動手順 | [STARTUP.md](STARTUP.md) |

---

## データソース

| ソース | 取得指標 | ライセンス |
|--------|---------|----------|
| [e-Stat](https://www.e-stat.go.jp/) | 物価指数・出生数 | 政府標準利用規約 2.0 |
| [国土交通省 地価公示](https://www.land.mlit.go.jp/landPrice_/) | 地価 | 政府標準利用規約 2.0 |
| [国土交通省 不動産価格指数](https://www.reinfolib.mlit.go.jp/) | 賃料相場 | 政府標準利用規約 2.0 |
| [環境省 そらまめくん](https://soramame.env.go.jp/) | 空気質(PM2.5) | 政府標準利用規約 2.0 |
| [国土地理院 ハザードマップ](https://disaportal.gsi.go.jp/) | 災害リスク | 政府標準利用規約 2.0 |
| [国土交通省 交通インフラ](https://www.mlit.go.jp/sogoseisaku/transport/) | 交通アクセス | 政府標準利用規約 2.0 |

各データの出典・最終更新日は本ツール内で常時表示されます。

---

## ライセンス

MIT(コード)/ 各データソースのライセンスに従う(取込データ)

## クレジット

- [dataofjapan/land](https://github.com/dataofjapan/land) — 都道府県境界 GeoJSON
- twin-build フローによる設計駆動開発(Phase 0-8 を一貫トレース)
