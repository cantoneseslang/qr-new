#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工場監視システム - Webダッシュボード
Flask-SocketIOを使用したリアルタイム監視ダッシュボード
"""

import os
import json
import time
import base64
from datetime import datetime, timedelta
from threading import Thread
import logging

import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from config import WEB_CONFIG, DATA_CONFIG
from factory_monitor import FactoryMonitor
from camera_connection import FactoryCameraConnection
from object_counter import AdvancedObjectCounter, ObjectCountVisualizer


class WebDashboard:
    """Webダッシュボードクラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # Flask アプリケーション初期化
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'factory_monitor_secret_key'
        
        # CORS とSocketIO設定
        CORS(self.app)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 監視システム初期化
        self.monitor = FactoryMonitor()
        self.camera = FactoryCameraConnection(self.monitor)
        self.counter = AdvancedObjectCounter()
        self.visualizer = ObjectCountVisualizer(self.counter)
        
        # ダッシュボード状態
        self.is_streaming = False
        self.connected_clients = 0
        self.last_frame = None
        self.last_counts = {}
        
        # ルート設定
        self.setup_routes()
        self.setup_socketio_events()
        
        self.logger.info("Webダッシュボードが初期化されました")
    
    def setup_routes(self):
        """Flask ルート設定"""
        
        @self.app.route('/')
        def index():
            """メインダッシュボードページ"""
            return render_template('dashboard.html')
        
        @self.app.route('/api/status')
        def get_status():
            """システム状態API"""
            return jsonify({
                'monitor_status': self.monitor.get_current_status(),
                'camera_info': self.camera.get_camera_info(),
                'inventory_summary': self.counter.get_inventory_summary(),
                'is_streaming': self.is_streaming,
                'connected_clients': self.connected_clients
            })
        
        @self.app.route('/api/statistics')
        def get_statistics():
            """統計情報API"""
            hours = request.args.get('hours', 24, type=int)
            return jsonify({
                'monitor_stats': self.monitor.get_statistics(hours),
                'trend_analysis': self.counter.get_trend_analysis(hours)
            })
        
        @self.app.route('/api/history')
        def get_history():
            """履歴データAPI"""
            limit = request.args.get('limit', 100, type=int)
            history = list(self.monitor.detection_history)[-limit:]
            return jsonify({'history': history})
        
        @self.app.route('/api/connect_camera', methods=['POST'])
        def connect_camera():
            """カメラ接続API"""
            data = request.get_json()
            source = data.get('source')
            
            if source is not None:
                success = self.camera.connect_camera(source)
                return jsonify({
                    'success': success,
                    'message': 'カメラ接続成功' if success else 'カメラ接続失敗',
                    'camera_info': self.camera.get_camera_info()
                })
            else:
                return jsonify({'success': False, 'message': '無効なソース'}), 400
        
        @self.app.route('/api/start_streaming', methods=['POST'])
        def start_streaming():
            """ストリーミング開始API"""
            if not self.camera.is_connected:
                return jsonify({'success': False, 'message': 'カメラが接続されていません'}), 400
            
            if not self.is_streaming:
                self.start_video_streaming()
                return jsonify({'success': True, 'message': 'ストリーミング開始'})
            else:
                return jsonify({'success': False, 'message': '既にストリーミング中です'})
        
        @self.app.route('/api/stop_streaming', methods=['POST'])
        def stop_streaming():
            """ストリーミング停止API"""
            if self.is_streaming:
                self.stop_video_streaming()
                return jsonify({'success': True, 'message': 'ストリーミング停止'})
            else:
                return jsonify({'success': False, 'message': 'ストリーミングしていません'})
        
        @self.app.route('/api/export_data', methods=['POST'])
        def export_data():
            """データエクスポートAPI"""
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"factory_data_{timestamp}.json"
                filepath = os.path.join(DATA_CONFIG['data_dir'], filename)
                
                success = self.counter.export_count_data(filepath)
                
                return jsonify({
                    'success': success,
                    'filename': filename,
                    'message': 'データエクスポート成功' if success else 'データエクスポート失敗'
                })
            except Exception as e:
                return jsonify({'success': False, 'message': str(e)}), 500
    
    def setup_socketio_events(self):
        """SocketIO イベント設定"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """クライアント接続"""
            self.connected_clients += 1
            self.logger.info(f"クライアント接続: {self.connected_clients}人")
            emit('status', {'message': '接続されました', 'clients': self.connected_clients})
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """クライアント切断"""
            self.connected_clients = max(0, self.connected_clients - 1)
            self.logger.info(f"クライアント切断: {self.connected_clients}人")
        
        @self.socketio.on('request_frame')
        def handle_frame_request():
            """フレーム要求"""
            if self.last_frame is not None:
                frame_data = self.encode_frame(self.last_frame)
                emit('frame_data', {
                    'image': frame_data,
                    'counts': self.last_counts,
                    'timestamp': datetime.now().isoformat()
                })
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """状態要求"""
            status = {
                'monitor_status': self.monitor.get_current_status(),
                'camera_info': self.camera.get_camera_info(),
                'inventory_summary': self.counter.get_inventory_summary(),
                'is_streaming': self.is_streaming
            }
            emit('status_update', status)
    
    def encode_frame(self, frame: np.ndarray) -> str:
        """フレームをBase64エンコード"""
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_data = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{frame_data}"
        except Exception as e:
            self.logger.error(f"フレームエンコードエラー: {e}")
            return ""
    
    def start_video_streaming(self):
        """ビデオストリーミング開始"""
        if self.is_streaming:
            return
        
        self.is_streaming = True
        self.streaming_thread = Thread(target=self.streaming_loop, daemon=True)
        self.streaming_thread.start()
        self.logger.info("ビデオストリーミング開始")
    
    def stop_video_streaming(self):
        """ビデオストリーミング停止"""
        self.is_streaming = False
        self.logger.info("ビデオストリーミング停止")
    
    def streaming_loop(self):
        """ストリーミングループ"""
        while self.is_streaming and self.camera.is_connected:
            try:
                # フレーム取得
                ret, frame = self.camera.capture_single_frame()
                
                if ret and frame is not None:
                    # 物体検出
                    counts, annotated_frame = self.monitor.detect_objects(frame)
                    
                    # ダッシュボード作成
                    dashboard_frame = self.visualizer.create_count_dashboard(annotated_frame, counts)
                    
                    # カウントゾーン描画
                    final_frame = self.counter.draw_counting_zones(dashboard_frame)
                    
                    # フレーム・カウント更新
                    self.last_frame = final_frame
                    self.last_counts = counts
                    
                    # クライアントに送信
                    if self.connected_clients > 0:
                        frame_data = self.encode_frame(final_frame)
                        self.socketio.emit('frame_update', {
                            'image': frame_data,
                            'counts': counts,
                            'timestamp': datetime.now().isoformat(),
                            'inventory_summary': self.counter.get_inventory_summary()
                        })
                
                # フレームレート制御
                time.sleep(1.0 / WEB_CONFIG.get('auto_refresh_interval', 5))
                
            except Exception as e:
                self.logger.error(f"ストリーミングエラー: {e}")
                break
        
        self.is_streaming = False
    
    def create_dashboard_template(self):
        """ダッシュボードHTMLテンプレート作成"""
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        os.makedirs(template_dir, exist_ok=True)
        
        html_content = '''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>工場監視システム - YOLO11 ダッシュボード</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f0f0f0;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
        }
        .dashboard-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        .video-panel {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .control-panel {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        #video-stream {
            width: 100%;
            max-width: 800px;
            border-radius: 5px;
        }
        .btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
        }
        .btn:hover {
            background: #5a6fd8;
        }
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online {
            background-color: #4CAF50;
        }
        .status-offline {
            background-color: #f44336;
        }
        .alert {
            background-color: #ff6b6b;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
        }
        .count-display {
            font-size: 2em;
            font-weight: bold;
            color: #333;
            text-align: center;
            margin: 10px 0;
        }
        .input-group {
            margin: 10px 0;
        }
        .input-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        .input-group input {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏭 工場監視システム - YOLO11 ダッシュボード</h1>
        <p>リアルタイム物体検出・在庫管理システム</p>
    </div>

    <div class="dashboard-grid">
        <div class="video-panel">
            <h2>📹 ライブ映像</h2>
            <img id="video-stream" src="" alt="ビデオストリーム" style="display: none;">
            <div id="no-stream" style="text-align: center; color: #666; padding: 50px;">
                ストリーミングが開始されていません
            </div>
        </div>

        <div class="control-panel">
            <h2>🎛️ 制御パネル</h2>
            
            <div class="input-group">
                <label for="camera-source">カメラソース:</label>
                <input type="text" id="camera-source" placeholder="0 (Webカメラ) または RTSP URL">
            </div>
            
            <button class="btn" onclick="connectCamera()">📷 カメラ接続</button>
            <button class="btn" onclick="startStreaming()" id="start-btn" disabled>▶️ 開始</button>
            <button class="btn" onclick="stopStreaming()" id="stop-btn" disabled>⏹️ 停止</button>
            
            <hr style="margin: 20px 0;">
            
            <h3>📊 システム状態</h3>
            <div id="system-status">
                <p><span class="status-indicator status-offline"></span>カメラ: 未接続</p>
                <p><span class="status-indicator status-offline"></span>ストリーミング: 停止中</p>
                <p>接続クライアント: <span id="client-count">0</span>人</p>
            </div>
            
            <hr style="margin: 20px 0;">
            
            <h3>📁 データ管理</h3>
            <button class="btn" onclick="exportData()">💾 データエクスポート</button>
            <button class="btn" onclick="refreshStats()">🔄 統計更新</button>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <h3>📦 現在の在庫</h3>
            <div id="current-inventory">
                <div class="count-display" id="total-count">0</div>
                <p>総アイテム数</p>
                <div id="item-counts"></div>
            </div>
        </div>

        <div class="stat-card">
            <h3>🚨 アラート</h3>
            <div id="alerts-container">
                <p style="color: #666;">アラートはありません</p>
            </div>
        </div>

        <div class="stat-card">
            <h3>📈 統計情報</h3>
            <div id="statistics">
                <p>検出レート: <span id="detection-rate">0</span>/時間</p>
                <p>セッション開始: <span id="session-start">-</span></p>
                <p>総検出数: <span id="total-detections">0</span></p>
            </div>
        </div>

        <div class="stat-card">
            <h3>📊 トレンドグラフ</h3>
            <div id="trend-chart" style="height: 300px;"></div>
        </div>
    </div>

    <script>
        // Socket.IO接続
        const socket = io();
        
        let isStreaming = false;
        let isConnected = false;

        // Socket.IOイベントハンドラ
        socket.on('connect', function() {
            console.log('サーバーに接続しました');
            updateConnectionStatus(true);
        });

        socket.on('disconnect', function() {
            console.log('サーバーから切断されました');
            updateConnectionStatus(false);
        });

        socket.on('frame_update', function(data) {
            updateVideoStream(data);
            updateInventoryDisplay(data);
        });

        socket.on('status_update', function(data) {
            updateSystemStatus(data);
        });

        // カメラ接続
        function connectCamera() {
            const source = document.getElementById('camera-source').value;
            if (!source) {
                alert('カメラソースを入力してください');
                return;
            }

            fetch('/api/connect_camera', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({source: source === '0' ? 0 : source})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    isConnected = true;
                    document.getElementById('start-btn').disabled = false;
                    alert('カメラ接続成功');
                } else {
                    alert('カメラ接続失敗: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('接続エラー');
            });
        }

        // ストリーミング開始
        function startStreaming() {
            fetch('/api/start_streaming', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    isStreaming = true;
                    document.getElementById('start-btn').disabled = true;
                    document.getElementById('stop-btn').disabled = false;
                } else {
                    alert('ストリーミング開始失敗: ' + data.message);
                }
            });
        }

        // ストリーミング停止
        function stopStreaming() {
            fetch('/api/stop_streaming', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    isStreaming = false;
                    document.getElementById('start-btn').disabled = false;
                    document.getElementById('stop-btn').disabled = true;
                    document.getElementById('video-stream').style.display = 'none';
                    document.getElementById('no-stream').style.display = 'block';
                }
            });
        }

        // ビデオストリーム更新
        function updateVideoStream(data) {
            const videoElement = document.getElementById('video-stream');
            const noStreamElement = document.getElementById('no-stream');
            
            if (data.image) {
                videoElement.src = data.image;
                videoElement.style.display = 'block';
                noStreamElement.style.display = 'none';
            }
        }

        // 在庫表示更新
        function updateInventoryDisplay(data) {
            if (data.inventory_summary) {
                const summary = data.inventory_summary;
                
                // 総数表示
                document.getElementById('total-count').textContent = summary.total_items || 0;
                
                // アイテム別カウント
                const itemCountsDiv = document.getElementById('item-counts');
                itemCountsDiv.innerHTML = '';
                
                for (const [item, count] of Object.entries(summary.current_counts || {})) {
                    const itemDiv = document.createElement('div');
                    itemDiv.innerHTML = `<strong>${item}:</strong> ${count}個`;
                    itemCountsDiv.appendChild(itemDiv);
                }
                
                // アラート表示
                const alertsDiv = document.getElementById('alerts-container');
                alertsDiv.innerHTML = '';
                
                if (summary.alerts && summary.alerts.length > 0) {
                    summary.alerts.forEach(alert => {
                        const alertDiv = document.createElement('div');
                        alertDiv.className = 'alert';
                        alertDiv.textContent = `${alert.class_name}: ${alert.current_count}/${alert.threshold}`;
                        alertsDiv.appendChild(alertDiv);
                    });
                } else {
                    alertsDiv.innerHTML = '<p style="color: #666;">アラートはありません</p>';
                }
            }
        }

        // システム状態更新
        function updateSystemStatus(data) {
            // 実装予定
        }

        // 接続状態更新
        function updateConnectionStatus(connected) {
            // 実装予定
        }

        // データエクスポート
        function exportData() {
            fetch('/api/export_data', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('データエクスポート完了: ' + data.filename);
                } else {
                    alert('エクスポート失敗: ' + data.message);
                }
            });
        }

        // 統計更新
        function refreshStats() {
            fetch('/api/statistics')
            .then(response => response.json())
            .then(data => {
                // 統計表示更新
                console.log('統計データ:', data);
            });
        }

        // 定期更新
        setInterval(() => {
            if (isStreaming) {
                socket.emit('request_frame');
            }
            socket.emit('request_status');
        }, 2000);
    </script>
</body>
</html>
        '''
        
        template_path = os.path.join(template_dir, 'dashboard.html')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"ダッシュボードテンプレート作成: {template_path}")
    
    def run(self, host=None, port=None, debug=False):
        """Webサーバー起動"""
        # テンプレート作成
        self.create_dashboard_template()
        
        # サーバー設定
        host = host or WEB_CONFIG['host']
        port = port or WEB_CONFIG['port']
        debug = debug or WEB_CONFIG['debug']
        
        self.logger.info(f"Webダッシュボード起動: http://{host}:{port}")
        
        # サーバー起動
        self.socketio.run(
            self.app,
            host=host,
            port=port,
            debug=debug,
            allow_unsafe_werkzeug=True
        )


def main():
    """メイン関数"""
    print("=== 工場監視システム - Webダッシュボード ===")
    
    # ダッシュボード初期化・起動
    dashboard = WebDashboard()
    
    try:
        dashboard.run()
    except KeyboardInterrupt:
        print("\nダッシュボードを終了します...")
    except Exception as e:
        print(f"エラー: {e}")


if __name__ == "__main__":
    main() 