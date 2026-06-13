# MoveMap SEO アクション一覧(計測駆動の出発点)

| メタ | 値 |
|---|---|
| **作成日** | 2026-06-13 |
| **対象** | https://movemap.streamlit.app/ |
| **目的** | ユーザー認知の獲得(ポートフォリオ用途) |
| **計測前提** | GA4 `G-XBN239TY94`(Cookie 同意済セッションのみ) |
| **次の成果物** | `02_hypotheses.md` で仮説 5 件 → 厳選 1-2 件 |

---

## 評価軸:ICE スコア

各施策に **Impact × Confidence × Ease**(各 1〜5)を付与し、積で優先順位を決める。

| 軸 | 1 | 3 | 5 |
|---|---|---|---|
| **Impact**(効果の大きさ) | 微差 | そこそこ | 桁が変わる |
| **Confidence**(成功確度) | 賭け | 五分五分 | ほぼ確実 |
| **Ease**(実行容易性) | 大工事 | 半日 | 30 分以内 |

**最大 125 点**(5×5×5)。ICE ≥ 75 が「Quick Win」帯。

## ステータス凡例

| 記号 | 意味 |
|---|---|
| ✅ | 完了 |
| 🟡 | 部分完了(改善余地あり) |
| ❌ | 未着手 |
| ➖ | 対象外(今は不要) |

---

## 🚀 Quick Wins(ICE ≥ 75)— まず打つ 8 手

| 順 | ID | 施策 | I | C | E | ICE | 状態 | 工数 |
|---|---|---|---|---|---|---|---|---|
| 1 | T5-01 | **Google Search Console 登録 + 所有権検証** | 5 | 5 | 4 | **100** | ❌ | 20 分 |
| 2 | T3-01 | **GitHub README 強化(公開 URL + スクショ + 構成図)** | 4 | 5 | 5 | **100** | 🟡 | 30 分 |
| 3 | T1-06 | **robots.txt 設置(Streamlit Cloud 対応)** | 4 | 5 | 5 | **100** | ❌ | 15 分 |
| 4 | T1-08 | **動的 page title(view ごと)** | 5 | 5 | 4 | **100** | 🟡 | 30 分 |
| 5 | T5-04 | **GA4 ↔ Search Console 連携** | 4 | 5 | 4 | **80** | ❌ | 10 分 |
| 6 | T1-01 | **meta description(view ごとに最適化)** | 3 | 5 | 5 | **75** | 🟡 | 30 分 |
| 7 | T1-03 | **Twitter Card / OGP メタタグ** | 3 | 5 | 5 | **75** | 🟡 | 20 分 |
| 8 | T4-02 | **Core Web Vitals 計測(PageSpeed Insights)** | 3 | 5 | 5 | **75** | ❌ | 15 分 |

→ **Quick Win 合計工数 = 約 3 時間**

---

## 📋 全 36 施策(ICE 降順)

### Tier 1: On-site SEO(10 件)

| ID | 施策 | I | C | E | ICE | 状態 | メモ |
|---|---|---|---|---|---|---|---|
| T1-06 | robots.txt 設置 | 4 | 5 | 5 | 100 | ❌ | Streamlit は静的 robots.txt 配信不可 → GitHub Pages or `/_robots.txt` カスタム handler |
| T1-08 | 動的 page title(view ごと) | 5 | 5 | 4 | 100 | 🟡 | `app/main.py` で view 切替時に `st.set_page_config(page_title=...)` |
| T1-01 | meta description(view ごと) | 3 | 5 | 5 | 75 | 🟡 | `st.markdown` で `<meta>` 注入 |
| T1-03 | Twitter Card / OGP メタタグ | 3 | 5 | 5 | 75 | 🟡 | 共有時のサムネイル表示で CTR ↑ |
| T1-04 | JSON-LD: SoftwareApplication / Article | 4 | 4 | 4 | 64 | 🟡 | 既存の WebApplication を SoftwareApplication に格上げ、記事は別途 |
| T1-07 | sitemap.xml(動的生成) | 4 | 5 | 3 | 60 | ❌ | 47 県 LP 公開時に必須 |
| T1-05 | BreadcrumbList JSON-LD | 3 | 4 | 4 | 48 | ❌ | パンくず構造ができてから |
| T1-09 | 画像 alt + image sitemap | 3 | 4 | 3 | 36 | ❌ | ヒーロー / 県写真 |
| T1-02 | OGP 画像(1200×630)作成 | 4 | 4 | 3 | 48 | ❌ | 共有用 KV、後述 T1-03 と一体化 |
| T1-10 | hreflang(将来英語版) | 1 | 2 | 4 | 8 | ➖ | 英語版予定なし |

