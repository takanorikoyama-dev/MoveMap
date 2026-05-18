# アーキテクチャ

## 作成日
2026-05-17

## 入力ドキュメント
- `outputs/04_system_requirements.md`

## このドキュメントの位置づけ

Phase 4 のシステム要件(SF-001〜021、論理ERD、CRUD、不変条件)を実現するための技術スタック・Feature 分割・Usecase・ディレクトリ構造を確定する。
個人ツール限定(DEC-005)・3ヶ月 MVP の制約下で、最小限のコストで動作するシンプルな構成を採用。

---

## 技術スタック(DEC-011 で A 案を採用)

| カテゴリ | 採用 | 理由 |
|---------|------|------|
| 言語 | Python 3.11+ | データ処理・AI 予測・UI を 1 言語で完結 |
| UI | Streamlit | データ可視化のプロトタイプ最速、47都道府県のヒートマップを最小コードで実現 |
| 地図ライブラリ | Plotly choropleth | Streamlit との相性が良く対話的ヒートマップに最適 |
| DB | DuckDB | 分析特化・組み込み・地理拡張あり、個人ツール規模で運用負荷最小 |
| ETL | httpx + pandas | 標準的な HTTP/CSV 取得+データ処理 |
| 時系列予測 | statsmodels (ARIMA/SARIMA) + Prophet | 主要4指標で評価し、精度の良い方を採用 |
| スケジューラ | GitHub Actions(cron) | 個人開発で運用負荷ゼロ、無料、ログ閲覧容易 |
| パッケージ管理 | uv | pip より高速、最新ベストプラクティス |
| テスト | pytest | Python 標準 |
| 静的解析 | ruff + mypy | Lint + 型チェック |
| ホスティング | Streamlit Community Cloud または ローカル | 無料デプロイ + 個人ツール限定 |
| アーキテクチャパターン | VSA(Vertical Slice Architecture) | Feature/Usecase 単位で凝集、AI による実装支援との相性が良い |

将来公開拡張する場合の移行パス: Streamlit → React + FastAPI(同じ Python バックエンドを再利用)。

---

## Feature 分割

| Feature | 役割 | 含む SF | 主要集約 |
|---------|------|---------|---------|
| `map_view` | UI 表示・操作 | SF-001〜005 | (集約なし、read-only) |
| `data_pipeline` | ETL + 予測モデル | SF-010〜019 | 4 集約(下記) |
| `compliance` | 免責・出典 | SF-020, SF-021 | (集約なし) |

### Feature 分割の根拠

- **map_view**: 表示・操作の責務を集約。テストはスナップショット中心で容易
- **data_pipeline**: ETL+予測の責務を集約。バッチ実行は CLI スクリプトとして独立起動可能
- **compliance**: 法的責任を分離するための小 Feature。INV-BIZ-005(免責バナー必須)を担保する

---

## Usecase 一覧

### Feature `map_view`(query)

| Usecase | 対応 SF | 概要 |
|---------|---------|------|
| `ShowMap` | SF-001 | 47都道府県の選択中指標・年次でヒートマップ描画 |
| `SwitchIndicator` | SF-002 | 7指標から1つを選び再描画 |
| `SwitchHorizon` | SF-003 | 現在/3/5/10年を切替 |
| `ShowPrefectureDetail` | SF-004 | 1都道府県の全指標(現在+予測)を詳細表示 |
| `ShowModelDetail` | SF-005 | AI モデルの根拠ページ表示 |

### Feature `data_pipeline`(mutation)

| Usecase | 対応 SF | 概要 |
|---------|---------|------|
| `RunBatch` | SF-010 | バッチ全体のオーケストレーション |
| `FetchExternalData` | SF-011 | 各データソースからの取得(差分判定込み) |
| `NormalizeData` | SF-012 | 都道府県コード・単位・型の統一 |
| `UpsertCurrentValues` | SF-013 | CurrentValue テーブル upsert |
| `AppendHistory` | SF-014 | HistoricalValue 追記 |
| `RetrainModels` | SF-015 | 主要4指標のモデル再学習 |
| `EvaluateModels` | SF-016 | R²/MAE 計算 |
| `GeneratePredictions` | SF-017 | 47×4×3 予測値生成 |
| `ApplyFallback` | SF-018 | R²<0.6 指標を no_prediction に |
| `LogBatchOutcome` | SF-019 | BatchJob.status 更新 + AuditLog 記録 |

### Feature `compliance`(query)

| Usecase | 対応 SF | 概要 |
|---------|---------|------|
| `ShowDisclaimer` | SF-020 | 免責バナーの全画面表示 |
| `ShowDataSources` | SF-021 | 指標のデータ出典・最終更新日表示 |

---

## Feature 依存マップ

