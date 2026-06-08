# GA4(Google Analytics 4)セットアップ記録

最終更新: 2026-06-03
DEC-016(mode C 公開)に伴う計測ツール導入記録.

---

## 取得済の構成

| 項目 | 値 |
|---|---|
| **Google Analytics アカウント** | MoveMap 開発者(個人) |
| **プロパティ名** | MoveMap |
| **タイムゾーン** | 日本 |
| **通貨** | 日本円(JPY) |
| **業種** | テクノロジー |
| **ビジネスサイズ** | 小規模 |
| **データストリーム名** | MoveMap Production |
| **データストリーム URL** | `https://movemap.streamlit.app` |
| **ストリーム ID** | `14987802711` |
| **測定 ID(Measurement ID)** | **`G-XBN239TY94`** |
| **取得日** | 2026-06-03 |

> **注**: Measurement ID は秘密情報ではない(各訪問者のブラウザで gtag.js が動作する際に HTML 上で公開される値)。
> ただし**運用設定(プロパティ・データストリーム・ダッシュボード)へのアクセス**は Google アカウントログインで保護される。

---

## 実装状況(コード)

| ファイル | 役割 | 状態 |
|---|---|---|
| `app/shared/config.py` | `Config.ga4_measurement_id` フィールド | ✅ |
| `app/shared/ui_theme.py` | `inject_ga4(measurement_id)` 関数 | ✅ |
| `app/features/compliance/cookie_consent.py` | INV-BIZ-007 同意バナー | ✅ |
| `app/main.py` | 同意済みの場合のみ GA4 注入 | ✅ |
| `.env.example` | `GA4_MEASUREMENT_ID=` placeholder | ✅ |
| `tests/unit/test_cookie_consent.py` | 5 件パス | ✅ |
| `tests/unit/test_invariants_static.py` | INV-BIZ-007 静的検証 1 件パス | ✅ |

---

## 動作仕様(INV-BIZ-007 準拠)

```
[ユーザー初訪問]
  ↓
[Cookie 同意バナー表示]
  ├─ 同意する → session_state["movemap_ga_consent"] = True
  │              → gtag.js 注入 → GA4 計測開始
  └─ 拒否する → session_state["movemap_ga_consent"] = False
                → GA4 注入なし → 計測されない
```

- 同意状態は **session_state**(ブラウザセッション単位)で保持
- 1 セッション内では一度判断するとバナー再表示されない
- ハードリロード後はバナー再表示(localStorage 永続化は将来課題)
- `anonymize_ip: true` で IP アドレス匿名化済
- 詳細: `outputs/legal/privacy_policy.md` §5.3

---

## 環境別の Measurement ID 設定方法

### ローカル開発

`.env` ファイル(`.gitignore` 済)に以下を記載:

```
GA4_MEASUREMENT_ID=G-XBN239TY94
```

### Streamlit Cloud(本番)

1. https://share.streamlit.io/ にログイン
2. アプリ `movemap` を選択
3. **「⋮」 → 「Settings」 → 「Secrets」** タブを開く
4. 以下を追記:

```toml
GA4_MEASUREMENT_ID = "G-XBN239TY94"
UNSPLASH_ACCESS_KEY = "NLrVT_88rsgC2INTDzU1GKk0qRuT2yvEBTZze0RODwU"
```

5. 「Save」 → アプリが自動再起動 → GA4 計測有効化

---

## 動作確認手順(本番デプロイ後)

1. https://movemap.streamlit.app/ にアクセス
2. **Cookie 同意バナー**が表示されることを確認
3. 「同意する」をクリック
4. **GA4 リアルタイムレポート** を別タブで開く
   - https://analytics.google.com/ → MoveMap プロパティ
   - 左メニュー「レポート」→「リアルタイム」
5. 5〜30 秒以内に**「過去 30 分間のユーザー数 = 1」**が表示されれば成功

---

## トラブルシューティング

| 症状 | 原因と対処 |
|---|---|
| Cookie バナーが出ない | `GA4_MEASUREMENT_ID` が空 → Secrets / .env 確認 |
| 同意してもリアルタイムに乗らない | gtag.js 注入失敗 → ブラウザ Console で `dataLayer` を確認 |
| データ収集が有効になっていません警告 | 計測初回は最大 48 時間反映タイムラグ |
| ad blocker で計測されない | ユーザー側の問題、対処不要(プライバシー尊重) |

---

## 関連ドキュメント

- [DEC-016 起票文書](decisions/DEC-016.md)
- [利用規約](legal/terms.md)
- [プライバシーポリシー §5.3](legal/privacy_policy.md)
- [INV-BIZ-007(baseline.md)](baseline.md)

---

## 次のステップ

- [ ] Streamlit Cloud Secrets に `GA4_MEASUREMENT_ID` を追加(ユーザー作業)
- [ ] 本番デプロイ後、リアルタイムレポートで動作確認(ユーザー作業)
- [ ] (任意・後日)GTM(Google Tag Manager)導入でタグ管理を柔軟化
- [ ] (任意・後日)カスタムイベント(タブ切替、診断完了等)の追加
- [ ] (任意・後日)localStorage ベースの永続的 Cookie 同意(現状は session 単位)
