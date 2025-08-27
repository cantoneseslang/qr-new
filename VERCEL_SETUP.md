# Vercel外部接続設定手順

## 概要
このシステムをVercelで外部からアクセス可能にするための設定手順です。

## 前提条件
- ローカルシステムが正常に起動している（ポート5013）
- ngrokがインストールされている
- Vercelアカウントがある

## 設定手順

### 1. ngrokでトンネルを作成
```bash
# 新しいターミナルで実行
ngrok http 5013
```

### 2. ngrokのURLを取得
ngrokが起動すると、以下のようなURLが表示されます：
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5013
```

### 3. Vercelにデプロイ
```bash
# Vercel CLIをインストール
npm i -g vercel

# プロジェクトをデプロイ
vercel
```

### 4. 環境変数を設定
Vercelのダッシュボードで以下の環境変数を設定：
- `NGROK_URL`: ngrokのURL（例：https://abc123.ngrok.io）

### 5. 再デプロイ
```bash
vercel --prod
```

## アクセス方法
- ローカル: http://localhost:5013
- 外部: https://your-project.vercel.app

## 注意事項
- ngrokのURLは定期的に変更されるため、環境変数の更新が必要
- セキュリティ設定を適切に行う
- 本番環境では認証の追加を検討

## トラブルシューティング
- プロキシエラーが発生する場合は、ngrokのURLが正しいか確認
- タイムアウトエラーが発生する場合は、ローカルシステムの応答性を確認
