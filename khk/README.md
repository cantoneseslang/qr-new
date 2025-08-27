# KHK-AI-DETECT-MONITOR

AI物体検出監視システムへの入り口を提供するVercelアプリケーション

## 🎯 目的

- ngrokの不安定な問題を解決
- 固定URLで監視システムにアクセス可能
- 会社のプラットフォームから安定したリンクを提供

## 🚀 機能

- 監視システムへの入り口
- システムステータス表示
- 固定URLでのアクセス
- レスポンシブデザイン

## 🔗 アクセス方法

- **Vercel URL**: `vercel.com/kirii/KHK-AI-DETECT-MONITOR`
- **ローカル監視システム**: `http://localhost:5013`
- **API エンドポイント**: `/status`, `/health`

## 📁 ファイル構成

```
KHK-AI-DETECT-MONITOR/
├── app.py              # Flaskアプリケーション
├── vercel.json         # Vercel設定
├── requirements.txt    # 依存関係
└── README.md          # このファイル
```

## 🛠️ 技術仕様

- **フレームワーク**: Flask 2.3.3
- **デプロイ先**: Vercel
- **言語**: Python 3.x
- **デザイン**: レスポンシブCSS

## 📊 監視システム情報

- **監視対象**: CCTVカメラ (192.168.0.98:18080)
- **AI検出**: YOLO11 物体検出エンジン
- **検出対象**: 人物、車両、自転車、バス、電車、トラック

## 🔧 セットアップ

1. Vercelにログイン
2. 新しいプロジェクトを作成: `KHK-AI-DETECT-MONITOR`
3. このディレクトリをアップロード
4. デプロイを実行

## 📝 注意事項

- 監視システムはローカル環境で動作する必要があります
- このVercelアプリは入り口として機能します
- 実際のCCTV監視はローカル環境で実行されます

