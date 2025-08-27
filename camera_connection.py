#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工場監視システム - カメラ接続処理
IPカメラ・Webカメラからのリアルタイム映像取得
"""

import cv2
import numpy as np
import time
import threading
import logging
from typing import Optional, Callable, Tuple
from urllib.parse import urlparse

from config import CAMERA_CONFIG, CAMERA_URLS, NETWORK_CONFIG
from factory_monitor import FactoryMonitor


class FactoryCameraConnection:
    """工場カメラ接続管理クラス"""
    
    def __init__(self, monitor: Optional[FactoryMonitor] = None):
        """
        初期化
        
        Args:
            monitor: FactoryMonitorインスタンス（オプション）
        """
        self.logger = logging.getLogger(__name__)
        self.monitor = monitor or FactoryMonitor()
        
        # カメラ設定
        self.cap = None
        self.is_connected = False
        self.is_streaming = False
        self.current_url = None
        
        # ストリーミング制御
        self.streaming_thread = None
        self.stop_streaming = False
        
        # フレーム管理
        self.latest_frame = None
        self.frame_count = 0
        self.fps_counter = 0
        self.last_fps_time = time.time()
        
        self.logger.info("カメラ接続システムが初期化されました")
    
    def connect_camera(self, source) -> bool:
        """
        カメラ接続
        
        Args:
            source: カメラソース（URL、デバイス番号など）
            
        Returns:
            bool: 接続成功フラグ
        """
        try:
            # 既存接続を切断
            self.disconnect_camera()
            
            # OpenCV VideoCapture初期化
            self.cap = cv2.VideoCapture(source)
            
            # カメラ設定適用
            self._apply_camera_settings()
            
            # 接続テスト
            if self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret and frame is not None:
                    self.is_connected = True
                    self.current_url = source
                    self.logger.info(f"カメラ接続成功: {source}")
                    return True
            
            self.logger.error(f"カメラ接続失敗: {source}")
            return False
            
        except Exception as e:
            self.logger.error(f"カメラ接続エラー: {e}")
            return False
    
    def _apply_camera_settings(self):
        """カメラ設定適用"""
        if self.cap is None:
            return
        
        try:
            # フレームサイズ設定
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_CONFIG['frame_width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_CONFIG['frame_height'])
            
            # FPS設定
            self.cap.set(cv2.CAP_PROP_FPS, CAMERA_CONFIG['fps'])
            
            # バッファサイズ設定（遅延軽減）
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_CONFIG['buffer_size'])
            
            # RTSPタイムアウト設定
            if isinstance(self.current_url, str) and 'rtsp://' in self.current_url:
                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAMERA_CONFIG['rtsp_timeout'] * 1000)
            
            self.logger.info("カメラ設定を適用しました")
            
        except Exception as e:
            self.logger.warning(f"カメラ設定適用エラー: {e}")
    
    def disconnect_camera(self):
        """カメラ切断"""
        try:
            # ストリーミング停止
            self.stop_live_streaming()
            
            # カメラリソース解放
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            
            self.is_connected = False
            self.current_url = None
            self.latest_frame = None
            
            self.logger.info("カメラ切断完了")
            
        except Exception as e:
            self.logger.error(f"カメラ切断エラー: {e}")
    
    def capture_single_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        単一フレーム取得
        
        Returns:
            Tuple[bool, Optional[np.ndarray]]: (成功フラグ, フレーム)
        """
        if not self.is_connected or self.cap is None:
            return False, None
        
        try:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.latest_frame = frame.copy()
                self.frame_count += 1
                return True, frame
            else:
                self.logger.warning("フレーム取得失敗")
                return False, None
                
        except Exception as e:
            self.logger.error(f"フレーム取得エラー: {e}")
            return False, None
    
    def start_live_streaming(self, callback: Optional[Callable] = None):
        """
        ライブストリーミング開始
        
        Args:
            callback: フレーム処理コールバック関数
        """
        if self.is_streaming:
            self.logger.warning("既にストリーミング中です")
            return
        
        if not self.is_connected:
            self.logger.error("カメラが接続されていません")
            return
        
        self.stop_streaming = False
        self.is_streaming = True
        
        # ストリーミングスレッド開始
        self.streaming_thread = threading.Thread(
            target=self._streaming_loop,
            args=(callback,),
            daemon=True
        )
        self.streaming_thread.start()
        
        self.logger.info("ライブストリーミング開始")
    
    def _streaming_loop(self, callback: Optional[Callable] = None):
        """ストリーミングループ"""
        self.fps_counter = 0
        self.last_fps_time = time.time()
        
        while not self.stop_streaming and self.is_connected:
            try:
                # フレーム取得
                ret, frame = self.capture_single_frame()
                
                if ret and frame is not None:
                    # FPS計算
                    self._update_fps_counter()
                    
                    # 物体検出実行
                    counts, annotated_frame = self.monitor.detect_objects(frame)
                    
                    # コールバック実行
                    if callback:
                        callback(annotated_frame, counts)
                    
                    # フレーム情報描画
                    self._draw_frame_info(annotated_frame, counts)
                    
                    # 最新フレーム更新
                    self.latest_frame = annotated_frame
                    
                else:
                    # 接続エラー時の再接続試行
                    self.logger.warning("フレーム取得失敗 - 再接続試行")
                    if not self._reconnect():
                        break
                
                # フレームレート制御
                time.sleep(1.0 / CAMERA_CONFIG['fps'])
                
            except Exception as e:
                self.logger.error(f"ストリーミングエラー: {e}")
                break
        
        self.is_streaming = False
        self.logger.info("ライブストリーミング終了")
    
    def _update_fps_counter(self):
        """FPS計算更新"""
        self.fps_counter += 1
        current_time = time.time()
        
        if current_time - self.last_fps_time >= 1.0:
            self.current_fps = self.fps_counter
            self.fps_counter = 0
            self.last_fps_time = current_time
    
    def _draw_frame_info(self, frame: np.ndarray, counts: dict):
        """フレーム情報描画"""
        try:
            # 背景矩形
            cv2.rectangle(frame, (10, 10), (400, 100), (0, 0, 0), -1)
            cv2.rectangle(frame, (10, 10), (400, 100), (255, 255, 255), 2)
            
            # 情報テキスト
            y_offset = 30
            
            # FPS表示
            fps_text = f"FPS: {getattr(self, 'current_fps', 0)}"
            cv2.putText(frame, fps_text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 20
            
            # 検出数表示
            total_objects = sum(counts.values())
            count_text = f"Total Objects: {total_objects}"
            cv2.putText(frame, count_text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            y_offset += 20
            
            # 各クラスのカウント表示
            for class_name, count in counts.items():
                class_text = f"{class_name}: {count}"
                cv2.putText(frame, class_text, (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                y_offset += 15
                
        except Exception as e:
            self.logger.error(f"フレーム情報描画エラー: {e}")
    
    def stop_live_streaming(self):
        """ライブストリーミング停止"""
        if not self.is_streaming:
            return
        
        self.stop_streaming = True
        
        # スレッド終了待機
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=5.0)
        
        self.is_streaming = False
        self.logger.info("ライブストリーミング停止")
    
    def _reconnect(self) -> bool:
        """再接続試行"""
        if self.current_url is None:
            return False
        
        for attempt in range(NETWORK_CONFIG['retry_attempts']):
            self.logger.info(f"再接続試行 {attempt + 1}/{NETWORK_CONFIG['retry_attempts']}")
            
            if self.connect_camera(self.current_url):
                return True
            
            time.sleep(NETWORK_CONFIG['retry_delay'])
        
        self.logger.error("再接続失敗")
        return False
    
    def test_rtsp_connection(self, rtsp_url: str) -> bool:
        """
        RTSP接続テスト
        
        Args:
            rtsp_url: RTSPストリームURL
            
        Returns:
            bool: 接続テスト結果
        """
        self.logger.info(f"RTSP接続テスト: {rtsp_url}")
        
        try:
            # 一時的な接続テスト
            test_cap = cv2.VideoCapture(rtsp_url)
            test_cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CAMERA_CONFIG['rtsp_timeout'] * 1000)
            
            if test_cap.isOpened():
                ret, frame = test_cap.read()
                test_cap.release()
                
                if ret and frame is not None:
                    self.logger.info("RTSP接続テスト成功")
                    return True
            
            test_cap.release()
            self.logger.error("RTSP接続テスト失敗")
            return False
            
        except Exception as e:
            self.logger.error(f"RTSP接続テストエラー: {e}")
            return False
    
    def get_camera_info(self) -> dict:
        """カメラ情報取得"""
        if not self.is_connected or self.cap is None:
            return {}
        
        try:
            info = {
                'connected': self.is_connected,
                'streaming': self.is_streaming,
                'source': self.current_url,
                'frame_width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'frame_height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': int(self.cap.get(cv2.CAP_PROP_FPS)),
                'frame_count': self.frame_count,
                'current_fps': getattr(self, 'current_fps', 0)
            }
            return info
            
        except Exception as e:
            self.logger.error(f"カメラ情報取得エラー: {e}")
            return {}
    
    def run_continuous_monitoring(self, source, display: bool = True):
        """
        連続監視実行
        
        Args:
            source: カメラソース
            display: 画面表示フラグ
        """
        self.logger.info(f"連続監視開始: {source}")
        
        # カメラ接続
        if not self.connect_camera(source):
            self.logger.error("カメラ接続失敗")
            return
        
        try:
            while True:
                # フレーム取得・処理
                ret, frame = self.capture_single_frame()
                
                if ret and frame is not None:
                    # 物体検出
                    counts, annotated_frame = self.monitor.detect_objects(frame)
                    
                    # フレーム情報描画
                    self._draw_frame_info(annotated_frame, counts)
                    
                    # 画面表示
                    if display:
                        cv2.imshow('Factory Monitor', annotated_frame)
                        
                        # キー入力チェック
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            break
                        elif key == ord('s'):
                            # スクリーンショット保存
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            filename = f"screenshot_{timestamp}.jpg"
                            cv2.imwrite(filename, annotated_frame)
                            print(f"スクリーンショット保存: {filename}")
                    
                    # 検出結果出力
                    if counts:
                        print(f"検出結果: {counts} (合計: {sum(counts.values())}個)")
                
                else:
                    self.logger.warning("フレーム取得失敗")
                    break
                
        except KeyboardInterrupt:
            self.logger.info("ユーザーによる中断")
        except Exception as e:
            self.logger.error(f"監視エラー: {e}")
        finally:
            # クリーンアップ
            self.disconnect_camera()
            if display:
                cv2.destroyAllWindows()


def main():
    """メイン関数 - テスト用"""
    print("=== 工場監視システム - カメラ接続テスト ===")
    
    # モニター初期化
    monitor = FactoryMonitor()
    camera = FactoryCameraConnection(monitor)
    
    print("\n利用可能なカメラソース:")
    print("0: Webカメラ")
    print("1: RTSP URL入力")
    
    choice = input("\n選択してください (0/1): ").strip()
    
    if choice == "0":
        # Webカメラテスト
        print("\nWebカメラで監視を開始します...")
        print("'q'キーで終了、's'キーでスクリーンショット保存")
        camera.run_continuous_monitoring(0)
        
    elif choice == "1":
        # RTSP URLテスト
        rtsp_url = input("RTSP URLを入力してください: ").strip()
        
        if rtsp_url:
            # 接続テスト
            if camera.test_rtsp_connection(rtsp_url):
                print(f"\n{rtsp_url} で監視を開始します...")
                print("'q'キーで終了、's'キーでスクリーンショット保存")
                camera.run_continuous_monitoring(rtsp_url)
            else:
                print("RTSP接続に失敗しました")
        else:
            print("無効なURLです")
    
    else:
        print("無効な選択です")


if __name__ == "__main__":
    main() 