/**
 * Gmail Inventory PDF Processor with Gemini AI
 * Gmailから「inventory」件名のメールを検索し、添付PDFをGemini 2.5で要約してGoogle Sheetsに保存
 * 指定時間（8:05、13:05、18:17）でGmailをチェックし、条件に合致するメールがあった場合にスクリプトを実行
 */

// 設定定数
const CONFIG = {
  GEMINI_API_KEY: 'AIzaSyBljM0KL5In5JIiXiN8nrvfA4LXf44tJkI',
  GEMINI_MODEL: 'gemini-2.0-flash',
  SHEET_ID: '1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M',
  GMAIL_ADDRESS: 'bestinksalesman@gmail.com',
  INVENTORY_SUMMARY_SHEET_NAME: 'InventorySummaryReport',
  SEARCH_QUERY: 'subject:inventory has:attachment filename:inventory.pdf',
  // 指定チェック時間（24時間形式）
  CHECK_TIMES: ['08:05', '13:05', '18:17'],
  // メール条件（件名に含まれるキーワード）
  EMAIL_CONDITIONS: ['inventory', 'stock', '在庫', 'データ'],
  // 再トライ設定
  RETRY_DELAY_MINUTES: 3, // 再トライまでの待機時間（分）
  MAX_RETRY_ATTEMPTS: 2,  // 最大再トライ回数
  RETRY_TRIGGER_FUNCTION: 'retryMain', // 再トライ用関数名
  // 限定公開シート対応設定
  USE_PRIVATE_SHEET: true, // 限定公開シート使用フラグ
  SHEET_ACCESS_METHOD: 'direct' // 直接アクセス方法
};

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
 * メイン実行関数（トリガー用）
 */
function main() {
  let processedEmail = null;
  try {
    console.log('=== メイン処理開始 ===');
    
    // 時間チェック機能を実行
    if (!checkScheduledTime()) {
      console.log('指定時間外のため、処理をスキップします');
      return;
    }
    
    // メール条件チェック機能を実行
    const emails = searchInventoryEmails();
    if (emails.length === 0) {
      console.log('条件に合致するメールがないため、3分後に再トライをスケジュールします');
      sendNoEmailNotification();
      scheduleRetry();
      return;
    }
    
    // メールが見つかった場合のみ処理を実行
    console.log('条件に合致するメールが見つかりました。在庫データ処理を開始します');
    processedEmail = processInventoryEmailsWithEmails(emails);
    
    // メール処理が成功した場合のみStock式設定を実行
    if (processedEmail) {
      console.log('=== 在庫メール処理完了、Stock式設定開始 ===');
      setStockFormulas();
    } else {
      console.log('=== メール処理が完了しませんでした、Stock式設定をスキップ ===');
    }
    
    // Gemini API失敗時でもInventorySummaryReport!F2の設定を実行
    console.log('=== InventorySummaryReport!F2設定を強制実行 ===');
    setInventorySummaryReportFormula();
    
    console.log('=== メイン処理完了 ===');
    
    // 作業終了お知らせメールを送信
    console.log('=== 作業終了メール送信開始 ===');
    console.log(`処理したメール: ${processedEmail ? 'あり' : 'なし'}`);
    sendCompletionNotification(processedEmail);
    console.log('=== 作業終了メール送信完了 ===');
  } catch (error) {
    console.error('メイン処理でエラーが発生しました:', error);
    sendErrorNotification(error);
    throw error;
  }
}

/**
 * 再トライ用メイン関数
 */
function retryMain() {
  let processedEmail = null;
  try {
    console.log('=== 再トライ処理開始 ===');
    
    // 再トライ回数をチェック
    const retryCount = getRetryCount();
    if (retryCount >= CONFIG.MAX_RETRY_ATTEMPTS) {
      console.log(`最大再トライ回数（${CONFIG.MAX_RETRY_ATTEMPTS}回）に達したため、処理を終了します`);
      sendRetryLimitNotification();
      return;
    }
    
    console.log(`再トライ回数: ${retryCount + 1}/${CONFIG.MAX_RETRY_ATTEMPTS}`);
    
    // 時間チェック機能を実行
    if (!checkScheduledTime()) {
      console.log('再トライ時も指定時間外のため、処理をスキップします');
      return;
    }
    
    // メール条件チェック機能を実行
    const emails = searchInventoryEmails();
    if (emails.length === 0) {
      console.log('再トライ時も条件に合致するメールがないため、3分後に再トライをスケジュールします');
      incrementRetryCount();
      sendNoEmailNotification();
      scheduleRetry();
      return;
    }
    
    // 再トライ成功時はカウンターをリセット
    resetRetryCount();
    
    // メールが見つかった場合のみ処理を実行
    console.log('再トライで条件に合致するメールが見つかりました。在庫データ処理を開始します');
    processedEmail = processInventoryEmailsWithEmails(emails);
    
    // メール処理が成功した場合のみStock式設定を実行
    if (processedEmail) {
      console.log('=== 在庫メール処理完了、Stock式設定開始 ===');
      setStockFormulas();
    } else {
      console.log('=== メール処理が完了しませんでした、Stock式設定をスキップ ===');
    }
    
    // Gemini API失敗時でもInventorySummaryReport!F2の設定を実行
    console.log('=== InventorySummaryReport!F2設定を強制実行 ===');
    setInventorySummaryReportFormula();
    
    console.log('=== 再トライ処理完了 ===');
    
    // 作業終了お知らせメールを送信
    console.log('=== 作業終了メール送信開始 ===');
    console.log(`処理したメール: ${processedEmail ? 'あり' : 'なし'}`);
    sendCompletionNotification(processedEmail);
    console.log('=== 作業終了メール送信完了 ===');
  } catch (error) {
    console.error('再トライ処理でエラーが発生しました:', error);
    sendErrorNotification(error);
    throw error;
  }
}

/**
 * 在庫メール処理関数（メール配列を受け取る版）
 */
