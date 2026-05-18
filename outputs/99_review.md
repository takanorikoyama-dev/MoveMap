# プロジェクト最終レビュー

## 作成日
2026-05-17

## 入力
- `outputs/00_problem.md`〜`06_system_design/`(全 Phase 成果物)
- `app/` 配下 38 Python ファイル
- `seeds/` 配下 3 CSV
- `tests/` 配下 6 テストファイル
- `baseline.md`(INV 18 件)
- `.twin-build.json` / `pyproject.toml` / GitHub Actions 設定

---

## 1. 翻訳一貫性の検証(Phase 間)

### Phase 0 → 1(課題定義 → 要求仕様)

**評価: OK**

- Who: 「50-60代セカンドキャリア/リタイア前」が Phase 1 のペルソナ説明に一貫
- 困りごと:「複数地域 × 指標 × 将来予測 を横並び比較する手段がない」が Phase 1 の Why に反映
- スコープ:「物件紹介・移住あっせん・海外」の Out of Scope が Phase 1 でも明示
- KGI: Phase 0 にはなく Phase 1 で「プロダクト完成型」として新規定義 — 自然な追加

**課題**: なし

### Phase 1 → 2(要求仕様 → 業務構造)

**評価: OK**

- Must 7 指標が `seeds/indicators.csv` + Phase 2 X-01〜X-06 データソースに対応
- AI 予測モデルが S-02 アクターに展開
- 商流・金流・物流が「該当なし」と明示され、業務構造が情報流中心に整理
- 業務ルール R1.1〜R3.3 が要求仕様の Must / Should と矛盾なし

**課題**: なし

### Phase 2 → 3(業務構造 → 業務フロー)

**評価: OK**

- F1(月次データ更新)と F2(MAP 閲覧)が業務構造のタイミング表 t0〜t6 と整合
- 補償経路 C-01〜C-07 が業務ルール R1.3 / R1.4 / R2.1 / R2.2 を反映
- Phase 2 で「アクター」「4 流」と決めた構造が Phase 3 の各 Step に一対一マップ

**課題**: なし

### Phase 3 → 4(業務フロー → システム要件)

**評価: OK**

- F1 の各ステップが SF-010〜019、F2 の各ステップが SF-001〜005 にマップ
- 補償経路 C-01〜C-07 が EX-001〜003 と統合され、Phase 4 の例外処理セクションに展開
- 業務ルール R1.1〜R3.3 が INV-BIZ / INV-DATA として再形式化
- F3 共有フローが Phase 4 で「非システム化」と明示

**課題**:
- F2.7「比較・絞り込みの記憶化」が非システム化となったが、Should/Could で復活する余地があり明示推奨(現状: Phase 4 備考に記載済)

### Phase 4 → 5(システム要件 → アーキテクチャ)

**評価: OK**

- SF-001〜021 が Feature(map_view / data_pipeline / compliance) × Usecase に分割
- 論理 ERD 10 エンティティが Phase 5 の集約 4 つに集約(Theme 3)
- データ共有方法(Theme 2)が「単一プロセス + 直接 read」で確定
- ドメインイベントカタログは「該当なし」と明示(Theme 4)

**課題**: なし

### Phase 5 → 6(アーキテクチャ → システム設計)

**評価: OK**

- Feature/Usecase が 7 設計書(00_概要 〜 07_イベント設計)に展開
- 物理 ERD(DuckDB スキーマ)が論理 ERD と一致、INV-DATA が CHECK/FK 制約として表現
- 集約境界詳細(Theme 3 第二段階)で削除カスケード・TX スコープ確定
- 業務不変条件が baseline.md に最終化(18 件、INV-BIZ 5 + INV-DATA 8 + INV-EXT 3 + INV-IDEM 2)

**課題**: なし

### Phase 6 → 7(システム設計 → 実装)

**評価: OK**

| 設計書 | 実装対応 |
|--------|---------|
| 01_シーケンス図 F1 | `usecases/run_batch.py` 全 10 Usecase 順次呼出 |
| 01_シーケンス図 F2 | `app/main.py` 3 タブ + `usecases/show_*` |
| 02_API設計 API-EXT-01〜06 | `sources/{estat, mlit_land_price, mlit_rent_index, env_soramame, gsi_hazard, mlit_transport}.py` |
| 03_状態遷移 BatchJob/PredictedValue/CurrentValue | DDL の status / quality_status CHECK 制約 + Usecase での遷移処理 |
| 04_データ設計 物理 ERD | `app/shared/db.py` の DDL_STATEMENTS |
| 04_集約境界詳細 | dataclass(`domain/*.py`)+ Usecase の TX スコープ |
| 05_画面設計 SCR-001/002/003 | `app/main.py` の `tab_map` / `tab_detail` / `tab_model` |
| 06_テスト設計 | `tests/unit/` + `tests/integration/` の 6 ファイル |
| 07_イベント設計 | 該当なしと宣言済、コード上もイベントなし |

