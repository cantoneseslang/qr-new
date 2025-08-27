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
        # 在庫データ（実際の運用時はデータベースやAPIから取得）
        self.inventory_data = {
            "BD-060": {
                "name": "泰山普通石膏板 4'x6'x12mmx 4.5mm",
                "quantity": 100,
                "updated": "2025-07-26",
                "location": "倉庫A-1",
                "category": "建材",
                "unit": "枚"
            },
            "US0503206MM2440": {
                "name": "Stud 50mmx32mmx0.6mmx2440mm",
                "quantity": 200,
                "updated": "2025-07-26",
                "location": "倉庫A-2",
                "category": "金属材",
                "unit": "本"
            },
            "AC-258": {
                "name": "KIRII Corner Bead 2440mm (25pcs/bdl)(0.4mm 鋁)",
                "quantity": 50,
                "updated": "2025-07-26",
                "location": "倉庫B-1",
                "category": "部品",
                "unit": "束"
            },
            "AC-261": {
                "name": "黃岩綿- 60g (6pcs/pack)",
                "quantity": 10,
                "updated": "2025-07-26",
                "location": "倉庫B-2",
                "category": "断熱材",
                "unit": "パック"
            }
        }

platform = KiriiInventoryPlatform()

@app.route('/')
def index():
    """メインページ - 携帯対応ダッシュボード"""
    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🏭 KIRII在庫管理システム</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 480px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        
        .logo {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .title {
            font-size: 1.5em;
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
            font-size: 0.9em;
            margin-bottom: 8px;
            line-height: 1.3;
        }
        
        .product-quantity {
            font-size: 1.1em;
            font-weight: bold;
            color: #4CAF50;
        }
        
        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-high { background: #4CAF50; }
        .status-medium { background: #FF9800; }
        .status-low { background: #F44336; }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            opacity: 0.7;
            font-size: 0.8em;
        }
        
        @media (max-width: 480px) {
            .container {
                padding: 10px;
            }
            
            .header {
                padding: 15px;
            }
            
            .logo {
                font-size: 2em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🏭</div>
            <div class="title">KIRII在庫管理</div>
            <div class="subtitle">QRコード在庫確認システム</div>
        </div>
        
        <div class="qr-scanner">
            <button class="scan-button" onclick="startQRScan()">
                📱 QRコードをスキャン
            </button>
            <div class="manual-input">
                <div class="input-group">
                    <input type="text" class="code-input" id="productCode" 
                           placeholder="製品コードを入力" maxlength="20">
                    <button class="search-button" onclick="searchProduct()">
                        🔍 検索
                    </button>
                </div>
            </div>
        </div>
        
        <div class="inventory-list">
            <div class="list-title">📦 在庫一覧</div>
            {% for code, product in inventory_data.items() %}
            <div class="product-card" onclick="showProductDetail('{{ code }}')">
                <div class="product-code">{{ code }}</div>
                <div class="product-name">{{ product.name }}</div>
                <div class="product-quantity">
                    <span class="status-indicator {% if product.quantity > 50 %}status-high{% elif product.quantity > 20 %}status-medium{% else %}status-low{% endif %}"></span>
                    在庫: {{ product.quantity }}{{ product.unit }}
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="footer">
            © 2025 KIRII工場監視システム<br>
            最終更新: {{ current_time }}
        </div>
    </div>
    
    <script>
        function startQRScan() {
            // 実際の運用時はカメラAPIを使用
            alert('QRコードスキャン機能を起動します\\n\\nカメラの使用を許可してください');
            
                         // デモ用：製品コード選択
             const codes = {{ product_codes | tojson }};
             const selectedCode = prompt('デモ用：製品コードを選択してください\\n\\n' + codes.join('\\n'));
            
            if (selectedCode && codes.includes(selectedCode)) {
                window.location.href = '/product/' + selectedCode;
            }
        }
        
        function searchProduct() {
            const code = document.getElementById('productCode').value.trim();
            if (code) {
                window.location.href = '/product/' + code;
            } else {
                alert('製品コードを入力してください');
            }
        }
        
        function showProductDetail(code) {
            window.location.href = '/product/' + code;
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
    inventory_data=platform.inventory_data,
    current_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
    product_codes=list(platform.inventory_data.keys())
    )

@app.route('/product/<product_code>')
def product_detail(product_code):
    """製品詳細ページ - QRコードからアクセス"""
    if product_code not in platform.inventory_data:
        return render_template_string('''
        <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
            <h1>❌ 製品が見つかりません</h1>
            <p>製品コード: {{ code }}</p>
            <a href="/" style="color: blue;">トップページに戻る</a>
        </div>
        ''', code=product_code), 404
    
    product = platform.inventory_data[product_code]
    
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
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 480px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        
        .back-button {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 10px 15px;
            border-radius: 10px;
            text-decoration: none;
            font-size: 1.2em;
        }
        
        .product-detail {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
        }
        
        .product-code {
            font-family: 'Courier New', monospace;
            font-size: 1.5em;
            font-weight: bold;
            color: #FFE082;
            text-align: center;
            margin-bottom: 20px;
            padding: 15px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
        }
        
        .product-name {
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 25px;
            text-align: center;
            line-height: 1.4;
        }
        
        .info-grid {
            display: grid;
            gap: 15px;
        }
        
        .info-item {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .info-label {
            font-weight: bold;
            opacity: 0.8;
        }
        
        .info-value {
            font-size: 1.1em;
            font-weight: bold;
        }
        
        .quantity-large {
            font-size: 2.5em;
            font-weight: bold;
            text-align: center;
            margin: 30px 0;
            padding: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            {% if product.quantity > 50 %}
            color: #4CAF50;
            {% elif product.quantity > 20 %}
            color: #FF9800;
            {% else %}
            color: #F44336;
            {% endif %}
        }
        
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
            {% if product.quantity > 50 %}
            background: #4CAF50;
            {% elif product.quantity > 20 %}
            background: #FF9800;
            {% else %}
            background: #F44336;
            {% endif %}
        }
        
        .action-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 30px;
        }
        
        .btn {
            padding: 15px;
            border: none;
            border-radius: 10px;
            font-weight: bold;
            font-size: 1em;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        
        .btn:hover {
            transform: translateY(-2px);
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
        }
        
        .btn-secondary {
            background: linear-gradient(45deg, #2196F3, #1976D2);
            color: white;
        }
        
        .update-time {
            text-align: center;
            margin-top: 20px;
            opacity: 0.7;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <a href="/" class="back-button">← 戻る</a>
    
    <div class="container">
        <div class="header">
            <div style="font-size: 2em; margin-bottom: 10px;">📦</div>
            <div style="font-size: 1.2em; font-weight: bold;">製品詳細情報</div>
        </div>
        
        <div class="product-detail">
            <div class="product-code">{{ product_code }}</div>
            <div class="product-name">{{ product.name }}</div>
            
            <div class="quantity-large">
                {{ product.quantity }} {{ product.unit }}
                <div style="font-size: 0.4em; margin-top: 10px;">
                    <span class="status-badge">
                        {% if product.quantity > 50 %}
                        在庫充分
                        {% elif product.quantity > 20 %}
                        在庫注意
                        {% else %}
                        在庫不足
                        {% endif %}
                    </span>
                </div>
            </div>
            
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">📍 保管場所</span>
                    <span class="info-value">{{ product.location }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">🏷️ カテゴリ</span>
                    <span class="info-value">{{ product.category }}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">📅 最終更新</span>
                    <span class="info-value">{{ product.updated }}</span>
                </div>
            </div>
            
            <div class="action-buttons">
                <button class="btn btn-primary" onclick="updateQuantity()">
                    📝 数量更新
                </button>
                <button class="btn btn-secondary" onclick="shareProduct()">
                    📤 共有
                </button>
            </div>
        </div>
        
        <div class="update-time">
            最終確認: {{ current_time }}
        </div>
    </div>
    
    <script>
        function updateQuantity() {
            const newQuantity = prompt('新しい在庫数量を入力してください:', '{{ product.quantity }}');
            if (newQuantity && !isNaN(newQuantity)) {
                alert('在庫数量を更新しました: ' + newQuantity + '{{ product.unit }}');
                // 実際の運用時はAPIで更新
            }
        }
        
        function shareProduct() {
            if (navigator.share) {
                navigator.share({
                    title: '{{ product.name }}',
                    text: '製品コード: {{ product_code }}\\n在庫数量: {{ product.quantity }}{{ product.unit }}',
                    url: window.location.href
                });
            } else {
                // フォールバック
                const text = '製品コード: {{ product_code }}\\n品名: {{ product.name }}\\n在庫: {{ product.quantity }}{{ product.unit }}\\nURL: ' + window.location.href;
                navigator.clipboard.writeText(text).then(() => {
                    alert('製品情報をクリップボードにコピーしました');
                });
            }
        }
    </script>
</body>
</html>
    ''', 
    product_code=product_code,
    product=product,
    current_time=datetime.now().strftime('%Y-%m-%d %H:%M')
    )

@app.route('/api/inventory')
def api_inventory():
    """在庫データAPI"""
    return jsonify(platform.inventory_data)

@app.route('/api/product/<product_code>')
def api_product(product_code):
    """製品詳細API"""
    if product_code not in platform.inventory_data:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'code': product_code,
        'product': platform.inventory_data[product_code]
    })

# Vercel用のアプリインスタンス
app_instance = app

if __name__ == '__main__':
    print("🏭 KIRII在庫管理Vercelプラットフォーム起動")
    print("📱 携帯対応在庫確認システム")
    print("🌐 アクセス: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True) 