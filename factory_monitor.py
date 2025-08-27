#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工場監視システム - メインクラス
YOLO11を使用したリアルタイム物体検出・在庫管理システム
"""

import cv2
import numpy as np
import json
import time
import os
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Optional
import logging

from ultralytics import YOLO
import torch

from config import (
    YOLO_MODEL, CONFIDENCE_THRESHOLD, NMS_THRESHOLD,
    MONITORING_CONFIG, INVENTORY_ALERTS, DATA_CONFIG,
    SYSTEM_CONFIG, PRODUCT_MASTER
)


class FactoryMonitor:
    """工場監視システムメインクラス"""
    
    def __init__(self):
        """初期化"""
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # YOLO11モデル初期化
        self.model = None
        self.device = self._setup_device()
        self.load_model()
        
        # 検出履歴
        self.detection_history = deque(maxlen=MONITORING_CONFIG['max_history_records'])
        self.current_counts = defaultdict(int)
        self.last_detection_time = time.time()
        
        # データ保存設定
        self.setup_data_directories()
        
        # アラート管理
        self.last_alert_time = defaultdict(float)
        
        # 監視状態
        self.is_monitoring = False
        self.monitoring_thread = None
        
        self.logger.info("工場監視システムが初期化されました")
    
    def setup_logging(self):
        """ログ設定"""
        if MONITORING_CONFIG['enable_logging']:
            logging.basicConfig(
                level=getattr(logging, MONITORING_CONFIG['log_level']),
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler('factory_monitor.log'),
                    logging.StreamHandler()
                ]
            )
    
    def _setup_device(self):
        """デバイス設定（GPU/CPU）"""
        if SYSTEM_CONFIG['enable_gpu'] and torch.cuda.is_available():
            device = f"cuda:{SYSTEM_CONFIG['gpu_device']}"
            self.logger.info(f"GPU使用: {device}")
        else:
            device = "cpu"
            self.logger.info("CPU使用")
        return device
    
    def load_model(self):
        """YOLO11モデル読み込み"""
        try:
            self.model = YOLO(YOLO_MODEL)
            self.model.to(self.device)
            self.logger.info(f"YOLO11モデル '{YOLO_MODEL}' を読み込みました")
        except Exception as e:
            self.logger.error(f"モデル読み込みエラー: {e}")
            raise
    
    def setup_data_directories(self):
        """データ保存ディレクトリ作成"""
        os.makedirs(DATA_CONFIG['data_dir'], exist_ok=True)
        os.makedirs(os.path.join(DATA_CONFIG['data_dir'], DATA_CONFIG['images_dir']), exist_ok=True)
        self.logger.info("データディレクトリを作成しました")
    
    def detect_objects(self, frame: np.ndarray) -> Tuple[Dict[str, int], np.ndarray]:
        """
        物体検出実行
        
        Args:
            frame: 入力画像フレーム
            
        Returns:
            Tuple[Dict[str, int], np.ndarray]: (検出カウント, 描画済みフレーム)
        """
        if self.model is None:
            return {}, frame
        
        try:
            # YOLO11で検出実行
            results = self.model(
                frame,
                conf=CONFIDENCE_THRESHOLD,
                iou=NMS_THRESHOLD,
                verbose=False
            )
            
            # 検出結果処理
            counts = defaultdict(int)
            annotated_frame = frame.copy()
            
            if results and len(results) > 0:
                result = results[0]
                
                if result.boxes is not None and len(result.boxes) > 0:
                    # バウンディングボックス取得
                    boxes = result.boxes.xyxy.cpu().numpy()
                    confidences = result.boxes.conf.cpu().numpy()
                    class_ids = result.boxes.cls.cpu().numpy().astype(int)
                    
                    # 検出結果描画・カウント
                    for i, (box, conf, class_id) in enumerate(zip(boxes, confidences, class_ids)):
                        if conf >= CONFIDENCE_THRESHOLD:
                            # クラス名取得
                            class_name = self.model.names[class_id]
                            counts[class_name] += 1
                            
                            # バウンディングボックス描画
                            x1, y1, x2, y2 = box.astype(int)
                            
                            # 色設定（クラスごと）
                            color = self._get_class_color(class_name)
                            
                            # ボックス描画
                            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                            
                            # ラベル描画
                            label = f"{class_name}: {conf:.2f}"
                            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                            cv2.rectangle(
                                annotated_frame,
                                (x1, y1 - label_size[1] - 10),
                                (x1 + label_size[0], y1),
                                color,
                                -1
                            )
                            cv2.putText(
                                annotated_frame,
                                label,
                                (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (255, 255, 255),
                                2
                            )
            
            return dict(counts), annotated_frame
            
        except Exception as e:
            self.logger.error(f"物体検出エラー: {e}")
            return {}, frame
    
    def _get_class_color(self, class_name: str) -> Tuple[int, int, int]:
        """クラス別色取得"""
        colors = {
            'person': (255, 0, 0),      # 青
            'car': (0, 255, 0),         # 緑
            'truck': (0, 0, 255),       # 赤
            'motorcycle': (255, 255, 0), # シアン
            'bus': (255, 0, 255),       # マゼンタ
            'bicycle': (0, 255, 255),   # 黄色
        }
        return colors.get(class_name, (128, 128, 128))  # デフォルト: グレー
    
    def process_single_image(self, image_path: str) -> Dict[str, int]:
        """
        単一画像の処理
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            Dict[str, int]: 検出カウント結果
        """
        try:
            # 画像読み込み
            frame = cv2.imread(image_path)
            if frame is None:
                self.logger.error(f"画像読み込み失敗: {image_path}")
                return {}
            
            # 物体検出
            counts, annotated_frame = self.detect_objects(frame)
            
            # 結果保存（オプション）
            if DATA_CONFIG['save_detection_images']:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(
                    DATA_CONFIG['data_dir'],
                    DATA_CONFIG['images_dir'],
                    f"detection_{timestamp}.{DATA_CONFIG['image_format']}"
                )
                cv2.imwrite(output_path, annotated_frame)
                self.logger.info(f"検出結果画像保存: {output_path}")
            
            # 履歴記録
            self.record_detection(counts)
            
            return counts
            
        except Exception as e:
            self.logger.error(f"画像処理エラー: {e}")
            return {}
    
    def record_detection(self, counts: Dict[str, int]):
        """検出結果記録"""
        timestamp = datetime.now()
        
        detection_record = {
            'timestamp': timestamp.isoformat(),
            'counts': counts,
            'total_objects': sum(counts.values())
        }
        
        # 履歴追加
        self.detection_history.append(detection_record)
        
        # 現在のカウント更新
        self.current_counts.update(counts)
        self.last_detection_time = time.time()
        
        # アラートチェック
        self.check_alerts(counts)
        
        # 定期保存
        if len(self.detection_history) % MONITORING_CONFIG['save_interval'] == 0:
            self.save_history()
    
    def check_alerts(self, counts: Dict[str, int]):
        """アラートチェック"""
        if not INVENTORY_ALERTS['enable_alerts']:
            return
        
        current_time = time.time()
        
        for class_name, count in counts.items():
            if class_name in INVENTORY_ALERTS['alert_thresholds']:
                threshold = INVENTORY_ALERTS['alert_thresholds'][class_name]
                
                # しきい値以下でアラート
                if count <= threshold:
                    # クールダウンチェック
                    if (current_time - self.last_alert_time[class_name] > 
                        INVENTORY_ALERTS['alert_cooldown']):
                        
                        self.trigger_alert(class_name, count, threshold)
                        self.last_alert_time[class_name] = current_time
    
    def trigger_alert(self, class_name: str, current_count: int, threshold: int):
        """アラート発動"""
        message = f"在庫アラート: {class_name} = {current_count}個 (しきい値: {threshold}個)"
        self.logger.warning(message)
        
        # ここでメール送信、Slack通知などを実装可能
        print(f"🚨 {message}")
    
    def save_history(self):
        """履歴保存"""
        try:
            history_file = os.path.join(DATA_CONFIG['data_dir'], DATA_CONFIG['history_file'])
            
            # 履歴データをJSON形式で保存
            history_data = {
                'last_updated': datetime.now().isoformat(),
                'records': list(self.detection_history)
            }
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"履歴保存完了: {len(self.detection_history)}件")
            
        except Exception as e:
            self.logger.error(f"履歴保存エラー: {e}")
    
    def load_history(self):
        """履歴読み込み"""
        try:
            history_file = os.path.join(DATA_CONFIG['data_dir'], DATA_CONFIG['history_file'])
            
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                
                # 履歴復元
                self.detection_history.clear()
                for record in history_data.get('records', []):
                    self.detection_history.append(record)
                
                self.logger.info(f"履歴読み込み完了: {len(self.detection_history)}件")
            
        except Exception as e:
            self.logger.error(f"履歴読み込みエラー: {e}")
    
    def get_current_status(self) -> Dict:
        """現在の状態取得"""
        return {
            'timestamp': datetime.now().isoformat(),
            'is_monitoring': self.is_monitoring,
            'current_counts': dict(self.current_counts),
            'total_objects': sum(self.current_counts.values()),
            'last_detection_time': self.last_detection_time,
            'history_count': len(self.detection_history)
        }
    
    def get_statistics(self, hours: int = 24) -> Dict:
        """統計情報取得"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 指定時間内の記録を抽出
        recent_records = [
            record for record in self.detection_history
            if datetime.fromisoformat(record['timestamp']) > cutoff_time
        ]
        
        if not recent_records:
            return {}
        
        # 統計計算
        stats = {
            'period_hours': hours,
            'total_records': len(recent_records),
            'average_counts': {},
            'max_counts': {},
            'min_counts': {},
            'detection_rate': len(recent_records) / hours if hours > 0 else 0
        }
        
        # クラス別統計
        all_classes = set()
        for record in recent_records:
            all_classes.update(record['counts'].keys())
        
        for class_name in all_classes:
            counts = [record['counts'].get(class_name, 0) for record in recent_records]
            stats['average_counts'][class_name] = sum(counts) / len(counts)
            stats['max_counts'][class_name] = max(counts)
            stats['min_counts'][class_name] = min(counts)
        
        return stats


if __name__ == "__main__":
    # テスト実行
    monitor = FactoryMonitor()
    
    print("工場監視システム - テストモード")
    print("現在の状態:", monitor.get_current_status())
    
    # サンプル画像があれば処理
    test_image = "test_image.jpg"
    if os.path.exists(test_image):
        print(f"\nテスト画像処理: {test_image}")
        result = monitor.process_single_image(test_image)
        print("検出結果:", result)
    else:
        print(f"\nテスト画像 '{test_image}' が見つかりません")
        print("Webカメラでテストする場合は camera_connection.py を使用してください") 