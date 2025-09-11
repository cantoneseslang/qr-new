# CCTV-YOLO 統合復元記録（最新版）

最終更新: 2025-08-22

このドキュメントは、以下2つの記録を統合し、最新の実装方針と運用手順を一本化したものです。
- ① `CCTV_YOLO_復元記録.md`（旧）
- ② `CCTV-YOLO-復活呪文.md`（新）

以後は本ドキュメントを正とし、①②は参照用のアーカイブとします。

---

## 1. システム全体方針（2025-08-09確定）
- ランタイムの正解ファイル: `cctv_streaming_fixed.py`
- ポート: 5013（`http://localhost:5013`）
- カメラ側中継: `http://192.168.0.98:18080`
- 認証: Basic（admin/admin）
- 重要URLパラメータ（ライブ強制）: `&live=1&realtime=1`
- 取得URL（統一）:
  - メイン: `http://192.168.0.98:18080/cgi-bin/guest/Video.cgi?media=MJPEG&live=1&realtime=1&nocache=<ts>`
  - 単一/分割: `http://192.168.0.98:18080/cgi-bin/guest/Video.cgi?media=MJPEG&channel={ch}&resolution=1&live=1&realtime=1`

---

## 2. 時系列（要点）

### 2025-07-26（① 復元記録）
- 正しい中継ルーター: `192.168.0.98:18080`
- 正しいベースURL: `.../Video.cgi?media=MJPEG`
- 失敗パターンやネットワーク経路を記録。`cctv_working_restored.py` を運用対象として復旧。

### 2025-07-28〜29（② 復活呪文）
- 重要パラメータ `&live=1&realtime=1` を徹底（同一映像/過去映像問題を解消）
- 単一/分割取得のURL生成を `get_channel_stream_url()` に統一
- 表示切替の中断機構（interruption）を導入
- 16同時取得は不可（順次取得へ方針転換）

### 2025-08-09（本統合・UI/挙動最終化）
- 正式ランタイムを `cctv_streaming_fixed.py`（5013）に決定
- 既存の比較表示は廃止。初期表示はメインストリーム（単一ビュー）
- フロントエンドの安定化:
  - ページロード時: `/relogin` → `/start_stream` を自動実行
  - ボタン配置: 上段に「停控/開控」「主面」「4面」「9面」「16面」、その下に 1〜16 の単一選択ボタン
  - 単一選択時はメイン更新を停止し、単一ポーリングに切替（持続）
  - 「主面」はリフレッシュ（停止→再ログイン→開始→単一ビュー）
  - 背景色を白統一、UIサイズ/配色を調整
- ポーリング間隔:
  - メイン: 3秒
  - 分割: 10秒（順次取得・負荷軽減）
  - 単一: 3秒
- ログ抑制: `werkzeug` INFO抑制、冪等起動、フレーム停止検知でセッション再生成

---

## 3. 環境構築・起動手順（完全版）

### 必要環境
- **Python**: 3.8以上
- **OS**: Windows 10/11（PowerShell対応）
- **ネットワーク**: CCTVサーバー `192.168.0.98:18080` へのアクセス

### 必要インストール
1. **依存関係のインストール**:
   ```bash
   pip install -r requirements.txt
   ```
   
2. **requirements.txt の内容**:
   ```
   Flask==2.3.3
   requests==2.31.0
   ultralytics
   opencv-python
   ```

### 起動手順（推奨・安定版）
**⚠️ 重要: 以下の手順以外は絶対に使用禁止**

#### 1. ポートキル手順（サーバー停止時）
```powershell
# 現在のPythonプロセスを強制終了
taskkill /F /IM python.exe

# 確認: プロセスが存在しないことを確認
Get-Process python -ErrorAction SilentlyContinue
```

#### 2. 再起動手順
```powershell
# プロジェクトディレクトリに移動（必須）
cd E:\factory_monitoring_system

# サーバー起動（これ以外のコマンドは禁止）
python cctv_streaming_fixed.py
```

#### 3. 使用するファイル（これ以外は禁止）
- **起動ファイル**: `cctv_streaming_fixed.py` のみ
- **Pythonバージョン**: システムにインストールされているPython 3.11以上
- **ポート**: 5013（固定・変更禁止）

#### 4. サーバー起動問題の解決手順（2025-08-26追加）
**⚠️ 重要: サーバーが起動しない場合の唯一の解決方法**

**問題の症状:**
- サーバーが起動しない
- ポート5013でLISTENING状態にならない
- 変更が反映されない

**解決手順（これ以外は禁止）:**
```powershell
# 1. 現在のプロセスを完全停止
taskkill /f /im python.exe 2>$null

# 2. 環境変数を設定してtorchエラーを回避
$env:TORCH_DISABLE_META=1

# 3. サーバーを起動
python cctv_streaming_fixed.py

# 4. 起動確認（10秒待機）
Start-Sleep -Seconds 10
netstat -ano | findstr :5013
```

**確認ポイント:**
- `LISTENING` 状態が表示されること
- ブラウザで `http://localhost:5013` にアクセスできること

**禁止事項:**
- 別の起動手順を試すこと
- 環境変数を設定しないこと
- プロセスを停止せずに起動すること

#### 4. 起動確認手順
```powershell
# ポート5013でリッスンしているか確認
netstat -an | Select-String ":5013"

# 正常な場合: LISTENING状態が表示される
# 異常な場合: TIME_WAITやSYN_SENTのみ表示される
```

#### 5. 禁止事項（絶対に実行しない）

