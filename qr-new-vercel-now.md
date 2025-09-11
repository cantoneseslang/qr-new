# QR-NEW Vercel デプロイ管理記録

## プロジェクト概要
- **プロジェクト名**: qr-new
- **Vercel URL**: https://vercel.com/kirii/qr-new
- **プロジェクトID**: prj_Z7anXpADDUgRpDlTEyStAQvWlH5N
- **本番URL**: https://qr-nb45nbhzi-kirii.vercel.app
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
- アクセス: http://localhost:5000

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

## 最終更新日
2025年9月11日 - 正しいUI復元・不要ファイル削除完了
