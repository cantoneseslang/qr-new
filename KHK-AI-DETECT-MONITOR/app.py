#!/usr/bin/env python3
"""
KHK-AI-DETECT-MONITOR
AI物体検出監視システム - 画像受信・表示サーバー
Vercelで固定URLを提供
"""

from flask import Flask, render_template_string, jsonify, request, Response
import os
from datetime import datetime
import base64
import threading
import time

app = Flask(__name__)

# 受信した画像の保存
received_image = None
received_image_timestamp = None
image_lock = threading.Lock()

@app.route('/')
def index():
    """メインページ - 完全な監視システムUI"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📹 KHK-MONITOR</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background: white; 
            color: #333; 
        }
        
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
        }
        
        .header { 
            display: flex; 
            align-items: center; 
            margin-bottom: 4px; 
        }
        
        .logo { 
            height: 63px; 
            width: auto; 
            margin-right: 15px; 
        }
        .title-container { 
            flex: 1; 
            text-align: center; 
        }
        h1 { 
            font-size: 24px; 
            margin: 0; 
            color: #2c3e50; 
            font-weight: 900; 
        }
        
        .status-info { 
            background: #f8f9fa; 
            border: 2px solid #17a2b8; 
            border-radius: 10px; 
            padding: 15px; 
            margin: 20px 0; 
            text-align: center; 
            font-weight: bold; 
            color: #17a2b8; 
        }
        .status-info.success { 
            border-color: #28a745; 
            color: #28a745; 
        }
        .status-info.error { 
            border-color: #dc3545; 
            color: #dc3545; 
        }
        
        .controls { 
            text-align: center; 
            margin: 20px 0; 
        }
        .btn { 
            padding: 12px 24px; 
            margin: 10px; 
            border: none; 
            border-radius: 8px; 
            font-size: 16px; 
            font-weight: bold; 
            cursor: pointer; 
            transition: all 0.3s; 
        }
        .btn:hover { 
            transform: translateY(-2px); 
        }
        .btn-success { 
            background: #28a745; 
            color: white; 
        }
        .btn-danger { 
            background: #dc3545; 
            color: white; 
        }
        
        .video-container { 
            margin: 4px 0; 
        }
        .video-section { 
            background: #f8f9fa; 
            border: 2px solid #dee2e6; 
            border-radius: 10px; 
            padding: 10px; 
        }
        .video-frame { 
            width: 100%; 
            height: 420px; 
            object-fit: contain; 
            border-radius: 8px; 
            background: #fff; 
        }
        
        .view-controls { 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            gap: 12px; 
            margin: 16px 0; 
            flex-wrap: wrap; 
            row-gap: 10px; 
        }
        .view-btn { 
            padding: 10px 20px; 
            margin: 0 4px; 
            border: 2px solid #007bff; 
            border-radius: 14px; 
            background: white; 
            color: #007bff; 
            font-weight: 800; 
            cursor: pointer; 
            transition: all 0.3s; 
            font-size: 16px; 
        }
        .view-btn:hover { 
            background: #007bff; 
            color: white; 
        }
        .view-btn.active { 
            background: #007bff; 
            color: white; 
        }
        
        .grid-container { 
            display: grid; 
            gap: 2px; 
            background: #fff; 
            border-radius: 8px; 
            overflow: hidden; 
        }
        .grid-4 { 
            grid-template-columns: 1fr 1fr; 
            grid-template-rows: 1fr 1fr; 
        }
        .grid-6 { 
            grid-template-columns: 1fr 1fr 1fr; 
            grid-template-rows: 1fr 1fr; 
        }
        .grid-9 { 
            grid-template-columns: 1fr 1fr 1fr; 
            grid-template-rows: 1fr 1fr 1fr; 
        }
        .grid-16 { 
            grid-template-columns: 1fr 1fr 1fr 1fr; 
            grid-template-rows: 1fr 1fr 1fr 1fr; 
        }
        .grid-item { 
            background: #fff; 
            min-height: 120px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            color: #6c757d; 
            font-size: 12px; 
        }
        .channel-select { 
            display: grid; 
            justify-content: center; 
            margin-top: 12px; 
            gap: 6px; 
            grid-template-columns: repeat(16, 40px); 
            grid-auto-rows: 36px; 
            place-items: center; 
        }
        .ch-btn { 
            width: 40px; 
            height: 36px; 
            border: 2px solid #007bff; 
            border-radius: 8px; 
            background: white; 
            color: #007bff; 
            font-weight: 800; 
            cursor: pointer; 
            display:inline-flex; 
            align-items:center; 
            justify-content:center; 
        }
        .ch-btn.active { 
            background: #007bff; 
            color: white; 
        }
        
        /* ティッカー表示用スタイル */
        .ticker-container {
            background: rgba(0, 0, 0, 0.95);
            color: white;
            padding: 8px 12px;
            margin: 8px 0;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.2;
            position: absolute;
            top: 10px;
            left: 10px;
            right: 10px;
            z-index: 1000;
        }
        
        .ticker-content {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .ticker-item {
            flex: 1;
            min-width: 300px;
        }
        
        .ticker-label {
            font-weight: bold;
            margin-bottom: 4px;
            animation: blink 6s ease-in-out infinite;
        }
        
        .ticker-text {
            margin: 2px 0;
            animation: blink 6s ease-in-out infinite;
            animation-delay: calc(var(--delay) * 0.3s);
            font-size: 15px;
        }
        
        .ticker-text:nth-child(1) { --delay: 1; }
        .ticker-text:nth-child(2) { --delay: 2; }
        .ticker-text:nth-child(3) { --delay: 3; }
        
        /* ステータスアイコン */
        .status-icon {
            margin-right: 8px;
            font-size: 14px;
        }
        
        .status-complete {
            color: #28a745;
        }
        
        .status-in-progress {
            color: #ffc107;
        }
        
        .status-pending {
            color: #dc3545;
        }
        
        /* テキスト色 */
        .ticker-text.complete {
            color: #28a745;
        }
        
        .ticker-text.in-progress {
            color: #ffc107;
        }
        
        .ticker-text.pending {
            color: #dc3545;
        }
        
        /* 点滅アニメーション */
        @keyframes blink {
            0% { opacity: 0.5; }
            20% { opacity: 1; }
            60% { opacity: 1; }
            100% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img class="logo" src="/static/kirii_logo.png" alt="KIRII Logo">
            <div class="title-container">
                <h1>AI-DETECT-MONITOR</h1>
            </div>
        </div>
        
        <!-- ティッカー表示 -->
        <div id="tickerContainer" class="ticker-container">
            <div class="ticker-content">
                <div class="ticker-item">
                    <div class="ticker-label">本日生産</div>
                    <div class="ticker-text complete">
                        <span class="status-icon status-complete">●</span>
                        K#2504035 0.40x64 0.4x32x32AL批灰角24400-519-生産完
                    </div>
                    <div class="ticker-text in-progress">
                        <span class="status-icon status-in-progress">●</span>
                        K#2412168 0.40x64 0.4x32x32AL批灰角24400-300-生産中
                    </div>
                    <div class="ticker-text pending">
                        <span class="status-icon status-pending">●</span>
                        K#2412300 0.40x64 0.4x32x32AL批灰角24400-250-未生産
                    </div>
                </div>
                <div class="ticker-item">
                    <div class="ticker-label">本日出貨</div>
                    <div class="ticker-text pending">
                        <span class="status-icon status-pending">●</span>
                        SC/20250B/64 50mm企筒2440mm45高1.5厚(藍帯)用料147.0mm-40支-未出貨
                    </div>
                    <div class="ticker-text complete">
                        <span class="status-icon status-complete">●</span>
                        SC/20250B/65 50mm企筒2440mm45高1.2厚(藍帯)用料138.2mm-10支-出貨完
                    </div>
                    <div class="ticker-text complete">
                        <span class="status-icon status-complete">●</span>
                        SC/20250B/75 76mm企筒2440mm45高1.2厚(-帯)用料172.0mm-30支-出貨完
                    </div>
                </div>
            </div>
        </div>
        
        <div class="video-container" style="margin-bottom: 0; position: relative;">
            <div class="video-section">
                <!-- 單一畫面 -->
                <div id="singleView" class="video-display">
                    <img id="videoFrame" class="video-frame" style="display: none;" alt="CCTV YOLO Stream">
                    <div id="noVideo" style="text-align: center; line-height: 420px; color: #6c757d; font-size: 18px;">沒有影像</div>
                </div>
                
                <!-- 分割畫面 -->
                <div id="gridView" class="grid-container grid-6" style="display: none; height: 500px; grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr;">
                    <div class="grid-item" id="grid0">CH1</div>
                    <div class="grid-item" id="grid1">CH2</div>
                    <div class="grid-item" id="grid2">CH3</div>
                    <div class="grid-item" id="grid3">CH4</div>
                    <div class="grid-item" id="grid4">CH5</div>
                    <div class="grid-item" id="grid5">CH6</div>
                </div>
            </div>
        </div>
        
        <div class="view-controls">
            <button id="controlBtn" class="btn btn-success" onclick="toggleStream()">開控</button>
            <button class="view-btn" onclick="refreshMain()" id="btnMain">主面</button>
            <button class="view-btn" onclick="changeView(4)" id="view4">4面</button>
            <button class="view-btn" onclick="changeView(9)" id="view9">9面</button>
            <button class="view-btn" onclick="toggleCycle()" id="btnCycle">循面</button>
            <button class="view-btn" onclick="toggleCycleExpanded()" id="btnCycleExpanded">循拡</button>
            <button class="view-btn" onclick="toggleRemote()" id="btnRemote">遙控</button>
            <button id="debugLogBtn" class="view-btn" onclick="toggleDebugLog()">Log-on</button>
            <button id="tickerToggleBtn" class="view-btn" onclick="toggleTicker()">T-on/off</button>
        </div>

        <div id="channelSelector" class="channel-select" style="display:grid;">
            <button class="ch-btn" onclick="selectChannel(1)" id="ch1">1</button>
            <button class="ch-btn" onclick="selectChannel(2)" id="ch2">2</button>
            <button class="ch-btn" onclick="selectChannel(3)" id="ch3">3</button>
            <button class="ch-btn" onclick="selectChannel(4)" id="ch4">4</button>
            <button class="ch-btn" onclick="selectChannel(5)" id="ch5">5</button>
            <button class="ch-btn" onclick="selectChannel(6)" id="ch6">6</button>
            <button class="ch-btn" onclick="selectChannel(7)" id="ch7">7</button>
            <button class="ch-btn" onclick="selectChannel(8)" id="ch8">8</button>
            <button class="ch-btn" onclick="selectChannel(9)" id="ch9">9</button>
            <button class="ch-btn" onclick="selectChannel(10)" id="ch10">10</button>
            <button class="ch-btn" onclick="selectChannel(11)" id="ch11">11</button>
            <button class="ch-btn" onclick="selectChannel(12)" id="ch12">12</button>
            <button class="ch-btn" onclick="selectChannel(13)" id="ch13">13</button>
            <button class="ch-btn" onclick="selectChannel(14)" id="ch14">14</button>
            <button class="ch-btn" onclick="selectChannel(15)" id="ch15">15</button>
            <button class="ch-btn" onclick="selectChannel(16)" id="ch16">16</button>
        </div>
    </div>
    
    <script>
        // グローバル変数
        let isStreaming = false;
        let currentViewMode = 'single';
        let selectedChannel = 1;
        let isCycleMode = false;
        let isCycleExpanded = false;
        let isRemoteMode = false;
        let debugLogEnabled = false;
        let tickerVisible = true;

        // 基本機能
        function toggleStream() {
            const btn = document.getElementById('controlBtn');
            if (isStreaming) {
                stopStream();
                btn.textContent = '開控';
                btn.className = 'btn btn-success';
            } else {
                startStream();
                btn.textContent = '關控';
                btn.className = 'btn btn-danger';
            }
        }

        function startStream() {
            isStreaming = true;
            updateStatus('🚀 ストリーム開始中...', 'info');
            // 画像更新開始
            startImageUpdate();
        }

        function stopStream() {
            isStreaming = false;
            updateStatus('⏹️ ストリーム停止', 'info');
            // 画像更新停止
            stopImageUpdate();
        }

        // ビューモード切り替え
        function refreshMain() {
            changeViewMode('single');
            updateStatus('🔄 メインビューに戻りました', 'success');
        }

        function changeView(num) {
            changeViewMode('grid' + num);
            updateStatus('📺 ' + num + '分割ビューに切り替え', 'success');
        }

        function changeViewMode(mode) {
            currentViewMode = mode;
            
            // すべてのビューを非表示
            document.getElementById('singleView').style.display = 'none';
            document.getElementById('gridView').style.display = 'none';
            
            // 選択されたビューを表示
            if (mode === 'single') {
                document.getElementById('singleView').style.display = 'block';
                document.getElementById('videoFrame').style.display = 'block';
                document.getElementById('noVideo').style.display = 'none';
            } else if (mode.startsWith('grid')) {
                document.getElementById('gridView').style.display = 'block';
                const num = mode.replace('grid', '');
                updateGridLayout(parseInt(num));
            }
            
            // ボタンのアクティブ状態を更新
            updateButtonStates(mode);
        }

        function updateGridLayout(num) {
            const gridView = document.getElementById('gridView');
            const gridItems = document.querySelectorAll('.grid-item');
            
            // グリッドレイアウトを更新
            if (num === 4) {
                gridView.className = 'grid-container grid-4';
                gridItems.forEach((item, index) => {
                    item.style.display = index < 4 ? 'flex' : 'none';
                });
            } else if (num === 9) {
                gridView.className = 'grid-container grid-9';
                gridItems.forEach((item, index) => {
                    item.style.display = index < 9 ? 'flex' : 'none';
                });
            }
        }

        function updateButtonStates(mode) {
            // すべてのボタンからactiveクラスを削除
            document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
            
            // 選択されたボタンにactiveクラスを追加
            if (mode === 'single') {
                document.getElementById('btnMain').classList.add('active');
            } else if (mode === 'grid4') {
                document.getElementById('view4').classList.add('active');
            } else if (mode === 'grid9') {
                document.getElementById('view9').classList.add('active');
            }
        }

        // 循環モード
        function toggleCycle() {
            isCycleMode = !isCycleMode;
            const btn = document.getElementById('btnCycle');
            if (isCycleMode) {
                btn.classList.add('active');
                updateStatus('🔄 循環モード開始（Vercel側）', 'success');
                // 循環モード時の画像更新を開始
                startCycleMode();
            } else {
                btn.classList.remove('active');
                updateStatus('⏹️ 循環モード停止', 'info');
                // 循環モードを停止
                stopCycleMode();
            }
        }

        function toggleCycleExpanded() {
            isCycleExpanded = !isCycleExpanded;
            const btn = document.getElementById('btnCycleExpanded');
            if (isCycleExpanded) {
                btn.classList.add('active');
                document.body.classList.add('cycle-expanded-mode');
                updateStatus('🔄 循環拡張モード開始（Vercel側）', 'success');
                // 循環拡張モード時の画像更新を開始
                startCycleExpandedMode();
            } else {
                btn.classList.remove('active');
                document.body.classList.remove('cycle-expanded-mode');
                updateStatus('⏹️ 循環拡張モード停止', 'info');
                // 循環拡張モードを停止
                stopCycleExpandedMode();
            }
        }

        // リモート制御
        function toggleRemote() {
            isRemoteMode = !isRemoteMode;
            const btn = document.getElementById('btnRemote');
            if (isRemoteMode) {
                btn.classList.add('active');
                updateStatus('🎮 リモート制御モード開始', 'success');
            } else {
                btn.classList.remove('active');
                updateStatus('⏹️ リモート制御モード停止', 'info');
            }
        }

        // デバッグログ
        function toggleDebugLog() {
            debugLogEnabled = !debugLogEnabled;
            const btn = document.getElementById('debugLogBtn');
            if (debugLogEnabled) {
                btn.textContent = 'Log-off';
                btn.classList.add('active');
                updateStatus('📝 デバッグログ有効', 'success');
            } else {
                btn.textContent = 'Log-on';
                btn.classList.remove('active');
                updateStatus('📝 デバッグログ無効', 'info');
            }
        }

        // ティッカー表示切り替え
        function toggleTicker() {
            const tickerContainer = document.getElementById('tickerContainer');
            const btn = document.getElementById('tickerToggleBtn');
            
            tickerVisible = !tickerVisible;
            
            if (tickerVisible) {
                tickerContainer.style.display = 'block';
                btn.textContent = 'T-off';
                btn.classList.add('active');
                updateStatus('📺 ティッカー表示有効', 'success');
            } else {
                tickerContainer.style.display = 'none';
                btn.textContent = 'T-on';
                btn.classList.remove('active');
                updateStatus('📺 ティッカー表示無効', 'info');
            }
        }

        // チャンネル選択
        function selectChannel(channel) {
            selectedChannel = channel;
            
            // すべてのチャンネルボタンからactiveクラスを削除
            document.querySelectorAll('.ch-btn').forEach(btn => btn.classList.remove('active'));
            
            // 選択されたチャンネルボタンにactiveクラスを追加
            document.getElementById('ch' + channel).classList.add('active');
            
            updateStatus('📺 チャンネル ' + channel + ' を選択', 'success');
        }

        // 画像更新
        let imageUpdateInterval = null;

        function startImageUpdate() {
            if (imageUpdateInterval) {
                clearInterval(imageUpdateInterval);
            }
            
            // 5秒間隔で画像更新
            imageUpdateInterval = setInterval(() => {
                if (isStreaming) {
                    updateImage();
                }
            }, 5000);
            
            // 初回更新
            updateImage();
        }

        function stopImageUpdate() {
            if (imageUpdateInterval) {
                clearInterval(imageUpdateInterval);
                imageUpdateInterval = null;
            }
        }

        function updateImage() {
            const img = document.getElementById('videoFrame');
            const noVideo = document.getElementById('noVideo');
            
            if (img && noVideo) {
                // 画像のタイムスタンプを更新（キャッシュ回避）
                img.src = '/vercel/frame?' + new Date().getTime();
                
                // 画像読み込み成功時
                img.onload = function() {
                    img.style.display = 'block';
                    noVideo.style.display = 'none';
                };
                
                // 画像読み込み失敗時
                img.onerror = function() {
                    img.style.display = 'none';
                    noVideo.style.display = 'block';
                };
            }
        }

        // ステータス更新
        function updateStatus(message, type = 'info') {
            console.log('[' + type.toUpperCase() + '] ' + message);
            
            if (debugLogEnabled) {
                // デバッグログが有効な場合、コンソールに出力
                console.log('📝 ' + new Date().toLocaleTimeString() + ' - ' + message);
            }
        }

        // 循環モード時の画像更新処理
        let cycleInterval = null;
        let cycleExpandedInterval = null;
        
        function startCycleMode() {
            if (cycleInterval) {
                clearInterval(cycleInterval);
            }
            
            cycleInterval = setInterval(() => {
                if (isStreaming && isCycleMode) {
                    updateImage();
                }
            }, 3000);
        }
        
        function stopCycleMode() {
            if (cycleInterval) {
                clearInterval(cycleInterval);
                cycleInterval = null;
            }
        }
        
        function startCycleExpandedMode() {
            if (cycleExpandedInterval) {
                clearInterval(cycleExpandedInterval);
            }
            
            cycleExpandedInterval = setInterval(() => {
                if (isStreaming && isCycleExpanded) {
                    updateImage();
                }
            }, 2000);
        }
        
        function stopCycleExpandedMode() {
            if (cycleExpandedInterval) {
                clearInterval(cycleExpandedInterval);
                cycleExpandedInterval = null;
            }
        }

        // 初期化
        document.addEventListener('DOMContentLoaded', function() {
            // 初期状態設定
            changeViewMode('single');
            selectChannel(1);
            
            // 初期ステータス
            updateStatus('🚀 Vercel監視システム起動完了', 'success');
        });
    </script>
</body>
</html>
    ''')

@app.route('/receive_image', methods=['POST'])
def receive_image():
    """画像を受信して保存"""
    global received_image, received_image_timestamp
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': '画像データがありません'}), 400
        
        image_data = data['image']
        timestamp = data.get('timestamp', time.time())
        
        with image_lock:
            received_image = image_data
            received_image_timestamp = timestamp
        
        print(f"✅ 画像受信成功: {len(image_data)} bytes, タイムスタンプ: {timestamp}")
        return jsonify({'status': 'success', 'message': '画像を受信しました'})
        
    except Exception as e:
        print(f"❌ 画像受信エラー: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/vercel/frame')
def get_frame():
    """最新の受信画像を返す"""
    global received_image, received_image_timestamp
    
    if not received_image:
        return "画像が受信されていません", 404
    
    try:
        # Base64デコード
        image_data = base64.b64decode(received_image)
        
        response = Response(image_data, mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        print(f"❌ 画像表示エラー: {e}")
        return "画像表示エラー", 500

@app.route('/status')
def get_status():
    """システム状態を返す"""
    global received_image, received_image_timestamp
    
    if received_image:
        status = f"画像受信中 - サイズ: {len(received_image)} bytes"
    else:
        status = "画像受信待機中"
    
    return jsonify({
        'status': status,
        'has_image': bool(received_image),
        'last_image_time': received_image_timestamp,
        'endpoints': {
            'receive_image': 'POST /receive_image',
            'frame': 'GET /vercel/frame'
        }
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