- ❌ 他のPythonファイルでの起動
- ❌ 異なるポートでの起動
- ❌ デバッグモードでの起動（トラブル時以外）
- ❌ バックグラウンド起動（`&`や`start`の使用）

#### 6. トラブルシューティング時のみ
```powershell
# デバッグログ付き起動（問題解決後は通常起動に戻す）
$env:ENABLE_DEBUG_LOG="1"; python cctv_streaming_fixed.py
```

4. **ブラウザアクセス**:
   ```
   http://localhost:5013
   ```

### 重要な起動ファイル
- **正式ランタイム**: `cctv_streaming_fixed.py`
- **ポート**: 5013
- **文字エンコーディング**: UTF-8（必須）
- **デバッグモード**: オフ（推奨・安定性向上）
- **メモリ使用量**: 約225MB（正常範囲）

### 完全起動手順（これ以外は禁止）

#### 標準起動手順（毎回必ず実行）
```powershell
# 1. プロジェクトディレクトリに移動
cd E:\factory_monitoring_system

# 2. 既存プロセスを強制終了
taskkill /F /IM python.exe

# 3. プロセス終了確認
Get-Process python -ErrorAction SilentlyContinue

# 4. サーバー起動（これ以外のコマンドは禁止）
python cctv_streaming_fixed.py

# 5. 起動確認
netstat -an | Select-String ":5013"
```

#### 起動成功の確認方法
- ✅ ポート5013で`LISTENING`状態が表示される
- ✅ ブラウザで`http://localhost:5013`にアクセス可能
- ❌ `TIME_WAIT`や`SYN_SENT`のみの場合は起動失敗

#### 禁止コマンド（絶対に使用しない）
```powershell
# ❌ 禁止: exec形式での起動
python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"

# ❌ 禁止: バックグラウンド起動
python cctv_streaming_fixed.py &

# ❌ 禁止: 他のファイルでの起動
python app.py
python web_dashboard.py
```

### 自動リセット機能について
**元の目的：**
- 5分ごとにストリームを自動停止→再ログイン→再開
- フレーム停止やセッション切れを予防するため
- システムの「安定性向上」を狙った機能

**問題点：**
- 実際には逆効果で、5分ごとに強制リセットが発生
- システムが「自動爆弾」のように不安定になる
- エラーの蓄積でどんどん壊れる状況

**対応：**
- 2025-08-22: 自動リセット機能を完全無効化
- 手動リフレッシュ（「主面」ボタン）で対応
- システムの安定性が大幅に向上

### サーバー起動問題と解決策（2025-08-22）

**発生した問題：**
- サーバーが起動しても、Flaskアプリの実行前に停止
- ポート5013でリッスンしない
- フロントエンドから接続できない
- エラーログが表示されない

**原因の特定：**
- `psutil`パッケージのインポートでエラーが発生
- メモリ使用量の取得処理でクラッシュ
- サーバー起動部分で`app.run()`が実行されない

**解決策：**
```python
# 修正前（問題あり）
import psutil
process = psutil.Process()
print(f"💾 初期メモリ使用量: {process.memory_info().rss / 1024 / 1024:.1f} MB")

# 修正後（問題解決）
# import psutil
# process = psutil.Process()
# print(f"💾 初期メモリ使用量: {process.memory_info().rss / 1024 / 1024:.1f} MB")
```

**今後の予防策：**
1. **依存関係の確認**: 起動前に全パッケージの動作確認
2. **エラーハンドリング**: 起動部分での例外処理の強化
3. **段階的起動**: 各機能を段階的に有効化して問題箇所を特定
4. **ログ出力**: 起動過程での詳細ログ出力
5. **代替手段**: 問題のある機能の代替実装

**技術的教訓：**
- 外部パッケージ（psutil）の依存関係は慎重に管理
- サーバー起動部分での例外処理は必須
- 問題の特定には段階的なデバッグが効果的

### 起動確認
- サーバー起動メッセージ: `Running on http://127.0.0.1:5013`
- ブラウザでページロード後、自動で再ログイン→メインストリーム開始
- 「開控」ボタンでメインストリーム表示確認
- YOLOオブジェクト検知が動作（person, bicycle, car, bus, train, truck）

### トラブルシューティング
- **文字化けエラー**: 必ず `encoding='utf-8'` 付きで起動
- **モジュールエラー**: `pip install -r requirements.txt` で依存関係再インストール
- **接続エラー**: CCTVサーバー `192.168.0.98:18080` の稼働状況確認

### フロントエンド要件
- 単一選択（数字）時:
  - メイン更新タイマーを停止
  - `/get_multi_frames/1?channel={n}` で取得し、3秒間隔で更新
  - ビューは単一のまま持続
- 主面（リフレッシュ）:
  - `/stop_stream` → `/relogin` → `/start_stream` → 単一ビュー
- 分割（4/9/16）:
  - 順次取得でCCTV負荷を回避
  - 5秒間隔で更新

---

## 4. API 一覧（抜粋）
- `POST /start_stream` — メインストリーム開始（冪等）
- `POST /stop_stream` — 停止
- `POST /relogin` — セッション再生成
- `GET  /get_frame` — 現在フレーム（メイン）
- `GET  /get_multi_frames/<n>` — 分割フレーム
- `GET  /get_multi_frames/1?channel=<n>` — 単一フレーム

---

## 5. 既知の制限と対処
- 16同時取得は不可 → 順次取得（実質並列1）
- 過去映像/同一映像 → `&live=1&realtime=1` を必須化
- フレーム停止（>5秒） → 自動再ログイン→再開

---

