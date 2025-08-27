#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚛 KIRII フォークリフト検出モデル - 時間範囲テスト
============================================================
特定時間範囲（3:02-4:30）でフォークリフト検出をテスト
"""

import cv2
import numpy as np
from ultralytics import YOLO
import os
import time
from pathlib import Path

class ForkliftTimeRangeTester:
    def __init__(self, model_path="forklift_model.pt"):
        """フォークリフト時間範囲テストシステム初期化"""
        print("🚛 KIRII フォークリフト検出モデル - 時間範囲テスト")
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
        
        # 時間範囲設定（秒）
        self.start_time = 3 * 60 + 2  # 3:02 (182秒)
        self.end_time = 4 * 60 + 30   # 4:30 (270秒)
        
    def test_video_time_range(self, video_path):
        """特定時間範囲でフォークリフト検出テスト"""
        print(f"\n🎬 時間範囲テスト開始: {video_path}")
        print(f"⏰ テスト時間範囲: {self.start_time//60}:{self.start_time%60:02d} - {self.end_time//60}:{self.end_time%60:02d}")
        
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
        print(f"  - 総時間: {total_frames/fps:.1f}秒")
        
        # 時間範囲をフレーム番号に変換
        start_frame = int(self.start_time * fps)
        end_frame = int(self.end_time * fps)
        
        print(f"📈 処理フレーム範囲: {start_frame} - {end_frame}")
        print(f"📈 処理フレーム数: {end_frame - start_frame}")
        
        # 出力動画設定
        output_path = f"forklift_detection_3min02_4min30_{Path(video_path).stem}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        
        # 検出統計
        detection_stats = {
            'total_frames': 0,
            'frames_with_forklift': 0,
            'total_forklifts': 0,
            'start_time': time.time()
        }
        
        print(f"\n🎯 フォークリフト検出開始（時間範囲: {self.start_time//60}:{self.start_time%60:02d}-{self.end_time//60}:{self.end_time%60:02d}）...")
        print(f"💡 検出閾値: {self.confidence_threshold} (10%)")
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            current_time = frame_count / fps
            
            # 時間範囲外はスキップ
            if current_time < self.start_time:
                continue
            if current_time > self.end_time:
                break
            
            detection_stats['total_frames'] += 1
            
            # 進捗表示
            if frame_count % 30 == 0:  # 30フレームごと
                progress = ((current_time - self.start_time) / (self.end_time - self.start_time)) * 100
                elapsed = time.time() - detection_stats['start_time']
                fps_processed = detection_stats['total_frames'] / elapsed if elapsed > 0 else 0
                print(f"📈 進捗: {progress:.1f}% (時間: {current_time//60:.0f}:{current_time%60:02.0f}) - {fps_processed:.1f} FPS")
            
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
                print(f"🚛 時間 {current_time//60:.0f}:{current_time%60:02.0f} (フレーム{frame_count}): {forklifts_in_frame}個のフォークリフトを検出")
            
            # 統計情報を画面に表示
            stats_text = f"Time: {current_time//60:.0f}:{current_time%60:02.0f}"
            cv2.putText(annotated_frame, stats_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            forklift_text = f"Forklifts: {forklifts_in_frame}"
            cv2.putText(annotated_frame, forklift_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            frame_text = f"Frame: {frame_count}"
            cv2.putText(annotated_frame, frame_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 出力動画に書き込み
            out.write(annotated_frame)
        
        # リソース解放
        cap.release()
        out.release()
        
        # 結果表示
        elapsed_time = time.time() - detection_stats['start_time']
        print(f"\n🎉 時間範囲フォークリフト検出テスト完了!")
        print(f"📊 検出結果:")
        print(f"  - 処理時間: {elapsed_time:.1f}秒")
        print(f"  - 処理FPS: {detection_stats['total_frames']/elapsed_time:.1f}")
        print(f"  - 処理フレーム数: {detection_stats['total_frames']}")
        print(f"  - フォークリフト検出フレーム: {detection_stats['frames_with_forklift']}")
        print(f"  - 総フォークリフト検出数: {detection_stats['total_forklifts']}")
        print(f"  - 検出率: {(detection_stats['frames_with_forklift']/detection_stats['total_frames'])*100:.1f}%")
        
        print(f"\n📁 出力ファイル:")
        print(f"  - {output_path}")
        
        return output_path, detection_stats

def main():
    """メイン関数"""
    # フォークリフト時間範囲テストシステム初期化
    tester = ForkliftTimeRangeTester("forklift_model.pt")
    
    # テスト用動画ファイル
    video_path = '/Users/sakonhiroki/Desktop/screeshot/画面収録 2025-07-31 11.27.02.mov'
    
    # 動画テスト実行
    output_path, stats = tester.test_video_time_range(video_path)
    
    print(f"\n🚛 時間範囲フォークリフト検出テスト完了!")
    print(f"📁 結果動画: {output_path}")

if __name__ == "__main__":
    main() 