# CANONICAL CODE SOURCES LOCK

最終更新: 2026-02-14

このプロジェクトで採用する正規コード/設定は、以下の3対象のみ。
これ以外の情報・記録・履歴・推測は絶対に採用しない。

## 1) モニター本体 (Local Main)

- 画面: `http://localhost:5013/`
- 正規コード: `E:/factory_monitoring_system/cctv_streaming_fixed.py`
- 役割: 5013で表示されるメイン監視画面の唯一ソース

## 2) モニター簡易版 (Vercel Side)

- 正規コード: `E:/factory_monitoring_system/KHK-AI-DETECT-MONITOR/app.py`
- 役割: Vercel側で運用する簡易版の唯一ソース

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
- モニター簡易版の確認は `KHK-AI-DETECT-MONITOR/app.py` のみ。
- 在庫系の確認は `kirii_inventory_vercel/app.py` と `kirii_inventory_vercel/vercel.json` のみ。