## 6. ファイル方針（整理済み）
- 正式運用: `cctv_streaming_fixed.py`
- アーカイブ（`old_versions/` へ移動）:
  - `cctv_16channel_system.py`, `cctv_authenticated_system.py`, `cctv_complete_16ch.py`, `cctv_direct_test.py`
  - `cctv_dual_stream_system.py`, `cctv_forklift_integrated.py`, `cctv_kirii_wifi_system.py`
  - `cctv_real_monitoring_system.py`, `cctv_smooth_switch_system.py`, `cctv_stable_system.py`
  - `cctv_working_restored_backup.py`, `cctv_working_restored_original.py`, `cctv_working_restored.py`

---

## 7. YOLO検知システム統合（2025-08-22）

### 7.1 実装完了機能
- ✅ **メインストリーム（開控）**: YOLO検知有効、2秒間隔で検知実行
- ✅ **循面モード**: 4画面表示でYOLO検知有効、各チャンネルで検知実行
- ✅ **循拡モード**: 1.5倍拡大表示でYOLO検知有効
- ✅ **16面表示**: 削除済み（使用不可）

### 7.2 技術的実装ポイント
- **YOLO検知制御**: `self.enable_main_detection = True` でメインストリーム有効化
- **循面検知**: `get_specific_channels_frames(channel_list, with_detection=True)` で検知有効化
- **API統合**: `&dets=1` パラメータで検知要求を統一
- **検知間引き**: メインストリームは2秒間隔、循面は新規取得時のみ

### 7.3 検知ログ出力例
```
🔍 CH10 YOLO検知: 1 objects detected
🔍 CH1 YOLO検知: 1 objects detected  
🔍 CH11 YOLO検知: 1 objects detected
```

### 7.4 依存関係
- **必須ライブラリ**: `ultralytics`, `opencv-python`
- **モデルファイル**: `yolo11n.pt`（YOLO11n）
- **検知対象**: person, bicycle, car, bus, train, truck（クラスID: 0,1,2,5,6,7）

---

## 8. 既知のトラブルと回避（2025-08-22更新）

### 8.1 文字エンコーディング問題
- **症状**: `UnicodeDecodeError: 'cp950' codec can't decode byte 0x91`
- **原因**: Windows環境での文字エンコーディング不一致
- **解決**: `python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"` で起動

### 8.2 持続ストリーム過負荷
- **症状**: CCTVサーバー `Read timed out` エラー
- **原因**: 16チャンネル同時接続による過負荷
- **解決**: `self.working_channels = [1]` で負荷軽減

### 8.3 早期リターン問題
- **症状**: メインストリームが表示されない
- **原因**: `start_optimized_stream` での早期リターン条件
- **解決**: `if self.is_streaming:` ブロックの条件修正

### 8.4 YOLO検知不動作問題（2025-08-22解決）
- **症状**: 「循面」モードでYOLO検知が動作しない
- **原因**: 
  1. `get_specific_channels_frames` 関数でYOLO検知が実装されていない
  2. API呼び出しに `&dets=1` パラメータが不足
  3. `last_yolo_time` 変数の初期化漏れ
- **解決**:
  1. `get_specific_channels_frames(channel_list, with_detection=True)` で検知有効化
  2. JavaScript側で `&dets=1` パラメータを追加
  3. `self.last_yolo_time = 0` を初期化に追加
  4. `_get_channel_frame_with_detection` 関数を新規作成

### 8.5 構文エラー問題
- **症状**: `SyntaxError: expected 'except' or 'finally' block`
- **原因**: `try` ブロック内の `except` 文が不完全
- **解決**: YOLO検知処理部分に適切な `except` 文を追加
  - `cctv_working_test.py`, `cctv_yolo_system.py`
- 旧記録: ①②は参照用として残置（本書を参照）

---

## 7. 変更履歴（今日の修正・追記）
- 単一チャンネル選択時にメイン更新を停止し、単一ポーリングを開始するロジックを修正
- 数字ボタンのUI（サイズ/アクティブ表示）と上段ボタンの配置/文言を統一
- 既存の比較表示を完全撤去
- 初期表示を単一ビュー（メインストリーム）に固定。分割はボタン押下時のみ
- `/relogin` 自動実行とストール検知でセッション再生成
- `start_cctv_safe.*` の起動先を `cctv_streaming_fixed.py`（5013）へ変更
- 旧 `cctv_*` スクリプト群を `old_versions/` へアーカイブ移動

---

## 8. 検証チェックリスト
- [ ] ページロードでメインストリームが開始される
- [ ] 単一選択後も単一表示が持続する
- [ ] 「主面」で停止→再ログイン→再開→単一ビューに戻る
- [ ] 4/9/16で順次取得し、エラーでUIが止まらない
- [ ] フレーム停止後に自動復旧する

---

## 9. 追加実装（2025-08-09 完了分の詳細記録）

この章は、スクリプトが失われても完全復元できるよう、実装内容をロジック・API仕様レベルで詳細に残す。

### 9.1 画面/UI 改訂
- タイトルを「AI-DETECT-MONITOR」に変更（`<title>` と `<h1>` を同名で統一）。
- 左上ロゴを `static/kirii_logo.png` として表示。高さは 63px、ヘッダー余白は最小化。
- 単一ビューの外枠余白圧縮：
  - `.video-section` padding: 10px
  - `.video-frame` 高さ: 420px（モバイル ≤480px では 360px）
  - プレースホルダの line-height も同値に合わせる
- チャンネル数字列は常時表示に固定（4/9/16 でも `display: grid` 維持）。

