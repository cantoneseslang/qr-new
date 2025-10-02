#!/usr/bin/env python3
"""
KIRII在庫管理Vercelプラットフォーム
QRコードからアクセスする携帯対応在庫確認システム
Googleシート連携対応
"""

from flask import Flask, render_template_string, jsonify, request, redirect, abort
from urllib.parse import unquote, urlparse
import json
from datetime import datetime
import os
import requests

app = Flask(__name__)

class KiriiInventoryPlatform:
    def __init__(self):
        # Googleシート設定
        self.sheet_url = os.getenv('GOOGLE_SHEET_URL', 'https://docs.google.com/spreadsheets/d/1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M/edit?usp=sharing')
        
        # HTMLエンティティデコード用のライブラリをインポート
        import html
        import re
        self.html = html
        self.re = re
        self.use_google_sheets = bool(self.sheet_url)
        
        
        # Googleシート接続を初期化
        self.sheet_client = None
        self.worksheet = None
        self._init_google_sheets()
        
        print("🏭 KIRII番号ベース在庫管理プラットフォーム初期化完了")
        print("📱 携帯対応在庫確認システム")
        print("🔢 QRコード: 番号ベース（超大型マス対応）")
        if self.use_google_sheets:
            print("📊 Googleシート連携: 有効")
        else:
            print("📊 データソース: ローカル（フォールバック）")

    def _decode_html_entities(self, text):
        """HTMLエンティティをデコードする包括的なメソッド"""
        if not text:
            return ''
        
        # 方法1: 正規表現で数値エンティティを直接置換（最確実）
        decoded = self.re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
        decoded = self.re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), decoded)
        
        # 方法2: 手動置換（残りのエンティティ）
        decoded = decoded.replace('&quot;', '"').replace('&apos;', "'")
        decoded = decoded.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        decoded = decoded.replace('&nbsp;', ' ')
        
        # 方法3: html.unescape（バックアップ）
        decoded = self.html.unescape(decoded)
        
        # 方法4: 連続するダブルクォートを1つに統一（"" → "）
        decoded = self.re.sub(r'""+', '"', decoded)
        
        # 方法5: 先頭と末尾の不要なダブルクォートを除去
        decoded = decoded.strip('"')
        
        # 方法6: 連続する空白を1つに統一
        decoded = self.re.sub(r'\s+', ' ', decoded).strip()
        
        return decoded

    def _init_google_sheets(self):
        """Googleシート接続を初期化"""
        try:
            print(f"🔍 デバッグ: シートURL = {self.sheet_url}")
            # シートIDを抽出
            self.sheet_id = self._extract_sheet_id_from_url(self.sheet_url)
            print(f"🔍 デバッグ: シートID = {self.sheet_id}")
            if not self.sheet_id:
                print("⚠️ 無効なシートURL")
                self.use_google_sheets = False
                return
                
            # サービスアカウント認証（環境変数からJSONキーを取得）
            self.sheets_service = None
            self.api_key = None
            
            # 環境変数からサービスアカウントJSONを取得
            service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
            print(f"🔍 デバッグ: サービスアカウントJSON設定済み = {bool(service_account_json)}")
            if service_account_json:
                try:
                    # 依存が無い環境でも動作するよう遅延インポート
                    from google.oauth2 import service_account  # type: ignore
                    from googleapiclient.discovery import build  # type: ignore
                    import json

                    # JSON文字列をパース
                    service_account_info = json.loads(service_account_json)
                    
                    credentials = service_account.Credentials.from_service_account_info(
                        service_account_info,
                        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                    )
                    self.sheets_service = build('sheets', 'v4', credentials=credentials)
                    print("✅ サービスアカウント認証成功")
                except Exception as e:
                    print(f"⚠️ サービスアカウント認証失敗: {e}")
                    print("📋 API Key方式にフォールバック")
                    self.api_key = "AIzaSyARbSHGDK-dCkmuP8ys7E2-G-treb3ZYIw"
            else:
                print("⚠️ サービスアカウントJSONが設定されていません")
                print("📋 API Key方式を使用します")
                self.api_key = "AIzaSyARbSHGDK-dCkmuP8ys7E2-G-treb3ZYIw"
            
            # Google Sheets API接続テスト
            if self.sheets_service:
                # サービスアカウント認証での接続テスト
                try:
                    print(f"🔍 デバッグ: サービスアカウント認証で接続テスト開始")
                    result = self.sheets_service.spreadsheets().values().get(
                        spreadsheetId=self.sheet_id,
                        range='Stock!A1:Y1'
                    ).execute()
                    print(f"✅ Googleシート接続成功 (サービスアカウント認証) (ID: {self.sheet_id[:8]}...)")
                    print(f"🔍 デバッグ: 取得データ = {result}")
                    self.use_google_sheets = True
                except Exception as e:
                    print(f"❌ Googleシート接続失敗 (サービスアカウント): {e}")
                    print(f"🔍 デバッグ: エラー詳細 = {type(e).__name__}: {str(e)}")
                    print("📋 フォールバックモードで動作")
                    self.use_google_sheets = False
            elif self.api_key:
                # API Key認証での接続テスト
                test_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Stock!A1:Y1?key={self.api_key}"
                test_response = requests.get(test_url, timeout=10)
                
                if test_response.status_code == 200:
                    print(f"✅ Googleシート接続成功 (API Key認証) (ID: {self.sheet_id[:8]}...)")
                    self.use_google_sheets = True
                else:
                    print(f"❌ Googleシート接続失敗: {test_response.status_code}")
                    print("📋 フォールバックモードで動作")
                    self.use_google_sheets = False
            else:
                print("❌ 認証方法が設定されていません")
                self.use_google_sheets = False
                
        except Exception as e:
            print(f"❌ Googleシート初期化エラー: {e}")
            print("📋 フォールバックモードで動作")
            self.use_google_sheets = False
    
    def _extract_sheet_id_from_url(self, url):
        """GoogleシートのURLからシートIDを抽出"""
        try:
            if '/spreadsheets/d/' in url:
                return url.split('/spreadsheets/d/')[1].split('/')[0]
        except:
            pass
        return None

    def get_inventory_data(self):
        """在庫データを取得（Googleシートまたはローカル）"""
        if self.use_google_sheets and (hasattr(self, 'sheets_service') or hasattr(self, 'api_key')):
            try:
                return self._fetch_from_google_sheets()
            except Exception as e:
                print(f"⚠️ Googleシートからのデータ取得エラー: {e}")
                print("📋 フォールバックデータを使用します")
                
        return self.fallback_inventory

    def _fetch_from_google_sheets(self):
        """Googleシートからデータを取得（サービスアカウント認証またはAPI Key方式）"""
        import requests
        import time
        
        try:
            if self.sheets_service:
                # サービスアカウント認証でのデータ取得
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.sheet_id,
                        range='Stock!A1:Y1500'
                ).execute()
                values = result.get('values', [])
            else:
                # API Key認証でのデータ取得
                api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Stock!A1:Y1500?key={self.api_key}"
                
                # Google Sheets APIからデータを取得（キャッシュ無効化ヘッダー付き）
                headers = {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
                response = requests.get(api_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                values = data.get('values', [])
            
            if not values:
                print("⚠️ Googleシートにデータがありません")
                return self.fallback_inventory
            
            # ヘッダー行を取得
            headers = values[0] if values else []
            
            # データを辞書形式に変換（C列: ProductCode が存在する行を採用）
            rows = values[1:]  # ヘッダー行をスキップ
            # まず既存の数値A列の最大値を取得
            max_number = 0
            for r in rows:
                if len(r) > 0:
                    a_val = str(r[0]).strip() if r[0:] else ''
                    if a_val.isdigit():
                        try:
                            max_number = max(max_number, int(a_val))
                        except Exception:
                            pass

            next_auto_number = max_number + 1
            inventory_data = {}
            for row in rows:
                try:
                    # 採用条件: C列にProductCodeがある
                    if len(row) <= 2:
                        continue
                    code_cell = str(row[2]).strip()
                    if code_cell == '':
                        continue

                    # 番号（A列）。非数値・空なら自動採番
                    number_val = str(row[0]).strip() if len(row) > 0 else ''
                    if number_val.isdigit():
                        number = int(number_val)
                    else:
                        number = next_auto_number
                        next_auto_number += 1

                    # D列: 製品名（品名をD列参照に統一、HTMLエンティティをデコード）
                    raw_name = row[3] if len(row) > 3 else ''
                    name = self._decode_html_entities(raw_name)
                    
                    # デバッグ用：HTMLエンティティが含まれる製品名を確認
                    if raw_name and ('&#34;' in str(raw_name) or '&#39;' in str(raw_name) or 'Marco' in str(raw_name) or 'Themawool' in str(raw_name)):
                        print(f"🔍 DEBUG HTML: raw='{raw_name}', decoded='{name}'")

                    # T列: 保管場所 正規化（空/"0"→"0"）
                    raw_loc = row[19] if len(row) > 19 else ''
                    loc_str = str(raw_loc).strip()
                    normalized_loc = '0' if (loc_str == '' or loc_str == '0') else loc_str

                    # U列: On Hand（参考値）
                    raw_on_hand = row[20] if len(row) > 20 else ''
                    on_hand_str = str(raw_on_hand).replace(',', '').strip()
                    on_hand = int(on_hand_str) if (on_hand_str and on_hand_str.lstrip('-').isdigit()) else None

                    # V列: w/o DN（出荷未処理）
                    raw_wo = row[21] if len(row) > 21 else ''
                    wo_str = str(raw_wo).replace(',', '').strip()
                    without_dn = int(wo_str) if (wo_str and wo_str.lstrip('-').isdigit()) else None

                    # W列: Available（在庫数量）カンマ付き・負数対応
                    raw_qty = row[22] if len(row) > 22 else '0'
                    qty_str = str(raw_qty).replace(',', '').strip()
                    quantity = int(qty_str) if (qty_str and qty_str.lstrip('-').isdigit()) else 0

                    # X列: Unit
                    unit_val = row[23] if len(row) > 23 else ''

                    # Y列: LastTime
                    updated_val = row[24] if len(row) > 24 else datetime.now().strftime('%Y-%m-%d')

                    # E列: Category
                    category_val = row[4] if len(row) > 4 else ''

                    inventory_data[number] = {
                        'code': code_cell,
                        'name': name,
                        'location': normalized_loc,
                        'quantity': quantity,
                        'on_hand': on_hand,
                        'without_dn': without_dn,
                        'unit': unit_val,
                        'updated': updated_val,
                        'category': category_val,
                        'category_detail': row[3] if len(row) > 3 else ''
                    }
                except (ValueError, IndexError) as e:
                    print(f"⚠️ 行データ処理エラー: {e}")
                    continue
            
            if inventory_data:
                print(f"✅ Googleシートから{len(inventory_data)}件のデータを取得")
                return inventory_data
            else:
                print("⚠️ 有効なデータが見つかりませんでした")
                return self.fallback_inventory
                
        except requests.RequestException as e:
            print(f"❌ Googleシート API リクエストエラー: {e}")
            if hasattr(self, 'api_key') and self.api_key:
                api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Stock!A1:Y1500?key={self.api_key}"
                print(f"📋 API URL: {api_url}")
            print(f"📋 レスポンスコード: {getattr(e.response, 'status_code', 'N/A')}")
            print(f"📋 レスポンス内容: {getattr(e.response, 'text', 'N/A')}")
            return self.fallback_inventory
        except Exception as e:
            print(f"❌ データ処理エラー: {e}")
            print(f"📋 エラータイプ: {type(e).__name__}")
            return self.fallback_inventory

    @property
    def inventory_mapping(self):
        """在庫データのプロパティ"""
        return self.get_inventory_data()

    @property 
    def code_to_number(self):
        """製品コードから番号への逆引き"""
        inventory = self.get_inventory_data()
        return {v["code"]: k for k, v in inventory.items()}

    @property
    def fallback_inventory(self):
        """フォールバック用の在庫データ（Googleシート接続失敗時）"""
        # Googleシート接続失敗時は空の辞書を返す（エラー表示のため）
        return {}

platform = KiriiInventoryPlatform()

# ロゴとファビコンの例外処理のみ有効（認証チェック無効化）
@app.before_request
def handle_static_files():
    # ロゴとファビコンは許可
    if request.path.startswith('/static/logo.png') or request.path == '/favicon.ico':
        return
    
    # 認証チェックは無効化（誰でもアクセス可能）
    return

@app.errorhandler(401)
def handle_unauthorized(_e):
    # APIはJSONで返す
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'access_restricted',
            'message': 'Access restricted to KIRII(HK) employees only.'
        }), 401
    # HTMLは統一メッセージ（中央寄せ・青ボタン）
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Access Restricted</title>
  <style>
    html, body { height:100%; }
    body { margin:0; background:#ffffff; color:#111827; display:flex; align-items:center; justify-content:center; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Apple Color Emoji', 'Segoe UI Emoji'; }
    .wrap { text-align:center; max-width:720px; padding:24px; }
    h1 { font-size:28px; font-weight:700; margin:0 0 16px; }
    p { margin:6px 0; color:#4b5563; }
    .btn { display:inline-block; margin-top:18px; padding:10px 16px; background:#2563eb; color:#fff; border-radius:8px; text-decoration:none; box-shadow:0 1px 2px rgba(0,0,0,.06); }
    .btn:hover { background:#1d4ed8; }
  </style>
  </head>
  <body>
    <div class="wrap">
      <h1>存取受限制 Access Restricted</h1>
      <p>此頁面僅供 KIRII(HK) 員工使用，非員工恕不提供服務。</p>
      <p>This page is for KIRII(HK) employees only. Access is not available to non-employees.</p>
      <a class="btn" href="#">返回公司入口 · Back to company portal</a>
    </div>
  </body>
</html>
    '''), 401

@app.route('/')
def index():
    """メインページ - QRスキャン機能付き"""
    # Googleシートから最新の在庫データを取得
    inventory_data = platform.get_inventory_data()
    
    # Googleシート接続が失敗している場合はエラーメッセージを表示
    if not inventory_data and not platform.use_google_sheets:
        return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>STOCK-AI-SCAN - 接続エラー</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            min-height: 100vh;
            color: #333;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .error-container {
            max-width: 600px;
            text-align: center;
            padding: 40px;
            border: 2px solid #dc3545;
            border-radius: 15px;
            background: #f8f9fa;
        }
        
        .error-icon {
            font-size: 4em;
            color: #dc3545;
            margin-bottom: 20px;
        }
        
        .error-title {
            font-size: 1.8em;
            font-weight: bold;
            color: #dc3545;
            margin-bottom: 20px;
        }
        
        .error-message {
            font-size: 1.1em;
            color: #666;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        
        .retry-button {
            background: #007bff;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .retry-button:hover {
            background: #0056b3;
            transform: translateY(-2px);
        }
        
        .footer {
            margin-top: 30px;
            color: #6c757d;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-icon">⚠️</div>
        <div class="error-title">Googleシート接続エラー</div>
        <div class="error-message">
            Googleスプレッドシートに接続できませんでした。<br>
            システム管理者にお問い合わせください。
        </div>
        <button class="retry-button" onclick="window.location.reload()">
            🔄 再試行
        </button>
        <div class="footer">
            STOCK-AI-SCAN / 庫存及AIQR掃描儀<br>
            Copyright © Kirii (Hong Kong) Limited. All Rights Reserved.
        </div>
    </div>
</body>
</html>
        ''')
    # クエリによるフィルタリング
    query = request.args.get('q', '').strip()
    cat = request.args.get('cat', '').strip()
    if query:
        import unicodedata
        from urllib.parse import unquote
        def normalize(s: str) -> str:
            if s is None:
                return ''
            s = unicodedata.normalize('NFKC', str(s))
            return ' '.join(s.lower().split())
        needle = normalize(unquote(query))
        filtered = {}
        for num, item in inventory_data.items():
            name = item.get('name', '')
            code = item.get('code', '')
            if needle in normalize(name) or needle in normalize(code):
                filtered[num] = item
        inventory_data = filtered

    # カテゴリ（詳細分類: D列）フィルタ（表記ゆれを吸収して厳密化）
    import re, unicodedata
    def _canon_cat(label: str) -> str:
        if not label:
            return ''
        s = unicodedata.normalize('NFKC', str(label)).lower()
        s = s.replace('—', '-').replace('–', '-').replace('‐', '-')
        s = re.sub(r'\s+', '', s)
        
        # mm Runner/Stud を統一（例: "50mm - S", "50mmS", "50mm Runner" など）
        m = re.search(r'(\d+)mm[- ]?(runner|stud|[rs])', s)
        if m:
            kind = m.group(2).lower()
            suffix = 'runner' if kind in ('runner', 'r') else 'stud'
            return f"{m.group(1)}mm-{suffix}"
        # 2-1/2"-R/S を統一
        m = re.search(r'2[- ]?1\/2\"?[- ]?(runner|stud|[rs])', s)
        if m:
            kind = m.group(1).lower()
            suffix = 'runner' if kind in ('runner', 'r') else 'stud'
            return f"2-1/2\"-{suffix}"
        # HD/SD 系
        m = re.search(r'^(hd|sd)[- ]?(\d+)$', s)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        
        # 指定されたカテゴリのマッピング
        category_mapping = {
            'accessories': 'accessories',
            'boardfibrecement': 'board-fibrecement',
            'boardgwb': 'board-gwb',
            'boardmacau': 'board-macau',
            'ceilingsystemhd25': 'ceilingsystemhd-25',
            'ceilingsystemsd19': 'ceilingsystemsd-19',
            'metalangle': 'metalangle',
            'screw': 'screw',
            'teebarmk15': 'teebarmk-15',
            'teebarmk24': 'teebarmk-24',
            'teebarnewcolour1': 'teebarnewcolour1',
            'uchannel': 'uchannel',
            'venetianastmg90': 'venetianastm-g90',
            'z-mk': 'z-mk',
            'accesspanel': 'accesspanel'
        }
        
        # より詳細なマッピング（括弧や特殊文字を含む）
        detailed_mapping = {
            'boardgwb(gyproc)': 'board-gwb',
            'boardfibrecement': 'board-fibrecement',
            'boardmacau': 'board-macau',
            'ceilingsystemhd-25': 'ceilingsystemhd-25',
            'ceilingsystemsd-19': 'ceilingsystemsd-19',
            'metalangle': 'metalangle',
            'screw': 'screw',
            'teebar(mk-15)': 'teebarmk-15',
            'teebar(mk-24)': 'teebarmk-24',
            'teebar(newcolour)1': 'teebarnewcolour1',
            'uchannel': 'uchannel',
            'venetian(astm-g90)': 'venetianastm-g90',
            'z-mk': 'z-mk',
            'accesspanel': 'accesspanel'
        }
        
        # 既知カテゴリのマッピング
        s2 = re.sub(r'[^a-z0-9]+', '', s)
        
        # 詳細マッピングを先にチェック
        for key, value in detailed_mapping.items():
            if key in s2:
                return value
        for key, value in category_mapping.items():
            if key in s2:
                return value
        
        return s2

    # BDシリーズとFCシリーズの製品コードリスト
    bd_series_codes = [
        'BD-011', 'BD-024', 'BD-030', 'BD-043', 'BD-045-MN', 'BD-048-MN', 'BD-049', 
        'BD-050-MN', 'BD-051', 'BD-052', 'BD-053', 'BD-054', 'BD-055-M', 'BD-056-M', 
        'BD-057', 'BD-059', 'BD-060', 'BD-061', 'BD-062', 'BD-063', 'BD-064', 'BD-065', 'BD-067',
        'FC-003', 'FC-006', 'FC-007', 'FC-008', 'FC-014', 'FC-015', 'FC-036', 'FC-041', 
        'FC-043', 'FC-044', 'FC-046', 'FC-049', 'FC-052', 'FC-053', 'FC-055', 'FC-056', 'FC-057', 'FC-059'
    ]
    
    # ACシリーズの製品コードリスト
    ac_series_codes = [
        'AC-260', 'AC-261', 'AC-262', 'AC-269', 'AC-270'
    ]

    # cat変数をデコードして統一
    from urllib.parse import unquote
    cat_decoded = unquote(cat) if cat else ''
    print(f"🔍 DEBUG: cat='{cat}', cat_decoded='{cat_decoded}'")  # デバッグ用
    
    if cat_decoded:
        # AllBoardフィルターの特別処理
        if cat_decoded == 'AllBoard':
            inventory_data = {
                num: item for num, item in inventory_data.items()
                if item.get('code', '') in bd_series_codes
            }
        # Allwoolフィルターの特別処理
        elif cat_decoded == 'Allwool':
            inventory_data = {
                num: item for num, item in inventory_data.items()
                if item.get('code', '') in ac_series_codes
            }
        else:
            # E列のカテゴリと直接比較
            inventory_data = {
                num: item for num, item in inventory_data.items()
                if item.get('category', '') == cat_decoded
            }
    
    # カテゴリ一覧（件数順）
    from collections import Counter
    def normalize_label(label: str) -> str:
        if not label:
            return '—'
        import re
        lbl = str(label).strip()
        # 余分な空白を1つに
        lbl = re.sub(r'\s+', ' ', lbl)

        # 1) mm系 Runner/Stud → 100mm-R / 100mm-S
        m = re.search(r'(\d+)\s*mm\s*[- ]?\s*(runner|stud|r|s)', lbl, re.IGNORECASE)
        if m:
            kind = m.group(2).lower()
            suffix = 'R' if kind in ('runner', 'r') else 'S'
            return f"{m.group(1)}mm-{suffix}"

        # 2) 2-1/2" Runner/Stud → 2-1/2"-R / 2-1/2"-S
        m = re.search(r'2\s*-\s*1/2\"?\s*[- ]?\s*(runner|stud|r|s)', lbl, re.IGNORECASE)
        if m:
            kind = m.group(1).lower()
            suffix = 'R' if kind in ('runner', 'r') else 'S'
            return '2-1/2"-' + suffix

        # 3) HD/SD 系 → HD-25 / SD-19 など
        m = re.search(r'\b(hd|sd)\s*-?\s*(\d+)\b', lbl, re.IGNORECASE)
        if m:
            return f"{m.group(1).upper()}-{m.group(2)}"

        # 4) 既知カテゴリの短縮（順序重要）
        rules = [
            (r'Board[^\w]*GWB[^\w]*\(\s*GypRoc\s*\)', 'Bd-GR'),
            (r'Board[^\w]*Fibre\s*Cement', 'Bd-FC'),
            (r'Board[^\w]*Macau', 'Bd-MC'),
            (r'Metal\s*Angle', 'M-Angle'),
            (r'Vent[ei]lation[^\w]*\(\s*ASTM\s*-?\s*G90\s*\)', 'ASTM-G90'),
            (r'Accessories?', 'Access'),
            (r'Screw', 'SCREW'),
            (r'Tee-?\s*Bar[^\w]*MK\s*-?\s*15', 'T-BarMK-15'),
            (r'Tee-?\s*Bar[^\w]*MK\s*-?\s*24', 'T-BarMK-24'),
            (r'Tee-?\s*Bar[^\w]*(New\s*Colour|NC)', 'T-BarNC'),
            (r'U-?\s*Channel', 'U-CH'),
            (r'Z\s*-?\s*MK', 'Z-MK'),
        ]
        for pat, rep in rules:
            if re.search(pat, lbl, re.IGNORECASE):
                return rep

        # 最後にRunner/Stud単語だけの置換（フォールバック）
        lbl2 = lbl.replace('Runner', '-R').replace('Stud', '-S')
        return lbl2

    # E列のカテゴリをそのまま使用（変換不要）
    raw_categories = [v.get('category', '') for v in platform.get_inventory_data().values()]
    print(f"🔍 E列のカテゴリデータ: {raw_categories[:10]}...")  # デバッグ用
    
    # 空でないカテゴリのみを集計（KSSを除外）
    valid_categories = [c for c in raw_categories if c.strip() and c != 'KSS']
    canon_counts = Counter(valid_categories)
    print(f"🔍 カテゴリ集計: {dict(canon_counts)}")  # デバッグ用
    
    # AllBoardカテゴリの件数を計算
    all_inventory = platform.get_inventory_data()
    bd_count = sum(1 for item in all_inventory.values() if item.get('code', '') in bd_series_codes)
    if bd_count > 0:
        canon_counts['AllBoard'] = bd_count
    
    # Allwoolカテゴリの件数を計算
    ac_count = sum(1 for item in all_inventory.values() if item.get('code', '') in ac_series_codes)
    if ac_count > 0:
        canon_counts['Allwool'] = ac_count
    
    # E列の値をそのまま使用するため、変換マッピングは不要

    # E列の実際の値に基づく順序（ユーザー指定の順序）
    predefined_order = [
        'AllBoard', 'Allwool', '50mm Runner', '50mm Stud', '2-1/2" Runner', '51mm Runner',
        '51mm Stud', '64mm Runner', '64mm Stud', '75mm Runner', '75mm Stud', '76mm Runner',
        '76mm Stud', '86mm Runner', '86mm Stud', '92mm Runner', '92mm Stud',
        '100mm Runner', '100mm Stud', '102mm Runner', '102mm Stud', '125mm Runner', '125mm Stud',
        '127mm Runner', '127mm Stud', '150mm Runner', '150mm Stud', '152mm Runner', '152mm Stud',
        'Accessories', 'Board- Fibre Cement', 'Board- GWB (GypRoc)', 'Board- Macau',
        'Ceiling System HD-25', 'Ceiling System SD-19', 'Metal Angle', 'SCREW', 'Tee-Bar (MK -15)',
        'Tee-Bar (MK -24)', 'Tee-Bar(New Colour)1', 'U-Channel', 'Venetian (ASTM-G90)', 'Z-MK', 'Access Panel'
    ]
    
    # 既存のカテゴリを指定順に並べる
    ordered_categories = []
    for cat in predefined_order:
        if cat in canon_counts:
            ordered_categories.append(cat)
    
    # 指定順にないカテゴリを最後に追加
    for cat in canon_counts.keys():
        if cat not in ordered_categories:
            ordered_categories.append(cat)
    
    print(f"🔍 順序付けられたカテゴリ: {ordered_categories}")  # デバッグ用
    
    top_categories_canon = ordered_categories[:10]
    ordered_cnt = [(c, canon_counts[c]) for c in ordered_categories]
    
    print(f"🔍 表示用カテゴリ（最初の10個）: {top_categories_canon}")  # デバッグ用

    return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta http-equiv="Permissions-Policy" content="camera=*">
    <title>STOCK-AI-SCAN</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            min-height: 100vh;
            color: #333;
            padding: 20px;
        }
        
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .logo {
            height: 27px;
            width: auto;
            margin-right: 15px;
        }
        
        .header-title {
            font-size: 1.4em;
            font-weight: bold;
            color: #333;
        }
        

        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .qr-scanner {
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .scan-button {
            background: #28a745;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        
        .scan-button:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        
        .manual-input {
            margin-top: 15px;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
        }
        
        .code-input {
            flex: 1;
            padding: 12px;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            font-size: 1em;
            background: white;
            color: #333;
        }
        
        .code-input:focus {
            border-color: #007bff;
            outline: none;
        }
        
        .search-button {
            background: #007bff;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 10px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .search-button:hover {
            background: #0056b3;
            transform: translateY(-2px);
        }
        
        .camera-notice {
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 15px;
            padding: 10px;
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
        }
        
        .inventory-list {
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 15px;
            padding: 25px;
        }
        
        .list-title {
            color: #333;
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .list-title-text {
            flex: 1;
            text-align: center;
        }
        
        /* モバイル表示用 */
        @media (max-width: 768px) {
            .list-title {
                flex-direction: column;
                gap: 10px;
            }
            
            .list-title-text {
                flex: none;
                text-align: center;
            }
        }
        
        .download-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.8em;
            cursor: pointer;
            transition: background 0.2s;
        }
        
        .download-btn:hover {
            background: #218838;
        }
        /* フィルタチップ */
        .chip-bar { display: flex; gap: 8px; overflow-x: auto; padding: 8px 2px; margin: 8px 0 14px; }
        .chip { white-space: nowrap; padding: 6px 10px; border: 1px solid #dee2e6; border-radius: 999px; font-size: 12px; color:#333; background:#fff; }
        .chip.active { background:#007bff; color:#fff; border-color:#007bff; }
        .chip-count { font-size: 10px; opacity:.7; margin-left:4px; }
        .more-btn { padding:6px 10px; border:1px solid #dee2e6; border-radius:999px; background:#f8f9fa; font-size:12px; }
        /* ボトムシート */
        .sheet { position: fixed; left:0; right:0; bottom:-100%; background:#fff; border-top-left-radius:12px; border-top-right-radius:12px; box-shadow:0 -4px 16px rgba(0,0,0,.2); transition: bottom .25s; padding:12px; }
        .sheet.open { bottom:0; }
        .grid { display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; max-height: 50vh; overflow:auto; }
        .grid button { padding:8px; font-size:12px; border:1px solid #dee2e6; border-radius:8px; background:#fff; }
        
        .product-card {
            background: white;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .product-card:hover {
            transform: translateY(-2px);
            border-color: #007bff;
            box-shadow: 0 5px 15px rgba(0,123,255,0.2);
        }
        
        .product-code {
            color: #28a745;
            font-weight: bold;
            font-size: 0.95em;
            margin-bottom: 8px;
        }
        
        .product-name {
            color: #333;
            font-size: 0.95em;
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .product-details {
            color: #6c757d;
            font-size: 0.95em;
        }
        
        .footer {
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
        }
        
        #qr-reader {
            width: 100%;
            max-width: 400px;
            margin: 0 auto;
            display: none;
        }
        
        .qr-active #qr-reader {
            display: block;
        }
        
        .qr-active .scan-button {
            background: #dc3545;
        }
        
        .qr-active .scan-button:hover {
            background: #c82333;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="/static/logo.png" class="logo" alt="KIRII Logo">
            <div>
                <div class="header-title">STOCK-AI-SCAN</div>
            </div>
        </div>
        
        <div class="qr-scanner" id="qr-scanner">
            <button class="scan-button" id="scan-btn" onclick="toggleQRScan()">📱 QR Code Scan / QR碼掃描</button>
            <div id="qr-reader"></div>
            <div class="manual-input">
                <div class="input-group">
                    <input type="text" id="productCode" class="code-input" placeholder="Manual Input ProductCode or Number / 手動輸入產品代碼或編號" value="{{ query or '' }}">
                    <button class="search-button" onclick="searchProduct()">Search / 搜尋</button>
                </div>
            </div>
        </div>
        
        <div class="inventory-list">
            <div class="list-title">
                <div class="list-title-text">📦 Inventory List / 庫存清單</div>
                <button class="download-btn" onclick="downloadStockList()">📥 Download List/下載名單</button>
            </div>

            <!-- Category chips -->
            <div class="chip-bar">
                <!-- DEBUG: cat='{{ cat }}', cat_decoded='{{ cat_decoded }}' -->
                <a class="chip {{ 'active' if not cat_decoded or cat_decoded == '' else '' }}" href="/">All<span class="chip-count"></span></a>
                {% if 'AllBoard' in canon_counts %}
                <a class="chip {{ 'active' if cat_decoded=='AllBoard' else '' }}" href="/?cat=AllBoard">AllBoard<span class="chip-count">{{ canon_counts.get('AllBoard', 0) }}</span></a>
                {% endif %}
                {% if 'Allwool' in canon_counts %}
                <a class="chip {{ 'active' if cat_decoded=='Allwool' else '' }}" href="/?cat=Allwool">Allwool<span class="chip-count">{{ canon_counts.get('Allwool', 0) }}</span></a>
                {% endif %}
                <button class="more-btn" onclick="openSheet()">More</button>
                {% for c in top_categories %}
                {% if c != 'AllBoard' and c != 'Allwool' %}
                <a class="chip {{ 'active' if cat_decoded==c else '' }}" href="/?cat={{ c | urlencode }}">{{ c }}<span class="chip-count">{{ canon_counts.get(c, 0) }}</span></a>
                {% endif %}
                {% endfor %}
            </div>

            <!-- Bottom sheet for all categories -->
            <div id="cat-sheet" class="sheet">
                <div style="text-align:center; font-weight:bold; margin-bottom:8px;">Filter by Category</div>
                <input id="cat-search" type="text" placeholder="Search category..." style="width:100%; padding:8px; border:1px solid #dee2e6; border-radius:8px; font-size:12px; margin-bottom:8px;">
                <div class="grid" id="cat-grid">
                    {% for c, n in ordered_cnt %}
                    <button data-label="{{ c }}" onclick="selectCat('{{ c | urlencode }}')">{{ c }} ({{ n }})</button>
                    {% endfor %}
                </div>
                <div style="text-align:center; margin-top:8px;"><button class="more-btn" onclick="closeSheet()">Close</button></div>
            </div>
            {% for number, product in inventory_data.items() %}
            <div class="product-card" onclick="showProductDetail({{ number }})">
                <div class="product-code">產品編碼 | {{ product.code }}</div>
                <div class="product-name">{{ product.name }}</div>
                <div class="product-details">
                    📍 {{ product.location or '0' }} |
                    {% if product.on_hand is not none %}📦 OH {{ product.on_hand }}{{ product.unit }} |{% endif %}
                    {% if product.without_dn is not none %} 📃 w/o {{ product.without_dn }}{{ product.unit }} |{% endif %}
                    Avail 📊 {{ product.quantity }}{{ product.unit }}
                    | 🏷️ {{ 'MK' if 'merchandises' in ((product.category or '')|lower) else product.category }}
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="footer">
            STOCK-AI-SCAN / 庫存及AIQR掃描儀<br>
            Copyright © Kirii (Hong Kong) Limited. All Rights Reserved.
        </div>
    </div>
    

    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js"></script>
    <script>
        let videoStream = null;
        let isScanning = false;
        let scanInterval = null;
        
        function toggleQRScan() {
            if (!isScanning) {
                startQRScan();
            } else {
                stopQRScan();
            }
        }
        
        async function startQRScan() {
            const qrReader = document.getElementById('qr-reader');
            
            // HTTPSチェック
            if (location.protocol !== 'https:' && location.hostname !== 'localhost') {
                qrReader.innerHTML = '<div style="text-align: center; padding: 20px; color: red;">⚠️ HTTPS Required for Camera Access / 需要HTTPS才能使用相機<br><br>Please use manual input below / 請使用下方手動輸入</div>';
                return;
            }
            
            try {
                // カメラ権限を事前確認
                const permissions = await navigator.permissions.query({name: 'camera'});
                console.log('カメラ権限状態:', permissions.state);
                
                // カメラストリーム開始
                videoStream = await navigator.mediaDevices.getUserMedia({
                    video: {
                        facingMode: { ideal: "environment" },
                        width: { ideal: 640, max: 1280 },
                        height: { ideal: 480, max: 720 }
                    }
                });
                
                // ビデオ要素作成
                const video = document.createElement('video');
                video.autoplay = true;
                video.playsInline = true;
                video.muted = true;
                video.style.width = '100%';
                video.style.height = '300px';
                video.style.objectFit = 'cover';
                video.srcObject = videoStream;
                
                // Canvas作成（QR読み取り用）
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                
                qrReader.innerHTML = '';
                qrReader.appendChild(video);
                
                // 読み取り結果表示エリア
                const resultDiv = document.createElement('div');
                resultDiv.id = 'scan-result-display';
                resultDiv.style.cssText = 'text-align: center; padding: 10px; background: rgba(0,100,0,0.1); color: green; margin-top: 10px; border-radius: 5px; display: none;';
                qrReader.appendChild(resultDiv);
                
                
                isScanning = true;
                document.getElementById('scan-btn').textContent = '⏹️ Stop / 停止';
                document.getElementById('qr-scanner').classList.add('qr-active');
                
                // QR読み取り処理（jsQRライブラリ使用）- 高速化版
                scanInterval = setInterval(() => {
                    if (video.readyState === video.HAVE_ENOUGH_DATA) {
                        canvas.width = video.videoWidth;
                        canvas.height = video.videoHeight;
                        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                        
                        // jsQRでQRコード読み取り
                        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                        const code = jsQR(imageData.data, imageData.width, imageData.height);
                        
            if (code) {
                            console.log('QRコード読み取り成功:', code.data);
                            
                            // 結果表示
                            const resultDisplay = document.getElementById('scan-result-display');
                            resultDisplay.innerHTML = `✅ 読み取り成功: ${code.data}`;
                            resultDisplay.style.display = 'block';
                            
                            // 番号1-4の場合は即座に製品ページに移動（高速化）
                            if (['1', '2', '3', '4'].includes(code.data.trim())) {
                                stopQRScan();
                                // 遅延を200msに短縮（視覚的フィードバックは残す）
                                setTimeout(() => {
                                    window.location.href = '/product/' + code.data.trim();
                                }, 200);
            } else {
                                // 無効な番号の場合は2秒後に結果を非表示（短縮）
                                setTimeout(() => {
                                    if (resultDisplay) {
                                        resultDisplay.style.display = 'none';
                                    }
                                }, 2000);
                            }
                        }
                    }
                }, 150); // 150msごとにスキャン（高速化）
                
            } catch (error) {
                console.error('カメラアクセスエラー:', error);
                let errorMsg = 'カメラにアクセスできません。';
                
                if (error.name === 'NotAllowedError') {
                    errorMsg = '📷 カメラ権限が拒否されました。<br>ブラウザ設定でカメラアクセスを許可してください。';
                } else if (error.name === 'NotFoundError') {
                    errorMsg = '📷 カメラが見つかりません。';
                } else if (error.name === 'NotSupportedError') {
                    errorMsg = '📷 お使いのブラウザはカメラをサポートしていません。';
                }
                
                qrReader.innerHTML = `<div style="text-align: center; padding: 20px; color: red;">${errorMsg}<br><br>下の手動入力をご利用ください。</div>`;
            }
        }
        
        function stopQRScan() {
            if (scanInterval) {
                clearInterval(scanInterval);
                scanInterval = null;
            }
            
            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
                videoStream = null;
            }
            
            isScanning = false;
            document.getElementById('qr-reader').innerHTML = '';
            document.getElementById('scan-btn').textContent = '📱 QR Code Scan / QR碼掃描';
            document.getElementById('qr-scanner').classList.remove('qr-active');
        }
        
        function searchProduct() {
            const code = document.getElementById('productCode').value.trim();
            if (!code) {
                alert('Please enter ProductCode or Name / 請輸入產品代碼或名稱');
                return;
            }
            if (/^\d+$/.test(code)) {
            window.location.href = '/product/' + code;
                return;
            }
            // ProductCode 形（例: BD-060, AC-019 等）はコード優先
            if (/^[A-Za-z]{1,5}-[A-Za-z0-9]+$/.test(code)) {
                window.location.href = '/product/code/' + encodeURIComponent(code);
                return;
            }
            // それ以外は名称検索としてリストをフィルタ
            window.location.href = '/?q=' + encodeURIComponent(code);
        }
        
        function showProductDetail(number) {
            window.location.href = '/product/' + number;
        }
        
        document.getElementById('productCode').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchProduct();
            }
        });
        // Download stock list function
        function downloadStockList() {
            // Create CSV content with UTF-8 BOM for proper encoding (Complete Google Sheet mapping)
            let csvContent = "\\uFEFFNumber,Product_Code,Product_Name,Category,Stock_Location,On_Hand,Without_DN,Available_Quantity,Unit,Last_Updated\\n";
            
            // Add data from inventory
            {% for number, product in inventory_data.items() %}
            // 製品名を安全にCSV用にエスケープ
            var productName = "{{ product.name | replace('"', '""') | replace('\\n', ' ') | replace('\\r', ' ') | replace(',', '，') }}";
            // HTMLエンティティを再度デコード（Jinja2で再エンコードされた可能性）
            productName = productName.replace(/&#34;/g, '"').replace(/&#39;/g, "'");
            productName = productName.replace(/&quot;/g, '"').replace(/&apos;/g, "'");
            productName = productName.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
            productName = productName.replace(/&nbsp;/g, ' ');
            // 連続するダブルクォートを1つに統一
            productName = productName.replace(/""+/g, '"');
            
            csvContent += "{{ number }},{{ product.code }}," + productName + ",{{ product.category or '' }},{{ product.location or '0' }},{{ product.on_hand or '' }},{{ product.without_dn or '' }},{{ product.quantity or '0' }},{{ product.unit or '' }},{{ product.updated or '' }}\\n";
            {% endfor %}
            
            // Create and download file with proper UTF-8 encoding
            const blob = new Blob([csvContent], { 
                type: 'text/csv;charset=utf-8;',
                endings: 'native'
            });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', 'stock_list.csv');
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
        
        // Category sheet controls
        function openSheet(){ document.getElementById('cat-sheet').classList.add('open'); }
        function closeSheet(){ document.getElementById('cat-sheet').classList.remove('open'); }
        function selectCat(value){ window.location.href='/?cat='+value+ (document.getElementById('productCode').value? '&q='+encodeURIComponent(document.getElementById('productCode').value.trim()):''); }
        // Filter in sheet
        document.getElementById('cat-search').addEventListener('input', function(){
            const v=this.value.toLowerCase();
            document.querySelectorAll('#cat-grid button').forEach(b=>{
                b.style.display = b.textContent.toLowerCase().includes(v)?'block':'none';
            });
        });
        
        // ページ読み込み時にURLパラメータをチェックしてカメラ自動起動
        window.addEventListener('DOMContentLoaded', function() {
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('scan') === 'active') {
                // URLからパラメータを削除（履歴をきれいに保つ）
                const newUrl = window.location.pathname;
                window.history.replaceState({}, document.title, newUrl);
                
                // カメラを自動起動（少し遅延を入れて確実に起動）
                setTimeout(() => {
                    if (!isScanning) {
                        startQRScan();
                    }
                }, 300);
            }
        });
    </script>
</body>
</html>
    ''', 
    inventory_data=inventory_data,
    query=query,
    cat=cat,
    cat_decoded=cat_decoded,
    top_categories=top_categories_canon,
    canon_counts=canon_counts,
    ordered_cnt=ordered_cnt
    )

@app.route('/product/<int:product_number>')
def product_detail(product_number):
    """製品詳細ページ - QRコード番号からアクセス"""
    try:
        # Googleシートから最新の在庫データを取得
        inventory_data = platform.get_inventory_data()
        
        if product_number not in inventory_data:
            return render_template_string('''
        <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif; background: white; color: #333;">
            <h1>❌ 製品が見つかりません</h1>
            <p>番号: {{ number }}</p>
            <a href="/" style="color: #007bff;">トップページに戻る</a>
        </div>
        ''', number=product_number), 404
        
        product = inventory_data[product_number]
        
        return render_template_string('''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📦 {{ product.name | replace('&#34;', '"') | replace('&#39;', "'") | replace('&quot;', '"') | replace('&apos;', "'") | replace('&amp;', '&') | replace('&lt;', '<') | replace('&gt;', '>') }} - STOCK-AI-SCAN</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: white;
            min-height: 100vh;
            color: #333;
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .header {
            display: flex;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .logo {
            height: 27px;
            width: auto;
            margin-right: 15px;
        }
        
        .back-button {
            background: #6c757d;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s ease;
        }
        
        .back-button:hover {
            background: #5a6268;
            transform: translateY(-2px);
        }
        
        .product-card {
            background: #f8f9fa;
            border: 2px solid #dee2e6;
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            margin-top: 20px;
        }
        
        .product-number {
            display: none;
        }
        
        .product-code {
            display: none;
        }
        .product-code-line {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
            margin-bottom: 20px;
        }
        
        .product-name {
            font-size: 1.5em;
            font-weight: bold;
            color: #333;
            margin-bottom: 30px;
            line-height: 1.4;
            word-wrap: break-word;
            word-break: break-all;
            overflow-wrap: break-word;
            hyphens: auto;
            max-width: 100%;
        }
        
        .details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            grid-template-rows: auto auto auto;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .detail-item {
            background: white;
            border: 2px solid #dee2e6;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .detail-item.factory-layout-item {
            grid-column: 1 / -1; /* 2行目は全幅 */
        }
        
        .detail-item.last-updated-item {
            grid-column: 1 / -1; /* 3行目は全幅 */
        }
        
        .detail-label {
            font-size: 0.9em;
            color: #6c757d;
            margin-bottom: 5px;
        }
        
        .detail-value {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
        }
        
        .quantity {
            font-size: 2em;
            color: #28a745;
        }
        
        .location-value {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        
        .scan-again {
            background: #28a745;
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.1em;
            font-weight: bold;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
            transition: all 0.3s ease;
        }
        
        .scan-again:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #6c757d;
            font-size: 0.8em;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
        }
        
        /* 工場配置図スタイル */
        .factory-layout {
            margin-top: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 8px;
            border: 1px solid #dee2e6;
        }
        
        .layout-title {
            font-size: 0.85em;
            color: #6c757d;
            margin-bottom: 8px;
            text-align: center;
        }
        
        .factory-grid {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            grid-template-rows: repeat(4, 1fr);
            gap: 2px;
            max-width: 100%;
            aspect-ratio: 3/2;
            position: relative;
        }
        
        /* 工場内部の外壁境界線 */
        .factory-grid::after {
            content: '';
            position: absolute;
            top: 0;                      /* B-1行の上端に合わせる */
            left: calc(16.666% + 1px);   /* B列の左端に合わせる */
            width: calc(66.666% - 2px);  /* B-1からE-3の幅 */
            height: calc(75% - 1px);     /* B-1からB-3の高さ */
            border: 3px solid #333;
            border-radius: 4px;
            pointer-events: none;
            z-index: 1;
        }
        
        .grid-cell {
            background: #ffffff;
            border: 1px solid #dee2e6;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7em;
            font-weight: bold;
            color: #333;
            border-radius: 3px;
            min-height: 20px;
            transition: all 0.3s ease;
        }
        
        .grid-cell.entrance {
            background: #e9ecef;
            color: #6c757d;
            font-size: 0.6em;
        }
        
        .grid-cell.storage-cell {
            background: #ffffff;
            color: #333;
            cursor: pointer;
        }
        
        .grid-cell.storage-cell:hover {
            background: #e3f2fd;
            border-color: #2196f3;
        }
        
        .grid-cell.storage-cell.highlighted {
            background: #4caf50;
            color: white;
            border-color: #388e3c;
            box-shadow: 0 2px 4px rgba(76, 175, 80, 0.3);
            transform: scale(1.05);
        }
        
        .grid-cell.empty {
            background: transparent;
            border: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="/static/logo.png" class="logo" alt="KIRII Logo">
            <button class="back-button" onclick="window.location.href='/?scan=active'">← Back / 返回</button>
        </div>
        
        <div class="product-card">
            <div class="product-code-line">產品編碼 | {{ product.code }}</div>
            <div class="product-name">{{ product.name | replace('&#34;', '"') | replace('&#39;', "'") | replace('&quot;', '"') | replace('&apos;', "'") | replace('&amp;', '&') | replace('&lt;', '<') | replace('&gt;', '>') }}</div>
            
            <div class="details-grid">
                <div class="detail-item">
                    <div class="detail-label">📊Available Stock / 可出數量</div>
                    <div class="detail-value quantity">{{ product.quantity }}{{ product.unit }}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">📍 Storage Location / 儲存位置</div>
                    <div class="detail-value location-value">{{ product.location or '0' }}</div>
            </div>
                <div class="detail-item">
                    <div class="detail-label">📃 w/o DN / 有單未出</div>
                    <div class="detail-value">{{ (product.without_dn if product.without_dn is not none else '—') }}{{ (product.unit if product.without_dn is not none else '') }}</div>
                </div>
                <div class="detail-item">
                    <div class="detail-label">📦 On Hand / 倉庫數量</div>
                    <div class="detail-value">{{ (product.on_hand if product.on_hand is not none else '—') }}{{ (product.unit if product.on_hand is not none else '') }}</div>
                </div>
                <div class="detail-item factory-layout-item">
                    <div class="detail-label">🏭 Factory Layout / 工廠配置圖</div>
                    <div class="factory-layout">
                        <div class="factory-grid">
                            <div class="grid-cell entrance">門口</div>
                            <div class="grid-cell storage-cell" data-location="B-1">B-1</div>
                            <div class="grid-cell storage-cell" data-location="C-1">C-1</div>
                            <div class="grid-cell storage-cell" data-location="D-1">D-1</div>
                            <div class="grid-cell storage-cell" data-location="E-1">E-1</div>
                            <div class="grid-cell storage-cell" data-location="A-9">A-9</div>
                            
                            <div class="grid-cell storage-cell" data-location="A-1">A-1</div>
                            <div class="grid-cell storage-cell" data-location="B-2">B-2</div>
                            <div class="grid-cell storage-cell" data-location="C-2">C-2</div>
                            <div class="grid-cell storage-cell" data-location="D-2">D-2</div>
                            <div class="grid-cell storage-cell" data-location="E-2">E-2</div>
                            <div class="grid-cell storage-cell" data-location="A-8">A-8</div>
                            
                            <div class="grid-cell storage-cell" data-location="A-2">A-2</div>
                            <div class="grid-cell storage-cell" data-location="B-3">B-3</div>
                            <div class="grid-cell storage-cell" data-location="C-3">C-3</div>
                            <div class="grid-cell storage-cell" data-location="D-3">D-3</div>
                            <div class="grid-cell storage-cell" data-location="E-3">E-3</div>
                            <div class="grid-cell storage-cell" data-location="A-7">A-7</div>
                            
                            <div class="grid-cell storage-cell" data-location="A-3">A-3</div>
                            <div class="grid-cell storage-cell" data-location="A-4">A-4</div>
                            <div class="grid-cell storage-cell" data-location="A-5">A-5</div>
                            <div class="grid-cell storage-cell" data-location="A-6">A-6</div>
                            <div class="grid-cell empty"></div>
                            <div class="grid-cell empty"></div>
                </div>
                </div>
                </div>
                <div class="detail-item last-updated-item">
                    <div class="detail-label">📅 Last Updated / 最後更新</div>
                    <div class="detail-value">{{ product.updated }}</div>
                </div>
            </div>
            
            <button class="scan-again" onclick="window.location.href='/'">📱 Scan Other Products / 掃描其他產品</button>
        </div>
        
        <div class="footer">
            STOCK-AI-SCAN / 庫存及AIQR掃描儀<br>
            Copyright © Kirii (Hong Kong) Limited. All Rights Reserved.
        </div>
    </div>
    
    <script>
        // 工場配置図で該当位置をハイライト
        document.addEventListener('DOMContentLoaded', function() {
            const currentLocation = '{{ product.location }}';
            const storageCells = document.querySelectorAll('.storage-cell');
            
            storageCells.forEach(cell => {
                if (cell.dataset.location === currentLocation) {
                    cell.classList.add('highlighted');
                }
            });
        });
        
        // 製品詳細ページ用の関数
        function showProductDetail(number) {
            window.location.href = '/product/' + number;
        }
    </script>
</body>
</html>
    ''', product=product, number=product_number)
    
    except Exception as e:
        print(f"❌ 製品詳細ページエラー (番号: {product_number}): {e}")
        return render_template_string('''
        <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif; background: white; color: #333;">
            <h1>❌ エラーが発生しました</h1>
            <p>製品番号: {{ number }}</p>
            <p>エラー: {{ error }}</p>
            <a href="/" style="color: #007bff;">トップページに戻る</a>
        </div>
        ''', number=product_number, error=str(e)), 500

@app.route('/api/inventory')
def api_inventory():
    """在庫データAPI"""
    inventory_data = platform.get_inventory_data()
    return jsonify(inventory_data)

@app.route('/api/product/<int:product_number>')
def api_product(product_number):
    """製品詳細API"""
    inventory_data = platform.get_inventory_data()
    
    if product_number not in inventory_data:
        return jsonify({'error': 'Product not found'}), 404
    
    return jsonify({
        'number': product_number,
        'product': inventory_data[product_number]
    })

@app.route('/product/code/<path:product_code>')
def product_detail_by_code(product_code):
    """製品詳細ページ - 製品コード/名称からアクセス（C列 ProductCode / G列 ProductName）"""
    inventory_data = platform.get_inventory_data()
    # URLデコード（%20 → 空白 など）
    display_code = unquote(product_code)

    # 製品コード 厳密一致（大文字小文字・全半角を無視した厳密一致）
    import unicodedata
    def normalize(s: str) -> str:
        if s is None:
            return ''
        s = unicodedata.normalize('NFKC', str(s))
        return ' '.join(s.lower().split())

    norm_target = normalize(display_code)
    for num, v in inventory_data.items():
        code = v.get('code')
        if normalize(code) == norm_target:
            return redirect(f'/product/{num}')

    # 部分一致（製品名）: 大文字小文字・全角半角・スペース差を緩く比較
    needle = norm_target
    matches = []
    for num, v in inventory_data.items():
        name = v.get('name', '')
        code = v.get('code', '')
        if needle and (needle in normalize(name) or needle in normalize(code)):
            matches.append((num, v))

    if len(matches) == 1:
        return redirect(f'/product/{matches[0][0]}')
    if len(matches) > 1:
        # 複数候補表示
        return render_template_string('''
        <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 30px auto;">
            <h2>🔎 Search Results</h2>
            <p>Query: {{ q }}</p>
            <ul>
            {% for num, item in items %}
                <li><a href="/product/{{ num }}">[{{ num }}] {{ item.code }} — {{ item.name }}</a></li>
            {% endfor %}
            </ul>
            <p><a href="/">Back to Home</a></p>
        </div>
        ''', q=product_code, items=matches)

    # 該当なし（広東語繁體字／英語）
    return render_template_string('''
    <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif; background: white; color: #333;">
        <h1 style="margin-bottom:16px;">搵唔到產品 / Product not found</h1>
        <p style="margin:8px 0;">你輸入：{{ code }}</p>
        <p style="margin:8px 0;">You entered: {{ code }}</p>
        <div style="margin-top:14px; text-align:left; display:inline-block;">
            <p><strong>提示 / Tips</strong></p>
            <ul>
                <li>請檢查拼寫同空格；避免全形／半形混用</li>
                <li>試下用產品代碼（例：BD-060）或者關鍵字（例：Hanger）</li>
                <li>Check spelling and spaces; avoid mixing full-width/half-width chars</li>
                <li>Try a ProductCode (e.g., BD-060) or a keyword (e.g., Hanger)</li>
            </ul>
        </div>
        <p style="margin-top:18px;"><a href="/" style="color: #007bff;">返回首頁 / Back to Home</a></p>
    </div>
    ''', code=display_code), 404

# 静的ファイル /static/logo.png として配信
# @app.route('/static/logo')
# def get_logo():
    """KIRIIロゴを提供 - Base64で直接埋め込み"""
    # KIRIIロゴのBase64データ（直接埋め込み）
    logo_base64 = "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"
    
    try:
        import base64
        logo_data = base64.b64decode(logo_base64)
        return logo_data, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        print(f"ロゴ読み込みエラー: {e}")
        return "KIRII", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    print("🏭 KIRII在庫管理Vercelプラットフォーム起動")
    print("📱 携帯対応在庫確認システム")
    print("🌐 アクセス: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)