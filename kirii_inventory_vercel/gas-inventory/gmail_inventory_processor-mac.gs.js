/**
 * Gmail Inventory PDF Processor with Gemini AI (Gmail Trigger Version)
 * Gmail受信トリガー版 - メールを受信したら自動的に処理を開始
 * gas_with_python_api.gsのパターンに倣って実装
 * 
 * 変更点:
 * - main() → onGmailReceived() に変更
 * - 時間チェック機能を削除
 * - 前回処理日時管理機能を追加（重複処理防止）
 * - setupTriggers() をGmailトリガー設定に変更
 * - 429/503エラー通知の改善: リトライで成功した場合は通知を送らない（全てのリトライが失敗した場合のみ通知）
 *
 * - 原因1: onGmailReceived 内で時間トリガーを自動作成していたため、トリガー削除後も実行1回で復活・重複しやすかった。
 *   → 対策: トリガー作成は setupGmailTrigger / restoreNormalOperationAfterEmergency のみ（本体ハンドラ内では作らない）。
 * - 原因2: 同一 onGmailReceived の時限トリガーが複数残ると、間隔どおりに並列実行が積み上がる。
 *   → 対策: ensureBackupTimeTrigger で複数検出時に整理し1件にする。
 * - 原因3: 送信した通知メール等が has:attachment + 件名キーワードで検索に掛かり、Gmail トリガーが再発火することがある。
 *   → 対策: buildGmailQuery で -from:実行アカウント（CONFIG.EXCLUDE_SELF_FROM_INVENTORY_GMAIL_QUERY で無効可）。
 */

// 設定定数
const CONFIG = {
  // モデルコードは公式一覧に合わせる（プレビューは変更・終了の通知あり）
  GEMINI_MODEL: 'gemini-3.1-flash-lite-preview',
  // Geminiを使わずにOCRのみで処理する場合は true（429 が止まらないときは true を推奨）
  FORCE_OCR_ONLY: false,
  /** マルチパス間の待機(ms)。RPM 制限で 429 が続く場合は 120000〜180000 へ */
  GEMINI_INTER_PASS_DELAY_MS: 120000,
  /** 不足コード救済で、追いの Gemini の前に Drive OCR を試す（429 削減） */
  GEMINI_RESCUE_TRY_OCR_FIRST: true,
  /**
   * true: PDF 全ページを 1 回の Gemini で尽くす（長い帳票では P4 以降の行ずれ・欠落が起きやすい）
   * false: ページ帯のマルチパス（＋下記拡張帯）を優先（推奨）
   */
  FULL_PDF_SINGLE_GEMINI_PASS: false,
  /**
   * マルチパス（6–8 ページまで）のあと、さらに読むページ帯。長い PDF 用。
   * 各帯の前に GEMINI_INTER_PASS_DELAY_MS の待機が入るため、多数指定すると実行時間上限に触れやすい。
   */
  GEMINI_EXTRA_PAGE_RANGE_PASSES: [],
  /**
   * true: 統合後に「Z-MK など不足コード」だけを追いかける追撃 Gemini/OCR を使う
   * false: PDF に載っている行を一括抽出した結果のみを使う（指定コードリストに依存しない）
   */
  GEMINI_TARGETED_CODE_RESCUE: false,
  /** true: 前回成功行数からの乖離で保存を中止する */
  ENABLE_ROW_COUNT_STABILITY_CHECK: false,
  SCRIPT_VERSION: '2026-05-04-single-file-merge',
  SHEET_ID: '1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M',
  GMAIL_ADDRESS: 'bestinksalesman@gmail.com',
  // 重大エラー通知の宛先（カンマ区切り）。未設定時は GMAIL_ADDRESS を使用
  ALERT_EMAILS: 'bestinksalesman@gmail.com',
  INVENTORY_SUMMARY_SHEET_NAME: 'InventorySummaryReport',
  SEARCH_QUERY: 'subject:inventory has:attachment filename:inventory.pdf',
  // メール条件（件名に含まれるキーワード）
  EMAIL_CONDITIONS: ['inventory', 'stock', '在庫', 'データ'],
  // 0: 行数下限チェックなし（PDFの内容をそのまま反映する運用）
  MIN_EXPECTED_ROWS: 0,
  REQUIRED_CODES: [
    // Tee-Bar (MK -15)
    'TNMA1532M3000MK', 'TNMC1525M0600MK', 'TNMC1525M1200MK',
    // Tee-Bar (MK -24)
    'TNIA2432I0800MK', 'TNIA2432I1000MK', 'TNIC2425I0200MK', 'TNIC2425I0400MK',
    'TNIL2025I0800MK', 'TNIL2025I1000MK', 'TNMA2432M2400MK', 'TNMA2432M3000H200MK',
    'TNMA2432M3000H500MK', 'TNMA2432M3000MK', 'TNMC2425M0500MK', 'TNMC2425M0600MK',
    'TNMC2425M1000MK', 'TNMC2425M1200MK',
    // Tee-Bar (New Colour)
    'TNIW2020I1000N1',
    // SCREW（代表コード — OCR 救済用）
    'SW-002', 'SW-003', 'SW-003B', 'SW-005', 'SW-008', 'SW-009', 'SW-009B', 'SW-010',
    'SW-011', 'SW-012', 'SW-018', 'SW-020', 'SW-028', 'SW-030', 'SW-031', 'SW-032',
    'SW-033', 'SW-039C', 'SW-039S', 'SW-040B', 'SW-041', 'SW-044', 'SW-048', 'SW-049',
    'SW-050', 'SW-063', 'SW-065', 'SW-068'
  ],
  REQUIRED_CODE_EXPECTED_VALUES: {},
  STRICT_REQUIRED_CODES: false,
  // 同一指紋・同一バージョンでも再処理する（手動再実行用）
  ALLOW_REPROCESS_SAME_MESSAGE: false,
  // 同一運用での件数急変は異常として扱う（429/OCRフォールバック時は一時的に行数が減るため緩め）
  MAX_ROW_DRIFT_PERCENT: 28,
  MAX_ROW_DRIFT_ABS: 70,
  /**
   * true: 検索クエリに -from:実行アカウント を付与（自身の送信が検索に入り Gmail トリガー連鎖するのを防ぐ）
   * false: 在庫PDFが必ず自分のアドレスから届く運用のみ
   */
  EXCLUDE_SELF_FROM_INVENTORY_GMAIL_QUERY: true,
  // Gmail受信トリガーの取りこぼし対策（分単位ポーリング）。0=時限バックアップ無効（無限実行に見える連続実行を抑える）
  BACKUP_POLLING_MINUTES: 30,
  // PDFメタデータ時刻抽出は補助機能（429多発時は無効推奨）
  USE_GEMINI_PDF_METADATA_TIME: false,
  /** PDF表頭の Date : (DD/MM/YYYY) が香港の実行当日と一致する場合のみ更新（古い添付の再処理防止） */
  REQUIRE_INVENTORY_PDF_HEADER_DATE_MATCH: true,
  /** PDF表頭 Time : と SLOT1-3（朝・昼・夜）を照合。実行がスロット外なら照合スキップ */
  REQUIRE_INVENTORY_PDF_HEADER_SLOT_MATCH: true,
  /** 表頭は先に Drive OCR（Gemini へ PDF を送らず UrlFetch 帯域を節約。Drive 一時障害時は後段で再試行） */
  HEADER_EXTRACT_OCR_FIRST: true,
  /** 表頭が取得できず、メール受信日時(香港)の日付が実行当日と一致する場合のみ、その日時で照合を継続 */
  HEADER_DATE_FALLBACK_EMAIL_RECEIVED_HK: true,
  /** メール受信日(香港)が実行当日かつ OCR で Date 未取得なら、Gemini 表頭（429 で数分待ち）を省略してメールフォールバックへ */
  SKIP_LONG_GEMINI_HEADER_WHEN_EMAIL_TODAY: true,
  // Inventory PDF Time (HK same day): 6:00-9:00, 12:00-13:30, 17:30-19:30 (inclusive)
  SLOT1_START_HOUR: 6,
  SLOT1_START_MINUTE: 0,
  SLOT1_END_HOUR: 9,
  SLOT1_END_MINUTE: 0,
  SLOT2_START_HOUR: 12,
  SLOT2_START_MINUTE: 0,
  SLOT2_END_HOUR: 13,
  SLOT2_END_MINUTE: 30,
  SLOT3_START_HOUR: 17,
  SLOT3_START_MINUTE: 30,
  SLOT3_END_HOUR: 19,
  SLOT3_END_MINUTE: 30,
  // 限定公開シート対応設定
  USE_PRIVATE_SHEET: true, // 限定公開シート使用フラグ
  SHEET_ACCESS_METHOD: 'direct' // 直接アクセス方法
};

/** 0 のときのみ時限バックアップ無効。未設定時は 30 分 */
function getBackupPollingMinutes() {
  const v = CONFIG.BACKUP_POLLING_MINUTES;
  if (v === 0 || v === '0') return 0;
  const n = Number(v);
  return !isNaN(n) && n > 0 ? n : 30;
}

/** PDF\u8868\u982d\u30fb\u30b9\u30ed\u30c3\u30c8\u7167\u5408\u3067\u5f3e\u304b\u308c\u305f\u5931\u6557\uff08\u518d\u8a66\u884c\u3057\u3066\u3082\u540c\u4e00\u30e1\u30fc\u30eb\u3067\u306f\u6539\u5584\u3057\u306a\u3044\uff09 */
const PDF_INTEGRITY_FAILURE_REASONS = ['PDF_DATE_MISMATCH', 'PDF_TIME_SLOT_MISMATCH', 'PDF_TIME_SLOT_UNKNOWN'];
const SCRIPT_PROP_LAST_PDF_INTEGRITY_NOTIFY_DEDUP = 'LAST_PDF_INTEGRITY_NOTIFY_DEDUP_V1';

// Script Properties から機密値を取得（未設定時はエラー）
function getGeminiApiKey() {
  const props = PropertiesService.getScriptProperties();
  const key = props.getProperty('GEMINI_API_KEY');
  if (key && key.trim()) {
    return key.trim();
  }
  throw new Error('GEMINI_API_KEY is not set in Script Properties. Set it in Project Settings → Script Properties.');
}

/**
 * 実際に呼ぶモデル ID。スクリプト プロパティ GEMINI_MODEL があればそれを優先（クラウドのコードが古くてもここだけ更新可）
 */
function getEffectiveGeminiModelId() {
  const props = PropertiesService.getScriptProperties();
  const o = (props.getProperty('GEMINI_MODEL') || '').trim();
  if (o) return o;
  return CONFIG.GEMINI_MODEL;
}

/**
 * API キーはクエリに付けないこと。UrlFetch 失敗時、例外メッセージにリクエスト URL が含まれ key がログに漏れる。
 * @see https://ai.google.dev/api/rest
 */
function getGeminiGenerateContentUrl() {
  const id = getEffectiveGeminiModelId();
  return 'https://generativelanguage.googleapis.com/v1beta/models/' + id + ':generateContent';
}

function geminiApiHeaders(apiKey) {
  return {
    'Content-Type': 'application/json',
    'x-goog-api-key': apiKey
  };
}

/** ログ・通知文からキーっぽい文字列を除去 */
function getGeminiInterPassDelayMs() {
  const n = Number(CONFIG.GEMINI_INTER_PASS_DELAY_MS);
  return n >= 0 ? n : 120000;
}

