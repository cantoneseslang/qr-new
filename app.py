#!/usr/bin/env python3
"""
KIRII在庫管理Vercelプラットフォーム
QRコードからアクセスする携帯対応在庫確認システム
"""

from flask import Flask, render_template_string, jsonify, request
import json
from datetime import datetime
import os

app = Flask(__name__)

class KiriiInventoryPlatform:
    def __init__(self):
        # 番号ベースの在庫データ（Googleシートマッピング対応）
        self.inventory_mapping = {
            1: {"code": "BD-060", "name": "泰山普通石膏板 4'x6'x12mmx 4.5mm", "quantity": 100, "updated": "2025-07-26", "location": "倉庫A-1", "category": "建材", "unit": "枚"},
            2: {"code": "US0503206MM2440", "name": "Stud 50mmx32mmx0.6mmx2440mm", "quantity": 200, "updated": "2025-07-26", "location": "倉庫A-2", "category": "建材", "unit": "本"},
            3: {"code": "AC-258", "name": "KIRII Corner Bead 2440mm (25pcs/bdl)(0.4mm 鋁)", "quantity": 50, "updated": "2025-07-26", "location": "倉庫B-1", "category": "金具", "unit": "束"},
            4: {"code": "AC-261", "name": "黃岩綿- 60g (6pcs/pack)", "quantity": 10, "updated": "2025-07-26", "location": "倉庫C-1", "category": "断熱材", "unit": "パック"}
        }
        
        # 番号から製品コードへの逆引き用
        self.code_to_number = {v["code"]: k for k, v in self.inventory_mapping.items()}
        
        print("🏭 KIRII番号ベース在庫管理プラットフォーム初期化完了")
        print("📱 携帯対応在庫確認システム")
        print("🔢 QRコード: 番号ベース（超大型マス対応）")

platform = KiriiInventoryPlatform()

