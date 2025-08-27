#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚛 KIRII フォークリフト自動ラベル作成ツール
==================================================
既存のYOLO11nモデルを使って自動的にラベルを作成します
"""

import os
import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
import argparse

class AutoLabelCreator:
    def __init__(self, model_path="yolo11n.pt", confidence=0.3):
        """
        自動ラベル作成ツールの初期化
        
        Args:
            model_path: YOLOモデルのパス
            confidence: 検出信頼度の閾値
        """
        self.model_path = model_path
        self.confidence = confidence
        self.model = None
        
        # フォークリフト関連のクラスID（YOLO11nの既存クラス）
        self.forklift_classes = {
            2: "car",      # 車
            5: "bus",      # バス
            7: "truck",    # トラック
            3: "motorcycle", # バイク
            8: "boat"      # ボート（フォークリフトの一部として）
        }
        
        print(f"🚛 フォークリフト自動ラベル作成ツール")
        print(f"📁 モデル: {model_path}")
        print(f"🎯 信頼度閾値: {confidence}")
        print("=" * 50)
    
    def load_model(self):
        """YOLOモデルを読み込み"""
        try:
            print("📥 YOLOモデルを読み込み中...")
            self.model = YOLO(self.model_path)
            print("✅ モデル読み込み完了")
            return True
        except Exception as e:
            print(f"❌ モデル読み込みエラー: {e}")
            return False
    
    def detect_objects(self, image_path):
        """
        画像からオブジェクトを検出
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            list: 検出結果のリスト
        """
        try:
            results = self.model(image_path, conf=self.confidence)
            detections = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # 座標を取得
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        
                        # フォークリフト関連クラスのみ対象
                        if class_id in self.forklift_classes:
                            detections.append({
                                'class_id': class_id,
                                'confidence': confidence,
                                'bbox': [x1, y1, x2, y2]
                            })
            
            return detections
        except Exception as e:
            print(f"❌ 検出エラー ({image_path}): {e}")
            return []
    
    def convert_to_yolo_format(self, detections, image_width, image_height):
        """
        検出結果をYOLO形式に変換
        
        Args:
            detections: 検出結果のリスト
            image_width: 画像の幅
            image_height: 画像の高さ
            
        Returns:
            list: YOLO形式のラベルリスト
        """
        yolo_labels = []
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            
            # YOLO形式に変換（中心座標、幅、高さ、正規化）
            center_x = (x1 + x2) / 2 / image_width
            center_y = (y1 + y2) / 2 / image_height
            width = (x2 - x1) / image_width
            height = (y2 - y1) / image_height
            
            # フォークリフトクラス（0）として保存
            yolo_labels.append(f"0 {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}")
        
        return yolo_labels
    
    def process_images(self, image_dir, label_dir):
        """
        画像ディレクトリ内の全画像を処理
        
        Args:
            image_dir: 画像ディレクトリのパス
            label_dir: ラベル保存ディレクトリのパス
        """
        if not self.load_model():
            return
        
        # ディレクトリ作成
        os.makedirs(label_dir, exist_ok=True)
        
        # 画像ファイルを取得
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        image_files = []
        
        for ext in image_extensions:
            image_files.extend(Path(image_dir).glob(f"*{ext}"))
            image_files.extend(Path(image_dir).glob(f"*{ext.upper()}"))
        
        print(f"📊 処理対象画像: {len(image_files)}枚")
        
        processed_count = 0
        labeled_count = 0
        
        for image_path in image_files:
            try:
                # 画像を読み込み
                image = cv2.imread(str(image_path))
                if image is None:
                    print(f"⚠️ 画像読み込み失敗: {image_path}")
                    continue
                
                height, width = image.shape[:2]
                
                # オブジェクト検出
                detections = self.detect_objects(str(image_path))
                
                if detections:
                    # YOLO形式に変換
                    yolo_labels = self.convert_to_yolo_format(detections, width, height)
                    
                    # ラベルファイルを保存
                    label_path = Path(label_dir) / f"{image_path.stem}.txt"
                    with open(label_path, 'w') as f:
                        f.write('\n'.join(yolo_labels))
                    
                    labeled_count += 1
                    print(f"✅ {image_path.name}: {len(detections)}個のオブジェクトを検出")
                else:
                    print(f"⚠️ {image_path.name}: オブジェクト未検出")
                
                processed_count += 1
                
            except Exception as e:
                print(f"❌ 処理エラー ({image_path}): {e}")
        
        print("\n" + "=" * 50)
        print(f"📊 処理完了")
        print(f"📁 処理画像: {processed_count}枚")
        print(f"🏷️ ラベル作成: {labeled_count}枚")
        print(f"📂 ラベル保存先: {label_dir}")
    
    def process_dataset(self, dataset_path="./dataset"):
        """
        データセット全体を処理
        
        Args:
            dataset_path: データセットのルートパス
        """
        print("🚛 データセット全体を自動ラベル作成中...")
        
        # 学習画像
        train_images = os.path.join(dataset_path, "images", "train")
        train_labels = os.path.join(dataset_path, "labels", "train")
        
        if os.path.exists(train_images):
            print(f"\n📚 学習画像を処理中...")
            self.process_images(train_images, train_labels)
        
        # 検証画像
        val_images = os.path.join(dataset_path, "images", "val")
        val_labels = os.path.join(dataset_path, "labels", "val")
        
        if os.path.exists(val_images):
            print(f"\n🔍 検証画像を処理中...")
            self.process_images(val_images, val_labels)

def main():
    parser = argparse.ArgumentParser(description="フォークリフト自動ラベル作成ツール")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLOモデルのパス")
    parser.add_argument("--confidence", type=float, default=0.3, help="検出信頼度の閾値")
    parser.add_argument("--dataset", default="./dataset", help="データセットのパス")
    
    args = parser.parse_args()
    
    # 自動ラベル作成ツールを初期化
    labeler = AutoLabelCreator(args.model, args.confidence)
    
    # データセット全体を処理
    labeler.process_dataset(args.dataset)

if __name__ == "__main__":
    main() 