function redactForLog(x) {
  const s =
    x == null
      ? ''
      : typeof x === 'string'
        ? x
        : x && x.message
          ? String(x.message)
          : String(x);
  return String(s)
    .replace(/([?&])key=[^&\s"'<>]+/gi, '$1key=[REDACTED]')
    .replace(/\bAIzaSy[A-Za-z0-9_\-]{10,}\b/g, '[REDACTED_API_KEY]');
}

// アラート送信先の取得
function getAlertRecipients() {
  try {
    const list = (CONFIG.ALERT_EMAILS || CONFIG.GMAIL_ADDRESS || '').split(',').map(s => s.trim()).filter(Boolean);
    return list.length ? list : [CONFIG.GMAIL_ADDRESS];
  } catch (_e) {
    return [CONFIG.GMAIL_ADDRESS];
  }
}

/** 香港の現在時刻を HH:MM:SS（24h）で返す */
function getHongKongTimeHmsString() {
  const hk = getHongKongNow();
  const p = n => String(n).padStart(2, '0');
  return p(hk.getHours()) + ':' + p(hk.getMinutes()) + ':' + p(hk.getSeconds());
}

function inventorySlotLabel(index) {
  if (index == null) return '\u30b9\u30ed\u30c3\u30c8\u5916';
  const names = { 1: '\u671d', 2: '\u663c', 3: '\u591c' };
  return (names[index] || '?') + '(' + index + ')';
}

/**
 * 完了/メール用の照合情報ベース（PDF取得後に呼ぶ）
 */
function buildIntegrityAuditBase(latestMessage, pdfBlob) {
  const recv = formatDateTimeInHK(latestMessage.getDate());
  const runSlot = getHkNowInventorySlotIndex();
  return {
    pdfFileName: pdfBlob ? pdfBlob.getName() : '',
    emailSubject: latestMessage.getSubject(),
    emailReceivedDateTimeHK: recv.dateTimeLabel,
    pdfHeaderDate: null,
    pdfHeaderTime: null,
    hkRunDate: getHongKongTodayDdMmYyyy(),
    hkRunTime: getHongKongTimeHmsString(),
    hkRunSlotIndex: runSlot,
    hkRunSlotLabel: inventorySlotLabel(runSlot),
    pdfSlotIndex: null,
    pdfSlotLabel: '-',
    dateMatch: null,
    slotMatch: null,
    slotCheckSkipped: false,
    integrityOk: false,
    integrityFailureReason: ''
  };
}

function formatIntegrityAuditSectionForEmail(audit) {
  if (!audit) return '';
  const yn = function (v) {
    if (v === true) return '\u306f\u3044';
    if (v === false) return '\u3044\u3044\u3048';
    return '\u2014';
  };
  const slotLine =
    audit.slotCheckSkipped === true
      ? '\u30b9\u30ed\u30c3\u30c8\u7167\u5408: \u5b9f\u884c\u304c\u30b9\u30ed\u30c3\u30c8\u5916\u306e\u305f\u3081\u7167\u5408\u30b9\u30ad\u30c3\u30d7'
      : '\u30b9\u30ed\u30c3\u30c8\u4e00\u81f4: ' + yn(audit.slotMatch) + ' (\u5b9f\u884c' + (audit.hkRunSlotLabel || '-') + ' / PDF ' + (audit.pdfSlotLabel || '-') + ')';
  return `
\u25a0 \u53d7\u4fe1PDF\u3068\u5b9f\u884c\u7167\u5408
- \u30e1\u30fc\u30eb\u53d7\u4fe1(\u9999\u6e2f\u8868\u793a): ${audit.emailReceivedDateTimeHK || '-'}
- PDF\u30d5\u30a1\u30a4\u30eb\u540d: ${audit.pdfFileName || '-'}
- PDF\u8868\u982d \u671f\u65e5(Date): ${audit.pdfHeaderDate || '-'}
- PDF\u8868\u982d \u6642\u523b(Time): ${audit.pdfHeaderTime || '-'}
- \u5b9f\u884c\u57fa\u6e96 \u5f53\u65e5(\u9999\u6e2f DD/MM/YYYY): ${audit.hkRunDate || '-'}
- \u5b9f\u884c\u57fa\u6e96 \u6642\u523b(\u9999\u6e2f): ${audit.hkRunTime || '-'}
- ${slotLine}
- \u65e5\u4ed8\u4e00\u81f4: ${yn(audit.dateMatch)}
- \u7167\u5408\u307e\u3068\u3081: ${audit.integrityOk ? '\u554f\u984c\u306a\u3057' : '\u8981\u78ba\u8a8d\uff08\u65e5\u4ed8\u307e\u305f\u306f\u5e2f\u304c\u4e00\u81f4\u3057\u306a\u3044\u53ef\u80fd\uff09'}
- \u51e6\u7406\u5bfe\u8c61: \u53d7\u4fe1\u30e1\u30fc\u30eb\u306e\u6dfb\u4ed8PDF\u3092\u305d\u306e\u307e\u307e\u89e3\u6790\u30fbSheets\u53cd\u6620
${audit.checkNote ? '- NOTE: ' + audit.checkNote : ''}
`;
}

function buildPdfIntegrityNotifyDedupeKey(executionResult) {
  const reason = (executionResult && executionResult.failureReason) || '';
  const fp = executionResult && executionResult.messageFingerprint;
  if (fp) return reason + '|' + fp;
  const a = executionResult && executionResult.integrityAudit;
  if (a) {
    return (
      reason +
      '|' +
      (a.emailSubject || '') +
      '|' +
      (a.pdfFileName || '') +
      '|' +
      String(a.pdfHeaderDate || '') +
      '|' +
      String(a.pdfHeaderTime || '')
    );
  }
  return reason + '|_unknown_';
}

/** PDF\u304c\u6700\u65b0\u3067\u306a\u3044\u53ef\u80fd\u6027\uff08\u65e5\u4ed8/\u30b9\u30ed\u30c3\u30c8\u4e0d\u4e00\u81f4\u7b49\uff09 */
function sendPdfIntegrityFailureNotification(executionResult) {
  try {
    const dedupeKey = buildPdfIntegrityNotifyDedupeKey(executionResult);
    const props = PropertiesService.getScriptProperties();
    const prevDedupe = props.getProperty(SCRIPT_PROP_LAST_PDF_INTEGRITY_NOTIFY_DEDUP);
    if (prevDedupe === dedupeKey) {
      console.log('PDF\u7167\u5408\u91cd\u8981\u901a\u77e5: \u540c\u4e00\u4e8b\u8c61\u306e\u305f\u3081\u9001\u4fe1\u30b9\u30ad\u30c3\u30d7');
      return;
    }

    const audit = executionResult && executionResult.integrityAudit;
    const hongKongTime = getHongKongNow();
    const completionTime = hongKongTime.toLocaleString('ja-JP');
    const subject =
      '\uff01\u30d5\u30a1\u30a4\u30eb\u304c\u6700\u65b0\u306e\u3082\u306e\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044 - GAS\u5728\u5eab';
    const reason = (executionResult && executionResult.failureReason) || '';
    const body =
      '\u5728\u5eab\u51e6\u7406\u3092\u30b9\u30ad\u30c3\u30d7\u3057\u307e\u3057\u305f\uff08PDF\u8868\u982d\u3068\u5b9f\u884c\u65e5\u6642\u306e\u7167\u5408\u3067\u4e0d\u6574\u5408\uff09\u3002\n\n' +
      '\u767a\u751f\u6642\u523b(HK): ' +
      completionTime +
      '\n\u533a\u5206: ' +
      reason +
      '\n' +
      formatIntegrityAuditSectionForEmail(audit) +
      '\n\uff01\u30d5\u30a1\u30a4\u30eb\u304c\u6700\u65b0\u306e\u3082\u306e\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002\n';
    const recipients = getAlertRecipients();
    recipients.forEach(function (to) {
      GmailApp.sendEmail(to, subject, body);
    });
    props.setProperty(SCRIPT_PROP_LAST_PDF_INTEGRITY_NOTIFY_DEDUP, dedupeKey);
    console.log('\u2705 PDF\u7167\u5408\u4e0d\u6b63\u901a\u77e5\u3092\u9001\u4fe1\u3057\u307e\u3057\u305f');
  } catch (e) {
    console.error('sendPdfIntegrityFailureNotification failed:', e);
  }
}

// 重大エラー通知（即時送信）
function sendCriticalErrorNotification(error, context) {
  try {
    const now = new Date();
    const hk = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
    // タイトルに状況を反映
    const msg = (error && error.message) || '';
    let code = '';
    let kind = '例外';
    const m1 = msg.match(/Gemini API[^0-9]*?(\d{3})/);
    const m2 = msg.match(/エラーを返しました:\s*(\d{3})/);
    code = (m1 && m1[1]) || (m2 && m2[1]) || '';
    if (context && String(context).toLowerCase().indexOf('gemini') >= 0) {
      kind = 'Gemini API';
    }
    const labelMap = { '401': '認証エラー', '403': '認可エラー', '429': 'レート制限', '503': 'サービス一時停止' };
    const label = code ? (labelMap[code] || `エラー ${code}`) : '実行エラー';
    const subject = `【重大${code ? '/' + code : ''}】${label} – ${kind} – Gmail Inventory Processor`;
    const safeMsg = redactForLog((error && error.message) || String(error));
    const safeStack = redactForLog((error && error.stack) || '');
    const body =
`重大エラーが発生しました。\n\n発生時刻(HK): ${hk.toLocaleString('ja-JP')}\nコンテキスト: ${context || '-'}\n\nメッセージ:\n${safeMsg}\n\nスタックトレース:\n${safeStack}`;
    const recipients = getAlertRecipients();
    recipients.forEach(to => GmailApp.sendEmail(to, subject, body));
  } catch (e) {
    console.error('重大エラー通知の送信に失敗:', e);
  }
}

/**
 * 限定公開シートにアクセスするためのヘルパー関数
 * 同じGoogleアカウントで所有しているシートにアクセス
 */
function getPrivateSpreadsheet() {
  try {
    console.log('限定公開シートにアクセス中...');
    
    // 方法1: 直接IDでアクセス（同じアカウントで所有している場合）
    if (CONFIG.USE_PRIVATE_SHEET) {
      try {
        const spreadsheet = SpreadsheetApp.openById(CONFIG.SHEET_ID);
        console.log('✅ 限定公開シートにアクセス成功');
        return spreadsheet;
      } catch (error) {
        console.error('❌ 限定公開シートへのアクセスに失敗:', error);
        throw new Error(`限定公開シートへのアクセスに失敗しました: ${error.message}`);
      }
    }
    
    // フォールバック: 通常のアクセス方法
    return SpreadsheetApp.openById(CONFIG.SHEET_ID);
    
  } catch (error) {
    console.error('スプレッドシートアクセスエラー:', error);
    throw error;
  }
}

/**
 * 限定公開シートのシートを取得
 */
function getPrivateSheet(sheetName) {
  try {
    const spreadsheet = getPrivateSpreadsheet();
    const sheet = spreadsheet.getSheetByName(sheetName);
    
    if (!sheet) {
      throw new Error(`シート「${sheetName}」が見つかりません`);
    }
    
    console.log(`✅ 限定公開シート「${sheetName}」を取得しました`);
    return sheet;
    
  } catch (error) {
    console.error('シート取得エラー:', error);
    throw error;
  }
}

/**
 * Gmailトリガー関数
 * 前回処理したメールの日時より新しいメールの最新1件のみを処理
 * 緊急停止・復旧はこのファイル末尾の emergencyStopOn / deleteAllTriggersNow など
 */
function onGmailReceived() {
  let processedEmail = null;
  let executionResult = { success: false, error: null, processedEmail: null, summary: null, failureReason: '' };
  const lock = LockService.getScriptLock();
  let lockAcquired = false;
  
  try {
    if (shouldEmergencyExitInventory()) {
      console.log('緊急停止中のため onGmailReceived を終了（解除: emergencyStopOff）');
      return;
    }
    console.log('=== Gmailトリガー処理開始 ===');
    console.log('[ビルド確認] SCRIPT_VERSION=' + CONFIG.SCRIPT_VERSION + ' 使用Gemini=' + getEffectiveGeminiModelId());
    // 同時実行による競合更新を防止
    lockAcquired = lock.tryLock(5000);
    if (!lockAcquired) {
      console.log('別実行が動作中のため、今回の実行をスキップします');
      recordStabilityEvent('SKIP_LOCKED', 'Another execution is active');
      return;
    }
    // 注意: ここで ScriptApp でトリガーを自動作成しないこと（削除しても実行一回で復活させていた）
    
    // 前回処理情報を取得
    const lastProcessedTime = getLastProcessedTime();
    const lastProcessedFingerprint = getLastProcessedFingerprint();
    const lastProcessedScriptVersion = getLastProcessedScriptVersion();
    console.log(`前回処理日時: ${lastProcessedTime ? new Date(lastProcessedTime).toLocaleString('ja-JP') : 'なし（初回実行）'}`);
    console.log(`前回処理指紋: ${lastProcessedFingerprint ? 'あり' : 'なし'}`);
    console.log(`前回処理バージョン: ${lastProcessedScriptVersion || 'なし'}`);
    
    // Gmail検索クエリを構築
    const query = buildGmailQuery();
    const threads = GmailApp.search(query, 0, 50);
    
    console.log(`${threads.length}件のスレッドが見つかりました`);
    
    if (threads.length === 0) {
      console.log('条件に合致するメールが見つかりませんでした');
      recordStabilityEvent('NO_MATCHING_EMAIL', 'No thread matched Gmail query');
      console.log('=== Gmailトリガー処理完了（メール未発見） ===');
      return;
    }
    
    // スレッドを日時順にソート（新しい順）
    // 重要: スレッド内の最新メッセージの日時を使用
    const sortedThreads = threads.sort((a, b) => {
      const messagesA = a.getMessages();
      const messagesB = b.getMessages();
      const timeA = messagesA.length > 0 ? messagesA[messagesA.length - 1].getDate().getTime() : a.getLastMessageDate().getTime();
      const timeB = messagesB.length > 0 ? messagesB[messagesB.length - 1].getDate().getTime() : b.getLastMessageDate().getTime();
      return timeB - timeA;
    });
    
    // デバッグ: 最新5件のスレッドの日時を確認
    console.log('=== デバッグ: 最新5件のスレッド日時 ===');
    for (let i = 0; i < Math.min(5, sortedThreads.length); i++) {
      const thread = sortedThreads[i];
      const messages = thread.getMessages();
      // スレッド内の最新メッセージの日時を使用
      const latestMessage = messages.length > 0 ? messages[messages.length - 1] : null;
      const threadTime = latestMessage ? latestMessage.getDate().getTime() : thread.getLastMessageDate().getTime();
      const threadDate = new Date(threadTime);
      console.log(`${i + 1}. ${thread.getFirstMessageSubject()}: ${threadDate.toLocaleString('ja-JP')} (${threadTime})`);
      if (latestMessage) {
        console.log(`   メッセージ日時: ${latestMessage.getDate().toLocaleString('ja-JP')} (${latestMessage.getDate().getTime()})`);
      }
    }
    
    // 常に最新の1件を処理（重複判定は指紋で実施）
    const latestThread = sortedThreads[0];
    const latestMessages = latestThread.getMessages();
    const latestMessage = latestMessages.length > 0 ? latestMessages[latestMessages.length - 1] : null;
    const threadTime = latestMessage ? latestMessage.getDate().getTime() : latestThread.getLastMessageDate().getTime();
    const threadDate = new Date(threadTime);
    const latestFingerprint = buildMessageFingerprint(latestMessage);
    
    console.log(`処理対象: ${latestThread.getFirstMessageSubject()} (${threadDate.toLocaleString('ja-JP')}) [前回: ${lastProcessedTime ? new Date(lastProcessedTime).toLocaleString('ja-JP') : 'なし'}]`);
    console.log(`処理対象メッセージ日時: ${latestMessage ? latestMessage.getDate().toLocaleString('ja-JP') + ' (' + latestMessage.getDate().getTime() + ')' : 'なし'}`);
    if (latestFingerprint && latestFingerprint === lastProcessedFingerprint) {
      if (lastProcessedScriptVersion === CONFIG.SCRIPT_VERSION && !CONFIG.ALLOW_REPROCESS_SAME_MESSAGE) {
        console.log('前回と同一メール（同一指紋）かつ同一バージョンのため処理をスキップします');
        recordStabilityEvent('SKIP_DUPLICATE', 'Same message fingerprint and same script version');
        console.log('=== Gmailトリガー処理完了（重複スキップ） ===');
        return;
      }
      if (lastProcessedScriptVersion === CONFIG.SCRIPT_VERSION && CONFIG.ALLOW_REPROCESS_SAME_MESSAGE) {
        console.log('同一メール・同一バージョンですが再処理設定が有効のため処理を継続します');
      } else {
        console.log(`同一メールですがスクリプト更新を検知 (${lastProcessedScriptVersion} -> ${CONFIG.SCRIPT_VERSION})。再処理します`);
      }
    }
    
    // メールを処理
    const result = processInventoryThread(latestThread);
    
    if (result && result.success) {
      executionResult = { 
        success: true, 
        error: null, 
        processedEmail: result.processedEmail, 
        summary: result.summary, 
        failureReason: '',
        processedCount: result.processedCount || 0,
        skippedCount: result.skippedCount || 0,
        integrityAudit: result.integrityAudit
      };
      processedEmail = result.processedEmail;
      // 成功時のみ処理日時を保存（失敗時に再処理不能になる事故を防止）
      saveLastProcessedTime(threadTime);
      saveLastProcessedFingerprint(latestFingerprint);
      saveLastProcessedScriptVersion(CONFIG.SCRIPT_VERSION);
      recordStabilityEvent('SUCCESS', `Processed rows: ${executionResult.processedCount || 0}`);
      console.log(`✓ 処理日時を保存（成功後）: ${new Date(threadTime).toLocaleString('ja-JP')} (${threadTime})`);
      
      // Stock式設定も実行（1回のみ）
      console.log('=== 在庫メール処理完了、Stock式設定開始 ===');
      setStockFormulas();
    } else {
      console.log('=== メール処理が完了しませんでした、Stock式設定をスキップ ===');
      executionResult = { 
        success: false, 
        error: result?.error || new Error('処理に失敗しました'), 
        processedEmail: null, 
        summary: null, 
        failureReason: result?.failureReason || 'PROCESS_ERROR',
        integrityAudit: result?.integrityAudit,
        messageFingerprint: latestFingerprint
      };
      if (PDF_INTEGRITY_FAILURE_REASONS.indexOf(executionResult.failureReason) >= 0) {
        saveLastProcessedTime(threadTime);
        saveLastProcessedFingerprint(latestFingerprint);
        saveLastProcessedScriptVersion(CONFIG.SCRIPT_VERSION);
        console.log('PDF\u7167\u5408\u4e0d\u4e00\u81f4: \u30dd\u30fc\u30ea\u30f3\u30b0\u3067\u306e\u518d\u51e6\u7406\u30fb\u901a\u77e5\u591a\u767a\u3092\u9632\u3050\u305f\u3081\u6307\u7d0b\u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f\uff08Sheets\u306f\u672a\u66f4\u65b0\uff09');
      }
    }
    
    // Gemini API失敗時でもInventorySummaryReport!F2の設定を実行
    console.log('=== InventorySummaryReport!F2設定を強制実行 ===');
    setInventorySummaryReportFormula();
    
    console.log('=== Gmailトリガー処理完了 ===');
    
    if (!executionResult.success && PDF_INTEGRITY_FAILURE_REASONS.indexOf(executionResult.failureReason) >= 0) {
      console.log('=== PDF照合不一致のため重要通知メール送信 ===');
      sendPdfIntegrityFailureNotification(executionResult);
    } else if (executionResult.success && (executionResult.processedCount || 0) > 0) {
      console.log('=== 作業終了メール送信開始 ===');
      console.log(`処理結果: ${executionResult.success ? '成功' : '失敗'}`);
      sendCompletionNotification(executionResult);
      console.log('=== 作業終了メール送信完了 ===');
    } else {
      console.log('作業終了メールは送信しません（更新なし、または失敗）');
    }
    
    // 明示的に処理完了をログに記録
    console.log('✅ Gmailトリガー処理が正常に完了しました');
    return; // 明示的なreturnを追加
    
  } catch (error) {
    console.error('Gmailトリガー処理でエラーが発生しました:', redactForLog(error));
    recordStabilityEvent('ERROR', redactForLog((error && error.message) || String(error)));
    const contextInfo = { failureReason: 'GMAIL_TRIGGER_EXCEPTION', processedEmail, additionalInfo: 'onGmailReceived() で捕捉された例外です。' };
    sendCriticalErrorNotification(error, 'onGmailReceived()');
    sendErrorNotification(error, contextInfo);
    console.log('❌ Gmailトリガー処理がエラーで終了しました');
    // エラー時も明示的にreturn（throwしない）
    return;
  } finally {
    if (lockAcquired) {
      lock.releaseLock();
    }
  }
}

/**
 * Gmail検索クエリ構築
 */
function getScriptUserEmailForGmailQuery() {
  try {
    return Session.getEffectiveUser().getEmail() || '';
  } catch (_e) {
    return '';
  }
}

function buildGmailQuery() {
  // 在庫メールの検索クエリ
  let query = 'has:attachment';
  
  // 件名の条件を追加
  const subjectConditions = CONFIG.EMAIL_CONDITIONS.map(keyword => `subject:${keyword}`).join(' OR ');
  query += ` (${subjectConditions})`;
  
  // PDFファイルの条件を追加
  query += ' filename:pdf';

  // 自分が送信した完了通知などが添付付きで検索に引っかかると Gmail トリガー連鎖の原因になるため除外（要らなければ CONFIG で false）
  if (CONFIG.EXCLUDE_SELF_FROM_INVENTORY_GMAIL_QUERY !== false) {
    const selfAddr = getScriptUserEmailForGmailQuery();
    if (selfAddr) {
      query += ' -from:' + selfAddr.replace(/"/g, '');
    }
  }

  console.log(`Gmail検索クエリ: ${query}`);
  return query;
}

/**
 * スレッドを処理（在庫メール処理）
 * @param {GmailThread} thread - 処理するGmailスレッド
 * @return {Object} 処理結果 {success: boolean, error?: string, threadTime?: number}
 */
function processInventoryThread(thread) {
  const messages = thread.getMessages();
  
  // スレッドの最新メッセージの日時を取得（処理済み判定に使用）
  const threadTime = thread.getLastMessageDate().getTime();
  
  // スレッド内の最新メッセージを取得
  const latestMessage = messages[messages.length - 1];
  
   try {
    // PDF添付ファイルを取得
    const pdfBlob = getPdfAttachment(latestMessage);
    if (!pdfBlob) {
      console.log(`PDF添付ファイルが見つかりませんでした`);
      return {success: false, error: 'PDF添付ファイルが見つかりませんでした', failureReason: 'NO_PDF_ATTACHMENT'};
    }

    const integrityAudit = buildIntegrityAuditBase(latestMessage, pdfBlob);
    let headerDateRaw = null;
    let headerTimeRaw = null;
    let skipHeaderSlotMatchBecauseEmailFallback = false;

    if (CONFIG.REQUIRE_INVENTORY_PDF_HEADER_DATE_MATCH) {
      const runDate = getHongKongTodayDdMmYyyy();
      let header = null;
      if (CONFIG.SKIP_LONG_GEMINI_HEADER_WHEN_EMAIL_TODAY !== false) {
        const emailDayPre = getDdMmYyyyInHongKong(latestMessage.getDate());
        const en = normalizeDdMmYyyy(emailDayPre);
        const rn = normalizeDdMmYyyy(runDate);
        if (en && rn && en === rn) {
          try {
            const ocrOnly = extractInventoryReportHeaderDateTimeFromOcr(pdfBlob);
            if (ocrOnly && ocrOnly.date) {
              header = { date: ocrOnly.date, time: ocrOnly.time };
              console.log('表頭: 当日メール・OCRで Date 取得成功のため Gemini 表頭呼び出しを省略');
            } else {
              header = { extractionFailed: true };
              console.log(
                '表頭: 当日メール・OCRで Date 未取得 — Gemini 表頭の長時間リトライを省略しメール日時フォールバックへ'
              );
            }
          } catch (ocrShort) {
            console.warn('表頭OCR（当日短絡）: ' + ocrShort);
            header = { extractionFailed: true };
          }
        }
      }
      if (!header) {
        header = extractInventoryReportHeaderDateAndTimeFromPdf(pdfBlob);
      }
      if (header && header.extractionFailed) {
        let recoveredFromEmail = false;
        if (CONFIG.HEADER_DATE_FALLBACK_EMAIL_RECEIVED_HK !== false) {
          const emailDay = getDdMmYyyyInHongKong(latestMessage.getDate());
          const emailNorm = normalizeDdMmYyyy(emailDay);
          const runNorm = normalizeDdMmYyyy(runDate);
          if (emailNorm && runNorm && emailNorm === runNorm) {
            headerDateRaw = emailDay;
            headerTimeRaw = getHmsStringInHongKong(latestMessage.getDate());
            recoveredFromEmail = true;
            skipHeaderSlotMatchBecauseEmailFallback = true;
            integrityAudit.checkNote = 'HEADER_DATE_TIME_FROM_EMAIL_RECEIVED_HK_FALLBACK';
            console.log(
              'PDF表頭未取得 — メール受信日(香港)が実行当日のため照合を継続: ' +
                headerDateRaw +
                ' ' +
                headerTimeRaw
            );
          }
        }
        if (!recoveredFromEmail) {
          console.log(
            'PDF表頭の日時を Gemini・OCR のいずれでも取得できず、メール日フォールバックも使えません（実行日とメール受信日が一致しない、または無効）。'
          );
          integrityAudit.pdfHeaderDate = '-';
          integrityAudit.pdfHeaderTime = '-';
          integrityAudit.dateMatch = null;
          integrityAudit.slotMatch = null;
          integrityAudit.integrityOk = false;
          integrityAudit.integrityFailureReason = 'GEMINI_HEADER_UNAVAILABLE';
          return {
            success: false,
            error: 'PDF header date/time extraction failed (Gemini rate limit or transient error)',
            failureReason: 'GEMINI_HEADER_UNAVAILABLE',
            processedEmail: null,
            summary: null,
            integrityAudit: integrityAudit
          };
        }
      } else {
        headerDateRaw = header && header.date;
        headerTimeRaw = header && header.time;
      }
      const headerDate = headerDateRaw ? normalizeDdMmYyyy(headerDateRaw) : null;
      const runDateNorm = normalizeDdMmYyyy(runDate);
      if (!headerDate || !runDateNorm || headerDate !== runDateNorm) {
        console.log(
          `PDF表頭の期日 "${headerDateRaw}" (正規化: ${headerDate}) が実行日 ${runDateNorm} と一致しません。古いレポートの可能性があるためスキップします。`
        );
        integrityAudit.pdfHeaderDate = headerDateRaw || '-';
        integrityAudit.pdfHeaderTime = headerTimeRaw || '-';
        integrityAudit.dateMatch = false;
        const ps0 = headerTimeRaw ? getPdfTimeInventorySlotIndex(headerTimeRaw) : null;
        integrityAudit.pdfSlotIndex = ps0;
        integrityAudit.pdfSlotLabel = inventorySlotLabel(ps0);
        integrityAudit.slotMatch = null;
        integrityAudit.integrityOk = false;
        integrityAudit.integrityFailureReason = 'PDF_DATE_MISMATCH';
        return {
          success: false,
          error: 'PDF header date does not match HK run date',
          failureReason: 'PDF_DATE_MISMATCH',
          processedEmail: null,
          summary: null,
          integrityAudit: integrityAudit
        };
      }

      if (CONFIG.REQUIRE_INVENTORY_PDF_HEADER_SLOT_MATCH) {
        if (skipHeaderSlotMatchBecauseEmailFallback) {
          console.log(
            '表頭の時刻はメール受信フォールバックのため、在庫スロット照合をスキップします（PDFの Time: 行ではない）'
          );
        } else {
          const slotNames = { 1: String.fromCharCode(0x671d), 2: String.fromCharCode(0x663c), 3: String.fromCharCode(0x591c) };
          const runSlot = getHkNowInventorySlotIndex();
          const pdfSlot = headerTimeRaw ? getPdfTimeInventorySlotIndex(headerTimeRaw) : null;
          if (runSlot != null) {
            if (pdfSlot == null) {
              console.log(
                'PDF time not in any inventory slot: ' + (headerTimeRaw || '')
              );
              integrityAudit.pdfHeaderDate = headerDateRaw || '-';
              integrityAudit.pdfHeaderTime = headerTimeRaw || '-';
              integrityAudit.dateMatch = true;
              integrityAudit.pdfSlotIndex = null;
              integrityAudit.pdfSlotLabel = '\u7121\u52b9(\u30b9\u30ed\u30c3\u30c8\u5916)';
              integrityAudit.slotMatch = false;
              integrityAudit.integrityOk = false;
              integrityAudit.integrityFailureReason = 'PDF_TIME_SLOT_UNKNOWN';
              return {
                success: false,
                error: 'PDF header time is not in any configured inventory slot',
                failureReason: 'PDF_TIME_SLOT_UNKNOWN',
                processedEmail: null,
                summary: null,
                integrityAudit: integrityAudit
              };
            }
            if (pdfSlot !== runSlot) {
              console.log(
                'PDF slot ' + pdfSlot + ' (' + (headerTimeRaw || '') + ') vs run slot ' + runSlot + ' — skip'
              );
              integrityAudit.pdfHeaderDate = headerDateRaw || '-';
              integrityAudit.pdfHeaderTime = headerTimeRaw || '-';
              integrityAudit.dateMatch = true;
              integrityAudit.pdfSlotIndex = pdfSlot;
              integrityAudit.pdfSlotLabel = inventorySlotLabel(pdfSlot);
              integrityAudit.slotMatch = false;
              integrityAudit.integrityOk = false;
              integrityAudit.integrityFailureReason = 'PDF_TIME_SLOT_MISMATCH';
              return {
                success: false,
                error: 'PDF header time slot does not match current run slot (HK)',
                failureReason: 'PDF_TIME_SLOT_MISMATCH',
                processedEmail: null,
                summary: null,
                integrityAudit: integrityAudit
              };
            }
            console.log(
              'PDF ' +
                headerDate +
                ' ' +
                (headerTimeRaw || '') +
                ' slot=' +
                pdfSlot +
                '(' +
                slotNames[pdfSlot] +
                ') matches run — continue'
            );
          } else {
            console.log(
              'PDF date OK; run outside slots, skip slot check (header time: ' + (headerTimeRaw || '-') + ')'
            );
          }
        }
      } else {
        console.log(`PDF期日 ${headerDate} が実行日と一致 — 本解析を続行します。`);
      }

      integrityAudit.pdfHeaderDate = headerDateRaw || '-';
      integrityAudit.pdfHeaderTime = headerTimeRaw || '-';
      integrityAudit.dateMatch = true;
      if (CONFIG.REQUIRE_INVENTORY_PDF_HEADER_SLOT_MATCH) {
        const rs = getHkNowInventorySlotIndex();
        const ps = headerTimeRaw ? getPdfTimeInventorySlotIndex(headerTimeRaw) : null;
        integrityAudit.hkRunSlotIndex = rs;
        integrityAudit.hkRunSlotLabel = inventorySlotLabel(rs);
        if (skipHeaderSlotMatchBecauseEmailFallback) {
          integrityAudit.pdfSlotIndex = null;
          integrityAudit.pdfSlotLabel = '\u2014(\u30e1\u30fc\u30eb\u53d7\u4fe1\u6642\u523b\u30fb\u7167\u5408\u30b9\u30ad\u30c3\u30d7)';
          integrityAudit.slotCheckSkipped = true;
          integrityAudit.slotMatch = null;
        } else {
          integrityAudit.pdfSlotIndex = ps;
          integrityAudit.pdfSlotLabel = inventorySlotLabel(ps);
          if (rs == null) {
            integrityAudit.slotCheckSkipped = true;
            integrityAudit.slotMatch = null;
          } else {
            integrityAudit.slotMatch = true;
            integrityAudit.slotCheckSkipped = false;
          }
        }
      } else {
        integrityAudit.slotMatch = null;
      }
    } else {
      integrityAudit.checkNote = 'REQUIRE_INVENTORY_PDF_HEADER_DATE_MATCH=false';
      integrityAudit.dateMatch = null;
      integrityAudit.slotMatch = null;
    }
    
    console.log(`処理開始: ${pdfBlob.getName()} (スレッド日時: ${new Date(threadTime).toLocaleString('ja-JP')})`);
    
    // Gemini AIでPDFを解析
    const summary = generateSummaryWithGeminiMultiplePasses(pdfBlob, 1);
    
    if (!summary || !summary.trim()) {
      throw new Error('Gemini解析結果が空でした');
    }
    
    // Google Sheetsに保存
    const savedCount = saveToGoogleSheets(summary, latestMessage, 1, pdfBlob);
    
    // メールを既読に
    latestMessage.markRead();
    
    console.log(`✓ 処理完了: ${pdfBlob.getName()}`);
    integrityAudit.integrityOk = true;
    integrityAudit.integrityFailureReason = '';
    return {
      success: true, 
      threadTime: threadTime,
      processedEmail: latestMessage,
      summary: summary,
      processedCount: savedCount || 0,
      skippedCount: 0,
      integrityAudit: integrityAudit
    };
    
  } catch (error) {
    console.error(`✗ 処理エラー: ${error.toString()}`);
    return {
      success: false, 
      error: error, 
      failureReason: 'PROCESS_ERROR',
      processedEmail: null,
      summary: null
    };
  }
}

/**
 * 前回処理した最新のメール日時を取得
 * PropertiesServiceを使用して保存・取得
 */
function getLastProcessedTime() {
  const properties = PropertiesService.getScriptProperties();
  const lastTime = properties.getProperty('LAST_PROCESSED_TIME');
  return lastTime ? parseInt(lastTime, 10) : null;
}

/**
 * 前回処理したメール指紋を取得
 */
function getLastProcessedFingerprint() {
  const properties = PropertiesService.getScriptProperties();
  return properties.getProperty('LAST_PROCESSED_FINGERPRINT') || '';
}

/**
 * 前回処理時のスクリプトバージョンを取得
 */
function getLastProcessedScriptVersion() {
  const properties = PropertiesService.getScriptProperties();
  return properties.getProperty('LAST_PROCESSED_SCRIPT_VERSION') || '';
}

/**
 * 最新の処理日時を保存
 */
function saveLastProcessedTime(timestamp) {
  const properties = PropertiesService.getScriptProperties();
  properties.setProperty('LAST_PROCESSED_TIME', timestamp.toString());
}

/**
 * 最新処理メールの指紋を保存
 */
function saveLastProcessedFingerprint(fingerprint) {
  const properties = PropertiesService.getScriptProperties();
  properties.setProperty('LAST_PROCESSED_FINGERPRINT', fingerprint || '');
}

/**
 * 前回処理時のスクリプトバージョンを保存
 */
function saveLastProcessedScriptVersion(version) {
  const properties = PropertiesService.getScriptProperties();
  properties.setProperty('LAST_PROCESSED_SCRIPT_VERSION', version || '');
}

/**
 * メールの一意指紋を作成（重複防止用）
 */
function buildMessageFingerprint(message) {
  if (!message) return '';
  const messageId = message.getId ? message.getId() : '';
  const ts = message.getDate ? message.getDate().getTime() : 0;
  const subject = message.getSubject ? message.getSubject() : '';
  const pdfAttachment = getPdfAttachment(message);
  const attachmentSig = pdfAttachment
    ? `${pdfAttachment.getName()}|${pdfAttachment.getContentType()}`
    : 'NO_PDF';
  return `${messageId}|${ts}|${subject}|${attachmentSig}`;
}

/**
 * 処理日時のリセット（テスト用）
 */
function resetProcessedTime() {
  const properties = PropertiesService.getScriptProperties();
  properties.deleteProperty('LAST_PROCESSED_TIME');
  properties.deleteProperty('LAST_PROCESSED_FINGERPRINT');
  properties.deleteProperty('LAST_PROCESSED_SCRIPT_VERSION');
  properties.deleteProperty('LAST_STABILITY_EVENT');
  properties.deleteProperty('LAST_SUCCESS_ROW_COUNT');
  properties.deleteProperty(SCRIPT_PROP_LAST_PDF_INTEGRITY_NOTIFY_DEDUP);
  console.log('処理日時をリセットしました');
}

/**
 * 再発調査のために最新の安定性イベントを記録
 */
function recordStabilityEvent(code, detail) {
  try {
    const props = PropertiesService.getScriptProperties();
    const now = new Date();
    const payload = {
      at: now.toISOString(),
      scriptVersion: CONFIG.SCRIPT_VERSION,
      code: code || 'UNKNOWN',
      detail: detail || ''
    };
    props.setProperty('LAST_STABILITY_EVENT', JSON.stringify(payload));
    console.log(`安定性イベント記録: ${payload.code}`);
  } catch (error) {
    console.error('安定性イベント記録エラー:', error);
  }
}

/**
 * シート更新成功時刻を記録（定時ダブルチェック用）
 */
function markSheetUpdated(rowCount) {
  try {
    const props = PropertiesService.getScriptProperties();
    props.setProperty('LAST_SHEET_UPDATE_AT', String(Date.now()));
    props.setProperty('LAST_SHEET_UPDATE_ROWS', String(rowCount || 0));
  } catch (error) {
    console.error('シート更新時刻記録エラー:', error);
  }
}

function getLastSheetUpdateAt() {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('LAST_SHEET_UPDATE_AT');
  return raw ? parseInt(raw, 10) : 0;
}

function getLastSuccessRowCount() {
  const props = PropertiesService.getScriptProperties();
  const raw = props.getProperty('LAST_SUCCESS_ROW_COUNT');
  return raw ? parseInt(raw, 10) : 0;
}

function saveLastSuccessRowCount(count) {
  const props = PropertiesService.getScriptProperties();
  props.setProperty('LAST_SUCCESS_ROW_COUNT', String(count || 0));
}

/**
 * onGmailReceived/main に紐づく時間トリガーを確認（削除しない）
 */
function removeLegacyTimeTriggersForInventory() {
  try {
    const triggers = ScriptApp.getProjectTriggers();
    let clockCount = 0;
    for (const trigger of triggers) {
      const handler = trigger.getHandlerFunction();
      if (handler !== 'onGmailReceived' && handler !== 'main') continue;
      if (trigger.getTriggerSource() === ScriptApp.TriggerSource.CLOCK) {
        clockCount++;
      }
    }
    console.log(`時間主導トリガー数（onGmailReceived/main）: ${clockCount}件`);
  } catch (error) {
    console.error('時間トリガー確認でエラー:', error);
  }
}

/**
 * メール無しの時の通知メールを送信します（Gmailトリガー用）
 */
function sendNoEmailNotificationForGmailTrigger() {
  try {
    const hongKongTime = getHongKongNow();
    const notificationTime = hongKongTime.toLocaleString('ja-JP');

    const subject = 'GASスクリプト「gmail-Inventory-AutoDataFill」メール未発見通知';
    const body = `
在庫データ処理スクリプトを実行しましたが、条件に合致するメールが見当たりませんでした。

通知時刻: ${notificationTime}
検索条件: ${CONFIG.EMAIL_CONDITIONS.join(', ')}

メールが到着次第、自動的に処理を実行します。
処理完了時には改めて完了通知メールをお送りします。
`;

    GmailApp.sendEmail(
      CONFIG.GMAIL_ADDRESS,
      subject,
      body
    );

    console.log('✅ メール未発見通知メールを送信しました');
  } catch (error) {
    console.error('メール未発見通知メールの送信に失敗しました:', error);
  }
}

// ===============================================================
// 以下は元のコードからそのまま引き継ぎ
// ===============================================================

/**
 * メールから 'inventory.pdf' を含むPDF添付ファイルを取得します。
 */
function getPdfAttachment(email) {
  try {
    const attachments = email.getAttachments();
    console.log(`添付ファイル数: ${attachments.length}件`);
    const candidates = [];
    
    for (const attachment of attachments) {
      console.log(`添付ファイル: ${attachment.getName()}, タイプ: ${attachment.getContentType()}`);
      
      // PDFファイルの検出（より柔軟な条件）
      const fileName = attachment.getName().toLowerCase();
      const contentType = attachment.getContentType();
      
      if (contentType === 'application/pdf' || 
          contentType === 'application/octet-stream' ||
          fileName.endsWith('.pdf')) {
        let score = 1;
        if (fileName.includes('inventory')) score += 10;
        if (fileName.includes('stock')) score += 5;
        if (fileName === 'inventory.pdf') score += 20;
        candidates.push({ attachment, score, fileName, contentType });
      }
    }
    if (candidates.length > 0) {
      candidates.sort((a, b) => b.score - a.score);
      const picked = candidates[0].attachment;
      console.log(`PDF添付ファイル発見: ${picked.getName()}, タイプ: ${picked.getContentType()}, サイズ: ${picked.getBytes().length} bytes`);
      return picked;
    }
    
    console.log('該当するPDF添付ファイルが見つかりませんでした');
    return null;
  } catch (error) {
    console.error('PDF添付ファイル取得エラー:', error);
    throw error;
  }
}

/**
 * PDF から在庫表を取得。既定は全ページ一括→失敗時のみ分割読み取り。
 */
function generateSummaryWithGeminiMultiplePasses(pdfBlob, emailIndex = 1) {
  try {
    if (CONFIG.FORCE_OCR_ONLY) {
      console.log('🔁 Geminiを使わずOCRのみで処理します');
      return extractInventoryTableWithoutGemini(pdfBlob);
    }
    console.log(`PDF解析開始 - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);

    if (CONFIG.FULL_PDF_SINGLE_GEMINI_PASS !== false) {
      const fullPdfPrompt = [
        'You are extracting data from an attached multi-page **Inventory Summary Report** PDF.',
        'Read **every page** of the PDF.',
        'Output **every inventory data row** that appears in tables — do not limit to any specific product codes list.',
        'Do not stop early; include rows under section headers (e.g. category names, thickness labels like 0.45mm) — output only real table rows with Product Code and numbers.',
        'Output **only** GitHub-flavored markdown tables.',
        'Each row: | Product Code | Description | On Hand | Quantity SC w/o DN | Available |',
        'Use exactly 5 columns. Preserve commas and negative numbers.',
        'Do not output prose, bullets, or explanations — tables only.'
      ].join('\n');
      const oneShot = generateSummaryWithGeminiSinglePass(pdfBlob, fullPdfPrompt, 1);
      if (oneShot && oneShot.trim()) {
        const tableLines = oneShot.split('\n').filter(function (line) {
          const t = line.trim();
          return t.indexOf('|') >= 0 && t.indexOf('---') < 0;
        });
        if (tableLines.length >= 15) {
          console.log('=== 全ページ一括読み取り完了: ' + tableLines.length + ' テーブル行 ===');
          return oneShot;
        }
        console.warn(
          '全ページ一括のテーブル行が少なすぎるため、分割読み取りへフォールバックします（' +
            tableLines.length +
            ' 行）'
        );
      }
    }

    const allResults = [];
    const requireGeminiPassResult = function (label, result) {
      const lineCount = result && result.trim()
        ? result.split('\n').filter(function (line) {
            return line.indexOf('|') >= 0 && line.indexOf('---') < 0;
          }).length
        : 0;
      if (!result || !result.trim() || lineCount === 0) {
        throw new Error(`${label} のGemini抽出が空です。全ページ必須のため保存を中止します`);
      }
      return lineCount;
    };
    
    // 1回目: 1-3ページ目
    console.log('=== 1回目読み取り: 1-3ページ目 ===');
    const result1 = generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルの1-3ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。

## 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 1-3ページ目の在庫アイテムを漏れなく抽出してください。
- マークダウンテーブルのみを出力してください。
`, 1);
    const result1Lines = requireGeminiPassResult('1-3ページ目', result1);
    allResults.push(result1);
    console.log(`1回目読み取り完了: ${result1Lines}行`);
    
    const passDelay = getGeminiInterPassDelayMs();
    console.log(`⏳ レート制限回避のため ${passDelay / 1000} 秒待機します...`);
    Utilities.sleep(passDelay);
    
    // 2回目: 4-5ページ目
    console.log('=== 2回目読み取り: 4-5ページ目 ===');
    const result2 = generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルの4-5ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。

## 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 4-5ページ目の在庫アイテムを漏れなく抽出してください。
- マークダウンテーブルのみを出力してください。
`, 2);
    const result2Lines = requireGeminiPassResult('4-5ページ目', result2);
    allResults.push(result2);
    console.log(`2回目読み取り完了: ${result2Lines}行`);
    
    console.log(`⏳ レート制限回避のため ${passDelay / 1000} 秒待機します...`);
    Utilities.sleep(passDelay);
    
    // 3回目: 6-8ページ目（Z-MKシリーズを含む）
    console.log('=== 3回目読み取り: 6-8ページ目（Z-MKシリーズ） ===');
    const result3 = generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルの6-8ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。

## 重要指示
- テーブルのヘッダーは「Product Code | Description | On Hand | Quantity SC w/o DN | Available」とすること。
- 6-7ページ目の**すべての在庫アイテム**を漏れなく抽出してください。
- **特に重要**: 6ページ目には「Z-MK」というカテゴリがあり、以下の商品コードが必ず含まれています：
  * AC-261, AC-262, AC-263, AC-264
  * BD-060, BD-061, BD-062, BD-063, BD-064, BD-065, BD-067
  * FC-056
- 7-8ページ目には以下のセクション・商品コードが含まれています：
  * Tee-Bar (MK -15): TNMA1532M3000MK, TNMC1525M0600MK, TNMC1525M1200MK
  * Tee-Bar (MK -24): TNIA2432I0800MK, TNIA2432I1000MK, TNIC2425I0200MK, TNIC2425I0400MK, TNIL2025I0800MK, TNIL2025I1000MK, TNMA2432M2400MK, TNMA2432M3000H200MK, TNMA2432M3000H500MK, TNMA2432M3000MK, TNMC2425M0500MK, TNMC2425M0600MK, TNMC2425M1000MK, TNMC2425M1200MK
  * Tee-Bar (New Colour): TNIW2020I1000N1
  * SCREW: SW-002, SW-003, SW-003B, SW-005, SW-008, SW-009, SW-009B, SW-010, SW-011, SW-012, SW-018, SW-020, SW-028, SW-030, SW-031, SW-032, SW-033, SW-039C, SW-039S, SW-040B, SW-041, SW-044, SW-048, SW-049, SW-050, SW-063, SW-065, SW-068
  * US05132045MI0800, US05132045MI0900, UT05125045MI0800
  * GSW04I0800B, GSW04I1000B, GSW04M3000B
  * GSC08I0800B, GSC08I1000B
- **必須**: カテゴリ名（Z-MKなど）は無視し、商品コードから始まるデータ行のみを抽出してください。
- **必須**: 各行は必ず5列（Product Code | Description | On Hand | Quantity SC w/o DN | Available）を含むマークダウンテーブル形式で出力してください。
- 数値はカンマ区切りでもそのまま抽出してください（例: 1,170.00, 23,000.00）。
- 負の数値もそのまま抽出してください（例: -382.00, -536.00）。

出力形式の例：
| Product Code | Description | On Hand | Quantity SC w/o DN | Available |
|-------------|-------------|---------|---------------------|-----------|
| AC-261 | Welltone Rock Wool 60kg/m3 1200 x 600 x 50mm thk. | 8.00 | 76.00 | 68.00 |
| AC-262 | Welltone Fireproof Rock Wool 100kg/m3 50mm thk. | 594.00 | 212.00 | -382.00 |

マークダウンテーブルのみを出力し、説明文やその他のテキストは一切含めないでください。
`, 3);
    const result3Lines = requireGeminiPassResult('6-8ページ目', result3);
    allResults.push(result3);
    console.log(`3回目読み取り完了: ${result3Lines}行`);

    const extraRanges = CONFIG.GEMINI_EXTRA_PAGE_RANGE_PASSES || [];
    for (let er = 0; er < extraRanges.length; er++) {
      const pair = extraRanges[er];
      if (!pair || pair.length < 2) continue;
      const pFrom = pair[0];
      const pTo = pair[1];
      console.log(`⏳ レート制限回避のため ${passDelay / 1000} 秒待機します...`);
      Utilities.sleep(passDelay);
      console.log(`=== 追加読み取り: ${pFrom}-${pTo}ページ目 ===`);
      const extraPrompt = [
        `添付された在庫PDFファイルの${pFrom}-${pTo}ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。`,
        '',
        '## 重要指示',
        '- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。',
        `- ${pFrom}-${pTo}ページ目に**実際に印刷されている**在庫表の行だけを漏れなく抽出すること（他ページの行を推測・コピーしない）。`,
        '- ページ先頭の Date / Time / Page 番号やフィルタ説明はデータ行に含めない。',
        '- マークダウンテーブルのみを出力してください。'
      ].join('\n');
      const resExtra = generateSummaryWithGeminiSinglePass(pdfBlob, extraPrompt, 4 + er);
      if (resExtra && resExtra.trim().length > 0) {
        allResults.push(resExtra);
        console.log(
          `追加読み取り(${pFrom}-${pTo})完了: ${resExtra.split('\n').filter(line => line.includes('|')).length}行`
        );
      }
    }
    
    // 結果を統合
    if (allResults.length === 0) {
      console.log('すべての読み取りで結果が得られませんでした');
      return '';
    }
    
    // 各結果のデバッグ情報を出力
    console.log('=== 各読み取り結果の詳細 ===');
    allResults.forEach((result, index) => {
      const lines = result.split('\n');
      const tableLines = lines.filter(line => line.includes('|') && !line.includes('---'));
      console.log(`${index + 1}回目: ${tableLines.length}行のテーブル行を抽出`);
      
      // Z-MKシリーズの商品コードが含まれているか確認
      const zMkCodes = ['AC-261', 'AC-262', 'AC-263', 'AC-264', 'BD-060', 'BD-061', 'BD-062', 'BD-063', 'BD-064', 'BD-065', 'BD-067', 'FC-056'];
      const foundCodes = zMkCodes.filter(code => result.includes(code));
      if (foundCodes.length > 0) {
        console.log(`  ✅ Z-MKシリーズ検出: ${foundCodes.join(', ')}`);
      } else if (index === 2) {
        console.log(`  ⚠️ 警告: 3回目の読み取り結果にZ-MKシリーズが含まれていません`);
      }
      
      // 最初の数行をサンプルとして表示
      const sampleLines = tableLines.slice(0, 3);
      if (sampleLines.length > 0) {
        console.log(`  サンプル行:`);
        sampleLines.forEach(line => console.log(`    ${line.substring(0, 100)}...`));
      }
    });
    
    const combinedResult = allResults.join('\n');
    const combinedTableLines = combinedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
    console.log(`統合結果: ${combinedTableLines.length}行のテーブル行`);

    let finalCombinedResult = combinedResult;
    if (CONFIG.GEMINI_TARGETED_CODE_RESCUE === true) {
      const zMkCodes = ['AC-261', 'AC-262', 'AC-263', 'AC-264', 'BD-060', 'BD-061', 'BD-062', 'BD-063', 'BD-064', 'BD-065', 'BD-067', 'FC-056'];
      const foundCodes = zMkCodes.filter(code => combinedResult.includes(code));
      if (foundCodes.length === zMkCodes.length) {
        console.log(`✅ 統合結果にZ-MKシリーズの全商品コードが含まれています`);
      } else {
        const missingCodes = zMkCodes.filter(code => !foundCodes.includes(code));
        console.error(`❌ 警告: 統合結果に以下のZ-MKシリーズが含まれていません: ${missingCodes.join(', ')}`);
        try {
          console.log('不足コード救済パスを実行します...');
          let rescue = '';
          if (CONFIG.GEMINI_RESCUE_TRY_OCR_FIRST !== false) {
            try {
              const ocrRescue = extractInventoryTableWithoutGemini(pdfBlob);
              const got = missingCodes.filter(function (c) {
                return ocrRescue && ocrRescue.indexOf(c) >= 0;
              });
              if (ocrRescue && ocrRescue.trim() && got.length > 0) {
                rescue = ocrRescue;
                console.log('✅ 不足コード救済: Drive OCR で取得 ' + got.join(', '));
              }
            } catch (ocrRescueErr) {
              console.warn('不足コード救済 OCR 試行: ' + ocrRescueErr);
            }
          }
          if (!rescue || !rescue.trim()) {
            const rescuePrompt = `
添付PDF全体を確認し、次の商品コードが存在する場合のみ行を抽出してください:
${missingCodes.join(', ')}

重要:
- 存在しないコードは出力しない
- 出力は下記ヘッダーのマークダウンテーブルのみ
| Product Code | Description | On Hand | Quantity SC w/o DN | Available |
`;
            rescue = generateSummaryWithGeminiSinglePass(pdfBlob, rescuePrompt, 99);
          }
          if (rescue && rescue.trim()) {
            finalCombinedResult = `${combinedResult}\n${rescue}`;
            console.log('✅ 不足コード救済の結果を統合しました');
          }
        } catch (rescueError) {
          console.error('不足コード救済パスでエラー:', rescueError);
        }
      }
    }

    return finalCombinedResult;
    
  } catch (error) {
    console.error('PDF解析エラー:', error);
    // フォールバック: 単一回処理
    return generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルを解析し、すべての製品アイテムをマークダウン形式のテーブルとして抽出してください。

# 指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 表形式のデータのみを抽出し、それ以外のテキストは含めないこと。
- 最終的な出力はマークダウンのテーブルのみとし、前後の説明文は一切不要です。
- すべての在庫アイテムを漏れなく抽出してください。
`, 1);
  }
}

/**
 * Gemini 1.5 APIにPDFファイルを直接送信して解析します（単一回処理）。
 */
function generateSummaryWithGeminiSinglePass(pdfBlob, prompt, passNumber = 1) {
  const apiKey = getGeminiApiKey();
  const url = getGeminiGenerateContentUrl();
  const maxRetries = 3;
  const retryDelay = 60000; // 60秒（503エラー用）
  const rateLimitDelays = [120000, 180000]; // 120秒、180秒（429エラー用）- エラーメッセージから抽出できない場合のデフォルト値

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(
        `Gemini API 処理開始 (試行 ${attempt}/${maxRetries}) モデル: ${getEffectiveGeminiModelId()} - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`
      );

      const base64Pdf = Utilities.base64Encode(pdfBlob.getBytes());

      const requestPayload = {
        contents: [
          {
            parts: [
              { text: prompt },
              {
                inline_data: {
                  mime_type: 'application/pdf',
                  data: base64Pdf
                }
              }
            ]
          }
        ],
        generationConfig: {
          temperature: 0.0,
          maxOutputTokens: 65536,
          topP: 0.9,
          topK: 50
        }
      };

      const requestOptions = {
        method: 'POST',
        headers: geminiApiHeaders(apiKey),
        payload: JSON.stringify(requestPayload),
        muteHttpExceptions: true
      };
      
      const response = UrlFetchApp.fetch(url, requestOptions);
      const responseCode = response.getResponseCode();
      const responseBody = response.getContentText();

      if (responseCode === 503 || responseCode === 429) {
        console.error(`Gemini API エラー: ${responseCode} - ${redactForLog(responseBody)}`);
        // 認証/認可エラー(401, 403)は即座に通知（リトライ不可）
        if (responseCode === 403 || responseCode === 401) {
          try { sendCriticalErrorNotification(new Error(`Gemini API error ${responseCode}`), `generateSummaryWithGeminiSinglePass(pass=${passNumber})`); } catch (_e) {}
        }
        // 429 もここまで来たら Utilities.sleep で待ってリトライ（即 return '' しない。空返却すると全ページ処理が続行不能になる）
        if (responseCode === 429) {
          console.warn(
            `⚠️ 429検出 (pass=${passNumber})。リトライ待機へ進みます（即空返却しない）`
          );
        }
        if (attempt < maxRetries) {
          let delay;
          if (responseCode === 429) {
            // エラーレスポンスからリトライ時間を抽出（秒単位）
            let retryAfterSeconds = null;
            try {
              const errorData = JSON.parse(responseBody);
              
              // まずメッセージから抽出を試みる（最も確実）
              if (errorData.error && errorData.error.message) {
                const retryMatch = errorData.error.message.match(/Please retry in ([\d.]+)s/i);
                if (retryMatch) {
                  retryAfterSeconds = parseFloat(retryMatch[1]);
                  console.log(`✅ メッセージからリトライ時間を抽出: ${retryMatch[1]}秒`);
                }
              }
              
              // RetryInfoからも抽出を試みる（メッセージから抽出できなかった場合）
              if (!retryAfterSeconds && errorData.error && errorData.error.details) {
                for (const detail of errorData.error.details) {
                  if (detail['@type'] === 'type.googleapis.com/google.rpc.RetryInfo' && detail.retryDelay) {
                    // retryDelayは秒単位の文字列（例: "36s" または "36.841947444s"）
                    const retryDelayStr = detail.retryDelay.toString();
                    // "s"を削除して数値に変換
                    retryAfterSeconds = parseFloat(retryDelayStr.replace(/s$/, '')) || null;
                    if (retryAfterSeconds) {
                      console.log(`✅ RetryInfoからリトライ時間を抽出: ${retryDelayStr} -> ${retryAfterSeconds}秒`);
                    }
                    break;
                  }
                }
              }
              
              // デバッグ: 抽出結果をログに記録
              if (!retryAfterSeconds) {
                console.log(`⚠️ リトライ時間の抽出に失敗しました。レスポンス: ${responseBody.substring(0, 500)}`);
              }
            } catch (e) {
              console.log(`リトライ時間の抽出でエラー: ${e.toString()}`);
            }
            
            // リトライ時間を決定（エラーメッセージから抽出した値を必ず使用）
            if (retryAfterSeconds && retryAfterSeconds > 0) {
              // エラーメッセージの指示に従う（+3秒の余裕のみ）
              delay = Math.ceil((retryAfterSeconds + 3) * 1000);
              console.log(`⚠️ レート制限エラー(429)検出。エラーメッセージから${retryAfterSeconds}秒後にリトライ可能と表示されています。${delay/1000}秒後にリトライします... (試行 ${attempt + 1}/${maxRetries})`);
            } else {
              // リトライ時間が抽出できない場合のみデフォルト値を使用
              delay = rateLimitDelays[attempt - 1] || 120000;
              console.log(`⚠️ レート制限エラー(429)検出。リトライ時間が抽出できなかったため、${delay/1000}秒後にリトライします... (試行 ${attempt + 1}/${maxRetries})`);
            }
          } else {
            delay = retryDelay;
            console.log(`${delay/1000}秒後にリトライします... (試行 ${attempt + 1}/${maxRetries})`);
          }
          Utilities.sleep(delay);
          continue;
        } else {
          // 429/503エラーが全てのリトライで失敗した場合のみ通知を送信
          if (responseCode === 429) {
            console.error(`❌ レート制限エラー(429)が${maxRetries}回連続で発生しました。実行時間制限を考慮して処理を中断します。`);
            console.error(`💡 対処法: 少し時間を空けて再実行してください。`);
            try { sendCriticalErrorNotification(new Error(`Gemini API error ${responseCode} - 全てのリトライが失敗`), `generateSummaryWithGeminiSinglePass(pass=${passNumber})`); } catch (_e) {}
            // Geminiが使えない場合はOCRフォールバックを試す
            try {
              console.log('⚠️ Geminiが利用不可のためOCRフォールバックを実行します...');
              const fallback = extractInventoryTableWithoutGemini(pdfBlob);
              if (fallback && fallback.trim()) {
                console.log('✅ OCRフォールバックで抽出成功');
                return fallback;
              }
            } catch (fallbackError) {
              console.error('❌ OCRフォールバックに失敗:', fallbackError);
            }
          } else if (responseCode === 503) {
            console.error(`❌ サービス一時停止(503)が${maxRetries}回連続で発生しました。`);
            try { sendCriticalErrorNotification(new Error(`Gemini API error ${responseCode} - 全てのリトライが失敗`), `generateSummaryWithGeminiSinglePass(pass=${passNumber})`); } catch (_e) {}
          }
          throw new Error(
            `Gemini APIがエラーを返しました: ${responseCode}. レスポンス: ${redactForLog(responseBody)}`
          );
        }
      }

      if (responseCode !== 200) {
        console.error(`Gemini API エラー: ${responseCode} - ${redactForLog(responseBody)}`);
        try { sendCriticalErrorNotification(new Error(`Gemini API error ${responseCode}`), `generateSummaryWithGeminiSinglePass(pass=${passNumber})`); } catch (_e) {}
        throw new Error(
          `Gemini APIがエラーを返しました: ${responseCode}. レスポンス: ${redactForLog(responseBody)}`
        );
      }

      const responseData = JSON.parse(responseBody);
      
      if (responseData.candidates && responseData.candidates[0].content) {
        const generatedText = responseData.candidates[0].content.parts[0].text;
        console.log(`Gemini解析成功: ${generatedText.length}文字`);
        
        const lines = generatedText.split('\n');
        const tableLines = lines.filter(line => line.includes('|') && !line.includes('---'));
        console.log(`抽出された表の行数: ${tableLines.length}行`);
        
        const correctedText = correctProductCodeErrors(generatedText);
        if (correctedText !== generatedText) {
          console.log('✅ 商品コード修正が適用されました');
        }
        
        return correctedText;
      } else {
        console.error(`Gemini APIからの予期しない応答:`, redactForLog(responseBody));
        throw new Error('Gemini APIから有効なコンテンツが返されませんでした。');
      }

    } catch (error) {
      console.error(`Gemini API処理エラー (試行 ${attempt}/${maxRetries}):`, redactForLog(error));
      try { sendCriticalErrorNotification(error, `generateSummaryWithGeminiSinglePass(pass=${passNumber})`); } catch (_e) {}
      if (attempt < maxRetries) {
        console.log(`${retryDelay/1000}秒後にリトライします... (試行 ${attempt + 1}/${maxRetries})`);
        Utilities.sleep(retryDelay);
        continue;
      } else {
        // 最終失敗時はOCRフォールバックを試す
        try {
          console.log('⚠️ Gemini最終失敗のためOCRフォールバックを実行します...');
          const fallback = extractInventoryTableWithoutGemini(pdfBlob);
          if (fallback && fallback.trim()) {
            console.log('✅ OCRフォールバックで抽出成功');
            return fallback;
          }
        } catch (fallbackError) {
          console.error('❌ OCRフォールバックに失敗:', fallbackError);
        }
        throw error;
      }
    }
  }
  
  throw new Error(`Gemini API処理が${maxRetries}回の試行後も失敗しました`);
}

/**
 * PDFファイルの更新時間を取得します（香港時間 UTC+8）
 */
function getPdfUpdateTime(email) {
  try {
    if (CONFIG.FORCE_OCR_ONLY || !CONFIG.USE_GEMINI_PDF_METADATA_TIME) {
      const emailDate = email.getDate();
      const emailDateHK = new Date(emailDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
      const updateTime = emailDateHK.toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      }).replace(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+)/, '$3/$1/$2 $4:$5');
      console.log(`PDF更新時間（メール受信日時）: ${updateTime}`);
      return updateTime;
    }
    const pdfBlob = getPdfAttachment(email);
    if (pdfBlob) {
      const pdfCreateTime = extractPdfCreationTime(pdfBlob);
      if (pdfCreateTime) {
        console.log(`PDFメタデータから作成日時を取得: ${pdfCreateTime}`);
        return pdfCreateTime;
      }
    }
    
    const emailDate = email.getDate();
    const emailDateHK = new Date(emailDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    
    const updateTime = emailDateHK.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+)/, '$3/$1/$2 $4:$5');
    
    console.log(`PDF更新時間（メール受信日時）: ${updateTime}`);
    return updateTime;
    
  } catch (error) {
    console.error('PDF更新時間取得エラー:', error);
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const fallbackTime = hongKongTime.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+)/, '$3/$1/$2 $4:$5');
    
    console.log(`フォールバック時間を使用: ${fallbackTime}`);
    return fallbackTime;
  }
}

/**
 * Geminiを使わずにPDFをOCRでテキスト化し、在庫テーブルを抽出します。
 * 429などでGeminiが使えない場合のフォールバック。
 */
function extractInventoryTableWithoutGemini(pdfBlob) {
  const text = extractPdfTextWithOcr(pdfBlob);
  if (!text || !text.trim()) {
    throw new Error('OCRでテキストを抽出できませんでした');
  }

  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const rows = [];

  const isCode = (token) => /^[A-Z0-9]{1,4}-?[A-Z0-9]{2,}/.test(token);
  const isNumber = (token) => /^-?[0-9,]+\.\d{2}$/.test(token);
  const toNumber = (token) => {
    const v = parseFloat(String(token || '').replace(/,/g, ''));
    return Number.isFinite(v) ? v : NaN;
  };

  const pickBestNumericTriple = (tokens) => {
    const numericPositions = [];
    for (let idx = 1; idx < tokens.length; idx++) {
      if (isNumber(tokens[idx])) numericPositions.push(idx);
    }
    if (numericPositions.length < 3) return null;

    const last3 = numericPositions.slice(-3);
    const n1 = toNumber(tokens[last3[0]]);
    const n2 = toNumber(tokens[last3[1]]);
    const n3 = toNumber(tokens[last3[2]]);
    if (!Number.isFinite(n1) || !Number.isFinite(n2) || !Number.isFinite(n3)) return null;
    return { p1: last3[0], p2: last3[1], p3: last3[2] };
  };

  // 1) 通常の行ベース抽出
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const tokens = line.split(/\s+/);
    if (tokens.length === 0) continue;

    const code = tokens[0];
    if (!isCode(code)) continue;

    let mergedTokens = tokens.slice();
    let lookahead = 0;
    while (lookahead < 2) {
      const numberCount = mergedTokens.filter(t => isNumber(t)).length;
      if (numberCount >= 3) break;
      const nextLine = lines[i + 1 + lookahead];
      if (!nextLine) break;
      const nextTokens = nextLine.split(/\s+/);
      if (nextTokens.length > 0 && isCode(nextTokens[0])) break;
      mergedTokens = mergedTokens.concat(nextTokens);
      lookahead++;
    }

    const bestTriple = pickBestNumericTriple(mergedTokens);
    if (!bestTriple) continue;

    const firstNumIdx = bestTriple.p1;
    const descTokens = mergedTokens.slice(1, firstNumIdx);
    const description = descTokens.join(' ');
    if (!description) continue;

    const onHand = mergedTokens[bestTriple.p1];
    const scWithoutDN = mergedTokens[bestTriple.p2];
    const available = mergedTokens[bestTriple.p3];

    rows.push([code, description, onHand, scWithoutDN, available]);
  }

  // 2) Z-MK系の不足を全文テキストから補完（行折り返し対策）
  const zMkCodes = ['AC-261','AC-262','AC-263','AC-264','BD-060','BD-061','BD-062','BD-063','BD-064','BD-065','BD-067','FC-056'];
  const existingCodes = new Set(rows.map(r => r[0]));
  const fullText = text.replace(/\s+/g, ' ').trim();

  for (const code of zMkCodes) {
    if (existingCodes.has(code)) continue;
    const re = new RegExp(`${code}\\s+(.+?)\\s+(-?[0-9,]+(?:\\.\\d+)?)\\s+(-?[0-9,]+(?:\\.\\d+)?)\\s+(-?[0-9,]+(?:\\.\\d+)?)`, 'i');
    const m = fullText.match(re);
    if (m) {
      const description = m[1].trim();
      const onHand = m[2];
      const scWithoutDN = m[3];
      const available = m[4];
      rows.push([code, description, onHand, scWithoutDN, available]);
      existingCodes.add(code);
    }
  }

  if (rows.length === 0) {
    throw new Error('OCRテキストから在庫行を抽出できませんでした');
  }

  // Markdownテーブルに変換
  const header = [
    '| Product Code | Description | On Hand | Quantity SC w/o DN | Available |',
    '|-------------|-------------|---------|---------------------|-----------|'
  ];
  const body = rows.map(r => `| ${r[0]} | ${r[1]} | ${r[2]} | ${r[3]} | ${r[4]} |`);
  return header.concat(body).join('\n');
}

/**
 * Drive OCRでPDFをテキスト化（1回のみ）。Advanced Drive Service 必須。
 */
function extractPdfTextWithOcrOnce(pdfBlob) {
  if (typeof Drive === 'undefined' || !Drive.Files || typeof Drive.Files.insert !== 'function') {
    throw new Error('Drive API not enabled in Apps Script Advanced Services. 「サービス」→「Google Advanced Services」→「Drive API」をONにして保存してください。');
  }
  const tempFile = DriveApp.createFile(pdfBlob);
  try {
    const resource = {
      title: tempFile.getName(),
      mimeType: 'application/pdf'
    };
    const ocrFile = Drive.Files.insert(resource, tempFile.getBlob(), {
      ocr: true,
      ocrLanguage: 'en'
    });

    const doc = DocumentApp.openById(ocrFile.id);
    const text = doc.getBody().getText();

    DriveApp.getFileById(ocrFile.id).setTrashed(true);
    tempFile.setTrashed(true);

    return text;
  } catch (e) {
    tempFile.setTrashed(true);
    throw e;
  }
}

/**
 * Drive OCR（Service error: Drive 等は待って再試行）
 */
function extractPdfTextWithOcr(pdfBlob) {
  const maxAttempts = 4;
  const delayMs = 8000;
  let lastError;
  for (let a = 1; a <= maxAttempts; a++) {
    try {
      return extractPdfTextWithOcrOnce(pdfBlob);
    } catch (e) {
      lastError = e;
      console.warn(`Drive OCR 試行 ${a}/${maxAttempts} 失敗: ${e}`);
      if (a < maxAttempts) {
        Utilities.sleep(delayMs);
      }
    }
  }
  throw lastError;
}

/**
 * PDFファイルのメタデータから作成日時を抽出します
 */
function extractPdfCreationTime(pdfBlob) {
  try {
    console.log('PDFメタデータの作成日時を抽出中...');
    
    const apiKey = getGeminiApiKey();
    const url = getGeminiGenerateContentUrl();
    
    const base64Pdf = Utilities.base64Encode(pdfBlob.getBytes());
    
    const requestPayload = {
      contents: [
        {
          parts: [
            { 
              text: `このPDFファイルのメタデータから作成日時または更新日時を抽出してください。
以下の情報を探してください：
- CreationDate（作成日時）
- ModDate（更新日時）
- Producer（作成者）
- CreationTool（作成ツール）

見つかった日時情報があれば、以下の形式で返してください：
YYYY/MM/DD HH:MM

見つからない場合は「見つかりません」と返してください。` 
            },
            {
              inline_data: {
                mime_type: 'application/pdf',
                data: base64Pdf
              }
            }
          ]
        }
      ],
      generationConfig: {
        temperature: 0.0,
        maxOutputTokens: 1000,
        topP: 0.9,
        topK: 50
      }
    };

    const requestOptions = {
      method: 'POST',
      headers: geminiApiHeaders(apiKey),
      payload: JSON.stringify(requestPayload),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(url, requestOptions);
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();

    if (responseCode !== 200) {
      console.error(`PDFメタデータ抽出エラー: ${responseCode} - ${redactForLog(responseBody)}`);
      // メタデータ抽出は補助機能のため、ここでは重大通知しない
      return null;
    }

    const responseData = JSON.parse(responseBody);
    
    if (responseData.candidates && responseData.candidates[0].content) {
      const generatedText = responseData.candidates[0].content.parts[0].text;
      console.log(`PDFメタデータ解析結果: ${generatedText}`);
      
      const datePattern = /(\d{4})\/(\d{2})\/(\d{2})\s+(\d{2}):(\d{2})/;
      const match = generatedText.match(datePattern);
      
      if (match) {
        const [, year, month, day, hour, minute] = match;
        const pdfDate = new Date(`${year}-${month}-${day}T${hour}:${minute}:00`);
        const pdfDateHK = new Date(pdfDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
        
        const formattedTime = pdfDateHK.toLocaleString('en-US', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        }).replace(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+)/, '$3/$1/$2 $4:$5');
        
        console.log(`PDF作成日時を抽出: ${formattedTime}`);
        return formattedTime;
      } else {
        console.log('PDFメタデータに日時情報が見つかりませんでした');
        return null;
      }
    }
    
    return null;
    
  } catch (error) {
    console.error('PDFメタデータ抽出エラー:', redactForLog(error));
    return null;
  }
}

/**
 * 香港時間の「今日」を DD/MM/YYYY で返す（在庫レポート表頭の Date : と同形式）
 */
function getHongKongTodayDdMmYyyy() {
  const now = new Date();
  const hk = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
  const d = String(hk.getDate()).padStart(2, '0');
  const m = String(hk.getMonth() + 1).padStart(2, '0');
  const y = String(hk.getFullYear());
  return `${d}/${m}/${y}`;
}

/** 任意の Date を香港タイムゾーンで DD/MM/YYYY に */
function getDdMmYyyyInHongKong(date) {
  const hk = new Date(date.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
  const d = String(hk.getDate()).padStart(2, '0');
  const m = String(hk.getMonth() + 1).padStart(2, '0');
  const y = String(hk.getFullYear());
  return `${d}/${m}/${y}`;
}

/** 任意の Date を香港タイムゾーンで HH:MM:SS に */
function getHmsStringInHongKong(date) {
  const hk = new Date(date.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
  const p = n => String(n).padStart(2, '0');
  return p(hk.getHours()) + ':' + p(hk.getMinutes()) + ':' + p(hk.getSeconds());
}

/**
 * "D/M/YYYY" / "DD/MM/YYYY" を DD/MM/YYYY に統一。不正なら null。
 */
function normalizeDdMmYyyy(s) {
  if (!s || typeof s !== 'string') return null;
  const t = s.trim();
  const m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (!m) return null;
  return `${m[1].padStart(2, '0')}/${m[2].padStart(2, '0')}/${m[3]}`;
}

/**
 * 香港時刻を 1 日の秒に変換。スロット境界は start〜end 秒の両端を含む（inclusive）。
 */
function inventoryClockToSeconds(hour, minute, second) {
  const h = Number(hour);
  const m = Number(minute);
  const s = Number(second) || 0;
  return h * 3600 + m * 60 + s;
}

/**
 * 現在（香港）が CONFIG の在庫スロット内なら 1|2|3、どれにも入らなければ null
 */
function getHkNowInventorySlotIndex() {
  const now = new Date();
  const hk = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
  const sec = inventoryClockToSeconds(hk.getHours(), hk.getMinutes(), hk.getSeconds());
  const slots = [
    {
      id: 1,
      start: inventoryClockToSeconds(CONFIG.SLOT1_START_HOUR, CONFIG.SLOT1_START_MINUTE, 0),
      end: inventoryClockToSeconds(CONFIG.SLOT1_END_HOUR, CONFIG.SLOT1_END_MINUTE, 0)
    },
    {
      id: 2,
      start: inventoryClockToSeconds(CONFIG.SLOT2_START_HOUR, CONFIG.SLOT2_START_MINUTE, 0),
      end: inventoryClockToSeconds(CONFIG.SLOT2_END_HOUR, CONFIG.SLOT2_END_MINUTE, 0)
    },
    {
      id: 3,
      start: inventoryClockToSeconds(CONFIG.SLOT3_START_HOUR, CONFIG.SLOT3_START_MINUTE, 0),
      end: inventoryClockToSeconds(CONFIG.SLOT3_END_HOUR, CONFIG.SLOT3_END_MINUTE, 0)
    }
  ];
  for (let i = 0; i < slots.length; i++) {
    const b = slots[i];
    if (sec >= b.start && sec <= b.end) return b.id;
  }
  return null;
}

/**
 * PDF表頭 "Time :" の HH:MM または HH:MM:SS をパース
 */
function parsePdfHeaderTimeToSeconds(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return null;
  const t = timeStr.trim();
  const m = t.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
  if (!m) return null;
  const h = parseInt(m[1], 10);
  const mi = parseInt(m[2], 10);
  const s = m[3] != null ? parseInt(m[3], 10) : 0;
  if (h > 23 || mi > 59 || s > 59) return null;
  return inventoryClockToSeconds(h, mi, s);
}

/**
 * PDF表頭時刻がどのスロット（朝・昼・夜）に属するか。該当なしなら null
 */
function getPdfTimeInventorySlotIndex(headerTimeStr) {
  const sec = parsePdfHeaderTimeToSeconds(headerTimeStr);
  if (sec == null) return null;
  const slots = [
    {
      id: 1,
      start: inventoryClockToSeconds(CONFIG.SLOT1_START_HOUR, CONFIG.SLOT1_START_MINUTE, 0),
      end: inventoryClockToSeconds(CONFIG.SLOT1_END_HOUR, CONFIG.SLOT1_END_MINUTE, 0)
    },
    {
      id: 2,
      start: inventoryClockToSeconds(CONFIG.SLOT2_START_HOUR, CONFIG.SLOT2_START_MINUTE, 0),
      end: inventoryClockToSeconds(CONFIG.SLOT2_END_HOUR, CONFIG.SLOT2_END_MINUTE, 0)
    },
    {
      id: 3,
      start: inventoryClockToSeconds(CONFIG.SLOT3_START_HOUR, CONFIG.SLOT3_START_MINUTE, 0),
      end: inventoryClockToSeconds(CONFIG.SLOT3_END_HOUR, CONFIG.SLOT3_END_MINUTE, 0)
    }
  ];
  for (let i = 0; i < slots.length; i++) {
    const b = slots[i];
    if (sec >= b.start && sec <= b.end) return b.id;
  }
  return null;
}

/**
 * Gemini 429/503 時の待機ミリ秒（generateSummary 系と同じ方針）
 */
function computeGeminiRetryWaitMs(responseCode, responseBody, attempt, rateLimitDelays, retryDelay503) {
  if (responseCode === 503) return retryDelay503;
  if (responseCode !== 429) return rateLimitDelays[Math.min(attempt - 1, rateLimitDelays.length - 1)] || 120000;
  let retryAfterSeconds = null;
  try {
    const errorData = JSON.parse(responseBody);
    if (errorData.error && errorData.error.message) {
      const retryMatch = errorData.error.message.match(/Please retry in ([\d.]+)s/i);
      if (retryMatch) retryAfterSeconds = parseFloat(retryMatch[1]);
    }
    if (!retryAfterSeconds && errorData.error && errorData.error.details) {
      for (let d = 0; d < errorData.error.details.length; d++) {
        const detail = errorData.error.details[d];
        if (detail['@type'] === 'type.googleapis.com/google.rpc.RetryInfo' && detail.retryDelay) {
          const retryDelayStr = detail.retryDelay.toString();
          retryAfterSeconds = parseFloat(retryDelayStr.replace(/s$/, '')) || null;
          break;
        }
      }
    }
  } catch (_e) {}
  if (retryAfterSeconds && retryAfterSeconds > 0) {
    return Math.ceil((retryAfterSeconds + 3) * 1000);
  }
  return rateLimitDelays[attempt - 1] || 120000;
}

/**
 * generateContent 応答テキストから DATE:/TIME: 行を解析
 * @return {{date: string|null, time: string|null}|null} null は候補なし等
 */
function parseInventoryReportHeaderFromGeminiResponseBody(responseBody) {
  let responseData;
  try {
    responseData = JSON.parse(responseBody);
  } catch (_e) {
    return null;
  }
  if (!responseData.candidates || !responseData.candidates[0].content) {
    return null;
  }
  const text = responseData.candidates[0].content.parts[0].text || '';
  const dateLine = text.match(/^DATE:\s*(.+)$/im);
  const timeLine = text.match(/^TIME:\s*(.+)$/im);
  let date = dateLine ? dateLine[1].trim() : null;
  let time = timeLine ? timeLine[1].trim() : null;
  if (date && /NOT_FOUND/i.test(date)) date = null;
  if (time && /NOT_FOUND/i.test(time)) time = null;
  if (date) {
    const dm = date.match(/(\d{1,2}\/\d{1,2}\/\d{4})/);
    date = dm ? dm[1] : null;
  }
  if (time) {
    const tm = time.match(/(\d{1,2}:\d{2}(?::\d{2})?)/);
    time = tm ? tm[1] : null;
  }
  return { date: date, time: time };
}

/**
 * Drive OCR テキスト先頭から Date : / Time : を正規表現で拾う（429 時のフォールバック）
 */
function extractInventoryReportHeaderDateTimeFromOcr(pdfBlob) {
  const text = extractPdfTextWithOcr(pdfBlob);
  if (!text || !text.trim()) {
    return { date: null, time: null };
  }
  const head = text.substring(0, 12000);
  let dateStr = null;
  const mSlash = head.match(/Date\s*[:：]\s*(\d{1,2}\/\d{1,2}\/\d{4})/i);
  const mHyphen = head.match(/Date\s*[:：]\s*(\d{1,2})-(\d{1,2})-(\d{4})/i);
  if (mSlash) {
    dateStr = mSlash[1];
  } else if (mHyphen) {
    dateStr =
      mHyphen[1].padStart(2, '0') + '/' + mHyphen[2].padStart(2, '0') + '/' + mHyphen[3];
  }
  const tm = head.match(/Time\s*[:：]\s*(\d{1,2}:\d{2}(?::\d{2})?)/i);
  return {
    date: dateStr,
    time: tm ? tm[1] : null
  };
}

/**
 * PDF先頭の "Date :" / "Time :" を Gemini で取得（429/503 リトライ＋OCRフォールバック）
 * @return {{date: string|null, time: string|null, extractionFailed?: boolean}}
 */
function extractInventoryReportHeaderDateAndTimeFromPdf(pdfBlob) {
  const maxRetries = 3;
  const retryDelay503 = 60000;
  const rateLimitDelays = [120000, 180000];
  let rateLimitOcrTried = false;

  if (CONFIG.HEADER_EXTRACT_OCR_FIRST !== false) {
    try {
      console.log('PDF表頭抽出: 帯域節約のため Drive OCR を先行');
      const ocrHdr = extractInventoryReportHeaderDateTimeFromOcr(pdfBlob);
      if (ocrHdr && ocrHdr.date) {
        console.log(
          'PDF表頭日時: OCR 先行で取得 date=' +
            ocrHdr.date +
            ' time=' +
            (ocrHdr.time || '-')
        );
        return { date: ocrHdr.date, time: ocrHdr.time };
      }
      console.log('PDF表頭抽出: OCR 先行では Date 行なし — Gemini を試行');
    } catch (ocrErr) {
      console.warn('PDF表頭 OCR 先行失敗（Gemini へ続行）: ' + ocrErr);
    }
  }

  const tryOcrHeaderAfterRateLimit = (responseCode) => {
    if (CONFIG.HEADER_EXTRACT_OCR_FIRST !== false) {
      console.log(
        'PDF表頭抽出: OCR 先行済みのため、' +
          responseCode +
          ' 時の追加 OCR はスキップ（待機後に Gemini のみ再試行）'
      );
      return null;
    }
    if (rateLimitOcrTried) return null;
    rateLimitOcrTried = true;
    try {
      console.log(
        'PDF表頭抽出: Gemini ' +
          responseCode +
          ' — 待機前に OCR で Date/Time を試行'
      );
      const ocrHdr = extractInventoryReportHeaderDateTimeFromOcr(pdfBlob);
      if (ocrHdr && ocrHdr.date) {
        console.log(
          'PDF表頭日時: OCR で取得（Gemini 待ちなし） date=' +
            ocrHdr.date +
            ' time=' +
            (ocrHdr.time || '-')
        );
        return { date: ocrHdr.date, time: ocrHdr.time };
      }
      console.log('PDF表頭抽出: OCR では Date を取得できず、Gemini リトライ待機へ進みます');
    } catch (ocrErr) {
      console.warn('PDF表頭 OCR（レート制限直後）: ' + ocrErr);
    }
    return null;
  };
  const apiKey = getGeminiApiKey();
  const url = getGeminiGenerateContentUrl();
  const base64Pdf = Utilities.base64Encode(pdfBlob.getBytes());
  const prompt = [
    'The first page of this PDF is an "Inventory Summary Report" style header.',
    'Find the lines "Date :" and "Time :" (with colons, spaces may vary).',
    'Reply with exactly two lines and nothing else:',
    'DATE: DD/MM/YYYY',
    'TIME: HH:MM:SS (24-hour, as printed; pad with zeros if needed)',
    'If Date is missing use: DATE: NOT_FOUND',
    'If Time is missing use: TIME: NOT_FOUND'
  ].join('\n');
  const requestPayload = {
    contents: [
      {
        parts: [
          { text: prompt },
          { inline_data: { mime_type: 'application/pdf', data: base64Pdf } }
        ]
      }
    ],
    generationConfig: {
      temperature: 0.0,
      maxOutputTokens: 256,
      topP: 0.9,
      topK: 50
    }
  };
  const requestOptions = {
    method: 'POST',
    headers: geminiApiHeaders(apiKey),
    payload: JSON.stringify(requestPayload),
    muteHttpExceptions: true
  };

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = UrlFetchApp.fetch(url, requestOptions);
      const responseCode = response.getResponseCode();
      const responseBody = response.getContentText();

      if (responseCode === 503 || responseCode === 429) {
        console.error(
          `PDF表頭日時抽出 Gemini ${responseCode}: ${redactForLog(responseBody.substring(0, 400))}`
        );
        const ocrEarly = tryOcrHeaderAfterRateLimit(responseCode);
        if (ocrEarly) {
          return ocrEarly;
        }
        if (attempt < maxRetries) {
          const waitMs = computeGeminiRetryWaitMs(
            responseCode,
            responseBody,
            attempt,
            rateLimitDelays,
            retryDelay503
          );
          console.log(
            `PDF表頭抽出: ${waitMs / 1000}秒待機後にリトライ (試行 ${attempt + 1}/${maxRetries})`
          );
          Utilities.sleep(waitMs);
          continue;
        }
        break;
      }

      if (responseCode !== 200) {
        console.error(
          `PDF表頭日時抽出 Gemini エラー: ${responseCode} - ${redactForLog(responseBody.substring(0, 500))}`
        );
        break;
      }

      const parsed = parseInventoryReportHeaderFromGeminiResponseBody(responseBody);
      if (parsed) {
        return parsed;
      }
      console.warn('PDF表頭抽出: 200 だが候補・解析なし — リトライします');
      if (attempt < maxRetries) {
        Utilities.sleep(retryDelay503);
        continue;
      }
      break;
    } catch (error) {
      const errStr = String(error && error.message ? error.message : error);
      console.error('PDF表頭日時抽出 fetch エラー:', redactForLog(error));
      if (/Bandwidth quota exceeded/i.test(errStr) && attempt < maxRetries) {
        const waitMs = 45000 * attempt;
        console.log(
          `UrlFetch 帯域制限 — ${waitMs / 1000}秒待ってリトライ (試行 ${attempt + 1}/${maxRetries})`
        );
        Utilities.sleep(waitMs);
        continue;
      }
      break;
    }
  }

  try {
    console.log('PDF表頭日時: Gemini 不成功 — OCR で最終試行（Drive 再試行あり）');
    const ocrHdr = extractInventoryReportHeaderDateTimeFromOcr(pdfBlob);
    if (ocrHdr && ocrHdr.date) {
      console.log(
        'PDF表頭日時: OCR で取得 date=' + ocrHdr.date + ' time=' + (ocrHdr.time || '-')
      );
      return { date: ocrHdr.date, time: ocrHdr.time };
    }
  } catch (ocrErr) {
    console.error('PDF表頭 OCR 最終試行エラー:', ocrErr);
  }

  return { date: null, time: null, extractionFailed: true };
}

/**
 * Google Sheetsに結果を保存します。
 */
function saveToGoogleSheets(summary, email, emailIndex = 1, pdfBlob = null) {
  try {
    let geminiData = parseInventoryData(summary);
    geminiData = repairInventoryRowsBleed(geminiData);
    console.log(`Gemini解析データ: ${geminiData.length}行`);

    geminiData = repairRowsWithEmbeddedQuantityTriples(geminiData);
    const gDedup = dedupeInventoryDataByProductCode(geminiData);
    // 保存対象はGeminiがページ帯ごとに抽出した全行のみ。OCRは保存データへ追加・上書きしない。
    let inventoryData = gDedup;
    inventoryData = repairInventoryRowsBleed(inventoryData);
    inventoryData = repairRowsWithEmbeddedQuantityTriples(inventoryData);

    // Gemini 分割読み取りで漏れた必須コード（Tee-Bar / SCREW 等）を OCR から補完して保存
    if (pdfBlob && (CONFIG.REQUIRED_CODES || []).length > 0) {
      try {
        const ocrText = extractPdfTextWithOcr(pdfBlob);
        const rescued = extractRequiredInventoryRowsFromOcrFullText(ocrText, CONFIG.REQUIRED_CODES);
        if (rescued.length > 0) {
          const map = new Map();
          for (let i = 0; i < inventoryData.length; i++) {
            const item = inventoryData[i];
            const k = normalizeProductCode(item.productCode || '');
            if (k) map.set(k, item);
          }
          for (let r = 0; r < rescued.length; r++) {
            const row = rescued[r];
            const k = normalizeProductCode(row.productCode || '');
            if (!k || map.has(k)) continue;
            map.set(k, row);
            console.log('✅ OCR必須コード補完(保存): ' + k);
          }
          inventoryData = Array.from(map.values());
          console.log('OCR必須コード補完後: ' + inventoryData.length + '行');
        }
      } catch (ocrMergeErr) {
        console.error('OCR必須コード補完エラー（続行）:', ocrMergeErr);
      }
    }

    console.log(`マージ後データ: ${inventoryData.length}行`);
    validateInventoryQualityOrThrow(inventoryData);
    validateRowCountStabilityOrThrow(inventoryData.length);

    const spreadsheet = getPrivateSpreadsheet();
    let sheet = spreadsheet.getSheetByName(CONFIG.INVENTORY_SUMMARY_SHEET_NAME);
    
    if (!sheet) {
      sheet = spreadsheet.insertSheet(CONFIG.INVENTORY_SUMMARY_SHEET_NAME);
      console.log(`新規シート作成: ${CONFIG.INVENTORY_SUMMARY_SHEET_NAME}`);
      const headers = ['Product Code', 'Description', 'On Hand', 'Quantity SC w/o DN', 'Available', '更新時間'];
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    }
    
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      console.log(`既存データを完全削除: 2行目から${lastRow}行目まで`);
      sheet.deleteRows(2, lastRow - 1);
    }
    
    const updateTime = getPdfUpdateTime(email);
    
    if (inventoryData.length > 0) {
      const allData = inventoryData.map(item => [
        item.productCode || '',
        item.description || '',
        formatNumber(item.onHand || ''),
        formatNumber(item.scWithoutDN || ''),
        formatNumber(item.available || ''),
        updateTime
      ]);
      
      sheet.getRange(2, 1, allData.length, allData[0].length).setValues(allData);
      console.log(`データ入力完了: 2行目から${allData.length}行分のデータを入力`);
      verifyRequiredRowsInSheetOrThrow(sheet);
    }
    
    // バージョンスタンプをシートに記録（確認用）
    writeScriptVersionStamp(sheet);
    markSheetUpdated(inventoryData.length);
    saveLastSuccessRowCount(inventoryData.length);

    sheet.autoResizeColumns(1, sheet.getLastColumn());
    console.log(`在庫データ ${inventoryData.length}行をGoogle Sheetsに保存完了`);
    return inventoryData.length;
    
  } catch (error) {
    console.error('Google Sheets保存エラー:', error);
    throw error;
  }
}

/**
 * 帳票ヘッダ・欄名を商品コード行と誤認しない（ページまたぎで先頭行の数量が壊れるのを防ぐ）
 */
function isOcrInventoryNoiseLine(line) {
  const s = String(line || '').trim();
  if (!s) return true;
  if (/^Page\s*:/i.test(s)) return true;
  if (/^Page\s+\d+\s*$/i.test(s)) return true;
  if (/^Description$/i.test(s)) return true;
  if (/^Quantity$/i.test(s)) return true;
  if (/^On\s+Hand$/i.test(s)) return true;
  if (/SC\s*w\/?o\s*DN/i.test(s) && s.length < 40) return true;
  if (/^Available$/i.test(s)) return true;
  if (/^From\s+Start\b/i.test(s)) return true;
  if (/^To\s+End\b/i.test(s)) return true;
  if (/^Date\s+Back\s*:/i.test(s)) return true;
  return false;
}

/**
 * OCRテキストから決定的に在庫行を抽出（Geminiの誤抽出対策）
 */
function extractInventoryDataDeterministicFromPdf(pdfBlob) {
  const text = extractPdfTextWithOcr(pdfBlob);
  if (!text || !text.trim()) {
    throw new Error('再抽出用OCRテキストが空です');
  }

  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const rows = [];
  const seen = new Set();
  let currentCode = '';
  let buffer = '';
  const isNewCodeLine = (line) => /^([A-Z0-9][A-Z0-9-]{2,})\b/.test(line);

  const flushBuffer = () => {
    if (!currentCode || !buffer) return;
    const parsed = parseBufferedInventoryLine(currentCode, buffer);
    if (parsed && parsed.productCode && !seen.has(parsed.productCode)) {
      rows.push(parsed);
      seen.add(parsed.productCode);
    }
  };

  for (const line of lines) {
    if (isOcrInventoryNoiseLine(line)) {
      continue;
    }
    if (
      line.startsWith('Product Code') ||
      line.startsWith('Inventory Summary Report') ||
      line.startsWith('Category :') ||
      line.startsWith('Sub-Category :') ||
      line.startsWith('Prod. Code :') ||
      line.startsWith('Warehouse :') ||
      line.startsWith('Date Back :') ||
      line.startsWith('KIRII (HONG KONG) LIMITED') ||
      line.startsWith('Date :') ||
      line.startsWith('Time :') ||
      line.startsWith('-- ') ||
      line.includes('End of Report')
    ) {
      continue;
    }

    if (isNewCodeLine(line)) {
      flushBuffer();
      const m = line.match(/^([A-Z0-9][A-Z0-9-]{2,})\s*(.*)$/);
      currentCode = normalizeProductCode(m ? m[1] : '');
      buffer = m ? (m[2] || '') : '';
      continue;
    }

    if (currentCode) {
      buffer = `${buffer} ${line}`.trim();
    }
  }
  flushBuffer();

  const fullTextRows = extractInventoryRowsFromOcrFullText(text);
  for (let i = 0; i < fullTextRows.length; i++) {
    const row = fullTextRows[i];
    const code = normalizeProductCode(row.productCode || '');
    if (!code || seen.has(code)) continue;
    rows.push(row);
    seen.add(code);
  }

  const targetedRows = extractRequiredInventoryRowsFromOcrFullText(text, CONFIG.REQUIRED_CODES || []);
  for (let i = 0; i < targetedRows.length; i++) {
    const row = targetedRows[i];
    const code = normalizeProductCode(row.productCode || '');
    if (!code || seen.has(code)) continue;
    console.log(`✅ 必須コードOCR指定補完: ${code}`);
    rows.push(row);
    seen.add(code);
  }

  if (rows.length === 0) {
    throw new Error('決定的再抽出で在庫行が0件でした');
  }

  return dedupeInventoryDataByProductCode(rows);
}

/**
 * Drive OCR は表の改行や列位置が崩れることがあるため、全文から
 * 「商品コード + 説明 + 小数点2桁の3数量」を直接抽出して不足行を補完する。
 */
function extractInventoryRowsFromOcrFullText(text) {
  const rows = [];
  try {
    const normalized = String(text || '')
      .replace(/\r/g, '\n')
      .replace(/[ \t]+/g, ' ')
      .replace(/\n+/g, ' ')
      .trim();
    if (!normalized) return rows;

    const codePattern = '[A-Z0-9]{1,4}-[A-Z0-9-]{2,}|[A-Z0-9]{6,}[A-Z0-9-]*';
    const rowRe = new RegExp(
      '(?:^|\\s)(' +
        codePattern +
        ')\\s+(.+?)\\s+(-?[\\d,]+\\.\\d{2})\\s+(-?[\\d,]+\\.\\d{2})\\s+(-?[\\d,]+\\.\\d{2})(?=\\s+(?:' +
        codePattern +
        '|End\\s+of\\s+Report\\b|$))',
      'g'
    );

    let m;
    while ((m = rowRe.exec(normalized)) !== null) {
      const code = normalizeProductCode(correctProductCodeErrors(m[1]));
      const desc = normalizeText(String(m[2] || '').trim());
      if (!code || !desc || isOcrInventoryNoiseLine(code)) continue;
      const nums = normalizeInventoryNumbers(m[3], m[4], m[5]);
      rows.push({
        productCode: code,
        description: desc,
        onHand: nums.onHand,
        scWithoutDN: nums.scWithoutDN,
        available: nums.available
      });
    }
  } catch (error) {
    console.error('OCR全文補完抽出エラー:', error);
  }
  return rows;
}

function escapeRegExp(text) {
  return String(text || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * 必須コードは通常パースが崩れても、コード位置から最初の3数量を直接読む。
 * 不足コードを黙って保存しないための最後の決定論的補完。
 */
function extractRequiredInventoryRowsFromOcrFullText(text, requiredCodes) {
  const rows = [];
  try {
    const normalized = String(text || '')
      .replace(/\r/g, '\n')
      .replace(/[ \t]+/g, ' ')
      .replace(/\n+/g, ' ')
      .trim();
    if (!normalized) return rows;

    for (let i = 0; i < (requiredCodes || []).length; i++) {
      const requiredCode = normalizeProductCode(requiredCodes[i] || '');
      if (!requiredCode) continue;

      const codeRe = new RegExp('(?:^|\\s)(' + escapeRegExp(requiredCode) + ')\\s+', 'i');
      const m = codeRe.exec(normalized);
      if (!m) {
        console.warn(`⚠️ 必須コードOCR指定補完: OCR全文内に見つかりません: ${requiredCode}`);
        continue;
      }

      const codeStart = m.index + m[0].indexOf(m[1]);
      const afterCodeStart = codeStart + m[1].length;
      const windowText = normalized.slice(afterCodeStart, afterCodeStart + 700).trim();
      const qtyRe = /-?[\d,]+\.\d{2}\b/g;
      const nums = [];
      let qm;
      while ((qm = qtyRe.exec(windowText)) !== null) {
        nums.push({ raw: qm[0], index: qm.index });
        if (nums.length === 3) break;
      }
      if (nums.length < 3) {
        console.warn(`⚠️ 必須コードOCR指定補完: 数量3つを取得できません: ${requiredCode}`);
        continue;
      }

      const desc = normalizeText(windowText.slice(0, nums[0].index).trim());
      if (!desc) {
        console.warn(`⚠️ 必須コードOCR指定補完: 説明が空です: ${requiredCode}`);
        continue;
      }

      const values = normalizeInventoryNumbers(nums[0].raw, nums[1].raw, nums[2].raw);
      rows.push({
        productCode: requiredCode,
        description: desc,
        onHand: values.onHand,
        scWithoutDN: values.scWithoutDN,
        available: values.available
      });
    }
  } catch (error) {
    console.error('必須コードOCR指定補完エラー:', error);
  }
  return rows;
}

/**
 * 商品コード重複時は後勝ちで1行に集約
 */
function dedupeInventoryDataByProductCode(inventoryData) {
  const map = new Map();
  for (const item of inventoryData || []) {
    const key = normalizeProductCode(item.productCode || '');
    if (!key) continue;
    map.set(key, {
      productCode: key,
      description: item.description || '',
      onHand: item.onHand || '',
      scWithoutDN: item.scWithoutDN || '',
      available: item.available || ''
    });
  }
  return Array.from(map.values());
}

/**
 * OCRで折返し混在の1レコードを解析
 */
function parseBufferedInventoryLine(productCode, bufferedText) {
  try {
    const text = String(bufferedText || '').replace(/\s+/g, ' ').trim();
    if (!text) return null;

    // 帳票の数量は必ず小数点2桁（0.4mm 等の説明文は除外）
    const qtyRe = /-?[\d,]+\.\d{2}\b/g;
    const nums = [];
    let m;
    while ((m = qtyRe.exec(text)) !== null) {
      nums.push({ raw: m[0], index: m.index });
    }
    if (nums.length < 3) return null;

    const last3 = nums.slice(-3);
    const desc = text.slice(0, last3[0].index).trim();
    if (!desc) return null;

    const normalized = normalizeInventoryNumbers(last3[0].raw, last3[1].raw, last3[2].raw);
    return {
      productCode: normalizeProductCode(productCode),
      description: desc,
      onHand: normalized.onHand,
      scWithoutDN: normalized.scWithoutDN,
      available: normalized.available
    };
  } catch (error) {
    console.error('折返し行解析エラー:', error);
    return null;
  }
}

/**
 * OCRベースを優先し、Gemini結果で不足コードを補完（レガシー。行数が大きく減るため save では非推奨）
 */
function mergeInventoryDataByProductCode(baseRows, supplementRows) {
  const map = new Map();

  for (const item of baseRows || []) {
    const key = normalizeProductCode(item.productCode || '');
    if (!key) continue;
    map.set(key, {
      productCode: key,
      description: item.description || '',
      onHand: item.onHand || '',
      scWithoutDN: item.scWithoutDN || '',
      available: item.available || ''
    });
  }

  for (const item of supplementRows || []) {
    const key = normalizeProductCode(item.productCode || '');
    if (!key || map.has(key)) continue;
    map.set(key, {
      productCode: key,
      description: item.description || '',
      onHand: item.onHand || '',
      scWithoutDN: item.scWithoutDN || '',
      available: item.available || ''
    });
  }

  return Array.from(map.values());
}

/**
 * Gemini 全行を重複除去した集合を主とし、OCRは一致コードのみ数値を上書き（OCR 数十行でも本解析行数を潰さない）
 */
function mergeGeminiDedupeWithOcrOverlay(geminiRows, ocrRows) {
  const map = new Map();
  const gDedup = dedupeInventoryDataByProductCode(geminiRows || []);
  for (let i = 0; i < gDedup.length; i++) {
    const item = gDedup[i];
    const key = normalizeProductCode(item.productCode || '');
    if (!key) continue;
    map.set(key, {
      productCode: key,
      description: item.description || '',
      onHand: item.onHand || '',
      scWithoutDN: item.scWithoutDN || '',
      available: item.available || ''
    });
  }
  for (let j = 0; j < (ocrRows || []).length; j++) {
    const item = ocrRows[j];
    const key = normalizeProductCode(item.productCode || '');
    if (!key) continue;
    map.set(key, {
      productCode: key,
      description: item.description || '',
      onHand: item.onHand || '',
      scWithoutDN: item.scWithoutDN || '',
      available: item.available || ''
    });
  }
  return Array.from(map.values());
}

function extractEmbeddedQuantityTripleFromDescription(description) {
  const text = String(description || '').replace(/\s+/g, ' ').trim();
  if (!text) return null;

  const qtyRe = /-?[\d,]+\.\d{2}\b/g;
  const nums = [];
  let m;
  while ((m = qtyRe.exec(text)) !== null) {
    nums.push({ raw: m[0], index: m.index, end: qtyRe.lastIndex });
  }
  if (nums.length < 3) return null;

  for (let i = 0; i <= nums.length - 3; i++) {
    const a = nums[i];
    const b = nums[i + 1];
    const c = nums[i + 2];
    const betweenAB = text.slice(a.end, b.index).trim();
    const betweenBC = text.slice(b.end, c.index).trim();
    if (betweenAB || betweenBC) continue;

    const desc = text.slice(0, a.index).trim();
    if (!desc) continue;
    const values = normalizeInventoryNumbers(a.raw, b.raw, c.raw);
    return {
      description: desc,
      onHand: values.onHand,
      scWithoutDN: values.scWithoutDN,
      available: values.available
    };
  }

  return null;
}

function repairRowsWithEmbeddedQuantityTriples(rows) {
  const required = new Set((CONFIG.REQUIRED_CODES || []).map(function (code) {
    return normalizeProductCode(code || '');
  }));
  return (rows || []).map(function (row) {
    const code = normalizeProductCode(row && row.productCode || '');
    const repair = extractEmbeddedQuantityTripleFromDescription(row && row.description);
    if (!repair) return row;

    const oldValues =
      quantityToFixed2String(row.onHand) + '/' +
      quantityToFixed2String(row.scWithoutDN) + '/' +
      quantityToFixed2String(row.available);
    const newValues =
      quantityToFixed2String(repair.onHand) + '/' +
      quantityToFixed2String(repair.scWithoutDN) + '/' +
      quantityToFixed2String(repair.available);
    const level = required.has(code) ? '✅ 必須コード数量修復' : '✅ 説明内数量修復';
    console.log(`${level}: ${code} ${oldValues} -> ${newValues}`);

    return {
      productCode: row.productCode,
      description: repair.description,
      onHand: repair.onHand,
      scWithoutDN: repair.scWithoutDN,
      available: repair.available
    };
  });
}

function quantityToFixed2String(value) {
  const n = parseFloat(String(value == null ? '' : value).replace(/,/g, ''));
  if (!Number.isFinite(n)) return String(value == null ? '' : value).trim();
  return n.toFixed(2);
}

function assertRequiredRowsAndValuesOrThrow(rows, label) {
  const requiredCodes = CONFIG.REQUIRED_CODES || [];
  const expected = CONFIG.REQUIRED_CODE_EXPECTED_VALUES || {};
  if (requiredCodes.length === 0) return;

  const map = new Map();
  for (let i = 0; i < (rows || []).length; i++) {
    const item = rows[i];
    const key = normalizeProductCode(item.productCode || '');
    if (!key) continue;
    map.set(key, item);
  }

  const missing = [];
  const mismatches = [];
  for (let r = 0; r < requiredCodes.length; r++) {
    const code = normalizeProductCode(requiredCodes[r] || '');
    const row = map.get(code);
    if (!row) {
      missing.push(code);
      continue;
    }

    const exp = expected[code];
    if (exp) {
      const actualOnHand = quantityToFixed2String(row.onHand);
      const actualSc = quantityToFixed2String(row.scWithoutDN);
      const actualAvailable = quantityToFixed2String(row.available);
      if (
        actualOnHand !== quantityToFixed2String(exp.onHand) ||
        actualSc !== quantityToFixed2String(exp.scWithoutDN) ||
        actualAvailable !== quantityToFixed2String(exp.available)
      ) {
        mismatches.push(
          `${code}: actual=${actualOnHand}/${actualSc}/${actualAvailable}, expected=${quantityToFixed2String(exp.onHand)}/${quantityToFixed2String(exp.scWithoutDN)}/${quantityToFixed2String(exp.available)}`
        );
      }
    }
  }

  if (missing.length > 0 || mismatches.length > 0) {
    const parts = [];
    if (missing.length > 0) parts.push(`missing=${missing.join(', ')}`);
    if (mismatches.length > 0) parts.push(`mismatch=${mismatches.join(' ; ')}`);
    throw new Error(`${label} 必須行チェック失敗: ${parts.join(' / ')}。既存データ保護のため更新を中止しました`);
  }

  console.log(`✅ ${label} 必須行チェックOK: ${requiredCodes.join(', ')}`);
}

function assertNoEmbeddedQuantityTriplesOrThrow(rows, label) {
  const badRows = [];
  for (let i = 0; i < (rows || []).length; i++) {
    const row = rows[i];
    const code = normalizeProductCode(row && row.productCode || '');
    const repair = extractEmbeddedQuantityTripleFromDescription(row && row.description);
    if (code && repair) {
      badRows.push(code);
      if (badRows.length >= 20) break;
    }
  }
  if (badRows.length > 0) {
    throw new Error(
      `${label} 説明列に数量が残っています: ${badRows.join(', ')}。列ずれ防止のため更新を中止しました`
    );
  }
  console.log(`✅ ${label} 説明列数量混入チェックOK`);
}

function assertAllRowsWellFormedOrThrow(rows, label) {
  const badRows = [];
  const codeRe = /^[A-Z0-9][A-Z0-9-]{2,}$/;
  for (let i = 0; i < (rows || []).length; i++) {
    const row = rows[i] || {};
    const code = normalizeProductCode(row.productCode || '');
    const desc = String(row.description || '').trim();
    const onHand = quantityToFixed2String(row.onHand);
    const sc = quantityToFixed2String(row.scWithoutDN);
    const available = quantityToFixed2String(row.available);
    if (
      !code ||
      !codeRe.test(code) ||
      !desc ||
      !/^-?\d+(?:\.\d{2})$/.test(onHand) ||
      !/^-?\d+(?:\.\d{2})$/.test(sc) ||
      !/^-?\d+(?:\.\d{2})$/.test(available)
    ) {
      badRows.push(code || `(row ${i + 2})`);
      if (badRows.length >= 20) break;
    }
  }
  if (badRows.length > 0) {
    throw new Error(`${label} 行形式チェック失敗: ${badRows.join(', ')}。全行必須のため更新を中止しました`);
  }
  console.log(`✅ ${label} 全行形式チェックOK: ${(rows || []).length}行`);
}

function verifyRequiredRowsInSheetOrThrow(sheet) {
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    throw new Error('保存後チェック失敗: InventorySummaryReport にデータ行がありません');
  }
  const values = sheet.getRange(2, 1, lastRow - 1, 5).getValues();
  const rows = values.map(function (r) {
    return {
      productCode: r[0],
      description: r[1],
      onHand: r[2],
      scWithoutDN: r[3],
      available: r[4]
    };
  });
  assertAllRowsWellFormedOrThrow(rows, '保存後シート');
  assertNoEmbeddedQuantityTriplesOrThrow(rows, '保存後シート');
  assertRequiredRowsAndValuesOrThrow(rows, '保存後シート');
}

/**
 * 低品質データによる誤更新を防ぐ品質チェック
 */
function validateInventoryQualityOrThrow(inventoryData) {
  if (!inventoryData || inventoryData.length === 0) {
    throw new Error('解析結果が0行のため、既存データ保護のため更新を中止しました');
  }

  const minRows = CONFIG.MIN_EXPECTED_ROWS || 0;
  if (minRows > 0 && inventoryData.length < minRows) {
    console.error(`⚠️ 解析行数不足: ${inventoryData.length}行（目標 ${minRows}行）。更新は継続します`);
  }

  assertAllRowsWellFormedOrThrow(inventoryData, '保存前');
  assertNoEmbeddedQuantityTriplesOrThrow(inventoryData, '保存前');

  if ((CONFIG.REQUIRED_CODES || []).length > 0) {
    if (CONFIG.STRICT_REQUIRED_CODES) {
      assertRequiredRowsAndValuesOrThrow(inventoryData, '保存前');
    } else {
      try {
        assertRequiredRowsAndValuesOrThrow(inventoryData, '保存前');
      } catch (error) {
        console.error(`⚠️ ${error.message}（警告のみ。更新は継続）`);
      }
    }
  }
}

/**
 * 前回成功時の行数から大きく乖離していないか検証
 */
function validateRowCountStabilityOrThrow(currentRows) {
  if (CONFIG.ENABLE_ROW_COUNT_STABILITY_CHECK !== true) {
    return;
  }
  const lastRows = getLastSuccessRowCount();
  if (!lastRows || lastRows <= 0) return;

  const absDiff = Math.abs(currentRows - lastRows);
  const pctDiff = (absDiff / lastRows) * 100;
  const maxPct = CONFIG.MAX_ROW_DRIFT_PERCENT || 10;
  const maxAbs = CONFIG.MAX_ROW_DRIFT_ABS || 20;

  if (absDiff >= maxAbs && pctDiff >= maxPct) {
    throw new Error(
      `処理件数が前回成功値から大きく乖離しています: current=${currentRows}, last=${lastRows}, diff=${absDiff} (${pctDiff.toFixed(1)}%)`
    );
  }
}

/**
 * スクリプトのバージョンスタンプをシートに記録
 */
function writeScriptVersionStamp(sheet) {
  try {
    const now = new Date();
    const hk = new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
    const stamp = `${CONFIG.SCRIPT_VERSION} @ ${hk.toLocaleString('ja-JP')}`;
    // 影響の少ない列へ書き込み（Z1）
    sheet.getRange('Z1').setValue(stamp);
    console.log(`スクリプトバージョン記録: ${stamp}`);
  } catch (e) {
    console.error('スクリプトバージョン記録に失敗:', e);
  }
}

/**
 * 在庫数量をシート用にフォーマット（PDF と同様に小数点2桁・千桁カンマ）
 */
function formatNumber(value) {
  try {
    if (value === '' || value == null) return '';

    const numStr = String(value).replace(/[^\d.-]/g, '');
    const num = parseFloat(numStr);

    if (isNaN(num)) return String(value);

    return num.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  } catch (error) {
    console.error('数字フォーマットエラー:', error);
    return value;
  }
}

/**
 * 文字を正規化してASCIIに変換します
 */
function normalizeText(text) {
  try {
    const greekToAscii = {
      'Τ': 'T', 'Ν': 'N', 'Ι': 'I', 'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': 'TH', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P', 'Ρ': 'R', 'Σ': 'S', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'CH', 'Ψ': 'PS', 'Ω': 'W'
    };
    
    let normalized = text;
    for (const [greek, ascii] of Object.entries(greekToAscii)) {
      normalized = normalized.replace(new RegExp(greek, 'g'), ascii);
    }
    
    return normalized;
  } catch (error) {
    console.error('文字正規化エラー:', error);
    return text;
  }
}

/**
 * 商品コードの読み取り失敗を修正します
 */
function correctProductCodeErrors(text) {
  try {
    let corrected = text;
    
    const productCodeCorrections = {
      'US05132045M10800': 'US05132045MI0800',
      'US05132045M10900': 'US05132045MI0900',
      'UT05125045M10800': 'UT05125045MI0800',
      'GSW0410800B': 'GSW04I0800B',
      'GSW0411000B': 'GSW04I1000B',
      'GSC0810800B': 'GSC08I0800B',
      'GSC0811000B': 'GSC08I1000B',
      // 帳票・OCRで「I」の次に 1 が重なる表記（正: GSC08I1000B = Main Channel L=10'）
      'GSC08I11000B': 'GSC08I1000B'
    };
    
    for (const [incorrect, correct] of Object.entries(productCodeCorrections)) {
      const regex = new RegExp(incorrect.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
      if (corrected.includes(incorrect)) {
        corrected = corrected.replace(regex, correct);
        console.log(`✅ 商品コード修正: ${incorrect} -> ${correct}`);
      }
    }
    
    return corrected;
  } catch (error) {
    console.error('商品コード修正エラー:', error);
    return text;
  }
}

/**
 * 説明に「3数量のあと次の商品コード」が混入している行だけを再パース（マークダウン列ずれの修復）
 */
function descriptionHasQtyBleedWithNextCode(desc) {
  return /\s-?[\d,]+\.\d{2}\s+-?[\d,]+\.\d{2}\s+-?[\d,]+\.\d{2}\s+[A-Z0-9][A-Z0-9-]{2,}\b/.test(
    String(desc || '')
  );
}

function repairInventoryRowsBleed(inventoryData) {
  const out = [];
  for (let i = 0; i < (inventoryData || []).length; i++) {
    const row = inventoryData[i];
    const code = String(row.productCode || '').trim();
    const desc = String(row.description || '');
    if (code && descriptionHasQtyBleedWithNextCode(desc)) {
      const expanded = expandMarkdownColumnsToInventoryRows([code, desc, '', '', '']);
      if (expanded.length > 0) {
        for (let j = 0; j < expanded.length; j++) {
          out.push(expanded[j]);
        }
        continue;
      }
    }
    out.push(row);
  }
  return out;
}

/**
 * Gemini/OCR が1行に複数商品を連結したとき、コード+説明+3数値ごとに分割する
 * 例: BD-060 … 1,260.00 0.00 1,260.00 BD-061 … 958.00 …
 */
function expandMarkdownColumnsToInventoryRows(columns) {
  const out = [];
  const code0 = normalizeProductCode(
    normalizeText(correctProductCodeErrors(columns[0] || ''))
  );
  if (!code0) {
    return out;
  }

  const isQty = function (s) {
    return /^-?[\d,]+\.\d{2}$/.test(String(s || '').trim());
  };

  let blob = String(columns[1] || '').trim();
  const c2 = String(columns[2] || '').trim();
  const c3 = String(columns[3] || '').trim();
  const c4 = String(columns[4] || '').trim();
  if (isQty(c2) && isQty(c3) && isQty(c4)) {
    blob = (blob ? blob + ' ' : '') + c2 + ' ' + c3 + ' ' + c4;
  }

  let remaining = (code0 + ' ' + blob).trim();
  const rowPattern = /^([0-9A-Z][0-9A-Z-]{2,})\s+(.+?)\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})\s+(-?[\d,]+\.\d{2})(?:\s+(.*))?$/;
  let guard = 0;
  while (remaining && guard++ < 100) {
    const m = remaining.match(rowPattern);
    if (!m) {
      break;
    }
    const code = normalizeProductCode(correctProductCodeErrors(m[1]));
    const desc = normalizeText(m[2].trim());
    const nums = normalizeInventoryNumbers(m[3], m[4], m[5]);
    out.push({
      productCode: code,
      description: desc,
      onHand: nums.onHand,
      scWithoutDN: nums.scWithoutDN,
      available: nums.available
    });
    remaining = (m[6] || '').trim();
  }
  return out;
}

/**
 * 在庫データのテキストを解析して配列に変換
 */
function parseInventoryData(summary) {
  try {
    const lines = summary.split('\n');
    const inventoryData = [];
    let skippedLines = 0;
    let processedLines = 0;
    
    console.log(`解析開始: 総行数 ${lines.length}行`);
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // 空行や区切り線をスキップ
      if (!line || line === '' || line.match(/^[\s\|-]+$/) || line.includes('---')) {
        continue;
      }
      
      // パイプ区切りの行を処理
      if (line.includes('|')) {
        const columns = line.split('|').map(col => col.trim()).filter(col => col !== '');
        
        // ヘッダー行をスキップ
        if (columns.length > 0 && columns[0].toLowerCase().includes('product code')) {
          console.log(`ヘッダー行をスキップ: ${line.substring(0, 50)}...`);
          continue;
        }
        
        // 5列以上ある行を処理（1セルに複数商品が連結されている場合は分割）
        if (columns.length >= 5) {
          const productCodeHead = normalizeProductCode(
            normalizeText(correctProductCodeErrors(columns[0] || ''))
          );
          if (!productCodeHead || productCodeHead === '') {
            skippedLines++;
            continue;
          }
          if (
            productCodeHead.match(/^[A-Z-]+$/i) &&
            columns[1] === '' &&
            columns[2] === '' &&
            columns[3] === '' &&
            columns[4] === ''
          ) {
            console.log(`カテゴリ行をスキップ: ${productCodeHead}`);
            skippedLines++;
            continue;
          }

          const expanded = expandMarkdownColumnsToInventoryRows(columns);
          if (expanded.length > 0) {
            for (let ei = 0; ei < expanded.length; ei++) {
              const row = expanded[ei];
              if (!row.productCode) {
                continue;
              }
              if (
                row.productCode.match(/^[A-Z-]+$/i) &&
                !row.description &&
                !row.onHand &&
                !row.scWithoutDN &&
                !row.available
              ) {
                skippedLines++;
                continue;
              }
              inventoryData.push(row);
              processedLines++;
            }
          } else {
            const joinedBlob = [columns[1], columns[2], columns[3], columns[4]]
              .map(function (x) {
                return String(x || '').trim();
              })
              .filter(Boolean)
              .join(' ');
            const expandedJoin = expandMarkdownColumnsToInventoryRows([
              productCodeHead,
              joinedBlob,
              '',
              '',
              ''
            ]);
            if (expandedJoin.length > 0) {
              for (let ej = 0; ej < expandedJoin.length; ej++) {
                const row = expandedJoin[ej];
                if (row.productCode) {
                  inventoryData.push(row);
                  processedLines++;
                }
              }
            } else {
              const normalizedNumbers = normalizeInventoryNumbers(
                columns[2] || '',
                columns[3] || '',
                columns[4] || ''
              );
              inventoryData.push({
                productCode: productCodeHead,
                description: columns[1] || '',
                onHand: normalizedNumbers.onHand,
                scWithoutDN: normalizedNumbers.scWithoutDN,
                available: normalizedNumbers.available
              });
              processedLines++;
            }
          }
        } else if (columns.length > 0) {
          // 列数が不足している行をログに記録
          console.log(`⚠️ 列数不足の行をスキップ (${columns.length}列): ${line.substring(0, 80)}...`);
          skippedLines++;
        }
      } else {
        // パイプがない行をスキップ（ただし、重要な商品コードが含まれている場合は警告）
        if (line.match(/^(AC-261|AC-262|AC-263|AC-264|BD-060|BD-061|BD-062|BD-063|BD-064|BD-065|BD-067|FC-056)/)) {
          console.log(`⚠️ パイプ区切りではない行に重要な商品コードを検出: ${line.substring(0, 80)}...`);
        }
        skippedLines++;
      }
    }
    
    console.log(`解析完了: ${inventoryData.length}件の在庫アイテムを抽出 (処理: ${processedLines}行, スキップ: ${skippedLines}行)`);

    if (CONFIG.GEMINI_TARGETED_CODE_RESCUE === true) {
      const zMkCodes = ['AC-261', 'AC-262', 'AC-263', 'AC-264', 'BD-060', 'BD-061', 'BD-062', 'BD-063', 'BD-064', 'BD-065', 'BD-067', 'FC-056'];
      const extractedCodes = inventoryData.map(item => item.productCode);
      const missingCodes = zMkCodes.filter(code => !extractedCodes.includes(code));
      if (missingCodes.length > 0) {
        console.error(`❌ 警告: 以下のZ-MKシリーズが抽出されていません: ${missingCodes.join(', ')}`);
      } else {
        console.log(`✅ Z-MKシリーズの全商品コードが正常に抽出されました`);
      }
    }

    return inventoryData;
  } catch (error) {
    console.error('在庫データ解析エラー:', error);
    console.error('エラー発生時のsummary（最初の500文字）:', summary.substring(0, 500));
    return [];
  }
}

/**
 * 作業終了お知らせメールを送信します。
 */
function sendCompletionNotification(executionResult) {
  try {
    console.log('sendCompletionNotification開始');
    const hongKongTime = getHongKongNow();
    const completionTime = hongKongTime.toLocaleString('ja-JP');

    const success = executionResult && executionResult.success;
    const processedCount = executionResult && executionResult.processedCount || 0;
    const skippedCount = executionResult && executionResult.skippedCount || 0;

    const subject = success
      ? 'GAS在庫メール受信処理 完了お知らせ'
      : '【要確認】GAS在庫メール処理 警告';

    const audit = executionResult && executionResult.integrityAudit;
    const auditBlock = formatIntegrityAuditSectionForEmail(audit);
    const closingLine =
      audit && audit.integrityOk === false
        ? '照合情報を確認してください。'
        : '処理は正常に完了しています。';

    let body = '';
    if (success) {
      const noDataProcessed = processedCount === 0 && skippedCount === 0;
      body = noDataProcessed
        ? `
該当するデータがなかったため、処理は行っていません。

確認時刻: ${completionTime}
処理件数: ${processedCount}件
スキップ件数: ${skippedCount}件

処理内容:
- Gmail在庫メールの検索・解析
- PDF添付ファイルのGemini AI解析
- Google Sheetsへの在庫データ保存
- StockシートのVLOOKUP式設定
${auditBlock}
${closingLine}
`
        : `
在庫データの処理が正常に完了しました。

処理完了時刻: ${completionTime}
処理件数: ${processedCount}件
スキップ件数: ${skippedCount}件

処理内容:
- Gmail在庫メールの検索・解析
- PDF添付ファイルのGemini AI解析
- Google Sheetsへの在庫データ保存
- StockシートのVLOOKUP式設定
${auditBlock}
${closingLine}
`;
    } else {
      body = `
在庫データ処理でエラーまたは未完了の状態が発生しました。

発生時刻: ${completionTime}
${executionResult.error ? `エラーメッセージ: ${executionResult.error}` : ''}

Google Sheets への書き込みや在庫更新が行われていない可能性があります。ログを確認し、必要に応じて手動対応をお願いします。
`;
    }

    console.log('メール送信実行中...');
    getAlertRecipients().forEach(function (to) {
      GmailApp.sendEmail(to, subject, body);
    });

    console.log(success ? '✅ 正常完了メールを送信しました' : '⚠️ 警告メールを送信しました');
  } catch (error) {
    console.error('作業終了お知らせメールの送信に失敗しました:', error);
  }
}

/**
 * エラー通知メールを送信します。
 */
function sendErrorNotification(error, contextInfo) {
  try {
    const hongKongTime = getHongKongNow();
    const notificationTime = hongKongTime.toLocaleString('ja-JP');
    const failureReason = contextInfo && contextInfo.failureReason ? contextInfo.failureReason : 'UNSPECIFIED';
    const processedEmail = contextInfo && contextInfo.processedEmail ? contextInfo.processedEmail : null;
    const additionalInfo = contextInfo && contextInfo.additionalInfo ? contextInfo.additionalInfo : '';
    
    let emailDetails = '';
    if (processedEmail) {
      const emailInfo = formatDateTimeInHK(processedEmail.getDate());
      emailDetails = `
処理対象メール情報:
- 件名: ${processedEmail.getSubject()}
- 受信日時(香港時間): ${emailInfo.dateTimeLabel}
- 送信者: ${processedEmail.getFrom()}
- 添付ファイル数: ${processedEmail.getAttachments().length}件
`;
    }
    
    const body = `
Gmail在庫PDF処理スクリプトでエラーが発生しました。

発生時刻(HK): ${notificationTime}
失敗区分: ${failureReason}
エラーメッセージ: ${redactForLog((error && error.message) || String(error))}
スタックトレース:
${redactForLog((error && error.stack) || '-')}
${emailDetails}${additionalInfo ? `\n追加情報:\n${additionalInfo}` : ''}
`;
    
    GmailApp.sendEmail(
      CONFIG.GMAIL_ADDRESS,
      '【要確認】GASスクリプトエラー通知 (Gmail Inventory Processor)',
      body
    );
  } catch (notificationError) {
    console.error('エラー通知の送信自体に失敗しました:', notificationError);
  }
}

/**
 * StockシートにVLOOKUP式とM2式を設定
 */
function setStockFormulas() {
  try {
    console.log('=== Stock式設定開始 ===');
    const ss = getPrivateSpreadsheet();
    console.log(`スプレッドシートID: ${ss.getId()}`);
    
    const stockSheet = ss.getSheetByName('Stock');
    console.log(`Stockシート: ${stockSheet ? '発見' : '見つからない'}`);
    
    if (!stockSheet) {
      console.error('Stockシートが見つかりません。Stockシートを作成します。');
      const newStockSheet = ss.insertSheet('Stock');
      console.log('Stockシートを作成しました');
      
      const headers = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M'];
      newStockSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      console.log('Stockシートのヘッダーを設定しました');
      
      return;
    }
    
    const lastRow = stockSheet.getRange('C:C').getValues().filter(String).length;
    console.log(`Stockシートのデータ行数: ${lastRow}`);
    
    if (lastRow < 2) {
      console.log('データが不足しているため、式の設定をスキップします');
      return;
    }
    
    console.log('U2, V2, W2にVLOOKUP式を設定中...');
    stockSheet.getRange('U2').setFormula('=IFERROR(VLOOKUP(TRIM($C2),InventorySummaryReport!$A:$E, 3, 0), 0)');
    stockSheet.getRange('V2').setFormula('=IFERROR(VLOOKUP(TRIM($C2),InventorySummaryReport!$A:$E, 4, 0), 0)');
    stockSheet.getRange('W2').setFormula('=IFERROR(VLOOKUP(TRIM($C2),InventorySummaryReport!$A:$E, 5, 0), 0)');
    console.log('✅ U2, V2, W2にVLOOKUP式を設定しました');
    
    if (lastRow > 2) {
      console.log(`U2:W2の式をU2:W${lastRow}までコピー中...`);
      const copyRange = stockSheet.getRange('U2:W2');
      const pasteRange = stockSheet.getRange(`U2:W${lastRow}`);
      copyRange.copyTo(pasteRange);
      console.log(`✅ U2:W2の式をU2:W${lastRow}までコピーしました`);
    }
    
    updateStockLatTimeColumn(ss, stockSheet, lastRow);
    
    console.log('Stockシートの式設定完了');
    
  } catch (error) {
    console.error('Stock式設定エラー:', error);
  }
}

/**
 * StockのLatTime列(Y列)にInventorySummaryReport!F2の値を一括反映
 * 参照式ではなく値を直接書くことで #REF! の連鎖を防ぐ
 */
function updateStockLatTimeColumn(ss, stockSheet, lastRow) {
  try {
    const safeLastRow = Math.max(lastRow || 0, 2);
    const rowCount = safeLastRow - 1; // 2行目開始
    const yLastRow = Math.max(stockSheet.getLastRow(), safeLastRow);
    const clearRange = stockSheet.getRange(`Y2:Y${yLastRow}`);
    const targetRange = stockSheet.getRange(`Y2:Y${safeLastRow}`);

    // 壊れた古い参照式を確実に除去
    clearRange.clearContent();

    const inventorySheet = ss.getSheetByName(CONFIG.INVENTORY_SUMMARY_SHEET_NAME);
    if (!inventorySheet) {
      console.error(`❌ ${CONFIG.INVENTORY_SUMMARY_SHEET_NAME}シートが見つかりません`);
      return;
    }

    const f2Display = String(inventorySheet.getRange('F2').getDisplayValue() || '').trim();
    const hasRefError = f2Display.toUpperCase().includes('#REF!');
    const hasAnyError = f2Display.startsWith('#');

    let latTimeValue = inventorySheet.getRange('F2').getValue();
    if (hasRefError || hasAnyError || latTimeValue === '' || latTimeValue == null) {
      // 参照先が壊れていてもStock側は復旧できるよう、現在時刻(HK)で代替
      latTimeValue = formatDateTimeInHK(new Date()).dateTimeLabel;
      console.warn(`⚠️ ${CONFIG.INVENTORY_SUMMARY_SHEET_NAME}!F2が異常値のため現在時刻で代替: ${f2Display}`);
    } else {
      console.log(`${CONFIG.INVENTORY_SUMMARY_SHEET_NAME}!F2の値: ${f2Display}`);
    }

    const values = Array.from({ length: rowCount }, () => [latTimeValue]);
    targetRange.setValues(values);
    console.log(`✅ LatTimeをY2:Y${safeLastRow}に一括設定しました（クリア範囲: Y2:Y${yLastRow}）`);
  } catch (error) {
    console.error('❌ LatTime列更新エラー:', error);
  }
}

/**
 * InventorySummaryReport!F2の設定を独立実行（Gemini API失敗時でも実行）
 */
function setInventorySummaryReportFormula() {
  try {
    console.log('=== InventorySummaryReport!F2設定開始 ===');
    const ss = getPrivateSpreadsheet();
    console.log(`スプレッドシートID: ${ss.getId()}`);

    const stockSheet = ss.getSheetByName('Stock');
    if (!stockSheet) {
      console.error('❌ Stockシートが見つかりません');
      return;
    }
    console.log('Stockシート: 発見');

    const lastRow = stockSheet.getRange('C:C').getValues().filter(String).length;
    console.log(`Stockシートのデータ行数: ${lastRow}`);
    if (lastRow < 2) {
      console.log('データが不足しているため、LatTimeの設定をスキップします');
      return;
    }

    updateStockLatTimeColumn(ss, stockSheet, lastRow);

    console.log('=== InventorySummaryReport!F2設定完了 ===');

  } catch (error) {
    console.error('InventorySummaryReport!F2設定エラー:', error);
  }
}

function getHongKongNow() {
  const now = new Date();
  return new Date(now.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
}

function getHongKongTodayLabel() {
  return getHongKongNow().toLocaleDateString('ja-JP');
}

function formatDateTimeInHK(date) {
  const hkDate = new Date(date.toLocaleString('en-US', { timeZone: 'Asia/Hong_Kong' }));
  return {
    dateLabel: hkDate.toLocaleDateString('ja-JP'),
    timeLabel: hkDate.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
    dateTimeLabel: hkDate.toLocaleString('ja-JP')
  };
}

/**
 * OCR崩れを吸収して商品コードを正規化します。
 */
function normalizeProductCode(code) {
  try {
    if (!code) return '';
    let normalized = String(code)
      .trim()
      .toUpperCase()
      .replace(/[|"'`]/g, '')
      .replace(/[‐‑‒–—―ー]/g, '-')
      .replace(/\s+/g, ' ');

    // "BD 030" -> "BD-030"
    normalized = normalized.replace(/^([A-Z]{1,4})\s+([A-Z0-9]+)$/, '$1-$2');
    // 許容文字以外を除去
    normalized = normalized.replace(/[^A-Z0-9-]/g, '');

    // ハイフン以降が数値系なら O を 0 に補正（例: BD-O30 -> BD-030）
    const m = normalized.match(/^([A-Z]{1,4})-([0-9O]+)$/);
    if (m) {
      normalized = `${m[1]}-${m[2].replace(/O/g, '0')}`;
    }

    if (normalized === 'GSC08I11000B') {
      normalized = 'GSC08I1000B';
    }

    return normalized;
  } catch (error) {
    console.error('商品コード正規化エラー:', error);
    return code;
  }
}

