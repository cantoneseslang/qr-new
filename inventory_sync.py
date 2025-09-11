#!/usr/bin/env python3
import email
import imaplib
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from typing import List, Any, Tuple

from google.oauth2.service_account import Credentials as SA_Credentials
import json as _json
from googleapiclient.discovery import build as ga_build
from googleapiclient.errors import HttpError
from email.header import decode_header, make_header


def _now_jst() -> datetime:
    return datetime.now(timezone(timedelta(hours=9)))


def _fmt_report_sheet_title() -> str:
    now = _now_jst()
    # 例: InventorySummaryReport20250910
    return f"InventorySummaryReport{now.strftime('%Y%m%d')}"


def _ensure_sheets_service() -> Tuple[Any, str]:
    spreadsheet_id = os.environ.get('PQFORM_SHEET_ID') or ''
    if not spreadsheet_id:
        raise RuntimeError('環境変数 PQFORM_SHEET_ID が未設定です')

    sa_json = os.environ.get('GOOGLE_SA_JSON')
    sa_file = os.environ.get('GOOGLE_SA_FILE')
    if not sa_json and not sa_file:
        raise RuntimeError('サービスアカウント認証情報が未設定（GOOGLE_SA_JSON または GOOGLE_SA_FILE）')

    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    if sa_json:
        creds = SA_Credentials.from_service_account_info(_json.loads(sa_json), scopes=scopes)
    else:
        creds = SA_Credentials.from_service_account_file(sa_file, scopes=scopes)

    service = ga_build('sheets', 'v4', credentials=creds, cache_discovery=False)
    return service, spreadsheet_id