```
map_view ──read-only──> [DuckDB] <──write── data_pipeline
   │
   └──refs──> compliance
```

- 循環依存なし
- 個人ツール&単一プロセスのため、Feature 間連携は **DuckDB 共有 + 関数呼び出し**(REST API 化は不要)

---

## 集約一覧(Theme 3 第一段階、詳細は Phase 6 で確定)

| 集約 | Root | 所属 Feature | 含むエンティティ(粗く) | 不変条件(粗く、業務的意味) |
|------|------|------------|----------------------|--------------------------|
| `IndicatorAggregate` | Indicator | data_pipeline | Indicator + DataSource | INV-BIZ-002: 主要4指標は is_predictable=true。INV-DATA-008: update_frequency は限定列挙 |
| `RegionMeasurement` | Prefecture | data_pipeline | Prefecture + CurrentValue + HistoricalValue | INV-BIZ-001: 47件固定。INV-DATA-001/002: FK 整合 + 一意性。INV-DATA-007: 履歴 append-only |
| `Prediction` | PredictionModel | data_pipeline | PredictionModel + ModelEvaluation + PredictedValue | INV-BIZ-003: R²<0.6 は no_prediction。INV-DATA-003/004/005: 一意性と FK 整合。INV-DATA-006: horizon_years は {3,5,10} |
| `BatchExecution` | BatchJob | data_pipeline | BatchJob + AuditLog | INV-BIZ-004: バッチ開始時に BatchJob C |

---

## サービス間データ共有方法(Theme 2 必須)

| Entity | ライフサイクル | Owner Feature | 共有方法 | 鮮度 |
|--------|------------|-------------|--------|------|
| Prefecture | master | data_pipeline | 直接 read(同一プロセス) | 業務サイクル |
| Indicator | master | data_pipeline | 直接 read | 業務サイクル |
| DataSource | master | data_pipeline | 直接 read | 業務サイクル |
| CurrentValue | transactional | data_pipeline | 直接 read (read-only 規約) | 月次 |
| HistoricalValue | append_only_history | data_pipeline | 直接 read | — |
| PredictionModel | transactional | data_pipeline | 直接 read | 業務サイクル |
| ModelEvaluation | append_only_history | data_pipeline | 直接 read | — |
| PredictedValue | transactional | data_pipeline | 直接 read | 月次 |
| BatchJob | append_only_history | data_pipeline | 直接 read | — |
| AuditLog | append_only_history | data_pipeline | 直接 read | — |

**既定外の選択(例外パターン)**:
- `transactional` を同期 read で `map_view` が直接参照 — **理由**: 単一プロセスのため即時鮮度可・結合コスト最小

---

## ドメインイベントカタログ(Theme 4 第一段階)

**該当なし** — 個人ツールで集約はすべて `data_pipeline` Feature 内に閉じる。集約をまたぐ業務イベントなし。

将来公開拡張する場合は `BatchCompleted` `ModelEvaluated` 等のイベント化を検討余地あり(別 Feature が購読する状況になったタイミングで追加)。

---

## 外部連携

| 連携先 | 用途 | 認証 | リトライ |
|--------|------|------|---------|
| e-Stat API | 物価指数・出生数 | アプリ ID(無料登録) | 指数バックオフ 3 回 |
| 国交省地価公示 | 地価 | なし(CSV/API) | 指数バックオフ 3 回 |
| 不動産価格指数(国交省) | 賃料相場 | なし(CSV) | 指数バックオフ 3 回 |
| 環境省そらまめくん | 空気質(PM2.5/AQI 等、Phase 4 D-01 で詳細化) | なし(API) | 指数バックオフ 3 回 |
| 国土地理院ハザード | 災害リスク(GeoJSON、D-02 で分解方針確定) | なし(GeoJSON) | 指数バックオフ 3 回 |
| 国交省交通インフラ | 空港・新幹線駅・高速 IC 位置 | なし(CSV) | 指数バックオフ 3 回 |

**段階的導入(DESIGN-01)**:
- Wave 1(MVP 第1ヶ月): e-Stat(物価/出生)+ 地価公示
- Wave 2(MVP 第2ヶ月): 賃料相場 + 空気質
- Wave 3(MVP 第3ヶ月): 災害リスク + 交通アクセス

---

## ディレクトリ構造

