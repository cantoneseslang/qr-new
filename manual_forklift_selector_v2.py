#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 KIRII 手動フォークリフト選別ツール v2
==================================================
動画からフレームを抽出し、手動でフォークリフト画像を選別します
"""

import cv2
import numpy as np
import os
import time
from pathlib import Path
import argparse
import shutil

class ManualForkliftSelectorV2:
    def __init__(self, video_path, output_dir="./dataset", frame_interval=60):
        """
        手動フォークリフト選別ツールの初期化
        
        Args:
            video_path: 入力動画のパス
            output_dir: 出力ディレクトリ
            frame_interval: フレーム抽出間隔（60フレームごと）
        """
        self.video_path = video_path
        self.output_dir = Path(output_dir)
        self.frame_interval = frame_interval
        
        # 出力ディレクトリ作成
        self.train_dir = self.output_dir / "images" / "train"
        self.val_dir = self.output_dir / "images" / "val"
        self.train_dir.mkdir(parents=True, exist_ok=True)
        self.val_dir.mkdir(parents=True, exist_ok=True)
        
        # 選択された画像のリスト
        self.selected_images = []
        
    def extract_frames(self):
        """動画からフレームを抽出"""
        print(f"🎬 動画からフレームを抽出中: {self.video_path}")
        
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"❌ 動画を開けません: {self.video_path}")
            return False
        
        frame_count = 0
        extracted_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % self.frame_interval == 0:
                # フレームを表示
                display_frame = cv2.resize(frame, (800, 600))
                cv2.imshow('フォークリフト選別 - スペースキーで選択、ESCでスキップ', display_frame)
                
                key = cv2.waitKey(0) & 0xFF
                
                if key == 27:  # ESC
                    print(f"⏭️ フレーム {frame_count} をスキップ")
                elif key == 32:  # スペースキー
                    # 画像を保存
                    filename = f"frame_{frame_count:06d}.jpg"
                    save_path = self.train_dir / filename
                    cv2.imwrite(str(save_path), frame)
                    self.selected_images.append(filename)
                    print(f"✅ フレーム {frame_count} を選択: {filename}")
                    extracted_count += 1
                elif key == ord('q'):  # qキーで終了
                    break
            
            frame_count += 1
        
        cap.release()
        cv2.destroyAllWindows()
        
        print(f"🎯 選択完了: {extracted_count}枚の画像を選択")
        return True
    
    def split_train_val(self, val_ratio=0.2):
        """学習用と検証用に分割"""
        if not self.selected_images:
            print("⚠️ 選択された画像がありません")
            return False
        
        # ランダムに分割
        np.random.shuffle(self.selected_images)
        split_idx = int(len(self.selected_images) * (1 - val_ratio))
        
        train_images = self.selected_images[:split_idx]
        val_images = self.selected_images[split_idx:]
        
        # 検証用画像を移動
        for img_name in val_images:
            src_path = self.train_dir / img_name
            dst_path = self.val_dir / img_name
            if src_path.exists():
                shutil.move(str(src_path), str(dst_path))
        
        print(f"📊 分割結果:")
        print(f"  学習用: {len(train_images)}枚")
        print(f"  検証用: {len(val_images)}枚")
        
        return True
    
    def run(self):
        """メイン実行"""
        print("🎯 KIRII 手動フォークリフト選別ツール v2")
        print("=" * 50)
        print(f"📹 動画: {self.video_path}")
        print(f"📁 出力: {self.output_dir}")
        print(f"⏱️ 抽出間隔: {self.frame_interval}フレーム")
        print()
        print("💡 操作方法:")
        print("  - スペースキー: フォークリフトが映っている画像を選択")
        print("  - ESC: このフレームをスキップ")
        print("  - q: 選別を終了")
        print()
        
        if self.extract_frames():
            self.split_train_val()
            print("✅ フォークリフト選別完了!")
            return True
        else:
            print("❌ フレーム抽出に失敗しました")
            return False

def main():
    parser = argparse.ArgumentParser(description="手動フォークリフト選別ツール")
    parser.add_argument("video_path", help="入力動画のパス")
    parser.add_argument("--output", default="./dataset", help="出力ディレクトリ")
    parser.add_argument("--interval", type=int, default=60, help="フレーム抽出間隔")
    
    args = parser.parse_args()
    
    selector = ManualForkliftSelectorV2(args.video_path, args.output, args.interval)
    selector.run()

if __name__ == "__main__":
    main() 