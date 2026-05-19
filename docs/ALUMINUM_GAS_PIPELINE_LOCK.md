# アルミ・Mysteel GAS パイプライン固ロック（正規定義）

最終更新: 2026-04-27

毎日同じ処理（`executeAllProcesses`）でも **「急に挙動が変わる」**ことがあり得ます。原因は「スクリプトのロジックが変わった」以外に、**外部要因**と **ブック上の手作業**があります。本書は **今の作業基準（正解）** を1か所に固定し、**意図しないドリフト**を防ぎます。

## 1. なぜ「4/14 付近から」など、急に変わるのか

| 要因 | 内容 |
|------|------|
| **Gmail 側** | 送信元が件名を `Today Mysteeldata`（スペース）→ `TodayMysteeldata`（なし）に変更した。検索・照合条件が合わず「見つからない」になる。 |
| **スプレッドシート** | タブを `镀锌板卷价格` から `镀锌板卷价格-2` のように**リネーム**した。コードの `getSheetByName` が**別物**を指し、**書き込み先が空振り**する。 |
| **データ形状** | Mysteel の Excel の**先頭行が日付最古**のまま。コードが「1行目＝最新」と誤ると、比較表・グラフが**古い日付**を採用する。 |
| **同じ毎日でも** | 上記は**コードを触らなくても**起き得る。 |

## 2. 正規ソース（唯一 true）

- **GAS コード（書き込み定義）**  
  `E:/factory_monitoring_system/gas_aluminum_clasp/aluminum_price_sheet_automation.gs`  
  デプロイ: このディレクトリで `clasp push`（`gas_aluminum_clasp/.clasp.json` の `scriptId` のプロジェクトに反映）。

- **参照・書き込み先スプレッドシート（ブック）**  
  - ID: `1RQb5fBTipFZPslbG60vP46DJZ8ZD9D7a7_eaKw718nM`  
  - URL: `https://docs.google.com/spreadsheets/d/1RQb5fBTipFZPslbG60vP46DJZ8ZD9D7a7_eaKw718nM/edit`  
  別ブックに差し替え**禁止**（`ALU_CANON_.SPREADSHEET_ID` の変更は PR ＋ 本ドキュメント更新が必須）。

## 3. 正規タブ名（`getSheetByName` ／ 数式内の表記と必ず一致）

| 定数（コード内 `ALU_CANON_`） | 日本語の役割 |
|-------------------------------|--------------|
| `SHEET_GALVANIZED_STEEL` = **镀锌板卷价格-2** | Mysteel 镀锌 Excel の転記先 |
| `SHEET_ALU_DAILY` = **当天铝锭价格** | 长江・南海の日次鋲錠価格（挿入は主に上から 3 行目） |
| `SHEET_COMPARISON` = **供应商资料及最新铝价与旧价对比** | 比較用の参照式・ログ（I10 / I21 等）。無いと一部ログはスキップ。 |
| `CHART_VIEW_SHEET` = **価格推移グラフ** | 価格推移チャート。無ければ GAS が作成。 |
| `CHART_DATA_SHEET` = **グラフデータ** | 中間データ（非表示）。無ければ作成。 |

**運用ルール（絶対）**

- 上記タブを **UI でリネーム・削除**しない。必要なら **コード＋本書＋`assertAluPipelineInvariants_` の想定**を一括更新してから。
- 同じブックに **同じ表示名の重複タブ**を作らない。

## 4. コード側の防止策（既に入っているもの）

- **`ALU_CANON_`**: スプレッドシート ID・タブ名の **単一の定義**（エイリアス `ALU_SPREADSHEET_ID` / `ALU_GALVANIZED_STEEL_SHEET_NAME` はここに合わせる）。
- **`assertAluPipelineInvariants_()`**: `executeAllProcesses` 冒頭で、必須タブ存在とエイリアス不整合を検査。失敗時は `docs/ALUMINUM_GAS_PIPELINE_LOCK.md` 参照を促す。
- **CI**（`.github/workflows/aluminum-gas-invariants.yml`）: 正規 GAS ファイルに **スプレッドシート ID** および **镀锌タブ名** の文字列が含まれることをプッシュ/PR 時に検査。

## 5. 変更手順（意図的に直す場合のみ）

1. 本ファイルの表と説明を更新する。  
2. `aluminum_price_sheet_automation.gs` の `ALU_CANON_` を**同じ内容**に更新する。  
3. `clasp push` し、Apps Script 実行ログで `assert` が通ることを確認する。  
4. PR に「どの外部要因（件名・タブ名・データ形）に合わせたか」を1行で書く。

## 6. 外部（Mysteel / Gmail）の記録

- 件名の表記: **From / Subject の現物**をここに随時追記（例: `TodayMysteeldata YYYY-MM-DD`）。
- 添付ファイル: `.xlsx` かつシート名 `日价格`（`MYSTEEL_EXCEL_SHEET`）想定。変わったら本書＋GAS 取込箇所を更新。

---

**要点**: 毎日同じでも、**相手（メール）とブック（タブ名）が変えれば**結果は変わる。不変にしたいのは **ここに書いた ID・タブ名・正規パス**であり、そこを機械的に揃えるのが上記 **CANON ＋ assert ＋ CI** である。