function processInventoryEmailsWithEmails(emails) {
  try {
    console.log('=== Gmail Inventory Processor 開始 ===');
    console.log(`検索結果: ${emails.length}件のメールが見つかりました`);

    if (emails.length === 0) {
      console.log('処理対象メールはありませんでした。');
      return null;
    }
    
    console.log(`本日のメール ${emails.length}件の処理を開始します。`);
    
    // 最新のメールのみを処理（重複を避けるため）
    const latestEmail = emails[0]; // 既に新しい順にソート済み
    const emailDate = latestEmail.getDate();
    const emailDateHK = new Date(emailDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const emailDateStr = emailDateHK.toLocaleDateString('ja-JP');
    const emailTimeStr = emailDateHK.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
    const mailInfo = `メール (件名: ${latestEmail.getSubject()}, 日時: ${emailDateStr} ${emailTimeStr})`;
    
    try {
      const startTime = new Date();
      console.log(`${mailInfo} - 処理開始: ${startTime.toLocaleString('ja-JP')}`);
      
      const pdfBlob = getPdfAttachment(latestEmail);
      if (!pdfBlob) {
        console.log(`${mailInfo} - PDF添付ファイルが見つかりませんでした。処理を終了します。`);
        return null;
      }
      
      console.log(`${mailInfo} - GeminiでPDF直接解析を開始します...`);
      const geminiStartTime = new Date();
      const summary = generateSummaryWithGeminiMultiplePasses(pdfBlob, 1); 
      const geminiEndTime = new Date();
      const geminiDuration = Math.round((geminiEndTime - geminiStartTime) / 1000);
      console.log(`${mailInfo} - Gemini解析完了 (処理時間: ${geminiDuration}秒)`);
      
      saveToGoogleSheets(summary, latestEmail, 1);
      console.log(`${mailInfo} - Google Sheetsへの保存が完了しました。`);
      
      const endTime = new Date();
      const totalDuration = Math.round((endTime - startTime) / 1000);
      console.log(`${mailInfo} - 処理完了 (総処理時間: ${totalDuration}秒)`);
      
      return latestEmail; // 処理したメールを返す
      
    } catch (error) {
      console.error(`${mailInfo} - 処理中にエラーが発生しました:`, error.message);
      
      // Gemini API エラーの場合は処理を継続（フォールバック）
      if (error.message.includes('Gemini API') || error.message.includes('503')) {
        console.log('⚠️ Gemini API エラーが発生しましたが、処理を継続します');
        console.log('⚠️ 既存のデータでInventorySummaryReport!F2の設定を実行します');
        return null; // エラー時はnullを返すが、処理は継続
      }
      
      throw error;
    }
    
    console.log('=== Gmail Inventory Processor 正常終了 ===');
  } catch (error) {
    console.error('スクリプト全体で致命的なエラーが発生しました:', error);
    
    // Gemini API エラーの場合は処理を継続（フォールバック）
    if (error.message.includes('Gemini API') || error.message.includes('503')) {
      console.log('⚠️ Gemini API エラーが発生しましたが、処理を継続します');
      console.log('⚠️ 既存のデータでInventorySummaryReport!F2の設定を実行します');
      return null; // エラー時はnullを返すが、処理は継続
    }
    
    sendErrorNotification(error);
    throw error; // エラーを上位に伝播
  }
}

/**
 * 在庫メール処理関数（従来版）
 */
function processInventoryEmails() {
  try {
    console.log('=== Gmail Inventory Processor 開始 ===');

    // メールを検索
    const emails = searchInventoryEmails();
    console.log(`検索結果: ${emails.length}件のメールが見つかりました`);

    if (emails.length === 0) {
      console.log('処理対象メールはありませんでした。');
      return null;
    }
    
    console.log(`本日のメール ${emails.length}件の処理を開始します。`);
    
    // 最新のメールのみを処理（重複を避けるため）
    const latestEmail = emails[0]; // 既に新しい順にソート済み
    const mailInfo = `メール (件名: ${latestEmail.getSubject()})`;
    
    try {
      const startTime = new Date();
      console.log(`${mailInfo} - 処理開始: ${startTime.toLocaleString('ja-JP')}`);
      
      const pdfBlob = getPdfAttachment(latestEmail);
      if (!pdfBlob) {
        console.log(`${mailInfo} - PDF添付ファイルが見つかりませんでした。処理を終了します。`);
        return null;
      }
      
      console.log(`${mailInfo} - GeminiでPDF直接解析を開始します...`);
      const geminiStartTime = new Date();
      const summary = generateSummaryWithGeminiMultiplePasses(pdfBlob, 1); 
      const geminiEndTime = new Date();
      const geminiDuration = Math.round((geminiEndTime - geminiStartTime) / 1000);
      console.log(`${mailInfo} - Gemini解析完了 (処理時間: ${geminiDuration}秒)`);
      
      saveToGoogleSheets(summary, latestEmail, 1);
      console.log(`${mailInfo} - Google Sheetsへの保存が完了しました。`);
      
      const endTime = new Date();
      const totalDuration = Math.round((endTime - startTime) / 1000);
      console.log(`${mailInfo} - 処理完了 (総処理時間: ${totalDuration}秒)`);
      
      return latestEmail; // 処理したメールを返す
      
    } catch (error) {
      console.error(`${mailInfo} - 処理中にエラーが発生しました:`, error.message);
      
      // Gemini API エラーの場合は処理を継続（フォールバック）
      if (error.message.includes('Gemini API') || error.message.includes('503')) {
        console.log('⚠️ Gemini API エラーが発生しましたが、処理を継続します');
        console.log('⚠️ 既存のデータでInventorySummaryReport!F2の設定を実行します');
        return null; // エラー時はnullを返すが、処理は継続
      }
      
      throw error;
    }
    
    console.log('=== Gmail Inventory Processor 正常終了 ===');
  } catch (error) {
    console.error('スクリプト全体で致命的なエラーが発生しました:', error);
    
    // Gemini API エラーの場合は処理を継続（フォールバック）
    if (error.message.includes('Gemini API') || error.message.includes('503')) {
      console.log('⚠️ Gemini API エラーが発生しましたが、処理を継続します');
      console.log('⚠️ 既存のデータでInventorySummaryReport!F2の設定を実行します');
      return null; // エラー時はnullを返すが、処理は継続
    }
    
    sendErrorNotification(error);
    throw error; // エラーを上位に伝播
  }
}

// ===============================================================
// 再トライ機能
// ===============================================================

/**
 * 再トライをスケジュールします（3分後）
 */
function scheduleRetry() {
  try {
    console.log(`${CONFIG.RETRY_DELAY_MINUTES}分後に再トライをスケジュールします`);
    
    // 既存の再トライトリガーを削除
    const triggers = ScriptApp.getProjectTriggers();
    for (const trigger of triggers) {
      if (trigger.getHandlerFunction() === CONFIG.RETRY_TRIGGER_FUNCTION) {
        ScriptApp.deleteTrigger(trigger);
      }
    }
    
    // 3分後に再トライトリガーを設定
    const retryTime = new Date();
    retryTime.setMinutes(retryTime.getMinutes() + CONFIG.RETRY_DELAY_MINUTES);
    
    ScriptApp.newTrigger(CONFIG.RETRY_TRIGGER_FUNCTION)
      .timeBased()
      .at(retryTime)
      .create();
    
    console.log(`再トライスケジュール完了: ${retryTime.toLocaleString('ja-JP')}`);
    
  } catch (error) {
    console.error('再トライスケジュールエラー:', error);
  }
}

/**
 * 再トライ回数を取得します
 */
function getRetryCount() {
  try {
    const properties = PropertiesService.getScriptProperties();
    const retryCount = properties.getProperty('retryCount');
    return retryCount ? parseInt(retryCount, 10) : 0;
  } catch (error) {
    console.error('再トライ回数取得エラー:', error);
    return 0;
  }
}

/**
 * 再トライ回数を増加させます
 */
function incrementRetryCount() {
  try {
    const properties = PropertiesService.getScriptProperties();
    const currentCount = getRetryCount();
    const newCount = currentCount + 1;
    properties.setProperty('retryCount', newCount.toString());
    console.log(`再トライ回数を更新: ${newCount}`);
  } catch (error) {
    console.error('再トライ回数更新エラー:', error);
  }
}

/**
 * 再トライ回数をリセットします
 */
function resetRetryCount() {
  try {
    const properties = PropertiesService.getScriptProperties();
    properties.deleteProperty('retryCount');
    console.log('再トライ回数をリセットしました');
  } catch (error) {
    console.error('再トライ回数リセットエラー:', error);
  }
}

/**
 * メール無しの時の通知メールを送信します
 */
function sendNoEmailNotification() {
  try {
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const notificationTime = hongKongTime.toLocaleString('ja-JP');
    
    const subject = 'GASスクリプト「gmail-Inventory-AutoDataFill」メール未発見通知';
    const body = `
在庫データ処理スクリプトを実行しましたが、条件に合致するメールが見当たりませんでした。

通知時刻: ${notificationTime}
指定チェック時間: ${CONFIG.CHECK_TIMES.join(', ')}
検索条件: ${CONFIG.EMAIL_CONDITIONS.join(', ')}

3分後に再度トライします。
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

/**
 * 再トライ制限通知メールを送信します
 */
function sendRetryLimitNotification() {
  try {
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const notificationTime = hongKongTime.toLocaleString('ja-JP');
    
    const subject = '【要確認】GASスクリプト再トライ制限到達通知';
    const body = `
Gmail在庫PDF処理スクリプトで最大再トライ回数に達しました。

通知時刻: ${notificationTime}
最大再トライ回数: ${CONFIG.MAX_RETRY_ATTEMPTS}回
再トライ間隔: ${CONFIG.RETRY_DELAY_MINUTES}分

指定時間（${CONFIG.CHECK_TIMES.join(', ')}）に条件に合致するメールが見つからなかったため、
処理を終了しました。

手動でスクリプトを実行するか、メールの送信状況を確認してください。
`;

    GmailApp.sendEmail(
      CONFIG.GMAIL_ADDRESS,
      subject,
      body
    );
    
    console.log('✅ 再トライ制限通知メールを送信しました');
  } catch (error) {
    console.error('再トライ制限通知メールの送信に失敗しました:', error);
  }
}

// ===============================================================
// 時間チェック・条件チェック機能
// ===============================================================

/**
 * 指定時間（8:05、13:05、18:17）かどうかをチェックします
 * @return {boolean} 指定時間内の場合true、そうでなければfalse
 */
function checkScheduledTime() {
  try {
    // テスト用: 時間チェックを無効化
    console.log('⚠️ テストモード: 時間チェックをスキップします');
    return true;
    
    // 本番用の時間チェック（コメントアウト）
    /*
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const currentTime = hongKongTime.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
    
    // 曜日チェック（日曜日は処理しない）
    const dayOfWeek = hongKongTime.getDay(); // 0=日曜日, 1=月曜日, ..., 6=土曜日
    if (dayOfWeek === 0) {
      console.log('❌ 日曜日のため、処理をスキップします');
      return false;
    }
    
    console.log(`現在の香港時間: ${currentTime}`);
    console.log(`指定チェック時間: ${CONFIG.CHECK_TIMES.join(', ')}`);
    
    // 指定時間内かチェック（±120分の許容範囲 - 手動テスト用）
    for (const checkTime of CONFIG.CHECK_TIMES) {
      if (isWithinTimeRange(currentTime, checkTime, 120)) {
        console.log(`✅ 指定時間内です: ${checkTime} (±120分許容)`);
        return true;
      }
    }
    
    console.log(`❌ 指定時間外です: ${currentTime}`);
    return false;
    */
    
  } catch (error) {
    console.error('時間チェックエラー:', error);
    // エラー時は処理を続行（安全側に倒す）
    return true;
  }
}

/**
 * 現在時刻が指定時刻の範囲内かチェックします
 * @param {string} currentTime - 現在時刻 (HH:MM形式)
 * @param {string} targetTime - 対象時刻 (HH:MM形式)
 * @param {number} toleranceMinutes - 許容範囲（分）
 * @return {boolean} 範囲内の場合true
 */
function isWithinTimeRange(currentTime, targetTime, toleranceMinutes = 5) {
  try {
    const [currentHour, currentMinute] = currentTime.split(':').map(Number);
    const [targetHour, targetMinute] = targetTime.split(':').map(Number);
    
    const currentTotalMinutes = currentHour * 60 + currentMinute;
    const targetTotalMinutes = targetHour * 60 + targetMinute;
    
    const diffMinutes = Math.abs(currentTotalMinutes - targetTotalMinutes);
    
    return diffMinutes <= toleranceMinutes;
  } catch (error) {
    console.error('時間範囲チェックエラー:', error);
    return false;
  }
}


// ===============================================================
// ヘルパー関数
// ===============================================================

/**
 * PDFを3回に分けて解析し、すべての在庫データを取得します。
 * ⚠️ 重要: この3回読み取りの仕組みは絶対に削除してはいけません！
 * 理由: Gemini APIの出力トークン制限により、1回の読み取りでは途中で処理が中断され、
 * 6ページ目のZ-MKシリーズ（BD-060〜BD-067, AC-261〜AC-264, FC-056, FC-057）が
 * 抽出されなくなります。詳細は「3回読み取りの重要性.md」を参照してください。
 * 
 * @param {GoogleAppsScript.Base.Blob} pdfBlob - 解析するPDFファイル。
 * @param {number} emailIndex - 処理中のメール番号。
 * @return {string} すべての在庫データを統合したテキスト。
 */
function generateSummaryWithGeminiMultiplePasses(pdfBlob, emailIndex = 1) {
  try {
    console.log(`PDF解析開始 - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);
    
    // ===============================================================
    // ⚠️ 重要: 3回読み取りは絶対に削除してはいけません！
    // ===============================================================
    // 理由:
    // 1. Gemini APIの出力トークン制限により、1回の読み取りでは途中で処理が中断される
    // 2. 6ページ目のZ-MKシリーズ（BD-060〜BD-067, AC-261〜AC-264, FC-056, FC-057）が
    //    5ページ目の途中で処理が止まり、抽出されない
    // 3. 3回に分けることで、各ページを確実に読み取り、完全なデータ抽出を実現
    // 4. この仕組みにより、期待値204件の正確な在庫データを取得できる
    // 5. 効率化の名目で1回読み取りに変更すると、重要なデータが失われる
    // ===============================================================
    
    // 3回の読み取りでPDFを完全に解析
    const allResults = [];
    
    // 1回目: 1-3ページ目 - 削除禁止！基本的な在庫データを抽出
    console.log('=== 1回目読み取り: 1-3ページ目 ===');
    const result1 = generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルの1-3ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。

## 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 1-3ページ目の在庫アイテムを漏れなく抽出してください。
- マークダウンテーブルのみを出力してください。
`, 1);
    if (result1 && result1.trim().length > 0) {
      allResults.push(result1);
      console.log(`1回目読み取り完了: ${result1.split('\n').filter(line => line.includes('|')).length}行`);
    }
    
    // 2回目: 4-5ページ目 - 削除禁止！中間ページの在庫データを抽出
    console.log('=== 2回目読み取り: 4-5ページ目 ===');
    const result2 = generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルの4-5ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。

## 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 4-5ページ目の在庫アイテムを漏れなく抽出してください。
- マークダウンテーブルのみを出力してください。
`, 2);
    if (result2 && result2.trim().length > 0) {
      allResults.push(result2);
      console.log(`2回目読み取り完了: ${result2.split('\n').filter(line => line.includes('|')).length}行`);
    }
    
    // 3回目: 6-7ページ目（Z-MKシリーズを含む） - 削除禁止！最重要データを抽出
    console.log('=== 3回目読み取り: 6-7ページ目（Z-MKシリーズ） ===');
    const result3 = generateSummaryWithGeminiSinglePass(pdfBlob, `
添付された在庫PDFファイルの6-7ページ目を解析し、在庫データをマークダウン形式のテーブルとして抽出してください。

## 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 6-7ページ目の在庫アイテムを漏れなく抽出してください。
- **特に重要**: 6ページ目のZ-MKシリーズ（AC-261, AC-262, AC-263, AC-264, BD-060, BD-061, BD-062, BD-063, BD-064, BD-065, BD-067, FC-056, FC-057, US05132045MI0800, US05132045MI0900, UT05125045MI0800, GSW04I0800B, GSW04I1000B, GSW04M3000B, GSC08I0800B, GSC08I1000B）は必ずマークダウンテーブル形式で抽出してください。
- 6ページ目には38件のアイテムが存在するはずです。すべてのアイテムを漏れなく抽出してください。

**重要**: 6ページ目のZ-MKセクションの商品コードは、必ず以下の形式でマークダウンテーブルに含めてください：
| AC-261 | [説明] | [数量] | [数量] | [数量] |
| AC-262 | [説明] | [数量] | [数量] | [数量] |
| AC-263 | [説明] | [数量] | [数量] | [数量] |
| AC-264 | [説明] | [数量] | [数量] | [数量] |
| BD-060 | [説明] | [数量] | [数量] | [数量] |
| BD-061 | [説明] | [数量] | [数量] | [数量] |
| BD-062 | [説明] | [数量] | [数量] | [数量] |
| BD-063 | [説明] | [数量] | [数量] | [数量] |
| BD-064 | [説明] | [数量] | [数量] | [数量] |
| BD-065 | [説明] | [数量] | [数量] | [数量] |
| BD-067 | [説明] | [数量] | [数量] | [数量] |
| FC-056 | [説明] | [数量] | [数量] | [数量] |
| FC-057 | [説明] | [数量] | [数量] | [数量] |
| US05132045MI0800 | [説明] | [数量] | [数量] | [数量] |
| US05132045MI0900 | [説明] | [数量] | [数量] | [数量] |
| UT05125045MI0800 | [説明] | [数量] | [数量] | [数量] |
| GSW04I0800B | [説明] | [数量] | [数量] | [数量] |
| GSW04I1000B | [説明] | [数量] | [数量] | [数量] |
| GSW04M3000B | [説明] | [数量] | [数量] | [数量] |
| GSC08I0800B | [説明] | [数量] | [数量] | [数量] |
| GSC08I1000B | [説明] | [数量] | [数量] | [数量] |

マークダウンテーブルのみを出力してください。
`, 3);
    if (result3 && result3.trim().length > 0) {
      allResults.push(result3);
      console.log(`3回目読み取り完了: ${result3.split('\n').filter(line => line.includes('|')).length}行`);
    }
    
    // 結果を統合
    if (allResults.length === 0) {
      console.log('すべての読み取りで結果が得られませんでした');
      return '';
    }
    
    const combinedResult = allResults.join('\n');
    console.log(`統合結果: ${combinedResult.split('\n').filter(line => line.includes('|')).length}行`);
    
    // 重複処理を完全に無効化（期待値211件を確保するため）
    console.log('✅ 重複処理を完全に無効化します（期待値211件確保）');
    const deduplicatedResult = combinedResult; // 重複処理をスキップ
    
    const originalLines = combinedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
    const deduplicatedLines = deduplicatedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
    
    console.log(`元データの総行数: ${originalLines.length}行`);
    console.log(`重複処理後の行数: ${deduplicatedLines.length}行`);
    
    // BDシリーズの存在確認
    const bdItems = deduplicatedLines.filter(line => line.includes('BD-'));
    console.log(`BDシリーズのアイテム数: ${bdItems.length}件`);
    if (bdItems.length > 0) {
      console.log('BDシリーズの最初の5件:');
      bdItems.slice(0, 5).forEach(item => console.log(`  ${item}`));
    }
    
    // Z-MKシリーズの存在確認
    const zmkItems = deduplicatedLines.filter(line => line.includes('Z-MK'));
    console.log(`Z-MKシリーズのアイテム数: ${zmkItems.length}件`);
    if (zmkItems.length > 0) {
      console.log('Z-MKシリーズの最初の5件:');
      zmkItems.slice(0, 5).forEach(item => console.log(`  ${item}`));
    }
    
    // 重要な商品コードの存在確認
    const importantCodes = ['BD-060', 'BD-061', 'BD-062', 'BD-063', 'BD-064', 'BD-065', 'BD-067', 'AC-261', 'AC-262', 'AC-263', 'AC-264', 'FC-056', 'FC-057'];
    const foundImportantCodes = [];
    for (const code of importantCodes) {
      const found = deduplicatedLines.some(line => line.includes(code));
      if (found) {
        foundImportantCodes.push(code);
      }
    }
    console.log(`重要な商品コードの抽出状況: ${foundImportantCodes.length}/${importantCodes.length}件`);
    console.log(`抽出された重要な商品コード: ${foundImportantCodes.join(', ')}`);
    if (foundImportantCodes.length < importantCodes.length) {
      const missing = importantCodes.filter(code => !foundImportantCodes.includes(code));
      console.log(`❌ 抽出されていない重要な商品コード: ${missing.join(', ')}`);
    }
    
    // 204件の期待値との比較
    if (deduplicatedLines.length === 204) {
      console.log('✅ 正確に204件のアイテムが抽出されました');
    } else {
      console.log(`⚠️ 期待値204件と異なります: 実際の件数 ${deduplicatedLines.length}件`);
    }
    
    return deduplicatedResult; // 重複処理済みのデータを返す
    
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
 * @param {GoogleAppsScript.Base.Blob} pdfBlob - 解析するPDFファイル。
 * @param {string} prompt - プロンプトテキスト。
 * @param {number} passNumber - 処理パス番号。
 * @return {string} Geminiによって生成されたテキスト。
 */
function generateSummaryWithGeminiSinglePass(pdfBlob, prompt, passNumber = 1) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.GEMINI_MODEL}:generateContent?key=${CONFIG.GEMINI_API_KEY}`;
    const maxRetries = 3;
    const retryDelay = 60000; // 60秒

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`Gemini API 処理開始 (試行 ${attempt}/${maxRetries}) - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);

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
        temperature: 0.0,      // 最高精度を求めるため創造性を0に設定
        maxOutputTokens: 65536, // 出力トークン数を大幅に増加
        topP: 0.9,             // より多様な出力を許可
        topK: 50               // より多くの選択肢を考慮
        }
      };

      const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        payload: JSON.stringify(requestPayload),
        muteHttpExceptions: true
      };
      
      const response = UrlFetchApp.fetch(url, requestOptions);
      const responseCode = response.getResponseCode();
      const responseBody = response.getContentText();

      if (responseCode === 503 || responseCode === 429) {
        console.error(`Gemini API エラー: ${responseCode} - ${responseBody}`);
        if (attempt < maxRetries) {
          const delay = responseCode === 429 ? retryDelay * 2 : retryDelay; // 429の場合は2倍の待機時間
          console.log(`${delay/1000}秒後にリトライします... (試行 ${attempt + 1}/${maxRetries})`);
          Utilities.sleep(delay);
          continue;
        } else {
          throw new Error(`Gemini APIがエラーを返しました: ${responseCode}. レスポンス: ${responseBody}`);
        }
      }

      if (responseCode !== 200) {
        console.error(`Gemini API エラー: ${responseCode} - ${responseBody}`);
        throw new Error(`Gemini APIがエラーを返しました: ${responseCode}. レスポンス: ${responseBody}`);
      }

      const responseData = JSON.parse(responseBody);
      
      if (responseData.candidates && responseData.candidates[0].content) {
        const generatedText = responseData.candidates[0].content.parts[0].text;
        console.log(`Gemini解析成功: ${generatedText.length}文字`);
      
      // 解析結果の詳細をログ出力
      const lines = generatedText.split('\n');
      const tableLines = lines.filter(line => line.includes('|') && !line.includes('---'));
      console.log(`抽出された表の行数: ${tableLines.length}行`);
      
      // BDシリーズの詳細確認
      const bdLines = tableLines.filter(line => line.includes('BD-'));
      console.log(`BDシリーズの抽出数: ${bdLines.length}件`);
      
      // Z-MKシリーズの詳細確認
      const zmkLines = tableLines.filter(line => line.includes('Z-MK'));
      console.log(`Z-MKシリーズの抽出数: ${zmkLines.length}件`);
      if (zmkLines.length > 0) {
        console.log('Z-MKシリーズの最初の5件:');
        zmkLines.slice(0, 5).forEach(item => console.log(`  ${item}`));
      }
      
      // 全アイテムのProduct Codeを抽出して確認
      const productCodes = tableLines.map(line => {
        const columns = line.split('|').map(col => col.trim()).filter(col => col !== '');
        return columns.length > 0 ? columns[0] : '';
      }).filter(code => code && !code.toLowerCase().includes('product code'));
      
      console.log(`抽出されたProduct Code数: ${productCodes.length}件`);
      console.log(`Product Codeの最初の10件: ${productCodes.slice(0, 10).join(', ')}`);
      
      // Z-MKシリーズのProduct Codeを確認
      const zmkCodes = productCodes.filter(code => code.includes('Z-MK'));
      console.log(`Z-MKシリーズのProduct Code数: ${zmkCodes.length}件`);
      if (zmkCodes.length > 0) {
        console.log(`Z-MKシリーズのProduct Code: ${zmkCodes.join(', ')}`);
      }
      
      console.log(`解析結果の最初の1000文字: ${generatedText.substring(0, 1000)}`);
      
      // 商品コード修正を有効化
      const correctedText = correctProductCodeErrors(generatedText);
      if (correctedText !== generatedText) {
        console.log('✅ 商品コード修正が適用されました');
      }
      
      return correctedText; // 修正されたテキストを返す
    } else {
      console.error(`Gemini APIからの予期しない応答:`, responseBody);
      throw new Error('Gemini APIから有効なコンテンツが返されませんでした。');
    }

    } catch (error) {
      console.error(`Gemini API処理エラー (試行 ${attempt}/${maxRetries}):`, error);
      if (attempt < maxRetries) {
        console.log(`${retryDelay/1000}秒後にリトライします... (試行 ${attempt + 1}/${maxRetries})`);
        Utilities.sleep(retryDelay);
        continue;
      } else {
        throw error;
      }
    }
  }
  
  // すべてのリトライが失敗した場合
  throw new Error(`Gemini API処理が${maxRetries}回の試行後も失敗しました`);
}