/**
 * 在庫3数値は PDF / マークダウン列の順をそのまま保持する（列ずれデータを並べ替えると誤った値になる）
 */
function normalizeInventoryNumbers(onHand, scWithoutDN, available) {
  const clean = function (v) {
    return String(v == null ? '' : v).trim();
  };
  return {
    onHand: clean(onHand),
    scWithoutDN: clean(scWithoutDN),
    available: clean(available)
  };
}

/**
 * Gmailトリガーを設定します
 * 注意: Gmailのフィルターで特定のラベルを設定する必要があります
 */
function setupGmailTrigger() {
  try {
    // 既存の重複トリガーを整理
    const triggers = ScriptApp.getProjectTriggers();
    for (const trigger of triggers) {
      if (trigger.getHandlerFunction() === 'main') {
        ScriptApp.deleteTrigger(trigger);
      }
    }

    // 受信取りこぼし対策の時限バックアップ（間隔は CONFIG.BACKUP_POLLING_MINUTES）
    ensureBackupTimeTrigger();
    ensureScheduledDoubleCheckTriggers();
    
    console.log('Gmailトリガー設定手順（緊急停止中・トリガー0件なら先に restoreNormalOperationAfterEmergency()）:');
    console.log('1. Gmailでフィルターを作成:');
    console.log('   - 検索条件: ' + buildGmailQuery());
    console.log('   - アクション: ラベル「ProcessInventory」を適用');
    console.log('2. Apps Scriptのエディタで:');
    console.log('   - トリガー → トリガーを追加');
    console.log('   - イベントのソース: Gmail');
    console.log('   - イベントの種類: メールが届いたとき');
    console.log('   - 関数: onGmailReceived');
    console.log('   - ラベル: ProcessInventory');
    console.log(`3. バックアップ時間トリガー: ${getBackupPollingMinutes()}分ごと（自動作成、0 で無効）`);
    console.log(`4. 定時ダブルチェック: 平日 06:00-09:00 / 12:00-13:30 / 17:30-19:30（自動作成）`);
    
    console.log('Gmailトリガー設定手順を表示しました。');
    
  } catch (error) {
    console.error(`Gmailトリガー設定エラー: ${error.toString()}`);
  }
}

