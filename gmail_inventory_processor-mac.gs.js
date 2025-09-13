/**
 * Gmail Inventory PDF Processor with Gemini AI
 * Gmailから「inventory」件名のメールを検索し、添付PDFをGemini 2.5で要約してGoogle Sheetsに保存
 * 指定時間（8:05、13:05、18:17）でGmailをチェックし、条件に合致するメールがあった場合にスクリプトを実行
 */

// 設定定数
const CONFIG = {
  GEMINI_API_KEY: 'AIzaSyDny2k_jer095pYLo8dCiZEpHo8WHEgf_s',
  GEMINI_MODEL: 'gemini-1.5-flash',
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
  RETRY_TRIGGER_FUNCTION: 'retryMain' // 再トライ用関数名
};

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
    console.log('=== 在庫メール処理完了、Stock式設定開始 ===');
    setStockFormulas();
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
    console.log('=== 在庫メール処理完了、Stock式設定開始 ===');
    setStockFormulas();
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
      throw error;
    }
    
    console.log('=== Gmail Inventory Processor 正常終了 ===');
  } catch (error) {
    console.error('スクリプト全体で致命的なエラーが発生しました:', error);
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
      throw error;
    }
    
    console.log('=== Gmail Inventory Processor 正常終了 ===');
  } catch (error) {
    console.error('スクリプト全体で致命的なエラーが発生しました:', error);
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
    
    // 指定時間内かチェック（±60分の許容範囲 - 手動テスト用）
    for (const checkTime of CONFIG.CHECK_TIMES) {
      if (isWithinTimeRange(currentTime, checkTime, 60)) {
        console.log(`✅ 指定時間内です: ${checkTime} (±60分許容)`);
        return true;
      }
    }
    
    console.log(`❌ 指定時間外です: ${currentTime}`);
    return false;
    
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
 * PDFを1回で解析し、すべての在庫データを取得します。
 * @param {GoogleAppsScript.Base.Blob} pdfBlob - 解析するPDFファイル。
 * @param {number} emailIndex - 処理中のメール番号。
 * @return {string} すべての在庫データを統合したテキスト。
 */
function generateSummaryWithGeminiMultiplePasses(pdfBlob, emailIndex = 1) {
  try {
    console.log(`PDF解析開始 - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);
    
    const prompt = `
添付された在庫PDFファイルを解析し、製品アイテムをマークダウン形式のテーブルとして抽出してください。

# 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 表形式のデータのみを抽出し、それ以外のテキストは含めないこと。
- 最終的な出力はマークダウンのテーブルのみとし、前後の説明文は一切不要です。
- すべてのページの在庫アイテムを漏れなく抽出してください。
- 商品コードが不完全でも、数値データがあれば抽出してください。

以下の商品コードパターンを含むすべてのアイテムを抽出してください：
- TNIA, TNIC, TNIL, TNIW, TNMA, TNMC で始まるコード
- UU で始まるコード  
- V で始まるコード
- AC-, BD-, FC-, SW-, GSY, GHC, GHW, GSC, GSW で始まるコード
- その他すべての商品コード

各ページを隅から隅まで確認し、見落としがないようにしてください。
`;

    const result = generateSummaryWithGeminiSinglePass(pdfBlob, prompt, 1);
    
    if (!result || result.trim().length === 0) {
      console.log('解析結果が空です');
      return '';
    }
    
    console.log(`解析完了: ${result.split('\n').filter(line => line.includes('|')).length}行`);
    
    // 重複除去を実行
    const deduplicatedResult = removeDuplicateInventoryItems(result);
    const finalLines = deduplicatedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
    console.log(`重複除去後の総行数: ${finalLines.length}行`);
    
    return deduplicatedResult;
    
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

  try {
    console.log(`Gemini API 処理開始 - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);

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
        temperature: 0.1,      // 精度を求めるため創造性を低く設定
        maxOutputTokens: 16384, // 出力トークン数を倍増
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
      console.log(`解析結果の最初の500文字: ${generatedText.substring(0, 500)}`);
      
      return generatedText;
    } else {
      console.error(`Gemini APIからの予期しない応答:`, responseBody);
      throw new Error('Gemini APIから有効なコンテンツが返されませんでした。');
    }

  } catch (error) {
    console.error('Gemini API処理エラー:', error);
    throw error;
  }
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
    
    // 現在時刻に最も近い指定時間を特定（手動テスト用に±60分許容）
    let targetTime = null;
    for (const checkTime of CONFIG.CHECK_TIMES) {
      if (isWithinTimeRange(currentTime, checkTime, 60)) {
        targetTime = checkTime;
        break;
      }
    }
    
    if (!targetTime) {
      console.log('指定時間の±60分範囲外のため、メール検索をスキップします');
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
 * Google Sheetsに結果を保存します。
 */
function saveToGoogleSheets(summary, email, emailIndex = 1) {
  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SHEET_ID);
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
    
    // 更新時間をフォーマット（香港時間 UTC+8）
    const now = new Date();
    const hongKongTime = new Date(now.toLocaleString("en-US", {timeZone: "Asia/Hong_Kong"}));
    const updateTime = hongKongTime.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/(\d+)\/(\d+)\/(\d+),?\s+(\d+):(\d+)/, '$3/$1/$2 $4:$5');
    
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
    
    return normalized;
  } catch (error) {
    console.error('文字正規化エラー:', error);
    return text;
  }
}