```
MoveMap/
├── .twin-build.json
├── pyproject.toml          # uv プロジェクト定義
├── README.md
├── .github/workflows/
│   ├── ci.yml              # lint + tests
│   └── monthly-batch.yml   # 月初 02:00 JST cron
├── app/
│   ├── main.py             # Streamlit エントリ
│   ├── features/
│   │   ├── map_view/
│   │   │   ├── usecases/
│   │   │   │   ├── show_map.py
│   │   │   │   ├── switch_indicator.py
│   │   │   │   ├── switch_horizon.py
│   │   │   │   ├── show_prefecture_detail.py
│   │   │   │   └── show_model_detail.py
│   │   │   └── components/  # UI 部品(ヒートマップ・凡例・操作パネル)
│   │   ├── data_pipeline/
│   │   │   ├── usecases/   # 上記10 Usecase
│   │   │   ├── sources/    # 各データソースアダプタ
│   │   │   │   ├── estat.py
│   │   │   │   ├── land_value.py
│   │   │   │   ├── rent_index.py
│   │   │   │   ├── air_quality.py
│   │   │   │   ├── hazard.py
│   │   │   │   └── transport.py
│   │   │   └── models/     # ARIMA/Prophet ラッパ
│   │   └── compliance/
│   │       ├── show_disclaimer.py
│   │       └── show_data_sources.py
│   ├── shared/             # db.py, config.py, logger.py
│   └── domain/             # エンティティ・値オブジェクト
├── data/                   # *.duckdb(.gitignore)+ snapshots/
├── seeds/                  # prefectures.csv, indicators.csv
├── tests/
│   ├── unit/
│   ├── integration/
│   └── smoke/
└── scripts/
    ├── run_batch.py        # CI から呼ぶエントリ
    └── seed.py             # 初期化スクリプト
```

**レイヤー依存ルール**(VSA):
- features/ → shared/ / domain/(逆方向不可)
- features 間は直接 import しない(必要なら domain/ を経由)
- shared/ → domain/ のみ依存可

---

## アーキテクチャ必須チェックリスト

| カテゴリ | 確認項目 | 対応 |
|---------|---------|------|
| スケジュール | 定期実行 | GitHub Actions `monthly-batch.yml` で月初 02:00 JST に `scripts/run_batch.py` 実行 |
| 認証 | 認証方式 | 該当なし(個人ツール限定、DEC-005) |
| 外部連携 | Webhook 署名検証 | 該当なし(Webhook を使わない) |
| セキュリティ | 暗号化対象 | 該当なし(公的データのみ、個人情報非含有) |
| セキュリティ | 認可マトリクス | 該当なし(単一ユーザー) |
| インフラ | DB バックアップ | 月次バッチ後の DuckDB スナップショットを `data/snapshots/YYYYMM/` に保存(直近 12 世代) |
| インフラ | コネクションプーリング | 該当なし(DuckDB はファイルベース) |
| 監視 | エラー監視 | アプリログを `logs/app.log` に出力。バッチ失敗は GitHub Actions ジョブの失敗通知 |
| QA | テスト戦略 | unit(pytest) + integration(DuckDB 実DBで) + smoke(Streamlit 起動確認) |
| QA | CI/CD | GitHub Actions: `ci.yml`(ruff + pytest)+ `monthly-batch.yml`(cron) |
| 運用 | ヘルスチェック | 推奨だが MVP では省略 |
| 運用 | ロールバック手順 | DB スナップショットから復元(`scripts/restore.py` を Phase 6 で詳細化) |

---

## Architecture Intent Record(AIR)

### AIR-01: Streamlit 採用

- **判断**: Python フルスタックの UI に Streamlit を選定
- **理由**: 個人ツール&データ可視化に最も少ないコードで MAP UI を構築可能。再描画モデルがシンプル
- **却下案**: Dash(より宣言的だがコード量増)、自作 Flask + Jinja2(運用負荷高)
- **受容したトレードオフ**: 大規模化時の UI 表現自由度の制約
- **変更条件**: 公開拡張・複数ユーザー対応・モバイル UI 要件 → React + FastAPI へ移行

### AIR-02: DuckDB 採用

- **判断**: DB に DuckDB を選定
- **理由**: 分析特化のカラム指向、ファイルベース、地理拡張(spatial)が利用可、低運用
- **却下案**: SQLite(分析機能が限定的)、PostgreSQL(個人ツールには過剰)
- **受容したトレードオフ**: 同時書き込みの制約(個人ツールなので問題なし)
- **変更条件**: 複数同時ユーザー・大規模履歴データ → PostgreSQL へ移行

### AIR-03: Feature A/B/C 分割

- **判断**: map_view / data_pipeline / compliance の 3 Feature 分割
- **理由**: 表示・データ更新・法的責務の責務分離。テスト・デプロイ単位として明快
- **却下案**: フラット構造(規模拡張時に痛む)
- **受容したトレードオフ**: 個人開発として若干のオーバーヘッド
- **変更条件**: Should/Could 追加で Feature が増える場合は再分割を検討

### AIR-04: GitHub Actions cron 採用

