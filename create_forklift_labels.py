#!/usr/bin/env python3
"""
フォークリフト専用ラベル作成ツール
フォークリフト画像からYOLO形式のラベルファイルを作成します
"""

import os
import cv2
import numpy as np
from pathlib import Path

class ForkliftLabelCreator:
    def __init__(self):
        # フォークリフト専用クラス定義
        self.class_names = {
            0: 'forklift',        # フォークリフト（メイン）
            1: 'person',          # 人（運転手など）
            2: 'pallet',          # パレット
            3: 'box',             # 箱・荷物
            4: 'warning_sign',    # 警告標識
            5: 'safety_cone'      # 安全コーン
        }
        
        # クラス別の色設定
        self.class_colors = {
            0: (0, 255, 0),       # 緑 - フォークリフト
            1: (255, 0, 0),       # 青 - 人
            2: (0, 0, 255),       # 赤 - パレット
            3: (255, 255, 0),     # シアン - 箱
            4: (255, 0, 255),     # マゼンタ - 警告標識
            5: (0, 255, 255)      # イエロー - 安全コーン
        }
        
        self.current_class = 0  # デフォルトはフォークリフト
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.annotations = []
        
    def mouse_callback(self, event, x, y, flags, param):
        """マウスイベントコールバック"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
            self.end_point = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.end_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)
            
            # アノテーションを追加
            if self.start_point and self.end_point:
                x1, y1 = self.start_point
                x2, y2 = self.end_point
                
                # 座標を正規化
                x_center = (x1 + x2) / 2 / self.image_width
                y_center = (y1 + y2) / 2 / self.image_height
                width = abs(x2 - x1) / self.image_width
                height = abs(y2 - y1) / self.image_height
                
                annotation = {
                    'class_id': self.current_class,
                    'x_center': x_center,
                    'y_center': y_center,
                    'width': width,
                    'height': height,
                    'start_point': self.start_point,
                    'end_point': self.end_point
                }
                
                self.annotations.append(annotation)
                print(f"✅ アノテーション追加: {self.class_names[self.current_class]} ({x_center:.3f}, {y_center:.3f}, {width:.3f}, {height:.3f})")
    
    def draw_annotations(self, image):
        """アノテーションを描画"""
        for ann in self.annotations:
            x1, y1 = ann['start_point']
            x2, y2 = ann['end_point']
            color = self.class_colors[ann['class_id']]
            class_name = self.class_names[ann['class_id']]
            
            # バウンディングボックスを描画
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # クラス名を描画
            cv2.putText(image, class_name, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # 現在描画中のボックス
        if self.drawing and self.start_point and self.end_point:
            x1, y1 = self.start_point
            x2, y2 = self.end_point
            color = self.class_colors[self.current_class]
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
    
    def save_yolo_labels(self, image_path, output_dir):
        """YOLO形式のラベルファイルを保存"""
        if not self.annotations:
            print("⚠️ アノテーションがありません")
            return False
        
        # 画像ファイル名からラベルファイル名を生成
        image_name = Path(image_path).stem
        label_path = os.path.join(output_dir, f"{image_name}.txt")
        
        # YOLO形式でラベルファイルを作成
        with open(label_path, 'w') as f:
            for ann in self.annotations:
                line = f"{ann['class_id']} {ann['x_center']:.6f} {ann['y_center']:.6f} {ann['width']:.6f} {ann['height']:.6f}\n"
                f.write(line)
        
        print(f"✅ ラベルファイル保存: {label_path}")
        return True
    
    def annotate_image(self, image_path):
        """画像にアノテーションを追加"""
        # 画像を読み込み
        image = cv2.imread(image_path)
        if image is None:
            print(f"❌ 画像を読み込めません: {image_path}")
            return False
        
        self.image_height, self.image_width = image.shape[:2]
        print(f"📊 画像サイズ: {self.image_width}x{self.image_height}")
        
        # ウィンドウを作成
        window_name = f"フォークリフトラベル作成 - {os.path.basename(image_path)}"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self.mouse_callback)
        
        print("\n🎯 フォークリフトアノテーション操作:")
        print("  - マウスドラッグ: バウンディングボックスを描画")
        print("  - 数字キー: クラスを変更")
        print("  - 's': ラベルファイルを保存")
        print("  - 'c': アノテーションをクリア")
        print("  - 'q': 終了")
        print(f"  - 現在のクラス: {self.class_names[self.current_class]} (ID: {self.current_class})")
        print("\n📋 利用可能なクラス:")
        for class_id, class_name in self.class_names.items():
            print(f"    {class_id}: {class_name}")
        
        while True:
            # アノテーションを描画
            display_image = image.copy()
            self.draw_annotations(display_image)
            
            # 現在のクラス情報を表示
            info_text = f"Class: {self.class_names[self.current_class]} (ID: {self.current_class}) | Annotations: {len(self.annotations)}"
            cv2.putText(display_image, info_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow(window_name, display_image)
            
            key = cv2.waitKey(1) & 0xFF
            
            # キー入力処理
            if key == ord('q'):
                break
            elif key == ord('s'):
                output_dir = input("保存先ディレクトリを入力 (train/val): ").strip()
                if output_dir in ['train', 'val']:
                    label_dir = f"dataset/labels/{output_dir}"
                    os.makedirs(label_dir, exist_ok=True)
                    self.save_yolo_labels(image_path, label_dir)
                else:
                    print("❌ 無効なディレクトリ名です")
            elif key == ord('c'):
                self.annotations.clear()
                print("🗑️ アノテーションをクリアしました")
            elif key >= ord('0') and key <= ord('5'):
                # 数字キーでクラス変更
                class_id = key - ord('0')
                if class_id in self.class_names:
                    self.current_class = class_id
                    print(f"🔄 クラス変更: {self.class_names[self.current_class]} (ID: {self.current_class})")
        
        cv2.destroyAllWindows()
        return True

def main():
    """メイン実行関数"""
    print("🚛 KIRII フォークリフト専用ラベル作成ツール")
    print("=" * 50)
    
    # データセットディレクトリをチェック
    if not os.path.exists('dataset/images/train') and not os.path.exists('dataset/images/val'):
        print("❌ データセットディレクトリが見つかりません")
        print("先に train_forklift_model.py を実行してデータセット構造を作成してください")
        return
    
    # 画像ファイルを検索
    train_images = []
    val_images = []
    
    if os.path.exists('dataset/images/train'):
        train_images = [f for f in os.listdir('dataset/images/train') 
                       if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    if os.path.exists('dataset/images/val'):
        val_images = [f for f in os.listdir('dataset/images/val') 
                     if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    print(f"📊 学習画像: {len(train_images)}枚")
    print(f"📊 検証画像: {len(val_images)}枚")
    
    if not train_images and not val_images:
        print("❌ フォークリフト画像ファイルが見つかりません")
        print("dataset/images/train/ または dataset/images/val/ にフォークリフト画像を配置してください")
        return
    
    # 画像選択
    print("\n📁 アノテーション対象を選択:")
    if train_images:
        print("1. 学習画像 (train)")
    if val_images:
        print("2. 検証画像 (val)")
    
    choice = input("選択 (1/2): ").strip()
    
    if choice == "1" and train_images:
        image_dir = "dataset/images/train"
        images = train_images
    elif choice == "2" and val_images:
        image_dir = "dataset/images/val"
        images = val_images
    else:
        print("❌ 無効な選択です")
        return
    
    # 画像一覧表示
    print(f"\n📋 {image_dir} の画像一覧:")
    for i, image in enumerate(images[:10]):  # 最初の10枚のみ表示
        print(f"  {i+1}. {image}")
    
    if len(images) > 10:
        print(f"  ... 他 {len(images)-10}枚")
    
    # 画像選択
    try:
        image_choice = int(input(f"\nアノテーションする画像番号を選択 (1-{len(images)}): ")) - 1
        if 0 <= image_choice < len(images):
            selected_image = images[image_choice]
            image_path = os.path.join(image_dir, selected_image)
            
            print(f"\n🎯 選択された画像: {selected_image}")
            
            # フォークリフトラベル作成ツールを実行
            label_creator = ForkliftLabelCreator()
            label_creator.annotate_image(image_path)
            
        else:
            print("❌ 無効な画像番号です")
    except ValueError:
        print("❌ 無効な入力です")

if __name__ == '__main__':
    main() 