@app.route('/')
def index():
    """メインページ - QRスキャン機能付き"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏭 KIRII在庫管理システム</title>
    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
            padding: 20px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .title {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .subtitle {
            opacity: 0.9;
            font-size: 0.9em;
        }
        
        .qr-scanner {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
                        margin-bottom: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        
        .scan-button {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
                        font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-bottom: 15px;
            transition: transform 0.3s ease;
        }
        
        .scan-button:hover {
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
            border: none;
            border-radius: 10px;
            font-size: 1em;
            background: rgba(255,255,255,0.9);
            color: #333;
        }
        
        .search-button {
            background: linear-gradient(45deg, #2196F3, #1976D2);
            color: white;
                        border: none; 
            padding: 12px 20px;
            border-radius: 10px;
            font-weight: bold;
                        cursor: pointer; 
        }
        
        .inventory-list {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        
        .list-title {
            font-size: 1.2em;
                        font-weight: bold;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .product-card {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
                        padding: 15px; 
            margin-bottom: 10px;
                        cursor: pointer;
            transition: all 0.3s ease;
                    }
        
        .product-card:hover {
            background: rgba(255,255,255,0.2);
            transform: translateY(-2px);
                    }
        
        .product-code {
            font-family: 'Courier New', monospace;
            font-weight: bold;
            color: #FFE082;
            margin-bottom: 5px;
                    }
        
        .product-name {
            font-size: 1.1em;
            margin-bottom: 5px;
                    }
        
        .product-details {
            font-size: 0.9em;
            opacity: 0.8;
                    }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            opacity: 0.7;
            font-size: 0.8em;
                    }
        
        .camera-notice {
            background: rgba(255,193,7,0.2);
            border: 1px solid #ffc107;
            border-radius: 10px;
                        padding: 15px;
            margin-bottom: 15px;
            text-align: center;
            font-size: 0.9em;
                    }
                </style>
            </head>
            <body>
    <div class="container">
                <div class="header">
            <div class="title">🏭 KIRII在庫管理</div>
            <div class="subtitle">📱 QRコードスキャン対応 | {{ current_time }}</div>
                </div>
                
        <div class="qr-scanner">
            <div class="camera-notice">
                📱 カメラが使用できない場合は、下の手動入力をご利用ください
            </div>
            <button class="scan-button" onclick="startQRScan()">📱 QRコードをスキャン</button>
            <div class="manual-input">
                <div class="input-group">
                    <input type="text" id="productCode" class="code-input" placeholder="番号を手動入力 (1, 2, 3, 4)">
                    <button class="search-button" onclick="searchProduct()">検索</button>
                </div>
            </div>
                </div>
                
        <div class="inventory-list">
            <div class="list-title">📦 在庫一覧</div>
            {% for number, product in inventory_data.items() %}
            <div class="product-card" onclick="showProductDetail({{ number }})">
                <div class="product-code">番号: {{ number }} | {{ product.code }}</div>
                <div class="product-name">{{ product.name }}</div>
                <div class="product-details">
                    📍 {{ product.location }} | 📊 {{ product.quantity }}{{ product.unit }} | 🏷️ {{ product.category }}
                </div>
                        </div>
            {% endfor %}
                    </div>
                    
        <div class="footer">
            🏭 KIRII在庫管理システム v2.0 | 番号ベースQRコード対応
                    </div>
                </div>
                
                <script>
        async function startQRScan() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    video: { 
                        facingMode: 'environment' // 背面カメラを優先
                    } 
                });
                
                const video = document.createElement('video');
                video.srcObject = stream;
                video.autoplay = true;
                video.playsInline = true;
                video.style.width = '100%';
                video.style.height = '300px';
                video.style.objectFit = 'cover';
                video.style.borderRadius = '10px';
                
                // キャンバスを作成（QRコード読み取り用）
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                
                // スキャナーUIを作成
                const scannerDiv = document.createElement('div');
                scannerDiv.style.position = 'fixed';
                scannerDiv.style.top = '0';
                scannerDiv.style.left = '0';
                scannerDiv.style.width = '100%';
                scannerDiv.style.height = '100%';
                scannerDiv.style.backgroundColor = 'rgba(0,0,0,0.9)';
                scannerDiv.style.zIndex = '9999';
                scannerDiv.style.display = 'flex';
                scannerDiv.style.flexDirection = 'column';
                scannerDiv.style.alignItems = 'center';
                scannerDiv.style.justifyContent = 'center';
                scannerDiv.style.padding = '20px';
                    
                const title = document.createElement('h2');
                title.textContent = '📱 QRコードをスキャン';
                title.style.color = 'white';
                title.style.marginBottom = '20px';
                
                const statusDiv = document.createElement('div');
                statusDiv.style.color = '#4CAF50';
                statusDiv.style.marginBottom = '10px';
                statusDiv.style.fontSize = '14px';
                statusDiv.textContent = '🔍 QRコードを画面に映してください';
                
                const closeBtn = document.createElement('button');
                closeBtn.textContent = '✕ 閉じる';
                closeBtn.style.position = 'absolute';
                closeBtn.style.top = '20px';
                closeBtn.style.right = '20px';
                closeBtn.style.padding = '10px 20px';
                closeBtn.style.backgroundColor = '#ff6b6b';
                closeBtn.style.color = 'white';
                closeBtn.style.border = 'none';
                closeBtn.style.borderRadius = '5px';
                closeBtn.style.fontSize = '16px';
                
                let isScanning = true;
                
                closeBtn.onclick = () => {
                    isScanning = false;
                    stream.getTracks().forEach(track => track.stop());
                    document.body.removeChild(scannerDiv);
                };
                
                // QRコードスキャン機能
                function scanQRCode() {
                    if (!isScanning) return;
                    
                    if (video.readyState === video.HAVE_ENOUGH_DATA) {
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        
                        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        
                        // jsQRライブラリでQRコード読み取り
                        const code = jsQR(imageData.data, imageData.width, imageData.height);
                        
                        if (code) {
                            statusDiv.textContent = '✅ QRコード検出！';
                            statusDiv.style.color = '#4CAF50';
                            
                            // QRコードデータを取得（番号ベース）
                            const qrData = code.data.trim();
                            let productNumber = '';
                            
                            // 数字のみ（番号）の場合
                            if (qrData.match(/^\\d+$/)) {
                                productNumber = parseInt(qrData);
                            }
                            // URLの場合は製品コードを抽出（旧形式対応）
                            else {
                                const urlMatch = qrData.match(/\\/product\\/([^\\/\\?]+)/);
                                if (urlMatch) {
                                    // 製品コードから番号に変換
                                    const productCode = urlMatch[1];
                                    // ここで製品コードから番号を逆引き
                                    const codeToNumber = {
                                        'BD-060': 1,
                                        'US0503206MM2440': 2,
                                        'AC-258': 3,
                                        'AC-261': 4
                                    };
                                    productNumber = codeToNumber[productCode];
                                }
                            }
                            
                            if (productNumber) {
                                isScanning = false;
                                stream.getTracks().forEach(track => track.stop());
                                document.body.removeChild(scannerDiv);
                                window.location.href = '/product/' + productNumber;
                                return;
                            } else {
                                statusDiv.textContent = '❌ 無効なQRコード';
                                statusDiv.style.color = '#ff6b6b';
                            }
                        } else {
                            statusDiv.textContent = '🔍 QRコードを画面に映してください';
                            statusDiv.style.color = '#4CAF50';
                    }
                    }
                    
                    setTimeout(scanQRCode, 100); // 100msごとにスキャン
                }
                
                const manualInput = document.createElement('div');
                manualInput.style.marginTop = '20px';
                manualInput.style.textAlign = 'center';
                
                const manualText = document.createElement('p');
                manualText.textContent = 'または手動で入力:';
                manualText.style.color = 'white';
                manualText.style.marginBottom = '10px';
                
                const input = document.createElement('input');
                input.type = 'text';
                input.placeholder = '番号を手動入力';
                input.style.padding = '12px';
                input.style.fontSize = '16px';
                input.style.borderRadius = '5px';
                input.style.border = '1px solid #ccc';
                input.style.marginRight = '10px';
                input.style.width = '200px';
                
                const submitBtn = document.createElement('button');
                submitBtn.textContent = '検索';
                submitBtn.style.padding = '12px 20px';
                submitBtn.style.backgroundColor = '#4CAF50';
                submitBtn.style.color = 'white';
                submitBtn.style.border = 'none';
                submitBtn.style.borderRadius = '5px';
                submitBtn.style.fontSize = '16px';
                submitBtn.onclick = () => {
                    const code = input.value.trim();
                    if (code) {
                        isScanning = false;
                        stream.getTracks().forEach(track => track.stop());
                        document.body.removeChild(scannerDiv);
                        window.location.href = '/product/' + code;
                            }
                };
                
                // エンターキーでも検索
                input.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        submitBtn.click();
                    }
                });
                
                scannerDiv.appendChild(title);
                scannerDiv.appendChild(statusDiv);
                scannerDiv.appendChild(closeBtn);
                scannerDiv.appendChild(video);
                scannerDiv.appendChild(manualInput);
                manualInput.appendChild(manualText);
                manualInput.appendChild(input);
                manualInput.appendChild(submitBtn);
                
                document.body.appendChild(scannerDiv);
                
                // ビデオが再生開始したらスキャン開始
                video.addEventListener('playing', () => {
                    scanQRCode();
                });
                
            } catch (error) {
                console.error('カメラアクセスエラー:', error);
                
                // カメラアクセスが失敗した場合の改善されたフォールバック
                alert('📱 カメラアクセスができませんでした\\n\\n💡 解決方法:\\n1. ブラウザでカメラ許可を確認\\n2. HTTPSが必要な場合があります\\n3. 下の手動入力をご利用ください\\n\\n対応番号: 1, 2, 3, 4');
                
                // 手動入力フィールドにフォーカス
                const manualInput = document.getElementById('productCode');
                if (manualInput) {
                    manualInput.focus();
                    manualInput.style.border = '2px solid #4CAF50';
                    manualInput.style.animation = 'pulse 1s infinite';
                }
            }
                    }
                    
        function searchProduct() {
            const code = document.getElementById('productCode').value.trim();
            if (code) {
                window.location.href = '/product/' + code;
                        } else {
                alert('番号を入力してください');
                        }
                    }
                    
        function showProductDetail(number) {
            window.location.href = '/product/' + number;
        }
        
        // エンターキーでの検索
        document.getElementById('productCode').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchProduct();
            }
        });
                </script>
            </body>
            </html>
    ''', 
    inventory_data=platform.inventory_mapping,
    current_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
    product_codes=list(platform.inventory_mapping.keys())
    )

@app.route('/product/<int:product_number>')
def product_detail(product_number):
    """製品詳細ページ - QRコード番号からアクセス"""
    if product_number not in platform.inventory_mapping:
        return render_template_string('''
        <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
            <h1>❌ 製品が見つかりません</h1>
            <p>番号: {{ number }}</p>
            <a href="/" style="color: blue;">トップページに戻る</a>
        </div>
        ''', number=product_number), 404
    
    product = platform.inventory_mapping[product_number]
    
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 {{ product.name }} - KIRII在庫</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .back-button {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            margin-bottom: 20px;
            cursor: pointer;
            font-size: 1em;
        }
        
        .product-card {
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 30px;
            backdrop-filter: blur(10px);
            text-align: center;
        }
        
        .product-number {
            font-size: 3em;
            font-weight: bold;
            color: #FFE082;
            margin-bottom: 10px;
        }
        
        .product-code {
            font-family: 'Courier New', monospace;
            font-size: 1.2em;
            color: #B39DDB;
            margin-bottom: 20px;
        }
        
        .product-name {
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 30px;
            line-height: 1.4;
        }
        
        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .detail-item {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .detail-label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-bottom: 5px;
        }
        
        .detail-value {
            font-size: 1.2em;
            font-weight: bold;
        }
        
        .quantity {
            font-size: 2em;
            color: #4CAF50;
        }
        
        .scan-again {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            opacity: 0.7;
            font-size: 0.8em;
        }
    </style>
</head>
<body>
    <div class="container">
        <button class="back-button" onclick="window.location.href='/'">← 戻る</button>
        
        <div class="product-card">
            <div class="product-number">{{ number }}</div>
            <div class="product-code">{{ product.code }}</div>
            <div class="product-name">{{ product.name }}</div>
            
            <div class="details-grid">
                <div class="detail-item">
                    <div class="detail-label">📦 在庫数量</div>
                    <div class="detail-value quantity">{{ product.quantity }}{{ product.unit }}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">📍 保管場所</div>
                    <div class="detail-value">{{ product.location }}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">🏷️ カテゴリ</div>
                    <div class="detail-value">{{ product.category }}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">📅 更新日</div>
                    <div class="detail-value">{{ product.updated }}</div>
                </div>
            </div>
            
            <button class="scan-again" onclick="window.location.href='/'">📱 他の製品をスキャン</button>
        </div>
        
        <div class="footer">
            🏭 KIRII在庫管理システム | 最終確認: {{ current_time }}
        </div>
    </div>
</body>
</html>
    ''', 
    product=product, 
    number=product_number,
    current_time=datetime.now().strftime('%Y-%m-%d %H:%M')
    )

@app.route('/api/inventory')
def api_inventory():
    """在庫データAPI"""
    return jsonify(platform.inventory_mapping)

@app.route('/api/product/<int:product_number>')
def api_product(product_number):
    """製品詳細API"""
    if product_number not in platform.inventory_mapping:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'number': product_number,
        'product': platform.inventory_mapping[product_number]
    })

if __name__ == '__main__':
    import sys
    
    # コマンドライン引数からポート番号を取得、デフォルトは5001
    port = 5001
    if len(sys.argv) > 1 and sys.argv[1] == '--port':
        try:
            port = int(sys.argv[2])
        except (IndexError, ValueError):
            pass
    
    print("🏭 KIRII在庫管理Vercelプラットフォーム起動")
    print("📱 携帯対応在庫確認システム")
    print(f"🌐 アクセス: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False) 