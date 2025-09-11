#!/usr/bin/env python3

import requests
import cv2
import numpy as np
from flask import Flask, render_template_string, jsonify, request, Response, stream_with_context, make_response
import logging
import threading
import time
import base64
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from ultralytics import YOLO
import os
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
import random
from datetime import datetime

# SSL警告を無効化
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# デバッグログ抑止（環境変数 ENABLE_DEBUG_LOG=1 のときのみ有効化）
if os.environ.get('ENABLE_DEBUG_LOG', '0') != '1':
    import builtins as _builtins
    def _noop_print(*args, **kwargs):
        return
    _builtins.print = _noop_print

app = Flask(__name__)
# HTTPアクセスログを抑制（200のアクセスログを出さない）
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# システムの安定性向上のための設定
@app.errorhandler(Exception)
def handle_exception(e):
    """予期しない例外をキャッチしてログ出力"""
    import traceback
    error_msg = f"❌ 予期しない例外が発生: {type(e).__name__}: {str(e)}"
    print(error_msg)
    print("🔍 スタックトレース:")
    traceback.print_exc()
    return jsonify({'error': 'Internal Server Error', 'message': str(e)}), 500

@app.errorhandler(500)
def internal_error(error):
    """500エラーの詳細ログ"""
    print(f"❌ 500エラーが発生: {error}")
    return jsonify({'error': 'Internal Server Error'}), 500

