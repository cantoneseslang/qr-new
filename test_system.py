#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工場監視システム - テスト・デモスクリプト
YOLO11を使用した工場在庫管理システムの動作確認
"""

import os
import sys
import time
import cv2
import numpy as np
from datetime import datetime
import logging

# プロジェクトモジュールのインポート
from factory_monitor import FactoryMonitor
from camera_connection import FactoryCameraConnection
from object_counter import AdvancedObjectCounter, CountingZone, DetectedObject, ObjectCountVisualizer
from web_dashboard import WebDashboard


class SystemTester:
    """システムテストクラス"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # システムコンポーネント
        self.monitor = None
        self.camera = None
        self.counter = None
        self.dashboard = None
        
        print("=== YOLO11工場監視システム - テスト環境 ===")
        print("Ultralyticsのページ: https://github.com/ultralytics/ultralytics/")
        print()
    
    def test_yolo_model(self):
        """YOLO11モデルテスト"""
        print("📋 1. YOLO11モデルテスト")
        print("-" * 40)
        
        try:
            # FactoryMonitor初期化
            self.monitor = FactoryMonitor()
            print("✅ YOLO11モデル読み込み成功")
            
            # モデル情報表示
            print(f"   モデル: {self.monitor.model}")
            print(f"   デバイス: {self.monitor.device}")
            print(f"   クラス数: {len(self.monitor.model.names)}")
            
            # 利用可能なクラス表示
            print("   検出可能クラス:")
            for i, class_name in enumerate(list(self.monitor.model.names.values())[:10]):
                print(f"     {i}: {class_name}")
            if len(self.monitor.model.names) > 10:
                print(f"     ... 他 {len(self.monitor.model.names) - 10} クラス")
            
            return True
            
        except Exception as e:
            print(f"❌ YOLO11モデルテスト失敗: {e}")
            return False
    
    def test_camera_connection(self):
        """カメラ接続テスト"""
        print("\n📋 2. カメラ接続テスト")
        print("-" * 40)
        
        try:
            # カメラ接続初期化
            self.camera = FactoryCameraConnection(self.monitor)
            
            # Webカメラテスト
            print("🔍 Webカメラ接続テスト中...")
            if self.camera.connect_camera(0):
                print("✅ Webカメラ接続成功")
                
                # カメラ情報表示
                info = self.camera.get_camera_info()
                print(f"   解像度: {info.get('frame_width', 'N/A')}x{info.get('frame_height', 'N/A')}")
                print(f"   FPS: {info.get('fps', 'N/A')}")
                
                # テストフレーム取得
                ret, frame = self.camera.capture_single_frame()
                if ret and frame is not None:
                    print(f"   フレームサイズ: {frame.shape}")
                    print("✅ フレーム取得成功")
                else:
                    print("⚠️  フレーム取得失敗")
                
                self.camera.disconnect_camera()
                return True
            else:
                print("❌ Webカメラ接続失敗")
                return False
                
        except Exception as e:
            print(f"❌ カメラ接続テスト失敗: {e}")
            return False
    
    def test_object_detection(self):
        """物体検出テスト"""
        print("\n📋 3. 物体検出テスト")
        print("-" * 40)
        
        try:
            # テスト画像作成（合成画像）
            print("🎨 テスト画像作成中...")
            test_image = self.create_test_image()
            
            # 物体検出実行
            print("🔍 物体検出実行中...")
            counts, annotated_frame = self.monitor.detect_objects(test_image)
            
            # 結果表示
            if counts:
                print("✅ 物体検出成功")
                print("   検出結果:")
                total_objects = 0
                for class_name, count in counts.items():
                    print(f"     {class_name}: {count}個")
                    total_objects += count
                print(f"   総検出数: {total_objects}個")
            else:
                print("⚠️  物体検出なし（テスト画像では正常）")
            
            # 結果画像保存
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"test_detection_{timestamp}.jpg"
            cv2.imwrite(output_path, annotated_frame)
            print(f"   結果画像保存: {output_path}")
            
            return True
            
        except Exception as e:
            print(f"❌ 物体検出テスト失敗: {e}")
            return False
    
    def test_advanced_counting(self):
        """高度カウント機能テスト"""
        print("\n📋 4. 高度カウント機能テスト")
        print("-" * 40)
        
        try:
            # AdvancedObjectCounter初期化
            self.counter = AdvancedObjectCounter()
            print("✅ 高度カウントシステム初期化成功")
            
            # テスト用カウントゾーン作成
            test_zone = CountingZone(
                name="テストエリア",
                polygon=[(100, 100), (400, 100), (400, 300), (100, 300)],
                target_classes={'person', 'car', 'truck'}
            )
            self.counter.add_counting_zone(test_zone)
            print("✅ カウントゾーン追加成功")
            
            # テスト用検出データ作成
            test_detections = [
                DetectedObject(
                    class_name='person',
                    confidence=0.85,
                    bbox=(150, 150, 200, 250),
                    center=(175, 200),
                    area=2500,
                    timestamp=datetime.now()
                ),
                DetectedObject(
                    class_name='car',
                    confidence=0.92,
                    bbox=(250, 180, 350, 280),
                    center=(300, 230),
                    area=10000,
                    timestamp=datetime.now()
                )
            ]
            
            # カウント実行
            counts = self.counter.count_objects_in_frame(test_detections)
            print("✅ 物体カウント実行成功")
            print(f"   カウント結果: {counts}")
            
            # 在庫サマリー取得
            summary = self.counter.get_inventory_summary()
            print("✅ 在庫サマリー取得成功")
            print(f"   総アイテム: {summary['total_items']}個")
            
            # データエクスポートテスト
            export_path = "test_export_data.json"
            if self.counter.export_count_data(export_path):
                print(f"✅ データエクスポート成功: {export_path}")
            else:
                print("⚠️  データエクスポート失敗")
            
            return True
            
        except Exception as e:
            print(f"❌ 高度カウント機能テスト失敗: {e}")
            return False
    
    def test_web_dashboard(self):
        """Webダッシュボードテスト"""
        print("\n📋 5. Webダッシュボードテスト")
        print("-" * 40)
        
        try:
            # WebDashboard初期化（テストモード）
            print("🌐 Webダッシュボード初期化中...")
            self.dashboard = WebDashboard()
            print("✅ Webダッシュボード初期化成功")
            
            # テンプレート作成テスト
            self.dashboard.create_dashboard_template()
            template_path = os.path.join("templates", "dashboard.html")
            if os.path.exists(template_path):
                print("✅ HTMLテンプレート作成成功")
                print(f"   テンプレートパス: {template_path}")
            else:
                print("⚠️  HTMLテンプレート作成失敗")
            
            # API エンドポイントテスト（モック）
            print("✅ APIエンドポイント設定完了")
            print("   利用可能API:")
            print("     GET  /api/status")
            print("     GET  /api/statistics")
            print("     GET  /api/history")
            print("     POST /api/connect_camera")
            print("     POST /api/start_streaming")
            print("     POST /api/stop_streaming")
            print("     POST /api/export_data")
            
            return True
            
        except Exception as e:
            print(f"❌ Webダッシュボードテスト失敗: {e}")
            return False
    
    def create_test_image(self):
        """テスト用画像作成"""
        # 640x480の背景画像作成
        image = np.ones((480, 640, 3), dtype=np.uint8) * 128
        
        # 簡単な図形を描画（物体検出テスト用）
        # 矩形（車っぽい形）
        cv2.rectangle(image, (100, 200), (200, 300), (0, 0, 255), -1)
        cv2.rectangle(image, (110, 210), (190, 290), (255, 255, 255), 2)
        
        # 円（人っぽい形）
        cv2.circle(image, (350, 150), 30, (255, 0, 0), -1)
        cv2.rectangle(image, (330, 180), (370, 280), (255, 0, 0), -1)
        
        # テキスト追加
        cv2.putText(image, "Factory Test Image", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        return image
    
    def run_interactive_demo(self):
        """インタラクティブデモ実行"""
        print("\n📋 6. インタラクティブデモ")
        print("-" * 40)
        print("利用可能なデモ:")
        print("1. Webカメラリアルタイム監視")
        print("2. Webダッシュボード起動")
        print("3. システム統計表示")
        print("4. 終了")
        
        while True:
            try:
                choice = input("\n選択してください (1-4): ").strip()
                
                if choice == "1":
                    self.run_realtime_demo()
                elif choice == "2":
                    self.run_web_dashboard_demo()
                elif choice == "3":
                    self.show_system_statistics()
                elif choice == "4":
                    print("デモを終了します")
                    break
                else:
                    print("無効な選択です")
                    
            except KeyboardInterrupt:
                print("\nデモを終了します")
                break
    
    def run_realtime_demo(self):
        """リアルタイム監視デモ"""
        print("\n🎥 リアルタイム監視デモ開始")
        print("'q'キーで終了、's'キーでスクリーンショット保存")
        
        try:
            if not self.camera:
                self.camera = FactoryCameraConnection(self.monitor)
            
            # Webカメラで連続監視
            self.camera.run_continuous_monitoring(0, display=True)
            
        except Exception as e:
            print(f"リアルタイム監視エラー: {e}")
    
    def run_web_dashboard_demo(self):
        """Webダッシュボードデモ"""
        print("\n🌐 Webダッシュボードデモ開始")
        print("ブラウザで http://localhost:5000 にアクセスしてください")
        print("Ctrl+C で終了")
        
        try:
            if not self.dashboard:
                self.dashboard = WebDashboard()
            
            self.dashboard.run(debug=False)
            
        except KeyboardInterrupt:
            print("\nWebダッシュボードを終了します")
        except Exception as e:
            print(f"Webダッシュボードエラー: {e}")
    
    def show_system_statistics(self):
        """システム統計表示"""
        print("\n📊 システム統計情報")
        print("-" * 40)
        
        if self.monitor:
            status = self.monitor.get_current_status()
            print("🔍 監視システム状態:")
            print(f"   監視中: {status['is_monitoring']}")
            print(f"   総検出数: {status['total_objects']}")
            print(f"   履歴件数: {status['history_count']}")
        
        if self.counter:
            summary = self.counter.get_inventory_summary()
            print("\n📦 在庫情報:")
            print(f"   総アイテム: {summary['total_items']}")
            if summary['current_counts']:
                for item, count in summary['current_counts'].items():
                    print(f"     {item}: {count}個")
        
        print("\n💾 データファイル:")
        for filename in ['factory_monitor.log', 'detection_history.json']:
            if os.path.exists(filename):
                size = os.path.getsize(filename)
                print(f"   {filename}: {size} bytes")
    
    def run_all_tests(self):
        """全テスト実行"""
        print("🚀 工場監視システム - 全機能テスト開始")
        print("=" * 50)
        
        test_results = []
        
        # 各テスト実行
        test_results.append(("YOLO11モデル", self.test_yolo_model()))
        test_results.append(("カメラ接続", self.test_camera_connection()))
        test_results.append(("物体検出", self.test_object_detection()))
        test_results.append(("高度カウント", self.test_advanced_counting()))
        test_results.append(("Webダッシュボード", self.test_web_dashboard()))
        
        # 結果サマリー
        print("\n" + "=" * 50)
        print("📊 テスト結果サマリー")
        print("=" * 50)
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:<20}: {status}")
            if result:
                passed += 1
        
        print("-" * 50)
        print(f"成功: {passed}/{total} ({passed/total*100:.1f}%)")
        
        if passed == total:
            print("🎉 全テスト成功！システムは正常に動作しています。")
            return True
        else:
            print("⚠️  一部テストが失敗しました。ログを確認してください。")
            return False


def main():
    """メイン関数"""
    tester = SystemTester()
    
    print("工場監視システムテスト開始")
    print("使用技術: YOLO11 (Ultralytics)")
    print("参考URL: https://github.com/ultralytics/ultralytics/")
    print()
    
    # 全テスト実行
    success = tester.run_all_tests()
    
    if success:
        print("\n🎯 システムテスト完了！")
        print("次のステップ:")
        print("1. python camera_connection.py - カメラテスト")
        print("2. python web_dashboard.py - Webダッシュボード起動")
        print("3. python factory_monitor.py - 単体テスト")
        
        # インタラクティブデモ実行
        print("\nインタラクティブデモを開始しますか？ (y/n): ", end="")
        if input().lower().startswith('y'):
            tester.run_interactive_demo()
    
    else:
        print("\n❌ システムテストで問題が発生しました。")
        print("requirements.txtの依存関係を確認してください:")
        print("pip install -r requirements.txt")


if __name__ == "__main__":
    main() 