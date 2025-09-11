# GAS Gmail Inventory Processor セットアップ手順

## 📋 概要
Gmailから「inventory」件名のメールを検索し、添付ファイル「inventory.pdf」をGemini 2.5で要約してGoogle Sheetsに保存するシステムです。

**特徴:**
- 今日の日付でメールをフィルタリング（毎日2回のメールに対応）
- 複数メールの一括処理
- 各メールの処理状況を詳細ログで確認

## 🔧 必要な準備

### 1. Google Apps Script プロジェクトの作成
1. [Google Apps Script](https://script.google.com/) にアクセス
2. 「新しいプロジェクト」をクリック
3. プロジェクト名を「Gmail Inventory Processor」に変更

### 2. 必要なAPIの有効化
以下のAPIを有効化してください：

#### Gmail API
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. プロジェクトを選択（または新規作成）
3. 「APIとサービス」→「ライブラリ」
4. 「Gmail API」を検索して有効化

#### Google Drive API
1. 同じくGoogle Cloud Consoleで
2. 「Google Drive API」を検索して有効化

#### Google Sheets API
1. 「Google Sheets API」を検索して有効化

### 3. 認証の設定
1. Google Cloud Consoleで「認証情報」→「認証情報を作成」→「サービスアカウント」
2. サービスアカウントを作成
3. キーをJSON形式でダウンロード
4. サービスアカウントのメールアドレスをGoogle Sheetsに共有

## 📝 コードの設定

### 1. メインスクリプトの配置
1. `gmail_inventory_processor.gs` の内容をGoogle Apps Scriptエディタにコピー
2. ファイル名を「Code」から「gmail_inventory_processor」に変更

### 2. 設定値の確認
スクリプト内の `CONFIG` オブジェクトを確認：

```javascript
const CONFIG = {
  GEMINI_API_KEY: 'AIzaSyDny2k_jer095pYLo8dCiZEpHo8WHEgf_s', // 提供されたAPIキー
  SHEET_ID: '1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M', // 提供されたシートID
  GMAIL_ADDRESS: 'bestinksalesman@gmail.com', // 提供されたGmailアドレス
  INVENTORY_SUMMARY_SHEET_NAME: 'InventorySummaryReport',
  SEARCH_QUERY: 'subject:inventory has:attachment filename:inventory.pdf'
};
```

### 3. 権限の設定
1. スクリプトを初回実行すると権限の許可が求められます
2. 以下の権限を許可：
   - Gmail読み取り
   - Google Drive読み取り
   - Google Sheets読み取り・書き込み

## 🚀 実行方法

### 1. 手動実行
1. Google Apps Scriptエディタで `manualRun` 関数を選択
2. 「実行」ボタンをクリック
3. 初回は権限の許可が必要

### 2. 定期実行の設定
1. `setupTrigger` 関数を実行
2. 毎日午前9時に自動実行されるように設定

### 3. 実行ログの確認
1. 「実行」→「ログを表示」で実行状況を確認
2. エラーが発生した場合は詳細なログが表示されます

## 📊 結果の確認

### Google Sheetsでの確認
1. 指定されたスプレッドシートを開く
2. 「InventorySummaryReport」シートを確認
3. 以下の列が作成されます：
   - 処理日時
   - メール番号（今日の何件目か）
   - メール件名
   - 送信者
   - 受信時刻
   - 要約内容

### 処理ログの確認
1. Google Apps Scriptエディタで「実行」→「ログを表示」
2. 以下の情報が表示されます：
   - 今日の検索範囲
   - 見つかったメール数
   - 各メールの処理状況
   - エラーが発生した場合の詳細

## 🔍 トラブルシューティング

### よくある問題と解決方法

#### 1. Gmail API エラー
- **問題**: Gmail APIが有効化されていない
- **解決**: Google Cloud ConsoleでGmail APIを有効化

#### 2. 権限エラー
- **問題**: 必要な権限が許可されていない
- **解決**: スクリプトを再実行して権限を許可

#### 3. PDF処理エラー
- **問題**: PDFのテキスト抽出に失敗
- **解決**: フォールバック機能が動作し、基本的な情報が保存されます

#### 4. Gemini API エラー
- **問題**: APIキーが無効または制限に達した
- **解決**: APIキーを確認し、使用量制限を確認

## 📈 機能拡張

### 追加可能な機能
1. **複数メールの一括処理**
2. **要約のカスタマイズ**
3. **エラー通知の改善**
4. **処理履歴の管理**

### カスタマイズ例
```javascript
// 検索条件の変更
const CONFIG = {
  SEARCH_QUERY: 'subject:inventory has:attachment filename:inventory.pdf newer_than:7d'
};

// 要約プロンプトのカスタマイズ
const prompt = `
カスタム要約プロンプト:
${pdfText}
`;
```

## 📞 サポート

問題が発生した場合は、以下を確認してください：
1. 実行ログの内容
2. APIの有効化状況
3. 権限の設定状況
4. ネットワーク接続

## 🔄 更新履歴

### 2025年9月11日 - バージョン 2.0 大幅機能強化

#### 新機能・改善点

**1. データ抽出精度の大幅向上**
- 複数回のGemini API処理（3パス）を実装
  - パス1: PDFの1-3ページ目を詳細解析
  - パス2: PDFの4-6ページ目を詳細解析  
  - パス3: PDFの7ページ目以降を詳細解析
- 特定商品コード（TNIA, TNIC, TNIL, TNIW, TNMA, TNMC, UU, V, GSY）の重点検索
- GSYパターンが見つからない場合の追加処理機能

**2. データ品質管理の強化**
- 重複除去機能の実装（商品コードベース）
- ギリシャ文字の正規化（ΤΝΙΑ → TNIA）
- 数値フォーマットの統一（カンマ区切り、小数点なし）

**3. Google Sheets出力の最適化**
- シート名を「InventorySummaryReport」に変更
- 列構成の最適化：
  - A列: Product Code
  - B列: Description  
  - C列: On Hand
  - D列: Quantity SC w/o DN
  - E列: Available
  - F列: 更新時間（香港時間、yyyy/mm/dd hh:mm形式）
- 既存データの完全削除機能（2行目以降を削除してから新データ挿入）

**4. エラー処理の強化**
- Gemini API 503エラー（サーバー過負荷）の自動リトライ
- フォールバック処理の実装
- 詳細なログ出力による問題診断機能

**5. トリガー設定の簡素化**
- `main()`関数の追加（トリガー設定時に1つの関数を選択するだけ）
- 既存の`processInventoryEmails()`関数との連携

#### 技術的改善

**Gemini API処理**
- モデルを`gemini-1.5-flash`に変更
- 出力トークン数を8192から16384に倍増
- 複数回処理による網羅的なデータ抽出

**データ処理**
- 正規化機能による文字エンコーディング問題の解決
- 重複除去アルゴリズムの実装
- バッチ処理から一括処理への変更

**時間処理**
- 香港時間（UTC+8）の正確な計算
- 更新時間の統一フォーマット（yyyy/mm/dd hh:mm）

#### 設定変更

```javascript
const CONFIG = {
  GEMINI_API_KEY: 'AIzaSyDny2k_jer095pYLo8dCiZEpHo8WHEgf_s',
  GEMINI_MODEL: 'gemini-1.5-flash', // 新規追加
  SHEET_ID: '1u_fsEVAumMySLx8fZdMP5M4jgHiGG6ncPjFEXSXHQ1M',
  GMAIL_ADDRESS: 'bestinksalesman@gmail.com',
  INVENTORY_SUMMARY_SHEET_NAME: 'InventorySummaryReport', // 変更
  SEARCH_QUERY: 'subject:inventory has:attachment filename:inventory.pdf'
};
```

#### 実行結果

- **データ抽出精度**: 154行（パス1）+ 94行（パス2）= 248行の高精度抽出
- **エラー処理**: 503エラー発生時も自動リトライで正常完了
- **処理時間**: 約1分30秒（3パス処理 + エラーリトライ含む）
- **データ品質**: 重複除去、正規化、フォーマット統一済み

---

**作成日**: 2025年1月27日  
**最終更新**: 2025年9月11日  
**バージョン**: 2.0  
**対応API**: Gmail API, Google Drive API, Google Sheets API, Gemini 1.5 Flash API