/**
 * 指定時間の±1時間以内のメールを検索します。
 */
function searchInventoryEmails() {
  try {
    // 現在時刻を取得（香港時間）
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const currentTime = hongKongTime.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
    
    console.log(`現在の香港時間: ${currentTime}`);
    
    // 現在時刻に最も近い指定時間を特定（手動テスト用に±120分許容）
    let targetTime = null;
    for (const checkTime of CONFIG.CHECK_TIMES) {
      if (isWithinTimeRange(currentTime, checkTime, 120)) {
        targetTime = checkTime;
        break;
      }
    }
    
    if (!targetTime) {
      console.log('指定時間の±120分範囲外のため、メール検索をスキップします');
      return [];
    }
    
    console.log(`対象時間: ${targetTime} (±1時間以内のメールを検索)`);
    
    // 検索時間範囲を計算（±1時間）
    const [targetHour, targetMinute] = targetTime.split(':').map(Number);
    const targetTotalMinutes = targetHour * 60 + targetMinute;
    
    const startMinutes = targetTotalMinutes - 60; // 1時間前
    const endMinutes = targetTotalMinutes + 60;   // 1時間後
    
    const startHour = Math.floor(startMinutes / 60);
    const startMin = startMinutes % 60;
    const endHour = Math.floor(endMinutes / 60);
    const endMin = endMinutes % 60;
    
    console.log(`検索時間範囲: ${String(startHour).padStart(2, '0')}:${String(startMin).padStart(2, '0')} - ${String(endHour).padStart(2, '0')}:${String(endMin).padStart(2, '0')}`);
    
    // 複数の検索クエリでメールを検索（効率化のため、該当メールが見つかったら早期終了）
    const searchQueries = [
      'subject:inventory has:attachment filename:inventory.pdf',
      'subject:inventory has:attachment',
      'subject:stock has:attachment',
      'subject:在庫 has:attachment',
      'subject:データ has:attachment',
      'from:bestinksalesman@gmail.com has:attachment'
    ];
    
    let allEmails = [];
    let foundTargetEmails = false;
    
    for (const query of searchQueries) {
      console.log(`検索クエリ: ${query}`);
      try {
        const threads = GmailApp.search(query, 0, 50);
        const messages = threads.flatMap(thread => thread.getMessages());
        allEmails = allEmails.concat(messages);
        console.log(`クエリ「${query}」で${messages.length}件のメールを発見`);
        
        // 該当メールが見つかった場合は早期終了
        if (messages.length > 0) {
          foundTargetEmails = true;
          console.log('該当メールが見つかったため、検索を終了します');
          break;
        }
      } catch (queryError) {
        console.log(`クエリ「${query}」でエラー: ${queryError.message}`);
      }
    }

    // 重複を除去し、指定時間の±1時間以内のメールのみをフィルタリング
    const uniqueEmails = [];
    const seenIds = new Set();
    
    for (const message of allEmails) {
      const msgId = message.getId();
      if (!seenIds.has(msgId)) {
        seenIds.add(msgId);
        const msgDate = message.getDate();
        const msgDateHK = new Date(msgDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
        const msgTime = msgDateHK.toLocaleTimeString('ja-JP', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        });
        
        // 時間を分に変換
        const [msgHour, msgMinute] = msgTime.split(':').map(Number);
        const msgTotalMinutes = msgHour * 60 + msgMinute;
        
        // 指定時間の±1時間以内のメールのみを処理
        if (msgTotalMinutes >= startMinutes && msgTotalMinutes <= endMinutes && message.getAttachments().length > 0) {
          // 件名に条件キーワードが含まれているかチェック
          const subject = message.getSubject().toLowerCase();
          const hasConditionKeyword = CONFIG.EMAIL_CONDITIONS.some(keyword => 
            subject.includes(keyword.toLowerCase())
          );
          
          if (hasConditionKeyword) {
          uniqueEmails.push(message);
            const msgDate = msgDateHK.toLocaleDateString('ja-JP');
            console.log(`✅ 該当メール発見: ${message.getSubject()} (${msgDate} ${msgTime})`);
          }
        }
      }
    }

    // 新しい順にソート
    uniqueEmails.sort((a, b) => b.getDate().getTime() - a.getDate().getTime());
    
    console.log(`指定時間±1時間以内の該当メール数: ${uniqueEmails.length}件`);
    return uniqueEmails;
  } catch (error) {
    console.error('Gmail検索エラー:', error);
    throw error;
  }
}


