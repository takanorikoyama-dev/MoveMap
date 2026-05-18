# Changelog

すべての注目すべき変更は本ファイルに記録します。形式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、バージョニングは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

---

## [Unreleased]

### Added(運用品質向上)
- 月次バッチ用 GitHub Actions に `health_check` ステップを追加。結果を artifact として永続化、abnormal なら job 失敗
- CI を Python 3.11 / 3.12 のマトリクスに拡張(将来互換性確認)
- `logger.py` を `RotatingFileHandler` 化(5 MB × 5 世代、合計 25 MB 上限)

---

## [0.1.0] — 2026-05-18

### Highlights
**MoveMap launch-ready リリース**。
twin-build フロー Phase 0-8 を一貫適用し、設計駆動で個人ツール「地方移住MAP」を完成させた。
ローンチ可能なドキュメント・テスト・運用基盤を備える。

### Added(設計フェーズ 2026-05-16〜17)
- Phase 0: 課題定義(50-60 代セカンドキャリア向け、全国地域比較)
- Phase 1: 要求仕様(KGI: プロダクト完成型、Must 6 要件)
- Phase 2: 業務構造(アクター 4 + 4 流情報中心 + R1-R3 ルール)
- Phase 3: 業務フロー(F1 月次バッチ、F2 利用フロー、補償経路 C-01〜07)
- Phase 4: システム要件(SF 21 + 論理 ERD 10 + CRUD + 不変条件 INV 13)
- Phase 5: アーキテクチャ(Python + Streamlit + DuckDB + VSA)
- Phase 6: システム設計 7 種(00 概要〜07 イベント)+ baseline.md
- Phase 7: 実装 17 Usecase + テスト 143 件(Coverage 100%)
- Phase 8: 最終レビュー(99_review.md、総合 A-)

### Added(実装 2026-05-17)
- `app/shared/db.py`: DuckDB 10 テーブル DDL + `HistoryProtectedConnection`(INV-DATA-007 DB 層強制)
- `app/shared/http_client.py`: httpx + tenacity 指数バックオフ + truststore 自動注入(社内 SSL 対応)
- `app/features/data_pipeline/`: 10 Usecase 全本実装(ETL → 正規化 → upsert/append → ARIMA 学習 → 評価 → 予測 → フォールバック → ログ)
- `app/features/data_pipeline/sources/`: 6 公的データソースアダプタ(e-Stat / 地価公示 / 不動産価格指数 / そらまめくん / ハザード / 交通インフラ)
- `app/features/map_view/`: Streamlit 3 タブ UI(MAP / 都道府県詳細 / モデル根拠)
- `app/features/map_view/data_provider.py`: DB → dummy フォールバックファサード(透明性表示付き)
- `app/features/map_view/data_status.py` + `components/status_panel.py`: サイドバー状態サマリ
- `seeds/`: 47 都道府県 + 7 指標 + 6 データソース + hazard_scores + transport_facilities

### Added(運用 2026-05-17〜18)
- `scripts/seed.py` (`--with-synthetic-history` / `--with-synthetic-current` フラグ): API キーなしのデモ可能化
- `scripts/demo.py`: 1 コマンドフルデモ環境構築(`--quick` / `--no-geojson` モード)
- `scripts/snapshot.py` / `scripts/restore.py`: DB スナップショット + 復元(retention 12 世代)
- `scripts/fetch_geojson.py`: 日本 47 都道府県 GeoJSON 自動取得
- `scripts/health_check.py`: DB 状態確認 CLI(human / `--json`、終了コード 0/1/2)
- `STARTUP.md`: 5 分セットアップガイド
- `outputs/DEPLOYMENT.md`: デプロイモード判断(ローカル / プライベートクラウド / 完全公開)
- `outputs/OPERATIONS.md`: 障害対応 runbook(日常運用 / 障害対応 / 定期メンテナンス / 監視)

### Added(CI/CD)
- `.github/workflows/ci.yml`: ruff + mypy + pytest + smoke + pip-audit(2026-05-17)、Python 3.11/3.12 matrix(2026-05-18)
- `.github/workflows/monthly-batch.yml`: 月初 02:00 JST cron + health_check + snapshot artifact(2026-05-18)

### Decisions(twin-build に記録)
- DEC-001 ペルソナ: 50-60代セカンドキャリア
- DEC-002 MAP 粒度: 都道府県のみ
- DEC-005 公開形態: 個人ツール限定
- DEC-007 Must 予測対象: 主要4指標(物価/地価/賃料/出生数)
- DEC-009 (GATE-001) データモデリング: 2段階
- DEC-011 (GATE-002) 技術スタック: Python フルスタック
- DEC-012 Phase 7 完了 → Phase 8 進行
- DEC-013 INV-DATA-007 DB 層強制 完遂
- DEC-014 pip-audit を CI に追加
- DEC-015 Phase 8 完了 → twin-build フロー完結

### Performance
- `prefecture_full_table()`: 28 DB 接続 → 2 SQL クエリ + 1 接続(2026-05-18)

### Bug Fixes
- DuckDB Sequence は対応 Table より前に作る必要があった(seed.py FK 違反、2026-05-17 修正)
- DuckDB `ON CONFLICT DO UPDATE SET = CURRENT_TIMESTAMP` を `now()` に置換(BinderException、2026-05-17 修正)
- DuckDB FK 厳格制約により `ON CONFLICT DO UPDATE` 再実行で失敗 → 存在チェック後 INSERT に変更(2026-05-17 修正)
- `data_provider`: `current_values` 空判定が全 horizon に適用される過剰判定 → `current` horizon に限定(2026-05-18 修正)

### Documentation
- README.md / STARTUP.md / DEPLOYMENT.md / OPERATIONS.md / CHANGELOG.md
- 設計ドキュメント 16 ファイル(outputs/00_problem.md 〜 outputs/99_review.md)
- baseline.md(業務不変条件 18 件: INV-BIZ 5 + INV-DATA 8 + INV-EXT 3 + INV-IDEM 2)

### Tests
- pytest: **143 passed**(高速 default 138 + slow E2E 5)
- Coverage: 全 8 checkpoint 100%

---

## バージョニング指針

- 0.1.x: ローンチ準備期(個人ツール限定運用)
- 0.x: 安定運用 + 細部改善
- 1.0: 公開拡張可能性が見えた時点(DEC-005 撤回判断時)

[Unreleased]: ./
[0.1.0]: ./