- **判断**: スケジューラに GitHub Actions cron を選定
- **理由**: 個人開発で運用負荷ゼロ・無料・ログ閲覧容易・複数環境(ローカル/CI/Cloud)で同じ動作
- **却下案**: systemd timer(ローカル限定)、Render cron(コスト発生)
- **受容したトレードオフ**: GitHub Actions の月次無料枠制限(個人ツールでは問題なし)
- **変更条件**: 頻繁な定期実行・大量データ処理 → 専用ジョブ実行基盤へ

### AIR-05: VSA(Vertical Slice Architecture)採用

- **判断**: Feature / Usecase 単位のディレクトリ構造を採用
- **理由**: AI による実装支援(Phase 7)との相性が良く、Usecase 単位でテストしやすい
- **却下案**: レイヤード(controllers/services/repositories/...)
- **受容したトレードオフ**: 横断的処理(認証・ロギング)の重複(個人ツールでは影響軽微)
- **変更条件**: 将来 React + FastAPI に移行する場合も VSA を維持

---

## Phase 4 要件のカバー状況(SF レベル)

全 21 SF を Usecase に 1:1 マッピング完了:

| Phase 4 SF | Phase 5 Usecase | Feature |
|-----------|----------------|---------|
| SF-001〜005 | `ShowMap`, `SwitchIndicator`, `SwitchHorizon`, `ShowPrefectureDetail`, `ShowModelDetail` | map_view |
| SF-010〜019 | `RunBatch`, `FetchExternalData`, `NormalizeData`, `UpsertCurrentValues`, `AppendHistory`, `RetrainModels`, `EvaluateModels`, `GeneratePredictions`, `ApplyFallback`, `LogBatchOutcome` | data_pipeline |
| SF-020, SF-021 | `ShowDisclaimer`, `ShowDataSources` | compliance |

---

## Phase 4 持ち越し論点への対応

| ID | 内容 | Phase 5 での対応 |
|----|------|----------------|
| TECH-01 DB 選定 | DuckDB に確定(AIR-02) |
| TECH-02 言語・FW | Python + Streamlit に確定(DEC-011) |
| TECH-03 フロント | Streamlit + Plotly choropleth に確定 |
| TECH-04 AI ライブラリ | statsmodels(ARIMA) + Prophet に確定(Phase 6 で評価対決) |
| TECH-05 スケジューラ | GitHub Actions cron に確定(AIR-04) |
| TECH-06 データソース取得実装 | sources/ 配下にアダプタ層を配置(Phase 6 で各アダプタ詳細化) |
| TECH-07 ETL→予測の同期/非同期 | 同期実行(個人ツール、単一プロセス) |
| DESIGN-01 段階的導入 | Wave 1/2/3 の月次計画を本ドキュメントに記載 |
| DESIGN-02 災害リスク分解 | Phase 6 で確定(複数指標化検討) |
| DESIGN-03 環境(空気)の指標 | Phase 6 で「そらまめくん」AQI/PM2.5 を確定 |
| DESIGN-04 ヒートマップ階層 | Phase 6 でユーザーテスト |
| DESIGN-05 「予測なし」表示 | Phase 6 で UI 詳細化 |
| DESIGN-06 URL/PDF 共有 | スコープ外維持 |
| LEGAL-01 データソース利用規約 | Phase 6 で各ソースのライセンス・クレジット確認 |
| LEGAL-02 コード公開ライセンス | Phase 6 で確定(MIT 推奨、Phase 7 リリース判断時に最終化) |
| OPS-01 履歴テーブル保管期間 | スナップショット 12 世代(1年分)に確定 |
| OPS-02 R² 評価期間 | Phase 6 で評価期間(直近 5 年等)を確定 |

---

## Phase 6 へ持ち越す論点

| ID | 内容 |
|----|------|
| P6-01 | データソース別の取得仕様詳細(API エンドポイント、フィールド、サンプル) |
| P6-02 | AI モデル選定の最終評価(ARIMA vs Prophet、評価期間、ハイパーパラメータ) |
| P6-03 | 集約境界の確定(削除カスケード、Cross-Boundary Reference、不変条件の検証方法) |
| P6-04 | 物理 ERD(DuckDB の型・インデックス) |
| P6-05 | UI 詳細(ヒートマップ階層、年次切替UI、「予測なし」表示) |
| P6-06 | コード公開ライセンス選定 |
| P6-07 | snapshot 復元手順詳細(`scripts/restore.py`) |

---

## Phase 5 で記録した主要判断

| ID | 判断 | 結論 |
|----|------|------|
| DEC-011 (GATE-002) | 技術スタック方向性 | A: Python フルスタック(Streamlit + DuckDB) |

---

## 備考

- アーキテクチャパターン: VSA を維持
- 「個人ツール」前提を継続。将来公開拡張時には Streamlit → React + FastAPI への移行を意識
- Phase 5 完了後は Phase 6(システム設計)へ
