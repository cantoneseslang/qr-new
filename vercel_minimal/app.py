from flask import Flask, request, Response, jsonify
import requests
import os
from datetime import datetime
import base64
import threading
import time
from flask import stream_with_context

app = Flask(__name__)

# ローカル監視システムのIPアドレス
LOCAL_MONITOR_URL = "http://192.168.0.119:5013"

# 受信した画像の保存
received_image = None
received_image_timestamp = None
image_lock = threading.Lock()

@app.route('/')
def index():
    """メインページ - 監視システムの状態表示"""
    return jsonify({
        "status": "online",
        "service": "KHK AI Monitor - Vercel Production",
        "local_system": LOCAL_MONITOR_URL,
        "timestamp": datetime.now().isoformat(),
        "note": "画像は /vercel/stream エンドポイントで取得してください",
        "endpoints": {
            "stream": "/vercel/stream",
            "frame": "/vercel/frame",
            "receive": "/receive_image"
        }
    })

@app.route('/receive_image', methods=['POST'])
def receive_image():
    """ローカル監視システムから画像を受信"""
    global received_image, received_image_timestamp
    
    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({"error": "画像データがありません"}), 400
        
        # base64デコードして画像データを保存
        image_data = base64.b64decode(data['image'])
        timestamp = data.get('timestamp', time.time())
        
        with image_lock:
            received_image = image_data
            received_image_timestamp = timestamp
        
        print(f"✅ 画像受信成功: {len(image_data)} bytes, timestamp: {timestamp}")
        return jsonify({"success": True, "received_bytes": len(image_data)})
        
    except Exception as e:
        print(f"❌ 画像受信エラー: {str(e)}")
        return jsonify({"error": f"受信エラー: {str(e)}"}), 500

@app.route('/vercel/stream')
def vercel_stream():
    """Vercelでの画像ストリーミング（受信した画像を配信）"""
    try:
        def generate_vercel_stream():
            while True:
                with image_lock:
                    if received_image:
                        # 受信した画像をストリーミング
                        yield f"--boundary\r\n"
                        yield f"Content-Type: image/jpeg\r\n"
                        yield f"Content-Length: {len(received_image)}\r\n\r\n"
                        yield received_image
                        yield "\r\n"
                
                # 0.5秒間隔
                time.sleep(0.5)
        
        return Response(
            stream_with_context(generate_vercel_stream()),
            content_type='multipart/x-mixed-replace; boundary=boundary',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        return jsonify({"error": f"ストリーミングエラー: {str(e)}"}), 500

@app.route('/vercel/frame')
def vercel_single_frame():
    """Vercelでの単発画像取得（受信した画像を返す）"""
    try:
        with image_lock:
            if received_image:
                return Response(
                    received_image,
                    content_type='image/jpeg',
                    headers={
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Access-Control-Allow-Origin': '*'
                    }
                )
        
        return jsonify({"error": "画像が受信されていません"}), 404
    except Exception as e:
        return jsonify({"error": f"エラー: {str(e)}"}), 500

@app.route('/status')
def status():
    """ローカル監視システムの状態確認"""
    try:
        response = requests.get(f"{LOCAL_MONITOR_URL}/", timeout=5)
        return jsonify({
            "local_system_status": "online" if response.status_code == 200 else "offline",
            "local_url": LOCAL_MONITOR_URL,
            "vercel_status": "online",
            "vercel_endpoints": ["/vercel/stream", "/vercel/frame", "/receive_image"],
            "received_image": received_image is not None,
            "last_image_timestamp": received_image_timestamp,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "local_system_status": "connection_error",
            "error": str(e),
            "vercel_status": "online",
            "vercel_endpoints": ["/vercel/stream", "/vercel/frame", "/receive_image"],
            "received_image": received_image is not None,
            "last_image_timestamp": received_image_timestamp,
            "timestamp": datetime.now().isoformat()
        })

@app.route('/health')
def health():
    """ヘルスチェック"""
    return jsonify({
        "status": "healthy",
        "service": "KHK AI Monitor - Vercel Production",
        "vercel_endpoints": ["/vercel/stream", "/vercel/frame", "/receive_image"],
        "received_image": received_image is not None,
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(debug=False)