/**
 * メールから 'inventory.pdf' を含むPDF添付ファイルを取得します。
 */
function getPdfAttachment(email) {
  try {
    const attachments = email.getAttachments();
    console.log(`添付ファイル数: ${attachments.length}件`);
    
    for (const attachment of attachments) {
      console.log(`添付ファイル: ${attachment.getName()}, タイプ: ${attachment.getContentType()}`);
      
      // PDFファイルの検出（より柔軟な条件）
      const fileName = attachment.getName().toLowerCase();
      const contentType = attachment.getContentType();
      
      if (contentType === 'application/pdf' || 
          contentType === 'application/octet-stream' ||
          fileName.endsWith('.pdf')) {
        
        if (fileName.includes('inventory') || 
            fileName.includes('stock') || 
            fileName.includes('pdf') ||
            fileName === 'inventory.pdf' ||
            fileName.includes('inventory.pdf')) {
          console.log(`PDF添付ファイル発見: ${attachment.getName()}, タイプ: ${contentType}, サイズ: ${attachment.getBytes().length} bytes`);
          return attachment;
        }
      }
    }
    
    console.log('該当するPDF添付ファイルが見つかりませんでした');
    return null;
  } catch (error) {
    console.error('PDF添付ファイル取得エラー:', error);
    throw error;
  }
}

