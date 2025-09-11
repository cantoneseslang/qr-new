/**
 * GAS Gmail Inventory Processor テスト用関数
 * 各機能を個別にテストするための関数群
 */

/**
 * Gmail検索機能のテスト（今日の日付フィルタリング対応）
 */
function testGmailSearch() {
  try {
    console.log('=== Gmail検索テスト開始 ===');
    
    // 今日の日付を取得
    const today = new Date();
    const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 0, 0, 0);
    const todayEnd = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59);
    
    console.log(`今日の検索範囲: ${todayStart.toLocaleString('ja-JP')} ～ ${todayEnd.toLocaleString('ja-JP')}`);
    
    // 今日の日付を含む検索クエリを作成
    const todayQuery = `subject:inventory has:attachment filename:inventory.pdf after:${formatDateForGmail(todayStart)} before:${formatDateForGmail(todayEnd)}`;
    console.log(`検索クエリ: ${todayQuery}`);
    
    const threads = GmailApp.search(todayQuery, 0, 10);
    const emails = [];
    
    console.log(`検索結果: ${threads.length}件のスレッドが見つかりました`);
    
    threads.forEach((thread, index) => {
      const messages = thread.getMessages();
      console.log(`スレッド ${index + 1}:`);
      console.log(`- メッセージ数: ${messages.length}`);
      
      messages.forEach((message, msgIndex) => {
        const messageDate = message.getDate();
        const isToday = messageDate >= todayStart && messageDate <= todayEnd;
        
        console.log(`  メッセージ ${msgIndex + 1}:`);
        console.log(`  - 件名: ${message.getSubject()}`);
        console.log(`  - 送信者: ${message.getFrom()}`);
        console.log(`  - 日付: ${message.getDate()}`);
        console.log(`  - 今日のメール: ${isToday ? 'はい' : 'いいえ'}`);
        console.log(`  - 添付ファイル数: ${message.getAttachments().length}`);
        
        if (isToday && message.getAttachments().length > 0) {
          emails.push(message);
          console.log(`  → 今日の該当メールとして追加`);
        }
        
        message.getAttachments().forEach((attachment, attIndex) => {
          console.log(`    添付ファイル ${attIndex + 1}: ${attachment.getName()}`);
        });
      });
    });
    
    console.log(`今日の該当メール数: ${emails.length}件`);
    console.log('=== Gmail検索テスト完了 ===');
    return emails;
    
  } catch (error) {
    console.error('Gmail検索テストエラー:', error);
    throw error;
  }
}

/**
 * Gmail検索用の日付フォーマット関数（テスト用）
 */
function formatDateForGmail(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}/${month}/${day}`;
}

/**
 * Google Sheets接続テスト
 */
function testGoogleSheetsConnection() {
  try {
    console.log('=== Google Sheets接続テスト開始 ===');
    
    const SHEET_ID = '1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M';
    const spreadsheet = SpreadsheetApp.openById(SHEET_ID);
    
    console.log(`スプレッドシート名: ${spreadsheet.getName()}`);
    console.log(`シート数: ${spreadsheet.getSheets().length}`);
    
    // 既存のシート一覧を表示
    const sheets = spreadsheet.getSheets();
    sheets.forEach((sheet, index) => {
      console.log(`シート ${index + 1}: ${sheet.getName()}`);
    });
    
    // InventorySummaryReportシートの存在確認
    const targetSheet = spreadsheet.getSheetByName('InventorySummaryReport');
    if (targetSheet) {
      console.log('InventorySummaryReportシートが存在します');
      console.log(`最終行: ${targetSheet.getLastRow()}`);
      console.log(`最終列: ${targetSheet.getLastColumn()}`);
    } else {
      console.log('InventorySummaryReportシートが存在しません（新規作成が必要）');
    }
    
    console.log('=== Google Sheets接続テスト完了 ===');
    return spreadsheet;
    
  } catch (error) {
    console.error('Google Sheets接続テストエラー:', error);
    throw error;
  }
}

/**
 * Gemini API接続テスト
 */
function testGeminiConnection() {
  try {
    console.log('=== Gemini API接続テスト開始 ===');
    
    const GEMINI_API_KEY = 'AIzaSyDny2k_jer095pYLo8dCiZEpHo8WHEgf_s';
    const testPrompt = 'こんにちは。これはテストメッセージです。';
    
    const response = UrlFetchApp.fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${GEMINI_API_KEY}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      payload: JSON.stringify({
        contents: [{
          parts: [{
            text: testPrompt
          }]
        }],
        generationConfig: {
          temperature: 0.7,
          maxOutputTokens: 100,
        }
      })
    });
    
    const responseData = JSON.parse(response.getContentText());
    console.log('Gemini API応答:', responseData);
    
    if (responseData.candidates && responseData.candidates[0] && responseData.candidates[0].content) {
      const generatedText = responseData.candidates[0].content.parts[0].text;
      console.log(`生成されたテキスト: ${generatedText}`);
      console.log('=== Gemini API接続テスト成功 ===');
      return true;
    } else {
      console.error('Gemini API応答の解析に失敗');
      return false;
    }
    
  } catch (error) {
    console.error('Gemini API接続テストエラー:', error);
    return false;
  }
}

/**
 * PDF処理テスト（サンプルデータ使用）
 */
function testPdfProcessing() {
  try {
    console.log('=== PDF処理テスト開始 ===');
    
    // サンプルPDFテキストを生成
    const samplePdfText = `
