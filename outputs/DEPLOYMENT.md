# デプロイ判断ドキュメント

## 作成日
2026-05-18

## 背景

MoveMap は DEC-005 で **個人ツール限定** として定義された。Phase 7 完了、Coverage 100%、E2E 動作確認済の今、デプロイ形態を改めて整理する。

## 想定される 3 つのデプロイモード

| モード | 説明 | 利用シーン |
|-------|------|----------|
| **A. ローカル限定** | 自分の PC で `streamlit run` | DEC-005 通り、本人 + H-02(家族・近しい友人)が同席で利用 |
| **B. プライベートクラウド**(認証付き) | Cloudflare Tunnel / Tailscale / Streamlit Community Cloud(リンク非公開) | リモートで自分が使う、URL を友人 1〜2 名に共有 |
| **C. 完全公開** | Streamlit Cloud Public、URL を一般公開 | **DEC-016(2026-05-30)で解禁**。ポートフォリオ・転職活動・GREE 社内提示用途。商業展開はしない |

## 各モードの判断材料

### モード A: ローカル限定(推奨)

| 観点 | 評価 |
|------|------|
| DEC-005 整合性 | ✅ 完全に整合 |
| コスト | ✅ ゼロ |
| セキュリティ | ✅ 認証不要、攻撃面ゼロ |
| GitHub Actions 月次バッチ | ⚠️ DB ファイルを GitHub Actions Artifact として保存 → ローカルへダウンロードして使用、or ローカル PC で cron 実行 |
| データ更新の自動化 | ⚠️ ローカル cron / systemd timer / Windows Task Scheduler のセットアップが必要(STARTUP.md §6) |
| 共有 UX | ⚠️ 画面同席 / スクリーンショットのみ(F3 共有フロー) |

**結論**: 最も DEC-005 と整合する。GitHub Actions Artifact からの DB ダウンロード手順を整備すれば運用可能。

### モード B: プライベートクラウド(検討余地あり)

| 観点 | 評価 |
|------|------|
| DEC-005 整合性 | ⚠️ 「個人ツール」の範囲をどう解釈するかで分かれる |
| コスト(Streamlit Community Cloud) | ✅ 無料枠あり(public のみ)。private は Tier 上げ要 |
| コスト(Cloudflare Tunnel) | ✅ 無料(無料ドメイン名で OK) |
| コスト(Tailscale) | ✅ 個人ユース無料 |
| セキュリティ | ⚠️ 認証実装(or トンネル経由のアクセス制御)が必要。INV-AUTH 系の新規論点 |
| データ更新の自動化 | ✅ GitHub Actions cron がそのまま使える |
| 共有 UX | ✅ URL シェア可、自分のスマホからも見える |

**Streamlit Community Cloud 採用時の課題**:
- 無料枠は **public のみ** = 「個人ツール限定」(DEC-005)と矛盾
- `secrets.toml` で API キー管理は可能
- データ保存に永続ストレージなし(DB ファイルが揮発)→ GitHub Actions で生成して repo にコミットする必要があり、DB の機密性に注意

**Cloudflare Tunnel / Tailscale 採用時の課題**:
- ローカル PC を 24/7 起動する必要あり
- 自宅ネットワーク経由のため、外出先からの応答時間に影響

**結論**: モード A をベースに、必要に応じてトンネル経由で個別共有を検討。Streamlit Community Cloud は public 制約で DEC-005 不整合。

### モード C: 完全公開(DEC-016 で解禁, 2026-05-30)

| 観点 | 評価 |
|------|------|
| DEC-005 整合性 | ~~❌ 不整合~~ → **DEC-016 で上書き、整合** |
| DEC-016 整合性 | ✅ 整合(ポートフォリオ用途で許容) |
| 必要な追加対応 | 利用規約 / プライバシーポリシー / 免責表示強化(INV-BIZ-006/008)/ Cookie 同意(GA4 導入時 INV-BIZ-007)/ 不動産公正競争規約・金商法に対する明示注記 |
| 必要な技術対応 | `requirements.txt` / `runtime.txt` 整備、サンプル DB スナップショット同梱、`outputs/legal/` 整備 |

