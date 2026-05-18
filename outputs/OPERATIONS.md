# 運用 Runbook

## 作成日
2026-05-18

## 対象
MoveMap を実運用する担当者(本人 = 個人ツール想定)向けの運用手順書。
障害対応・定期メンテナンス・データ更新の手順を集約する。

---

## 1. 日常運用

### 1-1. 健康状態の確認

```sh
# 人向け
python -m uv run python scripts/health_check.py

# JSON(他システム連携)
python -m uv run python scripts/health_check.py --json
```

期待される出力(健全):
```
=== MoveMap 健全性レポート (healthy) ===
DB: data/movemap.duckdb
DB 存在: yes
...
```

終了コード:
- `0`: 健全
- `1`: 警告(直近 7 日にエラーあり、または最新バッチが partial)
- `2`: 異常(DB 未生成、最新バッチが failure 等)

### 1-2. UI 起動

```sh
python -m uv run streamlit run app/main.py
# → http://localhost:8501 を開く
```

サイドバーの「データ状態」パネルで:
- 🔵 DB 実データ / 🟡 ダミー の区別を即確認
- 最新バッチの success / partial / failure を即確認
- 直近 7 日のエラー件数を確認

### 1-3. 月次バッチの手動実行(任意)

GitHub Actions cron で自動実行されるが、ローカルで手動実行も可:

```sh
python -m uv run python scripts/run_batch.py
```

実行後:
1. ログを確認(`logs/app.log` も参照)
2. `python scripts/health_check.py` で結果確認
3. 必要なら `python scripts/snapshot.py` でスナップショット作成

---

## 2. 障害対応(Incident Response)

### 2-1. 月次バッチが failure になった

**症状**: `health_check.py` が exit code 2、サイドバーに ❌ 表示

**初動対応**:
1. `audit_logs` を確認
   ```sh
   python -m uv run python -c "from app.shared.db import connect; con = connect(protect_history=False); print(con.execute(\"SELECT * FROM audit_logs WHERE event_type LIKE 'batch.%' ORDER BY occurred_at DESC LIMIT 10\").fetchall())"
   ```
2. `batch_jobs.error_details` を読む
3. ログファイル `logs/app.log` の該当時刻周辺を確認

**根本原因別の対応**:

| 症状 | 原因 | 対応 |
|------|------|------|
| `HttpRetryExhausted: Transport error` | 外部 API 障害 / ネットワーク | 自然回復を待つ、次回バッチで自動再試行(INV-EXT-001) |
| `HttpSchemaError: ...` | 外部 API のレスポンス形式変更 | 該当 source アダプタの parser 更新が必要 |
| `ESTAT_APP_ID が未設定` | Secrets 設定漏れ | `.env` または GitHub Actions Secrets を確認 |
| `Constraint Error: FK violation` | 内部バグ | コード変更を疑う(git diff 確認)、`scripts/restore.py` でロールバック |
| `Catalog Error: Sequence ...` | DDL 順序バグ(2026-05-17 修正済) | 最新コードに更新 |

### 2-2. DB ファイルが壊れた / 不整合

**症状**: pytest が落ちる、INV 違反が出る、UI でエラー表示

**復旧手順**:
1. 現状を退避
   ```sh
   copy data\movemap.duckdb data\movemap.duckdb.bak    # Windows
   cp data/movemap.duckdb data/movemap.duckdb.bak       # POSIX
   ```
2. 最新の snapshot から復元
   ```sh
   python -m uv run python scripts/restore.py
   ```
3. 健全性確認
   ```sh
   python -m uv run python scripts/health_check.py
   ```
4. UI 起動して目視確認

snapshot がない / 全部壊れている場合:
```sh
del data\movemap.duckdb       # Windows
rm data/movemap.duckdb         # POSIX
python -m uv run python scripts/demo.py    # 合成データで復旧(本物データは要再取込)
```

### 2-3. API キーローテーション

```sh
# .env を編集
notepad .env

# GitHub Actions Secret を更新(GitHub Web UI から)
# Settings → Secrets and variables → Actions
# → 該当 Secret を Update

# 動作確認
python -m uv run python scripts/run_batch.py
```

### 2-4. Streamlit が起動しない

| エラー | 対応 |
|--------|------|
| `Port 8501 already in use` | `python -m uv run streamlit run app/main.py --server.port=8502` |
| `ModuleNotFoundError` | `python -m uv sync --extra dev` 再実行 |
| `SSL: CERTIFICATE_VERIFY_FAILED` | `truststore` が正しく注入されているか確認(`http_client.py` 冒頭) |

