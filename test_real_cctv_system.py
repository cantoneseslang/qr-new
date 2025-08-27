#!/usr/bin/env python3
"""
実際のCCTV監視システムのユニットテスト
実際のCCTV機器接続が必要であることを確認
"""

import unittest
import requests
import sys
import os
from unittest.mock import patch, MagicMock
import logging

# テスト対象のモジュールをインポート
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cctv_real_monitoring_system import CCTVMonitoringSystem

class TestRealCCTVSystem(unittest.TestCase):
    """実際のCCTV監視システムのテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.system = CCTVMonitoringSystem()
        # ログレベルを設定してテスト出力を抑制
        logging.getLogger().setLevel(logging.CRITICAL)
    
    def test_system_initialization_requires_real_connection(self):
        """システム初期化には実際の接続が必要であることを確認"""
        # 実際のCCTV機器がない環境では初期化が失敗することを確認
        result = self.system.initialize_system()
        self.assertFalse(result, "CCTV機器がない場合、システム初期化は失敗すべき")
        self.assertFalse(self.system.system_healthy, "システムは非正常状態であるべき")
    
    def test_no_dummy_data_generation(self):
        """ダミーデータが生成されないことを確認"""
        # システム初期化失敗後、フレームデータが存在しないことを確認
        self.system.initialize_system()
        self.assertEqual(len(self.system.frames), 0, "ダミーフレームは生成されるべきではない")
        self.assertFalse(hasattr(self.system, 'available_channels'), "利用可能チャンネルは設定されるべきではない")
    
    def test_connection_failure_handling(self):
        """接続失敗時の適切な処理を確認"""
        # 基本接続確認が失敗することを確認
        connection_success = self.system.check_cctv_connection()
        self.assertFalse(connection_success, "CCTV機器がない場合、接続確認は失敗すべき")
    
    def test_channel_availability_without_device(self):
        """機器なしでのチャンネル利用可能性テスト"""
        available_channels = self.system.test_channel_availability()
        self.assertEqual(len(available_channels), 0, "CCTV機器がない場合、利用可能チャンネルは0であるべき")
    
    def test_system_exit_on_failure(self):
        """システム初期化失敗時の終了処理を確認"""
        with self.assertRaises(SystemExit):
            # start_monitoring は初期化失敗時に sys.exit(1) を呼ぶ
            self.system.start_monitoring()
    
    def test_system_status_after_failure(self):
        """システム失敗後の状態を確認"""
        self.system.initialize_system()
        status = self.system.get_system_status()
        
        self.assertFalse(status['healthy'], "システム状態は非正常であるべき")
        self.assertEqual(len(status['available_channels']), 0, "利用可能チャンネルは0であるべき")
        self.assertEqual(len(status['active_channels']), 0, "アクティブチャンネルは0であるべき")
    
    
    def test_authentication_configuration(self):
        """認証設定が正しく構成されていることを確認"""
        self.assertEqual(self.system.username, "admin", "ユーザー名が正しく設定されているべき")
        self.assertEqual(self.system.password, "admin", "パスワードが正しく設定されているべき")
        self.assertEqual(self.system.auth, ("admin", "admin"), "認証情報が正しく設定されているべき")
    
    def test_network_configuration(self):
        """ネットワーク設定が実際のCCTV機器設定に合致することを確認"""
        self.assertEqual(self.system.cctv_ip, "192.168.1.10", "CCTV IPアドレスが正しく設定されているべき")
        self.assertEqual(self.system.cctv_port, 10000, "CCTVポートが正しく設定されているべき")
        self.assertEqual(self.system.base_url, "http://192.168.1.10:10000", "ベースURLが正しく構成されているべき")
    
    def test_required_channels_configuration(self):
        """必須チャンネル数の設定を確認"""
        self.assertEqual(self.system.required_channels, 4, "最低4チャンネルが必要であるべき")
        self.assertEqual(self.system.max_channels, 16, "最大16チャンネルに対応すべき")

class TestSystemBehaviorWithoutMockData(unittest.TestCase):
    """モックデータを使用しないシステム動作テスト"""
    
    def test_strict_no_mock_data_policy(self):
        """厳格なモックデータ禁止ポリシーの確認"""
        system = CCTVMonitoringSystem()
        
        # システム初期化失敗時
        init_result = system.initialize_system()
        self.assertFalse(init_result)
        
        # フレームデータが一切生成されていないことを確認
        self.assertEqual(len(system.frames), 0, "フレームデータは一切生成されるべきではない")
        
        # 接続状態も空であることを確認
        self.assertEqual(len(system.connection_status), 0, "接続状態データも生成されるべきではない")
        
        # システムが非健全状態であることを確認
        self.assertFalse(system.system_healthy, "システムは非健全状態を維持すべき")

def run_tests():
    """テスト実行関数"""
    print("="*60)
    print("🧪 実際のCCTV監視システム ユニットテスト")
    print("="*60)
    print("⚠️  このテストは実際のCCTV機器なしで実行されます")
    print("⚠️  全てのテストが「接続失敗」を期待値として設計されています")
    print("="*60)
    
    # テストスイートを作成
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # テストクラスを追加
    suite.addTests(loader.loadTestsFromTestCase(TestRealCCTVSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemBehaviorWithoutMockData))
    
    # テスト実行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("="*60)
    if result.wasSuccessful():
        print("✅ 全てのテストが成功しました！")
        print("✅ システムは実際のCCTV機器が必要であることが確認されました")
        print("✅ ダミーデータの生成が完全に防止されていることが確認されました")
    else:
        print("❌ 一部のテストが失敗しました")
        print(f"失敗: {len(result.failures)}, エラー: {len(result.errors)}")
    
    print("="*60)
    print("📝 テスト概要:")
    print("   - 実際のCCTV機器への接続要求の確認")
    print("   - 接続失敗時のシステム停止動作の確認") 
    print("   - ダミーデータ生成の完全防止の確認")
    print("   - 認証設定とネットワーク設定の確認")
    print("="*60)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