def _find_latest_inventory_pdf_from_gmail() -> str:
    """
    GmailのIMAPで件名に 'inventory' を含む最新メールのPDF添付を1つ保存して返す。
    必要環境変数: GMAIL_ADDRESS, GMAIL_APP_PASSWORD
    """
    # 1) テスト用フォールバック（手元のPDFを直接指定してバイパス）
    test_pdf = os.environ.get('TEST_PDF_PATH')
    if test_pdf and os.path.isfile(test_pdf):
        return test_pdf

    user = os.environ.get('GMAIL_ADDRESS')
    app_pw = os.environ.get('GMAIL_APP_PASSWORD')
    if not user or not app_pw:
        raise RuntimeError('GMAIL_ADDRESS または GMAIL_APP_PASSWORD が未設定です')

    mbox = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    try:
        mbox.login(user, app_pw)
        mbox.select('INBOX')
        # シンプルに最新100通を対象に件名マッチ + PDF添付を探索
        typ, data = mbox.search(None, 'ALL')
        if typ != 'OK':
            raise RuntimeError('Gmail検索に失敗しました')
        all_ids = data[0].split()
        if not all_ids:
            raise RuntimeError('メールボックスが空です')
        ids = all_ids[-100:]  # 末尾（新しい）100通に限定
        # 最新から探索
        for msg_id in reversed(ids):
            typ, msg_data = mbox.fetch(msg_id, '(RFC822)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            try:
                subj_decoded = str(make_header(decode_header(msg.get('Subject') or '')))
            except Exception:
                subj_decoded = msg.get('Subject') or ''
            subj_lower = subj_decoded.lower()
            if 'inventory' not in subj_lower:
                continue
            # 添付からPDFを探す
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue
                filename = part.get_filename() or ''
                if filename.lower().endswith('.pdf'):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                        tmp.write(part.get_payload(decode=True))
                        return tmp.name
        raise RuntimeError('PDF添付が見つかりませんでした（最新100通・件名に"inventory"）\nTEST_PDF_PATH にファイルパスを設定するとフォールバックできます')
    finally:
        try:
            mbox.logout()
        except Exception:
            pass


def _extract_table_locally(pdf_path: str) -> List[List[Any]]:
    """pdfplumber で表を抽出し、必要列にマッピングして返す。Gemini不要。"""
    try:
        import pdfplumber  # type: ignore
    except Exception as e:
        raise RuntimeError(f'pdfplumber の読み込みに失敗しました: {e}')

    required_headers = [
        ('product code', ['product code', 'code', 'item code', 'product']),
        ('description', ['description', 'item description', 'desc']),
        ('onhand', ['onhand quantity sc w/o dn', 'onhand quantity', 'onhand', 'qty on hand']),
        ('available', ['available', 'availble', 'available qty', 'balance']),
    ]

    def normalize(s: Any) -> str:
        return str(s or '').strip().lower()

    def find_column_indices(header_row: List[Any]) -> dict:
        mapping = {}
        norm = [normalize(h) for h in header_row]
        for key, variants in required_headers:
            idx = -1
            for i, h in enumerate(norm):
                if any(v in h for v in variants):
                    idx = i
                    break
            if idx >= 0:
                mapping[key] = idx
        return mapping

    collected: List[List[Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 複数戦略でテーブル抽出を試す
            strategies = [
                dict(vertical_strategy='lines', horizontal_strategy='lines'),
                dict(vertical_strategy='text', horizontal_strategy='text'),
                {},
            ]
            for ts in strategies:
                try:
                    tables = page.extract_tables(table_settings=ts) if ts else page.extract_tables()
                except Exception:
                    continue
                for t in tables or []:
                    if not t or not any(any(cell for cell in row) for row in t):
                        continue
                    # 先頭にヘッダがある前提で走査（数行見て合致ヘッダを探す）
                    header_idx = -1
                    col_map = {}
                    max_scan = min(5, len(t))
                    for r in range(max_scan):
                        col_map = find_column_indices(t[r])
                        if len(col_map) >= 3:  # 必要列のうち3つ以上検出できれば採用
                            header_idx = r
                            break
                    if header_idx == -1:
                        continue
                    # データ行を収集
                    for row in t[header_idx+1:]:
                        if not row or not any(row):
                            continue
                        def get(idx: int) -> Any:
                            try:
                                return row[idx]
                            except Exception:
                                return ''
                        prod = get(col_map.get('product code', -1))
                        desc = get(col_map.get('description', -1))
                        onhand = get(col_map.get('onhand', -1))
                        avail = get(col_map.get('available', -1))
                        # 最低限コードか説明がある行のみ
                        if not str(prod).strip() and not str(desc).strip():
                            continue
                        collected.append([
                            str(prod or '').strip(),
                            str(desc or '').strip(),
                            str(onhand or '').strip(),
                            str(avail or '').strip(),
                        ])

    # ヘッダ付与とE列ダミー追加
    if not collected:
        raise RuntimeError('PDFからテーブルを抽出できませんでした（ローカル解析）')
    header = [
        'Product Code',
        'Description',
        'OnHand Quantity SC w/o DN',
        'Available',
        'Available (dup)'
    ]
    rows = [header]
    for prod, desc, onhand, avail in collected:
        rows.append([prod, desc, onhand, avail, avail])
    return rows


def _extract_table_with_gemini(pdf_path: str) -> List[List[Any]]:
    """
    Gemini 2.5 PRO でPDFから表を抽出。戻り値は 2次元配列（ヘッダ含む）。
    必要環境変数: GEMINI_API_KEY
    """
    import google.generativeai as genai  # 遅延import

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('環境変数 GEMINI_API_KEY が未設定です')

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-pro')

    prompt = (
        "次のPDFから以下の列を抽出し、ヘッダ行付きの表データをJSON配列で返してください。"
        "列: Product Code, Description, OnHand Quantity SC w/o DN, Available. "
        "出力は必ず JSON のみ（例: [{\"Product Code\":\"...\",\"Description\":\"...\",\"OnHand Quantity SC w/o DN\":123,\"Available\":123}]）。"
    )

    text = ''
    try:
        # まずはファイルアップロード経由で解析（推奨）
        uploaded = genai.upload_file(pdf_path)
        resp = model.generate_content([uploaded, prompt])
        text = resp.text or ''
    except Exception:
        # ファイルアップロードが失敗する環境向けフォールバック
        # ローカルでPDFテキストを抽出して、テキストを直接プロンプトに渡す
        try:
            import pdfplumber  # type: ignore
            extracted = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    extracted.append(page.extract_text() or '')
            pdf_text = '\n'.join(extracted)
        except Exception:
            # pdfplumber不調時はPyPDF2で簡易抽出
            try:
                from PyPDF2 import PdfReader  # type: ignore
                reader = PdfReader(pdf_path)
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or '')
                pdf_text = '\n'.join(parts)
            except Exception as e:
                raise RuntimeError(f'PDFテキスト抽出に失敗しました: {e}')

        trimmed = pdf_text[:15000]
        alt_prompt = (
            "次のPDFテキストから、列 Product Code, Description, OnHand Quantity SC w/o DN, Available を抽出し、"
            "ヘッダ付きのJSON配列で返してください。出力はJSONのみ。\n--- PDF TEXT START ---\n" + trimmed + "\n--- PDF TEXT END ---\n"
        )
        resp = model.generate_content(alt_prompt)
        text = resp.text or ''

    # JSON抽出
    import json
    m = re.search(r"\[.*\]", text, flags=re.S)
    if not m:
        raise RuntimeError('Geminiの応答からJSONを抽出できませんでした')
    arr = json.loads(m.group(0))

    # 行化（ヘッダ + データ）
    # フォーミュラ要件に合わせて A:E の5列を作成
    # 3列目(C) = OnHand Quantity SC w/o DN, 4列目(D) = Available, 5列目(E) = Availableの複製
    header = [
        'Product Code',
        'Description',
        'OnHand Quantity SC w/o DN',
        'Available',
        'Available (dup)'
    ]
    rows = [header]
    for obj in arr:
        rows.append([
            obj.get('Product Code', ''),
            obj.get('Description', ''),
            obj.get('OnHand Quantity SC w/o DN', ''),
            obj.get('Available', ''),
            obj.get('Available', ''),
        ])
    return rows


def _sheets_create_sheet_if_not_exists(service, spreadsheet_id: str, title: str) -> None:
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        for s in meta.get('sheets', []):
            if s.get('properties', {}).get('title') == title:
                return
        # create
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                'requests': [{
                    'addSheet': {
                        'properties': {'title': title}
                    }
                }]
            }
        ).execute()
    except HttpError as e:
        raise RuntimeError(f'Sheetsのシート作成でエラー: {e}')


