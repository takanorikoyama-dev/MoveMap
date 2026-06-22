# Streamlit Cloud の SEO 制約と回避策

| メタ | 値 |
|---|---|
| **作成日** | 2026-06-22 |
| **対象** | https://movemap.streamlit.app/ |
| **要約** | Streamlit Community Cloud は SPA 構成のため、伝統的な SEO 手法の一部が機能しない。対処法を体系化する。 |

---

## 🚨 Streamlit Cloud の SPA 制約(発見されたもの)

### 制約 1:**`/robots.txt` 配信不可**

| | |
|---|---|
| **症状** | https://movemap.streamlit.app/robots.txt は React shell HTML を返す(plain text の robots ディレクティブではない) |
| **理由** | Streamlit Cloud のフロントエンドは SPA で、すべての URL に同一の `index.html` shell を返す |
| **影響** | 検索エンジンが robots を読めず、クロール制御不能 |

### 制約 2:**`/sitemap.xml` 配信不可**

| | |
|---|---|
| **症状** | 動的に sitemap を生成しても配信できない(同上の SPA 問題) |
| **影響** | Search Console に sitemap を登録できない、indexing 効率が下がる |

### 制約 3:**meta タグが `<head>` ではなく `<body>` に置かれる**

| | |
|---|---|
| **症状** | `st.markdown('<meta ...>', unsafe_allow_html=True)` は body 内に注入される |
| **理由** | Streamlit は標準的な `<head>` 操作 API を持たない |
| **影響** | Google は body 内の meta も一定程度認識するが、`<head>` 配置より弱い扱い |

### 制約 4:**JS レンダリングによる indexing 遅延**

| | |
|---|---|
| **症状** | UI コンテンツは React + WebSocket で動的描画される |
| **影響** | Googlebot は JS をレンダリングできるが、indexing キューが二段階になり優先度が下がる |
| **証拠** | Streamlit Cloud のスリープ画面さえ JS 実行後にしか分からない(keep-alive 検証で判明) |

### 制約 5:**異なる URL でも HTML が同一**

| | |
|---|---|
| **症状** | `/`, `/?view=ranking`, `/_stcore/health` がすべて同じ shell HTML を返す(差は JS で出る) |
| **影響** | canonical URL が body の meta タグ経由で間接的に伝わる → 弱い |

---

## 🛠 適用済の回避策(現状)

| 制約 | 回避策 | 実装場所 |
|---|---|---|
| 1. robots.txt 不可 | `<meta name="robots" content="index, follow">` を body に注入 | [app/main.py](../../app/main.py) |
| 2. sitemap 不可 | (現状なし。T1-07 で別ホスト経由を検討) | — |
| 3. meta が body | body 内でも Google は読むため body 注入で凌ぐ | [app/features/compliance/seo_meta.py](../../app/features/compliance/seo_meta.py) |
| 4. JS レンダリング | (現状なし。T4-01 GitHub Pages SSR LP が中期の本命) | — |
| 5. URL 区別困難 | `<link rel="canonical" href="...?view=KEY">` を body 注入 | [app/features/compliance/seo_meta.py](../../app/features/compliance/seo_meta.py) |

---

## 🚀 中期の本命:**T4-01 GitHub Pages SSR LP の併設**

Streamlit Cloud の SEO 制約を根本解決する方法は、**SEO 用 LP を別途静的サイト(GitHub Pages)に置く** こと:

```
[エンドユーザー / 検索エンジン]
        ↓
[GitHub Pages: https://takanorikoyama-dev.github.io/movemap/]
   - 静的 LP (HTML/CSS のみ、JS なし)
   - /robots.txt ✅
   - /sitemap.xml ✅
   - 完全な <head> 管理 ✅
   - meta タグ正規配置 ✅
   - 47 県の LP (long-tail SEO) ✅
   - 「触る」CTA → ↓
        ↓
[Streamlit Cloud: https://movemap.streamlit.app/]
   - 実際のインタラクティブツール (現状)
```

→ 検索流入は GitHub Pages 経由、操作は Streamlit Cloud、という二段構成。
→ ICE スコア 40(impact 5 × confidence 4 × ease 2)で工数大だが、SEO 上限突破には不可欠。

---

## 📝 リポジトリ準備済の資産

将来の T4-01 / セルフホスト移行に備えて以下を準備:

| ファイル | 用途 | 使えるようになるタイミング |
|---|---|---|
| [`robots.txt`](../../robots.txt) | クロール制御 | GitHub Pages / セルフホスト移行時 |
| (今後) `sitemap.xml` 自動生成スクリプト | indexing 補助 | 同上 |
| (今後) `docs/_includes/seo-head.html` | static `<head>` テンプレ | GitHub Pages 構築時 |

---

## 関連参照

- [outputs/seo/01_action_list.md](01_action_list.md) — T1-06 / T1-07 / T4-01 の元施策
- [outputs/decisions/DEC-016.md](../decisions/DEC-016.md) — mode C 公開の前提
- メモリ:`streamlit_cloud_keepalive_pattern.md` — 同 SPA 問題の別側面(keep-alive)
