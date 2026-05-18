# Baseline(業務不変条件 cross-phase 集約)

> **このドキュメントの位置づけ**:
> `04_system_requirements.md` の「業務不変条件」セクションと**同一内容**で同期させる正典。
> Phase 5/6 でも追記される。`/review-risk` 等で参照される。

最終同期: 2026-05-17(Phase 4 完了時点)

## INV-BIZ(業務ルール)

| ID | 種類 | 内容 | 検証方法 |
|----|------|------|--------|
| INV-BIZ-001 | state | Prefecture テーブルは 47 都道府県以外のレコードを持ってはならない | DB 制約 + 起動時シード検証 |
| INV-BIZ-002 | state | `is_predictable=true` の Indicator は主要4指標(物価/地価/賃料/出生数)のみ | DB 制約 + シード検証 |
| INV-BIZ-003 | transition | R²<0.6 のモデルから生成された PredictedValue は `quality_status='no_prediction'` でなければならない | SF-018 の単体テスト + バッチ後のアサート |
| INV-BIZ-004 | transition | 月次バッチ開始時に BatchJob レコードが C されなければならない | SF-010 の単体テスト |
| INV-BIZ-005 | state | MAP 表示時(SF-001/002/003/004)は常に免責バナーが表示されなければならない | E2E テスト + フロントエンドの常時マウントコンポーネント |

## INV-DATA(データ整合性)

| ID | 種類 | 内容 | 検証方法 |
|----|------|------|--------|
| INV-DATA-001 | structural | CurrentValue.prefecture_code は Prefecture.code に必ず存在 | DB FK 制約 |
| INV-DATA-002 | structural | CurrentValue (prefecture_code, indicator_id) は一意 | DB UNIQUE 制約(PK) |
| INV-DATA-003 | structural | PredictedValue (prefecture_code, indicator_id, horizon_years) は一意 | DB UNIQUE 制約(PK) |
| INV-DATA-004 | structural | `is_predictable=false` の Indicator は PredictedValue を持ってはならない | アプリ層バリデーション + バッチ事後検証 |
| INV-DATA-005 | structural | PredictedValue は必ず `is_predictable=true` の Indicator を参照 | INV-DATA-004 の対偶として同じテスト |
| INV-DATA-006 | state | PredictedValue.horizon_years は {3, 5, 10} のいずれか | DB CHECK 制約 |
| INV-DATA-007 | structural | HistoricalValue は append-only(UPDATE/DELETE 禁止) | アプリ層強制 + DB トリガー(オプション) |
| INV-DATA-008 | state | DataSource.update_frequency は {monthly, quarterly, yearly, irregular} のいずれか | DB CHECK 制約 |

## INV-AUTH(認可・認証)

**該当なし** — 個人ツール限定(DEC-005)、単一ユーザー、認証なし

## INV-EXT(外部連携)

| ID | 種類 | 内容 | 検証方法 |
|----|------|------|--------|
| INV-EXT-001 | side_effect | 外部 API(API-EXT-01〜06)失敗時は前回値を保持し UI に「未更新」を表示しなければならない(C-01, R1.3) | TC-DP-05 単体テスト |
| INV-EXT-002 | side_effect | 外部 API の 3 回連続失敗時は UI 警告を出さなければならない(C-02, R2.2) | TC-DP-05 + smoke |
| INV-EXT-003 | structural | e-Stat AppID は Secret 経由(GitHub Actions Secret / `.env`)で渡し、コードにハードコードしてはならない | コードレビュー + ruff/bandit 規則 |

## INV-IDEM(冪等性)

| ID | 種類 | 内容 | 検証方法 |
|----|------|------|--------|
| INV-IDEM-001 | transition | 月次バッチ(RunBatch)は同月内に複数回実行されても結果が同等でなければならない(upsert + append_only_history 設計) | TC-DP-01 を二度実行で検証 |
| INV-IDEM-002 | transition | `scripts/seed.py` は再実行でも seed データが重複生成されてはならない | smoke テスト |

## ソース

- 抽出元: `MoveMap/outputs/04_system_requirements.md`(INV-BIZ-001〜005, INV-DATA-001〜008)
- Phase 6 で追加: INV-EXT-001〜003, INV-IDEM-001〜002
- Phase 4 確定: 2026-05-17
- Phase 6 最終化: 2026-05-17