/**
 * onGmailReceived のバックアップ時間トリガーを作成（重複削除＋無効化）
 */
function ensureBackupTimeTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  const mins = getBackupPollingMinutes();
  const clockOnGmail = triggers.filter(t =>
    t.getHandlerFunction() === 'onGmailReceived' &&
    t.getTriggerSource() === ScriptApp.TriggerSource.CLOCK
  );

  if (mins <= 0) {
    clockOnGmail.forEach(function (t) {
      ScriptApp.deleteTrigger(t);
    });
    if (clockOnGmail.length) {
      console.log('バックアップ時間トリガーを無効化しました（BACKUP_POLLING_MINUTES<=0）');
    }
    return;
  }

  if (clockOnGmail.length > 1) {
    console.warn(`バックアップ時限トリガーが${clockOnGmail.length}件あるため整理します（エンドレス実行の典型原因）`);
    clockOnGmail.forEach(function (t) {
      ScriptApp.deleteTrigger(t);
    });
    ScriptApp.newTrigger('onGmailReceived').timeBased().everyMinutes(mins).create();
    console.log(`✅ バックアップ時間トリガーを1件に再作成しました（${mins}分ごと）`);
    return;
  }

  if (clockOnGmail.length === 1) {
    console.log('バックアップ時間トリガーは既に1件です');
    return;
  }

  ScriptApp.newTrigger('onGmailReceived').timeBased().everyMinutes(mins).create();
  console.log(`✅ バックアップ時間トリガーを作成しました（${mins}分ごと）`);
}

