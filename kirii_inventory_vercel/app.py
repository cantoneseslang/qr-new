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
        self.use_google_sheets = bool(self.sheet_url)
        
        # テスト用のローカルデータ（Googleシートと同じ構造）
        self.fallback_inventory = {
            1: {"code": "BD-060", "name": "泰山普通石膏板 4'x6'x12mmx 4.5mm", "quantity": 200, "updated": "2025-07-26", "location": "A-1", "category": "Merchandies", "unit": "張"},
            2: {"code": "US0503206MM2440", "name": "Stud 50mmx32mmx0.6mmx2440mm", "quantity": 200, "updated": "2025-07-26", "location": "A-2", "category": "Products", "unit": "只"},
            3: {"code": "AC-258", "name": "KIRII Corner Bead 2440mm (25pcs/bdl)(0.4mm 鋁)", "quantity": 50, "updated": "2025-07-26", "location": "B-1", "category": "Products", "unit": "個"},
            4: {"code": "AC-261", "name": "黃岩綿- 60g (6pcs/pack)", "quantity": 10, "updated": "2025-07-26", "location": "C-1", "category": "MK", "unit": "包"}
        }
        
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

    def _init_google_sheets(self):
        """Googleシート接続を初期化"""
        try:
            # シートIDを抽出
            self.sheet_id = self._extract_sheet_id_from_url(self.sheet_url)
            if not self.sheet_id:
                print("⚠️ 無効なシートURL")
                self.use_google_sheets = False
                return
                
            # API Key設定
            self.api_key = "AIzaSyARbSHGDK-dCkmuP8ys7E2-G-treb3ZYIw"
            
            # サービスアカウント認証（将来の拡張用）
            if os.path.exists('google_service_account.json'):
                try:
                    # 依存が無い環境でも動作するよう遅延インポート
                    from google.oauth2 import service_account  # type: ignore
                    from googleapiclient.discovery import build  # type: ignore

                    credentials = service_account.Credentials.from_service_account_file(
                        'google_service_account.json',
                        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
                    )
                    self.sheets_service = build('sheets', 'v4', credentials=credentials)
                    print("✅ サービスアカウント認証成功")
                except Exception as e:
                    print(f"⚠️ サービスアカウント認証失敗またはライブラリ未導入: {e}")
                    print("📋 API Key方式を使用します")
            
            # Google Sheets API接続テスト（対象シート: Stock）
            test_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Stock!A1:A1?key={self.api_key}"
            test_response = requests.get(test_url, timeout=10)
            
            if test_response.status_code == 200:
                print(f"✅ Googleシート接続成功 (ID: {self.sheet_id[:8]}...)")
                self.use_google_sheets = True
            else:
                print(f"❌ Googleシート接続失敗: {test_response.status_code}")
                print("📋 フォールバックモードで動作")
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
        if self.use_google_sheets and hasattr(self, 'api_key'):
            try:
                return self._fetch_from_google_sheets()
            except Exception as e:
                print(f"⚠️ Googleシートからのデータ取得エラー: {e}")
                print("📋 フォールバックデータを使用します")
                
        return self.fallback_inventory

    def _fetch_from_google_sheets(self):
        """Googleシートからデータを取得（API Key方式）"""
        import requests
        import time
        
        try:
            # Google Sheets API URL（シート名: Stock、列範囲: A〜AE、十分な行数を取得）
            api_url = f"https://sheets.googleapis.com/v4/spreadsheets/{self.sheet_id}/values/Stock!A1:AE1500?key={self.api_key}"
            
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

                    # D列: 製品名（品名をD列参照に統一）
                    name = row[3] if len(row) > 3 else ''

                    # H列: 保管場所 正規化（空/"0"→"0"）
                    raw_loc = row[7] if len(row) > 7 else ''
                    loc_str = str(raw_loc).strip()
                    normalized_loc = '0' if (loc_str == '' or loc_str == '0') else loc_str

                    # K列: Available（在庫数量）カンマ付き・負数対応
                    raw_qty = row[10] if len(row) > 10 else '0'
                    qty_str = str(raw_qty).replace(',', '').strip()
                    quantity = int(qty_str) if (qty_str and qty_str.lstrip('-').isdigit()) else 0

                    # I列: On Hand（参考値）
                    raw_on_hand = row[8] if len(row) > 8 else ''
                    on_hand_str = str(raw_on_hand).replace(',', '').strip()
                    on_hand = int(on_hand_str) if (on_hand_str and on_hand_str.lstrip('-').isdigit()) else None

                    # J列: w/o DN（出荷未処理）
                    raw_wo = row[9] if len(row) > 9 else ''
                    wo_str = str(raw_wo).replace(',', '').strip()
                    without_dn = int(wo_str) if (wo_str and wo_str.lstrip('-').isdigit()) else None

                    # L列: Unit
                    unit_val = row[11] if len(row) > 11 else ''

                    # M列: LastTime
                    updated_val = row[12] if len(row) > 12 else datetime.now().strftime('%Y-%m-%d')

                    # E列: Category-3
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