/**
 * 重複する在庫アイテムを除去します
 */
function removeDuplicateInventoryItems(text) {
  try {
    console.log('重複除去処理開始...');
    
    const lines = text.split('\n');
    const inventoryItems = new Map(); // Product Codeをキーとして重複を除去
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
            // 文字を正規化して比較
            const normalizedCode = normalizeText(productCode);
            
            // 既存のアイテムと比較（正規化されたProduct Codeが同じ場合）
            if (!inventoryItems.has(normalizedCode)) {
              // 正規化されたコードで保存し、元の行を保持
              inventoryItems.set(normalizedCode, line);
            } else {
              console.log(`重複発見: ${productCode} (正規化後: ${normalizedCode})`);
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
    
    console.log(`重複除去完了: ${inventoryItems.size}件のユニークなアイテム`);
    return result;
    
  } catch (error) {
    console.error('重複除去エラー:', error);
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
            productCode: normalizeText(columns[0] || ''),
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
 * StockシートにVLOOKUP式とM2式を設定
 */
function setStockFormulas() {
  try {
    console.log('=== Stock式設定開始 ===');
    const ss = SpreadsheetApp.openById(CONFIG.SHEET_ID);
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
    
    // I2, J2, K2にVLOOKUP式を設定
    stockSheet.getRange('I2').setFormula('=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 3, 0), 0)');
    stockSheet.getRange('J2').setFormula('=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 4, 0), 0)');
    stockSheet.getRange('K2').setFormula('=IFERROR(VLOOKUP($C2,InventorySummaryReport!$A:$E, 5, 0), 0)');
    
    // データがある行まで式をコピー（I2:K2から下方向にコピー）
    if (lastRow > 2) {
      const copyRange = stockSheet.getRange('I2:K2');
      const pasteRange = stockSheet.getRange(`I2:K${lastRow}`);
      copyRange.copyTo(pasteRange);
      console.log(`I2:K2の式をI2:K${lastRow}までコピーしました`);
    }
    
    // 最後にM2に式を設定
    stockSheet.getRange('M2').setFormula('=InventorySummaryReport!F2');
    
    console.log('Stockシートの式設定完了:');
    console.log('- I2:K2にVLOOKUP式を設定');
    console.log('- データ行まで式をコピー');
    console.log('- M2に=InventorySummaryReport!F2を設定');
    
  } catch (error) {
    console.error('Stock式設定エラー:', error);
  }
}