/**
 * 定時ダブルチェック用トリガーを保証
 */
function ensureScheduledDoubleCheckTriggers() {
  const triggers = ScriptApp.getProjectTriggers();

  // 旧定時チェックトリガーを削除
  for (const trigger of triggers) {
    const fn = trigger.getHandlerFunction();
    if ((fn === 'scheduledCheckMorning' || fn === 'scheduledCheckEvening') &&
        trigger.getTriggerSource() === ScriptApp.TriggerSource.CLOCK) {
      ScriptApp.deleteTrigger(trigger);
    }
  }

  const latest = ScriptApp.getProjectTriggers();
  const hasS1 = latest.some(t => t.getHandlerFunction() === 'scheduledCheckSlot1' && t.getTriggerSource() === ScriptApp.TriggerSource.CLOCK);
  const hasS2 = latest.some(t => t.getHandlerFunction() === 'scheduledCheckSlot2' && t.getTriggerSource() === ScriptApp.TriggerSource.CLOCK);
  const hasS3 = latest.some(t => t.getHandlerFunction() === 'scheduledCheckSlot3' && t.getTriggerSource() === ScriptApp.TriggerSource.CLOCK);

  if (!hasS1) {
    ScriptApp.newTrigger('scheduledCheckSlot1')
      .timeBased()
      .atHour(CONFIG.SLOT1_END_HOUR || 9)
      .nearMinute(CONFIG.SLOT1_END_MINUTE || 0)
      .everyDays(1)
      .create();
    console.log('✅ 定時チェック(06:00-09:00)トリガーを作成しました');
  }

  if (!hasS2) {
    ScriptApp.newTrigger('scheduledCheckSlot2')
      .timeBased()
      .atHour(CONFIG.SLOT2_END_HOUR || 13)
      .nearMinute(CONFIG.SLOT2_END_MINUTE || 30)
      .everyDays(1)
      .create();
    console.log('✅ 定時チェック(12:00-13:30)トリガーを作成しました');
  }

  if (!hasS3) {
    ScriptApp.newTrigger('scheduledCheckSlot3')
      .timeBased()
      .atHour(CONFIG.SLOT3_END_HOUR || 19)
      .nearMinute(CONFIG.SLOT3_END_MINUTE || 30)
      .everyDays(1)
      .create();
    console.log('✅ 定時チェック(17:30-19:30)トリガーを作成しました');
  }
}

