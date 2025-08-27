#!/usr/bin/env python3

import sys
import os

# ローカルテスト用のポート設定
os.environ['PORT'] = '5050'

# 統合版を実行
if __name__ == '__main__':
    print("🚀 KIRII-VERCEL統合版 ローカルテスト開始")
    print("📱 ブラウザで http://localhost:5050 を開いてください")
    print("💡 Ctrl+C で停止")
    print("=" * 60)
    
    try:
        from vercel_integrated import app
        app.run(host='0.0.0.0', port=5050, debug=True)
    except KeyboardInterrupt:
        print("\n🛑 テスト終了")
    except Exception as e:
        print(f"❌ エラー: {e}")
        print("依存関係をインストールしてください: pip install -r requirements.txt") 