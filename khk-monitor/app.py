#!/usr/bin/env python3
"""
KHK-AI-DETECT-MONITOR
AI物体検出監視システムへの入り口
Vercelで固定URLを提供
"""

from flask import Flask, render_template_string, jsonify, request
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def index():
    """メインページ - 監視システムへの入り口"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📹 KHK-AI-DETECT-MONITOR</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }
        
        .logo {
            font-size: 4em;
            margin-bottom: 20px;
        }
        
        .title {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .monitoring-card {
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .monitoring-link {
            display: block;
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            text-decoration: none;
            padding: 25px;
            border-radius: 15px;
            font-size: 1.3em;
            font-weight: bold;
            transition: all 0.3s ease;
            margin: 20px 0;
        }
        
        .monitoring-link:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }
        
        .monitoring-link .icon {
            font-size: 2.5em;
            margin-bottom: 15px;
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #4CAF50;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .info-section {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        
        .info-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #4CAF50;
        }
        
        .footer {
            text-align: center;
            opacity: 0.7;
            margin-top: 40px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">📹</div>
            <div class="title">KHK-AI-DETECT-MONITOR</div>
            <div class="subtitle">AI物体検出監視システム</div>
        </div>
        
        <div class="monitoring-card">
            <div class="status-indicator"></div>
            <div style="font-size: 1.1em; margin-bottom: 20px;">監視システム稼働中</div>
            
            <a href="http://localhost:5013" class="monitoring-link" target="_blank">
                <div class="icon">🚀</div>
                <div>監視システムを開く</div>
                <div style="font-size: 0.8em; opacity: 0.8;">CCTV監視・YOLO物体検出</div>
            </a>
            
            <div style="margin-top: 20px; padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; font-size: 0.9em;">
                <div style="color: #ffd700; margin-bottom: 10px;">⚠️ 重要なお知らせ</div>
                <div>• このページは監視システムへの入り口です</div>
                <div>• 実際の監視機能はローカル環境（localhost:5013）で動作します</div>
                <div>• Vercel環境ではフレーム取得やストリーミングは無効化されています</div>
            </div>
        </div>
        
        <div class="info-section">
            <div class="info-title">📊 システム情報</div>
            <div>• 監視対象: CCTVカメラ (192.168.0.98:18080)</div>
            <div>• AI検出: YOLO11 物体検出エンジン</div>
            <div>• 検出対象: 人物、車両、自転車、バス、電車、トラック</div>
            <div>• 更新時刻: {{ current_time }}</div>
        </div>
        
        <div class="info-section">
            <div class="info-title">🔗 アクセス方法</div>
            <div>• ローカル: http://localhost:5013</div>
            <div>• 外部: このVercelアプリからリンク</div>
            <div>• 固定URL: vercel.com/kirii/KHK-AI-DETECT-MONITOR</div>
        </div>
        
        <div class="footer">
            © 2025 KHK-AI-DETECT-MONITOR<br>
            Powered by Vercel
        </div>
    </div>
    
    <script>
        // 404エラー防止のためのエラーハンドリング
        console.log('📹 Vercel環境: フレーム取得はローカル環境でご利用ください');
        
        // フレーム取得の試行を完全に無効化
        if (typeof updateImage === 'function') {
            // updateImage関数が存在する場合は無効化
            window.updateImage = function() {
                console.log('📹 Vercel環境: フレーム取得は無効化されています');
                return false;
            };
        }
        
        // ストリーム開始の試行を無効化
        if (typeof startStream === 'function') {
            window.startStream = function() {
                console.log('📹 Vercel環境: ストリーミングは無効化されています');
                return false;
            };
        }
        
        // 画像更新の試行を無効化
        if (typeof startImageUpdate === 'function') {
            window.startImageUpdate = function() {
                console.log('📹 Vercel環境: 画像更新は無効化されています');
                return false;
            };
        }
        
        // エラーイベントの処理
        window.addEventListener('error', function(e) {
            if (e.target.src && e.target.src.includes('/vercel/frame')) {
                console.log('📹 Vercel環境: フレーム取得はローカル環境でご利用ください');
                e.target.style.display = 'none';
            }
        });
        
        // 画像読み込みエラーの処理
        document.addEventListener('DOMContentLoaded', function() {
            const images = document.querySelectorAll('img');
            images.forEach(img => {
                img.addEventListener('error', function() {
                    if (this.src.includes('/vercel/frame')) {
                        console.log('📹 Vercel環境: フレーム取得はローカル環境でご利用ください');
                        this.style.display = 'none';
                    }
                });
            });
        });
    </script>
</body>
</html>
    ''', current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/status')
def status():
    """システムステータス確認用API"""
    return jsonify({
        'status': 'online',
        'service': 'KHK-AI-DETECT-MONITOR',
        'timestamp': datetime.now().isoformat(),
        'monitoring_url': 'http://localhost:5013'
    })

@app.route('/vercel/frame')
def vercel_frame():
    """Vercel用フレーム取得エンドポイント（404エラー防止）"""
    return jsonify({
        'success': False,
        'error': 'Vercel環境ではフレーム取得はサポートされていません。ローカル環境でご利用ください。',
        'local_url': 'http://localhost:5013'
    })

@app.route('/vercel/stream')
def vercel_stream():
    """Vercel用ストリームエンドポイント（404エラー防止）"""
    return jsonify({
        'success': False,
        'error': 'Vercel環境ではストリーミングはサポートされていません。ローカル環境でご利用ください。',
        'local_url': 'http://localhost:5013'
    })

@app.route('/health')
def health():
    """ヘルスチェック用エンドポイント"""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(debug=False)