在庫管理レポート
日付: 2025年1月27日

製品一覧:
1. BD-060 - 泰山普通石膏板 - 在庫数: 200張
2. US0503206MM2440 - Stud - 在庫数: 200只
3. AC-258 - KIRII Corner Bead - 在庫数: 50個
4. AC-261 - 黃岩綿 - 在庫数: 10包

総在庫数: 460点
更新者: システム管理者
    `;
    
    console.log(`サンプルPDFテキスト: ${samplePdfText}`);
    
    // Gemini APIで要約生成をテスト
    const summary = generateSummaryWithGemini(samplePdfText);
    console.log(`生成された要約: ${summary}`);
    
    console.log('=== PDF処理テスト完了 ===');
    return summary;
    
  } catch (error) {
    console.error('PDF処理テストエラー:', error);
    throw error;
  }
}

/**
 * 全機能の統合テスト
 */
function runFullTest() {
  try {
    console.log('=== 全機能統合テスト開始 ===');
    
    // 1. Gmail検索テスト
    console.log('\n1. Gmail検索テスト');
    const emails = testGmailSearch();
    
    // 2. Google Sheets接続テスト
    console.log('\n2. Google Sheets接続テスト');
    const spreadsheet = testGoogleSheetsConnection();
    
    // 3. Gemini API接続テスト
    console.log('\n3. Gemini API接続テスト');
    const geminiResult = testGeminiConnection();
    
    // 4. PDF処理テスト
    console.log('\n4. PDF処理テスト');
    const summary = testPdfProcessing();
    
    // 5. 結果の保存テスト
    console.log('\n5. 結果保存テスト');
    if (geminiResult && summary) {
      const testEmail = {
        getSubject: () => 'テストメール',
        getFrom: () => 'test@example.com'
      };
      
      saveToGoogleSheets(summary, testEmail);
      console.log('テスト結果をGoogle Sheetsに保存しました');
    }
    
    console.log('\n=== 全機能統合テスト完了 ===');
    console.log('すべてのテストが正常に完了しました');
    
  } catch (error) {
    console.error('統合テストエラー:', error);
    console.log('一部のテストが失敗しました。詳細は上記のエラーログを確認してください。');
  }
}

/**
 * 設定値の確認
 */
function checkConfiguration() {
  console.log('=== 設定値確認 ===');
  console.log(`Gmailアドレス: ${CONFIG.GMAIL_ADDRESS}`);
  console.log(`シートID: ${CONFIG.SHEET_ID}`);
  console.log(`Gemini APIキー: ${CONFIG.GEMINI_API_KEY.substring(0, 10)}...`);
  console.log(`検索クエリ: ${CONFIG.SEARCH_QUERY}`);
  console.log(`対象シート名: ${CONFIG.INVENTORY_SUMMARY_SHEET_NAME}`);
  console.log('=== 設定値確認完了 ===');
}
