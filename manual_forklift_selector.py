#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎯 KIRII 手動フォークリフト選別ツール
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

class ManualForkliftSelector:
    def __init__(self, video_path, output_dir="./dataset", frame_interval=30):
        """
        手動フォークリフト選別ツールの初期化
        
        Args:
            video_path: 入力動画のパス
            output_dir: 出力ディレクトリ
            frame_interval: フレーム抽出間隔（30フレームごと）
        """
        self.video_path = video_path
        self.output_dir = Path(output_dir)
        self.frame_interval = frame_interval
        
        # 出力ディレクトリ作成
        self.train_dir = self.output_dir / "images" / "train"
        self.val_dir = self.output_dir / "images" / "val"
        self.train_dir.mkdir(parents=True, exist_ok=True)
        self.val_dir.mkdir(parents=True, exist_ok=True)
        
        # 統計情報
        self.total_frames = 0
        self.selected_frames = 0
        self.skipped_frames = 0
        
        print(f"🎯 手動フォークリフト選別ツール")
        print(f"📹 動画: {video_path}")
        print(f"📁 出力先: {output_dir}")
        print(f"⏱️ フレーム間隔: {frame_interval}")
        print("=" * 50)
    
    def extract_frames(self):
        """動画からフレームを抽出"""
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            print(f"❌ 動画を開けません: {self.video_path}")
            return False
        
        # 動画情報を取得
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        
        print(f"📹 動画情報:")
        print(f"   - 総フレーム数: {total_frames}")
        print(f"   - FPS: {fps}")
        print(f"   - 再生時間: {duration:.1f}秒")
        print(f"   - 抽出予定フレーム数: {total_frames // self.frame_interval}")
        
        frame_count = 0
        extracted_count = 0
        
        print("\n🎬 フレーム抽出開始...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            
            # 指定間隔でフレームを抽出
            if frame_count % self.frame_interval == 0:
                # フレームを保存
                frame_path = self.train_dir / f"frame_{frame_count:06d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                extracted_count += 1
                
                if extracted_count % 10 == 0:
                    print(f"📸 抽出済み: {extracted_count}フレーム")
        
        cap.release()
        self.total_frames = extracted_count
        
        print(f"✅ フレーム抽出完了: {extracted_count}フレーム")
        return True
    
    def manual_selection(self):
        """手動でフォークリフト画像を選別"""
        print("\n🎯 手動選別開始...")
        print("💡 操作方法:")
        print("   - 'y' または 'Enter': フォークリフトあり（選択）")
        print("   - 'n' または 'Space': フォークリフトなし（スキップ）")
        print("   - 'q': 終了")
        print("   - 'b': 前のフレームに戻る")
        print("   - 's': 現在のフレームを保存（強制選択）")
        
        # 抽出されたフレームを取得
        frame_files = sorted(self.train_dir.glob("*.jpg"))
        if not frame_files:
            print("❌ 抽出されたフレームが見つかりません")
            return False
        
        selected_frames = []
        current_index = 0
        
        while current_index < len(frame_files):
            frame_path = frame_files[current_index]
            
            # フレームを読み込み
            frame = cv2.imread(str(frame_path))
            if frame is None:
                current_index += 1
                continue
            
            # フレーム情報を表示
            info_text = f"Frame {current_index + 1}/{len(frame_files)}: {frame_path.name}"
            cv2.putText(frame, info_text, (10, 30), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 選択状況を表示
            status_text = f"Selected: {len(selected_frames)} | Skipped: {self.skipped_frames}"
            cv2.putText(frame, status_text, (10, 60), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # フレームを表示
            cv2.imshow('Manual Forklift Selection', frame)
            
            # キー入力待機
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('y') or key == 13:  # Enter
                # フォークリフトあり - 選択
                selected_frames.append(frame_path)
                self.selected_frames += 1
                print(f"✅ 選択: {frame_path.name}")
                current_index += 1
            elif key == ord('n') or key == 32:  # Space
                # フォークリフトなし - スキップ
                self.skipped_frames += 1
                print(f"⏭️ スキップ: {frame_path.name}")
                current_index += 1
            elif key == ord('s'):
                # 強制保存
                selected_frames.append(frame_path)
                self.selected_frames += 1
                print(f"💾 強制選択: {frame_path.name}")
                current_index += 1
            elif key == ord('b'):
                # 前のフレームに戻る
                if current_index > 0:
                    current_index -= 1
                    # 前の選択を取り消し
                    if selected_frames and selected_frames[-1] == frame_files[current_index]:
                        selected_frames.pop()
                        self.selected_frames -= 1
                    else:
                        self.skipped_frames -= 1
                    print(f"⬅️ 前のフレームに戻る")
        
        cv2.destroyAllWindows()
        
        print(f"\n📊 選別結果:")
        print(f"   - 選択されたフレーム: {len(selected_frames)}")
        print(f"   - スキップされたフレーム: {self.skipped_frames}")
        print(f"   - 選択率: {(len(selected_frames)/self.total_frames)*100:.1f}%")
        
        return selected_frames
    
    def organize_dataset(self, selected_frames):
        """データセットを整理（学習用と検証用に分割）"""
        if not selected_frames:
            print("❌ 選択されたフレームがありません")
            return False
        
        print(f"\n📁 データセット整理中...")
        
        # 学習用と検証用に分割（80:20）
        train_count = int(len(selected_frames) * 0.8)
        train_frames = selected_frames[:train_count]
        val_frames = selected_frames[train_count:]
        
        # 検証用ディレクトリに移動
        for frame_path in val_frames:
            val_path = self.val_dir / frame_path.name
            shutil.move(str(frame_path), str(val_path))
        
        print(f"📊 データセット分割:")
        print(f"   - 学習用: {len(train_frames)}枚")
        print(f"   - 検証用: {len(val_frames)}枚")
        
        return True
    
    def cleanup(self):
        """不要なファイルを削除"""
        print(f"\n🧹 クリーンアップ中...")
        
        # 選択されなかったフレームを削除
        remaining_files = list(self.train_dir.glob("*.jpg"))
        if remaining_files:
            for file_path in remaining_files:
                file_path.unlink()
            print(f"   - 削除されたフレーム: {len(remaining_files)}枚")
        
        print("✅ クリーンアップ完了")
    
    def run(self):
        """メイン実行関数"""
        # 1. フレーム抽出
        if not self.extract_frames():
            return False
        
        # 2. 手動選別
        selected_frames = self.manual_selection()
        if not selected_frames:
            return False
        
        # 3. データセット整理
        if not self.organize_dataset(selected_frames):
            return False
        
        # 4. クリーンアップ
        self.cleanup()
        
        print(f"\n🎉 手動選別完了!")
        print(f"📁 データセット準備完了:")
        print(f"   - 学習用画像: {len(list(self.train_dir.glob('*.jpg')))}枚")
        print(f"   - 検証用画像: {len(list(self.val_dir.glob('*.jpg')))}枚")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="手動フォークリフト選別ツール")
    parser.add_argument("video_path", help="入力動画のパス")
    parser.add_argument("--output", default="./dataset", help="出力ディレクトリ")
    parser.add_argument("--interval", type=int, default=30, help="フレーム抽出間隔")
    
    args = parser.parse_args()
    
    # 動画ファイルの存在確認
    if not os.path.exists(args.video_path):
        print(f"❌ 動画ファイルが見つかりません: {args.video_path}")
        return
    
    # 手動選別ツールを実行
    selector = ManualForkliftSelector(args.video_path, args.output, args.interval)
    selector.run()

if __name__ == "__main__":
    main() 