/**
 * 月〜金 06:00-09:00 定時ダブルチェック
 */
function scheduledCheckSlot1() {
  runScheduledDoubleCheck('SLOT1_0600_0900', CONFIG.SLOT1_START_HOUR || 6, CONFIG.SLOT1_START_MINUTE || 0);
}

/**
 * 月〜金 12:00-13:30 定時ダブルチェック
 */
function scheduledCheckSlot2() {
  runScheduledDoubleCheck('SLOT2_1200_1330', CONFIG.SLOT2_START_HOUR || 12, CONFIG.SLOT2_START_MINUTE || 0);
}

/**
 * 月〜金 17:30-19:30 定時ダブルチェック
 */
function scheduledCheckSlot3() {
  runScheduledDoubleCheck('SLOT3_1730_1930', CONFIG.SLOT3_START_HOUR || 17, CONFIG.SLOT3_START_MINUTE || 30);
}

/**
 * 定時時点で更新済みか検査し、未更新なら再処理→再検査→重大通知
 */
function runScheduledDoubleCheck(slotName, startHour, startMinute) {
  if (shouldEmergencyExitInventory()) {
    console.log('緊急停止中のため定時チェックを終了（解除: emergencyStopOff）');
    return;
  }
  const now = getHongKongNow();
  const day = now.getDay(); // 0:Sun, 6:Sat
  if (day === 0 || day === 6) {
    console.log(`週末のため定時チェックをスキップ: ${slotName}`);
    return;
  }

  const slotStart = new Date(now);
  slotStart.setHours(startHour, startMinute, 0, 0);
  const before = getLastSheetUpdateAt();
  const beforeOk = before >= slotStart.getTime() && before <= now.getTime();
  if (beforeOk) {
    console.log(`定時チェックOK(事前更新済み): ${slotName}`);
    recordStabilityEvent('SCHEDULED_OK_PRECHECK', `${slotName} updateAt=${new Date(before).toISOString()}`);
    return;
  }

  // この枠の開始以降に対象メールが無い場合は、未更新でも重大エラーにしない
  const hasIncomingMail = hasCandidateInventoryMailSince(slotStart.getTime());
  if (!hasIncomingMail) {
    const msg = `定時チェック情報: ${slotName} は対象メール未到着のため未更新（エラー扱いしない）`;
    console.log(msg);
    recordStabilityEvent('SCHEDULED_NO_MAIL', msg);
    return;
  }

  console.log(`定時チェックNG(未更新)のため再処理実行: ${slotName}`);
  recordStabilityEvent('SCHEDULED_RETRY', slotName);
  try {
    // 同一メールでも再処理設定を活かし、最新データを再投入
    manualRun();
  } catch (error) {
    console.error('定時再処理で例外:', error);
  }

  const after = getLastSheetUpdateAt();
  const afterOk = after >= slotStart.getTime() && after <= getHongKongNow().getTime();
  if (afterOk) {
    console.log(`定時ダブルチェック成功: ${slotName}`);
    recordStabilityEvent('SCHEDULED_OK_POSTCHECK', `${slotName} updateAt=${new Date(after).toISOString()}`);
    return;
  }

  const message = `定時ダブルチェック失敗: ${slotName}。再処理後も更新時刻が基準を満たしません。`;
  recordStabilityEvent('SCHEDULED_CRITICAL', message);
  sendCriticalErrorNotification(new Error(message), `runScheduledDoubleCheck(${slotName})`);
}