### 9.2 ビュー制御ロジック（JS）
- 重要フラグ・タイマー
  - `singleChannelMode`（単一モード）
  - `updateInterval`（メイン3秒）
  - `singleInterval`（単一1.0秒）
  - `multiChannelInterval`（分割10秒）
  - 循環モード: `isCycling` / `cycleInterval`
- 主面（メイン）
  - ページロード時に `/relogin`→`/start_stream` 自動実行
  - 主面押下時は `singleChannelMode=false`、`singleInterval` 停止、循環停止、メイン3秒ポーリングを再開
- 単一（数字）
  - 数字押下で `singleChannelMode=true`、`updateInterval`/`multiChannelInterval` 停止、単一1.0秒ポーリング開始
  - 主面ボタンのアクティブは外す（単一選択強制）
- 分割（4/9/16）
  - `singleChannelMode=false` に戻し `singleInterval` 停止、循環停止
  - 取得は順次（CCTV負荷対策）、10秒間隔で更新（負荷軽減）
- 循環モード（「循面」）
  - トグル式。4面表示で指定チャンネルグループを20秒間隔で交互表示
  - グループA（20秒）: チャンネル2,3,4,7,11,14
  - グループB（20秒）: チャンネル1,5,10,13,14,15
  - 6面表示（3列×2行）のグリッドに指定チャンネルの映像を表示
  - 主面/分割/数字/停止/リフレッシュ時は必ず `stopCycle()` を呼び循環停止

### 9.3 API・サーバロジック（Flask/Python）
- 既存 `/start_stream`, `/stop_stream`, `/relogin`, `/get_frame` は維持。
- 分割/単一取得 `/get_multi_frames/<int:num_channels>` を拡張：
  - 単一取得は `/get_multi_frames/1?channel=<n>`
  - 検出を同時適用する場合は `dets=1` を付与
  - レスポンス例（単一・検出あり）：
    ```json
    {
      "success": true,
      "frames": { "<n>": "<base64jpeg>" },
      "channels": [<n>],
      "total_channels": 1,
      "is_combined": false,
      "detections": [ {"class":"person","confidence":0.83, "bbox":[x1,y1,x2,y2]} ]
    }
    ```
- 新規 `/single_stream?channel=<n>`（MJPEGプロキシ）も作成済みだが、現行UIでは未使用。将来の連続ストリームへ切替する際の選択肢として保持。

### 9.4 単一フレームの検出タイミング調整（遅延解消の核心）
- 目的：循環モードや単一切替直後に「枠の反映が遅れる」問題を解決。
- 実装：
  - `get_single_channel_frame_optimized(channel, with_detection: bool=False)` に引数追加
  - `with_detection=True` の時は、取得したJPEGをサーバ側で即座にYOLOへ通す
  - 枠を描画したフレームをJPEG再エンコード→base64返却（UI側での後追い合成を廃止）
  - 戻り値: `(frame_base64, detections_list)` に変更
  - `/get_multi_frames/1?channel=<n>&dets=1` でこの経路を使用

### 9.5 YOLO推論設定
- モデル: YOLO11n（`yolo11n.pt`）
- 画像前処理: 50%縮小（`scale_factor=0.5`）、`imgsz=320`、軽量化
- クラスフィルタ（許可クラスのみ検出）:
  - `0: person`, `1: bicycle`, `2: car`, `5: bus`, `6: train`, `7: truck`
- クラス別しきい値:
  - `person`: 0.25（低め）
  - その他: 0.40
- メインストリーム: 従来通り0.5秒間隔でフレームを処理（間引き）。
- 単一/循環: 1.0秒間隔で `/get_multi_frames/1?channel=<n>&dets=1` を叩き、サーバ側で枠を焼き込み済み画像を返却。

### 9.6 ネットワーク/接続安定化
- メインストリームは `&live=1&realtime=1&nocache=<ts>` を付与して常時ライブを強制。
- フレームが5秒以上更新されない場合はストール判定→`stop_stream()`→`reset_session()` を挟み再起動。
- 分割取得は順次（実質並列1）でCCTV側の負荷を軽減。

### 9.7 既知のトラブルと回避
- CCTV側の断続的な `ReadTimeout` や `ConnectionError` は一定確率で発生。UI側はステータス更新のみで致命エラー扱いにしない。
- `/single_stream` は一部MJPEGのバウンダリ処理差で互換性に揺らぎがあるため、現行はスナップショット方式を採用。
- **文字エンコーディング問題**: WindowsでUTF-8ファイルを実行する際は `encoding='utf-8'` を明示指定する。
- **持続ストリーム過負荷**: 16チャンネル同時接続は避け、メインストリーム方式を優先使用する。
- **早期リターン問題**: `is_streaming`フラグだけでなく`current_frame`の存在も確認してからリターンする。

### 9.8 変更点一覧（差分サマリ）
- タイトル: `AI-DETECT-MONITOR` へ変更
- チャンネル数字列: 常時表示
- 単一ポーリング: 0.5秒→1.0秒に変更（軽量推論併用）
- 循環モード: 変更（6面表示でグループA: 2,3,4,7,11,14 / グループB: 1,5,10,13,14,15 を20秒間隔で交互表示）
- API拡張: `/get_multi_frames/6?channels=<n1,n2,n3,n4,n5,n6>&dets=1` で6チャンネル一括取得
- 単一取得関数に `with_detection` 引数を追加、枠焼き込みの即時化
- YOLO: 許可クラス絞り込み＋personのみ低閾値（0.25）
- UIレイアウト微調整（余白圧縮、フレーム高さ420/360）

### 9.9 6画面表示実装時の重大な問題点と解決過程

