# 設計書 02: API設計

## 作成日
2026-05-17

## 位置づけ

本プロジェクトは **Streamlit 単一プロセス** で動作するため、内部 REST/tRPC API は持たない。
本設計書は **外部データソース API クライアント仕様** のみを記述する。

内部の Feature 間通信は **Python 関数呼び出し + DuckDB 共有** で行う(05_architecture.md 参照)。

---

## 外部 API クライアント仕様

### API-EXT-01: e-Stat API(物価指数・出生数)

| 項目 | 値 |
|------|----|
| ベース URL | `https://api.e-stat.go.jp/rest/3.0/app/json/` |
| 認証 | クエリパラメータ `appId`(GitHub Actions Secret 経由) |
| 主要エンドポイント | `getStatsData?statsDataId=...` |
| レスポンス形式 | JSON |
| 差分判定 | `If-Modified-Since` ヘッダー対応(対応箇所のみ)、または `updatedDate` フィールド比較 |
| リトライ | 指数バックオフ 3 回(1s/2s/4s) |
| エラー処理 | API_ERROR → 前回値保持(C-01) |
| Rate Limit | 10 req/sec(超過時は 429 エラーで sleep) |
| 取得対象 | 消費者物価指数・人口動態統計(出生数) |

### API-EXT-02: 国交省地価公示

| 項目 | 値 |
|------|----|
| ベース URL | `https://www.land.mlit.go.jp/webland/api/...`(CSV / API) |
| 認証 | なし |
| 主要エンドポイント | `https://www.land.mlit.go.jp/landPrice_/...`(都道府県別CSV) |
| レスポンス形式 | CSV |
| 差分判定 | URL 末尾の年度パスで判定(年次更新) |
| リトライ | 指数バックオフ 3 回 |
| エラー処理 | 同上 |
| 取得対象 | 都道府県別地価公示 |

### API-EXT-03: 国交省不動産価格指数(賃料相場)

| 項目 | 値 |
|------|----|
| ベース URL | `https://www.reinfolib.mlit.go.jp/api/...`(2026 時点最新) |
| 認証 | なし(将来要登録の可能性、Phase 6 末で確認) |
| レスポンス形式 | JSON / CSV |
| 差分判定 | `month` クエリパラメータでヒット判定 |
| リトライ | 指数バックオフ 3 回 |
| 取得対象 | 都道府県別賃料相場(指数) |

### API-EXT-04: 環境省「そらまめくん」(空気質)

| 項目 | 値 |
|------|----|
| ベース URL | `https://soramame.env.go.jp/...` |
| 認証 | なし(公開 API) |
| レスポンス形式 | JSON(自治体測定局単位 → 都道府県別集計が必要) |
| 集計 | 各都道府県の測定局 PM2.5 を月平均化 |
| 差分判定 | 月次集計のためバッチ実行月単位で判定 |
| リトライ | 指数バックオフ 3 回 |
| 取得対象 | PM2.5 平均値(D-01 で確定済み) |

### API-EXT-05: 国土地理院・ハザードマップポータル

| 項目 | 値 |
|------|----|
| ベース URL | `https://disaportal.gsi.go.jp/...` |
| 認証 | なし |
| レスポンス形式 | GeoJSON / WMS |
| 差分判定 | 年次更新が中心、バッチ月単位でフェッチ |
| 集計 | 47都道府県別に「地震/津波/土砂/洪水」の総合リスクスコアを算出(D-02 の対応として 4 サブスコア+合成 1 で扱う) |
| リトライ | 指数バックオフ 3 回 |
| 取得対象 | 災害リスクスコア(4 サブ + 合成 1) |

### API-EXT-06: 国交省交通インフラ

| 項目 | 値 |
|------|----|
| ベース URL | `https://www.mlit.go.jp/...`(CSV) |
| 認証 | なし |
| レスポンス形式 | CSV(空港・新幹線駅・高速IC 位置情報) |
| 集計 | 各都道府県のアクセス指標(最寄りの空港/新幹線駅/IC からの距離) |
| 差分判定 | 年次データ |
| リトライ | 指数バックオフ 3 回 |
| 取得対象 | 交通アクセス指標 |

---

## 共通仕様

### エラーカタログ

| エラーコード | 説明 | 発生条件 | 対応 |
|------------|------|--------|------|
| `ERR_API_TIMEOUT` | API タイムアウト | 30秒以内に応答なし | リトライ 3 回 → 失敗時前回値 |
| `ERR_API_429` | Rate Limit 超過 | API 側の制限 | sleep + リトライ |
| `ERR_API_SCHEMA` | レスポンス形式異常 | 期待スキーマ不一致 | バッチ失敗 → AuditLog 記録 |
| `ERR_DATA_INTEGRITY` | データ整合性エラー | 値域不正・FK 不整合 | upsert スキップ + ログ |

### 共通 HTTP クライアント

`shared/http_client.py` に集約:
- httpx.AsyncClient ベース
- 指数バックオフリトライ(tenacity)
- User-Agent: `MoveMap/0.1.0 (personal-tool)`
- タイムアウト: 30 秒
- ログ: `request_url`, `status_code`, `response_time_ms`

### Secret 管理

- e-Stat AppID: GitHub Actions Secret `ESTAT_APP_ID` 経由で渡す(SEC-P5-01 対応)
- ローカル実行時は `.env` ファイル(.gitignore)

---

## API 設計の対象外

- 内部 REST/tRPC エンドポイント — Streamlit 単一プロセスのため不要
- 認証/認可 API — 単一ユーザー、認証なし
- WebSocket/SSE — リアルタイム通信不要

---

## Coverage 影響

| Usecase | API カバレッジ |
|---------|--------------|
| `FetchExternalData` | API-EXT-01〜06 を呼び分け |
| `RunBatch` | 直接 API は呼ばないが、FetchExternalData を経由 |
| その他 Usecase | API なし(内部関数呼び出しのみ) |
