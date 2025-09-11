# KIRII在庫管理システム - Vercelデプロイ版

## 🚀 Vercelデプロイ手順

### 1. GitHubリポジトリ作成
```bash
# GitHubに新しいリポジトリを作成
# このフォルダの内容をアップロード
```

### 2. Vercelでデプロイ
1. [Vercel](https://vercel.com) にアクセス
2. GitHubアカウントで登録/ログイン
3. 「New Project」をクリック
4. 作成したリポジトリを選択
5. 「Deploy」をクリック

### 3. 自動設定
- `vercel.json` により自動設定
- Python環境とFlask設定
- 本番用URL生成

## 📱 機能

- QRコード在庫確認
- 携帯対応レスポンシブデザイン
- リアルタイム在庫表示
- 製品詳細情報表示

## 🔗 QRコード連携

生成されたQRコードは本番URLに自動リダイレクト:
- `https://your-app-name.vercel.app/product/BD-060`
- `https://your-app-name.vercel.app/product/AC-258`

## 📊 在庫データ

現在はコード内にハードコード。実運用時は:
- データベース連携
- Google Sheets API
- REST API連携

## 🛠️ カスタマイズ

`app.py` の `inventory_data` を編集して在庫情報を更新可能。 