#### 9.9.1 私が犯した致命的な問題点
1. **コード全体の把握不足**
   - 2135行あるファイルの全体を確認せずに部分的な修正のみ実施
   - 最後の部分（1900行以降）を確認していなかった

2. **根本原因の特定失敗**
   - ログでは6チャンネルのデータ取得が成功しているのに、UI表示が変わらない問題を放置
   - 対処療法ばかりで根本原因を特定しようとしなかった

3. **CSSの競合問題の見落とし**
   - `.cycle-expanded`クラスがJavaScriptで設定した3列×2行レイアウトを2列×2行に上書きしていることに気づかなかった
   - ブラウザの開発者ツールでCSSの競合を確認するという基本的なデバッグ手順を怠った

4. **適当な修正と再起動の繰り返し**
   - 問題を特定せずに「修正したから再起動」を繰り返し、ユーザーの時間を無駄にした
   - 根本的な解決策を提示せず、表面的な修正のみ実施

#### 9.9.2 最終的に特定された根本原因
1. **CSSクラスの競合**
   ```css
   .cycle-expanded {
       grid-template-columns: 1fr 1fr;  /* ← 2列に上書き！ */
       grid-template-rows: 1fr 1fr;     /* ← 2行に上書き！ */
   }
   ```
   - このCSSが、JavaScriptで設定した3列×2行レイアウトを完全に無効化していた

2. **HTMLの構造問題**
   - 9個のグリッドアイテムが存在していたが、6画面表示用に最適化されていなかった

#### 9.9.3 最終的な解決策
1. **CSSの修正**
   ```css
   .cycle-expanded { 
       grid-template-columns: 1fr 1fr 1fr !important; /* 3列に修正！ */
       grid-template-rows: 1fr 1fr !important; /* 2行を維持 */
   }
   ```

2. **HTMLの最適化**
   - 6個のグリッドアイテムのみに削減
   - インラインスタイルで3列×2行レイアウトを強制

3. **非表示設定の修正**
   - 7番目以降のグリッドアイテムを非表示に変更

#### 9.9.4 教訓
- **コード全体を把握してから修正を開始する**
- **根本原因を特定せずに表面的な修正を繰り返さない**
- **ブラウザの開発者ツールでCSSの競合を確認する**
- **ユーザーの時間を無駄にしないよう、確実な解決策を提示する**

---

## 0. 5013/5508 の役割と標準運用（重要・固定方針）

- **5013（Flask本体）**: `cctv_streaming_fixed.py`。CCTV監視＋API（/api/...、/get_frame等）。これは唯一のサーバ本体。
- **5508（静的UI）**: `vercel_minimal/pq-form` のフロントUIのみ。`python -m http.server 5508` で提供。
- **Vercelは使用しない**: 本番/ローカルともに Flask のみで運用（UIはローカル静的配信）。

禁止・注意:
- ❌ ルート直下（`E:\factory_monitoring_system`）で `http.server` を起動しない（モニター等の別ファイルが見える/紛れる原因）。
- ❌ 5508にFlask本体を割り当てない。5013と5508は厳密に役割分離。
- ✅ 5508は必ず `E:\factory_monitoring_system\vercel_minimal\pq-form` で起動。

### 正しい停止・再起動手順（標準・唯一の手順）

1) 完全停止（ポート単位でPID終了）
```powershell
# 5013 (Flask) を停止
$pid5013 = (Get-NetTCPConnection -LocalPort 5013 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if($pid5013){ Stop-Process -Id $pid5013 -Force }

# 5508 (静的UI) を停止
$pid5508 = (Get-NetTCPConnection -LocalPort 5508 -State Listen -ErrorAction SilentlyContinue).OwningProcess; if($pid5508){ Stop-Process -Id $pid5508 -Force }
```

2) Flask本体（5013）起動（このワンライナーのみ使用）
```powershell
cd E:\factory_monitoring_system; $env:PQFORM_SHEET_ID="1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M"; $env:GOOGLE_SA_FILE="C:\Users\Satoshi\Downloads\cursor-434016-198bf8b96199.json"; $env:ENABLE_DEBUG_LOG="0"; python cctv_streaming_fixed.py
# ブラウザ: http://localhost:5013
```

3) pq-form UI（5508）起動（別ターミナル）
```powershell
cd E:\factory_monitoring_system\vercel_minimal\pq-form
python -m http.server 5508 --bind 127.0.0.1
# ブラウザ: http://127.0.0.1:5508
```

4) 確認
```powershell
netstat -ano | findstr :5013
netstat -ano | findstr :5508
```

補足:
- `vercel_minimal/pq-form/index.html` が欠損すると 5508 は 404 になる。必ず存在確認。
- 5508がモニター画面になる原因は「起動ディレクトリの誤り」。必ず `pq-form` 直下で起動すること。
- この節に記載の手順以外で再起動しないこと（他の再起動手順は使用禁止）。

### ワンコマンド起動（再発防止用）

- 前景でFlask（5013）＋ 背景でUI（5508）を正しく起動するスクリプト：
  ```powershell
  .\monitor_service.ps1            # 通常ログ
  .\monitor_service.ps1 -DebugLog  # デバッグログ有効
  ```
- Flaskのみ起動する簡易版：
  ```powershell
  .\start_service.ps1
  ```

これらはPIDで既存プロセスを安全に停止し、正しいディレクトリから確実に起動します。

---

## 11. Vercelデプロイ情報（正しい設定）

### 11.1 正しいプロジェクト情報
**以下の情報以外は一切存在しません（削除済み）**

