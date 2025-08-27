#!/usr/bin/env python3
"""
KIRII在庫管理Vercelプラットフォーム
QRコードからアクセスする携帯対応在庫確認システム
Googleシート連携対応
"""

from flask import Flask, render_template_string, jsonify, request
import json
from datetime import datetime
import os
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build

app = Flask(__name__)

class KiriiInventoryPlatform:
    def __init__(self):
        # Googleシート設定
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL', 'https://docs.google.com/spreadsheets/d/1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M/edit?usp=sharing')
        self.use_google_sheets = bool(self.sheet_url)
        
        # テスト用のローカルデータ（Googleシートと同じ構造）
        self.fallback_inventory = {
            1: {"code": "BD-060", "name": "泰山普通石膏板 4'x6'x12mmx 4.5mm", "quantity": 200, "updated": "2025-07-26", "location": "A-1", "category": "Merchandies", "unit": "張"},
            2: {"code": "US0503206MM2440", "name": "Stud 50mmx32mmx0.6mmx2440mm", "quantity": 200, "updated": "2025-07-26", "location": "A-2", "category": "Products", "unit": "只"},
            3: {"code": "AC-258", "name": "KIRII Corner Bead 2440mm (25pcs/bdl)(0.4mm 鋁)", "quantity": 50, "updated": "2025-07-26", "location": "B-1", "category": "Products", "unit": "個"},
            4: {"code": "AC-261", "name": "黃岩綿- 60g (6pcs/pack)", "quantity": 10, "updated": "2025-07-26", "location": "C-1", "category": "MK", "unit": "包"}
        }
        
        # Googleシート接続を初期化
        self.sheet_client = None
        self.worksheet = None
        self._init_google_sheets()
        
        print("🏭 KIRII番号ベース在庫管理プラットフォーム初期化完了")
        print("📱 携帯対応在庫確認システム")
        print("🔢 QRコード: 番号ベース（超大型マス対応）")
        if self.use_google_sheets:
            print("📊 Googleシート連携: 有効")
        else:
            print("📊 データソース: ローカル（フォールバック）")

    def _init_google_sheets(self):
        """Googleシート接続を初期化"""
        try:
            # シートIDを抽出
            self.sheet_id = self._extract_sheet_id_from_url(self.sheet_url)
            if not self.sheet_id:
                print("⚠️ 無効なシートURL")
                self.use_google_sheets = False
                return
                
            # API Key設定
            self.api_key = "AIzaSyARbSHGDK-dCkmuP8ys7E2-G-treb3ZYIw"
            
            # サービスアカウント認証（将来の拡張用）
            if os.path.exists('google_service_account.json'):
                try:
                    credentials = service_account.Credentials.from_service_account_file(
                        'google_service_account.json',
                        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                    )
                    self.sheets_service = build('sheets', 'v4', credentials=credentials)
                    print("✅ サービスアカウント認証成功")
                except Exception as e:
                    print(f"⚠️ サービスアカウント認証失敗: {e}")
                    print("📋 API Key方式を使用します")
            
            # Google Sheets API接続テスト
            test_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Sheet1?key={self.api_key}"
            test_response = requests.get(test_url, timeout=10)
            
            if test_response.status_code == 200:
                print(f"✅ Googleシート接続成功 (ID: {self.sheet_id[:8]}...)")
                self.use_google_sheets = True
            else:
                print(f"❌ Googleシート接続失敗: {test_response.status_code}")
                print("📋 フォールバックモードで動作")
                self.use_google_sheets = False
                
        except Exception as e:
            print(f"❌ Googleシート初期化エラー: {e}")
            print("📋 フォールバックモードで動作")
            self.use_google_sheets = False
    
    def _extract_sheet_id_from_url(self, url):
        """GoogleシートのURLからシートIDを抽出"""
        try:
            if '/spreadsheets/d/' in url:
                return url.split('/spreadsheets/d/')[1].split('/')[0]
        except:
            pass
        return None

    def get_inventory_data(self):
        """在庫データを取得（Googleシートまたはローカル）"""
        if self.use_google_sheets and hasattr(self, 'api_key'):
            try:
                return self._fetch_from_google_sheets()
            except Exception as e:
                print(f"⚠️ Googleシートからのデータ取得エラー: {e}")
                print("📋 フォールバックデータを使用します")
                
        return self.fallback_inventory

    def _fetch_from_google_sheets(self):
        """Googleシートからデータを取得（API Key方式）"""
        import requests
        import time
        
        try:
            # Google Sheets API URL（700行対応・明示的範囲指定）
            api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Sheet1!A1:I1000?key={self.api_key}"
            
            # Google Sheets APIからデータを取得（キャッシュ無効化ヘッダー付き）
            headers = {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            response = requests.get(api_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            values = data.get('values', [])
            
            if not values:
                print("⚠️ Googleシートにデータがありません")
                return self.fallback_inventory
            
            # ヘッダー行を取得
            headers = values[0] if values else []
            
            # データを辞書形式に変換
            inventory_data = {}
            for row in values[1:]:  # ヘッダー行をスキップ
                if len(row) >= 3:  # 最低限のデータがある場合
                    try:
                        # 番号（A列）
                        number = int(row[0]) if row[0] else 0
                        if number > 0:
                            inventory_data[number] = {
                                'code': row[2] if len(row) > 2 else '',  # C列: 製品コード
                                'name': row[6] if len(row) > 6 else '',  # G列: 製品名
                                'location': row[7] if len(row) > 7 else '',  # H列: 保管場所
                                'quantity': int(row[8]) if len(row) > 8 and str(row[8]).isdigit() else 0,  # I列: 在庫数量
                                'unit': row[9] if len(row) > 9 else '',  # J列: 数量の単位
                                'updated': row[10] if len(row) > 10 else datetime.now().strftime('%Y-%m-%d'),  # K列: 最終更新
                                'category': row[3] if len(row) > 3 else ''  # D列: カテゴリ
                            }
                    except (ValueError, IndexError) as e:
                        print(f"⚠️ 行データ処理エラー: {e}")
                        continue
            
            if inventory_data:
                print(f"✅ Googleシートから{len(inventory_data)}件のデータを取得")
                return inventory_data
            else:
                print("⚠️ 有効なデータが見つかりませんでした")
                return self.fallback_inventory
                
        except requests.RequestException as e:
            print(f"❌ Googleシート API リクエストエラー: {e}")
            print(f"📋 API URL: {api_url}")
            print(f"📋 レスポンスコード: {getattr(e.response, 'status_code', 'N/A')}")
            print(f"📋 レスポンス内容: {getattr(e.response, 'text', 'N/A')}")
            return self.fallback_inventory
        except Exception as e:
            print(f"❌ データ処理エラー: {e}")
            print(f"📋 エラータイプ: {type(e).__name__}")
            return self.fallback_inventory

    @property
    def inventory_mapping(self):
        """在庫データのプロパティ"""
        return self.get_inventory_data()

    @property 
    def code_to_number(self):
        """製品コードから番号への逆引き"""
        inventory = self.get_inventory_data()
        return {v["code"]: k for k, v in inventory.items()}

platform = KiriiInventoryPlatform()

@app.route('/')
def index():
    """メインページ - QRスキャン機能付き"""
    # Googleシートから最新の在庫データを取得
    inventory_data = platform.get_inventory_data()
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta http-equiv="Permissions-Policy" content="camera=*">
    <title>KHK-AI-QR-SCAN</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            min-height: 100vh;
            color: #333;
            padding: 20px;
        }
        
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .logo {
            height: 27px;
            width: auto;
            margin-right: 15px;
        }
        
        .header-title {
            font-size: 1.4em;
            font-weight: bold;
            color: #333;
        }
        

        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .qr-scanner {
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .scan-button {
            background: #28a745;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        
        .scan-button:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        
        .manual-input {
            margin-top: 15px;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
        }
        
        .code-input {
            flex: 1;
            padding: 12px;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            font-size: 1em;
            background: white;
            color: #333;
        }
        
        .code-input:focus {
            border-color: #007bff;
            outline: none;
        }
        
        .search-button {
            background: #007bff;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 10px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .search-button:hover {
            background: #0056b3;
            transform: translateY(-2px);
        }
        
        .camera-notice {
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 15px;
            padding: 10px;
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
        }
        
        .inventory-list {
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 15px;
            padding: 25px;
        }
        
        .list-title {
            color: #333;
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .product-card {
            background: white;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .product-card:hover {
            transform: translateY(-2px);
            border-color: #007bff;
            box-shadow: 0 5px 15px rgba(0,123,255,0.2);
        }
        
        .product-code {
            color: #28a745;
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 8px;
        }
        
        .product-name {
            color: #333;
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .product-details {
            color: #6c757d;
            font-size: 0.95em;
        }
        
        .footer {
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
        }
        
        #qr-reader {
            width: 100%;
            max-width: 400px;
            margin: 0 auto;
            display: none;
        }
        
        .qr-active #qr-reader {
            display: block;
        }
        
        .qr-active .scan-button {
            background: #dc3545;
        }
        
        .qr-active .scan-button:hover {
            background: #c82333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="/static/logo" class="logo" alt="KIRII Logo">
            <div>
                <div class="header-title">KHK-AI-QR-SCAN</div>
            </div>
        </div>
        
        <div class="qr-scanner" id="qr-scanner">
            <button class="scan-button" id="scan-btn" onclick="toggleQRScan()">📱 QR Code Scan / QR碼掃描</button>
            <div id="qr-reader"></div>
            <div class="manual-input">
                <div class="input-group">
                    <input type="text" id="productCode" class="code-input" placeholder="Manual Input Number (1, 2, 3, 4) / 手動輸入編號 (1, 2, 3, 4)">
                    <button class="search-button" onclick="searchProduct()">Search / 搜尋</button>
                </div>
            </div>
        </div>
        
        <div class="inventory-list">
            <div class="list-title">📦 Inventory List / 庫存清單</div>
            {% for number, product in inventory_data.items() %}
            <div class="product-card" onclick="showProductDetail({{ number }})">
                <div class="product-code">No. / 編號: {{ number }} | {{ product.code }}</div>
                <div class="product-name">{{ product.name }}</div>
                <div class="product-details">
                    📍 {{ product.location }} | 📊 {{ product.quantity }}{{ product.unit }} | 🏷️ {{ product.category }}
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="footer">
            KHK-AI-QR-SCAN v2.0 | 番号ベースQRコード対応 | 📊 Googleシート連携
        </div>
    </div>
    

    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
    <script>
        let videoStream = null;
        let isScanning = false;
        let scanInterval = null;
        
        function toggleQRScan() {
            if (!isScanning) {
                startQRScan();
            } else {
                stopQRScan();
            }
        }
        
        async function startQRScan() {
            const qrReader = document.getElementById('qr-reader');
            
            // HTTPSチェック
            if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
                qrReader.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">⚠️ HTTPS Required for Camera Access / 需要HTTPS才能使用相機<br><br>Please use manual input below / 請使用下方手動輸入</div>';
                return;
            }
            
            try {
                // カメラ権限を事前確認
                const permissions = await navigator.permissions.query({name: 'camera'});
                console.log('カメラ権限状態:', permissions.state);
                
                // カメラストリーム開始
                videoStream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: { ideal: "environment" },
                        width: { ideal: 640, max: 1280 },
                        height: { ideal: 480, max: 720 }
                    }
                });
                
                // ビデオ要素作成
                const video = document.createElement('video');
                video.autoplay = true;
                video.playsInline = true;
                video.muted = true;
                video.style.width = '100%';
                video.style.height = '300px';
                video.style.objectFit = 'cover';
                video.srcObject = videoStream;
                
                // Canvas作成（QR読み取り用）
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                
                qrReader.innerHTML = '';
                qrReader.appendChild(video);
                
                // 読み取り結果表示エリア
                const resultDiv = document.createElement('div');
                resultDiv.id = 'scan-result-display';
                resultDiv.style.cssText = 'text-align: center; padding: 10px; background: rgba(0,100,0,0.1); color: green; margin-top: 10px; border-radius: 5px; display: none;';
                qrReader.appendChild(resultDiv);
                
                
                isScanning = true;
                document.getElementById('scan-btn').textContent = '⏹️ Stop / 停止';
                document.getElementById('qr-scanner').classList.add('qr-active');
                
                // QR読み取り処理（jsQRライブラリ使用）- 高速化版
                scanInterval = setInterval(() => {
                    if (video.readyState === video.HAVE_ENOUGH_DATA) {
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        
                        // jsQRでQRコード読み取り
                        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        const code = jsQR(imageData.data, imageData.width, imageData.height);
                        
                        if (code) {
                            console.log('QRコード読み取り成功:', code.data);
                            
                            // 結果表示
                            const resultDisplay = document.getElementById('scan-result-display');
                            resultDisplay.innerHTML = `✅ 読み取り成功: ${code.data}`;
                            resultDisplay.style.display = 'block';
                            
                            // 番号1-4の場合は即座に製品ページに移動（高速化）
                            if (['1', '2', '3', '4'].includes(code.data.trim())) {
                                stopQRScan();
                                // 遅延を200msに短縮（視覚的フィードバックは残す）
                                setTimeout(() => {
                                    window.location.href = '/product/' + code.data.trim();
                                }, 200);
                            } else {
                                // 無効な番号の場合は2秒後に結果を非表示（短縮）
                                setTimeout(() => {
                                    if (resultDisplay) {
                                        resultDisplay.style.display = 'none';
                                    }
                                }, 2000);
                            }
                        }
                    }
                }, 150); // 150msごとにスキャン（高速化）
                
            } catch (error) {
                console.error('カメラアクセスエラー:', error);
                let errorMsg = 'カメラにアクセスできません。';
                
                if (error.name === 'NotAllowedError') {
                    errorMsg = '📷 カメラ権限が拒否されました。<br>ブラウザ設定でカメラアクセスを許可してください。';
                } else if (error.name === 'NotFoundError') {
                    errorMsg = '📷 カメラが見つかりません。';
                } else if (error.name === 'NotSupportedError') {
                    errorMsg = '📷 お使いのブラウザはカメラをサポートしていません。';
                }
                
                qrReader.innerHTML = `<div style="text-align: center; padding: 20px; color: red;">${errorMsg}<br><br>下の手動入力をご利用ください。</div>`;
            }
        }
        
        function stopQRScan() {
            if (scanInterval) {
                clearInterval(scanInterval);
                scanInterval = null;
            }
            
            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
                videoStream = null;
            }
            
            isScanning = false;
            document.getElementById('qr-reader').innerHTML = '';
            document.getElementById('scan-btn').textContent = '📱 QR Code Scan / QR碼掃描';
            document.getElementById('qr-scanner').classList.remove('qr-active');
        }
        
        function searchProduct() {
            const code = document.getElementById('productCode').value.trim();
            if (code) {
                window.location.href = '/product/' + code;
            } else {
                alert('Please enter a number / 請輸入編號');
            }
        }
        
        function showProductDetail(number) {
            window.location.href = '/product/' + number;
        }
        
        document.getElementById('productCode').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchProduct();
            }
        });
        
        // ページ読み込み時にURLパラメータをチェックしてカメラ自動起動
        window.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('scan') === 'active') {
                // URLからパラメータを削除（履歴をきれいに保つ）
                const newUrl = window.location.pathname;
                window.history.replaceState({}, document.title, newUrl);
                
                // カメラを自動起動（少し遅延を入れて確実に起動）
                setTimeout(() => {
                    if (!isScanning) {
                        startQRScan();
                    }
                }, 300);
            }
        });
    </script>
