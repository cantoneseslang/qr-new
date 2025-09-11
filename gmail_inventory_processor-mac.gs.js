/**
 * Gmail Inventory PDF Processor with Gemini AI
 * Gmailから「inventory」件名のメールを検索し、添付PDFをGemini 2.5で要約してGoogle Sheetsに保存
 */

// 設定定数
const CONFIG = {
  GEMINI_API_KEY: 'AIzaSyDny2k_jer095pYLo8dCiZEpHo8WHEgf_s',
  GEMINI_MODEL: 'gemini-1.5-flash',
  SHEET_ID: '1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M',
  GMAIL_ADDRESS: 'bestinksalesman@gmail.com',
  INVENTORY_SUMMARY_SHEET_NAME: 'InventorySummaryReport',
  SEARCH_QUERY: 'subject:inventory has:attachment filename:inventory.pdf'
};

/**
 * メイン実行関数（トリガー用）
 */
function main() {
  processInventoryEmails();
  setStockFormulas();
}

/**
 * 在庫メール処理関数
 */
function processInventoryEmails() {
  try {
    console.log('=== Gmail Inventory Processor 開始 ===');

    const emails = searchInventoryEmails();
    console.log(`検索結果: ${emails.length}件のメールが見つかりました`);

    if (emails.length === 0) {
      console.log('本日の処理対象メールはありませんでした。');
      return;
    }
    
    console.log(`本日のメール ${emails.length}件の処理を開始します。`);
    
    let processedCount = 0;
    for (let i = 0; i < emails.length; i++) {
      const email = emails[i];
      const mailInfo = `メール ${i + 1}/${emails.length} (件名: ${email.getSubject()})`;
      
      try {
        const startTime = new Date();
        console.log(`${mailInfo} - 処理開始: ${startTime.toLocaleString('ja-JP')}`);
        
        const pdfBlob = getPdfAttachment(email);
        if (!pdfBlob) {
          console.log(`${mailInfo} - PDF添付ファイルが見つかりませんでした。スキップします。`);
          continue;
        }
        
        console.log(`${mailInfo} - GeminiでPDF直接解析を開始します...`);
        const geminiStartTime = new Date();
        const summary = generateSummaryWithGeminiMultiplePasses(pdfBlob, i + 1); 
        const geminiEndTime = new Date();
        const geminiDuration = Math.round((geminiEndTime - geminiStartTime) / 1000);
        console.log(`${mailInfo} - Gemini解析完了 (処理時間: ${geminiDuration}秒)`);
        
        saveToGoogleSheets(summary, email, i + 1);
        console.log(`${mailInfo} - Google Sheetsへの保存が完了しました。`);
        
        const endTime = new Date();
        const totalDuration = Math.round((endTime - startTime) / 1000);
        console.log(`${mailInfo} - 処理完了 (総処理時間: ${totalDuration}秒)`);
        
        processedCount++;
        
        if (i < emails.length - 1) {
          console.log(`APIの連続呼び出しを避けるため5秒間待機します...`);
          Utilities.sleep(5000);
        }
        
      } catch (error) {
        console.error(`${mailInfo} - 処理中にエラーが発生しました:`, error.message);
        continue;
      }
    }
    
    console.log(`処理完了: ${processedCount}/${emails.length}件のメールを処理しました。`);
    console.log('=== Gmail Inventory Processor 正常終了 ===');
  } catch (error) {
    console.error('スクリプト全体で致命的なエラーが発生しました:', error);
    sendErrorNotification(error);
  }
}

// ===============================================================
// ヘルパー関数
// ===============================================================

/**
 * 複数回に分けてPDFを解析し、すべての在庫データを取得します。
 * @param {GoogleAppsScript.Base.Blob} pdfBlob - 解析するPDFファイル。
 * @param {number} emailIndex - 処理中のメール番号。
 * @return {string} すべての在庫データを統合したテキスト。
 */