#### 🔑 プロジェクト情報
- **プロジェクト名**: `khk-monitor`
- **プロジェクトID**: `prj_8tx0A5scrtndxx0Z2dBac5FLhTm5`
- **アカウント**: `kirii`
- **固定URL**: `https://khk-monitor.vercel.app`
- **Vercel URL**: `vercel.com/kirii/khk-monitor`

### 11.2 デプロイ方法（MDファイル記載の正しい手順）

#### ✅ 正しいVercelデプロイ手順（唯一の正解）

##### 🚀 自動化版（推奨）
```powershell
# PowerShellスクリプトで自動デプロイ
.\auto_deploy_vercel.ps1
```

##### 📋 手動版（初回のみ）
##### 手順1: 現在のプロジェクトを確認
```bash
vercel projects ls
```

##### 手順2: 正しいプロジェクトが表示されるまでアカウントを切り替え
```bash
vercel logout
vercel login
```

##### 手順3: 正しいプロジェクトが表示されたら、そのプロジェクトにリンク
```bash
vercel link
```

##### 手順4: デプロイ
```bash
vercel --prod
```

### 11.3 削除済みの間違った情報
**以下の情報は完全に削除済み（二度と出ない）**
- ~~プロジェクトID: `prj_LM8Qz5DLaRvwTrYUfWIu848YLc3j`~~
- ~~組織ID: `team_hfdVMgcn7GojZhG8Cz5Pb3iA`~~
- ~~プロジェクト名: `khk-monitor`~~

---

## 10. デバッグログ制御システム（環境変数による診断機能）

### 10.1 システム概要
`cctv_streaming_fixed.py`には**環境変数によるデバッグログ制御**機能が実装されている。この機能により、通常運用時はログを抑制し、トラブル時のみ詳細ログを表示可能。

### 10.2 技術仕様
```python
# cctv_streaming_fixed.py 26-30行目
if os.environ.get('ENABLE_DEBUG_LOG', '0') != '1':
    import builtins as _builtins
    def _noop_print(*args, **kwargs):
        return
    _builtins.print = _noop_print
```

**動作原理**:
- デフォルト: `ENABLE_DEBUG_LOG`環境変数未設定 → 全`print()`文を`_noop_print`で無効化
- デバッグ時: `ENABLE_DEBUG_LOG="1"`設定 → 通常の`print()`関数動作

### 10.3 有効化方法
```bash
# PowerShell
$env:ENABLE_DEBUG_LOG="1"; python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"

# CMD
set ENABLE_DEBUG_LOG=1 && python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"

# Linux/Mac
ENABLE_DEBUG_LOG=1 python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"
```

### 10.4 表示されるログ情報
- **接続状況**: `✅ メインストリーム接続成功` / `🔐 セッションを再生成しました`
- **フレーム処理**: `✅ CH1 並列取得成功` / `🔄 指定チャンネル毎秒更新取得開始`
- **エラー詳細**: `ReadTimeout` / `ConnectionError` の具体的内容
- **自動復旧**: `♻️ フレーム停止検知 → 再ログインして再起動します`

### 10.5 必須条件
**問題解決にはデバッグログ制御が必須**。ログなしでは以下が不可能:
- 接続エラーの原因特定
- フレーム取得状況の確認
- 自動復旧機能の動作確認
- CCTVサーバーとの通信状況監視

### 10.6 正しい起動ファイルの確認
**重要**: 必ず以下のファイルを起動すること
- **正しいファイル**: `cctv_streaming_fixed.py` ← **これが現在動いているファイル**
- **間違ったファイル**: `old_versions/`内のファイル（削除済み）
- **確認方法**: 起動時に以下のメッセージが表示されることを確認
  ```
  ✅ YOLO11モデル読み込み成功
  🏭 KIRII CCTV監視システム (最適化版)
  📺 CCTV: 192.168.0.98:18080 (ストリーミング対応)
  ```
- **起動コマンド**: 
  ```bash
  $env:ENABLE_DEBUG_LOG="1"; python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"
  ```

---

## 11. 緊急復旧記録（2025-08-22）

### 11.1 発生した問題
**症状**: 「開控」ボタンを押してもメインストリームが表示されない、接続が死んでいる状態

**根本原因の特定過程**:
1. **文字エンコーディング問題**: ファイルがUTF-8で保存されているのに、デフォルトの`cp950`で読み込まれていた
2. **持続ストリーム方式の過負荷**: 16チャンネル同時接続でCCTVサーバーがタイムアウト
3. **早期リターン問題**: `start_optimized_stream`関数で`is_streaming`フラグのみで判断し、実際のフレーム取得状況を無視
4. **stream_workerスレッド未起動**: 条件分岐により`stream_worker`スレッドが起動されない

### 11.2 解決手順（時系列）

#### ステップ1: デバッグログ有効化 + 文字エンコーディング修正
```bash
# 環境変数設定 + UTF-8明示指定
$env:ENABLE_DEBUG_LOG="1"; python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"
```

**重要**: この処理方法を「**環境変数によるデバッグログ制御**」と呼ぶ。

**仕組みの詳細**:
- `cctv_streaming_fixed.py`の26-30行目に以下のコードが存在:
  ```python
  if os.environ.get('ENABLE_DEBUG_LOG', '0') != '1':
      import builtins as _builtins
      def _noop_print(*args, **kwargs):
          return
      _builtins.print = _noop_print
  ```
- デフォルト状態では`ENABLE_DEBUG_LOG`環境変数が未設定のため、すべての`print()`文が無効化される
- `$env:ENABLE_DEBUG_LOG="1"`で環境変数を設定することで、`print()`文が有効になりリアルタイムログが表示される
- これにより接続状況、フレーム取得状況、エラー詳細をターミナルで確認可能

