#!/usr/bin/env python3

import requests
import cv2
import numpy as np
from flask import Flask, render_template_string
import threading
import time
import base64
from requests.auth import HTTPBasicAuth
from ultralytics import YOLO
import os

app = Flask(__name__)

class CCTVWorkingRestored:
    def __init__(self):
        # 動作確認済みのCCTV設定
        import time
        timestamp = int(time.time())
        self.working_url = f"http://192.168.0.98:18080/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&stream=1&nocache={timestamp}"
        self.username = "admin"
        self.password = "admin"
        
        # YOLO設定
        self.model = None
        self.forklift_model = None
        self.load_yolo_model()
        
        # ストリーム設定
        self.current_frame = None
        self.is_streaming = False
        self.detection_results = []
        self.connection_status = "停止中"
        
        # 検出機能制御
        self.yolo_enabled = False
        self.forklift_detection_enabled = True
        self.person_detection_enabled = True
        
        # 検出閾値設定
        self.forklift_confidence = 0.2
        self.forklift_iou = 0.5
        self.person_confidence = 0.2
        self.person_iou = 0.4
        
    def load_yolo_model(self):
        """YOLOモデル読み込み"""
        try:
            # フォークリフト専用モデル
            forklift_model_path = 'forklift_model.pt'
            if os.path.exists(forklift_model_path):
                self.forklift_model = YOLO(forklift_model_path)
                print("🚛 フォークリフト検出モデル読み込み成功")
            
            # 標準YOLOモデル
            model_path = 'yolo11n.pt'
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print("📦 標準YOLO11nモデル使用")
                print("✅ YOLOモデル読み込み成功: yolo11n.pt")
                print(f"📊 検出可能クラス数: {len(self.model.names)}")
            else:
                print("❌ YOLOモデルファイルが見つかりません")
        except Exception as e:
            print(f"❌ YOLOモデル読み込みエラー: {e}")
    
    def detect_objects(self, frame):
        """YOLO物体検出"""
        if self.model is None:
            return frame, []
        
        try:
            results = self.model(frame, verbose=False)
            detections = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = int(box.cls[0].cpu().numpy())
                        
                        if conf > 0.5:
                            class_name = self.model.names[cls]
                            detections.append({
                                'class': class_name,
                                'confidence': float(conf),
                                'bbox': [int(x1), int(y1), int(x2), int(y2)]
                            })
                            
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                            label = f'{class_name}: {conf:.2f}'
                            cv2.putText(frame, label, (int(x1), int(y1) - 10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            return frame, detections
            
        except Exception as e:
            print(f"❌ YOLO検出エラー: {e}")
            return frame, []
    
    def detect_forklifts(self, frame):
        """フォークリフト検出（専用モデル使用）"""
        if self.forklift_model is None:
            return []
        try:
            results = self.forklift_model(
                frame,
                conf=self.forklift_confidence,
                iou=self.forklift_iou,
                verbose=False
            )
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        if class_id == 0: # forklift
                            detection = {
                                'class': 'forklift',
                                'display_name': 'FORKLIFT',
                                'confidence': float(confidence),
                                'bbox': [int(x1), int(y1), int(x2), int(y2)]
                            }
                            detections.append(detection)
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 1)
                            label = f'FORKLIFT: {confidence:.1f}'
                            cv2.putText(frame, label, (int(x1), int(y1) - 5),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            return detections
        except Exception as e:
            print(f"❌ フォークリフト検出エラー: {e}")
            return []

    def detect_persons(self, frame):
        """Person検出（低閾値設定）"""
        if self.model is None:
            return []
        try:
            results = self.model(
                frame,
                conf=self.person_confidence,
                iou=self.person_iou,
                verbose=False
            )
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        if class_id == 0: # Person class is 0 in YOLO11n
                            detection = {
                                'class': 'person',
                                'display_name': 'PERSON',
                                'confidence': float(confidence),
                                'bbox': [int(x1), int(y1), int(x2), int(y2)]
                            }
                            detections.append(detection)
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 1)
                            label = f'PERSON: {confidence:.1f}'
                            cv2.putText(frame, label, (int(x1), int(y1) - 5),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
            return detections
        except Exception as e:
            print(f"❌ Person検出エラー: {e}")
            return []
    
    def start_cctv_stream(self):
        """CCTVストリーム開始"""
        self.is_streaming = True
        
        def stream_worker():
            try:
                print(f"🎥 CCTVストリーム開始: {self.working_url}")
                
                response = requests.get(
                    self.working_url,
                    auth=HTTPBasicAuth(self.username, self.password),
                    stream=True,
                    timeout=30
                )
                
                if response.status_code == 200:
                    print("✅ CCTV接続成功")
                    self.connection_status = "ストリーミング中"
                    
                    buffer = b''
                    frame_count = 0
                    
                    for chunk in response.iter_content(chunk_size=1024):
                        if not self.is_streaming:
                            break
                            
                        buffer += chunk
                        
                        while True:
                            start = buffer.find(b'\xff\xd8')
                            end = buffer.find(b'\xff\xd9')
                            
                            if start != -1 and end != -1 and end > start:
                                jpeg_data = buffer[start:end+2]
                                buffer = buffer[end+2:]
                                
                                img_array = np.frombuffer(jpeg_data, np.uint8)
                                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                
                                if frame is not None:
                                    processed_frame, detections = self.detect_objects(frame)
                                    
                                    _, buffer_encoded = cv2.imencode('.jpg', processed_frame, 
                                                                   [cv2.IMWRITE_JPEG_QUALITY, 80])
                                    frame_base64 = base64.b64encode(buffer_encoded).decode('utf-8')
                                    
                                    self.current_frame = frame_base64
                                    self.detection_results = detections
                                    
                                    frame_count += 1
                                    if frame_count % 30 == 0:
                                        print(f"🖼️ フレーム {frame_count}: {len(detections)} objects detected")
                                    
                                    time.sleep(0.1)
                            else:
                                break
                else:
                    print(f"❌ CCTV接続失敗: {response.status_code}")
                    self.connection_status = f"HTTP {response.status_code} エラー"
                    
            except Exception as e:
                print(f"❌ CCTVストリームエラー: {e}")
                self.connection_status = f"エラー: {str(e)}"
            finally:
                self.is_streaming = False
                print("🔴 CCTVストリーム停止")
        
        thread = threading.Thread(target=stream_worker, daemon=True)
        thread.start()
        return True
    
    def stop_stream(self):
        """ストリーム停止"""
        self.is_streaming = False
        self.current_frame = None
        self.detection_results = []
        self.connection_status = "停止中"

# グローバルインスタンス
cctv_system = CCTVWorkingRestored()

@app.route('/')
def index():
    # 5013のUIテイストを移植（機能は従来どおり単画面＋検出）
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>KIRII CCTV‑YOLO (復元版)</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #ffffff; color: #2c3e50; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { display: flex; align-items: center; margin-bottom: 20px; }
            .title-container { flex: 1; text-align: center; }
            h1 { font-size: 32px; margin: 0; color: #2c3e50; font-weight: 900; }
            .status-info { background: #f8f9fa; border: 2px solid #17a2b8; border-radius: 10px; padding: 15px; margin: 16px 0; text-align: center; font-weight: bold; color: #17a2b8; }
            .status-info.success { border-color: #28a745; color: #28a745; }
            .status-info.error { border-color: #dc3545; color: #dc3545; }
            .controls { text-align: center; margin: 10px 0 20px; }
            .btn { padding: 12px 24px; margin: 8px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .video-container { margin: 10px 0; }
            .video-section { background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 10px; padding: 20px; }
            .video-frame { width: 100%; height: 420px; object-fit: contain; border-radius: 8px; background: #000; }
            .detection-panel { background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 10px; padding: 16px; margin: 16px 0; }
            .detection-item { background: white; margin: 8px 0; padding: 12px; border-radius: 6px; display: flex; justify-content: space-between; border: 1px solid #dee2e6; }
            .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 12px 0; }
            .stat-card { background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 10px; padding: 12px; text-align: center; }
            .stat-number { font-size: 22px; font-weight: bold; color: #ffc107; }
            /* 比較表示 */
            .compare-wrap { background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 10px; padding: 16px; margin-top: 18px; }
            .compare-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
            .compare-row img { width: 100%; height: 240px; object-fit: contain; background:#000; border-radius: 8px; }
            .compare-controls { text-align:center; margin: 8px 0 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="title-container">
                    <h1>KIRII CCTV‑YOLO (復元版)</h1>
                </div>
            </div>

            <div class="controls">
                <button class="btn btn-success" onclick="startStream()">▶️ 監視開始</button>
                <button class="btn btn-danger" onclick="stopStream()">⏹️ 監視停止</button>
            </div>

            <div id="status" class="status-info">待機中 - 監視開始ボタンをクリックしてください</div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number" id="objectCount">0</div>
                    <div>検出オブジェクト数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="streamStatus">停止中</div>
                    <div>ストリーム状態</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">192.168.0.98:18080</div>
                    <div>CCTV URL (復元)</div>
                </div>
            </div>

            <div class="video-container">
                <div class="video-section">
                    <img id="videoFrame" class="video-frame" style="display: none;" alt="CCTV YOLO Stream" />
                    <div id="noVideo" style="text-align: center; line-height: 420px; color: #6c757d; font-size: 18px;">映像はありません</div>
                </div>
            </div>

            <div class="detection-panel">
                <h3 style="margin-top:0;">🎯 リアルタイム検出結果</h3>
                <div id="detectionList"><div style="color:#6c757d; text-align:center; padding: 12px;">検出されたオブジェクトはありません</div></div>
            </div>

            <div class="compare-wrap">
                <h3 style="margin-top:0;">🔍 比較表示（5011 / 5013 / 5009）</h3>
                <div class="compare-controls">
                    <button class="btn btn-success" onclick="startCompare()">🔄 比較開始</button>
                    <button class="btn btn-danger" onclick="stopCompare()">⏹ 比較停止</button>
                </div>
                <div class="compare-row">
                    <img id="cmp5011" alt="5011" />
                    <img id="cmp5013" alt="5013" />
                    <img id="cmp5009" alt="5009" />
                </div>
            </div>
        </div>

        <script>
            let updateInterval = null;
            let isStreaming = false;
            let compareInterval = null;

            function startStream() {
                updateStatus('🎥 CCTV接続中...', 'info');
                document.getElementById('streamStatus').textContent = '接続中';
                fetch('/start_stream', {method: 'POST'})
                  .then(r => r.json())
                  .then(d => {
                    if (d.success) {
                      updateStatus('✅ YOLO監視開始', 'success');
                      document.getElementById('streamStatus').textContent = '監視中';
                      isStreaming = true;
                      if (updateInterval) clearInterval(updateInterval);
                      updateInterval = setInterval(updateFrame, 200);
                    } else {
                      updateStatus('❌ 監視開始失敗', 'error');
                      document.getElementById('streamStatus').textContent = 'エラー';
                    }
                  });
            }

            function stopStream() {
                if (updateInterval) { clearInterval(updateInterval); updateInterval = null; }
                isStreaming = false;
                fetch('/stop_stream', {method: 'POST'})
                  .then(() => {
                    updateStatus('⏹️ 監視停止', 'info');
                    document.getElementById('streamStatus').textContent = '停止中';
                    document.getElementById('videoFrame').style.display = 'none';
                    document.getElementById('noVideo').style.display = 'block';
                    document.getElementById('objectCount').textContent = '0';
                    document.getElementById('detectionList').innerHTML = '<div style="color:#6c757d; text-align:center; padding:12px;">検出されたオブジェクトはありません</div>';
                  });
            }

            function updateFrame() {
                if (!isStreaming) return;
                fetch('/get_frame')
                  .then(r => r.json())
                  .then(data => {
                    if (data.success && data.frame) {
                      const img = document.getElementById('videoFrame');
                      img.src = 'data:image/jpeg;base64,' + data.frame;
                      img.style.display = 'block';
                      document.getElementById('noVideo').style.display = 'none';
                      updateDetections(data.detections || []);
                      document.getElementById('objectCount').textContent = (data.detections || []).length;
                      updateStatus('✅ 監視中 - ' + new Date().toLocaleTimeString(), 'success');
                    }
                  })
                  .catch(() => {});
            }

            function updateDetections(dets) {
                const el = document.getElementById('detectionList');
                if (dets && dets.length) {
                    el.innerHTML = dets.map(det => `<div class="detection-item"><span><strong>${det.class}</strong></span><span>${(det.confidence*100).toFixed(1)}%</span></div>`).join('');
                } else {
                    el.innerHTML = '<div style="color:#6c757d; text-align:center; padding:12px;">検出されたオブジェクトはありません</div>';
                }
            }

            function updateStatus(message, type) {
                const s = document.getElementById('status');
                s.textContent = message;
                s.className = 'status-info ' + type;
            }

            function startCompare() {
                if (compareInterval) clearInterval(compareInterval);
                compareInterval = setInterval(updateCompare, 400);
                updateCompare();
            }

            function stopCompare() {
                if (compareInterval) { clearInterval(compareInterval); compareInterval = null; }
                document.getElementById('cmp5011').removeAttribute('src');
                document.getElementById('cmp5013').removeAttribute('src');
                document.getElementById('cmp5009').removeAttribute('src');
            }

            function updateCompare() {
                fetch('/get_compare_frames')
                  .then(r => r.json())
                  .then(data => {
                    if (data.ch5011) {
                        document.getElementById('cmp5011').src = 'data:image/jpeg;base64,' + data.ch5011;
                    }
                    if (data.ch5013) {
                        document.getElementById('cmp5013').src = 'data:image/jpeg;base64,' + data.ch5013;
                    }
                    if (data.ch5009) {
                        document.getElementById('cmp5009').src = 'data:image/jpeg;base64,' + data.ch5009;
                    }
                  })
                  .catch(() => {});
            }
        </script>
    </body>
    </html>
    ''')

@app.route('/start_stream', methods=['POST'])
def start_stream():
    """ストリーム開始"""
    try:
        success = cctv_system.start_cctv_stream()
        return {'success': success}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    """ストリーム停止"""
    cctv_system.stop_stream()
    return {'success': True}

@app.route('/get_frame')
def get_frame():
    """フレーム取得"""
    if cctv_system.current_frame:
        return {
            'success': True, 
            'frame': cctv_system.current_frame,
            'detections': cctv_system.detection_results
        }
    else:
        return {'success': False}

@app.route('/get_compare_frames')
def get_compare_frames():
    """5011/5013/5009 を比較表示用にまとめて返す"""
    result = {'success': True}

    # 自身（5011）
    if cctv_system.current_frame:
        result['ch5011'] = cctv_system.current_frame

    def fetch_other(port: int):
        try:
            resp = requests.get(f'http://127.0.0.1:{port}/get_frame', timeout=1.5)
            if resp.status_code == 200:
                j = resp.json()
                if j.get('success') and j.get('frame'):
                    return j['frame']
        except Exception:
            return None
        return None

    # 他ポート（起動していない場合はNoneのまま）
    frame_5013 = fetch_other(5013)
    if frame_5013:
        result['ch5013'] = frame_5013
    frame_5009 = fetch_other(5009)
    if frame_5009:
        result['ch5009'] = frame_5009

    return result

if __name__ == '__main__':
    print("🏭 KIRII CCTV-YOLO監視システム (復元版)")
    print("📺 CCTV: 192.168.0.98:18080 (動作確認済み)")
    print("🤖 YOLO11: 物体検出有効")
    print("🌐 アクセス: http://localhost:5011")
    app.run(host='0.0.0.0', port=5011, debug=False) 