platform = KiriiInventoryPlatform()

ALLOWED_REFERRERS = set([d.strip().lower() for d in os.getenv('ALLOWED_REFERRERS', 'kirii-portfolio-1.vercel.app').split(',') if d.strip()])
STRICT_REFERER = os.getenv('STRICT_REFERER', '0') != '0'  # デフォルトで無効化

@app.before_request
def enforce_referer_protection():
    if not STRICT_REFERER:
        return
    path = request.path or '/'
    # 例外（ロゴ/ファビコン）
    if path.startswith('/static/logo') or path == '/favicon.ico':
        return
    # ローカル開発は許可
    if request.host.startswith('localhost') or request.host.startswith('127.0.0.1'):
        return
    referer = request.headers.get('Referer', '')
    # リファラが無い場合は拒否
    if not referer:
        abort(401)
    try:
        ref_host = urlparse(referer).hostname or ''
        req_host = request.host.split(':')[0].lower()
        if ref_host.lower() == req_host:
            return
        if ref_host.lower() in ALLOWED_REFERRERS:
            return
    except Exception:
        pass
    abort(401)

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
      <a class="btn" href="https://kirii-portfolio-1.vercel.app">返回公司入口 · Back to company portal</a>
    </div>
  </body>
</html>
    '''), 401

@app.route('/')
def index():
    """メインページ - QRスキャン機能付き"""
    # Googleシートから最新の在庫データを取得
    inventory_data = platform.get_inventory_data()
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
        # mm Runner/Stud を統一（例: "50mm - S", "50mmS" など）
        m = re.search(r'(\d+)mm[- ]?([rs])', s)
        if m:
            return f"{m.group(1)}mm-{m.group(2)}"
        # 2-1/2"-R/S を統一
        m = re.search(r'2[- ]?1\/2\"?[- ]?([rs])', s)
        if m:
            return f"2-1/2\"-{m.group(1)}"
        # HD/SD 系
        m = re.search(r'^(hd|sd)[- ]?(\d+)$', s)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        # 既知カテゴリは大文字・ハイフン抜きで丸め
        s2 = re.sub(r'[^a-z0-9]+', '', s)
        return s2

    if cat:
        from urllib.parse import unquote
        cat_key = _canon_cat(unquote(cat))
        inventory_data = {
            num: item for num, item in inventory_data.items()
            if _canon_cat(item.get('category', '')) == cat_key
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

    # カテゴリを正規化しつつ集計（同義語・表記ゆれを束ねる）
    raw_categories = [v.get('category', '') for v in platform.get_inventory_data().values()]
    canon_counts = Counter([_canon_cat(c) for c in raw_categories if c])
    # 表示用ラベル（最初に見つかったものを短縮整形して採用）
    canon_to_display = {}
    for c in raw_categories:
        k = _canon_cat(c)
        if k and k not in canon_to_display:
            canon_to_display[k] = normalize_label(c)

    # 並び順キー: 正規化キーで判定
    def category_sort_key_canon(canon: str):
        m = re.match(r'^(\d+)mm-([rs])$', canon)
        if m:
            return (0, int(m.group(1)), 0 if m.group(2) == 'r' else 1, canon)
        if canon.startswith('2-1/2"-'):
            # 63.5mm相当、R優先
            return (0, 63, 0 if canon.endswith('-r') else 1, canon)
        m = re.match(r'^(hd|sd)-(\d+)$', canon)
        if m:
            return (1 if m.group(1) == 'hd' else 2, int(m.group(2)), 0, canon)
        known = ['accesspanel','access','bdgr','bdfc','bdmc','mangle','screw',
                 'teebarmk15','teebarmk24','tbarnc','uch','astmg90','amk','zmk','boardmacau']
        for idx, name in enumerate(known):
            if canon.startswith(name):
                return (3, idx, 0, canon)
        return (4, canon)

    ordered_canon = sorted(canon_counts.keys(), key=category_sort_key_canon)
    top_categories_canon = ordered_canon[:10]
    ordered_cnt = [(c, canon_counts[c]) for c in ordered_canon]

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
            text-align: center;
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
            <img src="/static/logo" class="logo" alt="KIRII Logo">
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
            <div class="list-title">📦 Inventory List / 庫存清單</div>

            <!-- Category chips -->
            <div class="chip-bar">
                <a class="chip {{ 'active' if not cat else '' }}" href="/">All<span class="chip-count"></span></a>
                {% for c in top_categories %}
                <a class="chip {{ 'active' if cat==c else '' }}" href="/?cat={{ c | urlencode }}">{{ canon_to_display.get(c, c) }}<span class="chip-count">{{ dict(ordered_cnt).get(c, 0) }}</span></a>
                {% endfor %}
                <button class="more-btn" onclick="openSheet()">More</button>
            </div>

            <!-- Bottom sheet for all categories -->
            <div id="cat-sheet" class="sheet">
                <div style="text-align:center; font-weight:bold; margin-bottom:8px;">Filter by Category</div>
                <input id="cat-search" type="text" placeholder="Search category..." style="width:100%; padding:8px; border:1px solid #dee2e6; border-radius:8px; font-size:12px; margin-bottom:8px;">
                <div class="grid" id="cat-grid">
                    {% for c, n in ordered_cnt %}
                    <button data-label="{{ c }}" onclick="selectCat('{{ c | urlencode }}')">{{ normalize_label(c) }} ({{ n }})</button>
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
    top_categories=top_categories_canon,
    canon_to_display=canon_to_display,
    normalize_label=normalize_label,
    ordered_cnt=ordered_cnt
    )

@app.route('/product/<int:product_number>')
def product_detail(product_number):
    """製品詳細ページ - QRコード番号からアクセス"""
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
    <title>📦 {{ product.name }} - STOCK-AI-SCAN</title>
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
            <img src="/static/logo" class="logo" alt="KIRII Logo">
            <button class="back-button" onclick="window.location.href='/?scan=active'">← Back / 返回</button>
        </div>
        
        <div class="product-card">
            <div class="product-code-line">產品編碼 | {{ product.code }}</div>
            <div class="product-name">{{ product.name }}</div>
            
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
    </script>
</body>
</html>
    ''', 
    product=product,
    number=product_number
    )

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

