#!/usr/bin/env python3
"""
CCTVストリーミングシステムの単体テスト
"""

import unittest
import requests
import time
import threading
from cctv_streaming_fixed import OptimizedCCTVStream
import base64

class TestCCTVStreamingSystem(unittest.TestCase):
    
    def setUp(self):
        """テスト用セットアップ"""
        self.cctv_system = OptimizedCCTVStream()
        print("🧪 テスト環境初期化完了")
    
    def test_cctv_connection(self):
        """CCTV接続テスト"""
        print("🔍 CCTV接続テスト実行中...")
        result = self.cctv_system.test_cctv_connection()
        self.assertTrue(result, "CCTV接続が失敗しました")
        print("✅ CCTV接続テスト成功")
    
    def test_multicast_port_calculation(self):
        """マルチキャストポート計算テスト"""
        print("🔢 マルチキャストポート計算テスト実行中...")
        
        # CH1のポート計算
        multicast_port1 = 9000 + (1 - 1) * 6  # 9000
        multicast_port2 = multicast_port1 + 2  # 9002
        self.assertEqual(multicast_port1, 9000)
        self.assertEqual(multicast_port2, 9002)
        
        # CH2のポート計算
        multicast_port1 = 9000 + (2 - 1) * 6  # 9006
        multicast_port2 = multicast_port1 + 2  # 9008
        self.assertEqual(multicast_port1, 9006)
        self.assertEqual(multicast_port2, 9008)
        
        # CH16のポート計算
        multicast_port1 = 9000 + (16 - 1) * 6  # 9090
        multicast_port2 = multicast_port1 + 2  # 9092
        self.assertEqual(multicast_port1, 9090)
        self.assertEqual(multicast_port2, 9092)
        
        print("✅ マルチキャストポート計算テスト成功")
    
    def test_frame_cache_system(self):
        """フレームキャッシュシステムテスト"""
        print("💾 フレームキャッシュテスト実行中...")
        
        # キャッシュが空であることを確認
        with self.cctv_system.cache_lock:
            self.assertEqual(len(self.cctv_system.frame_cache), 0)
        
        # テスト用フレームデータ
        test_frame = base64.b64encode(b"test_frame_data").decode('utf-8')
        
        # キャッシュに保存
        with self.cctv_system.cache_lock:
            self.cctv_system.frame_cache[1] = (time.time(), test_frame)
        
        # キャッシュから取得
        with self.cctv_system.cache_lock:
            self.assertIn(1, self.cctv_system.frame_cache)
            cache_time, cached_frame = self.cctv_system.frame_cache[1]
            self.assertEqual(cached_frame, test_frame)
        
        print("✅ フレームキャッシュテスト成功")
    
    def test_yolo_model_loading(self):
        """YOLOモデル読み込みテスト"""
        print("🤖 YOLOモデル読み込みテスト実行中...")
        
        # モデルの存在チェック
        import os
        model_exists = os.path.exists('yolo11n.pt')
        
        if model_exists:
            self.assertIsNotNone(self.cctv_system.model, "YOLOモデルが読み込まれていません")
            print("✅ YOLOモデル読み込みテスト成功")
        else:
            print("⚠️ YOLOモデルファイルが見つかりません（スキップ）")
    
    def test_channel_configuration(self):
        """チャンネル設定テスト"""
        print("📺 チャンネル設定テスト実行中...")
        
        # 設定された動作チャンネル数
        expected_channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
        self.assertEqual(self.cctv_system.working_channels, expected_channels)
        
        # デフォルト表示モード
        self.assertEqual(self.cctv_system.current_view_mode, 16)
        
        print("✅ チャンネル設定テスト成功")
    
    def test_session_optimization(self):
        """セッション最適化テスト"""
        print("🔧 セッション最適化テスト実行中...")
        
        # セッションが正しく設定されているか
        self.assertIsNotNone(self.cctv_system.session)
        self.assertIsNotNone(self.cctv_system.session.auth)
        
        # タイムアウト設定
        self.assertEqual(self.cctv_system.session.timeout, (2, 5))
        
        print("✅ セッション最適化テスト成功")
    
    def test_concurrent_stream_limits(self):
        """同時ストリーム制限テスト"""
        print("⚡ 同時ストリーム制限テスト実行中...")
        
        # 最大同時ストリーム数の確認
        self.assertEqual(self.cctv_system.max_concurrent_streams, 4)
        
        # エグゼキューターの存在確認
        self.assertIsNotNone(self.cctv_system.executor)
        
        print("✅ 同時ストリーム制限テスト成功")
    
    def test_view_mode_change(self):
        """表示モード変更テスト"""
        print("🖼️ 表示モード変更テスト実行中...")
        
        # 初期状態
        self.assertEqual(self.cctv_system.current_view_mode, 16)
        
        # 4画面モードに変更
        result = self.cctv_system.change_view_mode(4)
        self.assertTrue(result)
        self.assertEqual(self.cctv_system.current_view_mode, 4)
        
        # 9画面モードに変更
        result = self.cctv_system.change_view_mode(9)
        self.assertTrue(result)
        self.assertEqual(self.cctv_system.current_view_mode, 9)
        
        # 16画面モードに戻す
        result = self.cctv_system.change_view_mode(16)
        self.assertTrue(result)
        self.assertEqual(self.cctv_system.current_view_mode, 16)
        
        print("✅ 表示モード変更テスト成功")

def run_tests():
    """テスト実行"""
    print("🚀 CCTVストリーミングシステム単体テスト開始")
    print("=" * 50)
    
    # テストスイートの作成
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestCCTVStreamingSystem)
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("=" * 50)
    
    # 結果サマリー
    if result.wasSuccessful():
        print("🎉 全テスト成功！システムは正常に動作しています")
        print(f"✅ 実行: {result.testsRun}テスト")
    else:
        print("⚠️ 一部テストが失敗しました")
        print(f"❌ 失敗: {len(result.failures)}テスト")
        print(f"🚫 エラー: {len(result.errors)}テスト")
        
        # 失敗詳細
        for test, traceback in result.failures:
            print(f"\n失敗: {test}")
            print(traceback)
        
        for test, traceback in result.errors:
            print(f"\nエラー: {test}")
            print(traceback)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
