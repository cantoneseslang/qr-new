#!/usr/bin/env python3

from flask import Flask, render_template_string, jsonify, request
import requests
import base64
import json
import os

app = Flask(__name__)

# ローカルストリーミングサーバーのURL（環境変数で設定可能）
STREAMING_SERVER_URL = os.getenv('STREAMING_SERVER_URL', 'http://localhost:5025')

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>KIRII-HK-CCTV-VIEWER</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { 
                margin: 0; 
                padding: 20px; 
                font-family: Arial, sans-serif; 
                background: #f5f5f5;
            }
            .header {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 15px;
                margin-bottom: 20px;
            }
            h1 { 
                color: #2c3e50; 
                text-align: center;
                margin: 0;
                font-size: 28px;
                font-weight: bold;
            }
            .video-container { 
                text-align: center; 
                margin: 20px 0; 
                border: 3px solid #ddd; 
                border-radius: 10px; 
                padding: 10px; 
                background: #fafafa;
                width: 100%;
                height: 70vh;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
                position: relative;
            }
            #video { 
                width: 100%; 
                height: 100%; 
                object-fit: contain;
                border-radius: 5px;
                max-width: none;
                max-height: none;
            }
            .loading {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-size: 18px;
                color: #666;
            }
            .controls { 
                text-align: center; 
                margin: 20px 0;
                display: flex;
                gap: 10px;
                justify-content: center;
                flex-wrap: wrap;
            }
            .btn { 
                padding: 12px 24px; 
                margin: 5px; 
                border: none; 
                border-radius: 5px; 
                cursor: pointer; 
                font-size: 16px; 
                font-weight: bold;
                transition: all 0.3s;
            }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .btn-primary { background: #007bff; color: white; }
            .status { 
                text-align: center; 
                margin: 20px 0; 
                padding: 15px; 
                background: #d4edda; 
                border: 1px solid #c3e6cb; 
                border-radius: 5px; 
                color: #155724;
                font-weight: bold;
            }
            .status.error {
                background: #f8d7da;
                border: 1px solid #f5c6cb;
                color: #721c24;
            }
            .detection-info {
                background: #e7f3ff;
                border: 1px solid #b3d9ff;
                border-radius: 5px;
                padding: 15px;
                margin: 20px 0;
                text-align: center;
            }
            .server-info {
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 5px;
                padding: 15px;
                margin: 20px 0;
                text-align: center;
                font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🌐 KIRII-HK-CCTV-VIEWER</h1>
        </div>
        
        <div class="video-container">
            <img id="video" style="display: none;" alt="CCTV Feed">
            <div id="loading" class="loading">📡 ストリーミングサーバーに接続中...</div>
        </div>
        
        <div class="controls">
            <button onclick="startViewing()" class="btn btn-success" id="startBtn">▶️ 視聴開始</button>
            <button onclick="stopViewing()" class="btn btn-danger" id="stopBtn">⏹️ 視聴停止</button>
            <button onclick="refreshStream()" class="btn btn-primary">🔄 更新</button>
        </div>
        
        <div id="status" class="status">
            ⏸️ 待機中 - 視聴開始ボタンを押してください
        </div>
        
        <div class="detection-info">
            <h3>🎯 検出情報</h3>
            <p id="detectionCount">検出数: 0</p>
            <div id="detectionList"></div>
        </div>
        
        <div class="server-info">
            <strong>📡 ストリーミングサーバー:</strong> {{ streaming_server_url }}<br>
            <small>※ローカルサーバーが起動している必要があります</small>
        </div>
        
        <script>
            let isViewing = false;
            let updateInterval = null;
            const streamingServerUrl = '{{ streaming_server_url }}';
            
            function startViewing() {
                isViewing = true;
                document.getElementById('status').textContent = '✅ 視聴開始 - ライブストリーミング中';
                document.getElementById('status').className = 'status';
                
                // フレーム更新を開始
                updateInterval = setInterval(updateFrame, 100); // 10 FPS
                updateFrame(); // 即座に1回実行
            }
            
            function stopViewing() {
                isViewing = false;
                if (updateInterval) {
                    clearInterval(updateInterval);
                    updateInterval = null;
                }
                
                document.getElementById('status').textContent = '⏹️ 視聴停止';
                document.getElementById('video').style.display = 'none';
                document.getElementById('loading').style.display = 'block';
                document.getElementById('loading').textContent = '⏸️ 視聴停止中';
            }
            
            function refreshStream() {
                if (isViewing) {
                    updateFrame();
                }
            }
            
            async function updateFrame() {
                if (!isViewing) return;
                
                try {
                    const response = await fetch('/api/stream_data');
                    const data = await response.json();
                    
                    if (data.success && data.frame) {
                        // フレーム表示
                        const video = document.getElementById('video');
                        video.src = 'data:image/jpeg;base64,' + data.frame;
                        video.style.display = 'block';
                        document.getElementById('loading').style.display = 'none';
                        
                        // 検出情報更新
                        updateDetectionInfo(data.detections || [], data.detection_count || 0);
                        
                        // ステータス更新
                        const timestamp = new Date(data.timestamp).toLocaleTimeString();
                        document.getElementById('status').textContent = 
                            `✅ ライブ配信中 - ${timestamp} (フレーム: ${data.frame_count || 0})`;
                        document.getElementById('status').className = 'status';
                        
                    } else {
                        // エラー状態
                        document.getElementById('video').style.display = 'none';
                        document.getElementById('loading').style.display = 'block';
                        document.getElementById('loading').textContent = '❌ ストリーミングサーバーに接続できません';
                        document.getElementById('status').textContent = '❌ 接続エラー - ローカルサーバーを確認してください';
                        document.getElementById('status').className = 'status error';
                    }
                    
                } catch (error) {
                    console.error('ストリーミングエラー:', error);
                    document.getElementById('video').style.display = 'none';
                    document.getElementById('loading').style.display = 'block';
                    document.getElementById('loading').textContent = '❌ 接続エラー';
                    document.getElementById('status').textContent = '❌ ネットワークエラー';
                    document.getElementById('status').className = 'status error';
                }
            }
            
            function updateDetectionInfo(detections, count) {
                document.getElementById('detectionCount').textContent = `検出数: ${count}`;
                
                const detectionList = document.getElementById('detectionList');
                if (detections && detections.length > 0) {
                    const listHtml = detections.map(det => 
                        `<div style="margin: 5px 0; padding: 5px; background: #f0f8ff; border-radius: 3px;">
                            ${det.class}: ${(det.confidence * 100).toFixed(1)}%
                        </div>`
                    ).join('');
                    detectionList.innerHTML = listHtml;
                } else {
                    detectionList.innerHTML = '<div style="color: #666;">検出されたオブジェクトはありません</div>';
                }
            }
            
            // 初期化
            window.onload = function() {
                console.log('KIRII CCTV Viewer 初期化完了');
            };
        </script>
    </body>
    </html>
    ''', streaming_server_url=STREAMING_SERVER_URL)

@app.route('/api/stream_data')
def api_stream_data():
    """ローカルストリーミングサーバーからデータを取得"""
    try:
        response = requests.get(f'{STREAMING_SERVER_URL}/api/stream', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'frame': data.get('frame'),
                'detections': data.get('detections', []),
                'detection_count': data.get('detection_count', 0),
                'timestamp': data.get('timestamp'),
                'frame_count': data.get('frame_count', 0),
                'status': data.get('status', 'unknown')
            })
        else:
            return jsonify({'success': False, 'error': 'Server response error'})
    
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 