#### ステップ2: 同時接続数削減
```python
# working_channelsを16→1に変更
self.working_channels = [1]  # 負荷軽減のため1チャンネルのみ
```

#### ステップ3: 持続ストリーム方式→メインストリーム方式への切替
```python
# 持続ストリーム無効化
def start_optimized_stream(self):
    """最適化されたストリーム開始（メインストリーム方式）"""
    # self.start_persistent_streams()  # コメントアウト
```

#### ステップ4: 早期リターン問題修正
```python
# 修正前：is_streamingフラグのみで判断
if self.is_streaming:
    return True  # 問題：stream_workerが起動されない

# 修正後：実際のフレーム取得状況も考慮
if self.is_streaming and self.current_frame:
    return True  # フレームが実際に取得できている場合のみ早期リターン
```

### 11.3 技術的解決のポイント

1. **Markdownファイル記載の既知解決方法が有効**:
   - 9.6 ネットワーク/接続安定化: メインストリーム方式推奨
   - 9.7 既知のトラブルと回避: `ReadTimeout`は既知問題

2. **自動復旧機能の正常動作**:
   ```python
   # フレーム停止検知→自動復旧
   if self.last_frame_time and (time.time() - self.last_frame_time) > 5:
       print("♻️ フレーム停止検知 → 再ログインして再起動します")
       self.stop_stream()
       self.reset_session()
   ```

3. **メインストリーム方式の有効性確認**:
   - CCTVサーバー負荷軽減
   - 安定したフレーム取得（48KB程度のフレームサイズ）
   - 循環表示機能も正常動作

### 11.4 今後の予防策

1. **起動時チェック**:
   - **必須**: 環境変数によるデバッグログ制御を有効化 `ENABLE_DEBUG_LOG=1`
   - 文字エンコーディング: UTF-8明示指定
   - ログ確認: `✅ メインストリーム接続成功`メッセージ
   - **重要**: デバッグログなしでは問題の特定と解決が困難

2. **監視ポイント**:
   - フレーム取得成功: `get_frame success: True`
   - フレームサイズ: 40KB以上
   - エラーログ: `ReadTimeout`は既知問題として許容

3. **トラブルシューティング順序**:
   - 文字エンコーディング確認
   - 同時接続数確認（1チャンネルから開始）
   - メインストリーム方式使用確認
   - 自動復旧機能動作確認

---

## 12. 復元手順（緊急復旧対応版・最新手順）

### 12.1 基本復元手順
1. 依存関係をインストール：`pip install -r requirements.txt`
2. 画像ファイル `static/kirii_logo.png` を配置（既存を利用可）
3. **修正されたアプリ起動（必須条件）**：
   ```bash
   $env:ENABLE_DEBUG_LOG="1"; python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"
   ```
   - **必須**: `ENABLE_DEBUG_LOG="1"`による環境変数デバッグログ制御
   - **必須**: `encoding='utf-8'`による文字エンコーディング明示指定
   - **必須**: **正しいファイル名** `cctv_streaming_fixed.py` ← **これが現在動いているファイル**
   - **この方法でのみ問題解決が可能**
4. アクセス：`http://localhost:5013`

### 12.1.1 完璧な状態への復帰手順
**問題解決後、通常運用モードに戻す**：
```bash
# 1. 現在のプロセスを停止
Stop-Process -Name python -Force

# 2. 通常運用モードで起動（ログ出力なし、負荷軽減）
python cctv_streaming_fixed.py

# 3. 確認：ターミナルが静かになることを確認
# 4. 動作確認：ブラウザで http://localhost:5013 にアクセス
```

### 12.2 動作確認チェックリスト
- [ ] 起動ログに `✅ メインストリーム接続成功` が表示される
- [ ] 主面でライブ再生を確認（フレーム取得成功）
- [ ] API確認：`/get_frame` で `success: True` とフレームサイズ40KB以上
- [ ] 数字押下で単一切替（1.0秒更新で枠焼き込み表示）
- [ ] 「循面」で20秒間隔でグループ切替（A: 3,4,7,11 ⇔ B: 1,5,10,13）
- [ ] 「循拡」で1.5倍拡大表示（画像サイズ: 180px高さ、18pxフォント）
- [ ] 4/9/16で数字列が残ること

### 12.3 トラブル時の対処
**症状**: 「沒有影像」が表示される場合
1. **正しいファイル確認**: `cctv_streaming_fixed.py`が起動されていることを確認
2. 文字エンコーディング確認：UTF-8明示指定で起動
3. ログ確認：`ReadTimeout`は既知問題として許容
4. フレーム取得確認：`python -c "import requests; print(requests.get('http://localhost:5013/get_frame').json())"`
5. 自動復旧待機：5秒後に自動的にセッション再生成される

**重要**: 間違ったファイル（old_versions内）を起動すると、問題の特定と解決が困難になる

### 12.3.1 問題解決後の完璧な状態への復帰
**トラブル解決後は必ず通常運用モードに戻す**：
```bash
# 1. デバッグモードのプロセスを停止
Stop-Process -Name python -Force

# 2. 通常運用モードで起動
python cctv_streaming_fixed.py

# 3. 完璧な状態の確認
# - ターミナルが静か（ログ出力なし）
# - プロセスが正常起動
# - ブラウザで動作確認
```

---

## 13. 完璧な状態の記録（2025-08-22 13:44:13）