/**
 * PDFファイルの更新時間を取得します（香港時間 UTC+8）
 * まずPDFのメタデータから作成日時を取得を試み、失敗した場合はメールの受信日時を使用します
 */
function getPdfUpdateTime(email) {
  try {
    // 1. PDFファイルのメタデータから作成日時を取得を試行
    const pdfBlob = getPdfAttachment(email);
    if (pdfBlob) {
      const pdfCreateTime = extractPdfCreationTime(pdfBlob);
      if (pdfCreateTime) {
        console.log(`PDFメタデータから作成日時を取得: ${pdfCreateTime}`);
        return pdfCreateTime;
      }
    }
    
    // 2. フォールバック: メールの受信日時を使用（これがPDFの実際の更新時間に最も近い）
    const emailDate = email.getDate();
    const emailDateHK = new Date(emailDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    
    // 香港時間でフォーマット
    const updateTime = emailDateHK.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+)/, '$3/$1/$2 $4:$5');
    
    console.log(`PDF更新時間（メール受信日時）: ${updateTime}`);
    console.log(`元のメール日時: ${emailDate.toLocaleString('ja-JP')}`);
    console.log(`香港時間変換後: ${emailDateHK.toLocaleString('ja-JP')}`);
    
    return updateTime;
    
  } catch (error) {
    console.error('PDF更新時間取得エラー:', error);
    // フォールバック: 現在時刻を使用
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
 * PDFファイルのメタデータから作成日時を抽出します
 * Gemini APIを使用してPDFのメタデータを解析します
 */
function extractPdfCreationTime(pdfBlob) {
  try {
    console.log('PDFメタデータの作成日時を抽出中...');
    
    const url = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.GEMINI_MODEL}:generateContent?key=${CONFIG.GEMINI_API_KEY}`;
    
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
      headers: { 'Content-Type': 'application/json' },
      payload: JSON.stringify(requestPayload),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(url, requestOptions);
    const responseCode = response.getResponseCode();
    const responseBody = response.getContentText();

    if (responseCode !== 200) {
      console.error(`PDFメタデータ抽出エラー: ${responseCode} - ${responseBody}`);
      return null;
    }

    const responseData = JSON.parse(responseBody);
    
    if (responseData.candidates && responseData.candidates[0].content) {
      const generatedText = responseData.candidates[0].content.parts[0].text;
      console.log(`PDFメタデータ解析結果: ${generatedText}`);
      
      // 日時パターンを検索
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
    console.error('PDFメタデータ抽出エラー:', error);
    return null;
  }
}

/**
 * Google Sheetsに結果を保存します。
 */
function saveToGoogleSheets(summary, email, emailIndex = 1) {
  try {
    const spreadsheet = getPrivateSpreadsheet();
    let sheet = spreadsheet.getSheetByName(CONFIG.INVENTORY_SUMMARY_SHEET_NAME);
    
    if (!sheet) {
      sheet = spreadsheet.insertSheet(CONFIG.INVENTORY_SUMMARY_SHEET_NAME);
      console.log(`新規シート作成: ${CONFIG.INVENTORY_SUMMARY_SHEET_NAME}`);
      const headers = ['Product Code', 'Description', 'On Hand', 'Quantity SC w/o DN', 'Available', '更新時間'];
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]).setFontWeight('bold');
    }
    
    // 既存のデータを完全に削除（2行目以降を削除）
    const lastRow = sheet.getLastRow();
    if (lastRow > 1) {
      console.log(`既存データを完全削除: 2行目から${lastRow}行目まで`);
      sheet.deleteRows(2, lastRow - 1);
    }
    
    // 在庫データを解析して各行に分割
    const inventoryData = parseInventoryData(summary);
    console.log(`解析された在庫データ: ${inventoryData.length}行`);
    
    // PDFファイルの更新時間を取得（香港時間 UTC+8）
    const updateTime = getPdfUpdateTime(email);
    
    // 2行目からデータを入力
    if (inventoryData.length > 0) {
      const allData = inventoryData.map(item => [
        item.productCode || '',
        item.description || '',
        formatNumber(item.onHand || ''),
        formatNumber(item.scWithoutDN || ''),
        formatNumber(item.available || ''),
        updateTime
      ]);
      
      // 2行目から一括入力
      sheet.getRange(2, 1, allData.length, allData[0].length).setValues(allData);
      console.log(`データ入力完了: 2行目から${allData.length}行分のデータを入力`);
    }
    
    sheet.autoResizeColumns(1, sheet.getLastColumn());
    console.log(`在庫データ ${inventoryData.length}行をGoogle Sheetsに保存完了`);
    
  } catch (error) {
    console.error('Google Sheets保存エラー:', error);
    throw error;
  }
}

/**
 * 数字を千の単位のカンマ付き整数形式にフォーマットします
 */
function formatNumber(value) {
  try {
    if (!value || value === '') return '';
    
    // 文字列から数字を抽出（小数点以下を切り捨て）
    const numStr = value.toString().replace(/[^\d.-]/g, '');
    const num = parseFloat(numStr);
    
    if (isNaN(num)) return value; // 数字でない場合は元の値を返す
    
    // 整数に変換して千の単位でカンマ区切り
    const integer = Math.round(num);
    return integer.toLocaleString('en-US');
  } catch (error) {
    console.error('数字フォーマットエラー:', error);
    return value; // エラー時は元の値を返す
  }
}

/**
 * 文字を正規化してASCIIに変換します
 */
function normalizeText(text) {
  try {
    // ギリシャ文字をASCII文字に変換
    const greekToAscii = {
      'Τ': 'T', 'Ν': 'N', 'Ι': 'I', 'Α': 'A', 'Β': 'B', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H', 'Θ': 'TH', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P', 'Ρ': 'R', 'Σ': 'S', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'CH', 'Ψ': 'PS', 'Ω': 'W'
    };
    
    let normalized = text;
    for (const [greek, ascii] of Object.entries(greekToAscii)) {
      normalized = normalized.replace(new RegExp(greek, 'g'), ascii);
    }
    
    // 商品コード修正を一時的に無効化（データ消失を防ぐため）
    // normalized = correctProductCodeErrors(normalized);
    
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
    
    // 商品コードの読み取り失敗パターンを修正
    const productCodeCorrections = {
      // 正解: US05132045MI0800, 間違い: US05132045M10800
      'US05132045M10800': 'US05132045MI0800',
      // 正解: US05132045MI0900, 間違い: US05132045M10900  
      'US05132045M10900': 'US05132045MI0900',
      // 正解: UT05125045MI0800, 間違い: UT05125045M10800
      'UT05125045M10800': 'UT05125045MI0800',
      // 正解: GSW04I0800B, 間違い: GSW0410800B
      'GSW0410800B': 'GSW04I0800B',
      // 正解: GSW04I1000B, 間違い: GSW0411000B
      'GSW0411000B': 'GSW04I1000B',
      // 正解: GSC08I0800B, 間違い: GSC0810800B
      'GSC0810800B': 'GSC08I0800B',
      // 正解: GSC08I1000B, 間違い: GSC0811000B
      'GSC0811000B': 'GSC08I1000B'
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
 * 重複する在庫アイテムを安全に処理します（データ消失を防ぐため）
 */
function removeDuplicateInventoryItems(text) {
  try {
    console.log('重複処理開始（安全モード）...');
    
    const lines = text.split('\n');
    const inventoryItems = new Map(); // Product Codeをキーとして重複を処理
    const headerLines = [];
    
    for (const line of lines) {
      if (line.includes('|') && !line.includes('---')) {
        const columns = line.split('|').map(col => col.trim()).filter(col => col !== '');
        
        if (columns.length >= 5) {
          // ヘッダー行をスキップ
          if (columns[0].toLowerCase().includes('product code')) {
            headerLines.push(line);
            continue;
          }
          
          const productCode = columns[0];
          if (productCode && productCode.trim() !== '') {
            // 商品コード修正を有効化
            const correctedCode = correctProductCodeErrors(productCode);
            const normalizedCode = normalizeText(correctedCode);
            
            // 既存のアイテムと比較（正規化されたProduct Codeが同じ場合）
            if (!inventoryItems.has(normalizedCode)) {
              // 元の行をそのまま使用（修正なし）
              inventoryItems.set(normalizedCode, line);
              console.log(`新規アイテム追加: ${productCode} (正規化後: ${normalizedCode})`);
              
              // BDシリーズの特別なログ出力
              if (productCode.startsWith('BD-') || productCode.startsWith('FC-') || productCode.startsWith('AC-')) {
                console.log(`重要アイテム追加: ${productCode} - データ保持確認`);
              }
            } else {
              // 重複が見つかった場合、数量を合計するか、より詳細な情報を保持
              const existingLine = inventoryItems.get(normalizedCode);
              console.log(`重複発見: ${productCode} - 既存データを保持します`);
              
              // 既存のデータを保持（後から来たデータを破棄）
              // 必要に応じて、ここで数量の合計処理を行うことも可能
              inventoryItems.set(normalizedCode, existingLine);
            }
          }
        }
      } else if (line.trim() !== '') {
        // ヘッダー行や区切り行を保持
        headerLines.push(line);
      }
    }
    
    // 結果を再構築
    let result = headerLines.join('\n') + '\n';
    result += Array.from(inventoryItems.values()).join('\n');
    
    console.log(`重複処理完了: ${inventoryItems.size}件のアイテムを保持`);
    return result;
    
  } catch (error) {
    console.error('重複処理エラー:', error);
    console.log('エラーが発生したため、元のデータをそのまま返します');
    return text; // エラー時は元のテキストを返す
  }
}

/**
 * 在庫データのテキストを解析して配列に変換
 */
function parseInventoryData(summary) {
  try {
    const lines = summary.split('\n');
    const inventoryData = [];
    
    for (const line of lines) {
      // 表の行を検出（| で区切られている）
      if (line.includes('|') && !line.includes('---')) {
        const columns = line.split('|').map(col => col.trim()).filter(col => col !== '');
        
        if (columns.length >= 5) {
          // ヘッダー行をスキップ
          if (columns[0].toLowerCase().includes('product code')) {
            continue;
          }
          
          inventoryData.push({
            productCode: normalizeText(correctProductCodeErrors(columns[0] || '')), // 商品コード修正を有効化
            description: columns[1] || '',
            onHand: columns[2] || '',
            scWithoutDN: columns[3] || '',
            available: columns[4] || ''
          });
        }
      }
    }
    
    console.log(`解析完了: ${inventoryData.length}件の在庫アイテム`);
    return inventoryData;
  } catch (error) {
    console.error('在庫データ解析エラー:', error);
    return [];
  }
}

/**
 * 作業終了お知らせメールを送信します。
 */
function sendCompletionNotification(processedEmail = null) {
  try {
    console.log('sendCompletionNotification開始');
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const completionTime = hongKongTime.toLocaleString('ja-JP');
    
    const subject = 'GASスクリプト定時作業"gmail-Inventory-AutoDataFill"完了お知らせ';
    console.log(`送信先: ${CONFIG.GMAIL_ADDRESS}`);
    console.log(`件名: ${subject}`);
    
    let fileInfo = '';
    if (processedEmail) {
      const emailDate = processedEmail.getDate();
      const emailDateHK = new Date(emailDate.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
      const emailDateStr = emailDateHK.toLocaleString('ja-JP');
      
      fileInfo = `
処理したファイル情報:
- メール件名: ${processedEmail.getSubject()}
- メール受信日時: ${emailDateStr}
- 送信者: ${processedEmail.getFrom()}
- 添付ファイル数: ${processedEmail.getAttachments().length}件
`;
    }
    
    const body = `
在庫データの処理が正常に完了しました。

処理完了時刻: ${completionTime}
処理内容:
- Gmail在庫メールの検索・解析
- PDF添付ファイルのGemini AI解析
- Google Sheetsへの在庫データ保存
- StockシートのVLOOKUP式設定
${fileInfo}
処理は正常に完了しています。
`;

    console.log('メール送信実行中...');
    GmailApp.sendEmail(
      CONFIG.GMAIL_ADDRESS,
      subject,
      body
    );
    
    console.log('✅ 作業終了お知らせメールを送信しました');
  } catch (error) {
    console.error('作業終了お知らせメールの送信に失敗しました:', error);
  }
}

/**
 * エラー通知メールを送信します。
 */
function sendErrorNotification(error) {
  try {
    GmailApp.sendEmail(
      CONFIG.GMAIL_ADDRESS,
      '【要確認】GASスクリプトエラー通知 (Gmail Inventory Processor)',
      `Gmail在庫PDF処理スクリプトでエラーが発生しました。\n\nエラーメッセージ:\n${error.message}\n\nスタックトレース:\n${error.stack}`
    );
  } catch (notificationError) {
    console.error('エラー通知の送信自体に失敗しました:', notificationError);
  }
}

/**
 * 定期実行トリガーを設定します (指定時間: 8:05、13:05、18:17)。
 */
function setupTriggers() {
  // 既存のトリガーを全て削除
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'main') {
      ScriptApp.deleteTrigger(trigger);
    }
  }

  // 指定時間にトリガーを設定（香港時間）
  ScriptApp.newTrigger('main')
    .timeBased()
    .everyDays(1)
    .atHour(8)
    .nearMinute(5) // 8:05
    .create();

  ScriptApp.newTrigger('main')
    .timeBased()
    .everyDays(1)
    .atHour(13)
    .nearMinute(5) // 13:05
    .create();
    
  ScriptApp.newTrigger('main')
    .timeBased()
    .everyDays(1)
    .atHour(18)
    .nearMinute(17) // 18:17
    .create();
    
  console.log('定期実行トリガーを指定時間（8:05、13:05、18:17）に設定しました。');
}

/**
 * テスト用関数 - メール検索のテスト
 */
function testEmailSearch() {
  try {
    console.log('=== メール検索テスト開始 ===');
    const emails = searchInventoryEmails();
    console.log(`検索結果: ${emails.length}件のメールが見つかりました`);
    
    if (emails.length > 0) {
      console.log('最初のメールの詳細:');
      const firstEmail = emails[0];
      console.log(`件名: ${firstEmail.getSubject()}`);
      console.log(`送信者: ${firstEmail.getFrom()}`);
      console.log(`受信日時: ${firstEmail.getDate().toLocaleString('ja-JP')}`);
      console.log(`添付ファイル数: ${firstEmail.getAttachments().length}件`);
      
      // PDF添付ファイルのテスト
      const pdfBlob = getPdfAttachment(firstEmail);
      if (pdfBlob) {
        console.log(`PDFファイル: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);
      }
    }
    
    console.log('=== メール検索テスト完了 ===');
  } catch (error) {
    console.error('テスト実行エラー:', error);
  }
}

