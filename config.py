#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工場監視システム設定ファイル
"""

# YOLO設定
YOLO_MODEL = 'yolo11n.pt'  # 使用するYOLOモデル
CONFIDENCE_THRESHOLD = 0.5  # 検出信頼度閾値
NMS_THRESHOLD = 0.45       # Non-Maximum Suppression閾値

# カメラ設定
CAMERA_CONFIG = {
    'rtsp_timeout': 30,        # RTSP接続タイムアウト（秒）
    'frame_width': 1920,       # フレーム幅
    'frame_height': 1080,      # フレーム高さ
    'fps': 30,                 # フレームレート
    'buffer_size': 1           # バッファサイズ
}

# IPカメラURL例
CAMERA_URLS = {
    'hikvision': 'rtsp://admin:password@{ip}:554/Streaming/Channels/101',
    'dahua': 'rtsp://admin:password@{ip}:554/cam/realmonitor?channel=1&subtype=0',
    'axis': 'rtsp://{ip}/axis-media/media.amp',
    'foscam': 'rtsp://admin:password@{ip}:88/videoMain',
    'generic_mjpeg': 'http://{ip}/mjpeg',
    'webcam': 0  # ローカルWebカメラ
}

# 監視設定
MONITORING_CONFIG = {
    'detection_interval': 5,    # 検出間隔（秒）
    'save_interval': 60,        # データ保存間隔（秒）
    'max_history_records': 1000, # 最大履歴保持数
    'enable_logging': True,     # ログ出力有効
    'log_level': 'INFO'        # ログレベル
}

# 在庫アラート設定
INVENTORY_ALERTS = {
    'enable_alerts': True,      # アラート機能有効
    'alert_thresholds': {       # 製品別アラート閾値
        'person': 2,            # 人が2人以下でアラート
        'car': 5,              # 車が5台以下でアラート
        'truck': 3,            # トラックが3台以下でアラート
        # 実際の製品に合わせて設定
    },
    'alert_cooldown': 300      # アラート間隔（秒）
}

# データ保存設定
DATA_CONFIG = {
    'data_dir': 'data',                    # データ保存ディレクトリ
    'history_file': 'detection_history.json', # 履歴ファイル名
    'images_dir': 'images',                # 画像保存ディレクトリ
    'save_detection_images': True,         # 検出結果画像保存
    'image_format': 'jpg',                 # 画像フォーマット
    'compress_images': True                # 画像圧縮
}

# Web UI設定
WEB_CONFIG = {
    'host': '0.0.0.0',         # サーバーホスト
    'port': 5024,              # サーバーポート
    'debug': False,            # デバッグモード
    'auto_refresh_interval': 5, # 自動更新間隔（秒）
    'enable_cors': True        # CORS有効
}

# ネットワーク設定
NETWORK_CONFIG = {
    'connection_timeout': 30,   # 接続タイムアウト
    'read_timeout': 30,        # 読み込みタイムアウト
    'retry_attempts': 3,       # 再試行回数
    'retry_delay': 5           # 再試行間隔（秒）
}

# 製品マスター（実際の工場製品に合わせて設定）
PRODUCT_MASTER = {
    'person': {
        'name': '作業員',
        'category': 'human',
        'alert_threshold': 2,
        'count_as_inventory': False  # 在庫としてカウントしない
    },
    'car': {
        'name': '自動車',
        'category': 'vehicle',
        'alert_threshold': 5,
        'count_as_inventory': True
    },
    'truck': {
        'name': 'トラック',
        'category': 'vehicle', 
        'alert_threshold': 3,
        'count_as_inventory': True
    }
    # 実際の製品を追加
}

# システム設定
SYSTEM_CONFIG = {
    'max_cpu_usage': 80,       # 最大CPU使用率（%）
    'max_memory_usage': 4096,  # 最大メモリ使用量（MB）
    'enable_gpu': True,        # GPU使用有効
    'gpu_device': 0,           # GPU デバイス番号
    'thread_count': 4          # 処理スレッド数
}