### 13.1 完璧な状態の定義
**状態**: 通常運用モード（ログ出力なし）で安定動作
- **プロセスID**: 5756
- **起動時刻**: 2025-08-22 13:44:13
- **起動方法**: `python cctv_streaming_fixed.py`（環境変数なし）
- **ログレベル**: 最小限（通常運用モード）
- **動作確認**: メインストリーム正常、循環表示正常、負荷軽減済み

### 13.2 この状態に戻す方法

#### 方法1: 通常運用モード（推奨）
```bash
# 現在のプロセスを停止
Stop-Process -Name python -Force

# 通常モードで起動（ログ出力なし、負荷軽減）
python cctv_streaming_fixed.py
```

#### 方法2: デバッグモード（トラブル時のみ）
```bash
# 現在のプロセスを停止
Stop-Process -Name python -Force

# デバッグモードで起動（ログ出力あり、問題特定用）
$env:ENABLE_DEBUG_LOG="1"; python -c "exec(open('cctv_streaming_fixed.py', encoding='utf-8').read())"
```

### 13.3 状態確認方法
```bash
# プロセス確認
Get-Process python -ErrorAction SilentlyContinue

# 正常動作確認
curl http://localhost:5013/get_frame
```

### 13.4 完璧な状態の特徴
- ✅ ログ出力が最小限（ターミナルが静か）
- ✅ メインストリームが正常動作
- ✅ 循環表示が20秒間隔で正常切替
- ✅ CCTVサーバーへの負荷が軽減済み
- ✅ 自動復旧機能が有効
- ✅ フレーム取得が安定（48KB程度）

### 13.5 この状態を維持するための注意点
1. **通常運用時**: `python cctv_streaming_fixed.py`を使用
2. **トラブル時のみ**: `ENABLE_DEBUG_LOG="1"`を使用
3. **ファイル名**: 必ず`cctv_streaming_fixed.py`を使用
4. **起動後**: ターミナルが静かになることを確認
5. **動作確認**: ブラウザで`http://localhost:5013`にアクセス

---

## 14. 「循拡」モードUIレイアウト改善完了（2025-08-22）

### 14.1 改善内容
**「循拡」モードの完全な全画面表示実装**
- **ヘッダー非表示**: 上部ヘッダーを完全に隠し、画面全体を4チャンネル表示に専用
- **4チャンネル全画面表示**: 4つのグリッドアイテムが画面全体を埋めるように配置
- **ボタン下部固定**: コントロールボタンを画面下部に固定配置
- **強制レイアウト制御**: CSSとJavaScriptの両方で確実な表示制御

### 14.2 実装された技術的改善

#### CSS強化
```css
.cycle-expanded {
    height: 100vh; /* 画面全体の高さを使用 */
    margin: 0;
    padding: 0;
    gap: 4px; /* グリッド間の隙間 */
}

.cycle-expanded .grid-item {
    min-height: 50vh; /* 画面高さの50% */
    display: flex !important; /* 強制表示 */
    align-items: center;
    justify-content: center;
    background: #000; /* 背景色 */
    border-radius: 8px;
    overflow: hidden;
}

/* 非表示にするグリッドアイテム */
.cycle-expanded .grid-item:nth-child(n+5) {
    display: none !important;
}

/* 循拡モード時のヘッダー非表示・ボタン下部固定 */
.cycle-expanded-mode .header {
    display: none !important;
}

.cycle-expanded-mode .controls {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-top: 2px solid #17a2b8;
    z-index: 1000;
    padding: 10px;
    margin: 0;
}
```

#### JavaScript強化
```javascript
// 4つのグリッドアイテムのみ表示（強制制御）
const gridItems = document.querySelectorAll('.grid-item');
gridItems.forEach((item, index) => {
    if (index < 4) {
        item.style.display = 'flex';
        item.style.visibility = 'visible';
        item.style.opacity = '1';
    } else {
        item.style.display = 'none';
        item.style.visibility = 'hidden';
        item.style.opacity = '0';
    }
});

// グリッドコンテナのスタイルを強制設定
gridView.style.gridTemplateColumns = '1fr 1fr';
gridView.style.gridTemplateRows = '1fr 1fr';
gridView.style.height = '100vh';
gridView.style.margin = '0';
gridView.style.padding = '0';

// ヘッダー非表示・ボタン下部固定のためのbodyクラス追加
document.body.classList.add('cycle-expanded-mode');
```

### 14.3 動作確認結果
**完璧な状態達成** ✅
- **上半分**: ヘッダーが完全に非表示、4チャンネルが画面全体を埋める
- **下半分**: コントロールボタンが画面下部に固定配置
- **表示制御**: 4つのグリッドアイテムのみ表示、他は完全非表示
- **レイアウト**: 画面全体を活用した1.5倍拡大表示が正常動作

### 14.4 技術的ポイント
1. **CSS `!important`**: 他のスタイルを上書きする強制適用
2. **JavaScript直接スタイル設定**: DOM要素への直接的なスタイル適用
3. **bodyクラス制御**: 全体的なレイアウトモードの切り替え
4. **可視性制御**: `display`、`visibility`、`opacity`の3段階制御
5. **レスポンシブ対応**: `100vh`と`50vh`による画面サイズ依存の高さ設定

### 14.5 今後の拡張性
- **「循拡」モード**: 完全実装済み、追加改善不要
- **他の表示モード**: 同様の手法で全画面表示化が可能
- **モバイル対応**: 既存のメディアクエリで対応済み
- **パフォーマンス**: 最小限のDOM操作で高速動作

### 14.6 完了確認
**日時**: 2025-08-22  
**状態**: 完璧 ✅  
**ユーザー評価**: 「完璧」  
**技術的課題**: 全て解決済み  
**追加作業**: 不要（完全実装完了）



