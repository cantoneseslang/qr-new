#!/usr/bin/env python3
"""
HTTPS対応ローカルテストサーバー
QRカメラのテスト用
"""

from kirii_qr_inventory_app import app
import ssl

if __name__ == '__main__':
    # 自己署名証明書でHTTPS起動
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    
    print("🔒 HTTPS対応ローカルサーバー起動")
    print("📱 QRカメラテスト用")
    print("🌐 アクセス: https://localhost:5000")
    print("⚠️  証明書警告が出ますが、「詳細設定」→「localhost に進む」で続行してください")
    
    app.run(host='0.0.0.0', port=5000, ssl_context=context, debug=False) 