def _sheets_write_rows(service, spreadsheet_id: str, sheet_title: str, rows: List[List[Any]]):
    rng = f"{sheet_title}!A1"
    body = {"values": rows}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()


def _sheets_find_last_row_in_stock(service, spreadsheet_id: str) -> int:
    rng = 'Stock!C:C'
    res = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id, range=rng
    ).execute()
    values = res.get('values', [])
    last = 0
    for i, row in enumerate(values, start=1):
        if row and any(cell.strip() for cell in row if isinstance(cell, str)):
            last = i
    return max(last, 2)


def _sheets_update_stock_formulas(service, spreadsheet_id: str, summary_title: str):
    last_row = _sheets_find_last_row_in_stock(service, spreadsheet_id)
    if last_row < 2:
        return

    # 行別に I/J/K の式を生成
    updates = []
    for r in range(2, last_row + 1):
        i_formula = f"=IFERROR(VLOOKUP($C{r},{summary_title}!$A:$E, 3, 0), 0)"
        j_formula = f"=IFERROR(VLOOKUP($C{r},{summary_title}!$A:$E, 4, 0), 0)"
        k_formula = f"=IFERROR(VLOOKUP($C{r},{summary_title}!$A:$E, 5, 0), 0)"
        updates.append([i_formula, j_formula, k_formula])

    rng = f"Stock!I2:K{last_row}"
    body = {"values": updates}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption='USER_ENTERED',
        body=body
    ).execute()


def run_inventory_sync() -> dict:
    """メイン処理。例外は呼び出し側でHTTP 500に変換してください。"""
    service, spreadsheet_id = _ensure_sheets_service()

    pdf_path = _find_latest_inventory_pdf_from_gmail()
    # 実行優先度: Vercel or FORCE_GEMINI=1 → Gemini優先、それ以外はローカル優先
    prefer_gemini = bool(os.environ.get('VERCEL')) or os.environ.get('FORCE_GEMINI') == '1'

    rows: List[List[Any]]
    if prefer_gemini:
        try:
            rows = _extract_table_with_gemini(pdf_path)
        except Exception:
            # Gemini失敗時はローカルにフォールバック
            rows = _extract_table_locally(pdf_path)
    else:
        try:
            rows = _extract_table_locally(pdf_path)
        except Exception:
            rows = _extract_table_with_gemini(pdf_path)

    title = _fmt_report_sheet_title()
    _sheets_create_sheet_if_not_exists(service, spreadsheet_id, title)
    _sheets_write_rows(service, spreadsheet_id, title, rows)
    _sheets_update_stock_formulas(service, spreadsheet_id, title)

    try:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
    except Exception:
        pass

    return {
        'ok': True,
        'sheet': title,
        'wrote_rows': len(rows),
    }