@app.route('/static/logo')
def get_logo():
    """KIRIIロゴを提供"""
    try:
        # Base64データファイルから読み込み
        if os.path.exists('logo_base64.txt'):
            with open('logo_base64.txt', 'r') as f:
                base64_data = f.read().strip()
            
            # data:image/png;base64, の部分を除去してBase64データのみ取得
            if base64_data.startswith('data:image/png;base64,'):
                base64_data = base64_data.replace('data:image/png;base64,', '')
            
            import base64
            logo_data = base64.b64decode(base64_data)
            return logo_data, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        print(f"Base64ロゴ読み込みエラー: {e}")
    
    try:
        # Base64ファイルが見つからない場合は、PNGファイルを試す
        if os.path.exists('KIRII-logo-3.png'):
            with open('KIRII-logo-3.png', 'rb') as f:
                logo_data = f.read()
            return logo_data, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        print(f"PNGロゴ読み込みエラー: {e}")
    
    # どちらも見つからない場合は、デフォルトのテキストロゴを返す
    print("ロゴファイルが見つかりません。テキストロゴを使用します。")
    return "KIRII", 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    print("🏭 KIRII在庫管理Vercelプラットフォーム起動")
    print("📱 携帯対応在庫確認システム")
    print("🌐 アクセス: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)