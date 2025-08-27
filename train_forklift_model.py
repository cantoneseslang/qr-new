#!/usr/bin/env python3
"""
フォークリフト専用YOLOモデル学習スクリプト
フォークリフト検出に特化したモデルを学習します
"""

import os
import yaml
from ultralytics import YOLO
import shutil

def setup_forklift_dataset():
    """フォークリフトデータセット構造をセットアップ"""
    print("🚛 フォークリフトデータセット構造をセットアップ中...")
    
    # 必要なディレクトリを作成
    directories = [
        'dataset/images/train',
        'dataset/images/val', 
        'dataset/labels/train',
        'dataset/labels/val'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ {directory} を作成")
    
    print("✅ フォークリフトデータセット構造のセットアップ完了")

def check_forklift_dataset():
    """フォークリフトデータセットの状態をチェック"""
    print("\n🔍 フォークリフトデータセット状態チェック中...")
    
    # 画像ファイル数をチェック
    train_images = len([f for f in os.listdir('dataset/images/train') if f.endswith(('.jpg', '.jpeg', '.png'))])
    val_images = len([f for f in os.listdir('dataset/images/val') if f.endswith(('.jpg', '.jpeg', '.png'))])
    
    # ラベルファイル数をチェック
    train_labels = len([f for f in os.listdir('dataset/labels/train') if f.endswith('.txt')])
    val_labels = len([f for f in os.listdir('dataset/labels/val') if f.endswith('.txt')])
    
    print(f"📊 学習画像: {train_images}枚")
    print(f"📊 検証画像: {val_images}枚")
    print(f"📊 学習ラベル: {train_labels}個")
    print(f"📊 検証ラベル: {val_labels}個")
    
    # フォークリフト画像の確認（ラベルファイルの存在で判定）
    forklift_images = 0
    for label_file in os.listdir('dataset/labels/train'):
        if label_file.endswith('.txt'):
            label_path = os.path.join('dataset/labels/train', label_file)
            try:
                with open(label_path, 'r') as f:
                    content = f.read().strip()
                    if content and any(line.startswith('0 ') for line in content.split('\n')):
                        forklift_images += 1
            except:
                continue
    
    print(f"🚛 フォークリフト関連画像: {forklift_images}枚")
    
    if train_images == 0:
        print("⚠️ 学習画像がありません。フォークリフト画像を追加してください。")
        return False
    
    if val_images == 0:
        print("⚠️ 検証画像がありません。フォークリフト画像を追加してください。")
        return False
    
    if forklift_images < 3:
        print("⚠️ フォークリフト画像が少なすぎます。最低3枚以上必要です。")
        return False
    
    print("✅ フォークリフトデータセットチェック完了")
    return True

def train_forklift_model():
    """フォークリフト専用モデルの学習を実行"""
    print("\n🎯 フォークリフト専用モデル学習開始...")
    
    # ベースモデルを読み込み
    print("📦 ベースモデル (yolo11n.pt) を読み込み中...")
    model = YOLO('yolo11n.pt')
    
    # フォークリフト専用学習設定
    training_args = {
        'data': 'forklift_dataset.yaml',  # フォークリフト専用データセット設定
        'epochs': 150,                    # エポック数を増加（フォークリフト検出精度向上のため）
        'imgsz': 640,                     # 画像サイズ
        'batch': 16,                      # バッチサイズ
        'device': 'cpu',                  # CPUで学習
        'workers': 8,                     # ワーカー数
        'patience': 30,                   # 早期停止の忍耐値（フォークリフト検出に特化）
        'save': True,                     # モデル保存
        'save_period': 10,                # 10エポックごとに保存
        'cache': False,                   # キャッシュ無効
        'verbose': True,                  # 詳細出力
        'seed': 42,                       # 乱数シード
        'deterministic': True,            # 再現性確保
        'single_cls': False,              # マルチクラス（フォークリフト + 関連物体）
        'rect': False,                    # 矩形学習無効
        'cos_lr': True,                   # コサイン学習率スケジューリング
        'close_mosaic': 10,               # モザイク拡張終了エポック
        'resume': False,                  # 学習再開無効
        'amp': True,                      # 混合精度学習有効
        'lr0': 0.01,                      # 初期学習率
        'lrf': 0.01,                      # 最終学習率
        'momentum': 0.937,                # モーメンタム
        'weight_decay': 0.0005,           # 重み減衰
        'warmup_epochs': 3.0,             # ウォームアップエポック
        'warmup_momentum': 0.8,           # ウォームアップモーメンタム
        'warmup_bias_lr': 0.1,            # ウォームアップバイアス学習率
        'box': 7.5,                       # ボックス損失重み
        'cls': 0.5,                       # クラス損失重み
        'dfl': 1.5,                       # DFL損失重み
        # 'fl_gamma': 0.0,                  # 焦点損失ガンマ（削除）
        'label_smoothing': 0.0,           # ラベルスムージング
        'nbs': 64,                        # 名目バッチサイズ
        'overlap_mask': True,             # マスク重複
        'mask_ratio': 4,                  # マスク比率
        'dropout': 0.0,                   # ドロップアウト
        'val': True,                      # 検証実行
        'plots': True,                    # プロット生成
    }
    
    print("🚀 フォークリフト学習開始...")
    print(f"📋 学習設定: {training_args}")
    
    try:
        # 学習実行
        results = model.train(**training_args)
        
        print("✅ フォークリフト学習完了!")
        print(f"📊 最終mAP: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
        
        # 最良モデルをコピー
        best_model_path = results.save_dir / 'weights' / 'best.pt'
        if best_model_path.exists():
            shutil.copy(best_model_path, 'forklift_model.pt')
            print("✅ 最良フォークリフトモデルを forklift_model.pt として保存")
        
        return True
        
    except Exception as e:
        print(f"❌ フォークリフト学習エラー: {e}")
        return False

def validate_forklift_model():
    """学習済みフォークリフトモデルの検証"""
    print("\n🔍 学習済みフォークリフトモデル検証中...")
    
    if not os.path.exists('forklift_model.pt'):
        print("❌ 学習済みフォークリフトモデルが見つかりません")
        return False
    
    try:
        # モデル読み込み
        model = YOLO('forklift_model.pt')
        
        # 検証実行
        results = model.val(data='forklift_dataset.yaml')
        
        print("✅ フォークリフトモデル検証完了")
        print(f"📊 mAP50: {results.box.map50}")
        print(f"📊 mAP50-95: {results.box.map}")
        
        # フォークリフトクラスの詳細結果
        if hasattr(results, 'names') and 0 in results.names:
            print(f"🚛 フォークリフト検出精度: {results.box.map50}")
        
        return True
        
    except Exception as e:
        print(f"❌ フォークリフト検証エラー: {e}")
        return False

def main():
    """メイン実行関数"""
    print("🚛 KIRII フォークリフト専用YOLOモデル学習システム")
    print("=" * 60)
    
    # 1. データセットセットアップ
    setup_forklift_dataset()
    
    # 2. データセットチェック
    if not check_forklift_dataset():
        print("\n❌ フォークリフトデータセットが不完全です。以下の手順を実行してください:")
        print("1. dataset/images/train/ にフォークリフト画像を配置（最低10枚以上）")
        print("2. dataset/images/val/ にフォークリフト画像を配置（学習用とは別の画像）") 
        print("3. dataset/labels/train/ に対応するラベルファイルを配置")
        print("4. dataset/labels/val/ に対応するラベルファイルを配置")
        print("\n📝 ラベルファイルはYOLO形式（class_id x_center y_center width height）で作成してください")
        print("📝 フォークリフトは class_id=0 としてラベリングしてください")
        return
    
    # 3. 学習実行
    if train_forklift_model():
        # 4. 検証実行
        validate_forklift_model()
        print("\n🎉 フォークリフト学習プロセス完了!")
        print("📁 学習結果:")
        print("  - forklift_model.pt: 最良フォークリフトモデル")
        print("  - runs/detect/train/: 学習ログとグラフ")
        print("\n🚛 フォークリフト検出モデルの準備完了!")
    else:
        print("\n❌ フォークリフト学習に失敗しました")

if __name__ == '__main__':
    main() 