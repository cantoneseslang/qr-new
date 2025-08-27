#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🖼️ KIRII ラベル付き画像表示ツール
==================================================
自動ラベル作成の結果を視覚的に確認します
"""

import cv2
import numpy as np
import os
from pathlib import Path
import argparse

class LabeledImageViewer:
    def __init__(self, dataset_dir="./dataset"):
        """
        ラベル付き画像表示ツールの初期化
        
        Args:
            dataset_dir: データセットディレクトリ
        """
        self.dataset_dir = Path(dataset_dir)
        self.train_images = self.dataset_dir / "images" / "train"
        self.train_labels = self.dataset_dir / "labels" / "train"
        self.val_images = self.dataset_dir / "images" / "val"
        self.val_labels = self.dataset_dir / "labels" / "val"
        
        # クラス名
        self.class_names = {
            0: "forklift",
            1: "person", 
            2: "pallet",
            3: "box",
            4: "warning_sign",
            5: "safety_cone"
        }
        
        # クラス色
        self.class_colors = {
            0: (0, 255, 0),    # 緑（フォークリフト）
            1: (255, 0, 0),    # 青（人）
            2: (0, 0, 255),    # 赤（パレット）
            3: (255, 255, 0),  # シアン（箱）
            4: (255, 0, 255),  # マゼンタ（警告標識）
            5: (0, 255, 255)   # 黄色（安全コーン）
        }
    
    def load_labels(self, label_path):
        """ラベルファイルを読み込み"""
        labels = []
        if label_path.exists():
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        x_center = float(parts[1])
                        y_center = float(parts[2])
                        width = float(parts[3])
                        height = float(parts[4])
                        labels.append((class_id, x_center, y_center, width, height))
        return labels
    
    def draw_boxes(self, image, labels):
        """画像にバウンディングボックスを描画"""
        img_h, img_w = image.shape[:2]
        
        for class_id, x_center, y_center, width, height in labels:
            # 絶対座標に変換
            x1 = int((x_center - width/2) * img_w)
            y1 = int((y_center - height/2) * img_h)
            x2 = int((x_center + width/2) * img_w)
            y2 = int((y_center + height/2) * img_h)
            
            # 座標を画像範囲内に制限
            x1 = max(0, min(x1, img_w-1))
            y1 = max(0, min(y1, img_h-1))
            x2 = max(0, min(x2, img_w-1))
            y2 = max(0, min(y2, img_h-1))
            
            # 色を取得
            color = self.class_colors.get(class_id, (255, 255, 255))
            
            # バウンディングボックスを描画
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # ラベルテキストを描画
            class_name = self.class_names.get(class_id, f"class_{class_id}")
            label_text = f"{class_name}"
            
            # テキストサイズを取得
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            (text_width, text_height), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)
            
            # テキスト背景を描画
            cv2.rectangle(image, (x1, y1-text_height-baseline-5), (x1+text_width+5, y1), color, -1)
            
            # テキストを描画
            cv2.putText(image, label_text, (x1+2, y1-baseline-2), font, font_scale, (255, 255, 255), thickness)
    
    def view_images(self, mode="train", start_index=0):
        """画像を表示"""
        if mode == "train":
            image_dir = self.train_images
            label_dir = self.train_labels
        else:
            image_dir = self.val_images
            label_dir = self.val_labels
        
        # 画像ファイル一覧
        image_files = sorted([f for f in image_dir.iterdir() if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])
        
        if not image_files:
            print(f"❌ {mode}画像が見つかりません")
            return
        
        print(f"🖼️ {mode}画像表示モード")
        print(f"📊 総画像数: {len(image_files)}枚")
        print("💡 操作方法:")
        print("  - スペースキー: 次の画像")
        print("  - b: 前の画像")
        print("  - q: 終了")
        print()
        
        current_index = start_index
        while current_index < len(image_files):
            img_file = image_files[current_index]
            label_file = label_dir / f"{img_file.stem}.txt"
            
            # 画像を読み込み
            image = cv2.imread(str(img_file))
            if image is None:
                print(f"❌ 画像を読み込めません: {img_file}")
                current_index += 1
                continue
            
            # ラベルを読み込み
            labels = self.load_labels(label_file)
            
            # バウンディングボックスを描画
            self.draw_boxes(image, labels)
            
            # 画像サイズを調整
            display_image = cv2.resize(image, (800, 600))
            
            # 情報を表示
            info_text = f"{mode.upper()}: {current_index+1}/{len(image_files)} - {img_file.name}"
            cv2.putText(display_image, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # ラベル情報を表示
            label_info = f"Labels: {len(labels)}"
            cv2.putText(display_image, label_info, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 画像を表示
            cv2.imshow(f'ラベル付き画像 - {mode}', display_image)
            
            # キー入力待ち
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('q'):  # qキーで終了
                break
            elif key == ord('b'):  # bキーで前の画像
                current_index = max(0, current_index - 1)
            else:  # その他のキーで次の画像
                current_index += 1
        
        cv2.destroyAllWindows()
        print("✅ 画像表示終了")

def main():
    parser = argparse.ArgumentParser(description="ラベル付き画像表示ツール")
    parser.add_argument("--mode", choices=["train", "val"], default="train", help="表示モード")
    parser.add_argument("--start", type=int, default=0, help="開始インデックス")
    parser.add_argument("--dataset", default="./dataset", help="データセットディレクトリ")
    
    args = parser.parse_args()
    
    viewer = LabeledImageViewer(args.dataset)
    viewer.view_images(args.mode, args.start)

if __name__ == "__main__":
    main() 