/**
 * 指定時刻以降に対象在庫メールが存在するかを判定
 */
function hasCandidateInventoryMailSince(sinceMs) {
  try {
    const query = buildGmailQuery();
    const threads = GmailApp.search(query, 0, 100);
    for (const thread of threads) {
      const messages = thread.getMessages();
      for (const message of messages) {
        const msgTime = message.getDate().getTime();
        if (msgTime < sinceMs) continue;
        const pdf = getPdfAttachment(message);
        if (pdf) {
          return true;
        }
      }
    }
    return false;
  } catch (error) {
    console.error('対象メール有無判定エラー:', error);
    // 判定失敗時はfalseにせず、誤って重大エラー乱発しないよう true 扱いで再処理へ進める
    return true;
  }
}

/**
 * 手動実行（テスト用）- 最新のinventoryメールを強制的に処理
 * 新旧チェックをスキップして、最新のメールを必ず処理します
 */
function manualRun() {
  try {
    if (shouldEmergencyExitInventory()) {
      console.log('緊急停止中のため manualRun を終了（解除: emergencyStopOff）');
      return;
    }
    console.log('=== マニュアル実行開始（新旧チェックスキップ） ===');
    console.log('[ビルド確認] SCRIPT_VERSION=' + CONFIG.SCRIPT_VERSION + ' 使用Gemini=' + getEffectiveGeminiModelId());
    
    // Gmail検索クエリを構築
    const query = buildGmailQuery();
    console.log(`検索クエリ: ${query}`);
    
    // 条件に合致するスレッドを検索
    const threads = GmailApp.search(query, 0, 10); // 最新10件を取得
    
    if (threads.length === 0) {
      console.log('❌ 条件に合致するメールが見つかりませんでした');
      console.log(`検索条件: ${query}`);
      return;
    }
    
    // スレッドを日時順にソート（新しい順）
    const sortedThreads = threads.sort((a, b) => {
      const messagesA = a.getMessages();
      const messagesB = b.getMessages();
      const timeA = messagesA.length > 0 ? messagesA[messagesA.length - 1].getDate().getTime() : a.getLastMessageDate().getTime();
      const timeB = messagesB.length > 0 ? messagesB[messagesB.length - 1].getDate().getTime() : b.getLastMessageDate().getTime();
      return timeB - timeA;
    });
    
    // 最新の1件を取得（新旧チェックなし）
    const latestThread = sortedThreads[0];
    const latestMessages = latestThread.getMessages();
    const latestMessage = latestMessages.length > 0 ? latestMessages[latestMessages.length - 1] : null;
    const threadTime = latestMessage ? latestMessage.getDate().getTime() : latestThread.getLastMessageDate().getTime();
    const threadDate = new Date(threadTime);
    const latestFingerprint = buildMessageFingerprint(latestMessage);
    
    console.log(`✅ 処理対象メール: ${latestThread.getFirstMessageSubject()}`);
    console.log(`   日時: ${threadDate.toLocaleString('ja-JP')}`);
    console.log(`   スレッド内メッセージ数: ${latestMessages.length}`);
    
    // メールを処理
    const result = processInventoryThread(latestThread);
    
    let executionResult;
    if (result && result.success) {
      executionResult = { 
        success: true, 
        error: null, 
        processedEmail: result.processedEmail, 
        summary: result.summary, 
        failureReason: '',
        processedCount: result.processedCount || 0,
        skippedCount: result.skippedCount || 0,
        integrityAudit: result.integrityAudit
      };
      // 成功時のみ処理日時を保存
      saveLastProcessedTime(threadTime);
      saveLastProcessedFingerprint(latestFingerprint);
      saveLastProcessedScriptVersion(CONFIG.SCRIPT_VERSION);
      console.log(`✓ 処理日時を保存（成功後）: ${new Date(threadTime).toLocaleString('ja-JP')} (${threadTime})`);
      
      // Stock式設定も実行
      console.log('=== 在庫メール処理完了、Stock式設定開始 ===');
      setStockFormulas();
    } else {
      executionResult = { 
        success: false, 
        error: result?.error || new Error('処理に失敗しました'), 
        processedEmail: null, 
        summary: null, 
        failureReason: result?.failureReason || 'PROCESS_ERROR',
        integrityAudit: result?.integrityAudit,
        messageFingerprint: latestFingerprint
      };
      if (PDF_INTEGRITY_FAILURE_REASONS.indexOf(executionResult.failureReason) >= 0) {
        saveLastProcessedTime(threadTime);
        saveLastProcessedFingerprint(latestFingerprint);
        saveLastProcessedScriptVersion(CONFIG.SCRIPT_VERSION);
        console.log('PDF\u7167\u5408\u4e0d\u4e00\u81f4: \u6307\u7d0b\u3092\u4fdd\u5b58\u3057\u307e\u3057\u305f\uff08manualRun\u30fbSheets\u672a\u66f4\u65b0\uff09');
      }
      console.log('=== メール処理が完了しませんでした、Stock式設定をスキップ ===');
    }
    
    // InventorySummaryReport!F2の設定を実行
    console.log('=== InventorySummaryReport!F2設定を強制実行 ===');
    setInventorySummaryReportFormula();
    
    if (!executionResult.success && PDF_INTEGRITY_FAILURE_REASONS.indexOf(executionResult.failureReason) >= 0) {
      console.log('=== PDF照合不一致のため重要通知メール送信 ===');
      sendPdfIntegrityFailureNotification(executionResult);
    } else if (executionResult.success && (executionResult.processedCount || 0) > 0) {
      console.log('=== 作業終了メール送信開始 ===');
      console.log(`処理結果: ${executionResult.success ? '成功' : '失敗'}`);
      sendCompletionNotification(executionResult);
      console.log('=== 作業終了メール送信完了 ===');
    } else {
      console.log('作業終了メールは送信しません（更新なし、または失敗）');
    }
    
    if (typeof executionResult !== 'undefined' && executionResult.success) {
      console.log('✅ マニュアル実行が正常に完了しました（在庫シートまで更新済み）');
    } else {
      console.log('⚠️ マニュアル実行は終了しましたが、在庫PDFの処理は成功していません（ログのエラーを確認してください）');
    }
    
  } catch (error) {
    console.error('❌ マニュアル実行でエラーが発生しました:', error);
    sendCriticalErrorNotification(error, 'manualRun()');
    throw error;
  }
}

