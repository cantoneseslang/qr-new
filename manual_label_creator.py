#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🖱️ KIRII 手動フォークリフトラベル作成ツール
==================================================
マウスでフォークリフトを手動で囲んでラベルを作成します
"""

import cv2
import numpy as np
import os
from pathlib import Path
import argparse

class ManualLabelCreator:
    def __init__(self, image_dir="./dataset/images", label_dir="./dataset/labels"):
        """
        手動ラベル作成ツールの初期化
        
        Args:
            image_dir: 画像ディレクトリのパス
            label_dir: ラベル保存ディレクトリのパス
        """
        self.image_dir = Path(image_dir)
        self.label_dir = Path(label_dir)
        
        # ラベルディレクトリ作成
        self.train_label_dir = self.label_dir / "train"
        self.val_label_dir = self.label_dir / "val"
        self.train_label_dir.mkdir(parents=True, exist_ok=True)
        self.val_label_dir.mkdir(parents=True, exist_ok=True)
        
        # マウス操作の状態
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.current_annotations = []
        
        # クラス名
        self.class_names = {
            0: "forklift",
            1: "person", 
            2: "pallet",
            3: "box",
            4: "warning_sign",
            5: "safety_cone"
        }
        
        # クラス色（BGR）
        self.class_colors = {
            0: (0, 255, 0),    # フォークリフト: 緑
            1: (255, 0, 0),    # 人: 青
            2: (0, 0, 255),    # パレット: 赤
            3: (255, 255, 0),  # 箱: シアン
            4: (0, 255, 255),  # 警告標識: 黄
            5: (255, 0, 255)   # 安全コーン: マゼンタ
        }
        
        self.current_class = 0  # フォークリフト（デフォルト）
        self.current_image_path = None
        self.current_image = None
        self.image_files = []
        self.current_index = 0
        
        print(f"🖱️ 手動フォークリフトラベル作成ツール")
        print(f"📁 画像ディレクトリ: {image_dir}")
        print(f"📁 ラベル保存先: {label_dir}")
        print("=" * 50)
    
    def mouse_callback(self, event, x, y, flags, param):
        """マウスコールバック関数"""
        if event == cv2.EVENT_LBUTTONDOWN:
            # マウス左ボタン押下
            self.drawing = True
            self.start_point = (x, y)
            self.end_point = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE:
            # マウス移動
            if self.drawing:
                self.end_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            # マウス左ボタン離上
            self.drawing = False
            if self.start_point and self.end_point:
                # バウンディングボックスを追加
                x1, y1 = self.start_point
                x2, y2 = self.end_point
                # 座標を正規化
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
                
                if x2 > x1 and y2 > y1:  # 有効なボックス
                    self.current_annotations.append({
                        'class': self.current_class,
                        'bbox': [x1, y1, x2, y2]
                    })
                    print(f"✅ バウンディングボックス追加: {self.class_names[self.current_class]}")
    
    def draw_annotations(self, image):
        """アノテーションを描画"""
        display_image = image.copy()
        
        # 既存のアノテーションを描画
        for ann in self.current_annotations:
            x1, y1, x2, y2 = ann['bbox']
            class_id = ann['class']
            color = self.class_colors.get(class_id, (0, 255, 0))
            
            # バウンディングボックスを描画
            cv2.rectangle(display_image, (x1, y1), (x2, y2), color, 2)
            
            # ラベルを描画
            label = self.class_names.get(class_id, f"class_{class_id}")
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(display_image, (x1, y1 - label_size[1] - 10), 
                        (x1 + label_size[0], y1), color, -1)
            cv2.putText(display_image, label, (x1, y1 - 5), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 現在描画中のボックスを描画
        if self.drawing and self.start_point and self.end_point:
            x1, y1 = self.start_point
            x2, y2 = self.end_point
            color = self.class_colors.get(self.current_class, (0, 255, 0))
            cv2.rectangle(display_image, (x1, y1), (x2, y2), color, 2)
        
        return display_image
    
    def save_yolo_labels(self, image_path, annotations):
        """YOLO形式でラベルを保存"""
        if not annotations:
            return
        
        # 画像サイズを取得
        image = cv2.imread(str(image_path))
        if image is None:
            return
        
        height, width = image.shape[:2]
        
        # ラベルファイルパスを決定
        if "train" in str(image_path):
            label_path = self.train_label_dir / f"{image_path.stem}.txt"
        else:
            label_path = self.val_label_dir / f"{image_path.stem}.txt"
        
        # YOLO形式でラベルを保存
        with open(label_path, 'w') as f:
            for ann in annotations:
                x1, y1, x2, y2 = ann['bbox']
                class_id = ann['class']
                
                # YOLO形式に変換（中心座標、幅、高さ、正規化）
                center_x = (x1 + x2) / 2 / width
                center_y = (y1 + y2) / 2 / height
                box_width = (x2 - x1) / width
                box_height = (y2 - y1) / height
                
                f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {box_width:.6f} {box_height:.6f}\n")
        
        print(f"💾 ラベル保存: {label_path}")
    
    def load_image(self, image_path):
        """画像を読み込み"""
        self.current_image_path = image_path
        self.current_image = cv2.imread(str(image_path))
        if self.current_image is None:
            print(f"❌ 画像を読み込めません: {image_path}")
            return False
        
        # 既存のラベルを読み込み
        self.current_annotations = []
        if "train" in str(image_path):
            label_path = self.train_label_dir / f"{image_path.stem}.txt"
        else:
            label_path = self.val_label_dir / f"{image_path.stem}.txt"
        
        if label_path.exists():
            height, width = self.current_image.shape[:2]
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        center_x = float(parts[1])
                        center_y = float(parts[2])
                        box_width = float(parts[3])
                        box_height = float(parts[4])
                        
                        # 座標を変換
                        x1 = int((center_x - box_width/2) * width)
                        y1 = int((center_y - box_height/2) * height)
                        x2 = int((center_x + box_width/2) * width)
                        y2 = int((center_y + box_height/2) * height)
                        
                        self.current_annotations.append({
                            'class': class_id,
                            'bbox': [x1, y1, x2, y2]
                        })
        
        return True
    
    def annotate_image(self):
        """画像にアノテーションを追加"""
        if self.current_image is None:
            return False
        
        # ウィンドウを作成
        window_name = f"Manual Labeling - {self.current_image_path.name}"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self.mouse_callback)
        
        print(f"\n🎯 画像: {self.current_image_path.name}")
        print(f"📊 現在のアノテーション数: {len(self.current_annotations)}")
        print("💡 操作方法:")
        print("   - マウスドラッグ: バウンディングボックスを描画")
        print("   - 0-5: クラス選択 (0:フォークリフト, 1:人, 2:パレット, 3:箱, 4:警告標識, 5:安全コーン)")
        print("   - s: 保存")
        print("   - c: クリア")
        print("   - n: 次の画像")
        print("   - p: 前の画像")
        print("   - q: 終了")
        
        while True:
            # アノテーションを描画
            display_image = self.draw_annotations(self.current_image)
            
            # 情報を表示
            info_text = f"Class: {self.class_names[self.current_class]} | Annotations: {len(self.current_annotations)}"
            cv2.putText(display_image, info_text, (10, 30), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 画像を表示
            cv2.imshow(window_name, display_image)
            
            # キー入力処理
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                cv2.destroyWindow(window_name)
                return False
            elif key == ord('s'):
                # 保存
                self.save_yolo_labels(self.current_image_path, self.current_annotations)
            elif key == ord('c'):
                # クリア
                self.current_annotations = []
                print("🗑️ アノテーションをクリア")
            elif key == ord('n'):
                # 次の画像
                cv2.destroyWindow(window_name)
                return True
            elif key == ord('p'):
                # 前の画像
                cv2.destroyWindow(window_name)
                return 'prev'
            elif key in [ord(str(i)) for i in range(6)]:
                # クラス選択
                self.current_class = int(chr(key))
                print(f"🎨 クラス変更: {self.class_names[self.current_class]}")
        
        cv2.destroyWindow(window_name)
        return True
    
    def run(self):
        """メイン実行関数"""
        # 画像ファイルを取得
        train_images = list((self.image_dir / "train").glob("*.jpg"))
        val_images = list((self.image_dir / "val").glob("*.jpg"))
        self.image_files = train_images + val_images
        
        if not self.image_files:
            print("❌ 画像ファイルが見つかりません")
            return False
        
        print(f"📊 処理対象画像: {len(self.image_files)}枚")
        
        while self.current_index < len(self.image_files):
            image_path = self.image_files[self.current_index]
            
            # 画像を読み込み
            if not self.load_image(image_path):
                self.current_index += 1
                continue
            
            # アノテーション実行
            result = self.annotate_image()
            
            if result == False:
                break
            elif result == True:
                self.current_index += 1
            elif result == 'prev':
                if self.current_index > 0:
                    self.current_index -= 1
        
        print(f"\n🎉 ラベル作成完了!")
        print(f"📁 処理画像: {self.current_index}枚")
        
        return True

def main():
    parser = argparse.ArgumentParser(description="手動フォークリフトラベル作成ツール")
    parser.add_argument("--image-dir", default="./dataset/images", help="画像ディレクトリ")
    parser.add_argument("--label-dir", default="./dataset/labels", help="ラベル保存ディレクトリ")
    
    args = parser.parse_args()
    
    # 手動ラベル作成ツールを実行
    labeler = ManualLabelCreator(args.image_dir, args.label_dir)
    labeler.run()

if __name__ == "__main__":
    main() 