</body>
</html>
    ''', 
    inventory_data=inventory_data
    )

@app.route('/product/<int:product_number>')
def product_detail(product_number):
    """製品詳細ページ - QRコード番号からアクセス"""
    # Googleシートから最新の在庫データを取得
    inventory_data = platform.get_inventory_data()
    
    if product_number not in inventory_data:
        return render_template_string('''
        <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif; background: white; color: #333;">
            <h1>❌ 製品が見つかりません</h1>
            <p>番号: {{ number }}</p>
            <a href="/" style="color: #007bff;">トップページに戻る</a>
        </div>
        ''', number=product_number), 404
    
    product = inventory_data[product_number]
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 {{ product.name }} - KHK-AI-QR-SCAN</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            min-height: 100vh;
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .logo {
            height: 27px;
            width: auto;
            margin-right: 15px;
        }
        
        .back-button {
            background: #6c757d;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s ease;
        }
        
        .back-button:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }
        
        .product-card {
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            margin-top: 20px;
        }
        
        .product-number {
            font-size: 3em;
            font-weight: bold;
            color: #28a745;
            margin-bottom: 10px;
        }
        
        .product-code {
            font-family: 'Courier New', monospace;
            font-size: 1.2em;
            color: #007bff;
            margin-bottom: 20px;
        }
        
        .product-name {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
            margin-bottom: 30px;
            line-height: 1.4;
            word-wrap: break-word;
            word-break: break-all;
            overflow-wrap: break-word;
            hyphens: auto;
            max-width: 100%;
        }
        
        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto auto;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .detail-item {
            background: white;
            border: 2px solid #dee2e6;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .detail-item.factory-layout-item {
            grid-column: 1 / -1; /* 2行目は全幅 */
        }
        
        .detail-item.last-updated-item {
            grid-column: 1 / -1; /* 3行目は全幅 */
        }
        
        .detail-label {
            font-size: 0.9em;
            color: #6c757d;
            margin-bottom: 5px;
        }
        
        .detail-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
        }
        
        .quantity {
            font-size: 2em;
            color: #28a745;
        }
        
        .location-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        
        .scan-again {
            background: #28a745;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
            transition: all 0.3s ease;
        }
        
        .scan-again:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #6c757d;
            font-size: 0.8em;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
        }
        
        /* 工場配置図スタイル */
        .factory-layout {
            margin-top: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        
        .layout-title {
            font-size: 0.85em;
            color: #6c757d;
            margin-bottom: 8px;
            text-align: center;
        }
        
        .factory-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            grid-template-rows: repeat(4, 1fr);
            gap: 2px;
            max-width: 100%;
            aspect-ratio: 3/2;
            position: relative;
        }
        
        /* 工場内部の外壁境界線 */
        .factory-grid::after {
            content: '';
            position: absolute;
            top: 0;                      /* B-1行の上端に合わせる */
            left: calc(16.666% + 1px);   /* B列の左端に合わせる */
            width: calc(66.666% - 2px);  /* B-1からE-3の幅 */
            height: calc(75% - 1px);     /* B-1からB-3の高さ */
            border: 3px solid #333;
            border-radius: 4px;
            pointer-events: none;
            z-index: 1;
        }
        
        .grid-cell {
            background: #ffffff;
            border: 1px solid #dee2e6;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7em;
            font-weight: bold;
            color: #333;
            border-radius: 3px;
            min-height: 20px;
            transition: all 0.3s ease;
        }
        
        .grid-cell.entrance {
            background: #e9ecef;
            color: #6c757d;
            font-size: 0.6em;
        }
        
        .grid-cell.storage-cell {
            background: #ffffff;
            color: #333;
            cursor: pointer;
        }
        
        .grid-cell.storage-cell:hover {
            background: #e3f2fd;
            border-color: #2196f3;
        }
        
        .grid-cell.storage-cell.highlighted {
            background: #4caf50;
            color: white;
            border-color: #388e3c;
            box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
            transform: scale(1.05);
        }
        
        .grid-cell.empty {
            background: transparent;
            border: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="/static/logo" class="logo" alt="KIRII Logo">
            <button class="back-button" onclick="window.location.href='/?scan=active'">← Back / 返回</button>
        </div>
        
        <div class="product-card">
            <div class="product-number">{{ number }}</div>
            <div class="product-code">{{ product.code }}</div>
            <div class="product-name">{{ product.name }}</div>
            
            <div class="details-grid">
                <div class="detail-item">
                    <div class="detail-label">📦 Stock Quantity / 庫存數量</div>
                    <div class="detail-value quantity">{{ product.quantity }}{{ product.unit }}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">📍 Storage Location / 儲存位置</div>
                    <div class="detail-value location-value">{{ product.location }}</div>
                </div>
                <div class="detail-item factory-layout-item">
                    <div class="detail-label">🏭 Factory Layout / 工廠配置圖</div>
                    <div class="factory-layout">
                        <div class="factory-grid">
                            <div class="grid-cell entrance">門口</div>
                            <div class="grid-cell storage-cell" data-location="B-1">B-1</div>
                            <div class="grid-cell storage-cell" data-location="C-1">C-1</div>
                            <div class="grid-cell storage-cell" data-location="D-1">D-1</div>
                            <div class="grid-cell storage-cell" data-location="E-1">E-1</div>
                            <div class="grid-cell storage-cell" data-location="A-9">A-9</div>
                            
                            <div class="grid-cell storage-cell" data-location="A-1">A-1</div>
                            <div class="grid-cell storage-cell" data-location="B-2">B-2</div>
                            <div class="grid-cell storage-cell" data-location="C-2">C-2</div>
                            <div class="grid-cell storage-cell" data-location="D-2">D-2</div>
                            <div class="grid-cell storage-cell" data-location="E-2">E-2</div>
                            <div class="grid-cell storage-cell" data-location="A-8">A-8</div>
                            
                            <div class="grid-cell storage-cell" data-location="A-2">A-2</div>
                            <div class="grid-cell storage-cell" data-location="B-3">B-3</div>
                            <div class="grid-cell storage-cell" data-location="C-3">C-3</div>
                            <div class="grid-cell storage-cell" data-location="D-3">D-3</div>
                            <div class="grid-cell storage-cell" data-location="E-3">E-3</div>
                            <div class="grid-cell storage-cell" data-location="A-7">A-7</div>
                            
                            <div class="grid-cell storage-cell" data-location="A-3">A-3</div>
                            <div class="grid-cell storage-cell" data-location="A-4">A-4</div>
                            <div class="grid-cell storage-cell" data-location="A-5">A-5</div>
                            <div class="grid-cell storage-cell" data-location="A-6">A-6</div>
                            <div class="grid-cell empty"></div>
                            <div class="grid-cell empty"></div>
                        </div>
                    </div>
                </div>
                <div class="detail-item last-updated-item">
                    <div class="detail-label">📅 Last Updated / 最後更新</div>
                    <div class="detail-value">{{ product.updated }}</div>
                </div>
            </div>
            
            <button class="scan-again" onclick="window.location.href='/'">📱 Scan Other Products / 掃描其他產品</button>
        </div>
        
        <div class="footer">
            KHK-AI-QR-SCAN | QR Inventory Management System / QR碼庫存管理系統
        </div>
    </div>
    
    <script>
        // 工場配置図で該当位置をハイライト
        document.addEventListener('DOMContentLoaded', function() {
            const currentLocation = '{{ product.location }}';
            const storageCells = document.querySelectorAll('.storage-cell');
            
            storageCells.forEach(cell => {
                if (cell.dataset.location === currentLocation) {
                    cell.classList.add('highlighted');
                }
            });
        });
    </script>
</body>
</html>
    ''', 
    product=product, 
    number=product_number
    )

