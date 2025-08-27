#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚛 KIRII フォークリフト検出モデル - 高速動画テスト
============================================================
フレーム間隔を大きくして動画全体を短時間で処理
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
import time
from pathlib import Path

class ForkliftVideoTesterFast:
    def __init__(self, model_path="forklift_model.pt"):
        """フォークリフト動画テストシステム初期化（高速版）"""
        print("🚛 KIRII フォークリフト検出モデル - 高速テスト")
        print("=" * 60)
        
        # モデル読み込み
        print(f"📦 フォークリフトモデル読み込み中: {model_path}")
        try:
            self.model = YOLO(model_path)
            print("✅ フォークリフトモデル読み込み完了")
        except Exception as e:
            print(f"❌ モデル読み込みエラー: {e}")
            return
        
        # クラス名設定
        self.class_names = {
            0: "forklift",
            1: "person", 
            2: "pallet",
            3: "box",
            4: "warning_sign",
            5: "safety_cone"
        }
        
        # 検出設定
        self.confidence_threshold = 0.1  # 10%
        self.iou_threshold = 0.3
        self.frame_interval = 30  # 30フレームごとに処理（2秒間隔）
        
    def test_video(self, video_path):
        """動画ファイルでフォークリフト検出テスト（高速版）"""
        print(f"\n🎬 高速動画テスト開始: {video_path}")
        
        # 動画ファイル確認
        if not os.path.exists(video_path):
            print(f"❌ 動画ファイルが見つかりません: {video_path}")
            return
        
        # 動画読み込み
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ 動画ファイルを開けません: {video_path}")
            return
        
        # 動画情報取得
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"📊 動画情報:")
        print(f"  - 解像度: {width}x{height}")
        print(f"  - FPS: {fps}")
        print(f"  - 総フレーム数: {total_frames}")
        print(f"  - 推定時間: {total_frames/fps:.1f}秒")
        print(f"  - 処理間隔: {self.frame_interval}フレーム ({self.frame_interval/fps:.1f}秒間隔)")
        
        # 出力動画設定
        output_path = f"forklift_detection_fast_{Path(video_path).stem}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # 検出統計
        detection_stats = {
            'total_frames': 0,
            'processed_frames': 0,
            'frames_with_forklift': 0,
            'total_forklifts': 0,
            'start_time': time.time()
        }
        
        print(f"\n🎯 フォークリフト検出開始（高速版）...")
        print(f"💡 検出閾値: {self.confidence_threshold} (10%)")
        print(f"💡 フレーム間隔: {self.frame_interval}")
        
        frame_count = 0
        processed_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            detection_stats['total_frames'] += 1
            
            # フレーム間隔で処理
            if frame_count % self.frame_interval == 0:
                processed_count += 1
                detection_stats['processed_frames'] += 1
                
                # 進捗表示
                progress = (frame_count / total_frames) * 100
                elapsed = time.time() - detection_stats['start_time']
                fps_processed = processed_count / elapsed if elapsed > 0 else 0
                print(f"📈 進捗: {progress:.1f}% (フレーム{frame_count}/{total_frames}) - 処理速度: {fps_processed:.1f} FPS")
                
                # フォークリフト検出
                results = self.model(frame, conf=self.confidence_threshold, iou=self.iou_threshold, verbose=False)
                
                # 検出結果描画
                annotated_frame = frame.copy()
                forklifts_in_frame = 0
                
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            # 座標取得
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                            confidence = box.conf[0].cpu().numpy()
                            class_id = int(box.cls[0].cpu().numpy())
                            
                            # フォークリフト検出の場合
                            if class_id == 0:  # forklift
                                forklifts_in_frame += 1
                                detection_stats['total_forklifts'] += 1
                                
                                # 信頼度に応じて色を変える
                                if confidence > 0.5:
                                    color = (0, 255, 0)  # 緑色（高信頼度）
                                elif confidence > 0.3:
                                    color = (0, 255, 255)  # 黄色（中信頼度）
                                else:
                                    color = (0, 165, 255)  # オレンジ（低信頼度）
                                
                                # バウンディングボックス描画
                                cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                                
                                # ラベル描画
                                label = f"Forklift: {confidence:.2f}"
                                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                                cv2.rectangle(annotated_frame, (int(x1), int(y1) - label_size[1] - 10), 
                                            (int(x1) + label_size[0], int(y1)), color, -1)
                                cv2.putText(annotated_frame, label, (int(x1), int(y1) - 5), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # フォークリフトが検出されたフレームをカウント
                if forklifts_in_frame > 0:
                    detection_stats['frames_with_forklift'] += 1
                    print(f"🚛 フレーム {frame_count}: {forklifts_in_frame}個のフォークリフトを検出")
                
                # 統計情報を画面に表示
                stats_text = f"Frame: {frame_count}/{total_frames}"
                cv2.putText(annotated_frame, stats_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                forklift_text = f"Forklifts: {forklifts_in_frame}"
                cv2.putText(annotated_frame, forklift_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                time_text = f"Time: {frame_count/fps:.1f}s"
                cv2.putText(annotated_frame, time_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # 出力動画に書き込み
                out.write(annotated_frame)
            else:
                # 処理しないフレームはそのまま出力
                out.write(frame)
        
        # リソース解放
        cap.release()
        out.release()
        
        # 結果表示
        elapsed_time = time.time() - detection_stats['start_time']
        print(f"\n🎉 高速フォークリフト検出テスト完了!")
        print(f"📊 検出結果:")
        print(f"  - 処理時間: {elapsed_time:.1f}秒")
        print(f"  - 総フレーム数: {detection_stats['total_frames']}")
        print(f"  - 処理フレーム数: {detection_stats['processed_frames']}")
        print(f"  - フォークリフト検出フレーム: {detection_stats['frames_with_forklift']}")
        print(f"  - 総フォークリフト検出数: {detection_stats['total_forklifts']}")
        print(f"  - 検出率: {(detection_stats['frames_with_forklift']/detection_stats['processed_frames'])*100:.1f}%")
        
        print(f"\n📁 出力ファイル:")
        print(f"  - {output_path}")
        
        return output_path, detection_stats

def main():
    """メイン関数"""
    # フォークリフト動画テストシステム初期化（高速版）
    tester = ForkliftVideoTesterFast("forklift_model.pt")
    
    # テスト用動画ファイル
    video_path = '/Users/sakonhiroki/Desktop/screeshot/画面収録 2025-07-31 11.27.02.mov'
    
    # 動画テスト実行
    output_path, stats = tester.test_video(video_path)
    
    print(f"\n🚛 高速フォークリフト検出テスト完了!")
    print(f"📁 結果動画: {output_path}")

if __name__ == "__main__":
    main() 