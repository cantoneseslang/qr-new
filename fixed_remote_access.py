#!/usr/bin/env python3

import cv2
import requests
from flask import Flask, render_template_string, Response, jsonify
import threading
import time
from datetime import datetime

class FixedRemoteAccess:
    def __init__(self):
        self.app = Flask(__name__)
        self.camera = None
        self.is_streaming = False
        
        # 修正されたカメラURL候補（ポート80に修正）
        self.camera_candidates = [
            # D-Linkポートフォワーディング経由（修正版）
            "http://192.168.0.98:18080/cgi-bin/guest/Video.cgi?media=MJPEG&resolution=640*480",
            "http://admin:admin@192.168.0.98:18080/cgi-bin/guest/Video.cgi?media=MJPEG&resolution=640*480",
            "http://192.168.0.98:18081/cgi-bin/guest/Video.cgi?media=MJPEG&resolution=640*480",
            "http://admin:admin@192.168.0.98:18081/cgi-bin/guest/Video.cgi?media=MJPEG&resolution=640*480",
            
            # 直接アクセス（テスト用）
            "http://192.168.1.10/cgi-bin/guest/Video.cgi?media=MJPEG&resolution=640*480",
            "http://admin:admin@192.168.1.10/cgi-bin/guest/Video.cgi?media=MJPEG&resolution=640*480",
        ]
        
        self.working_url = None
        self.setup_routes()
    
    def test_connection(self, url):
        """カメラURLの接続テスト"""
        try:
            print(f"テスト中: {url}")
            response = requests.get(url, timeout=5, stream=True)
            if response.status_code == 200:
                print(f"✅ 成功: {url}")
                return True
        except Exception as e:
            print(f"❌ 失敗: {url} - {str(e)}")
        return False
    
    def find_working_camera(self):
        """動作するカメラURLを探す"""
        print("=== CCTVカメラ接続テスト開始 ===")
        print("CCTVカメラ設定:")
        print("- IP: 192.168.1.10")
        print("- ポート: 80")
        print("- ゲートウェイ: 192.168.1.1 (D-Link)")
        print("- 認証: admin/admin")
        print()
        
        for url in self.camera_candidates:
            if self.test_connection(url):
                self.working_url = url
                return url
        return None
    
    def generate_frames(self):
        """フレーム生成"""
        if not self.working_url:
            return
            
        self.camera = cv2.VideoCapture(self.working_url)
        
        while self.is_streaming:
            success, frame = self.camera.read()
            if not success:
                print("フレーム読み取り失敗")
                break
            else:
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        
        if self.camera:
            self.camera.release()
    
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>修正版リモートアクセス</title>
                <meta charset="UTF-8">
                <style>
                    body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
                    .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
                    .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
                    .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
                    .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
                    .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
                    .warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
                    button { padding: 10px 20px; margin: 5px; font-size: 16px; border: none; border-radius: 5px; cursor: pointer; }
                    .btn-primary { background: #007bff; color: white; }
                    .btn-success { background: #28a745; color: white; }
                    .btn-danger { background: #dc3545; color: white; }
                    #video { max-width: 100%; border: 2px solid #ddd; border-radius: 5px; }
                    .log { background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; max-height: 300px; overflow-y: auto; }
                    .config-info { background: #e9ecef; padding: 15px; border-radius: 5px; margin: 10px 0; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🎥 修正版リモートアクセス</h1>
                    
                    <div class="config-info">
                        <h3>📋 CCTVカメラ設定情報</h3>
                        <strong>カメラIP:</strong> 192.168.1.10<br>
                        <strong>ポート:</strong> 80 (修正済み)<br>
                        <strong>ゲートウェイ:</strong> 192.168.1.1 (D-Link)<br>
                        <strong>認証:</strong> admin/admin<br>
                        <strong>MAC:</strong> 00:0E:53:2C:29:A4
                    </div>
                    
                    <div class="info status">
                        <strong>現在のネットワーク:</strong> kirii_wifi (192.168.0.x)<br>
                        <strong>D-Linkルーター:</strong> 192.168.0.98<br>
                        <strong>ポートフォワーディング:</strong> 18080→192.168.1.10:80 (修正版)
                    </div>
                    
                    <div class="warning status">
                        <strong>⚠️ 重要:</strong> D-Linkのポートフォワーディング設定で<br>
                        CCTV Private Port を <strong>10000 → 80</strong> に変更してください！
                    </div>
                    
                    <button onclick="testConnections()" class="btn-primary">🔍 接続テスト</button>
                    <button onclick="startStream()" class="btn-success">▶️ 配信開始</button>
                    <button onclick="stopStream()" class="btn-danger">⏹️ 配信停止</button>
                    
                    <div id="status" class="status"></div>
                    
                    <div style="text-align: center; margin: 20px 0;">
                        <img id="video" src="/video_feed" style="display: none;">
                    </div>
                    
                    <div id="log" class="log"></div>
                </div>
                
                <script>
                    function updateStatus(message, type = 'info') {
                        const status = document.getElementById('status');
                        status.className = 'status ' + type;
                        status.innerHTML = message;
                    }
                    
                    function addLog(message) {
                        const log = document.getElementById('log');
                        const time = new Date().toLocaleTimeString();
                        log.innerHTML += `[${time}] ${message}<br>`;
                        log.scrollTop = log.scrollHeight;
                    }
                    
                    function testConnections() {
                        updateStatus('接続テスト中...', 'info');
                        addLog('CCTVカメラ接続テスト開始');
                        
                        fetch('/test_connections')
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                updateStatus(`✅ 接続成功: ${data.url}`, 'success');
                                addLog(`接続成功: ${data.url}`);
                            } else {
                                updateStatus('❌ 全ての接続に失敗 - D-Linkポートフォワーディング設定を確認', 'error');
                                addLog('全ての接続に失敗 - ポートフォワーディング設定要確認');
                            }
                        })
                        .catch(error => {
                            updateStatus('❌ テストエラー', 'error');
                            addLog(`エラー: ${error}`);
                        });
                    }
                    
                    function startStream() {
                        fetch('/start_stream', {method: 'POST'})
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                updateStatus('✅ 配信開始', 'success');
                                document.getElementById('video').style.display = 'block';
                                addLog('配信開始');
                            } else {
                                updateStatus('❌ 配信開始失敗', 'error');
                                addLog('配信開始失敗');
                            }
                        });
                    }
                    
                    function stopStream() {
                        fetch('/stop_stream', {method: 'POST'})
                        .then(response => response.json())
                        .then(data => {
                            updateStatus('⏹️ 配信停止', 'info');
                            document.getElementById('video').style.display = 'none';
                            addLog('配信停止');
                        });
                    }
                    
                    // ページ読み込み時に自動テスト
                    window.onload = function() {
                        addLog('修正版リモートアクセステスト開始');
                        addLog('CCTVカメラ設定: IP=192.168.1.10, Port=80');
                        setTimeout(testConnections, 1000);
                    };
                </script>
            </body>
            </html>
            ''')
        
        @self.app.route('/test_connections')
        def test_connections():
            working_url = self.find_working_camera()
            if working_url:
                return jsonify({'success': True, 'url': working_url})
            else:
                return jsonify({'success': False, 'message': '接続失敗'})
        
        @self.app.route('/start_stream', methods=['POST'])
        def start_stream():
            if self.working_url:
                self.is_streaming = True
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'message': '有効なカメラURLなし'})
        
        @self.app.route('/stop_stream', methods=['POST'])
        def stop_stream():
            self.is_streaming = False
            if self.camera:
                self.camera.release()
            return jsonify({'success': True})
        
        @self.app.route('/video_feed')
        def video_feed():
            return Response(self.generate_frames(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
    
    def run(self, port=5020):
        print(f"🚀 修正版リモートアクセス起動: http://localhost:{port}")
        print("CCTVカメラ設定情報:")
        print("- IP: 192.168.1.10")
        print("- ポート: 80")
        print("- 認証: admin/admin")
        print("- D-Linkポートフォワーディング要修正: Private Port 10000→80")
        self.app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    app = FixedRemoteAccess()
    app.run() 