---

## 3. 定期メンテナンス

### 3-1. 月次(GitHub Actions cron で自動)

| 自動実行 | 内容 |
|---------|------|
| `monthly-batch.yml` | seed → run_batch → snapshot artifact 保存 |
| 結果通知 | GitHub Actions の Job 失敗時に email 通知(GitHub 設定) |

手動で確認すること:
1. GitHub Actions Run History を週次で目視確認
2. 失敗があれば 2-1 の手順で対応

### 3-2. 週次(任意)

```sh
# 依存脆弱性スキャン(GitHub Actions の pip-audit も同等)
python -m uv pip install pip-audit
python -m uv run pip-audit
```

### 3-3. 四半期

- `pyproject.toml` の依存バージョン更新
- `uv lock --upgrade`
- pytest 全体実行(`pytest -m ''` で slow 含む)
- データソース URL の変更がないか目視確認(reinfolib 等)

---

## 4. デプロイ手順

### 4-1. 初回セットアップ(モード A: ローカル限定)

```sh
# 1. リポクローン
git clone <repo-url>
cd MoveMap

# 2. 依存
python -m pip install uv
python -m uv sync --extra dev

# 3. 環境変数
copy .env.example .env       # Windows
cp .env.example .env          # POSIX
# .env を編集して ESTAT_APP_ID, REINFOLIB_API_KEY を設定

# 4. デモ環境構築(API キー不要、約 5 分)
python -m uv run python scripts/demo.py

# 5. UI 起動
python -m uv run streamlit run app/main.py
```

### 4-2. 本番データへの移行

```sh
# 1. 合成データを退避
mv data/movemap.duckdb data/movemap.demo.duckdb

# 2. 本物データで再構築
python -m uv run python scripts/seed.py
python -m uv run python scripts/run_batch.py    # API キー必要

# 3. 健全性確認
python -m uv run python scripts/health_check.py
```

参照: [STARTUP.md](../STARTUP.md) / [DEPLOYMENT.md](DEPLOYMENT.md)

---

## 5. 監視・アラート

### 5-1. 推奨される監視項目

| 項目 | 確認方法 | 閾値 |
|------|---------|------|
| 最新バッチの状態 | `health_check.py` | failure → アラート、partial → 警告 |
| 直近 7 日のエラー数 | `health_check.py` | 0 件 → OK、1 件以上 → 警告 |
| current_values の鮮度 | `health_check.py` の最新タイムスタンプ | 1.5 ヶ月以上更新なし → 警告 |
| 予測モデル R² | `health_check.py` 指標別状況 | 0.6 未満 → 注意(quality_status=no_prediction) |
| ディスク使用量 | OS 標準コマンド | data/snapshots/ が膨らみすぎていないか |

### 5-2. アラート設定(オプション)

GitHub Actions の Job 失敗通知に頼る前提だが、追加で:

- ローカル cron で `health_check.py --json` を毎日実行し、exit code が 2 ならメール通知
- 例(Linux cron):
  ```cron
  0 9 * * * cd /path/to/MoveMap && python -m uv run python scripts/health_check.py --json > /tmp/health.json || mail -s "MoveMap unhealthy" you@example.com < /tmp/health.json
  ```

---

## 6. 既知のリスクと回避策

| リスク | 影響 | 回避策 |
|-------|------|-------|
| reinfolib API URL の変更 | Wave 2 ソースが取得失敗 | 月 1 回手動で URL 確認、404 時は source アダプタ更新 |
| GeoJSON 配信元のリンク切れ | MAP が棒グラフ fallback | `scripts/fetch_geojson.py` 失敗時に通知、代替 URL を `.env` で指定可 |
| Prophet 学習の収束失敗 | 該当指標 R²<0.6 → no_prediction 表示 | 自動フォールバック動作(INV-BIZ-003)、UI で「予測なし」灰色表示 |
| 同時 DB アクセス競合 | DuckDB は単一書込のみ | バッチと UI を同時起動しない、または atomic swap(INFRA-P6-01)を Phase 9 で実装 |

---

## 7. 緊急時の連絡先

個人ツール(DEC-005)のため、運用担当 = ユーザー本人。
共有相手(H-02)に問題が起きた場合は、本人が直接対応する。

---

## 関連ドキュメント

- [STARTUP.md](../STARTUP.md) — 初回セットアップ手順
- [DEPLOYMENT.md](DEPLOYMENT.md) — デプロイモード判断
- [99_review.md](99_review.md) — Phase 8 最終レビュー
- [baseline.md](baseline.md) — 業務不変条件