**結論**: **採用する**(DEC-016 で解禁、2026-05-30)。ポートフォリオ・転職活動・GREE 社内向け公開デモ URL を提供するため、Streamlit Community Cloud Public にデプロイ。商業展開は引き続き対象外、認証は不要(認証なし閲覧専用)。

---

## 推奨方針

### 短期(launch 直後): **モード A**

1. 自分のローカル PC で `streamlit run app/main.py` を起動して使用
2. 月次バッチは GitHub Actions cron で自動実行 → Artifact として DB ファイル取得
3. 必要に応じて GUI で家族・友人に同席閲覧

実装は完了済(本ドキュメント作成時点)。追加作業: ローカル cron / Task Scheduler の設定手順を STARTUP.md §6 に追記済。

### 中期(評判が良ければ): **モード B(Cloudflare Tunnel 経由)**

1. ローカル PC を 24/7 起動できる環境を準備
2. Cloudflare Tunnel で `https://movemap.example.com` 等のサブドメインを発行
3. Zero Trust ポリシーで GitHub OAuth でログイン認証を追加
4. URL を信頼できる友人に限定共有

実装に必要な追加: なし(Tunnel 設定のみ、コード変更不要)。

### 長期(ポートフォリオ公開): **モード C(DEC-016 で解禁)**

DEC-005 を DEC-016(2026-05-30)で上書き、mode C を併用形態として解禁。

1. **デプロイ先**: Streamlit Community Cloud Public
2. **目的**: ポートフォリオ・転職活動・GREE 社内提示用の公開デモ URL
3. **商業展開はしない**: 課金・広告・有料機能なし
4. **認証なし閲覧専用**: 個人情報を受け付けない単方向公開
5. **法務整備**: `outputs/legal/terms.md`(利用規約)+ `outputs/legal/privacy_policy.md`(プライバシーポリシー)を整備、UI フッターから導線
6. **免責強化**: 「投資助言ではない」「移住助言ではない」明示(INV-BIZ-006 候補)
7. **Cookie 同意**: GA4 導入時のみ有効化(INV-BIZ-007 条件付き候補)

**本格的な商用展開を将来検討する場合**: 別プロジェクトとして Phase 0 から再走を推奨(twin-build 設計書・コードは流用可)。

---

## デプロイ前チェックリスト(モード A 採用時)

- [ ] `uv sync --extra dev` 成功
- [ ] `python scripts/seed.py --with-synthetic-history` 成功
- [ ] `python scripts/fetch_geojson.py` 成功
- [ ] `pytest tests/ -v` → 117 passed
- [ ] `streamlit run app/main.py` → ブラウザで UI が表示される
- [ ] `.env` に `ESTAT_APP_ID` / `REINFOLIB_API_KEY` 設定(任意)
- [ ] GitHub Actions Secret に同上を設定(月次バッチ運用時)
- [ ] `scripts/run_batch.py` 試走 → BatchJob 状態が `success` or `partial`
- [ ] `scripts/snapshot.py` で 1 回 snapshot を取得 → 復元手順を確認

---

## デプロイモード変更時の手続き

- A → B: 認証実装 + Tunnel 設定。INV-AUTH 系の論点を新規不変条件として追加
- B → C: ~~DEC-005 を撤回し、新規 GATE で再決定~~ → **DEC-016(2026-05-30)で実施済**。`outputs/legal/` 整備 + INV-BIZ-006/007/008 候補の正典化を伴う

---

## 関連決定

- DEC-005: プロダクト公開形態 = 個人ツール限定 **(DEC-016 で上書き)**
- DEC-013: INV-DATA-007 履歴 append-only DB 層強制(セキュリティ前提)
- DEC-014: pip-audit CI(供給チェーン脆弱性監視)
- **DEC-016: プロダクト公開形態の見直し(mode C 解禁, 2026-05-30)** — [`decisions/DEC-016.md`](decisions/DEC-016.md)
- R-03(Phase 0 専門家レビュー): 法的リスク → **DEC-016 で再オープン**, 99_review.md §「Re-opened: R-03」参照