@app.route('/api/inventory')
def api_inventory():
    """在庫データAPI"""
    inventory_data = platform.get_inventory_data()
    return jsonify(inventory_data)

@app.route('/api/product/<int:product_number>')
def api_product(product_number):
    """製品詳細API"""
    inventory_data = platform.get_inventory_data()
    
    if product_number not in inventory_data:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'number': product_number,
        'product': inventory_data[product_number]
    })

@app.route('/static/logo')
def get_logo():
    """KIRIIロゴを提供"""
    try:
        # Base64データファイルから読み込み
        if os.path.exists('logo_base64.txt'):
            with open('logo_base64.txt', 'r') as f:
                base64_data = f.read().strip()
            
            # data:image/png;base64, の部分を除去してBase64データのみ取得
            if base64_data.startswith('data:image/png;base64,'):
                base64_data = base64_data.replace('data:image/png;base64,', '')
            
            import base64
            logo_data = base64.b64decode(base64_data)
            return logo_data, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        print(f"Base64ロゴ読み込みエラー: {e}")
    
    try:
        # Base64ファイルが見つからない場合は、PNGファイルを試す
        if os.path.exists('KIRII-logo-3.png'):
            with open('KIRII-logo-3.png', 'rb') as f:
                logo_data = f.read()
            return logo_data, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        print(f"PNGロゴ読み込みエラー: {e}")
    
    # どちらも見つからない場合は、デフォルトのテキストロゴを返す
    print("ロゴファイルが見つかりません。テキストロゴを使用します。")
    return "KIRII", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    print("🏭 KIRII在庫管理Vercelプラットフォーム起動")
    print("📱 携帯対応在庫確認システム")
    print("🌐 アクセス: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
