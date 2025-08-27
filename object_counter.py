#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工場監視システム - 物体カウント処理
高度な物体カウント・在庫管理機能
"""

import cv2
import numpy as np
import json
import time
from datetime import datetime, timedelta
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Optional, Set
import logging
from dataclasses import dataclass

from config import PRODUCT_MASTER, INVENTORY_ALERTS


@dataclass
class DetectedObject:
    """検出された物体の情報"""
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    center: Tuple[int, int]
    area: float
    timestamp: datetime
    object_id: Optional[str] = None


@dataclass
class CountingZone:
    """カウント対象エリア"""
    name: str
    polygon: List[Tuple[int, int]]
    target_classes: Set[str]
    enabled: bool = True


class AdvancedObjectCounter:
    """高度な物体カウントシステム"""
    
    def __init__(self):
        """初期化"""
        self.logger = logging.getLogger(__name__)
        
        # カウント履歴
        self.count_history = deque(maxlen=1000)
        self.current_counts = defaultdict(int)
        self.object_buffer = deque(maxlen=100)  # 最近検出された物体
        
        # カウントゾーン
        self.counting_zones = []
        
        # 重複除去用
        self.processed_objects = set()
        self.object_tracking = {}
        
        # 統計情報
        self.session_stats = {
            'start_time': datetime.now(),
            'total_detections': 0,
            'class_totals': defaultdict(int),
            'peak_counts': defaultdict(int)
        }
        
        self.logger.info("高度物体カウントシステムが初期化されました")
    
    def add_counting_zone(self, zone: CountingZone):
        """カウントゾーン追加"""
        self.counting_zones.append(zone)
        self.logger.info(f"カウントゾーン追加: {zone.name}")
    
    def remove_counting_zone(self, zone_name: str):
        """カウントゾーン削除"""
        self.counting_zones = [z for z in self.counting_zones if z.name != zone_name]
        self.logger.info(f"カウントゾーン削除: {zone_name}")
    
    def count_objects_in_frame(self, detections: List[DetectedObject]) -> Dict[str, int]:
        """
        フレーム内の物体カウント
        
        Args:
            detections: 検出された物体リスト
            
        Returns:
            Dict[str, int]: クラス別カウント結果
        """
        frame_counts = defaultdict(int)
        
        # 基本カウント
        for obj in detections:
            if self._is_valid_detection(obj):
                frame_counts[obj.class_name] += 1
        
        # ゾーン別カウント
        zone_counts = self._count_objects_in_zones(detections)
        
        # 重複除去処理
        filtered_counts = self._remove_duplicates(frame_counts, detections)
        
        # カウント履歴更新
        self._update_count_history(filtered_counts)
        
        # 統計更新
        self._update_statistics(filtered_counts)
        
        return dict(filtered_counts)
    
    def _is_valid_detection(self, obj: DetectedObject) -> bool:
        """検出の有効性チェック"""
        # 信頼度チェック
        if obj.confidence < 0.5:
            return False
        
        # サイズチェック（異常に小さい・大きい物体を除外）
        if obj.area < 100 or obj.area > 500000:
            return False
        
        # 製品マスターチェック
        if obj.class_name not in PRODUCT_MASTER:
            return False
        
        # 在庫対象チェック
        product_info = PRODUCT_MASTER[obj.class_name]
        if not product_info.get('count_as_inventory', True):
            return False
        
        return True
    
    def _count_objects_in_zones(self, detections: List[DetectedObject]) -> Dict[str, Dict[str, int]]:
        """ゾーン別物体カウント"""
        zone_counts = {}
        
        for zone in self.counting_zones:
            if not zone.enabled:
                continue
            
            zone_count = defaultdict(int)
            
            for obj in detections:
                if obj.class_name in zone.target_classes:
                    if self._point_in_polygon(obj.center, zone.polygon):
                        zone_count[obj.class_name] += 1
            
            zone_counts[zone.name] = dict(zone_count)
        
        return zone_counts
    
    def _point_in_polygon(self, point: Tuple[int, int], polygon: List[Tuple[int, int]]) -> bool:
        """点がポリゴン内にあるかチェック"""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _remove_duplicates(self, counts: Dict[str, int], detections: List[DetectedObject]) -> Dict[str, int]:
        """重複検出除去"""
        # 単純な重複除去（位置ベース）
        filtered_detections = []
        
        for obj in detections:
            is_duplicate = False
            
            # 既存の検出と比較
            for existing in self.object_buffer:
                if (obj.class_name == existing.class_name and 
                    self._calculate_distance(obj.center, existing.center) < 50 and
                    abs((obj.timestamp - existing.timestamp).total_seconds()) < 1.0):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                filtered_detections.append(obj)
        
        # バッファ更新
        self.object_buffer.extend(filtered_detections)
        
        # フィルター後のカウント
        filtered_counts = defaultdict(int)
        for obj in filtered_detections:
            if self._is_valid_detection(obj):
                filtered_counts[obj.class_name] += 1
        
        return filtered_counts
    
    def _calculate_distance(self, point1: Tuple[int, int], point2: Tuple[int, int]) -> float:
        """2点間の距離計算"""
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def _update_count_history(self, counts: Dict[str, int]):
        """カウント履歴更新"""
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'counts': dict(counts),
            'total': sum(counts.values())
        }
        
        self.count_history.append(history_entry)
        self.current_counts = counts.copy()
    
    def _update_statistics(self, counts: Dict[str, int]):
        """統計情報更新"""
        self.session_stats['total_detections'] += sum(counts.values())
        
        for class_name, count in counts.items():
            self.session_stats['class_totals'][class_name] += count
            if count > self.session_stats['peak_counts'][class_name]:
                self.session_stats['peak_counts'][class_name] = count
    
    def get_inventory_summary(self) -> Dict:
        """在庫サマリー取得"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'current_counts': dict(self.current_counts),
            'total_items': sum(self.current_counts.values()),
            'by_category': defaultdict(int),
            'alerts': []
        }
        
        # カテゴリ別集計
        for class_name, count in self.current_counts.items():
            if class_name in PRODUCT_MASTER:
                category = PRODUCT_MASTER[class_name].get('category', 'unknown')
                summary['by_category'][category] += count
        
        # アラートチェック
        for class_name, count in self.current_counts.items():
            if class_name in INVENTORY_ALERTS['alert_thresholds']:
                threshold = INVENTORY_ALERTS['alert_thresholds'][class_name]
                if count <= threshold:
                    summary['alerts'].append({
                        'class_name': class_name,
                        'current_count': count,
                        'threshold': threshold,
                        'severity': 'warning' if count > 0 else 'critical'
                    })
        
        return summary
    
    def get_trend_analysis(self, hours: int = 24) -> Dict:
        """トレンド分析"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 指定時間内の履歴を抽出
        recent_history = [
            entry for entry in self.count_history
            if datetime.fromisoformat(entry['timestamp']) > cutoff_time
        ]
        
        if not recent_history:
            return {}
        
        # トレンド計算
        trends = {}
        
        for class_name in set().union(*[entry['counts'].keys() for entry in recent_history]):
            counts = [entry['counts'].get(class_name, 0) for entry in recent_history]
            
            if len(counts) > 1:
                # 線形回帰による傾向
                x = np.arange(len(counts))
                slope = np.polyfit(x, counts, 1)[0]
                
                trends[class_name] = {
                    'current': counts[-1],
                    'average': np.mean(counts),
                    'max': max(counts),
                    'min': min(counts),
                    'trend_slope': slope,
                    'trend_direction': 'increasing' if slope > 0.1 else 'decreasing' if slope < -0.1 else 'stable'
                }
        
        return {
            'period_hours': hours,
            'analysis_time': datetime.now().isoformat(),
            'trends': trends,
            'total_records': len(recent_history)
        }
    
    def export_count_data(self, filepath: str, format: str = 'json'):
        """カウントデータエクスポート"""
        try:
            export_data = {
                'export_time': datetime.now().isoformat(),
                'session_stats': dict(self.session_stats),
                'current_counts': dict(self.current_counts),
                'count_history': list(self.count_history),
                'counting_zones': [
                    {
                        'name': zone.name,
                        'polygon': zone.polygon,
                        'target_classes': list(zone.target_classes),
                        'enabled': zone.enabled
                    }
                    for zone in self.counting_zones
                ]
            }
            
            if format.lower() == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"カウントデータエクスポート完了: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"エクスポートエラー: {e}")
            return False
    
    def draw_counting_zones(self, frame: np.ndarray) -> np.ndarray:
        """カウントゾーン描画"""
        annotated_frame = frame.copy()
        
        for zone in self.counting_zones:
            if not zone.enabled:
                continue
            
            # ポリゴン描画
            points = np.array(zone.polygon, np.int32)
            cv2.polylines(annotated_frame, [points], True, (0, 255, 255), 2)
            
            # 半透明塗りつぶし
            overlay = annotated_frame.copy()
            cv2.fillPoly(overlay, [points], (0, 255, 255))
            cv2.addWeighted(annotated_frame, 0.8, overlay, 0.2, 0, annotated_frame)
            
            # ゾーン名表示
            if zone.polygon:
                center_x = int(np.mean([p[0] for p in zone.polygon]))
                center_y = int(np.mean([p[1] for p in zone.polygon]))
                cv2.putText(
                    annotated_frame,
                    zone.name,
                    (center_x - 50, center_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )
        
        return annotated_frame
    
    def reset_session_stats(self):
        """セッション統計リセット"""
        self.session_stats = {
            'start_time': datetime.now(),
            'total_detections': 0,
            'class_totals': defaultdict(int),
            'peak_counts': defaultdict(int)
        }
        self.logger.info("セッション統計をリセットしました")


class ObjectCountVisualizer:
    """物体カウント可視化クラス"""
    
    def __init__(self, counter: AdvancedObjectCounter):
        """初期化"""
        self.counter = counter
        self.logger = logging.getLogger(__name__)
    
    def create_count_dashboard(self, frame: np.ndarray, counts: Dict[str, int]) -> np.ndarray:
        """カウントダッシュボード作成"""
        dashboard_frame = frame.copy()
        
        # ダッシュボード背景
        dashboard_height = 200
        dashboard = np.zeros((dashboard_height, frame.shape[1], 3), dtype=np.uint8)
        
        # タイトル
        cv2.putText(
            dashboard,
            "Factory Inventory Monitor - YOLO11",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )
        
        # 現在時刻
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(
            dashboard,
            f"Time: {current_time}",
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (200, 200, 200),
            1
        )
        
        # カウント情報
        y_offset = 90
        total_count = sum(counts.values())
        cv2.putText(
            dashboard,
            f"Total Objects: {total_count}",
            (20, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        # クラス別カウント
        x_offset = 250
        for i, (class_name, count) in enumerate(counts.items()):
            color = self._get_class_color(class_name)
            cv2.putText(
                dashboard,
                f"{class_name}: {count}",
                (x_offset + (i * 150), y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )
        
        # アラート表示
        alerts = self.counter.get_inventory_summary().get('alerts', [])
        if alerts:
            alert_y = 130
            cv2.putText(
                dashboard,
                "ALERTS:",
                (20, alert_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 255),
                2
            )
            
            for i, alert in enumerate(alerts[:3]):  # 最大3つまで表示
                alert_text = f"{alert['class_name']}: {alert['current_count']}/{alert['threshold']}"
                cv2.putText(
                    dashboard,
                    alert_text,
                    (100 + (i * 200), alert_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1
                )
        
        # ダッシュボードを元フレームに結合
        result_frame = np.vstack([dashboard_frame, dashboard])
        
        return result_frame
    
    def _get_class_color(self, class_name: str) -> Tuple[int, int, int]:
        """クラス別色取得"""
        colors = {
            'person': (255, 0, 0),
            'car': (0, 255, 0),
            'truck': (0, 0, 255),
            'motorcycle': (255, 255, 0),
            'bus': (255, 0, 255),
            'bicycle': (0, 255, 255),
        }
        return colors.get(class_name, (128, 128, 128))


if __name__ == "__main__":
    # テスト実行
    counter = AdvancedObjectCounter()
    
    # テスト用カウントゾーン追加
    test_zone = CountingZone(
        name="Test Zone",
        polygon=[(100, 100), (300, 100), (300, 300), (100, 300)],
        target_classes={'person', 'car'}
    )
    counter.add_counting_zone(test_zone)
    
    print("高度物体カウントシステム - テストモード")
    print("在庫サマリー:", counter.get_inventory_summary()) 