class OptimizedCCTVStream:
    def __init__(self):
        self.cctv_base_url = "http://192.168.0.98:18080"
        self.username = "admin"
        self.password = "admin"
        
        # セッション設定を最適化
        self.session = self._create_optimized_session()
        
        self.model = None
        self.load_yolo_model()
        self.current_frame = None
        self.is_streaming = False
        self.detection_results = []
        self.connection_status = "停止中"
        self.current_view_mode = 16
        self.current_channel = 1
        self.last_frame_time = None
        self.last_yolo_time = 0  # YOLO検知の間引き制御用
        self.processing_interrupted = False
        self.current_processing_task = None
        
        # UI状態の保持（再起動時に復元するため）
        self.ui_state = {
            'view_mode': 1,
            'single_channel_mode': False,
            'selected_channel': 1,
            'is_cycling': False,
        }
        # 単一チャンネル持続ストリーム用
        self.single_stream_running = False
        self.single_stream_channel = None
        self.single_stream_stop = True  # デフォルト停止
        self.single_stream_thread = None
        self.current_single_frame = None
        self.current_single_detections = []
        self.single_last_frame_time = None
        # 接続安定化（再試行・バックオフ）
        self.single_connect_max_retries = 2
        self.single_connect_retry_delay = 0.8
        self.channel_backoff_seconds = 45
        self.channel_backoff_until = {}
        
        # フレームキャッシュ
        self.frame_cache = {}
        self.cache_lock = threading.Lock()
        
        # 持続ストリーム管理
        self.persistent_streams = {}  # チャンネル別の持続ストリーム
        self.stream_threads = {}      # ストリーム処理スレッド
        self.stream_active = {}       # ストリームのアクティブ状態
        self.stream_lock = threading.Lock()
        
        # 実際に動作するチャンネル（循環モード用に6チャンネル対応）
        self.working_channels = [1, 2, 3, 4, 5, 7, 10, 11, 13, 14, 15]
        
        # 循環モード用のチャンネルグループ定義（6画面表示）
        self.cycle_group_a = [2, 3, 4, 7, 11, 14]  # グループA: チャンネル2,3,4,7,11,14
        self.cycle_group_b = [1, 5, 10, 13, 14, 15]  # グループB: チャンネル1,5,10,13,14,15
        
        # ストリーミング制御
        self.max_concurrent_streams = 4  # 同時接続数を制限
        self.executor = ThreadPoolExecutor(max_workers=self.max_concurrent_streams)

        # 推論設定（YOLO検知を有効化）
        self.enable_main_detection = True
        self.enable_single_detection = True

        # ウォッチドッグを有効化（長時間動作の安定性向上）
        self.enable_watchdog = True

    def _create_optimized_session(self):
        """最適化されたHTTPセッションを作成"""
        session = requests.Session()
        session.auth = HTTPBasicAuth(self.username, self.password)
        
        # 接続プール設定
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            # 503が多発するため自動再試行は無効化
            max_retries=Retry(total=0)
        )
        
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # タイムアウト設定
        session.timeout = (5, 10)  # 接続タイムアウト5秒、読み取りタイムアウト10秒
        
        return session

    def reset_session(self):
        """HTTPセッションを再生成して認証・接続状態をリセット"""
        try:
            if hasattr(self, 'session') and self.session is not None:
                try:
                    self.session.close()
                except Exception:
                    pass
        finally:
            self.session = self._create_optimized_session()
        print("🔐 セッションを再生成しました（再ログイン）")

    def interrupt_current_processing(self):
        """現在の分割取得処理を即時中断するためのフラグを立てる"""
        self.processing_interrupted = True
        print("🛑 処理中断要求")

    def test_cctv_connection(self):
        """CCTV接続テスト"""
        try:
            # 明示的なテストは行わず、実際のストリーム取得で判定する方針に変更
            return True
        except Exception:
            return True


    def get_channel_stream_url(self, channel: int) -> str:
        """指定チャンネルの正しいストリームURL（ライブ映像強制）"""
        return f"{self.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&channel={int(channel)}&resolution=1&live=1&realtime=1"
    
    def get_channel_snapshot_url(self, channel: int) -> str:
        """指定チャンネルのスナップショットURL（単一フレーム取得用）"""
        return f"{self.cctv_base_url}/cgi-bin/guest/Video.cgi?media=JPEG&channel={int(channel)}&resolution=1&live=1&realtime=1"


    def get_single_channel_frame_optimized(self, channel, with_detection: bool = False, allow_stale: bool = False, stale_ttl_seconds: int = 30):
        """5011方式に準拠: ライブ映像強制のURLで単一チャンネルを取得
        with_detection=True の場合、YOLOで軽量推論し、枠を描画して返す
        戻り値: (frame_base64: str | None, detections: list)
        """
        try:
            # キャッシュチェック（allow_stale=True の場合はTTLを拡大して使用）
            with self.cache_lock:
                if channel in self.frame_cache:
                    cache_time, cached_frame = self.frame_cache[channel]
                    ttl = stale_ttl_seconds if allow_stale else 0.5
                    if time.time() - cache_time < ttl:
                        return cached_frame, []

            # 実際のCCTV接続を試行
            try:
                if channel == "all16":
                    # 16チャンネル統合は環境依存のためフォールバックせずNone
                    return None, []
                else:
                    ch_num = int(channel) if isinstance(channel, (int, str)) and str(channel).isdigit() else 1
                    stream_url = self.get_channel_stream_url(ch_num)
                
                # バックオフ中なら即スキップ（allow_stale時はキャッシュ返却を試みる）
                until = self.channel_backoff_until.get(ch_num, 0)
                if until and time.time() < until:
                    remain = int(until - time.time())
                    print(f"⏳ CH{ch_num} バックオフ中（残り{remain}秒）")
                    if allow_stale:
                        with self.cache_lock:
                            if channel in self.frame_cache:
                                cache_time, cached_frame = self.frame_cache[channel]
                                if time.time() - cache_time < stale_ttl_seconds:
                                    return cached_frame, []
                    return None, []

                print(f"🔗 CH{channel} CCTV接続試行: {stream_url}")

                # スナップショット取得（単一フレーム、適切なタイムアウト）
                snapshot_url = self.get_channel_snapshot_url(ch_num)
                response = self.session.get(snapshot_url, timeout=(3, 5))
                
                if response.status_code == 200:
                    print(f"✅ CH{channel} CCTVスナップショット取得成功")
                    
                    # JPEGデータを直接取得
                    jpeg_data = response.content
                    
                    # JPEGヘッダー確認
                    if len(jpeg_data) > 10 and jpeg_data[:2] == b'\xff\xd8' and jpeg_data[-2:] == b'\xff\xd9':
                        detections_local = []
                        frame_bytes_to_send = jpeg_data
                        
                        if with_detection and self.model is not None:
                            try:
                                img_array = np.frombuffer(jpeg_data, np.uint8)
                                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                if frame is not None:
                                    processed_frame, detections_local = self.detect_objects_fast(frame)
                                    _, buffer_encoded = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                    frame_bytes_to_send = buffer_encoded.tobytes()
                            except Exception as e:
                                print(f"❌ 単一推論エラー: {e}")
                        
                        frame_base64 = base64.b64encode(frame_bytes_to_send).decode('utf-8')
                        
                        # キャッシュに保存
                        with self.cache_lock:
                            self.frame_cache[channel] = (time.time(), frame_base64)
                            # 60秒以上古いキャッシュを削除
                            current_time = time.time()
                            expired_channels = [ch for ch, (t, _) in self.frame_cache.items() if current_time - t > 60]
                            for ch in expired_channels:
                                del self.frame_cache[ch]
                        
                        print(f"📹 CH{channel} スナップショット処理完了")
                        return frame_base64, detections_local
                    else:
                        print(f"❌ CH{channel} 無効なJPEGデータ")
                        return None, []
                else:
                    print(f"⚠️ CH{channel} HTTPエラー {response.status_code}")
                    if response.status_code == 503:
                        # チャンネル別バックオフ設定
                        self.channel_backoff_until[ch_num] = time.time() + self.channel_backoff_seconds
                        print(f"⛔ CH{ch_num} を {self.channel_backoff_seconds}秒 バックオフ")
                    return None, []
                    
            except requests.exceptions.Timeout:
                print(f"⏰ CH{channel} CCTV接続タイムアウト: {stream_url}")
                return None, []
            except requests.exceptions.ConnectionError:
                print(f"🔌 CH{channel} CCTV接続エラー: {stream_url}")
                # 短期バックオフ（接続系）
                try:
                    self.channel_backoff_until[ch_num] = time.time() + min(30, self.channel_backoff_seconds // 4)
                except Exception:
                    pass
                return None, []
            except Exception as e:
                print(f"❌ CH{channel} CCTV接続例外: {str(e)[:100]}")
                return None, []
            
            # 実際のCCTV接続のみ、フォールバックなし
            print(f"❌ CH{channel} 実際のCCTV接続失敗")
            return None, []
            
        except Exception as e:
            print(f"❌ CH{channel} 取得エラー: {e}")
            return None, []

    def get_specific_channels_frames(self, channel_list, with_detection=False):
        """指定されたチャンネルのフレームを取得（循面用・毎秒更新対応版）"""
        print(f"🔄 指定チャンネル毎秒更新取得開始: {channel_list}")
        frames = {}
        
        # まずキャッシュから可能な限り取得（短時間キャッシュで毎秒更新に対応）
        for ch in channel_list:
            with self.cache_lock:
                if ch in self.frame_cache:
                    cache_time, cached_frame = self.frame_cache[ch]
                    if time.time() - cache_time < 2:  # 2秒キャッシュで毎秒更新
                        frames[ch] = cached_frame
                        print(f"✅ CH{ch} キャッシュから取得成功")
        
        # キャッシュにないチャンネルのみ新規取得（並列処理で高速化）
        missing_channels = [ch for ch in channel_list if ch not in frames]
        if missing_channels:
            print(f"🔄 新規取得が必要なチャンネル: {missing_channels}")
            
            # 並列処理で4画面を同時取得（毎秒更新に対応）
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_channel = {
                    executor.submit(self._get_channel_frame_with_detection, ch, with_detection): ch 
                    for ch in missing_channels
                }
                
                for future in as_completed(future_to_channel):
                    ch = future_to_channel[future]
                    try:
                        frame_b64 = future.result()
                        if frame_b64:
                            frames[ch] = frame_b64
                            print(f"✅ CH{ch} 並列取得成功")
                        else:
                            print(f"⚠️ CH{ch} 並列取得失敗")
                    except Exception as e:
                        print(f"❌ CH{ch} 並列取得エラー: {e}")
        
        print(f"🔄 指定チャンネル毎秒更新取得完了: {sorted(list(frames.keys()))} ({len(frames)}枚)")
        return frames
    
    def _get_channel_frame_fast(self, channel):
        """高速チャンネルフレーム取得（毎秒更新用）"""
        try:
            # 短時間キャッシュチェック
            with self.cache_lock:
                if channel in self.frame_cache:
                    cache_time, cached_frame = self.frame_cache[channel]
                    if time.time() - cache_time < 1:  # 1秒キャッシュ
                        return cached_frame
            
            # 高速スナップショット取得
            ch_num = int(channel) if isinstance(channel, (int, str)) and str(channel).isdigit() else 1
            snapshot_url = self.get_channel_snapshot_url(ch_num)
            
            response = self.session.get(snapshot_url, timeout=(2, 3))  # 短いタイムアウト
            
            if response.status_code == 200:
                jpeg_data = response.content
                if len(jpeg_data) > 10 and jpeg_data[:2] == b'\xff\xd8' and jpeg_data[-2:] == b'\xff\xd9':
                    frame_base64 = base64.b64encode(jpeg_data).decode('utf-8')
                    
                    # 短時間キャッシュに保存
                    with self.cache_lock:
                        self.frame_cache[channel] = (time.time(), frame_base64)
                    
                    return frame_base64
            
            return None
            
        except Exception as e:
            print(f"❌ CH{channel} 高速取得エラー: {e}")
            return None

    def _get_channel_frame_with_detection(self, channel, with_detection=False):
        """YOLO検知付きチャンネルフレーム取得（循面用）"""
        try:
            # 短時間キャッシュチェック
            with self.cache_lock:
                if channel in self.frame_cache:
                    cache_time, cached_frame = self.frame_cache[channel]
                    if time.time() - cache_time < 1:  # 1秒キャッシュ
                        return cached_frame
            
            # 高速スナップショット取得
            ch_num = int(channel) if isinstance(channel, (int, str)) and str(channel).isdigit() else 1
            snapshot_url = self.get_channel_snapshot_url(ch_num)
            
            response = self.session.get(snapshot_url, timeout=(2, 3))  # 短いタイムアウト
            
            if response.status_code == 200:
                jpeg_data = response.content
                if len(jpeg_data) > 10 and jpeg_data[:2] == b'\xff\xd8' and jpeg_data[-2:] == b'\xff\xd9':
                    frame_base64 = base64.b64encode(jpeg_data).decode('utf-8')
                    
                    # YOLO検知が有効な場合のみ実行
                    if with_detection and self.enable_single_detection:
                        try:
                            img_array = np.frombuffer(jpeg_data, np.uint8)
                            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            
                            if frame is not None:
                                processed_frame, detections = self.detect_objects_fast(frame)
                                
                                _, buffer_encoded = cv2.imencode('.jpg', processed_frame, 
                                                               [cv2.IMWRITE_JPEG_QUALITY, 80])
                                frame_base64 = base64.b64encode(buffer_encoded).decode('utf-8')
                                
                                # 検知結果をログ出力
                                if len(detections) > 0:
                                    print(f"🔍 CH{channel} YOLO検知: {len(detections)} objects detected")
                        except Exception as e:
                            print(f"❌ CH{channel} YOLO検知処理エラー: {e}")
                    
                    # 短時間キャッシュに保存
                    with self.cache_lock:
                        self.frame_cache[channel] = (time.time(), frame_base64)
                    
                    return frame_base64
            
            return None
            
        except Exception as e:
            print(f"❌ CH{channel} YOLO検知付き取得エラー: {e}")
            return None
    
    def _get_channel_frame_with_retry(self, channel):
        """チャンネルフレーム取得（リトライ付き）"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # キャッシュチェック
                with self.cache_lock:
                    if channel in self.frame_cache:
                        cache_time, cached_frame = self.frame_cache[channel]
                        if time.time() - cache_time < 30:  # 30秒キャッシュ
                            return cached_frame
                
                # 実際の取得（キャッシュを有効活用）
                frame_b64, _ = self.get_single_channel_frame_optimized(
                    channel, with_detection=False, allow_stale=True, stale_ttl_seconds=30
                )
                return frame_b64
                
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"🔄 CH{channel} リトライ {attempt + 1}/{max_retries}")
                    time.sleep(0.5)  # 短い待機
                else:
                    print(f"❌ CH{channel} 最終失敗: {e}")
                    return None

    def get_multi_channel_frames_parallel(self, num_channels):
        """5011方式に寄せて、各CHをライブ強制URLで個別取得（並列）"""
        print(f"🎬 並列ストリーミング開始 ({num_channels}画面)")
        # 中断フラグを処理開始時にリセット
        self.processing_interrupted = False
        self.current_processing_task = f"multi_channel_{num_channels}"

        channels_to_fetch = [ch for ch in range(1, min(num_channels + 1, 17))]
        frames = {}

        # 並列数を絞る（CCTV側負荷/接続制限を回避）
        # 16同時は不可。順次取得（並列1）で確実に拾う
        # 並列1（実質順次）でインタラプトに対応
        for ch in channels_to_fetch:
            if self.processing_interrupted:
                print(f"🛑 CH{ch}処理中断 - 新しい処理に切替")
                break
            # グリッドではバックオフ中も最大30秒のキャッシュを許容
            frame_b64, _ = self.get_single_channel_frame_optimized(ch, with_detection=False, allow_stale=True, stale_ttl_seconds=30)
            if frame_b64:
                frames[ch] = frame_b64

        print(f"✅ 並列取得完了: {sorted(list(frames.keys()))} ({len(frames)}枚)")
        # 1枚も取れなければ順次フォールバック
        # 0枚の場合もそのまま返す（ログのみ最小限）
        return frames

    def load_yolo_model(self):
        """YOLOモデル読み込み"""
        try:
            model_path = 'yolo11n.pt'
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print("✅ YOLO11モデル読み込み成功")
            else:
                print("❌ YOLOモデルファイルが見つかりません")
                self.model = None
        except Exception as e:
            print(f"❌ YOLOモデル読み込みエラー: {e}")
            self.model = None  # モデルが読み込めない場合はNoneに設定

    def detect_objects_fast(self, frame):
        """高速YOLO物体検出"""
        if self.model is None:
            return frame, []
        
        try:
            height, width = frame.shape[:2]
            scale_factor = 0.5
            small_frame = cv2.resize(frame, (int(width * scale_factor), int(height * scale_factor)))
            
            results = self.model(small_frame, verbose=False, imgsz=256)
            detections = []
            # 許可クラスとクラス別しきい値
            allowed_class_ids = {0, 1, 2, 5, 6, 7}  # person, bicycle, car, bus, train, truck
            person_conf_threshold = 0.2
            default_conf_threshold = 0.5
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = int(box.cls[0].cpu().numpy())
                        # クラスフィルタ
                        if cls not in allowed_class_ids:
                            continue
                        # クラス別しきい値
                        threshold = person_conf_threshold if cls == 0 else default_conf_threshold
                        if conf > threshold:
                            x1, y1, x2, y2 = int(x1/scale_factor), int(y1/scale_factor), int(x2/scale_factor), int(y2/scale_factor)
                            
                            class_name = self.model.names[cls]
                            detections.append({
                                'class': class_name,
                                'confidence': float(conf),
                                'bbox': [x1, y1, x2, y2]
                            })
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            label = f'{class_name}'
                            cv2.putText(frame, label, (x1, y1 - 10), 
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            return frame, detections
            
        except Exception as e:
            print(f"❌ YOLO検出エラー: {e}")
            return frame, []

    def start_persistent_streams(self):
        """16チャンネルの持続ストリームを並行開始"""
        print("🚀 16チャンネル持続ストリーム開始")
        
        with self.stream_lock:
            for ch in self.working_channels:
                if ch not in self.stream_active or not self.stream_active[ch]:
                    self.stream_active[ch] = True
                    thread = threading.Thread(target=self._persistent_stream_worker, args=(ch,), daemon=True)
                    thread.start()
                    self.stream_threads[ch] = thread
                    print(f"✅ CH{ch} 持続ストリーム開始")
        
        print("🎬 全チャンネル持続ストリーム開始完了")
    
    def stop_persistent_streams(self):
        """全チャンネルの持続ストリームを停止"""
        print("🛑 全チャンネル持続ストリーム停止")
        
        with self.stream_lock:
            for ch in self.working_channels:
                self.stream_active[ch] = False
                if ch in self.stream_threads:
                    self.stream_threads[ch].join(timeout=1.0)
                    del self.stream_threads[ch]
                    print(f"🛑 CH{ch} 持続ストリーム停止")
    
    def _persistent_stream_worker(self, channel):
        """チャンネル別の持続ストリーム処理ワーカー"""
        print(f"🔄 CH{channel} 持続ストリームワーカー開始")
        
        while self.stream_active.get(channel, False):
            try:
                # 持続的なMJPEGストリームからフレームを取得
                stream_url = self.get_channel_stream_url(channel)
                response = self.session.get(stream_url, stream=True, timeout=(5, 10))
                
                if response.status_code == 200:
                    buffer = b''
                    for chunk in response.iter_content(chunk_size=8192):
                        if not self.stream_active.get(channel, False):
                            break
                        
                        buffer += chunk
                        
                        # JPEGフレームを検索
                        start = buffer.find(b'\xff\xd8')
                        end = buffer.find(b'\xff\xd9')
                        
                        if start != -1 and end != -1 and end > start:
                            jpeg_data = buffer[start:end+2]
                            buffer = buffer[end+2:]
                            
                            # フレームをbase64エンコードしてキャッシュに保存
                            frame_base64 = base64.b64encode(jpeg_data).decode('utf-8')
                            
                            with self.cache_lock:
                                self.frame_cache[channel] = (time.time(), frame_base64)
                            
                            # 短い待機（フレームレート制御）
                            time.sleep(0.1)
                
                response.close()
                
            except Exception as e:
                print(f"❌ CH{channel} 持続ストリームエラー: {e}")
                time.sleep(1.0)  # エラー時は少し待機
        
        print(f"🔄 CH{channel} 持続ストリームワーカー終了")
    
    def start_optimized_stream(self):
        """最適化されたストリーム開始（メインストリーム方式）"""
        # 持続ストリームは無効化（接続エラー対策）
        # self.start_persistent_streams()
        self.is_streaming = True
        print("✅ メインストリーム方式でストリーミング開始")
        
        # フレームが一定時間来ていなければ強制リセットして再スタート
        if self.is_streaming and self.last_frame_time and (time.time() - self.last_frame_time) > 5:
            print("♻️ フレーム停止検知 → 再ログインして再起動します")
            self.stop_stream()
            self.reset_session()
        elif self.is_streaming and self.current_frame:
            print("ℹ️ 正常にストリーミング中のため /start_stream は何もしません")
            return True

        self.is_streaming = True
        
        def stream_worker():
            try:
                print("🎥 最適化ストリーム開始")
                self.connection_status = "ストリーミング中"
                
                frame_count = 0
                last_yolo_time = time.time()
                
                # メインストリーム用URL（ライブ強制）
                timestamp = int(time.time())
                main_stream_url = (
                    f"{self.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&nocache={timestamp}"
                )
                
                # 読み取りは長め。CCTVの無送出に耐えて切断しにくくする
                # 要件: 単体取得の読み取りタイムアウト10秒
                response = self.session.get(main_stream_url, stream=True, timeout=(5, 10))
                
                if response.status_code == 200:
                    print("✅ メインストリーム接続成功")
                    buffer = b''
                    
                    for chunk in response.iter_content(chunk_size=4096):
                        if not self.is_streaming:
                            break
                            
                        buffer += chunk
                        
                        while True:
                            start = buffer.find(b'\xff\xd8')
                            end = buffer.find(b'\xff\xd9')
                            
                            if start != -1 and end != -1 and end > start:
                                jpeg_data = buffer[start:end+2]
                                buffer = buffer[end+2:]
                                
                                # まず即表示（エンコードし直さない）
                                self.current_frame = base64.b64encode(jpeg_data).decode('utf-8')
                                self.last_frame_time = time.time()
                                # YOLO処理（間引き）
                                current_time = time.time()
                                if self.enable_main_detection and (current_time - last_yolo_time) >= 2.0:
                                    img_array = np.frombuffer(jpeg_data, np.uint8)
                                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                    
                                    if frame is not None:
                                        processed_frame, detections = self.detect_objects_fast(frame)
                                        
                                        _, buffer_encoded = cv2.imencode('.jpg', processed_frame, 
                                                                       [cv2.IMWRITE_JPEG_QUALITY, 80])
                                        self.current_frame = base64.b64encode(buffer_encoded).decode('utf-8')
                                        self.detection_results = detections
                                        
                                        last_yolo_time = current_time
                                        frame_count += 1
                                        
                                        if frame_count % 30 == 0:
                                            print(f"🖼️ フレーム {frame_count}: {len(detections)} objects detected")
                            else:
                                break
                else:
                    print(f"❌ メインストリーム接続失敗: {response.status_code}")
                    self.connection_status = f"HTTP {response.status_code} エラー"
                    
            except Exception as e:
                print(f"❌ ストリームエラー: {e}")
                self.connection_status = f"エラー: {str(e)}"
            finally:
                self.is_streaming = False
                print("🔴 ストリーム停止")
        
        thread = threading.Thread(target=stream_worker, daemon=True)
        thread.start()
        return True

    def stop_stream(self):
        """ストリーム停止"""
        self.is_streaming = False
        self.current_frame = None
        self.detection_results = []
        self.connection_status = "停止中"
        
        # キャッシュクリア
        with self.cache_lock:
            self.frame_cache.clear()

    def change_view_mode(self, view_mode):
        """表示モード変更"""
        self.current_view_mode = view_mode
        print(f"🔧 表示モード変更: {view_mode}")
        return True

    def start_single_channel_stream(self, channel: int) -> bool:
        # 持続ストリームは使用しない（503対策）。スナップショット方式のみ使用。
        print("ℹ️ 単一持続ストリームは無効化（スナップショット方式のみ）")
        return True

    def stop_single_channel_stream(self) -> bool:
        self.single_stream_stop = True
        self.single_stream_running = False
        self.single_stream_channel = None
        self.current_single_detections = []
        return True

# グローバルインスタンス
cctv_system = OptimizedCCTVStream()

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI-DETECT-MONITOR</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: white; color: #333; }
            .container { max-width: 1400px; margin: 0 auto; }
            .header { display: flex; align-items: center; margin-bottom: 4px; }
            .logo { height: 63px; width: auto; margin-right: 15px; }
            .title-container { flex: 1; text-align: center; }
            h1 { font-size: 24px; margin: 0; color: #2c3e50; font-weight: 900; }
            .status-info { background: #f8f9fa; border: 2px solid #17a2b8; border-radius: 10px; padding: 15px; margin: 20px 0; text-align: center; font-weight: bold; color: #17a2b8; }
            .status-info.success { border-color: #28a745; color: #28a745; }
            .status-info.error { border-color: #dc3545; color: #dc3545; }
            .controls { text-align: center; margin: 20px 0; }
            .btn { padding: 12px 24px; margin: 10px; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer; transition: all 0.3s; }
            .btn:hover { transform: translateY(-2px); }
            .btn-success { background: #28a745; color: white; }
            .btn-danger { background: #dc3545; color: white; }
            .video-container { margin: 4px 0; }
            .video-section { background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 10px; padding: 10px; }
            .video-frame { width: 100%; height: 420px; object-fit: contain; border-radius: 8px; background: #fff; }
            .detection-panel { background: #f8f9fa; border: 2px solid #dee2e6; border-radius: 10px; padding: 20px; margin: 20px 0; }
            .detection-item { background: white; margin: 8px 0; padding: 12px; border-radius: 6px; display: flex; justify-content: space-between; border: 1px solid #dee2e6; }
            .view-controls { display: flex; align-items: center; justify-content: center; gap: 12px; margin: 16px 0; flex-wrap: wrap; row-gap: 10px; }
            .view-btn { padding: 10px 20px; margin: 0 4px; border: 2px solid #007bff; border-radius: 14px; background: white; color: #007bff; font-weight: 800; cursor: pointer; transition: all 0.3s; font-size: 16px; }
            .view-btn:hover { background: #007bff; color: white; }
            .view-btn.active { background: #007bff; color: white; }
            .grid-container { display: grid; gap: 2px; background: #fff; border-radius: 8px; overflow: hidden; }
            .grid-4 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
            .grid-6 { grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr; }
            .grid-9 { grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr 1fr; }
            .grid-16 { grid-template-columns: 1fr 1fr 1fr 1fr; grid-template-rows: 1fr 1fr 1fr 1fr; }
            .grid-item { background: #fff; min-height: 120px; display: flex; align-items: center; justify-content: center; color: #6c757d; font-size: 12px; }
            
            /* 循拡用の1.5倍拡大スタイル（6画面表示：3列×2行） */
            .cycle-expanded { 
                grid-template-columns: 1fr 1fr 1fr !important; /* 3列に修正！ */
                grid-template-rows: 1fr 1fr !important; /* 2行を維持 */
                height: 100vh; /* 画面全体の高さを使用 */
                margin: 0;
                padding: 0;
                gap: 4px; /* グリッド間の隙間 */
            }
            .cycle-expanded .grid-item { 
                min-height: 50vh; /* 画面高さの50% */
                font-size: 18px; /* 12px * 1.5 = 18px */
                display: flex !important; /* 強制表示 */
                align-items: center;
                justify-content: center;
                background: #000; /* 背景色 */
                border-radius: 8px;
                overflow: hidden;
            }
            .cycle-expanded .grid-item img { 
                width: 100%; 
                height: 100%; 
                object-fit: cover; 
                border-radius: 8px; 
            }
            /* 非表示にするグリッドアイテム（6画面表示用に修正） */
            .cycle-expanded .grid-item:nth-child(n+7) {
                display: none !important;
            }
            /* 循拡モード時のヘッダー非表示 */
            .cycle-expanded-mode .header {
                display: none !important;
            }
            .cycle-expanded-mode .controls {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border-top: 2px solid #17a2b8;
                z-index: 1000;
                padding: 10px;
                margin: 0;
            }
            .cycle-expanded-mode .video-container {
                margin: 0;
                height: 100vh;
            }
            .cycle-expanded-mode .video-section {
                border: none;
                border-radius: 0;
                padding: 0;
                height: 100vh;
            }
            /* 画面を上に詰めるための最小高さ調整（モバイルでも見やすく） */
            @media (max-width: 480px) {
              .video-frame { height: 360px; }
              #noVideo { line-height: 360px !important; }
            }
            .channel-select { display: grid; justify-content: center; margin-top: 12px; gap: 6px; 
                              grid-template-columns: repeat(16, 40px); grid-auto-rows: 36px; 
                              place-items: center; }
            .ch-btn { width: 40px; height: 36px; border: 2px solid #007bff; border-radius: 8px; background: white; color: #007bff; font-weight: 800; cursor: pointer; display:inline-flex; align-items:center; justify-content:center; }
                        .ch-btn.active { background: #007bff; color: white; }
            
            /* リモコンUI用スタイル */
            .remote-panel { 
                background: #f8f9fa; 
                border: 2px solid #17a2b8; 
                border-radius: 10px; 
                padding: 20px; 
                margin: 20px 0; 
                text-align: center; 
            }
            .remote-modes { 
                display: grid; 
                grid-template-columns: repeat(2, 1fr); 
                gap: 15px; 
                margin: 20px 0; 
            }
            .remote-mode-btn { 
                padding: 15px 20px;
                border: 2px solid #17a2b8; 
                border-radius: 10px; 
                background: white; 
                color: #17a2b8; 
                font-weight: 800; 
                cursor: pointer; 
                font-size: 14px; 
                transition: all 0.3s; 
            }
            .remote-mode-btn:hover { 
                background: #17a2b8; 
                color: white; 
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(23, 162, 184, 0.3);
            }
            .remote-actions { 
                margin-top: 20px; 
            }
            .remote-action-btn { 
                padding: 10px 20px; 
                border: 2px solid #6c757d; 
                border-radius: 8px; 
                background: white; 
                color: #6c757d; 
                font-weight: 600; 
                cursor: pointer; 
                transition: all 0.3s; 
            }
            .remote-action-btn:hover { 
                background: #6c757d; 
                color: white; 
            }
            
            @media (max-width: 900px) {
              .channel-select { grid-template-columns: repeat(8, 40px); }
              .view-btn { padding: 8px 14px; font-size: 15px; border-radius: 12px; }
              .view-controls { gap: 8px; row-gap: 8px; }
            }
            
            /* ティッカー表示用スタイル */
            .ticker-container {
                background: rgba(0, 0, 0, 0.95);
                color: white;
                padding: 8px 12px;
                margin: 8px 0;
                border-radius: 8px;
                font-size: 14px;
                line-height: 1.2;
            }
            
            .ticker-content {
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }
            
            .ticker-item {
                flex: 1;
                min-width: 300px;
            }
            
            .ticker-label {
                font-weight: bold;
                margin-bottom: 4px;
                animation: blink 6s ease-in-out infinite;
            }
            
            .ticker-text {
                margin: 2px 0;
                animation: blink 6s ease-in-out infinite;
                animation-delay: calc(var(--delay) * 0.3s);
                font-size: 16px;
            }
            
            .ticker-text:nth-child(1) { --delay: 1; }
            .ticker-text:nth-child(2) { --delay: 2; }
            .ticker-text:nth-child(3) { --delay: 3; }
            
            /* ステータスアイコン */
            .status-icon {
                margin-right: 8px;
                font-size: 14px;
            }
            
            .status-complete {
                color: #28a745;
            }
            
            .status-in-progress {
                color: #ffc107;
            }
            
            .status-pending {
                color: #dc3545;
            }
            
            /* テキスト色 */
            .ticker-text.complete {
                color: #28a745;
            }
            
            .ticker-text.in-progress {
                color: #ffc107;
            }
            
            .ticker-text.pending {
                color: #dc3545;
            }
            
            /* 点滅アニメーション */
            @keyframes blink {
                0% { opacity: 0.5; }
                20% { opacity: 1; }
                60% { opacity: 1; }
                100% { opacity: 0.5; }
            }
            
            /* 循拡モード時のティッカー */
            .cycle-expanded-mode .ticker-container {
                background: rgba(0, 0, 0, 0.95);
                position: fixed;
                top: 10px;
                left: 10px;
                right: 10px;
                z-index: 1001;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img class="logo" src="/static/kirii_logo.png" alt="KIRII Logo">
                <div class="title-container">
                    <h1>AI-DETECT-MONITOR</h1>
                </div>
            </div>
            
            <!-- ティッカー表示 -->
            <div id="tickerContainer" class="ticker-container">
                <div class="ticker-content">
                    <div class="ticker-item">
                        <div class="ticker-label">本日生産</div>
                                                    <div class="ticker-text complete">
                                <span class="status-icon status-complete">●</span>
                                K#2504035 0.40x64 0.4x32x32AL批灰角24400-519-生産完
                            </div>
                            <div class="ticker-text in-progress">
                                <span class="status-icon status-in-progress">●</span>
                                K#2412168 0.40x64 0.4x32x32AL批灰角24400-300-生産中
                            </div>
                            <div class="ticker-text pending">
                                <span class="status-icon status-pending">●</span>
                                K#2412300 0.40x64 0.4x32x32AL批灰角24400-250-未生産
                            </div>
                    </div>
                    <div class="ticker-item">
                        <div class="ticker-label">本日出貨</div>
                                                    <div class="ticker-text pending">
                                <span class="status-icon status-pending">●</span>
                                SC/20250B/64 50mm企筒2440mm45高1.5厚(藍帯)用料147.0mm-40支-未出貨
                            </div>
                            <div class="ticker-text complete">
                                <span class="status-icon status-complete">●</span>
                                SC/20250B/65 50mm企筒2440mm45高1.5厚(藍帯)用料138.2mm-10支-出貨完
                            </div>
                            <div class="ticker-text complete">
                                <span class="status-icon status-complete">●</span>
                                SC/20250B/75 76mm企筒2440mm45高1.2厚(-帯)用料172.0mm-30支-出貨完
                            </div>
                    </div>
                </div>
            </div>
            
            <div class="video-container" style="margin-bottom: 0;">
                <div class="video-section">
                    <!-- 單一畫面 -->
                    <div id="singleView" class="video-display">
                        <img id="videoFrame" class="video-frame" style="display: none;" alt="CCTV YOLO Stream">
                        <div id="noVideo" style="text-align: center; line-height: 420px; color: #6c757d; font-size: 18px;">沒有影像</div>
                    </div>
                    
                    
                    <!-- 分割畫面 -->
                    <div id="gridView" class="grid-container grid-6" style="display: none; height: 500px; grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr;">
                        <div class="grid-item" id="grid0">CH1</div>
                        <div class="grid-item" id="grid1">CH2</div>
                        <div class="grid-item" id="grid2">CH3</div>
                        <div class="grid-item" id="grid3">CH4</div>
                        <div class="grid-item" id="grid4">CH5</div>
                        <div class="grid-item" id="grid5">CH6</div>
                    </div>

                    
                </div>
            </div>
            
            <div class="view-controls">
                <button id="controlBtn" class="btn btn-success" onclick="toggleStream()">開控</button>
                <button class="view-btn" onclick="refreshMain()" id="btnMain">主面</button>
                <button class="view-btn" onclick="changeView(4)" id="view4">4面</button>
                <button class="view-btn" onclick="changeView(9)" id="view9">9面</button>
                <button class="view-btn" onclick="toggleCycle()" id="btnCycle">循面</button>
                <button class="view-btn" onclick="toggleCycleExpanded()" id="btnCycleExpanded">循拡</button>
                <button class="view-btn" onclick="toggleRemote()" id="btnRemote">遙控</button>
                <button id="debugLogBtn" class="view-btn" onclick="toggleDebugLog()">Log-on</button>
            </div>

            <div id="channelSelector" class="channel-select" style="display:grid;">
                <button class="ch-btn" onclick="selectChannel(1)" id="ch1">1</button>
                <button class="ch-btn" onclick="selectChannel(2)" id="ch2">2</button>
                <button class="ch-btn" onclick="selectChannel(3)" id="ch3">3</button>
                <button class="ch-btn" onclick="selectChannel(4)" id="ch4">4</button>
                <button class="ch-btn" onclick="selectChannel(5)" id="ch5">5</button>
                <button class="ch-btn" onclick="selectChannel(6)" id="ch6">6</button>
                <button class="ch-btn" onclick="selectChannel(7)" id="ch7">7</button>
                <button class="ch-btn" onclick="selectChannel(8)" id="ch8">8</button>
                <button class="ch-btn" onclick="selectChannel(9)" id="ch9">9</button>
                <button class="ch-btn" onclick="selectChannel(10)" id="ch10">10</button>
                <button class="ch-btn" onclick="selectChannel(11)" id="ch11">11</button>
                <button class="ch-btn" onclick="selectChannel(12)" id="ch12">12</button>
                <button class="ch-btn" onclick="selectChannel(13)" id="ch13">13</button>
                <button class="ch-btn" onclick="selectChannel(14)" id="ch14">14</button>
                <button class="ch-btn" onclick="selectChannel(15)" id="ch15">15</button>
                <button class="ch-btn" onclick="selectChannel(16)" id="ch16">16</button>
            </div>
            
            <!-- CCTVサーバー側表示モード切り替えパネル -->
            <div id="remoteControlPanel" class="remote-panel" style="display: none;">
                <h3 style="color: #2c3e50; margin-top: 0; text-align: center;">🎮 CCTVサーバー遙控操作</h3>
                <div class="remote-modes">
                    <button class="remote-mode-btn" onclick="remoteSelectMode('full')">Full Sequence</button>
                    <button class="remote-mode-btn" onclick="remoteSelectMode('quarter')">Quarter Sequence</button>
                    <button class="remote-mode-btn" onclick="remoteSelectMode('4cut')">4 Cut</button>
                    <button class="remote-mode-btn" onclick="remoteSelectMode('9cut')">9 Cut</button>
                    <button class="remote-mode-btn" onclick="remoteSelectMode('16cut')">16 Cut</button>
                </div>
                <div class="remote-actions">
                    <button class="remote-action-btn" onclick="closeRemote()">閉じる</button>
                </div>
            </div>
            

            
            <div class="detection-panel" style="margin-top: 12px;">
                <h3 style="color: #2c3e50; margin-top: 0;">🎯 即時檢測結果</h3>
                <div id="detectionList">
                    <div style="color: #6c757d; text-align: center; padding: 20px;">沒有檢測到物件</div>
                </div>
            </div>
            
            <div id="status" class="status-info">
                🔧 最適化CCTV監視システム準備完了（自動接続中...）
            </div>
        </div>
        
        <script>
            let updateInterval = null;
            let isStreaming = false;
            // デフォルトはメインストリーム表示（分割はボタン押下時のみ）
            let currentView = 1;
            let inflightFrame = false;
            let multiChannelInterval = null;
            let singleInterval = null;
            let inflightSingle = false;
            let singleChannelMode = false; // デフォルトはメインストリーム表示
            let selectedChannel = 1;
            // cycleIntervalは統合されたタイマーに統合済み
            let isCycling = false;
            // 循面用のチャンネルグループ定義（6画面表示）
            const cycleGroupA = [2, 3, 4, 7, 11, 14];  // グループA: チャンネル2,3,4,7,11,14
            const cycleGroupB = [1, 5, 10, 13, 14, 15]; // グループB: チャンネル1,5,10,13,14,15
            const cycleList = [1,3,4,5,7,10,11,13,14,15]; // 旧実装用（互換性保持）
            let cycleIndex = 0;
            let cycleGroupIndex = 0; // 循面グループインデックス
            let cycling = false; // 予約用（未使用）
            let lastCycleSwitchAt = 0; // 循環の実スイッチ時刻（デバウンス）
            let isCycleExpanded = false; // 循拡モードフラグ
            let autoResetInterval = null; // 自動リセット用（現在は無効化）
            let lastResetTime = Date.now();
            
            
            function toggleStream() {
                if (isStreaming) {
                    stopStream();
                } else {
                    startStream();
                }
            }
            
            function startStream() {
                updateStatus('🎥 CCTV連接中...', 'info');
                
                fetch('/start_stream', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateStatus('✅ 最適化監控中', 'success');
                        isStreaming = true;
                        // 要件: メインは5秒間隔（安定性向上）
                        updateInterval = setInterval(updateFrame, 5000);
                        
                        const btn = document.getElementById('controlBtn');
                        btn.textContent = '停控';
                        btn.className = 'btn btn-danger';
                        
                        // 起動直後はメインストリームを維持（単一は数字押下時のみ）
                        
                        // 自動リセット機能は無効化（システム安定性向上）
                        // startAutoReset();
                    } else {
                        updateStatus('❌ 監控啟動失敗', 'error');
                    }
                });
            }

            function startAutoReset() {
                // 自動リセット機能を無効化（システム安定性のため）
                if (autoResetInterval) clearInterval(autoResetInterval);
                autoResetInterval = null;
                console.log('🔧 自動リセット機能を無効化しました（システム安定性向上）');
            }

            function performAutoReset() {
                // 自動リセット機能を無効化（システム安定性のため）
                console.log('🔧 自動リセット機能は無効化されています');
                return;
            }

            // ページ読込時に再ログイン→メインストリーム開始（安定化）
            window.addEventListener('load', async () => {
                // 自動接続は行わず、ユーザーが「開控」を押した時だけ開始する
                changeView(1);
                updateStatus('🔧 最適化CCTV監視システム準備完了（待機中）', 'info');
            });
            
            function stopStream() {
                if (updateInterval) {
                    clearInterval(updateInterval);
                    updateInterval = null;
                }
                
                if (multiChannelInterval) {
                    clearInterval(multiChannelInterval);
                    multiChannelInterval = null;
                }
                
                isStreaming = false;
                stopSingleStream();
                stopCycle();
                stopCycleExpanded();
                
                // 自動リセットタイマーも停止
                if (autoResetInterval) {
                    clearInterval(autoResetInterval);
                    autoResetInterval = null;
                }
                
                fetch('/stop_stream', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    updateStatus('⏹️ 停控中', 'info');
                    document.getElementById('videoFrame').style.display = 'none';
                    document.getElementById('noVideo').style.display = 'block';
                    document.getElementById('detectionList').innerHTML = '<div style="color: #6c757d; text-align: center; padding: 20px;">沒有檢測到物件</div>';
                    
                    const btn = document.getElementById('controlBtn');
                    btn.textContent = '開控';
                    btn.className = 'btn btn-success';
                });
            }
            
            function updateFrame() {
                if (!isStreaming || inflightFrame) return;
                inflightFrame = true;
                fetch('/get_frame')
                .then(response => response.json())
                .then(data => {
                    if (data.success && data.frame) {
                        const img = document.getElementById('videoFrame');
                        // キャッシュバスティング: タイムスタンプ付きで強制更新
                        img.src = 'data:image/jpeg;base64,' + data.frame + '#t=' + Date.now();
                        img.style.display = 'block';
                        document.getElementById('noVideo').style.display = 'none';
                        
                        updateDetections(data.detections || []);
                        updateStatus('✅ 最適化監控中 - ' + new Date().toLocaleTimeString(), 'success');
                    }
                    inflightFrame = false;
                })
                .catch(error => {
                    console.error('更新錯誤:', error);
                    inflightFrame = false;
                });
            }
            
            function updateDetections(detections) {
                const detectionList = document.getElementById('detectionList');
                if (detections && detections.length > 0) {
                    const listHtml = detections.map(det => 
                        `<div class="detection-item">
                            <span><strong>${det.class}</strong></span>
                            <span>${(det.confidence * 100).toFixed(1)}%</span>
                        </div>`
                    ).join('');
                    detectionList.innerHTML = listHtml;
                } else {
                    detectionList.innerHTML = '<div style="color: #6c757d; text-align: center; padding: 20px;">沒有檢測到物件</div>';
                }
            }
            
            function updateStatus(message, type) {
                const status = document.getElementById('status');
                status.textContent = message;
                status.className = 'status-info ' + type;
            }
            
            function changeView(viewType) {
                currentView = viewType;
                
                // すべてのビューボタンのアクティブ状態をクリア
                document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
                
                // 循面モード中は循面ボタンをアクティブに保持
                if (isCycling) {
                    const cycleBtn = document.getElementById('btnCycle');
                    if (cycleBtn) cycleBtn.classList.add('active');
                } else if (isCycleExpanded) {
                    const cycleExpandedBtn = document.getElementById('btnCycleExpanded');
                    if (cycleExpandedBtn) cycleExpandedBtn.classList.add('active');
                } else {
                    // 循面モードでない場合のみ、通常のボタン状態管理
                    const mainBtn = document.getElementById('btnMain');
                    if (viewType === 1) {
                        // 単一チャンネルモード時は主面ボタンをアクティブにしない
                        if (!singleChannelMode && mainBtn) mainBtn.classList.add('active');
                    }
                    else {
                        const viewBtn = document.getElementById('view' + viewType);
                        if (viewBtn) viewBtn.classList.add('active');
                    }
                }
                
                // 循拡モード時は主面ボタンのアクティブ状態を解除
                if (isCycleExpanded && mainBtn) {
                    mainBtn.classList.remove('active');
                }
                
                const singleView = document.getElementById('singleView');
                const gridView = document.getElementById('gridView');
                const gridItems = document.querySelectorAll('.grid-item');
                const selector = document.getElementById('channelSelector');
                
                if (viewType === 1) {
                    // 主面押下時は循環を停止
                    stopCycle();
                    stopCycleExpanded();
                    singleView.style.display = 'block';
                    gridView.style.display = 'none';
                    if (selector) selector.style.display = 'grid';
                    // 分割更新停止
                    if (multiChannelInterval) { clearInterval(multiChannelInterval); multiChannelInterval = null; }
                    // 単一モードでなければ単一ポーリングは停止・リクエストも無効化
                    if (!singleChannelMode && singleInterval) { clearInterval(singleInterval); singleInterval = null; inflightSingle = false; }
                    // 単一モードなら単一ポーリング（0.5秒）に切替、そうでなければメインのまま
                    if (singleChannelMode) {
                        if (updateInterval) { clearInterval(updateInterval); updateInterval = null; }
                        if (isStreaming) startSinglePolling();
                    } else {
                        // メイン表示では数字ボタンの選択表示を解除
                        document.querySelectorAll('.ch-btn').forEach(btn => btn.classList.remove('active'));
                        // メインストリーム更新を有効に
                        if (!updateInterval && isStreaming) {
                            updateInterval = setInterval(updateFrame, 3000);
                        }
                    }
                } else {
                    // 分割に移る際も循環は停止
                    stopCycle();
                    stopCycleExpanded();
                    singleView.style.display = 'none';
                    gridView.style.display = 'grid';
                    gridView.className = 'grid-container grid-' + viewType;
                    singleChannelMode = false;
                    if (selector) selector.style.display = 'grid';
                    if (singleInterval) { clearInterval(singleInterval); singleInterval = null; }
                    stopSingleStream();
                    
                    gridItems.forEach((item, index) => {
                        if (index < viewType) {
                            item.style.display = 'flex';
                            item.innerHTML = '<div style="width:100%; height:100%; background:#000; display:flex; align-items:center; justify-content:center; color:#666; font-size:12px;">CH' + (index + 1) + '</div>';
                        } else {
                            item.style.display = 'none';
                        }
                    });
                    
                    if (isStreaming) {
                        loadMultiChannelFrames(viewType);
                    }
                }
                
                updateStatus('✅ ' + viewType + '画面表示に切替', 'success');

                // サーバへUI状態を通知（保持・復元用）
                try {
                    fetch('/set_ui_state', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ view_mode: viewType, single_channel_mode: singleChannelMode, selected_channel: selectedChannel, is_cycling: isCycling })
                    });
                } catch (e) {}
            }

            function selectChannel(n) {
                // 数字押下で循環停止
                stopCycle();
                stopCycleExpanded();
                // 単一モードに切り替えて、そのチャンネルに即切替
                singleChannelMode = true; // 数字押下で単一モードに入る
                if (currentView !== 1) {
                    changeView(1);
                }
                selectedChannel = n;
                document.querySelectorAll('.ch-btn').forEach(btn => btn.classList.remove('active'));
                const target = document.getElementById('ch' + n);
                if (target) target.classList.add('active');
                // 主面ボタンのアクティブを解除（単一モード時）
                document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
                // メイン更新が動いていれば停止
                if (updateInterval) { clearInterval(updateInterval); updateInterval = null; }
                // 既存の単一更新も一旦止めてから再開
                if (singleInterval) { clearInterval(singleInterval); singleInterval = null; }
                if (isStreaming) startSinglePolling();

                // サーバへUI状態を通知
                try {
                    fetch('/set_ui_state', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ view_mode: 1, single_channel_mode: true, selected_channel: n, is_cycling: isCycling })
                    });
                } catch (e) {}
            }

            function pullSingleOnce() { fetchSingleSnapshot(); }

            function fetchSingleSnapshot() {
                if (!isStreaming || !singleChannelMode) return;
                const key = String(selectedChannel);
                fetch('/get_multi_frames/1?channel=' + selectedChannel + '&dets=1')
                  .then(r => r.json())
                  .then(data => {
                      if (data && data.success && data.frames && data.frames[key]) {
                          const img = document.getElementById('videoFrame');
                          // キャッシュバスティング: タイムスタンプ付きで強制更新
                          img.src = 'data:image/jpeg;base64,' + data.frames[key] + '#t=' + Date.now();
                          img.style.display = 'block';
                          const noV = document.getElementById('noVideo');
                          if (noV) noV.style.display = 'none';
                          updateDetections(data.detections || []);
                      }
                  })
                  .catch(() => {});
            }

            function startSinglePolling() {
                if (singleInterval) { clearInterval(singleInterval); singleInterval = null; }
                // 即時スナップショット
                fetchSingleSnapshot();
                // 3秒ごとに更新（循環中も継続）
                singleInterval = setInterval(() => { if (isStreaming && singleChannelMode) fetchSingleSnapshot(); }, 3000);
            }

            function fetchSingleFrame() { /* 未使用（互換のため残置） */ }

            function startSingleStream(ch) { /* MJPEG持続は使わず、スナップショット方式に統一 */ }

            function stopSingleStream() { /* スナップショット方式のため特別な停止は不要 */ }

            function refreshMain() {
                // メインストリームを再読込（リフレッシュ）
                // 停止→再ログイン→開始の順で確実に張り直す
                const doRefresh = async () => {
                    // まず単一モード関連を完全停止
                    singleChannelMode = false;
                    if (singleInterval) { clearInterval(singleInterval); singleInterval = null; }
                    inflightSingle = false;
                    document.querySelectorAll('.ch-btn').forEach(btn => btn.classList.remove('active'));
                    stopSingleStream();
                    stopCycle();
                    // リセット時刻を更新
                    lastResetTime = Date.now();
                    try {
                        await fetch('/stop_stream', {method: 'POST'});
                    } catch(e) {}
                    try {
                        await fetch('/relogin', {method: 'POST'});
                    } catch(e) {}
                    try {
                        await fetch('/start_stream', {method: 'POST'});
                    } catch(e) {}
                    // 主畫面=メインストリームを表示
                    changeView(1);
                    updateStatus('🔄 主畫面をリフレッシュしました', 'success');
                };
                doRefresh();
            }

            // デバッグログ制御
            let enableDebugLog = false; // デフォルトでログ無効
            
            // ログ出力関数（オンオフ制御付き）
            function debugLog(message, force = false) {
                if (enableDebugLog || force) {
                    console.log(message);
                }
            }
            
            // ログ切り替えボタンの追加
                    function toggleDebugLog() {
            enableDebugLog = !enableDebugLog;
            const btn = document.getElementById('debugLogBtn');
            if (enableDebugLog) {
                btn.textContent = 'Log-off';
                btn.className = 'view-btn';
                debugLog('🔊 デバッグログを有効にしました', true);
            } else {
                btn.textContent = 'Log-on';
                btn.className = 'view-btn';
                console.log('🔇 デバッグログを無効にしました');
            }
        }
            
            // 循環モード（独立した表示モード）
            function startCycle() {
                if (isCycling) return;
                isCycling = true;
                
                // 他のボタンのアクティブ状態をクリア
                document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
                const btn = document.getElementById('btnCycle');
                if (btn) btn.classList.add('active');
                
                // 循拡モードがアクティブな場合は停止
                if (isCycleExpanded) {
                    stopCycleExpanded();
                }
                
                // 循面専用の表示モード（4面とは独立）
                currentView = 'cycle';  // 4ではなく'cycle'として管理
                const singleView = document.getElementById('singleView');
                const gridView = document.getElementById('gridView');
                const gridItems = document.querySelectorAll('.grid-item');
                
                singleView.style.display = 'none';
                gridView.style.display = 'grid';
                gridView.className = 'grid-container grid-6';
                console.log('🔄 グリッドクラスを grid-6 に設定');
                
                // 循面専用のグリッドアイテムを表示（6画面対応）
                gridItems.forEach((item, index) => {
                    if (index < 6) {
                        item.style.display = 'flex';
                        item.style.visibility = 'visible';
                        item.style.opacity = '1';
                        item.style.minHeight = '120px';
                        item.style.backgroundColor = '#fff';
                        item.style.alignItems = 'center';
                        item.style.justifyContent = 'center';
                        item.style.color = '#6c757d';
                        item.style.fontSize = '12px';
                        item.style.border = '1px solid #dee2e6';
                        item.style.borderRadius = '4px';
                        item.style.width = '100%';
                        item.style.height = '100%';
                        item.innerHTML = '<div style="width:100%; height:100%; background:#000; display:flex; align-items:center; justify-content:center; color:#666; font-size:12px;">循面</div>';
                        debugLog('✅ グリッドアイテム' + index + 'を表示: 循面');
                    } else {
                        item.style.display = 'none';
                        item.style.visibility = 'hidden';
                        item.style.opacity = '0';
                        debugLog('❌ グリッドアイテム' + index + 'を非表示');
                    }
                });
                
                debugLog('🔄 6画面表示設定完了: グリッドアイテム数: ' + gridItems.length);
                
                // グリッドコンテナのスタイルを強制設定（6画面表示：3列×2行）
                gridView.style.display = 'grid';
                gridView.style.gridTemplateColumns = '1fr 1fr 1fr';
                gridView.style.gridTemplateRows = '1fr 1fr';
                gridView.style.width = '100%';
                gridView.style.height = '500px';
                gridView.style.gap = '2px';
                gridView.style.backgroundColor = '#fff';
                gridView.style.borderRadius = '8px';
                gridView.style.overflow = 'hidden';
                
                // 重要：CSSクラスよりもインラインスタイルを優先
                gridView.setAttribute('style', 'display: grid !important; grid-template-columns: 1fr 1fr 1fr !important; grid-template-rows: 1fr 1fr !important; width: 100% !important; height: 500px !important; gap: 2px !important; background-color: #fff !important; border-radius: 8px !important; overflow: hidden !important;');
                
                debugLog('🔄 グリッドレイアウトを強制設定: 3列×2行');
                debugLog('🔄 gridTemplateColumns: ' + gridView.style.gridTemplateColumns);
                debugLog('🔄 gridTemplateRows: ' + gridView.style.gridTemplateRows);
                debugLog('🔄 実際のスタイル: ' + gridView.getAttribute('style'));
                
                // 単一モード解除
                singleChannelMode = false;
                if (updateInterval) { clearInterval(updateInterval); updateInterval = null; }
                if (singleInterval) { clearInterval(singleInterval); singleInterval = null; }
                
                // グループAから開始（チャンネル3,4,7,11）
                cycleGroupIndex = 0;
                lastCycleSwitchAt = Date.now() - 20000; // 初期化時は即座に切り替え可能

                // 統合された循面更新タイマー（5秒間隔で更新、20秒間隔でグループ切り替え）
                window.cycleUpdateInterval = setInterval(() => {
                    if (!isCycling) return;
                    
                    const nowTs = Date.now();
                    const shouldSwitchGroup = (nowTs - lastCycleSwitchAt) >= 20000;
                    
                    if (shouldSwitchGroup) {
                        // グループ切り替え
                        cycleGroupIndex = (cycleGroupIndex + 1) % 2;
                        lastCycleSwitchAt = nowTs;
                        const currentGroup = cycleGroupIndex === 0 ? cycleGroupA : cycleGroupB;
                        
                        updateStatus('🔄 循面グループ' + (cycleGroupIndex + 1) + '表示中: CH' + currentGroup.join(',CH'), 'info');
                        debugLog('🔄 循面グループ切り替え: ' + currentGroup + ' 時刻: ' + new Date().toLocaleTimeString());
                    }
                    
                    // 現在のグループを更新（5秒間隔で負荷軽減）
                    const currentGroup = cycleGroupIndex === 0 ? cycleGroupA : cycleGroupB;
                    // ログ出力を制限（デバッグ時のみ）
                    if (Date.now() % 30000 < 5000) { // 30秒に1回のみログ出力
                        debugLog('🔄 循面5秒更新実行: ' + currentGroup + ' 時刻: ' + new Date().toLocaleTimeString());
                    }
                    displayCycleGroup(currentGroup);
                }, 5000); // 1秒 → 5秒に変更
                
                // 初期表示
                displayCycleGroup(cycleGroupA);
                updateStatus('🔄 循面グループ1開始: CH2,3,4,7,11,14', 'info');

                // サーバへUI状態を通知
                try {
                    fetch('/set_ui_state', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ view_mode: 'cycle', single_channel_mode: false, selected_channel: 0, is_cycling: true })
                    });
                } catch (e) {}
            }

            function stopCycle() {
                // 統合された循面タイマーをクリア
                if (window.cycleUpdateInterval) { clearInterval(window.cycleUpdateInterval); window.cycleUpdateInterval = null; }
                isCycling = false;
                
                // 循面ボタンのアクティブ状態をクリア
                const btn = document.getElementById('btnCycle');
                if (btn) btn.classList.remove('active');
                
                // 循面モード終了時は主面に戻す
                if (currentView === 'cycle') {
                    currentView = 1;
                    const singleView = document.getElementById('singleView');
                    const gridView = document.getElementById('gridView');
                    const videoFrame = document.getElementById('videoFrame');
                    const noVideo = document.getElementById('noVideo');
                    
                    singleView.style.display = 'block';
                    gridView.style.display = 'none';
                    if (videoFrame) videoFrame.style.display = 'block';
                    if (noVideo) noVideo.style.display = 'none';
                    
                    // 主面ボタンをアクティブに
                    const mainBtn = document.getElementById('btnMain');
                    if (mainBtn) mainBtn.classList.add('active');
                }

                // サーバへUI状態を通知
                try {
                    fetch('/set_ui_state', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ view_mode: currentView, single_channel_mode: singleChannelMode, selected_channel: selectedChannel, is_cycling: false })
                    });
                } catch (e) {}
            }
            
            function startCycleExpanded() {
                // 他の表示モードを停止
                stopCycle();
                if (singleChannelMode) {
                    stopSingleChannel();
                }
                
                isCycleExpanded = true;
                currentView = 'cycle_expanded';
                
                // 循拡ボタンをアクティブに
                const btn = document.getElementById('btnCycleExpanded');
                if (btn) btn.classList.add('active');
                
                // 6面表示のグリッドを表示（1.5倍拡大）
                const singleView = document.getElementById('singleView');
                const gridView = document.getElementById('gridView');
                
                singleView.style.display = 'none';
                gridView.style.display = 'grid';
                gridView.className = 'grid-container cycle-expanded';
                
                // 6つのグリッドアイテムのみ表示（強制制御）
                const gridItems = document.querySelectorAll('.grid-item');
                gridItems.forEach((item, index) => {
                    if (index < 6) {
                        item.style.display = 'flex';
                        item.style.visibility = 'visible';
                        item.style.opacity = '1';
                    } else {
                        item.style.display = 'none';
                        item.style.visibility = 'hidden';
                        item.style.opacity = '0';
                    }
                });
                
                // グリッドコンテナのスタイルを強制設定（3列×2行）
                gridView.style.gridTemplateColumns = '1fr 1fr 1fr';
                gridView.style.gridTemplateRows = '1fr 1fr';
                gridView.style.height = '100vh';
                gridView.style.margin = '0';
                gridView.style.padding = '0';
                
                // ヘッダー非表示・ボタン下部固定のためのbodyクラス追加
                document.body.classList.add('cycle-expanded-mode');
                
                // 初期表示
                displayCycleGroupExpanded(cycleGroupA);
                updateStatus('🔍 循拡グループ1開始: CH2,3,4,7,11,14 (1.5倍拡大・ヘッダー非表示)', 'info');
                
                // 統合された循拡更新タイマー（1秒間隔で更新、20秒間隔でグループ切り替え）
                window.cycleExpandedUpdateInterval = setInterval(() => {
                    const nowTs = Date.now();
                    const shouldSwitchGroup = (nowTs - lastCycleSwitchAt) >= 20000;
                    
                    if (shouldSwitchGroup) {
                        cycleGroupIndex = (cycleGroupIndex + 1) % 2;
                        lastCycleSwitchAt = nowTs;
                        const currentGroup = cycleGroupIndex === 0 ? cycleGroupA : cycleGroupB;
                        
                        updateStatus('🔍 循拡グループ' + (cycleGroupIndex + 1) + '表示中: CH' + currentGroup.join(',CH') + ' (1.5倍拡大)', 'info');
                        debugLog('🔍 循拡グループ切り替え: ' + currentGroup + ' 時刻: ' + new Date().toLocaleTimeString());
                    }
                    
                    const currentGroup = cycleGroupIndex === 0 ? cycleGroupA : cycleGroupB;
                    // ログ出力を制限（デバッグ時のみ）
                    if (Date.now() % 30000 < 5000) { // 30秒に1回のみログ出力
                        debugLog('🔍 循拡5秒更新実行: ' + currentGroup + ' 時刻: ' + new Date().toLocaleTimeString());
                    }
                    displayCycleGroupExpanded(currentGroup);
                }, 5000); // 1秒 → 5秒に変更
                
                // 初期表示
                displayCycleGroupExpanded(cycleGroupA);
                updateStatus('🔍 循拡グループ1開始: CH2,3,4,7,11,14 (1.5倍拡大)', 'info');
            }
            
            function stopCycleExpanded() {
                // 統合された循拡タイマーをクリア
                if (window.cycleExpandedUpdateInterval) { 
                    clearInterval(window.cycleExpandedUpdateInterval); 
                    window.cycleExpandedUpdateInterval = null; 
                }
                isCycleExpanded = false;
                
                // 循拡ボタンのアクティブ状態をクリア
                const btn = document.getElementById('btnCycleExpanded');
                if (btn) btn.classList.remove('active');
                
                // ヘッダー表示・ボタン通常位置に戻すためのbodyクラス削除
                document.body.classList.remove('cycle-expanded-mode');
                
                // 循拡モード終了時は主面に戻す
                if (currentView === 'cycle_expanded') {
                    currentView = 1;
                    const singleView = document.getElementById('singleView');
                    const gridView = document.getElementById('gridView');
                    const videoFrame = document.getElementById('videoFrame');
                    const noVideo = document.getElementById('noVideo');
                    
                    singleView.style.display = 'block';
                    gridView.style.display = 'none';
                    if (videoFrame) videoFrame.style.display = 'block';
                    if (noVideo) noVideo.style.display = 'none';
                    
                    // 主面ボタンをアクティブに
                    const mainBtn = document.getElementById('btnMain');
                    if (mainBtn) mainBtn.classList.add('active');
                }
            }
            
            // 循面グループ表示関数（6画面表示対応版・デバッグ強化）
            function displayCycleGroup(channels) {
                const timestamp = new Date().toLocaleTimeString();
                debugLog('🔄 循面更新開始: ' + channels + ' 時刻: ' + timestamp);
                
                // 6面表示のグリッドアイテムを取得
                const gridItems = document.querySelectorAll('.grid-item');
                
                // 6画面を一括取得（個別取得ではなく）+ YOLO検知有効化
                const channelList = channels.slice(0, 6).join(',');
                // ログ出力を制限（デバッグ時のみ）
                if (Date.now() % 30000 < 5000) { // 30秒に1回のみログ出力
                    debugLog('🔄 循面API呼び出し: /get_multi_frames/6?channels=' + channelList + '&dets=1');
                }
                
                fetch('/get_multi_frames/6?channels=' + channelList + '&dets=1')
                .then(response => response.json())
                .then(data => {
                    debugLog('🔄 循面API応答: ' + data.success + ' フレーム数: ' + (data.frames ? Object.keys(data.frames).length : 0));
                    
                    if (data.success && data.frames) {
                        // 各グリッドアイテムに映像を表示（6画面対応）
                        channels.forEach((channel, index) => {
                            if (index < 6 && gridItems[index]) {
                                const gridItem = gridItems[index];
                                const channelKey = parseInt(channel);
                                
                                if (data.frames[channelKey]) {
                                    const imgSrc = 'data:image/jpeg;base64,' + data.frames[channelKey] + '#t=' + Date.now();
                                    gridItem.innerHTML = '<img src="' + imgSrc + '" style="width:100%; height:100%; object-fit:cover;" alt="CH' + channel + '">';
                                    debugLog('✅ CH' + channel + ' 表示更新完了');
                                } else {
                                    gridItem.innerHTML = '<div style="width:100%; height:100%; background:#000; display:flex; align-items:center; justify-content:center; color:#666; font-size:12px;">CH' + channel + '<br>フレーム無し</div>';
                                    debugLog('⚠️ CH' + channel + ' フレーム無し');
                                }
                            }
                        });
                    } else {
                        debugLog('❌ 循面一括取得失敗: ' + (data.error || '不明なエラー'));
                    }
                })
                .catch(error => {
                    debugLog('❌ 循面通信エラー: ' + error.message);
                    // エラーが発生した場合は、5秒後に再試行
                    setTimeout(() => {
                        if (isCycling) {
                            debugLog('🔄 循面通信エラー後の再試行');
                            displayCycleGroup(channels);
                        }
                    }, 5000);
                });
            }

            function toggleCycle() {
                if (isCycling) stopCycle(); else startCycle();
            }
            
            function toggleCycleExpanded() {
                if (isCycleExpanded) {
                    stopCycleExpanded();
                } else {
                    startCycleExpanded();
                }
                
                // ボタンのアクティブ状態を管理
                const cycleExpandedBtn = document.getElementById('btnCycleExpanded');
                const mainBtn = document.getElementById('btnMain');
                
                if (isCycleExpanded) {
                    // 循拡モード時は他のボタンのアクティブ状態を解除
                    document.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
                    if (cycleExpandedBtn) cycleExpandedBtn.classList.add('active');
                } else {
                    // 循拡モード終了時は主面ボタンをアクティブに
                    if (mainBtn) mainBtn.classList.add('active');
                }
            }
            
            // 循拡グループ表示関数（1.5倍拡大版）
            function displayCycleGroupExpanded(channels) {
                const timestamp = new Date().toLocaleTimeString();
                debugLog('🔍 循拡更新開始: ' + channels + ' 時刻: ' + timestamp);
                
                // 6面表示のグリッドアイテムを取得
                const gridItems = document.querySelectorAll('.grid-item');
                
                // 6画面を一括取得（個別取得ではなく）+ YOLO検知有効化
                const channelList = channels.slice(0, 6).join(',');
                // ログ出力を制限（デバッグ時のみ）
                if (Date.now() % 30000 < 5000) { // 30秒に1回のみログ出力
                    debugLog('🔍 循拡API呼び出し: /get_multi_frames/6?channels=' + channelList + '&dets=1');
                }
                
                fetch('/get_multi_frames/6?channels=' + channelList + '&dets=1')
                .then(response => response.json())
                .then(data => {
                    debugLog('🔍 循拡API応答: ' + data.success + ' フレーム数: ' + (data.frames ? Object.keys(data.frames).length : 0));
                    
                    if (data.success && data.frames) {
                        // 各グリッドアイテムに映像を表示（6画面対応・1.5倍拡大）
                        channels.forEach((channel, index) => {
                            if (index < 6 && gridItems[index]) {
                                const gridItem = gridItems[index];
                                const channelKey = parseInt(channel);
                                
                                if (data.frames[channelKey]) {
                                    const imgSrc = 'data:image/jpeg;base64,' + data.frames[channelKey] + '#t=' + Date.now();
                                    gridItem.innerHTML = '<img src="' + imgSrc + '" style="width:100%; height:100%; object-fit:cover;" alt="CH' + channel + '">';
                                    debugLog('🔍 CH' + channel + ' 循拡表示更新完了');
                                } else {
                                    gridItem.innerHTML = '<div style="width:100%; height:100%; background:#000; display:flex: align-items:center; justify-content:center; color:#666; font-size:18px;">CH' + channel + '<br>フレーム無し</div>';
                                    debugLog('⚠️ CH' + channel + ' 循拡フレーム無し');
                                }
                            }
                        });
                    } else {
                        debugLog('❌ 循拡一括取得失敗: ' + (data.error || '不明なエラー'));
                    }
                })
                .catch(error => {
                                            debugLog('❌ 循拡通信エラー: ' + error.message);
                    // エラーが発生した場合は、5秒後に再試行
                    setTimeout(() => {
                        if (isCycleExpanded) {
                            debugLog('🔍 循拡通信エラー後の再試行');
                            displayCycleGroupExpanded(channels);
                        }
                    }, 5000);
                });
            }
            
            // リモコン機能
            function toggleRemote() {
                const remotePanel = document.getElementById('remoteControlPanel');
                if (remotePanel.style.display === 'none') {
                    remotePanel.style.display = 'block';
                    document.getElementById('btnRemote').classList.add('active');
                } else {
                    remotePanel.style.display = 'none';
                    document.getElementById('btnRemote').classList.remove('active');
                }
            }
            
            function remoteSelectMode(mode) {
                // CCTVサーバー側の表示モードを選択
                updateStatus('🎮 遙控操作: ' + mode + ' モード選択中...', 'info');
                
                // CCTVサーバー側のAPIを呼び出して表示モード切り替え
                fetch('/remote_control?action=change_mode&mode=' + mode)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateStatus('✅ 遙控操作完了: ' + mode + ' モードに切り替え', 'success');
                        // メインストリームを更新
                        if (isStreaming) {
                            updateFrame();
                        }
                    } else {
                        updateStatus('❌ 遙控操作失敗: ' + (data.error || '不明なエラー'), 'error');
                    }
                })
                .catch(error => {
                    console.error('遙控操作エラー:', error);
                    updateStatus('❌ 遙控操作エラー: 通信失敗', 'error');
                });
            }
            
            function closeRemote() {
                document.getElementById('remoteControlPanel').style.display = 'none';
                document.getElementById('btnRemote').classList.remove('active');
            }
            
            function loadMultiChannelFrames(numChannels) {
                updateStatus('📺 最適化多頻道載入中...', 'info');
                
                if (multiChannelInterval) {
                    clearInterval(multiChannelInterval);
                    multiChannelInterval = null;
                }
                
                updateMultiChannelFrames(numChannels);
                
                // 分割は3秒間隔で更新
                multiChannelInterval = setInterval(() => {
                    if (isStreaming) {
                        updateMultiChannelFrames(numChannels);
                    }
                }, 3000);
            }
            
            function updateMultiChannelFrames(numChannels) {
                // 接続状態をチェック
                if (!isStreaming) return;
                
                fetch('/get_multi_frames/' + numChannels)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success && data.frames && data.total_channels > 0) {
                        Object.keys(data.frames).forEach(channel => {
                            const gridItem = document.getElementById('grid' + (parseInt(channel) - 1));
                            if (gridItem && data.frames[channel]) {
                                // タイムスタンプ付きでキャッシュ回避
                                gridItem.innerHTML = '<img src="data:image/jpeg;base64,' + data.frames[channel] + '#t=' + Date.now() + '" style="width:100%; height:100%; object-fit:cover;" alt="CH' + channel + '">';
                            }
                        });
                        
                        updateStatus('✅ ' + data.total_channels + '頻道最適化串流中', 'success');
                    } else {
                        // エラーメッセージを削除 - 静かに再試行
                        debugLog('多チャンネル取得失敗 - 再試行中');
                    }
                })
                .catch(error => {
                    updateStatus('⚠️ 通訊錯誤: ' + error.message, 'error');
                });
            }

            // ティッカー機能
            function initTicker() {
                updateTickerContent();
            }
            
            function updateTickerContent() {
                // ティッカーの内容を更新（必要に応じて）
                console.log('ティッカー表示開始');
            }
            
            // ページ読み込み時にティッカーを初期化
            window.addEventListener('load', () => {
                initTicker();
            });
            
        </script>
    </body>
    </html>
    ''')

@app.route('/start_stream', methods=['POST'])
def start_stream():
    """ストリーム開始"""
    try:
        # 毎回セッションを張り直して古い認証・接続を掃除
        cctv_system.reset_session()
        success = cctv_system.start_optimized_stream()
        # 起動後、保存された表示モードを反映
        try:
            vm = int(cctv_system.ui_state.get('view_mode', 1))
            cctv_system.change_view_mode(vm)
        except Exception:
            pass
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_stream', methods=['POST'])
def stop_stream():
    """ストリーム停止"""
    cctv_system.stop_stream()
    return jsonify({'success': True})

@app.route('/relogin', methods=['POST'])
def relogin():
    """HTTPセッションを再生成（再ログイン）"""
    try:
        cctv_system.reset_session()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/set_ui_state', methods=['POST'])
def set_ui_state():
    """フロントからのUI状態更新を保存し、ログに出力"""
    try:
        data = request.get_json(silent=True) or {}
        allowed_keys = ['view_mode', 'single_channel_mode', 'selected_channel', 'is_cycling']
        for key in allowed_keys:
            if key in data:
                # view_mode/selected_channel は数値化
                if key in ('view_mode', 'selected_channel'):
                    try:
                        cctv_system.ui_state[key] = int(data[key])
                    except Exception:
                        cctv_system.ui_state[key] = data[key]
                else:
                    cctv_system.ui_state[key] = data[key]
        print(f"🧭 UI状態更新: {cctv_system.ui_state}")
        return jsonify({'success': True, 'ui_state': cctv_system.ui_state})
    except Exception as e:
        print(f"🧭 UI状態更新エラー: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_ui_state')
def get_ui_state():
    """現在のUI状態を返す（デバッグ用）"""
    try:
        return jsonify({'success': True, 'ui_state': cctv_system.ui_state})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_frame')
def get_frame():
    """フレーム取得"""
    if cctv_system.current_frame:
        return jsonify({
            'success': True, 
            'frame': cctv_system.current_frame,
            'detections': cctv_system.detection_results
        })
    else:
        return jsonify({'success': False})

@app.route('/get_multi_frames/<int:num_channels>')
def get_multi_frames(num_channels):
    """複数チャンネルのフレームを取得"""
    try:
        # 単一チャンネル指定に対応: /get_multi_frames/1?channel=<n>
        channel_q = request.args.get('channel')
        # 循面用の複数チャンネル指定に対応: /get_multi_frames/6?channels=2,3,4,7,11,14
        channels_q = request.args.get('channels')
        with_dets = request.args.get('dets') is not None
        
        if num_channels == 1 and channel_q:
            # UI状態を保存（単一モード）
            try:
                cctv_system.ui_state['single_channel_mode'] = True
                cctv_system.ui_state['selected_channel'] = int(channel_q)
            except Exception:
                pass
            b64, dets = cctv_system.get_single_channel_frame_optimized(channel_q, with_detection=with_dets)
            frames = {int(channel_q): b64} if b64 else {}
            detections = dets if with_dets else []
        elif channels_q:
            # 指定されたチャンネルのみを取得（循面用）
            try:
                cctv_system.ui_state['single_channel_mode'] = False
            except Exception:
                pass
            channel_list = [int(ch) for ch in channels_q.split(',') if ch.strip()]
            frames = cctv_system.get_specific_channels_frames(channel_list, with_detection=with_dets)
            detections = []
        else:
            # 単一モード解除
            try:
                cctv_system.ui_state['single_channel_mode'] = False
            except Exception:
                pass
            frames = cctv_system.get_multi_channel_frames_parallel(num_channels)
            detections = []
        
        # バイナリデータをbase64エンコード
        encoded_frames = {}
        for ch, frame_data in frames.items():
            if frame_data:
                encoded_frames[ch] = frame_data
        
        # フレームが1つも取得できなかった場合はエラーを返す
        if len(encoded_frames) == 0:
            return jsonify({
                'success': False, 
                'error': f'全{num_channels}チャンネルの接続に失敗しました',
                'frames': {},
                'channels': [],
                'total_channels': 0,
                'detections': detections
            })
        
        return jsonify({
            'success': True,
            'frames': encoded_frames,
            'channels': list(encoded_frames.keys()),
            'total_channels': len(encoded_frames),
            'is_combined': False,
            'detections': detections
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/single_stream')
def single_stream():
    """指定チャンネルのMJPEGをそのままプロキシして配信"""
    try:
        channel_q = request.args.get('channel', default='1')
        ch = int(channel_q)
        stream_url = cctv_system.get_channel_stream_url(ch)

        def generate():
            with requests.get(stream_url, auth=HTTPBasicAuth(cctv_system.username, cctv_system.password), stream=True, timeout=(2, 10), verify=False) as r:
                for chunk in r.iter_content(chunk_size=4096):
                    if chunk:
                        yield chunk

        headers = {
            'Content-Type': 'multipart/x-mixed-replace; boundary=--myboundary',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
        # 多くのMJPEGは boundary を自前で含むため、Content-Type だけ指定
        return Response(stream_with_context(generate()), headers=headers)
    except Exception as e:
        return Response(status=502)

@app.route('/start_single_stream')
def http_start_single_stream():
    try:
        ch_q = request.args.get('channel', default='1')
        ch = int(ch_q)
        print(f"🔁 單一/循面 切替要求: ch={ch}")
        ok = cctv_system.start_single_channel_stream(ch)
        print(f"🔁 切替結果: ch={ch} -> {'成功' if ok else '失敗'}")
        # UI状態も併せて更新
        try:
            cctv_system.ui_state['single_channel_mode'] = True
            cctv_system.ui_state['selected_channel'] = ch
        except Exception:
            pass
        return jsonify({'success': bool(ok), 'channel': ch})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/stop_single_stream')
def http_stop_single_stream():
    try:
        ok = cctv_system.stop_single_channel_stream()
        return jsonify({'success': bool(ok)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_single_frame')
def http_get_single_frame():
    try:
        if cctv_system.current_single_frame:
            return jsonify({'success': True, 'frame': cctv_system.current_single_frame, 'detections': cctv_system.current_single_detections})
        return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/remote_control')
def remote_control():
    """CCTVサーバー側のリモート制御（表示モード切り替え）"""
    try:
        action = request.args.get('action')
        mode = request.args.get('mode')
        
        # ログをファイルにも保存
        log_message = f"🎮 遙控リクエスト受信: action={action}, mode={mode}"
        print(log_message)
        
        # ファイルにログ保存
        with open('remote_control.log', 'a', encoding='utf-8') as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {log_message}\n")
        
        if action == 'change_mode' and mode:
            # CCTVサーバー側の表示モード切り替えAPIを呼び出し
            # 各モードに対応するCCTVサーバー側のボタン操作
            mode_urls = {
                'full': f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1",
                'quarter': f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&quarter=1",
                '4cut': f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&cut=4",
                '9cut': f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&cut=9",
                '16cut': f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&cut=16"
            }
            
            if mode in mode_urls:
                # 複数のURLパターンを試行
                urls_to_try = [
                    mode_urls[mode],  # 元のURL
                    f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&split={mode.replace('cut', '')}",
                    f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&view={mode.replace('cut', '')}",
                    f"{cctv_system.cctv_base_url}/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&sequence={mode}",
                    # 異なるCGIスクリプトも試行
                    f"{cctv_system.cctv_base_url}/cgi-bin/guest/Control.cgi?action=view&mode={mode}",
                    f"{cctv_system.cctv_base_url}/cgi-bin/guest/Display.cgi?mode={mode}",
                    f"{cctv_system.cctv_base_url}/cgi-bin/guest/Split.cgi?count={mode.replace('cut', '')}",
                ]
                
                print(f"🎮 遙控操作: {mode}モード -> {len(urls_to_try)}個のURLパターンを試行")
                
                # 各URLパターンを順次試行
                for i, url in enumerate(urls_to_try):
                    try:
                        print(f"📡 試行 {i+1}: {url}")
                        response = cctv_system.session.get(url, timeout=(2, 5))
                        print(f"📡 通信結果: HTTP {response.status_code}")
                        
                        if response.status_code == 200:
                            print(f"✅ 成功: {mode}モード切り替え完了 (URL {i+1})")
                            return jsonify({'success': True, 'message': f'{mode}モードに切り替え完了', 'url': url})
                        else:
                            print(f"❌ 失敗: HTTP {response.status_code} (URL {i+1})")
                    except Exception as e:
                        print(f"🚨 通信エラー: {str(e)} (URL {i+1})")
                
                # すべてのURLパターンが失敗
                print(f"❌ すべてのURLパターンが失敗: {mode}モード")
                return jsonify({'success': False, 'error': f'すべてのURLパターンが失敗しました'})
            else:
                return jsonify({'success': False, 'error': f'無効なモード: {mode}'})
        else:
            return jsonify({'success': False, 'error': '無効なパラメータ'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/change_view/<int:view_mode>', methods=['POST'])
def change_view(view_mode):
    """CCTV分割表示を変更"""
    try:
        # 🚀 まず現在の処理を中断
        cctv_system.interrupt_current_processing()
        print(f"🛑 既存処理中断 -> {view_mode}分割表示に切替")

        # UI状態を保存
        try:
            cctv_system.ui_state['view_mode'] = int(view_mode)
        except Exception:
            pass

        success = cctv_system.change_view_mode(view_mode)
        
        view_names = {1: '單一畫面', 4: '4分割畫面', 9: '9分割畫面', 16: '16分割畫面'}
        
        return jsonify({
            'success': success,
            'view_mode': view_mode,
            'view_name': view_names.get(view_mode, '未知'),
            'message': f'表示モードを{view_names.get(view_mode)}に変更しました' if success else '表示モードの変更に失敗しました'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    print("🏭 KIRII CCTV監視システム (最適化版)")
    print("📺 CCTV: 192.168.0.98:18080 (ストリーミング対応)")
    print("🤖 YOLO11: 物体検出有効")
    print("🌐 アクセス: http://localhost:5013")
    print("🎮 遙控機能: 実装済み")
    print("📝 ログ出力: 有効")
    print("🚀 サーバー起動中...")
    
    # システムの安定性向上のための設定
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print(f"\n🛑 シグナル {sig} を受信 - システムを安全に終了します")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # メモリ使用量の監視とログ出力（一時的に無効化）
        # import psutil
        # process = psutil.Process()
        # print(f"💾 初期メモリ使用量: {process.memory_info().rss / 1024 / 1024:.1f} MB")
        
        print("🚀 Flaskサーバー起動中...")
        app.run(host='0.0.0.0', port=5013, debug=False, threaded=True)
    except Exception as e:
        print(f"❌ サーバー起動エラー: {e}")
        print(f"🔍 エラーの詳細: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        input("Enterキーを押して終了...")