### Tier 2: Content SEO(8 件)

| ID | 施策 | I | C | E | ICE | 状態 | メモ |
|---|---|---|---|---|---|---|---|
| T2-06 | About / メソッドページ(指標 9 種・モデル説明) | 3 | 4 | 4 | 48 | ❌ | E-E-A-T シグナル |
| T2-07 | FAQ ページ | 3 | 4 | 4 | 48 | ❌ | FAQ schema で SERP rich result |
| T2-02 | 指標別ランキング LP("地価 47都道府県" 等) | 4 | 4 | 3 | 48 | ❌ | キーワード狙い撃ち、SSG 必須 |
| T2-01 | 47 都道府県 LP(long-tail) | 5 | 4 | 2 | 40 | 🟡 | 北海道プロト記事あり、自動生成パイプ作成中 |
| T2-08 | 47 県 LP の AI 半自動生成パイプ | 4 | 3 | 3 | 36 | 🟡 | GitHub Models 統合済 |
| T2-05 | 全国マップガイド(固定 LP) | 3 | 3 | 4 | 36 | ❌ | "47都道府県 比較" ワード狙い |
| T2-04 | 用途別記事("子育てしやすい県" 等) | 4 | 3 | 2 | 24 | ❌ | 診断結果ベースの SEO 記事 |
| T2-03 | 比較ページ("東京 vs 大阪 移住" 等) | 3 | 3 | 2 | 18 | ❌ | 動的生成、47×46 = 2,162 ページ |

### Tier 3: Off-site SEO(8 件)

| ID | 施策 | I | C | E | ICE | 状態 | メモ |
|---|---|---|---|---|---|---|---|
| T3-01 | GitHub README 強化(公開 URL + スクショ + 構成図) | 4 | 5 | 5 | **100** | 🟡 | repo star → 開発者層流入 |
| T3-05 | LinkedIn 投稿(GREE 社内 + 転職市場向け) | 3 | 4 | 5 | 60 | ❌ | エンジニアコミュニティ |
| T3-02 | note 記事公開(被リンク) | 4 | 4 | 3 | 48 | ❌ | 「twin-build で個人ツール作った話」など |
| T3-06 | 個人ポートフォリオサイト / SNS プロフィールからリンク | 3 | 4 | 4 | 48 | ❌ | プロフィール一括更新 |
| T3-04 | X(Twitter)共有テンプレ + 投稿 | 3 | 3 | 5 | 45 | ❌ | OGP 画像と連動 |
| T3-07 | Zenn / Qiita 技術記事 | 4 | 3 | 3 | 36 | ❌ | DevTo もアリ。「Streamlit Cloud 公開 + GA4 計測」など |
| T3-03 | HN / Reddit / Product Hunt 投稿 | 5 | 2 | 3 | 30 | ❌ | バーストの可能性。当たれば桁違い |
| T3-08 | 移住系コミュニティ紹介 | 3 | 2 | 3 | 18 | ❌ | r/japan, 移住系 Slack 等 |

### Tier 4: Technical SEO(6 件)