function generateSummaryWithGeminiMultiplePasses(pdfBlob, emailIndex = 1) {
  try {
    console.log(`複数回処理開始 - ファイル名: ${pdfBlob.getName()}, サイズ: ${pdfBlob.getBytes().length} bytes`);
    
    const allResults = [];
    const maxPasses = 3; // 3回処理で効率化
    
    for (let pass = 1; pass <= maxPasses; pass++) {
      console.log(`=== 処理パス ${pass}/${maxPasses} 開始 ===`);
      
      let pageInstruction = '';
      if (pass === 1) {
        pageInstruction = 'PDFの1-3ページ目を詳細に解析してください。';
      } else if (pass === 2) {
        pageInstruction = 'PDFの4-6ページ目を詳細に解析してください。';
      } else {
        pageInstruction = 'PDFの7ページ目以降のすべてのページを詳細に解析してください。';
      }
      
      const prompt = `
添付された在庫PDFファイルを解析し、製品アイテムをマークダウン形式のテーブルとして抽出してください。

# 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- 表形式のデータのみを抽出し、それ以外のテキストは含めないこと。
- 最終的な出力はマークダウンのテーブルのみとし、前後の説明文は一切不要です。
- 指定されたページ範囲のすべての在庫アイテムを漏れなく抽出してください。
- 商品コードが不完全でも、数値データがあれば抽出してください。

${pageInstruction}

以下の商品コードパターンを含むすべてのアイテムを抽出してください：
- TNIA, TNIC, TNIL, TNIW, TNMA, TNMC で始まるコード
- UU で始まるコード  
- V で始まるコード
- その他すべての商品コード

各ページを隅から隅まで確認し、見落としがないようにしてください。
`;

      const result = generateSummaryWithGeminiSinglePass(pdfBlob, prompt, pass);
      
      if (result && result.trim().length > 0) {
        allResults.push(result);
        console.log(`パス ${pass} 完了: ${result.split('\n').filter(line => line.includes('|')).length}行`);
      } else {
        console.log(`パス ${pass} でデータなし`);
      }
      
      // パス間で少し待機
      if (pass < maxPasses) {
        console.log('次のパスまで5秒待機...');
        Utilities.sleep(5000);
      }
    }
    
    // 結果を統合
    const combinedResult = allResults.join('\n');
    console.log(`統合前の総行数: ${combinedResult.split('\n').filter(line => line.includes('|')).length}行`);
    
    // より包括的な商品コードパターンチェック
    const codePatterns = [
      'TNIA', 'TNIC', 'TNIL', 'TNIW', 'TNMA', 'TNMC',
      'UU', 'V', 'AC-', 'BD-', 'FC-', 'SW-', 'GSY', 'GHC', 'GHW', 'GSC', 'GSW'
    ];
    
    // GSYパターンの詳細チェック
    const gsyPatterns = ['GSY001', 'GSY002', 'GSY003', 'GSY004', 'GSY008', 'GSY010', 'GSY011', 'GSY014', 'GSY015', 'GSY026', 'GSY031'];
    const foundGsyCodes = [];
    for (const code of gsyPatterns) {
      if (combinedResult.includes(code)) {
        foundGsyCodes.push(code);
      }
    }
    console.log(`GSY詳細チェック: ${foundGsyCodes.length}/${gsyPatterns.length}件発見`);
    if (foundGsyCodes.length > 0) {
      console.log(`発見されたGSYコード: ${foundGsyCodes.join(', ')}`);
    }
    
    const foundPatterns = [];
    const totalLines = combinedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
    
    for (const pattern of codePatterns) {
      const matchingLines = totalLines.filter(line => line.includes(pattern));
      if (matchingLines.length > 0) {
        foundPatterns.push(`${pattern}: ${matchingLines.length}件`);
      }
    }
    
    console.log(`商品コードパターン別抽出結果:`);
    foundPatterns.forEach(pattern => console.log(`  ${pattern}`));
    console.log(`総抽出行数: ${totalLines.length}行`);
    
    // 特定の商品コードが含まれているかチェック
    const specificCodes = [
      'TNIA243210800MK', 'TNIC242510200MK', 'TNIC242510400MK', 
      'TNIL202510800MK', 'TNIL202511000MK', 'TNIW202011000NI',
      'TNMA2432M2400MK', 'TNMA2432M3000MK', 'UU0381512.506MM3050',
      'UU0703220MM2440', 'V0503208MM3000R', 'V0505008MM3150S'
    ];
    
    const foundCodes = [];
    const missingCodesFound = [];
    
    for (const code of specificCodes) {
      if (combinedResult.includes(code)) {
        foundCodes.push(code);
      } else {
        missingCodesFound.push(code);
      }
    }
    
    console.log(`特定商品コード検出: ${foundCodes.length}/${specificCodes.length}件`);
    if (foundCodes.length > 0) {
      console.log(`発見されたコード: ${foundCodes.join(', ')}`);
    }
    if (missingCodesFound.length > 0) {
      console.log(`見つからないコード: ${missingCodesFound.join(', ')}`);
    }
    
    // GSYパターンが0件の場合、追加処理を実行
    const gsyCount = combinedResult.split('\n').filter(line => line.includes('GSY')).length;
    if (gsyCount === 0) {
      console.log('GSYパターンが検出されませんでした。追加処理を実行します...');
      
      const additionalPrompt = `
添付された在庫PDFファイルを解析し、GSYで始まる製品アイテムをマークダウン形式のテーブルとして抽出してください。

# 重要指示
- テーブルのヘッダーは「Product Code, Description, On Hand, Quantity SC w/o DN, Available」とすること。
- GSYで始まるすべての商品コードを探してください（GSY001, GSY002, GSY003, ..., GSY031など）。
- 特に以下の商品コードを必ず見つけてください：GSY026, GSY031
- 表形式のデータのみを抽出し、それ以外のテキストは含めないこと。
- 最終的な出力はマークダウンのテーブルのみとし、前後の説明文は一切不要です。

PDFの最後のページや、Ceiling System関連のセクションを重点的に確認してください。
`;
      
      try {
        const additionalResult = generateSummaryWithGeminiSinglePass(pdfBlob, additionalPrompt, 99);
        if (additionalResult && additionalResult.trim().length > 0) {
          console.log(`追加処理でGSYデータを発見: ${additionalResult.split('\n').filter(line => line.includes('|')).length}行`);
          allResults.push(additionalResult);
          
          // 結果を再統合
          const updatedCombinedResult = allResults.join('\n');
          console.log(`更新後の総行数: ${updatedCombinedResult.split('\n').filter(line => line.includes('|')).length}行`);
          
          // 重複除去を実行
          const deduplicatedResult = removeDuplicateInventoryItems(updatedCombinedResult);
          const finalLines = deduplicatedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
          console.log(`重複除去後の総行数: ${finalLines.length}行`);
          
          return deduplicatedResult;
        }
      } catch (error) {
        console.error('追加処理エラー:', error);
      }
    }
    
    // 重複除去を実行
    const deduplicatedResult = removeDuplicateInventoryItems(combinedResult);
    const finalLines = deduplicatedResult.split('\n').filter(line => line.includes('|') && !line.includes('---'));
    console.log(`重複除去後の総行数: ${finalLines.length}行`);
    
    return deduplicatedResult;
    
  } catch (error) {
    console.error('複数回処理エラー:', error);
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
 * 香港時間で今日のメールを検索します。
 */
function searchInventoryEmails() {
  try {
    // 現在の香港時間を取得
    const now = new Date();
    const hongKongTime = new Date(now.getTime() + (8 * 60 * 60 * 1000)); // UTC+8
    console.log(`香港時間の今日: ${hongKongTime.getFullYear()}/${hongKongTime.getMonth() + 1}/${hongKongTime.getDate()} ${hongKongTime.getHours()}:${hongKongTime.getMinutes()}:${hongKongTime.getSeconds()}`);
    
    // より簡単な日付計算（香港時間の今日の0時と23時59分をUTCに変換）
    const hkYear = hongKongTime.getUTCFullYear();
    const hkMonth = hongKongTime.getUTCMonth();
    const hkDate = hongKongTime.getUTCDate();
    
    const todayStart = new Date(Date.UTC(hkYear, hkMonth, hkDate, 0, 0, 0) - (8 * 60 * 60 * 1000));
    const todayEnd = new Date(Date.UTC(hkYear, hkMonth, hkDate, 23, 59, 59) - (8 * 60 * 60 * 1000));
    
    console.log(`検索範囲（UTC）: ${todayStart.toISOString()} ～ ${todayEnd.toISOString()}`);
    console.log(`検索範囲（香港時間）: ${new Date(todayStart.getTime() + (8 * 60 * 60 * 1000)).toLocaleString('ja-JP')} ～ ${new Date(todayEnd.getTime() + (8 * 60 * 60 * 1000)).toLocaleString('ja-JP')}`);

    // より柔軟な検索クエリ
    const searchQueries = [
      `${CONFIG.SEARCH_QUERY} after:${formatDateForGmail(todayStart)} before:${formatDateForGmail(todayEnd)}`,
      `subject:inventory has:attachment after:${formatDateForGmail(todayStart)} before:${formatDateForGmail(todayEnd)}`,
      `from:bestinksalesman@gmail.com subject:inventory has:attachment after:${formatDateForGmail(todayStart)} before:${formatDateForGmail(todayEnd)}`
    ];
    
    let allEmails = [];
    
    for (const query of searchQueries) {
      console.log(`検索クエリ: ${query}`);
      try {
        const threads = GmailApp.search(query, 0, 50);
        const messages = threads.flatMap(thread => thread.getMessages());
        allEmails = allEmails.concat(messages);
        console.log(`クエリ「${query}」で${messages.length}件のメールを発見`);
      } catch (queryError) {
        console.log(`クエリ「${query}」でエラー: ${queryError.message}`);
      }
    }

    // 重複を除去し、日付でフィルタリング
    const uniqueEmails = [];
    const seenIds = new Set();
    
    for (const message of allEmails) {
      const msgId = message.getId();
      if (!seenIds.has(msgId)) {
        seenIds.add(msgId);
        const msgDate = message.getDate();
        const msgDateHK = new Date(msgDate.getTime() + (8 * 60 * 60 * 1000));
        
        console.log(`メール確認: ${message.getSubject()}`);
        console.log(`  UTC時間: ${msgDate.toISOString()}`);
        console.log(`  香港時間: ${msgDateHK.toLocaleString('ja-JP')}`);
        console.log(`  添付ファイル数: ${message.getAttachments().length}件`);
        console.log(`  日付範囲チェック: ${msgDate >= todayStart && msgDate <= todayEnd}`);
        
        // より柔軟な日付チェック（1日前から今日まで）
        const yesterdayStart = new Date(todayStart.getTime() - (24 * 60 * 60 * 1000));
        const tomorrowEnd = new Date(todayEnd.getTime() + (24 * 60 * 60 * 1000));
        
        if (msgDate >= yesterdayStart && msgDate <= tomorrowEnd && message.getAttachments().length > 0) {
          uniqueEmails.push(message);
          console.log(`✅ 該当メール発見: ${message.getSubject()} (UTC: ${msgDate.toISOString()}, 香港時間: ${msgDateHK.toLocaleString('ja-JP')})`);
        } else {
          console.log(`❌ 除外: ${message.getSubject()} - 日付範囲外または添付ファイルなし`);
        }
      }
    }

    // 新しい順にソート
    uniqueEmails.sort((a, b) => b.getDate().getTime() - a.getDate().getTime());
    
    console.log(`今日の該当メール数: ${uniqueEmails.length}件`);
    return uniqueEmails;
  } catch (error) {
    console.error('Gmail検索エラー:', error);
    throw error;
  }
}

/**
 * Gmail検索クエリ用に日付を "YYYY/MM/DD" 形式にフォーマットします。
 */
function formatDateForGmail(date) {
  return date.toISOString().slice(0, 10).replace(/-/g, '/');
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
 * 定期実行トリガーを設定します (毎日午前と午後の2回)。
 */
function setupTriggers() {
  // 既存のトリガーを全て削除
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'processInventoryEmails') {
      ScriptApp.deleteTrigger(trigger);
    }
  }

  // 新しいトリガーを設定
  ScriptApp.newTrigger('processInventoryEmails')
    .timeBased()
    .everyDays(1)
    .atHour(9) // 午前9時
    .create();

  ScriptApp.newTrigger('processInventoryEmails')
    .timeBased()
    .everyDays(1)
    .atHour(15) // 午後3時
    .create();
    
  console.log('定期実行トリガーを毎日午前9時と午後3時に設定しました。');
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
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const stockSheet = ss.getSheetByName('Stock');
    
    if (!stockSheet) {
      console.error('Stockシートが見つかりません');
      return;
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