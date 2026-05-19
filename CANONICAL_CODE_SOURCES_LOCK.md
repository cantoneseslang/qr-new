# CANONICAL CODE SOURCES LOCK

最終更新: 2026-02-14

このプロジェクトで採用する正規コード/設定は、以下の3対象のみ。
これ以外の情報・記録・履歴・推測は絶対に採用しない。

## 1) モニター本体 (Local Main)

- 画面: `http://localhost:5013/`
- 正規コード: `E:/factory_monitoring_system/cctv_streaming_fixed.py`
- 役割: 5013で表示されるメイン監視画面の唯一ソース

## 2) モニター簡易版 (Vercel Side)

- 正規コード: `E:/factory_monitoring_system/vercel_minimal/app.py`
- 正規設定: `E:/factory_monitoring_system/vercel_minimal/vercel.json`
- 役割: `https://khk-monitor.vercel.app` の Group A / Group B 画面の唯一ソース

## 3) 在庫 STOCK-AI-SCAN

- 正規コード: `E:/factory_monitoring_system/kirii_inventory_vercel/app.py`
- 正規設定: `E:/factory_monitoring_system/kirii_inventory_vercel/vercel.json`
- 役割: STOCK-AI-SCANの唯一ソース

## 絶対禁止ルール

- 上記3対象以外のコードを正規ソースとして扱わない。
- 旧フォルダ、複製フォルダ、過去メモ、古い実験ファイルを参照して判断しない。
- 情報が衝突した場合は、必ず上記3対象だけを採用する。
- 「他の場所にあるかもしれない」という探索を実施しない。

## 運用固定

- モニター本体の確認は `cctv_streaming_fixed.py` のみ。
- モニター簡易版の確認は `vercel_minimal/app.py` と `vercel_minimal/vercel.json` のみ。
- 在庫系の確認は `kirii_inventory_vercel/app.py` と `kirii_inventory_vercel/vercel.json` のみ。

## 4) アルミ・Mysteel GAS（スプレッドシート書き込み）

- 正規ドキュメント: `E:/factory_monitoring_system/docs/ALUMINUM_GAS_PIPELINE_LOCK.md`
- 正規コード: `E:/factory_monitoring_system/gas_aluminum_clasp/aluminum_price_sheet_automation.gs`（`clasp push` の唯一ソース）
- スプレッドシート ID・タブ名の定義は **`ALU_CANON_`** と上記 MD のみを採用する。

## 5) 在庫 Gmail GAS（InventorySummaryReport 同期）

- 正規コード: `E:/factory_monitoring_system/kirii_inventory_vercel/gas-inventory/gmail_inventory_processor-mac.gs.js`（`clasp push` の唯一ソース）
- 正規設定: `E:/factory_monitoring_system/kirii_inventory_vercel/gas-inventory/.clasp.json`
- デプロイ: `kirii_inventory_vercel/gas-inventory/` で `clasp push`（または `clasp-push.ps1`）
- 旧パス `kirii_inventory_vercel/gmail_inventory_processor-mac.gs.js` は使用禁止。

## 旧フォルダ整理（2026-03）

- `khk-monitor/` は保守対象外として削除。
- `khkmon/` は保守対象外として削除。
- `khkmonitor/` は保守対象外として削除。