/**
 * 最新のinventoryメールを強制的に処理（新旧チェックスキップ版）
 * manualRun()のエイリアス - より明確な関数名
 */
function processLatestInventoryEmail() {
  manualRun();
}

/**
 * 特定の件名のメールを処理（デバッグ用）
 * @param {string} subjectKeyword - 件名に含まれるキーワード
 */
function processEmailBySubject(subjectKeyword) {
  try {
    console.log(`=== 件名検索実行: "${subjectKeyword}" ===`);
    
    // 件名で検索
    const query = `subject:${subjectKeyword} has:attachment filename:pdf`;
    console.log(`検索クエリ: ${query}`);
    
    const threads = GmailApp.search(query, 0, 5);
    
    if (threads.length === 0) {
      console.log(`❌ 件名に"${subjectKeyword}"を含むメールが見つかりませんでした`);
      return;
    }
    
    // 最新の1件を処理
    const latestThread = threads[0];
    const latestMessages = latestThread.getMessages();
    const latestMessage = latestMessages.length > 0 ? latestMessages[latestMessages.length - 1] : null;
    const threadTime = latestMessage ? latestMessage.getDate().getTime() : latestThread.getLastMessageDate().getTime();
    const latestFingerprint = buildMessageFingerprint(latestMessage);
    
    console.log(`✅ 処理対象: ${latestThread.getFirstMessageSubject()}`);
    console.log(`   日時: ${new Date(threadTime).toLocaleString('ja-JP')}`);
    
    // メールを処理
    const result = processInventoryThread(latestThread);
    
    if (result && result.success) {
      saveLastProcessedTime(threadTime);
      saveLastProcessedFingerprint(latestFingerprint);
      saveLastProcessedScriptVersion(CONFIG.SCRIPT_VERSION);
      console.log(`✓ 処理日時を保存（成功後）: ${new Date(threadTime).toLocaleString('ja-JP')} (${threadTime})`);
      console.log('✅ 処理が正常に完了しました');
      setStockFormulas();
      setInventorySummaryReportFormula();
    } else {
      console.error('❌ 処理に失敗しました:', result?.error);
    }
    
  } catch (error) {
    console.error('❌ エラーが発生しました:', error);
    sendCriticalErrorNotification(error, 'processEmailBySubject()');
    throw error;
  }
}

/**
 * 現在の処理日時を確認（デバッグ用）
 */
function checkProcessedTime() {
  const lastTime = getLastProcessedTime();
  if (lastTime) {
    console.log(`現在の処理日時: ${new Date(lastTime).toLocaleString('ja-JP')}`);
    console.log(`タイムスタンプ: ${lastTime}`);
  } else {
    console.log('処理日時が設定されていません（初回実行）');
  }
}

// =============================================================================
// 緊急停止・トリガー操作・手動実行の別名（元 EmergencyStop.gs をマージ）
// =============================================================================

/** 止め方 / 復旧: 関数を選んで ▶ 実行 */
var SCRIPT_PROP_EMERGENCY_STOP = 'GAS_EMERGENCY_STOP_V1';

function shouldEmergencyExitInventory() {
  return PropertiesService.getScriptProperties().getProperty(SCRIPT_PROP_EMERGENCY_STOP) === '1';
}

function emergencyStopOn() {
  PropertiesService.getScriptProperties().setProperty(SCRIPT_PROP_EMERGENCY_STOP, '1');
  console.log('緊急停止ON: onGmailReceived / 定時再処理は即終了。解除は emergencyStopOff() または restoreNormalOperationAfterEmergency()');
}

function emergencyStopOff() {
  PropertiesService.getScriptProperties().deleteProperty(SCRIPT_PROP_EMERGENCY_STOP);
  console.log('緊急停止OFF');
}

function deleteAllTriggersNow() {
  var list = ScriptApp.getProjectTriggers();
  list.forEach(function (t) {
    ScriptApp.deleteTrigger(t);
  });
  console.log('削除したトリガー数: ' + list.length + '（0ならもともとなし）');
}

/** 【手動実行・在庫PDF】manualRun と同じ（プルダウン用の別名） */
function manualRunInventory() {
  manualRun();
}

function setupGmailTriggerHelp() {
  setupGmailTrigger();
}

function checkProcessedTimeHelp() {
  checkProcessedTime();
}

function restoreNormalOperationAfterEmergency() {
  emergencyStopOff();
  ensureBackupTimeTrigger();
  ensureScheduledDoubleCheckTriggers();
  console.log('--- 復旧完了: 緊急停止OFF + 時限トリガー再設定 ---');
  console.log('次: トリガー画面で Gmail→onGmailReceived（ラベルProcessInventory 等）があるか確認。無ければ追加。手順は setupGmailTrigger() 実行でログ出力。');
  console.log('動作確認: logAutomationHealth() 実行 → manualRunInventory() は緊急停止OFF後に実行');
}

function logAutomationHealth() {
  var stop = PropertiesService.getScriptProperties().getProperty(SCRIPT_PROP_EMERGENCY_STOP);
  console.log('緊急停止フラグ: ' + (stop === '1' ? 'ON（本体は即終了しているので先に OFF）' : 'OFF'));

  var triggers = ScriptApp.getProjectTriggers();
  console.log('登録トリガー数: ' + triggers.length);
  var gmailOn = false;
  var clockOnGmail = 0;
  for (var i = 0; i < triggers.length; i++) {
    var t = triggers[i];
    var fn = t.getHandlerFunction();
    var src = t.getTriggerSource();
    console.log(String(i + 1) + '. handler=' + fn + ' source=' + src);
    if (fn === 'onGmailReceived') {
      if (src === ScriptApp.TriggerSource.CLOCK) clockOnGmail++;
      if (src === ScriptApp.TriggerSource.GMAIL) gmailOn = true;
    }
  }
  console.log('onGmailReceived 時限(CLOCK)件数: ' + clockOnGmail + '（複数あると負荷増。ensure が1件に整理）');
  console.log('onGmailReceived Gmail由来: ' + (gmailOn ? 'あり' : 'なし（受信で即動かすならトリガー画面で追加）'));
}