| ID | 施策 | I | C | E | ICE | 状態 | メモ |
|---|---|---|---|---|---|---|---|
| T4-02 | Core Web Vitals 計測(PageSpeed Insights) | 3 | 5 | 5 | 75 | ❌ | 改善前のベースライン取得 |
| T4-05 | canonical URL タグ | 3 | 4 | 5 | 60 | ❌ | view パラメータ違いの重複回避 |
| T4-06 | HTTPS / セキュリティヘッダー(HSTS, CSP) | 2 | 5 | 5 | 50 | ✅ | Streamlit Cloud がデフォルト提供 |
| T4-03 | モバイル UX 改善(タップ領域・スクロール) | 4 | 4 | 3 | 48 | 🟡 | 既に大きめだが要再確認 |
| T4-01 | GitHub Pages LP で SSR 化(JS レンダリング問題回避) | 5 | 4 | 2 | 40 | ❌ | Streamlit は indexer に弱い、LP だけ SSG で補完 |
| T4-04 | Page Speed 改善(画像 lazy load 等) | 3 | 3 | 2 | 18 | ❌ | T4-02 後に着手 |

### Tier 5: Visibility ツール登録(4 件)

| ID | 施策 | I | C | E | ICE | 状態 | メモ |
|---|---|---|---|---|---|---|---|
| T5-01 | Google Search Console 登録 + 所有権検証 | 5 | 5 | 4 | **100** | ❌ | **絶対先**(計測の前提) |
| T5-04 | GA4 ↔ Search Console 連携 | 4 | 5 | 4 | 80 | ❌ | T5-01 直後 |
| T5-03 | Ahrefs Webmaster Tools(無料) | 3 | 4 | 4 | 48 | ❌ | 被リンク監視 |
| T5-02 | Bing Webmaster Tools 登録 | 2 | 5 | 4 | 40 | ❌ | 国内シェア小だが工数低い |

---

## 推奨実行順序

### Phase 1:計測の前提整備(1 時間)
1. **T5-01** Google Search Console 登録 ← まず
2. **T5-04** GA4 ↔ Search Console 連携
3. **T4-02** Core Web Vitals ベースライン取得

### Phase 2:Quick Wins 一気打ち(2 時間)
4. **T1-06** robots.txt
5. **T1-08** 動的 page title
6. **T1-01** meta description
7. **T1-03** Twitter Card / OGP
8. **T3-01** GitHub README 強化

### Phase 3:GA4 カスタムイベント実装(Step 3 で詳細)
9. horizon 切替 / 指標切替 / 県選択 / CTA クリック / 滞在時間
10. 仮説検証に必要な最小セット

### Phase 4:中期施策(T+14 以降)
- T2-* コンテンツ SEO
- T3-* 拡散施策
- T4-01 GitHub Pages SSR LP

---

## 仮説の起点となる観察ポイント(Step 2 への引き継ぎ)

この一覧から、**仮説 5 件**(Step 2)を立てる際の素材になる視点:

1. **どの view が一番見られるか?**(マップ vs ランキング vs 詳細 vs 診断)
2. **horizon 切替(現在 / 3年後 / 5年後 / 10年後)は実際に使われるか?**
3. **指標 9 種のうちどれが人気か?**(物価・地価・治安・転入超過 等)
4. **診断 → 詳細 への遷移率は?**(回遊している?単発で離脱?)
5. **どこから来た流入が最も滞在時間が長いか?**(Direct vs Search vs Social)

これらの観察に対し、上司のアドバイス通り「数値で予測」した仮説を **`02_hypotheses.md`** に書き起こします。

---

## このドキュメントの位置づけ

```
01_action_list.md   ← 今ここ (網羅 + 優先順)
        ↓
02_hypotheses.md   ← Step 2:仮説 5 件 + 厳選 1-2 件
        ↓
03_ga4_events.md   ← Step 3:GA4 カスタムイベント仕様 + 実装
        ↓
04_review_plan.md  ← Step 4:T+14(2026-06-27)レビュー手順
        ↓
[2026-06-27] 結果記録 → 当たり外れ → 次の打ち手
```