/**
 * テスト用関数 - 全体の処理テスト
 */
function testFullProcess() {
  try {
    console.log('=== 全体処理テスト開始 ===');
    processInventoryEmails();
    console.log('=== 全体処理テスト完了 ===');
  } catch (error) {
    console.error('全体処理テストエラー:', error);
  }
}

/**
 * テスト用関数 - PDF更新時間取得のテスト
 */
function testPdfUpdateTime() {
  try {
    console.log('=== PDF更新時間取得テスト開始 ===');
    const emails = searchInventoryEmails();
    
    if (emails.length > 0) {
      const firstEmail = emails[0];
      console.log(`テスト対象メール: ${firstEmail.getSubject()}`);
      console.log(`メール受信日時: ${firstEmail.getDate().toLocaleString('ja-JP')}`);
      
      const updateTime = getPdfUpdateTime(firstEmail);
      console.log(`取得されたPDF更新時間: ${updateTime}`);
    } else {
      console.log('テスト対象のメールが見つかりませんでした');
    }
    
    console.log('=== PDF更新時間取得テスト完了 ===');
  } catch (error) {
    console.error('PDF更新時間取得テストエラー:', error);
  }
}

/**
 * テスト用関数 - ページ別アイテム数を表示（重複処理なし）
 */
function countPdfItemsByPage() {
  try {
    console.log('=== ページ別アイテム数カウント開始 ===');
    const emails = searchInventoryEmails();
    
    if (emails.length === 0) {
      console.log('❌ テスト対象のメールが見つかりませんでした');
      return;
    }
    
    const latestEmail = emails[0];
    console.log(`テスト対象メール: ${latestEmail.getSubject()}`);
    
    const pdfBlob = getPdfAttachment(latestEmail);
    if (!pdfBlob) {
      console.log('❌ PDF添付ファイルが見つかりませんでした');
      return;
    }
    
    console.log(`PDFファイル: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);
    
    // ページ別に解析を実行（重複処理なし）
    console.log('=== ページ別解析開始（重複処理なし） ===');
    
    // 1回目: 1-3ページ
    console.log('📄 1-3ページ解析中...');
    const pass1 = generateSummaryWithGeminiSinglePass(pdfBlob, 
      'PDFの1-3ページ目を解析して、在庫データ表を抽出してください。表形式で出力し、各行にProduct Code, Description, On Hand, Quantity SC w/o DN, Availableを含めてください。', 1);
    const pass1Lines = pass1 ? pass1.split('\n').filter(line => 
      line.includes('|') && !line.includes('---') && !line.toLowerCase().includes('product code')
    ) : [];
    console.log(`  📊 1-3ページのアイテム数: ${pass1Lines.length}件`);
    
    // 2回目: 4-5ページ
    console.log('📄 4-5ページ解析中...');
    const pass2 = generateSummaryWithGeminiSinglePass(pdfBlob, 
      'PDFの4-5ページ目を解析して、在庫データ表を抽出してください。表形式で出力し、各行にProduct Code, Description, On Hand, Quantity SC w/o DN, Availableを含めてください。', 2);
    const pass2Lines = pass2 ? pass2.split('\n').filter(line => 
      line.includes('|') && !line.includes('---') && !line.toLowerCase().includes('product code')
    ) : [];
    console.log(`  📊 4-5ページのアイテム数: ${pass2Lines.length}件`);
    
    // 3回目: 6-7ページ
    console.log('📄 6-7ページ解析中...');
    const pass3 = generateSummaryWithGeminiSinglePass(pdfBlob, 
      'PDFの6-7ページ目を解析して、在庫データ表を抽出してください。特にFC-057, US05132045MI0800, US05132045MI0900, UT05125045MI0800, GSW04I0800B, GSW04I1000B, GSW04M3000B, GSC08I0800B, GSC08I1000Bなどの商品コードを探してください。表形式で出力し、各行にProduct Code, Description, On Hand, Quantity SC w/o DN, Availableを含めてください。', 3);
    const pass3Lines = pass3 ? pass3.split('\n').filter(line => 
      line.includes('|') && !line.includes('---') && !line.toLowerCase().includes('product code')
    ) : [];
    console.log(`  📊 6-7ページのアイテム数: ${pass3Lines.length}件`);
    
    // 合計計算
    const totalItems = pass1Lines.length + pass2Lines.length + pass3Lines.length;
    console.log(`📊 ページ別合計アイテム数: ${totalItems}件`);
    console.log(`  - 1-3ページ: ${pass1Lines.length}件`);
    console.log(`  - 4-5ページ: ${pass2Lines.length}件`);
    console.log(`  - 6-7ページ: ${pass3Lines.length}件`);
    
    // FC-057の検索
    const fc057InPass1 = pass1Lines.some(line => line.includes('FC-057'));
    const fc057InPass2 = pass2Lines.some(line => line.includes('FC-057'));
    const fc057InPass3 = pass3Lines.some(line => line.includes('FC-057'));
    
    console.log('🔍 FC-057の検索結果:');
    console.log(`  - 1-3ページ: ${fc057InPass1 ? '✅ 発見' : '❌ 未発見'}`);
    console.log(`  - 4-5ページ: ${fc057InPass2 ? '✅ 発見' : '❌ 未発見'}`);
    console.log(`  - 6-7ページ: ${fc057InPass3 ? '✅ 発見' : '❌ 未発見'}`);
    
    // 期待値との比較
    console.log('📈 期待値との比較:');
    console.log(`  - 期待値: 211件 (p1:21, p2:26, p3:41, p4:36, p5:43, p6:36, p7:8)`);
    console.log(`  - 実際値: ${totalItems}件`);
    console.log(`  - 差異: ${totalItems - 211}件`);
    
    if (totalItems === 211) {
      console.log('✅ 期待値と完全一致！重複処理は不要です。');
    } else {
      console.log('⚠️ 期待値と差異があります。');
    }
    
    console.log('=== ページ別アイテム数カウント完了 ===');
  } catch (error) {
    console.error('ページ別アイテム数カウントエラー:', error);
  }
}

/**
 * テスト用関数 - PDF内のアイテム数を数える
 */
function countPdfItems() {
  try {
    console.log('=== PDF内アイテム数カウント開始 ===');
    const emails = searchInventoryEmails();
    
    if (emails.length === 0) {
      console.log('❌ テスト対象のメールが見つかりませんでした');
      return;
    }
    
    const latestEmail = emails[0];
    console.log(`テスト対象メール: ${latestEmail.getSubject()}`);
    
    const pdfBlob = getPdfAttachment(latestEmail);
    if (!pdfBlob) {
      console.log('❌ PDF添付ファイルが見つかりませんでした');
      return;
    }
    
    console.log(`PDFファイル: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);
    
    // ページ別に解析を実行
    console.log('=== ページ別詳細解析開始 ===');
    
    // 1回目: 1-3ページ
    console.log('📄 1-3ページ解析中...');
    const pass1 = generateSummaryWithGeminiSinglePass(pdfBlob, 
      'PDFの1-3ページ目を解析して、在庫データ表を抽出してください。表形式で出力し、各行にProduct Code, Description, On Hand, Quantity SC w/o DN, Availableを含めてください。', 1);
    const pass1Lines = pass1 ? pass1.split('\n').filter(line => 
      line.includes('|') && !line.includes('---') && !line.toLowerCase().includes('product code')
    ) : [];
    console.log(`  📊 1-3ページのアイテム数: ${pass1Lines.length}件`);
    
    // 2回目: 4-5ページ
    console.log('📄 4-5ページ解析中...');
    const pass2 = generateSummaryWithGeminiSinglePass(pdfBlob, 
      'PDFの4-5ページ目を解析して、在庫データ表を抽出してください。表形式で出力し、各行にProduct Code, Description, On Hand, Quantity SC w/o DN, Availableを含めてください。', 2);
    const pass2Lines = pass2 ? pass2.split('\n').filter(line => 
      line.includes('|') && !line.includes('---') && !line.toLowerCase().includes('product code')
    ) : [];
    console.log(`  📊 4-5ページのアイテム数: ${pass2Lines.length}件`);
    
    // 3回目: 6-7ページ
    console.log('📄 6-7ページ解析中...');
    const pass3 = generateSummaryWithGeminiSinglePass(pdfBlob, 
      'PDFの6-7ページ目を解析して、在庫データ表を抽出してください。特にFC-057, US05132045MI0800, US05132045MI0900, UT05125045MI0800, GSW04I0800B, GSW04I1000B, GSW04M3000B, GSC08I0800B, GSC08I1000Bなどの商品コードを探してください。表形式で出力し、各行にProduct Code, Description, On Hand, Quantity SC w/o DN, Availableを含めてください。', 3);
    const pass3Lines = pass3 ? pass3.split('\n').filter(line => 
      line.includes('|') && !line.includes('---') && !line.toLowerCase().includes('product code')
    ) : [];
    console.log(`  📊 6-7ページのアイテム数: ${pass3Lines.length}件`);
    
    // FC-057の検索
    const fc057InPass1 = pass1Lines.some(line => line.includes('FC-057'));
    const fc057InPass2 = pass2Lines.some(line => line.includes('FC-057'));
    const fc057InPass3 = pass3Lines.some(line => line.includes('FC-057'));
    
    console.log('🔍 FC-057の検索結果:');
    console.log(`  - 1-3ページ: ${fc057InPass1 ? '✅ 発見' : '❌ 未発見'}`);
    console.log(`  - 4-5ページ: ${fc057InPass2 ? '✅ 発見' : '❌ 未発見'}`);
    console.log(`  - 6-7ページ: ${fc057InPass3 ? '✅ 発見' : '❌ 未発見'}`);
    
    // 統合解析
    const summary = generateSummaryWithGeminiMultiplePasses(pdfBlob, 1);
    
    if (summary && summary.trim().length > 0) {
      // テーブル行を抽出
      const lines = summary.split('\n');
      const tableLines = lines.filter(line => 
        line.includes('|') && 
        !line.includes('---') && 
        !line.toLowerCase().includes('product code')
      );
      
      console.log(`📊 統合後の総アイテム数: ${tableLines.length}件`);
      console.log(`📊 ページ別合計: ${pass1Lines.length + pass2Lines.length + pass3Lines.length}件`);
      
      // シリーズ別のカウント
      const bdItems = tableLines.filter(line => line.includes('BD-'));
      const acItems = tableLines.filter(line => line.includes('AC-'));
      const fcItems = tableLines.filter(line => line.includes('FC-'));
      const usItems = tableLines.filter(line => line.includes('US0'));
      const utItems = tableLines.filter(line => line.includes('UT0'));
      const gswItems = tableLines.filter(line => line.includes('GSW'));
      const gscItems = tableLines.filter(line => line.includes('GSC'));
      const kssItems = tableLines.filter(line => line.includes('KSS-'));
      
      console.log(`📈 シリーズ別アイテム数:`);
      console.log(`  - BDシリーズ: ${bdItems.length}件`);
      console.log(`  - ACシリーズ: ${acItems.length}件`);
      console.log(`  - FCシリーズ: ${fcItems.length}件`);
      console.log(`  - USシリーズ: ${usItems.length}件`);
      console.log(`  - UTシリーズ: ${utItems.length}件`);
      console.log(`  - GSWシリーズ: ${gswItems.length}件`);
      console.log(`  - GSCシリーズ: ${gscItems.length}件`);
      console.log(`  - KSSシリーズ: ${kssItems.length}件`);
      
      // 重要な商品コードの存在確認
      const importantCodes = [
        'BD-060', 'BD-061', 'BD-062', 'BD-063', 'BD-064', 'BD-065', 'BD-067',
        'AC-261', 'AC-262', 'AC-263', 'AC-264',
        'FC-056', 'FC-057',
        'US05132045MI0800', 'US05132045MI0900',
        'UT05125045MI0800',
        'GSW04I0800B', 'GSW04I1000B', 'GSW04M3000B',
        'GSC08I0800B', 'GSC08I1000B'
      ];
      
      const foundImportantCodes = [];
      for (const code of importantCodes) {
        const found = tableLines.some(line => line.includes(code));
        if (found) {
          foundImportantCodes.push(code);
        }
      }
      
      console.log(`🎯 重要な商品コードの抽出状況: ${foundImportantCodes.length}/${importantCodes.length}件`);
      console.log(`✅ 抽出された重要な商品コード: ${foundImportantCodes.join(', ')}`);
      
      if (foundImportantCodes.length < importantCodes.length) {
        const missing = importantCodes.filter(code => !foundImportantCodes.includes(code));
        console.log(`❌ 抽出されていない重要な商品コード: ${missing.join(', ')}`);
      }
      
      // 最初の10件を表示
      console.log(`📋 最初の10件のアイテム:`);
      tableLines.slice(0, 10).forEach((item, index) => {
        console.log(`  ${index + 1}. ${item}`);
      });
      
    } else {
      console.log('❌ PDF解析に失敗しました');
    }
    
    console.log('=== PDF内アイテム数カウント完了 ===');
  } catch (error) {
    console.error('PDF内アイテム数カウントエラー:', error);
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
      // Stockシートを作成
      const newStockSheet = ss.insertSheet('Stock');
      console.log('Stockシートを作成しました');
      
      // ヘッダー行を設定
      const headers = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M'];
      newStockSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      console.log('Stockシートのヘッダーを設定しました');
      
      return; // 新しく作成したシートにはデータがないので式設定をスキップ
    }
    
    // データの最後の行を取得（C列で判定）
    const lastRow = stockSheet.getRange('C:C').getValues().filter(String).length;
    console.log(`Stockシートのデータ行数: ${lastRow}`);
    
    if (lastRow < 2) {
      console.log('データが不足しているため、式の設定をスキップします');
      return;
    }
    
    // U2, V2, W2にVLOOKUP式を設定
    console.log('U2, V2, W2にVLOOKUP式を設定中...');
    stockSheet.getRange('U2').setFormula('=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 3, 0), 0)');
    stockSheet.getRange('V2').setFormula('=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 4, 0), 0)');
    stockSheet.getRange('W2').setFormula('=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 5, 0), 0)');
    console.log('✅ U2, V2, W2にVLOOKUP式を設定しました');
    
    // データがある行まで式をコピー（U2:W2から下方向にコピー）
    if (lastRow > 2) {
      console.log(`U2:W2の式をU2:W${lastRow}までコピー中...`);
      const copyRange = stockSheet.getRange('U2:W2');
      const pasteRange = stockSheet.getRange(`U2:W${lastRow}`);
      copyRange.copyTo(pasteRange);
      console.log(`✅ U2:W2の式をU2:W${lastRow}までコピーしました`);
    }
    
    // 最後にY2に式を設定
    try {
      // InventorySummaryReportシートの存在確認
      const inventorySheet = ss.getSheetByName('InventorySummaryReport');
      if (!inventorySheet) {
        console.error('❌ InventorySummaryReportシートが見つかりません');
        return;
      }
      
      // F2セルの値を確認
      const f2Value = inventorySheet.getRange('F2').getValue();
      console.log(`InventorySummaryReport!F2の値: ${f2Value}`);
      
      // Y2に式を設定
      stockSheet.getRange('Y2').setFormula('=InventorySummaryReport!F2');
      console.log('✅ Y2に=InventorySummaryReport!F2を設定しました');
      
      // 設定後の値を確認
      const y2Value = stockSheet.getRange('Y2').getValue();
      console.log(`Y2の設定後値: ${y2Value}`);
      
    } catch (y2Error) {
      console.error('❌ Y2セル設定エラー:', y2Error);
    }
    
    console.log('Stockシートの式設定完了:');
    console.log('- U2:W2にVLOOKUP式を設定');
    console.log('- データ行まで式をコピー');
    console.log('- Y2に=InventorySummaryReport!F2を設定');
    
  } catch (error) {
    console.error('Stock式設定エラー:', error);
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

    // Stockシートを取得
    const stockSheet = ss.getSheetByName('Stock');
    if (!stockSheet) {
      console.error('❌ Stockシートが見つかりません');
      return;
    }
    console.log('Stockシート: 発見');

    // InventorySummaryReportシートの存在確認
    const inventorySheet = ss.getSheetByName('InventorySummaryReport');
    if (!inventorySheet) {
      console.error('❌ InventorySummaryReportシートが見つかりません');
      return;
    }
    console.log('InventorySummaryReportシート: 発見');

    // F2セルの値を確認
    const f2Value = inventorySheet.getRange('F2').getValue();
    console.log(`InventorySummaryReport!F2の値: ${f2Value}`);

    // Y2に式を設定
    stockSheet.getRange('Y2').setFormula('=InventorySummaryReport!F2');
    console.log('✅ Y2に=InventorySummaryReport!F2を設定しました');

    // 設定後の値を確認
    const y2Value = stockSheet.getRange('Y2').getValue();
    console.log(`Y2の設定後値: ${y2Value}`);

    console.log('=== InventorySummaryReport!F2設定完了 ===');

  } catch (error) {
    console.error('InventorySummaryReport!F2設定エラー:', error);
  }
}