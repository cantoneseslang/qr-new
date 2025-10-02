# QR-NEW Vercel デプロイ管理記録

## プロジェクト概要
- **プロジェクト名**: qr-new
- **Vercel URL**: https://vercel.com/kirii/qr-new
- **プロジェクトID**: prj_Z7anXpADDUgRpDlTEyStAQvWlH5N
- **本番URL**: https://qr-new-six.vercel.app
- **GitHubリポジトリ**: https://github.com/cantoneseslang/qr-new.git

## 使用ファイル構成

### メインファイル
- **`E:\factory_monitoring_system\kirii_inventory_vercel\app.py`** ← **メインのFlaskアプリケーション**
  - 正しい「STOCK-AI-SCAN」UIが実装済み
  - Googleシート連携対応
  - QRコードスキャン機能付き
  - 在庫管理システムの完全版

### 設定ファイル
- **`E:\factory_monitoring_system\kirii_inventory_vercel\vercel.json`** ← Vercel設定
- **`E:\factory_monitoring_system\kirii_inventory_vercel\requirements.txt`** ← Python依存関係
- **`E:\factory_monitoring_system\kirii_inventory_vercel\inventory_sync.py`** ← 在庫同期スクリプト

### 関連ファイル（保持）
- **`E:\factory_monitoring_system\kirii_qr_generator.py`** ← QRコード生成ツール
- **`E:\factory_monitoring_system\logo_base64.txt`** ← KIRIIロゴ（Base64）
- **`E:\factory_monitoring_system\KIRII-logo-3.png`** ← KIRIIロゴ（PNG）

## 削除済みファイル（絶対に復元しない）
- ~~`E:\factory_monitoring_system\kirii_qr_inventory_app.py`~~ ← 完全アウト
- ~~`E:\factory_monitoring_system\kirii_inventory_platform.py`~~ ← 絶対存在してはいけない
- ~~`E:\factory_monitoring_system\kirii_qr_inventory\`~~ ← 完全アウトフォルダ
- ~~`E:\factory_monitoring_system\qr-new-vercel-now.py`~~ ← コピー済み
- ~~`E:\factory_monitoring_system\app.py`~~ ← 古いバージョン

## 起動手順

### ローカル起動
```bash
cd E:\factory_monitoring_system\kirii_inventory_vercel
python app.py
```
- アクセス: http://localhost:5001

### Vercelデプロイ
```bash
cd E:\factory_monitoring_system\kirii_inventory_vercel
vercel --prod
```

## 重要な注意事項

### ✅ 正しいファイル
- **`kirii_inventory_vercel/app.py`** のみが正しいコード
- ヘッダー: 「STOCK-AI-SCAN」
- Googleシート連携: 有効
- QRコード機能: 完全実装

### ❌ 絶対に使用してはいけないファイル
- `kirii_qr_inventory_app.py` - 完全アウト
- `kirii_inventory_platform.py` - 絶対存在してはいけない
- `kirii_qr_inventory/` フォルダ - 完全アウト

### 🔧 編集時の注意
1. **必ず `kirii_inventory_vercel/app.py` を編集**
2. 他の `app.py` ファイルは触らない
3. 削除済みファイルは絶対に復元しない
4. デプロイ前は必ずローカルでテスト

## システム機能
- QRコードスキャン（カメラ対応）
- 手動検索機能
- カテゴリフィルタ
- Googleシート連携
- 在庫データ表示
- 工場配置図表示

## Googleシート列マッピング（最新版）

### データ取得範囲
- **範囲**: A1:X1500（A列からX列、最大1500行まで）

### 列マッピング詳細

| 列 | インデックス | 項目名 | 説明 | 処理内容 |
|---|---|---|---|---|
| **A列** | `row[0]` | **番号** | 製品番号 | 数値ならそのまま、空/非数値なら自動採番 |
| **B列** | `row[1]` | - | 未使用 | - |
| **C列** | `row[2]` | **ProductCode** | 製品コード | 必須項目（存在チェック条件） |
| **D列** | `row[3]` | **製品名** | 品名 | 表示用製品名 |
| **E列** | `row[4]` | **Category** | カテゴリ | フィルタ用カテゴリ（KSS除外） |
| **F列** | `row[5]` | - | 未使用 | - |
| **G列** | `row[6]` | - | 未使用 | - |
| **H列** | `row[7]` | - | 未使用 | - |
| **I列** | `row[8]` | - | 未使用 | - |
| **J列** | `row[9]` | - | 未使用 | - |
| **K列** | `row[10]` | - | 未使用 | - |
| **L列** | `row[11]` | - | 未使用 | - |
| **M列** | `row[12]` | - | 未使用 | - |
| **N列** | `row[13]` | - | 未使用 | - |
| **O列** | `row[14]` | - | 未使用 | - |
| **P列** | `row[15]` | - | 未使用 | - |
| **Q列** | `row[16]` | - | 未使用 | - |
| **R列** | `row[17]` | - | 未使用 | - |
| **T列** | `row[18]` | - | 未使用 | - |
| **U列** | `row[19]` | **On Hand** | 参考値 | 在庫参考値（数値変換） |
| **V列** | `row[20]` | **w/o DN** | 出荷未処理 | 出荷未処理数量（数値変換） |
| **W列** | `row[21]` | **Available** | 在庫数量 | メイン在庫数（カンマ除去、負数対応） |
| **X列** | `row[22]` | **Unit** | 単位 | 在庫単位 |
| **Y列** | `row[23]` | **LastTime** | 最終更新日 | 更新日時（デフォルト：現在日時） |

### 認証方式
1. **サービスアカウント認証** (推奨・限定公開対応)
   - 環境変数: `GOOGLE_SERVICE_ACCOUNT_JSON`
2. **API Key認証** (フォールバック・公開シート用)

## Gmail Inventory Processor 設定

### VLOOKUP式設定（最新版）
- **U2列**: On Hand = `=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 3, 0), 0)`
- **V2列**: Quantity SC w/o DN = `=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 4, 0), 0)`
- **W2列**: Available = `=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 5, 0), 0)`
- **Y2列**: 更新時間 = `=InventorySummaryReport!F2`

### 限定公開シート対応
- サービスアカウント: `pq-form@cursor-434016.iam.gserviceaccount.com`
- アクセス方法: `getPrivateSpreadsheet()` 関数使用
- 共有設定: サービスアカウントに「編集者」権限を付与

### テスト関数
- `testMain()`: 時間チェックなしのテスト実行
- `searchInventoryEmailsForTest()`: テスト用メール検索

## 最終更新日
2025年1月27日 - 列マッピング更新（L列・M列削除、Q列から開始）・サービスアカウント認証対応完了
