# 監視システム 確実起動スクリプト
# 作成日: 2025-08-30

Write-Host "🏭 KIRII CCTV監視システム 確実起動スクリプト" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

# 1. 既存のPythonプロセスを停止
Write-Host "🛑 既存のPythonプロセスを停止中..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# 2. ポート5013の使用状況を確認
Write-Host "🔍 ポート5013の使用状況を確認中..." -ForegroundColor Yellow
$portCheck = netstat -ano | findstr :5013
if ($portCheck) {
    Write-Host "⚠️  ポート5013が使用中です。プロセスを終了します..." -ForegroundColor Red
    $portCheck | ForEach-Object {
        if ($_ -match '\s+(\d+)$') {
            $pid = $matches[1]
            Write-Host "🔄 プロセス $pid を終了中..." -ForegroundColor Yellow
            taskkill /PID $pid /F 2>$null
        }
    }
}

# 3. 少し待機
Write-Host "⏳ システムの安定化を待機中..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 4. 監視システムを起動
Write-Host "🚀 監視システムを起動中..." -ForegroundColor Green
Write-Host "📡 起動完了までお待ちください..." -ForegroundColor Cyan

try {
    # バックグラウンドで起動
    Start-Process python -ArgumentList "cctv_streaming_fixed.py" -WindowStyle Normal -Wait:$false
    
    # 起動確認
    Write-Host "⏳ 起動確認中..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    
    # ポート5013の確認
    $listening = netstat -ano | findstr ":5013.*LISTENING"
    if ($listening) {
        Write-Host "✅ 監視システムが正常に起動しました！" -ForegroundColor Green
        Write-Host "🌐 アクセスURL: http://localhost:5013" -ForegroundColor Cyan
        Write-Host "🎯 ブラウザで上記URLにアクセスしてください" -ForegroundColor Cyan
    } else {
        Write-Host "❌ 起動に失敗しました" -ForegroundColor Red
        Write-Host "🔍 エラーログを確認してください" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ 起動エラー: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "================================================" -ForegroundColor Green
Write-Host "スクリプト完了" -ForegroundColor Green


