/** Cheerio なし（ライブラリ未追加のプロジェクトでも動く） */
function aluStripHtml_(html) {
  if (!html) return "";
  return String(html)
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function aluExtractAnchors_(html) {
  const out = [];
  const re = /<a\s+[^>]*href\s*=\s*["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let m;
  while ((m = re.exec(html)) !== null) {
    out.push({ href: m[1], text: aluStripHtml_(m[2]) });
  }
  return out;
}

function aluExtractTdCells_(trHtml) {
  const cells = [];
  const tdRe = /<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi;
  let m;
  while ((m = tdRe.exec(trHtml)) !== null) {
    cells.push(aluStripHtml_(m[1]));
  }
  return cells;
}

/**
 * 正規定義（唯一の真解）。docs/ALUMINUM_GAS_PIPELINE_LOCK.md と同内容に保つ。タブ名・ID の手当は必ず同 PR で。
 */
var ALU_CANON_ = {
  SPREADSHEET_ID: "1RQb5fBTipFZPslbG60vP46DJZ8ZD9D7a7_eaKw718nM",
  SHEET_GALVANIZED_STEEL: "镀锌板卷价格-2",
  SHEET_ALU_DAILY: "当天铝锭价格",
  SHEET_COMPARISON: "供应商资料及最新铝价与旧价对比",
  CHART_VIEW_SHEET: "価格推移グラフ",
  CHART_DATA_SHEET: "グラフデータ",
  MYSTEEL_EXCEL_SHEET: "日价格"
};

/** 直接上書き禁止 — ALU_CANON_ と同期 */
var ALU_SPREADSHEET_ID = ALU_CANON_.SPREADSHEET_ID;
var ALU_GALVANIZED_STEEL_SHEET_NAME = ALU_CANON_.SHEET_GALVANIZED_STEEL;

/**
 * 必須タブ・ID 不整合の早期検出。意図変更はドキュメント＋ALU_CANON_ 一括更新。
 */
function assertAluPipelineInvariants_() {
  if (ALU_SPREADSHEET_ID !== ALU_CANON_.SPREADSHEET_ID) {
    throw new Error("ALU_SPREADSHEET_ID が ALU_CANON_ と不整合。docs/ALUMINUM_GAS_PIPELINE_LOCK.md 参照。");
  }
  if (ALU_GALVANIZED_STEEL_SHEET_NAME !== ALU_CANON_.SHEET_GALVANIZED_STEEL) {
    throw new Error("ALU_GALVANIZED_STEEL_SHEET_NAME が ALU_CANON_ と不整合。docs/ALUMINUM_GAS_PIPELINE_LOCK.md 参照。");
  }
  const ss = SpreadsheetApp.openById(ALU_CANON_.SPREADSHEET_ID);
  if (!ss.getSheetByName(ALU_CANON_.SHEET_GALVANIZED_STEEL) || !ss.getSheetByName(ALU_CANON_.SHEET_ALU_DAILY)) {
    throw new Error(
      "必須タブ（" + ALU_CANON_.SHEET_GALVANIZED_STEEL + " / " + ALU_CANON_.SHEET_ALU_DAILY + "）のいずれかなし。docs/ALUMINUM_GAS_PIPELINE_LOCK.md 参照。"
    );
  }
  if (!ss.getSheetByName(ALU_CANON_.SHEET_COMPARISON)) {
    console.warn("ALU: 推奨タブ「" + ALU_CANON_.SHEET_COMPARISON + "」なし。I10/I21 等はスキップされる場合あり。");
  }
}

function getMonitoredSpreadsheet_() {
  const active = SpreadsheetApp.getActiveSpreadsheet();
  if (active && active.getId() === ALU_SPREADSHEET_ID) return active;
  return SpreadsheetApp.openById(ALU_SPREADSHEET_ID);
}

function updateAluminumPriceSheet() {
  try {
    // 直近の営業日を取得（土曜日と日曜日を除く）
    const today = new Date();
    let mostRecentBusinessDay = new Date(today);

    const dayOfWeek = today.getDay();
    if (dayOfWeek === 0) { // 日曜日
      mostRecentBusinessDay.setDate(today.getDate() - 2); // 金曜日に戻す
    } else if (dayOfWeek === 6) { // 土曜日
      mostRecentBusinessDay.setDate(today.getDate() - 1); // 金曜日に戻す
    }

    function findLatestArticle(baseUrl, marketType) {
      try {
        const response = UrlFetchApp.fetch(baseUrl);
        const html = response.getContentText();
        Logger.log(`${baseUrl} からHTMLを取得しました`);
        const anchors = aluExtractAnchors_(html);
        const foundLinks = [];
        for (let i = 0; i < anchors.length; i++) {
          const linkText = anchors[i].text;
          const href = anchors[i].href;
          if (!href || !linkText) continue;
          const isDateRangeArticle = linkText.includes("～") || linkText.includes("-") || linkText.includes("至");
          if (isDateRangeArticle) continue;
          if (
            (marketType === "changjiang" && linkText.includes("长江") && linkText.includes("铝板价格")) ||
            (marketType === "nanhai" && linkText.includes("南海") && linkText.includes("铝锭价格"))
          ) {
            const fullUrl = href.startsWith("/")
              ? `https://market.cnal.com${href}`
              : href.startsWith("http")
                ? href
                : `${baseUrl}/${href}`;
            const dateMatch = fullUrl.match(/\/(\d{4})\/(\d{2})-(\d{2})\//);
            if (dateMatch) {
              const urlYear = parseInt(dateMatch[1], 10);
              const urlMonth = parseInt(dateMatch[2], 10);
              const urlDay = parseInt(dateMatch[3], 10);
              const urlDate = new Date(urlYear, urlMonth - 1, urlDay);
              foundLinks.push({
                text: linkText,
                url: fullUrl,
                date: urlDate,
                chineseDate: `${urlMonth}月${urlDay}日`,
              });
              Logger.log(`単日記事リンク: ${linkText} (${fullUrl})`);
            }
          }
        }
        if (foundLinks.length === 0) {
          Logger.log(`市場 ${marketType} に単日記事リンクが見つかりませんでした`);
          return null;
        }
        foundLinks.sort((a, b) => b.date - a.date);
        return { url: foundLinks[0].url, title: foundLinks[0].text };
      } catch (error) {
        Logger.log(`記事検索エラー: ${error.toString()}`);
        return null;
      }
    }

    function extractPriceData(url, marketType) {
      try {
        const response = UrlFetchApp.fetch(url);
        const html = response.getContentText();
        Logger.log(`HTMLコンテンツが正常に取得されました： ${url}`);
        const plain = aluStripHtml_(html);

        let title = "";
        const h1m =
          html.match(/<h1[^>]*class\s*=\s*["'][^"']*tit[^"']*["'][^>]*>([\s\S]*?)<\/h1>/i) ||
          html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
        if (h1m) title = aluStripHtml_(h1m[1]);
        Logger.log(`抽出されたタイトル: ${title}`);

        let dateTime = "";
        const tim =
          html.match(/<li[^>]*class\s*=\s*["'][^"']*time[^"']*["'][^>]*>([\s\S]*?)<\/li>/i) ||
          html.match(/class\s*=\s*["'][^"']*time[^"']*["'][^>]*>([\s\S]*?)<\/li>/i);
        if (tim) dateTime = aluStripHtml_(tim[1]);
        Logger.log(`抽出された日時: ${dateTime}`);

        let extractedDate = "";
        const dateMatch = title.match(/(\d+)月(\d+)日/);
        if (dateMatch) {
          const year = new Date().getFullYear();
          extractedDate = `${year}/${parseInt(dateMatch[1], 10)}/${parseInt(dateMatch[2], 10)}`;
          Logger.log(`タイトルから抽出された日付: ${extractedDate}`);
        }

        if (marketType === "changjiang") {
          let changjiangPrice = "";
          const trRe = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
          let trM;
          while ((trM = trRe.exec(html)) !== null) {
            const trInner = trM[1];
            const rowText = aluStripHtml_(trInner);
            if (!rowText.includes("铝") || !/\d{5}/.test(rowText)) continue;
            const cells = aluExtractTdCells_(trInner);
            if (cells.length >= 3 && /^\d{5,6}$/.test(cells[2])) {
              changjiangPrice = cells[2];
              Logger.log(`アルミニウム行のセルから直接日均价を取得しました: ${changjiangPrice}`);
              break;
            }
          }
          if (!changjiangPrice) {
            trRe.lastIndex = 0;
            while ((trM = trRe.exec(html)) !== null) {
              const rowText = aluStripHtml_(trM[1]);
              if (rowText.includes("铝") && /20\d{3}/.test(rowText)) {
                const cells = aluExtractTdCells_(trM[1]);
                for (let c = 0; c < cells.length; c++) {
                  if (/^20\d{3}$/.test(cells[c]) && cells[c].indexOf("-") === -1) {
                    changjiangPrice = cells[c];
                    Logger.log(`セルから日均价を直接取得しました: ${changjiangPrice}`);
                    break;
                  }
                }
                if (changjiangPrice) break;
              }
            }
          }
          if (!changjiangPrice) {
            const tdRe = /<td[^>]*>([\s\S]*?)<\/td>/gi;
            let tdM;
            while ((tdM = tdRe.exec(html)) !== null) {
              const cellText = aluStripHtml_(tdM[1]);
              if (/^20\d{3}$/.test(cellText) && cellText.indexOf("-") === -1) {
                const before = html.substring(0, tdM.index);
                const lastTr = before.lastIndexOf("<tr");
                const trSnippet = lastTr >= 0 ? html.substring(lastTr, tdM.index + 500) : "";
                if (aluStripHtml_(trSnippet).indexOf("铝") >= 0) {
                  changjiangPrice = cellText;
                  Logger.log(`テーブルセルから直接値を見つけました: ${changjiangPrice}`);
                  break;
                }
              }
            }
          }
          if (!changjiangPrice) {
            const articleText = plain;
            const tablePatternInText = articleText.match(/金属类别.*?价格区间.*?日均价.*?铝.*?(\d{5,6})-(\d{5,6}).*?(\d{5,6})/s);
            if (tablePatternInText && tablePatternInText[3]) {
              changjiangPrice = tablePatternInText[3];
            } else {
              const aluminumPattern = articleText.match(/铝.*?(\d{5,6})-(\d{5,6}).*?(\d{5,6})/);
              if (aluminumPattern && aluminumPattern[3]) changjiangPrice = aluminumPattern[3];
              else {
                const riJunJiaMatch = articleText.match(/日均价[:：]?\s*(\d{5,6})/);
                if (riJunJiaMatch) changjiangPrice = riJunJiaMatch[1];
                else {
                  const rangeAverageMatch = articleText.match(/价格区间[^]*?(\d{5,6})-(\d{5,6})[^]*?日均价[^]*?(\d{5,6})/);
                  if (rangeAverageMatch && rangeAverageMatch[3]) changjiangPrice = rangeAverageMatch[3];
                  else {
                    const specificPattern = articleText.match(/长江.*?铝.*?价格.*?(\d{5,6})/);
                    if (specificPattern) changjiangPrice = specificPattern[1];
                    else {
                      const priceMatchesDetailed = articleText.match(/\b2\d{4}\b/g);
                      if (priceMatchesDetailed && priceMatchesDetailed.length > 1) {
                        changjiangPrice = priceMatchesDetailed[2] || priceMatchesDetailed[0];
                      } else {
                        const priceMatches = articleText.match(/\b\d{5,6}\b/g);
                        changjiangPrice = priceMatches ? priceMatches[0] : "";
                      }
                    }
                  }
                }
              }
            }
          }
          return { title: title, dateTime: dateTime, extractedDate: extractedDate, price: changjiangPrice };
        }
        if (marketType === "nanhai") {
          let nanhaiPrice = "";
          const trRe2 = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
          let trM2;
          while ((trM2 = trRe2.exec(html)) !== null) {
            const rowText = aluStripHtml_(trM2[1]);
            if (
              (rowText.includes("佛山") || rowText.includes("南海")) &&
              (rowText.includes("A00") || rowText.includes("铝锭") || rowText.includes("铝"))
            ) {
              const rangeMatch = rowText.match(/(\d{5})-(\d{5})(?:.*?)(\d{5})/);
              if (rangeMatch && rangeMatch[3]) {
                nanhaiPrice = rangeMatch[3];
                Logger.log(`南海価格値を正確に見つけました: ${nanhaiPrice}`);
                break;
              }
              const a00Match = rowText.match(/A00.*?(\d{5,6})/i);
              if (a00Match) {
                nanhaiPrice = a00Match[1];
                break;
              }
              const priceMatches = rowText.match(/\b\d{5,6}\b/g);
              if (priceMatches && priceMatches.length > 0) {
                nanhaiPrice = priceMatches[priceMatches.length - 1];
                break;
              }
            }
          }
          if (!nanhaiPrice) {
            const specificPattern = plain.match(/(?:南海|佛山).*?(?:A00|铝锭).*?(\d{5,6})/);
            if (specificPattern) nanhaiPrice = specificPattern[1];
            else {
              const priceMatches = plain.match(/\b\d{5,6}\b/g);
              if (priceMatches && priceMatches.length > 1) nanhaiPrice = priceMatches[priceMatches.length - 1];
            }
          }
          return { title: title, dateTime: dateTime, extractedDate: extractedDate, price: nanhaiPrice };
        }
        return null;
      } catch (error) {
        Logger.log(`データ抽出エラー: ${error.toString()}`);
        return { title: "", dateTime: "", extractedDate: "", price: "" };
      }
    }

    const changjiangBaseUrl = "https://market.cnal.com/changjiang";
    const nanhaiBaseUrl = "https://market.cnal.com/nanhai";

    const changjiangData = findLatestArticle(changjiangBaseUrl, "changjiang");
    const nanhaiData = findLatestArticle(nanhaiBaseUrl, "nanhai");

    if (!changjiangData || !nanhaiData) throw new Error("最新価格記事が見つかりませんでした");

    const changjiangPriceData = extractPriceData(changjiangData.url, "changjiang");
    const nanhaiPriceData = extractPriceData(nanhaiData.url, "nanhai");

    const spreadsheet = getMonitoredSpreadsheet_();
    const sheet = spreadsheet.getSheetByName(ALU_CANON_.SHEET_ALU_DAILY);
    if (!sheet) throw new Error("シート '" + ALU_CANON_.SHEET_ALU_DAILY + "' が見つかりません");

    sheet.insertRowAfter(2);
    let dateStr = changjiangPriceData.extractedDate || nanhaiPriceData.extractedDate || 
                  (mostRecentBusinessDay.getFullYear() + "/" + (mostRecentBusinessDay.getMonth() + 1) + "/" + mostRecentBusinessDay.getDate());

    sheet.getRange("A3").setValue(dateStr);
    sheet.getRange("B3").setValue(changjiangPriceData.price);
    sheet.getRange("J3").setValue(nanhaiPriceData.price);
    sheet.getRange("C4:H4").copyTo(sheet.getRange("C3:H3"), {contentsOnly: false});
    sheet.getRange("K4:P4").copyTo(sheet.getRange("K3:P3"), {contentsOnly: false});

    const comparisonSheet = spreadsheet.getSheetByName(ALU_CANON_.SHEET_COMPARISON);
    if (comparisonSheet) {
      const ad = ALU_CANON_.SHEET_ALU_DAILY;
      comparisonSheet.getRange("J3").setFormula("='" + ad + "'!A3");
      comparisonSheet.getRange("K3").setFormula("='" + ad + "'!B3");
      comparisonSheet.getRange("M3").setFormula("='" + ad + "'!J3");
      comparisonSheet.getRange("J4").setFormula("='" + ad + "'!A4");
      comparisonSheet.getRange("K4").setFormula("='" + ad + "'!B4");
      comparisonSheet.getRange("M4").setFormula("='" + ad + "'!J4");

      // 数式をsetFormulaで直接設定
      comparisonSheet
        .getRange("J8")
        .setFormula("=XLOOKUP(DATE(YEAR(J3),MONTH(J3)-3,DAY(J3)),'" + ad + "'!A:A,'" + ad + "'!A:A,\"\",0,1)");
      comparisonSheet
        .getRange("J9")
        .setFormula(
          "=INDEX('" +
            ad +
            "'!A:A,MATCH(MINIFS('" +
            ad +
            "'!A:A,'" +
            ad +
            "'!A:A,\">=\"&DATE(2025,1,1)),'" +
            ad +
            "'!A:A,0))"
        );
      comparisonSheet
        .getRange("K8")
        .setFormula("=XLOOKUP(DATE(YEAR(J3),MONTH(J3)-3,DAY(J3)),'" + ad + "'!A:A,'" + ad + "'!B:B,\"\",0,1)");
      comparisonSheet
        .getRange("K9")
        .setFormula(
          "=INDEX('" +
            ad +
            "'!B:B,MATCH(MINIFS('" +
            ad +
            "'!A:A,'" +
            ad +
            "'!A:A,\">=\"&DATE(2025,1,1)),'" +
            ad +
            "'!A:A,0))"
        );
      comparisonSheet.getRange("L8").setFormula("=(K3-K8)/K8");
      comparisonSheet.getRange("L9").setFormula("=(K3-K9)/K9");
      comparisonSheet.getRange("M8").setFormula("=VLOOKUP(J8,'" + ad + "'!A:J,10,FALSE)");
      comparisonSheet.getRange("M9").setFormula("=VLOOKUP(J9,'" + ad + "'!A:J,10,FALSE)");
      comparisonSheet.getRange("N8").setFormula("=(M3-M8)/M8");
      comparisonSheet.getRange("N9").setFormula("=(M3-M9)/M9");

      const now = new Date();
      const updateInfo = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${now.getHours()}:${now.getMinutes() < 10 ? '0' + now.getMinutes() : now.getMinutes()} 已更新\n${nanhaiData.title} (${nanhaiData.url}),\n${changjiangData.title} (${changjiangData.url})`;
      comparisonSheet.getRange("I10").setValue(updateInfo).setHorizontalAlignment("left");
    }

    SpreadsheetApp.flush();
    Utilities.sleep(5000); // 計算完了を待機
    // 通知メールは送らない（一括は executeAllProcesses 末尾の [铝价分析表] のみ）
    Logger.log("アルミ価格反映完了（メール通知なし。一括完了メールに集約）。");

    return "すべての更新が完了しました";
  } catch (e) {
    Logger.log("エラー: " + e.toString());
    throw e;
  }
}

/**
 * Mysteel 日次メール用の Gmail 検索クエリ候補（上から順に試す）
 */
function aluGmailMysteelSearchQueries_() {
  return [
    '(subject:"Today Mysteeldata" OR subject:TodayMysteeldata) newer_than:7d',
    'subject:TodayMysteeldata newer_than:7d',
    'subject:"TodayMysteeldata" newer_than:7d',
    'subject:Mysteeldata has:attachment newer_than:7d',
  ];
}

function aluGmailSearchMysteelThreads_(maxThreads) {
  const queries = aluGmailMysteelSearchQueries_();
  for (let qi = 0; qi < queries.length; qi++) {
    const q = queries[qi];
    const threads = GmailApp.search(q, 0, maxThreads);
    console.log('Gmail search [' + (qi + 1) + '/' + queries.length + '] スレッド数: ' + threads.length + ' | ' + q);
    if (threads.length > 0) {
      return { threads: threads, query: q };
    }
  }
  return { threads: [], query: null };
}

/**
 * 件名に Mysteel 系が含まれるメッセージを優先し、その中で最も新しい1通を選ぶ
 *（複数スレッド混在で「通知メールの方が新しい」等の取り違えを減らす）
 */
function aluPickLatestMysteelMessage_(threads) {
  const pool = [];
  for (let ti = 0; ti < threads.length; ti++) {
    const msgs = threads[ti].getMessages();
    for (let mi = 0; mi < msgs.length; mi++) {
      pool.push(msgs[mi]);
    }
  }
  if (pool.length === 0) {
    return null;
  }
  const subjHasMysteel = function (subj) {
    const s = (subj || '').toLowerCase();
    return s.indexOf('mysteeldata') >= 0 || s.indexOf('mysteel') >= 0;
  };
  const preferred = pool.filter(function (m) {
    return subjHasMysteel(m.getSubject());
  });
  const use = preferred.length > 0 ? preferred : pool;
  let best = use[0];
  for (let j = 1; j < use.length; j++) {
    if (use[j].getDate().getTime() > best.getDate().getTime()) {
      best = use[j];
    }
  }
  return best;
}

function aluIsExcelLikeAttachment_(name) {
  if (!name) {
    return false;
  }
  const lower = name.toLowerCase();
  if (/\.(xls|xlsx|xlsm|xlsb)$/.test(lower)) {
    return true;
  }
  if (lower.indexOf('mysteel') >= 0) {
    return true;
  }
  if (name.indexOf('价格') >= 0) {
    return true;
  }
  return false;
}

/**
 * Gmailの添付ファイル（Excel）を処理し、指定のスプレッドシートにデータを転記する関数
 */
function processGmailAttachment() {
  const targetSpreadsheetId = ALU_SPREADSHEET_ID;
  const targetSheetName = ALU_GALVANIZED_STEEL_SHEET_NAME;
  const excelSheetName = ALU_CANON_.MYSTEEL_EXCEL_SHEET;

  try {
    console.log("processGmailAttachment の実行を開始します");

    // 件名表記揺れ・Gmail 検索の解釈差に備え、フォールバック付きで検索
    const maxThreads = 30;
    const found = aluGmailSearchMysteelThreads_(maxThreads);
    const threads = found.threads;
    if (threads.length === 0) {
      console.log("対象のメールが見つかりませんでした。処理を終了します。");
      return { imported: false, reason: "no_mail" };
    }

    const latestMessage = aluPickLatestMysteelMessage_(threads);
    if (!latestMessage) {
      return { imported: false, reason: "no_mail" };
    }
    console.log(`処理するメール - 件名: ${latestMessage.getSubject()}`);
    console.log(`処理するメール - 日時: ${latestMessage.getDate()}`);

    // 添付ファイルを確認
    const attachments = latestMessage.getAttachments();
    console.log(`添付ファイル数: ${attachments.length}`);

    let excelAttachment = null;
    for (let i = 0; i < attachments.length; i++) {
      const attachment = attachments[i];
      const attachmentName = attachment.getName();
      console.log(`添付ファイル ${i + 1}: ${attachmentName}`);

      if (aluIsExcelLikeAttachment_(attachmentName)) {
        excelAttachment = attachment;
        console.log(`処理対象のExcelファイルを見つけました: ${attachmentName}`);
        break;
      }
    }

    if (!excelAttachment) {
      console.log("処理対象のExcelファイルが見つかりませんでした。");
      return { imported: false, reason: "no_excel" };
    }

    // --- Google Sheets API を使用してExcelデータを読み取る ---
    // 1. 一時的にGoogle Driveにファイルを保存
    const tempFolder = DriveApp.getRootFolder(); // ルートフォルダを使用（必要に応じて変更）
    const tempFile = tempFolder.createFile(excelAttachment);
    const tempFileId = tempFile.getId();
    Logger.log(`Excelファイルを一時的にDriveに保存しました: ${tempFile.getName()} (ID: ${tempFileId})`);

    // 2. DriveファイルをGoogle Sheets形式に変換 (Sheets APIを使用)
    // この操作には Drive API v2 が必要です。GASエディタの「サービス」で「Drive API」を追加し、バージョンをv2にしてください。
    const convertedSheet = Drive.Files.copy({ mimeType: MimeType.GOOGLE_SHEETS }, tempFileId);
    const convertedSheetId = convertedSheet.id;
    Logger.log(`ファイルをGoogle Sheets形式に変換しました (ID: ${convertedSheetId})`);

    // 3. 変換されたスプレッドシートを開く
    let sourceSpreadsheet;
    let sourceSheet;
    try {
      sourceSpreadsheet = SpreadsheetApp.openById(convertedSheetId);
      sourceSheet = sourceSpreadsheet.getSheetByName(excelSheetName);

      if (!sourceSheet) {
        // 指定されたシート名が見つからない場合、最初のシートを使用するフォールバック
        Logger.log(`Excel内にシート名「${excelSheetName}」が見つかりません。最初のシートを使用します。`);
        const allSheets = sourceSpreadsheet.getSheets();
        if (allSheets.length > 0) {
          sourceSheet = allSheets[0];
          Logger.log(`フォールバックとしてシート「${sourceSheet.getName()}」を使用します。`);
        } else {
          throw new Error("変換されたスプレッドシートにシートが見つかりません。");
        }
      } else {
         Logger.log(`読み取り元シートを取得しました: ${sourceSheet.getName()}`);
      }
    } catch (openError) {
       Logger.log(`変換されたスプレッドシートを開く際にエラーが発生しました: ${openError}`);
       // 一時ファイルを削除
       try { DriveApp.getFileById(tempFileId).setTrashed(true); } catch(e) { Logger.log(`一時ファイル削除エラー(tempFileId): ${e}`);}
       try { DriveApp.getFileById(convertedSheetId).setTrashed(true); } catch(e) { Logger.log(`一時ファイル削除エラー(convertedSheetId): ${e}`);}
       // メールを既読にする
       try { latestMessage.markRead(); Logger.log("エラー発生後、メールを既読にしました。"); } catch(e) { Logger.log(`メール既読化エラー: ${e}`);}
       throw openError; // エラーを再スロー
    }


    // 4. データを取得
    const sourceData = sourceSheet.getDataRange().getValues();
    Logger.log(`読み取り元シートから ${sourceData.length} 行、${sourceData[0] ? sourceData[0].length : 0} 列のデータを取得しました。`);

    // 5. 一時ファイルを削除
    // Drive API v2 を使用しているため、DriveAppではなくDriveサービスで削除
    try { Drive.Files.remove(tempFileId); Logger.log(`一時ファイル (ID: ${tempFileId}) を削除しました。`); } catch(e) { Logger.log(`一時ファイル削除エラー(tempFileId): ${e}`);}
    try { Drive.Files.remove(convertedSheetId); Logger.log(`変換後ファイル (ID: ${convertedSheetId}) を削除しました。`); } catch(e) { Logger.log(`一時ファイル削除エラー(convertedSheetId): ${e}`);}
    // --- 読み取り完了 ---

    // 転記先のスプレッドシートとシートを取得
    const targetSpreadsheet = SpreadsheetApp.openById(targetSpreadsheetId);
    const targetSheet = targetSpreadsheet.getSheetByName(targetSheetName);

    if (!targetSheet) {
      throw new Error(`転記先のスプレッドシートにシート名「${targetSheetName}」が見つかりません。`);
    }
    Logger.log(`転記先シートを取得しました: ${targetSheet.getName()}`);

    // 転記先シートの既存データをクリア
    targetSheet.clearContents();
    Logger.log("転記先シートの既存データをクリアしました。");

    // データを転記先に貼り付け
    if (sourceData.length > 0 && sourceData[0].length > 0) {
      targetSheet.getRange(1, 1, sourceData.length, sourceData[0].length).setValues(sourceData);
      Logger.log(`データを転記先シートに貼り付けました。`);
    } else {
      Logger.log("読み取るデータがありませんでした。");
    }

    // 処理済みのメールを既読にする
    latestMessage.markRead();
    Logger.log("メールを既読にしました。");

    SpreadsheetApp.flush(); // 変更を即時反映

    // --- 完了ログをシートに書き込む ---
    try {
      const comparisonSheet = targetSpreadsheet.getSheetByName(ALU_CANON_.SHEET_COMPARISON);
      if (comparisonSheet) {
        const now = new Date();
        const formattedDateTime = Utilities.formatDate(now, Session.getScriptTimeZone(), "yyyy年MM月dd日 HH:mm");
        const logMessage = `${formattedDateTime} 已更新\n收集信息源：我的钢铁 https://price.mysteel.com/#/price-search?breedId=1-1`;
        comparisonSheet.getRange("I21").setValue(logMessage).setVerticalAlignment("top").setWrap(true); // 縦位置を上揃えにし、折り返しを有効にする
        Logger.log("完了ログをシート「" + ALU_CANON_.SHEET_COMPARISON + "」のセルI21に書き込みました。");
      } else {
        Logger.log("シート「" + ALU_CANON_.SHEET_COMPARISON + "」が見つからなかったため、完了ログを書き込めませんでした。");
      }
    } catch (logError) {
      Logger.log(`完了ログの書き込み中にエラーが発生しました: ${logError.toString()}`);
    }
    // --- 完了ログ書き込み終了 ---

    console.log("処理が正常に完了しました");
    // Mysteel 取込完了の個別メールは送らない（一括は executeAllProcesses 末尾の [铝价分析表] のみ）

    return { imported: true };

  } catch (e) {
    console.error(`エラーが発生しました: ${e.toString()}`);
    console.error(`スタックトレース: ${e.stack}`);
    // Mysteel 段階ではメール送信しない（成否とも一括は executeAllProcesses 末尾で通知）
    throw e;
  }
}

/**
 * グラフデータを更新し、自動的にグラフを更新する関数
 */
function updatePriceChart() {
  normalizeSteelSheetDates();
  normalizeAluminumSheetDates();
  const ss = getMonitoredSpreadsheet_();
  
  // データソースシートの取得
  const aluminumSheet = ss.getSheetByName(ALU_CANON_.SHEET_ALU_DAILY);
  const steelSheet = ss.getSheetByName(ALU_GALVANIZED_STEEL_SHEET_NAME);
  if (!steelSheet) {
    throw new Error('シート「' + ALU_GALVANIZED_STEEL_SHEET_NAME + '」が見つかりません。');
  }
  if (!aluminumSheet) {
    throw new Error("シート「" + ALU_CANON_.SHEET_ALU_DAILY + "」が見つかりません。");
  }
  
  // グラフ用の新しいシートを取得または作成
  let chartSheet = ss.getSheetByName(ALU_CANON_.CHART_VIEW_SHEET);
  if (!chartSheet) {
    chartSheet = ss.insertSheet(ALU_CANON_.CHART_VIEW_SHEET);
  }

  // データ範囲を取得
  const lastRowAlu = aluminumSheet.getLastRow();
  const lastRowSteel = steelSheet.getLastRow();
  
  // アルミデータを取得（日付、長江価格B、南海価格J）
  const aluData = aluminumSheet.getRange(`A3:J${lastRowAlu}`).getValues();
  
  // 鉄鋼板データを取得（日付、5種類の価格B-F）
  const steelData = steelSheet.getRange(`A5:F${lastRowSteel}`).getValues();
  
  // 2024年から最新までのデータのみをフィルタリング
  const startDate = new Date('2024-01-01');
  const endDate = new Date();
  
  // 日付を正しく処理する関数
  function parseDate(dateValue) {
    if (dateValue instanceof Date) {
      return dateValue;
    }
    if (typeof dateValue === 'string') {
      let parts;
      if (dateValue.includes('/')) {
        parts = dateValue.split('/');
      } else if (dateValue.includes('-')) {
        parts = dateValue.split('-');
      }
      if (parts && parts.length === 3) {
        return new Date(parts[0], parts[1] - 1, parts[2]);
      }
    }
    return null;
  }

  // データを一意の日付でグループ化
  const dateMap = new Map();
  
  // アルミデータの処理（過去年で長江/南海が片方空の行はスキップするのみ。行ごとログは出さない）
  aluData.forEach((row, idx) => {
    const date = parseDate(row[0]);
    const changjiangPrice = row[1] ? parseFloat(row[1].toString().replace(/[^\d.-]/g, '')) : null;
    const nanhaiPrice = row[9] ? parseFloat(row[9].toString().replace(/[^\d.-]/g, '')) : null;
    if (!date || isNaN(date.getTime()) || changjiangPrice === null || isNaN(changjiangPrice) || nanhaiPrice === null || isNaN(nanhaiPrice)) return;
    if (date < startDate || date > endDate) return;
    const dateKey = Utilities.formatDate(date, 'Asia/Shanghai', 'yyyy/MM/dd');
    if (changjiangPrice !== null || nanhaiPrice !== null) {
      dateMap.set(dateKey, {
        date: date,
        changjiang: changjiangPrice,
        nanhai: nanhaiPrice,
        steelPrices: Array(5).fill(null)
      });
    }
  });

  // 鉄鋼板データの処理
  steelData.forEach(row => {
    if (!row[0]) return;
    
    try {
      const date = parseDate(row[0]);
      if (!date || isNaN(date.getTime())) return;
      if (date < startDate || date > endDate) return;
      
      const dateKey = Utilities.formatDate(date, 'Asia/Shanghai', 'yyyy/MM/dd');
      const prices = row.slice(1).map(price => {
        if (!price) return null;
        const parsed = parseFloat(price.toString().replace(/[^\d.-]/g, ''));
        return isNaN(parsed) ? null : parsed;
      });
      
      if (dateMap.has(dateKey)) {
        dateMap.get(dateKey).steelPrices = prices;
      } else {
        dateMap.set(dateKey, {
          date: date,
          changjiang: null,
          nanhai: null,
          steelPrices: prices
        });
      }
    } catch (e) {
      Logger.log(`鉄鋼板データ処理エラー: ${e.toString()}, Row: ${JSON.stringify(row)}`);
    }
  });

  // ソートされたユニークなデータを作成
  const uniqueData = Array.from(dateMap.values())
    .sort((a, b) => a.date - b.date)
    .map(item => [
      new Date(item.date), // 日付型で書き込む
      item.changjiang,
      item.nanhai,
      ...item.steelPrices
    ])
    .map(row => {
      return row.map((cell, index) => {
        if (index === 0) return cell;
        const num = Number(cell);
        return isNaN(num) ? null : num;
      });
    });

  // 2週間ごとにデータを抽出（間引きロジックを削除し、全データを使う）
  const filteredData = uniqueData;

  // データを非表示のシートに保存
  const hiddenSheet = ss.getSheetByName(ALU_CANON_.CHART_DATA_SHEET) || ss.insertSheet(ALU_CANON_.CHART_DATA_SHEET);
  hiddenSheet.hideSheet();
  hiddenSheet.clear();

  // ヘッダー設定
  const headers = ["日付", "長江アルミ価格", "南海アルミ価格", 
                  "鉄鋼板価格1", "鉄鋼板価格2", "鉄鋼板価格3", "鉄鋼板価格4", "鉄鋼板価格5"];
  hiddenSheet.getRange(1, 1, 1, headers.length).setValues([headers]);

  // Excel互換のため、空欄やnull値は'=NA()'に変換する関数
  function safeValue(val) {
    return (val === null || val === '' || typeof val === 'undefined') ? '=NA()' : val;
  }

  // データを書き込み
  if (filteredData.length > 0) {
    const naFilteredData = filteredData.map(row => row.map(safeValue));
    hiddenSheet.getRange(2, 1, naFilteredData.length, headers.length).setValues(naFilteredData);
    const dateRange = hiddenSheet.getRange(2, 1, naFilteredData.length, 1);
    const dateValues = dateRange.getValues();
    const newDateValues = dateValues.map(row => [parseDate(row[0])]);
    dateRange.setValues(newDateValues);
    dateRange.setNumberFormat('yyyy/mm/dd');
    hiddenSheet.getRange(2, 2, naFilteredData.length, headers.length - 1).setNumberFormat('#,##0');
  }

  // グラフシートの既存のグラフを削除
  chartSheet.clear();
  const charts = chartSheet.getCharts();
  charts.forEach(chart => chartSheet.removeChart(chart));

  // 新しいグラフをLINEチャートとして直接作成
  const dataRange = hiddenSheet.getRange(1, 1, filteredData.length + 1, headers.length);
  let chart = chartSheet.newChart()
    .setChartType(Charts.ChartType.LINE)
    .addRange(dataRange)
    .setPosition(1, 1, 0, 0)
    .setOption('useFirstColumnAsDomain', true)
    .setOption('title', '铝锭・镀锌板卷价格走势图')
    .setOption('width', 1200)
    .setOption('height', 800)
    .setOption('series', {
      0: {targetAxisIndex: 0, labelInLegend: '长江铝锭', pointSize: 7},
      1: {targetAxisIndex: 0, labelInLegend: '南海灵通铝锭', pointSize: 7},
      2: {targetAxisIndex: 0, labelInLegend: '有花,DX51D+Z,1*1219*C,120g乐从镇,鞍钢', pointSize: 7},
      3: {targetAxisIndex: 0, labelInLegend: '无花,DX51D+Z,1*1250*C,120g,乐从镇,鞍钢', pointSize: 7},
      4: {targetAxisIndex: 0, labelInLegend: '无花,DX51D+Z,1*1250*C,120g,济南,宝钢', pointSize: 7},
      5: {targetAxisIndex: 0, labelInLegend: '无花,DX51D+Z,1*1250*C,120g,广州,鞍钢', pointSize: 7},
      6: {targetAxisIndex: 0, labelInLegend: '无花,DX51D+Z,1*1250*C,120g,天津,河钢唐', pointSize: 7}
    })
    .setOption('vAxes', {
      0: {
        viewWindow: { min: 3500, max: 25000 },
        format: '#,##0',
        logScale: true
      }
    })
    .setOption('legend', {
      position: 'bottom',
      alignment: 'start',
      maxLines: 7,
      textStyle: {
        fontSize: 11
      }
    })
    .setOption('chartArea', {
      width: '90%',
      height: '80%',
      left: '8%',
      top: '5%'
    })
    .setOption('hAxis', {
      title: '',
      type: 'date',
      titleTextStyle: {
        italic: false,
        bold: true,
        fontSize: 11
      },
      format: 'yyyy/MM/dd',
      slantedText: true,
      slantedTextAngle: 0,
      showTextEvery: 14,
      gridlines: {count: 10},
      minorGridlines: {count: 10},
      viewWindow: {
        min: startDate,
        max: endDate
      },
      textStyle: {
        fontSize: 10
      }
    })
    .setOption('lineWidth', 4)
    .setOption('interpolateNulls', true)
    .build();
  chartSheet.insertChart(chart);

  // M1:R1を結合して大見出し
  chartSheet.getRange('M1:R1').merge().setValue('现价与旧价对比');
  chartSheet.getRange('M1').setHorizontalAlignment('center');

  // ヘッダー（M2:R2）
  const header = [['', '日期', '长江铝锭(元/吨)', '长江铝锭走势(%)', '南海灵通铝锭(元/吨)', '南海灵通铝锭走势(%)']];
  chartSheet.getRange(2, 13, 1, 6).setValues(header);
  // ヘッダーを中央揃え
  chartSheet.getRange(2, 13, 1, 6).setHorizontalAlignment('center');

  // 行タイトル（M3:M9）
  const rowTitles = [
    '最新单价',
    '对比前一天',
    '对比上星期同期',
    '对比本月初',
    '对比上月同期',
    '对比上一季度同期',
    '对比年初'
  ];
  chartSheet.getRange(3, 13, rowTitles.length, 1).setValues(rowTitles.map(v => [v]));

  // データ部分（N3:R9）は空欄でOK
  chartSheet.getRange(3, 14, 7, 6).clearContent();

  Logger.log(`処理されたデータ数: ${filteredData.length}`);
  Logger.log(`最初のデータ: ${JSON.stringify(filteredData[0])}`);
  Logger.log(`最後のデータ: ${JSON.stringify(filteredData[filteredData.length-1])}`);

  // --- 比較表データ自動取得・反映 ---
  const aluCompareData = aluminumSheet.getRange(3, 1, aluminumSheet.getLastRow() - 2, 10).getValues();

  // 日付パース関数
  function parseDateString(str) {
    if (str instanceof Date) return str;
    if (typeof str === 'string') {
      let parts = str.includes('/') ? str.split('/') : str.split('-');
      if (parts.length === 3) {
        return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      }
    }
    return null;
  }

  // 最新データ取得
  const latestRow = aluCompareData[0]; // 先頭行が最新
  const latestDate = parseDateString(latestRow[0]);
  const latestChangjiang = latestRow[1];
  const latestNanhai = latestRow[9];

  // 比較用ターゲット日付を計算
  function getTargetDate(base, type) {
    const d = new Date(base.getTime());
    switch(type) {
      case 'prevDay': d.setDate(d.getDate() - 1); break;
      case 'weekAgo': d.setDate(d.getDate() - 7); break;
      case 'monthStart': d.setDate(1); break;
      case 'monthAgo': d.setMonth(d.getMonth() - 1); break;
      case 'quarterAgo': d.setMonth(d.getMonth() - 3); break;
      case 'yearStart': d.setMonth(0); d.setDate(2); break;
    }
    return d;
  }

  // 指定日付に完全一致する行を返す
  function findRowByDate(target) {
    for (let i = 0; i < aluCompareData.length; i++) {
      const rowDate = parseDateString(aluCompareData[i][0]);
      if (!rowDate) continue;
      if (
        rowDate.getFullYear() === target.getFullYear() &&
        rowDate.getMonth() === target.getMonth() &&
        rowDate.getDate() === target.getDate()
      ) {
        return aluCompareData[i];
      }
    }
    return null; // 見つからなければnull
  }

  // target日付以前で一番近いデータを返す
  function findClosestPastRow(target) {
    let minDiff = Infinity, found = null;
    for (let i = 0; i < aluCompareData.length; i++) {
      const rowDate = parseDateString(aluCompareData[i][0]);
      if (!rowDate) continue;
      if (rowDate >= target) continue; // targetより前のみ
      const diff = target - rowDate;
      if (diff >= 0 && diff < minDiff) {
        minDiff = diff;
        found = aluCompareData[i];
      }
    }
    return found;
  }

  // 各比較ロジックでデータ取得
  const compareTypes = [
    {type: 'latest', label: '最新单价'},
    {type: 'prevDay', label: '对比前一天'},
    {type: 'weekAgo', label: '对比上星期同期'},
    {type: 'monthStart', label: '对比本月初'},
    {type: 'monthAgo', label: '对比上月同期'},
    {type: 'quarterAgo', label: '对比上一季度同期'},
    {type: 'yearStart', label: '对比年初'}
  ];

  const tableRows = [];
  for (let i = 0; i < compareTypes.length; i++) {
    let row, date, changjiang, nanhai;
    if (compareTypes[i].type === 'latest') {
      row = latestRow;
    } else if (compareTypes[i].type === 'prevDay') {
      // 最新日より前で一番近い日付（直近営業日）
      row = findClosestPastRow(latestDate);
    } else if (compareTypes[i].type === 'quarterAgo') {
      // 最新日から4ヶ月前あたりで一番近い日付
      const targetDate = getTargetDate(latestDate, 'quarterAgo');
      row = findClosestPastRow(targetDate);
    } else {
      const targetDate = getTargetDate(latestDate, compareTypes[i].type);
      row = findRowByDate(targetDate) || findClosestPastRow(targetDate);
    }
    date = row ? row[0] : '';
    changjiang = row ? row[1] : '';
    nanhai = row ? row[9] : '';
    tableRows.push([date, changjiang, '', nanhai, '']);
  }

  // 変動率計算
  function calcRate(newVal, oldVal) {
    if (!newVal || !oldVal || isNaN(newVal) || isNaN(oldVal) || Number(oldVal) === 0) return '';
    const rate = (Number(newVal) - Number(oldVal)) / Number(oldVal) * 100;
    return (rate > 0 ? '' : '') + rate.toFixed(2) + '%';
  }
  // 最新値を基準に変動率を計算
  for (let i = 1; i < tableRows.length; i++) {
    tableRows[i][2] = calcRate(tableRows[0][1], tableRows[i][1]); // 长江铝锭走势
    tableRows[i][4] = calcRate(tableRows[0][3], tableRows[i][3]); // 南海灵通铝锭走势
  }

  // N3:R9に反映（=NA()対応）
  chartSheet.getRange(3, 14, tableRows.length, 5).setValues(
    tableRows.map(row => row.map(safeValue))
  );

  // データをセットした後、M:R列の幅を自動調整
  chartSheet.autoResizeColumns(13, 6); // M(13)〜R(18)まで

  // M1:R9に罫線を引く
  chartSheet.getRange('M1:R9').setBorder(true, true, true, true, true, true);

  // M:R列の幅をすべて182に固定
  for (let col = 13; col <= 18; col++) {
    chartSheet.setColumnWidth(col, 182);
  }

  // --- 镀锌板卷价格の価格比較表（M26:X34） ---
  // 日付（A列5行目以降）
  const steelDates = steelSheet.getRange(5, 1, steelSheet.getLastRow() - 4, 1).getValues();
  // 価格（B～F列5行目以降）
  const steelCompareData = steelSheet.getRange(5, 2, steelSheet.getLastRow() - 4, 5).getValues();

  // 最新データ取得: Mysteel 貼り付けは日付が昇順（A5 が最古列）のため、A 列の日付最大の行を「最新」とする
  //（先頭行＝[0] は最古日で、之前誤把「第一行當成最新」導致比較表不更新）
  let steelLatestIdx = -1;
  let steelLatestTime = -Infinity;
  for (let si = 0; si < steelDates.length; si++) {
    const d = parseDateString(steelDates[si][0]);
    if (!d || isNaN(d.getTime())) continue;
    const t = d.getTime();
    if (t > steelLatestTime) {
      steelLatestTime = t;
      steelLatestIdx = si;
    }
  }
  const steelLatestDate = steelLatestIdx >= 0 ? parseDateString(steelDates[steelLatestIdx][0]) : null;
  const steelLatestPrices = steelLatestIdx >= 0 ? steelCompareData[steelLatestIdx] : ['', '', '', '', ''];

  // target日付以前で一番近いデータを返す
  function findClosestPastSteelRow(target) {
    let minDiff = Infinity, found = null, foundDate = '';
    for (let i = 0; i < steelDates.length; i++) {
      const rowDate = parseDateString(steelDates[i][0]);
      if (!rowDate) continue;
      if (rowDate >= target) continue;
      const diff = target - rowDate;
      if (diff >= 0 && diff < minDiff) {
        minDiff = diff;
        found = steelCompareData[i];
        foundDate = steelDates[i][0];
      }
    }
    return found ? {date: foundDate, prices: found} : null;
  }

  // 比較ロジック
  const steelTableRows = [];
  for (let i = 0; i < compareTypes.length; i++) {
    let date, prices;
    if (compareTypes[i].type === 'latest') {
      if (steelLatestIdx < 0) {
        date = '';
        prices = ['', '', '', '', ''];
      } else {
        date = steelDates[steelLatestIdx][0];
        prices = steelCompareData[steelLatestIdx];
      }
    } else if (compareTypes[i].type === 'prevDay') {
      const found = findClosestPastSteelRow(steelLatestDate);
      date = found ? found.date : '';
      prices = found ? found.prices : ['', '', '', '', ''];
    } else if (compareTypes[i].type === 'quarterAgo') {
      const targetDate = getTargetDate(steelLatestDate, 'quarterAgo');
      const found = findClosestPastSteelRow(targetDate);
      date = found ? found.date : '';
      prices = found ? found.prices : ['', '', '', '', ''];
    } else {
      const targetDate = getTargetDate(steelLatestDate, compareTypes[i].type);
      let foundIndex = steelDates.findIndex(d => {
        const rowDate = parseDateString(d[0]);
        return rowDate && rowDate.getFullYear() === targetDate.getFullYear() && rowDate.getMonth() === targetDate.getMonth() && rowDate.getDate() === targetDate.getDate();
      });
      if (foundIndex !== -1) {
        date = steelDates[foundIndex][0];
        prices = steelCompareData[foundIndex];
      } else {
        const found = findClosestPastSteelRow(targetDate);
        date = found ? found.date : '';
        prices = found ? found.prices : ['', '', '', '', ''];
      }
    }
    // 11列構成: [日付, 価格1, 価格1変動率, ..., 価格5, 価格5変動率]
    const row = [date];
    for (let j = 0; j < 5; j++) {
      row.push(prices[j]);
      if (i === 0) {
        row.push(''); // 最新行は変動率空欄
      } else {
        row.push(calcRate(steelTableRows[0][j * 2 + 1], prices[j]));
      }
    }
    steelTableRows.push(row);
  }

  // 変動率計算
  function calcSteelRate(newVal, oldVal) {
    if (!newVal || !oldVal || isNaN(newVal) || isNaN(oldVal) || Number(oldVal) === 0) return '';
    const rate = (Number(newVal) - Number(oldVal)) / Number(oldVal) * 100;
    return rate.toFixed(2) + '%';
  }

  // ヘッダー
  const steelHeader = [
    '', '日期',
    '有花,DX51D+Z,1*1219*C,120g乐从镇,鞍钢', '有花,DX51D+Z,1*1219*C,120g乐从镇,鞍钢走势(%)',
    '无花,DX51D+Z,1*1250*C,120g,乐从镇,鞍钢', '无花,DX51D+Z,1*1250*C,120g,乐从镇,鞍钢走势(%)',
    '无花,DX51D+Z,1*1250*C,120g,济南,宝钢', '无花,DX51D+Z,1*1250*C,120g,济南,宝钢走势(%)',
    '无花,DX51D+Z,1*1250*C,120g,广州,鞍钢', '无花,DX51D+Z,1*1250*C,120g,广州,鞍钢走势(%)',
    '无花,DX51D+Z,1*1250*C,120g,天津,河钢唐', '无花,DX51D+Z,1*1250*C,120g,天津,河钢唐走势(%)'
  ];
  chartSheet.getRange(26, 13, 1, 12).setValues([steelHeader]);
  chartSheet.getRange(26, 13, 1, 12).setHorizontalAlignment('center');

  // 縦タイトル
  chartSheet.getRange(27, 13, rowTitles.length, 1).setValues(rowTitles.map(v => [v]));

  // データ貼り付け（=NA()対応）
  chartSheet.getRange(27, 14, steelTableRows.length, 11).setValues(
    steelTableRows.map(row => row.map(safeValue))
  );

  // 罫線
  chartSheet.getRange('M26:X34').setBorder(true, true, true, true, true, true);
  // 列幅
  for (let col = 13; col <= 24; col++) {
    chartSheet.setColumnWidth(col, 182);
  }
}

function normalizeSteelSheetDates() {
  const ss = getMonitoredSpreadsheet_();
  const steelSheet = ss.getSheetByName(ALU_GALVANIZED_STEEL_SHEET_NAME);
  if (!steelSheet) {
    return;
  }
  const lastRow = steelSheet.getLastRow();
  const dateRange = steelSheet.getRange(5, 1, lastRow - 4, 1); // A5:A
  const dates = dateRange.getValues();

  const newDates = dates.map(row => {
    const dateStr = row[0];
    if (typeof dateStr === 'string' && dateStr.includes('-')) {
      // 2025-04-25 → 2025/04/25
      return [dateStr.replace(/-/g, '/')];
    }
    return [dateStr];
  });

  dateRange.setValues(newDates);
}

function normalizeAluminumSheetDates() {
  const ss = getMonitoredSpreadsheet_();
  const aluminumSheet = ss.getSheetByName(ALU_CANON_.SHEET_ALU_DAILY);
  if (!aluminumSheet) {
    return;
  }
  const lastRow = aluminumSheet.getLastRow();
  const dateRange = aluminumSheet.getRange(3, 1, lastRow - 2, 1); // A3:A
  const dates = dateRange.getValues();

  const newDates = dates.map(row => {
    const dateStr = row[0];
    if (typeof dateStr === 'string' && dateStr.includes('/')) {
      // 2025/4/16 → 2025-04-16
      const parts = dateStr.split('/');
      if (parts.length === 3) {
        const yyyy = parts[0];
        const mm = parts[1].padStart(2, '0');
        const dd = parts[2].padStart(2, '0');
        return [`${yyyy}-${mm}-${dd}`];
      }
    }
    return [dateStr];
  });

  dateRange.setValues(newDates);
}

function strictNormalizeAluminumSheetDates() {
  const ss = getMonitoredSpreadsheet_();
  const sheet = ss.getSheetByName(ALU_CANON_.SHEET_ALU_DAILY);
  const lastRow = sheet.getLastRow();
  const dateRange = sheet.getRange(3, 1, lastRow - 2, 1); // A3:A
  const dateValues = dateRange.getValues();

  for (let i = 0; i < dateValues.length; i++) {
    let val = dateValues[i][0];
    if (typeof val === 'string') {
      // 不可視文字・全角スペース・改行などを除去
      val = val.replace(/[\s\u3000]/g, '');
    }
    // 日付として認識できるか
    let d = new Date(val);
    if (d instanceof Date && !isNaN(d)) {
      // yyyy/mm/dd形式で統一
      let yyyy = d.getFullYear();
      let mm = String(d.getMonth() + 1).padStart(2, '0');
      let dd = String(d.getDate()).padStart(2, '0');
      dateValues[i][0] = `${yyyy}/${mm}/${dd}`;
    } else {
      // 変換できなければ空欄にする（または警告ログ）
      dateValues[i][0] = '';
      Logger.log(`A列${i+3}行目は日付として認識できません: ${val}`);
    }
  }
  dateRange.setValues(dateValues);
}

/** スプレッドシートの日付列から「直近営業日」とのずれを検出（例外がなくても中身が古い場合用） */
function getExpectedLatestBusinessDate_() {
  const today = new Date();
  let mostRecentBusinessDay = new Date(today);
  const dayOfWeek = today.getDay();
  if (dayOfWeek === 0) {
    mostRecentBusinessDay.setDate(today.getDate() - 2);
  } else if (dayOfWeek === 6) {
    mostRecentBusinessDay.setDate(today.getDate() - 1);
  }
  return dateOnly_(mostRecentBusinessDay);
}

function dateOnly_(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function parseCellDate_(v) {
  if (v === "" || v === null || v === undefined) return null;
  if (v instanceof Date && !isNaN(v)) return dateOnly_(v);
  if (typeof v === "string") {
    const cleaned = v.replace(/[\s\u3000]/g, "");
    if (!cleaned) return null;
    const parsed = new Date(cleaned);
    if (!isNaN(parsed)) return dateOnly_(parsed);
  }
  return null;
}

function maxDateFromValues_(values) {
  let maxD = null;
  for (let i = 0; i < values.length; i++) {
    const p = parseCellDate_(values[i][0]);
    if (p && (!maxD || p > maxD)) maxD = p;
  }
  return maxD;
}

function validateSpreadsheetFreshness_(spreadsheetId) {
  const warnings = [];
  const tz = Session.getScriptTimeZone();
  const expected = getExpectedLatestBusinessDate_();
  const expectedMs = expected.getTime();
  const dayMs = 864e5;

  let ss;
  try {
    ss = SpreadsheetApp.openById(spreadsheetId);
  } catch (e) {
    return ["スプレッドシートを開けませんでした: " + e.toString()];
  }

  const steelSheet = ss.getSheetByName(ALU_GALVANIZED_STEEL_SHEET_NAME);
  const aluSheet = ss.getSheetByName(ALU_CANON_.SHEET_ALU_DAILY);
  if (!steelSheet || !aluSheet) {
    warnings.push("シート「" + ALU_GALVANIZED_STEEL_SHEET_NAME + "」または「" + ALU_CANON_.SHEET_ALU_DAILY + "」が見つかりません。");
    return warnings;
  }

  const lastRowSteel = steelSheet.getLastRow();
  const lastRowAlu = aluSheet.getLastRow();
  const steelEnd = Math.max(5, lastRowSteel - 4);
  const aluEnd = Math.max(3, lastRowAlu - 2);

  const steelDates = steelSheet.getRange(5, 1, steelEnd, 1).getValues();
  const aluDates = aluSheet.getRange(3, 1, aluEnd, 1).getValues();

  const steelMax = maxDateFromValues_(steelDates);
  const aluMax = maxDateFromValues_(aluDates);

  function fmt(d) {
    return Utilities.formatDate(d, tz, "yyyy/MM/dd");
  }

  function checkBehind(maxDate, label) {
    if (!maxDate) {
      warnings.push(label + "の日付列（A列）から有効な日付を読み取れませんでした。");
      return;
    }
    const d0 = dateOnly_(maxDate);
    const diff = Math.round((expectedMs - d0.getTime()) / dayMs);
    if (diff > 0) {
      warnings.push(
        label +
          "のA列で最新の日付は " +
          fmt(d0) +
          " です。\n\n" +
          "直近営業日（" +
          fmt(expected) +
          "）より " +
          diff +
          " 日分古い可能性があります。"
      );
    }
  }

  checkBehind(steelMax, ALU_GALVANIZED_STEEL_SHEET_NAME);
  checkBehind(aluMax, ALU_CANON_.SHEET_ALU_DAILY);

  return warnings;
}

// メイン実行関数を修正
function executeAllProcesses() {
  const tz = Session.getScriptTimeZone();
  const runAt = Utilities.formatDate(new Date(), tz, "yyyy/MM/dd HH:mm:ss");
  let errorMessages = [];
  let successMessages = [];
  let dataWarnings = [];

  try {
    assertAluPipelineInvariants_();
    // 1. processGmailAttachment の実行
    console.log("1. Mysteel データの処理を開始");
    try {
      const gmailResult = processGmailAttachment();
      if (gmailResult && gmailResult.imported === false) {
        if (gmailResult.reason === "no_mail") {
          dataWarnings.push(
            "Gmail 上で Mysteel 日次（件名に TodayMysteeldata 等）のメールが、フォールバック検索含め直近7日で見つかりませんでした。\n\n" +
              "镀锌板卷のシートは更新されていません（古いデータのままの可能性があります）。"
          );
        } else if (gmailResult.reason === "no_excel") {
          dataWarnings.push("対象メールに Excel 添付が見つかりませんでした。镀锌板卷は更新されていません。");
        }
      } else {
        successMessages.push("Mysteelデータの処理が完了しました。");
      }
    } catch (e) {
      errorMessages.push("Mysteelデータの処理でエラーが発生: " + e.toString());
      console.error("Mysteelデータ処理エラー:", e);
    }

    // 2. updateAluminumPriceSheet の実行
    console.log("2. アルミ価格データの更新を開始");
    try {
      updateAluminumPriceSheet();
      successMessages.push("アルミ価格データの更新が完了しました。");
    } catch (e) {
      errorMessages.push("アルミ価格データの更新でエラーが発生: " + e.toString());
      console.error("アルミ価格更新エラー:", e);
    }

    // 3. グラフの更新
    console.log("3. グラフの更新を開始");
    try {
      updatePriceChart();
      successMessages.push("グラフの更新が完了しました。");
    } catch (e) {
      errorMessages.push("グラフの更新でエラーが発生: " + e.toString());
      console.error("グラフ更新エラー:", e);
    }

    const freshnessWarnings = validateSpreadsheetFreshness_(ALU_SPREADSHEET_ID);
    const allDataWarnings = dataWarnings.concat(freshnessWarnings);

    // 処理結果の通知
    try {
      if (errorMessages.length > 0) {
        GmailApp.sendEmail(
          Session.getEffectiveUser().getEmail(),
          "[铝价分析表] 定期一括更新 完了（一部エラー）",
          `実行日時: ${runAt}\n\n` +
            `【エラー】\n` +
            errorMessages.join("\n") +
            `\n\n【成功した処理】\n` +
            successMessages.join("\n") +
            (allDataWarnings.length
              ? `\n\n【データ確認（参考）】\n` + allDataWarnings.join("\n\n")
              : "")
        );
      } else if (allDataWarnings.length > 0) {
        GmailApp.sendEmail(
          Session.getEffectiveUser().getEmail(),
          "[铝价分析表] 定期一括更新 完了（データ要確認）",
          `処理は例外なく終了しましたが、次の内容と矛盾する可能性があります。スプレッドシートを確認してください。\n\n` +
            `【要注意】\n` +
            allDataWarnings.join("\n\n") +
            `\n\n実行日時: ${runAt}\n\n` +
            `【完了した処理】\n` +
            successMessages.join("\n")
        );
      } else {
        GmailApp.sendEmail(
          Session.getEffectiveUser().getEmail(),
          "[铝价分析表] 定期一括更新 完了",
          `Mysteel 取込・长江/南海反映・グラフ更新まで、一括処理はすべて正常に完了しました（日付の整合も問題ありません）。\n\n` +
            `実行日時: ${runAt}\n\n` +
            `【完了した処理】\n` +
            successMessages.join("\n")
        );
      }
    } catch (e) {
      // メール送信エラーが発生しても処理を止めない
      console.error("メール送信エラー:", e);
    }
  } catch (e) {
    console.error("メイン処理でエラーが発生:", e);
    try {
      GmailApp.sendEmail(
        Session.getEffectiveUser().getEmail(),
        "[铝价分析表] 定期一括更新 異常終了",
        `実行日時: ${runAt}\n\nメイン処理で予期せぬエラーが発生しました。\n\n${e.toString()}`
      );
    } catch (mailError) {
      // メール送信エラーが発生しても処理を止めない
      console.error("重大なエラー通知メール送信エラー:", mailError);
    }
  }
}

// グラフのみを更新するテスト用関数
function testUpdatePriceChart() {
  try {
    updatePriceChart();
    Logger.log("グラフのみの更新が完了しました。");
  } catch (e) {
    Logger.log("グラフのみの更新でエラー: " + e.toString());
  }
}
