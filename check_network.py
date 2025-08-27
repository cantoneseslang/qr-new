#!/usr/bin/env python3
"""
ネットワーク接続確認スクリプト
"""

import subprocess
import socket
import requests
from requests.auth import HTTPBasicAuth

def check_current_network():
    """現在のネットワーク接続確認"""
    print("🌐 現在のネットワーク状況")
    print("-" * 40)
    
    # Wi-Fi接続確認
    try:
        result = subprocess.run(['networksetup', '-getairportnetwork', 'en0'], 
                              capture_output=True, text=True)
        if "You are not associated" in result.stdout:
            print("❌ Wi-Fi: 未接続")
        else:
            wifi_name = result.stdout.strip().replace("Current Wi-Fi Network: ", "")
            print(f"✅ Wi-Fi: {wifi_name}")
    except Exception as e:
        print(f"❌ Wi-Fi確認エラー: {e}")
    
    # IPアドレス確認
    try:
        result = subprocess.run(['ifconfig'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        for line in lines:
            if 'inet ' in line and '127.0.0.1' not in line and 'inet 169.254' not in line:
                ip = line.strip().split()[1]
                print(f"📍 現在のIP: {ip}")
                return ip
    except Exception as e:
        print(f"❌ IP確認エラー: {e}")
    
    return None

def ping_camera_ips():
    """カメラIPへのping確認"""
    print("\n🎯 カメラIP接続確認")
    print("-" * 40)
    
    camera_ips = ['192.168.1.10', '192.168.1.2', '192.168.0.99']
    
    for ip in camera_ips:
        try:
            result = subprocess.run(['ping', '-c', '1', '-W', '3000', ip], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {ip}: 接続可能")
            else:
                print(f"❌ {ip}: 接続不可")
        except Exception as e:
            print(f"❌ {ip}: ping エラー - {e}")

def test_camera_ports():
    """カメラポート接続確認"""
    print("\n🔌 ポート接続確認")
    print("-" * 40)
    
    test_configs = [
        ('192.168.1.10', 10000, 'CCTV Camera'),
        ('192.168.1.2', 80, 'IP Camera HTTP'),
        ('192.168.1.2', 8080, 'IP Camera Alt'),
        ('192.168.1.2', 554, 'IP Camera RTSP'),
        ('192.168.0.99', 5900, 'Card System VNC'),
    ]
    
    for ip, port, name in test_configs:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                print(f"✅ {name} ({ip}:{port}): ポート開放")
            else:
                print(f"❌ {name} ({ip}:{port}): ポート閉鎖")
        except Exception as e:
            print(f"❌ {name} ({ip}:{port}): エラー - {e}")

def test_http_access():
    """HTTP接続確認"""
    print("\n🌐 HTTP接続確認")
    print("-" * 40)
    
    test_urls = [
        ('http://192.168.1.10:10000', 'admin', 'password', 'CCTV Camera'),
        ('http://192.168.1.2', 'admin', 'admin', 'IP Camera'),
        ('http://192.168.1.2:8080', 'admin', 'admin', 'IP Camera Alt'),
    ]
    
    for url, username, password, name in test_urls:
        try:
            response = requests.get(url, 
                                  auth=HTTPBasicAuth(username, password),
                                  timeout=5)
            print(f"✅ {name}: HTTP {response.status_code}")
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '不明')
                print(f"   📄 Content-Type: {content_type}")
        except requests.exceptions.ConnectTimeout:
            print(f"❌ {name}: 接続タイムアウト")
        except requests.exceptions.ConnectionError:
            print(f"❌ {name}: 接続エラー")
        except Exception as e:
            print(f"❌ {name}: {e}")

def main():
    print("=" * 50)
    print("🔍 社内ネットワーク・カメラ接続診断")
    print("=" * 50)
    
    # 現在のネットワーク確認
    current_ip = check_current_network()
    
    # カメラIP ping確認
    ping_camera_ips()
    
    # ポート接続確認
    test_camera_ports()
    
    # HTTP接続確認
    test_http_access()
    
    print("\n" + "=" * 50)
    print("📋 診断結果まとめ")
    print("=" * 50)
    
    if current_ip and current_ip.startswith('192.168.1.'):
        print("✅ 適切なネットワーク (192.168.1.x) に接続済み")
        print("🎬 YOLOシステムでカメラURL設定を試してください")
    elif current_ip and current_ip.startswith('192.168.0.'):
        print("⚠️  現在は 192.168.0.x ネットワークに接続")
        print("📶 社内Wi-Fi 'link-791 E' に接続してください")
    else:
        print("❌ ネットワーク接続に問題があります")
    
    print("\n💡 次のステップ:")
    print("1. 社内Wi-Fi 'link-791 E' (パスワード: dbcci57208) に接続")
    print("2. 再度このスクリプトを実行して接続確認")
    print("3. 成功したカメラURLをYOLOシステムに設定")

if __name__ == "__main__":
    main() 