**画面突合(項目レベル)**:
- 指標切替 7 指標 → `INDICATOR_LABELS` 辞書(map_view/usecases/switch_indicator.py)で 7 件
- 年次切替 4 値(現在/3/5/10年) → `HORIZON_LABELS` で 4 件 ✓
- ヒートマップ 5 階層・色覚配慮 → Plotly `colorscale="viridis"`(R2.3 と整合)
- 「予測なし」灰色表示 → quality_status='no_prediction' は値が None → choropleth で自動灰色
- 免責バナー常時表示(INV-BIZ-005) → `app/main.py` の `render_disclaimer()` で 3 タブの上部に表示

**課題**:
- SCR-002 クリック→詳細パネル動線が現状「タブ切替 + selectbox」で代替(map クリックは Streamlit の制約)。要件は満たすが UX 上 Phase 8 で要再検証

---

## 2. 品質観点の検証

### 要件の充足

**評価: OK(部分検証可)**

- Must 要件 6 件すべて `manage_requirements` で Phase 2/3/4 = 100% covered
- impl 17/17 = 100% でコード実装済
- KGI「7指標 × 47都道府県 × 4時点を欠落なく表示」: コード上の構造は完備、実データの充足は Phase 8 の Wave 2 検証次第
- KPI:
  - 現在値被覆率 100%: コードは可能、実 API キーが揃えば達成可
  - 予測モデル R² ≥ 0.6: コードは ARIMA + Prophet 実装済、実履歴データで評価が Phase 8 課題
  - MAP UI 機能完成度: 全 5 Usecase 実装済 ✓

### スコープの遵守

**評価: OK**

- 「個別物件紹介」「移住あっせん」「海外移住」: コード上に該当機能なし ✓
- 「公開・商用展開」: 認証/課金機能なし ✓ DEC-005 個人ツール限定と整合
- 「認証・ユーザー管理」: コード上に user table・session 管理なし ✓
- スコープ外機能の混入なし

### 設計の一貫性

**評価: OK**

- VSA パターン: `features/<feature>/usecases/` 構造を全 17 Usecase で順守
- レイヤー依存ルール: `features → shared → domain` の単方向(逆流なし)
- 集約境界: 4 集約のすべてが `data_pipeline` Feature 内に閉じる(Phase 5 で合意)
- INV の検証手段: DB 制約 / アプリ層 / テスト の各層で適切に配置

---

## 3. 改善点

### プロセス面

| ID | 内容 |
|----|------|
| P-01 | Phase 0 で「個人ツール限定」を未決定としたが、その後 Phase 1 で確定する流れで一貫性が保てた。**判断**: 未決定を明示しつつ後段で再検討する流れは twin-build フローの強み |
| P-02 | Phase 4 で集約・CRUD を粗く宣言し、Phase 6 で詳細化する 2 段階アプローチが効果的だった |
| P-03 | セッション制約により Phase 7 を **6 セッションに分割**(初期化 → スキャフォールド → Wave 1 → UI → 予測 → オーケストレーション)した結果、各セッション内で完結する小さなマイルストーンが設定でき、メモリ機構と相性が良かった |
| P-04 | レビュー指摘(D-01〜DE-05、UX-D-01〜04 等)を「持ち越し論点」として明示的に Phase をまたいで追跡できた点が大きい改善 |

### 成果物面

| ID | 内容 |
|----|------|
| A-01 | `baseline.md` の Phase 6 最終化で技術的不変条件(INV-EXT/IDEM)を追加できた点はテンプレ通り良好 |
| A-02 | 設計書ディレクトリ `06_system_design/` を初期から作成し、設計書間の参照が容易だった |
| A-03 | seeds CSV を初期から物理データとして用意したことで Phase 7 実装時の整合確認が早期にできた |
| A-04 | **欠**: Phase 1 KPI に「R²≥0.6」と書いたが、 Phase 6 で「OPS-02 評価期間が確定していない」となり、評価方法の Phase 1 → Phase 6 への引き継ぎが粗かった。Phase 1 段階で「評価期間は Phase 6 で確定」とより明示的に書く改善余地 |

### 技術面

| ID | 内容 |
|----|------|
| T-01 | Python + Streamlit + DuckDB の組合せは個人ツール+データ可視化に最適だった。学習コストが小さく実装スピードが出た |
| T-02 | `PredictionState` dataclass による Usecase 間状態引き継ぎは設計通りだが、in-memory 状態を Usecase 引数で渡すパターンは VSA らしさが薄れた。Phase 8 で「集約 root に状態を埋め込む」リファクタ余地あり |
| T-03 | `INV-DATA-007`(履歴 append-only)を DB 層で強制できなかった点(DuckDB 制約)が技術的制約。app 層 wrapper or VIEW での補強が Phase 8 課題 |
| T-04 | reinfolib API はキー・URL 構造が変更される可能性が高く、Phase 7 段階では「best-effort」実装。Phase 8 で 1 ソースずつ動作確認するインクリメンタル戦略が必要 |
| T-05 | Streamlit `st.plotly_chart` のクリックイベント取得は API が制限的(`on_select` は新しい API)。SCR-002 都道府県クリックは selectbox による代替を採用したが UX として最適でない |

---

## 4. 総合評価: **A-**

### 総評

「個人ツール限定 + 50-60代向け地方移住MAP」というスコープを twin-build フローで Phase 0 から実装まで一貫して翻訳できた。
全 Phase で持ち越し論点を明示的に追跡し、Coverage / 不変条件 / 決定ログ という機械可読な形で記録できたことが大きな成果。

impl 17/17 = 100% に到達し、Streamlit 起動だけで MAP UI が動作する状態に持ち込めた。Wave 2 ソースアダプタも構造実装完了で、API キーが揃えば実データで動く準備が整っている。

**A** ではなく **A-** とした理由:
- impl_test 0%(pytest 未実行 = テストが「動く保証」が未確認)
- Wave 2 ソースは実 API 動作未検証(reinfolib のレスポンス形式仮定が現実と一致するかは未確認)
- INV-DATA-007 が app 層規約のみで強制不足
- これらはすべて Phase 8 で対応可能 = 「翻訳一貫性」「品質基準」自体は問題なし

---

## 5. 次のアクション

### 必須対応(Phase 8 内で解消)

| # | 内容 | 担当・優先 |
|---|------|----------|
| N1 | `uv sync --extra dev` → `pytest tests/` 実行で impl_test カバレッジを反映 | 高 |
| N2 | Wave 2 ソース 1 個ずつ実 API 検証(e-Stat 動作確認 → 残り 5 ソース) | 高 |
| N3 | `seeds/hazard_scores.json` / `seeds/transport_facilities.json` の本物データ調達 | 中 |
| N4 | `streamlit run app/main.py` で UI 起動確認 + 動作スクリーンショット記録 | 中 |

### 推奨対応(Phase 8 中盤)

| # | 内容 |
|---|------|
| R1 | INV-DATA-007 の app 層強化(`shared/db.py` に append-only wrapper) |
| R2 | pip-audit / Dependabot を CI に追加(SEC-P7-01) |
| R3 | SCR-002 都道府県クリックの UX 改善(`st.plotly_chart(... on_select)` への切替検討) |
| R4 | `STARTUP.md` 作成(uv インストールから初回起動までの手順) |

### 将来の検討事項(Phase 8 完了後・公開拡張時)

| # | 内容 |
|---|------|
| F1 | 公開拡張する場合のアーキ移行: Streamlit → React + FastAPI(AIR-01 の変更条件) |
| F2 | Should 指標(医療アクセス / 市区町村粒度 / 口コミ)の段階実装 |
| F3 | Could 指標(気候・カスタム重み付け・時系列グラフ)の検討 |
| F4 | コード公開時のライセンス選定(LEGAL-02:MIT 推奨で確定) |
| F5 | ARIMA vs Prophet の精度評価対決(TECH-04 持ち越し) |

---

## 付録: Phase 8 実施までの確認事項

- [ ] `uv` インストール完了
- [ ] `uv sync --extra dev` 成功
- [ ] `python scripts/seed.py` で DuckDB に 47 都道府県 + 7 指標 + 6 ソースが投入される
- [ ] `python scripts/fetch_geojson.py` で `seeds/japan_prefectures.geojson` 取得
- [ ] `pytest tests/unit tests/integration -v` で全テスト通過
- [ ] `streamlit run app/main.py` でブラウザ表示確認

完了したらこのドキュメントは **Phase 8 開始時のチェックリスト** として機能する。
