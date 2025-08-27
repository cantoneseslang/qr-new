# ngrok自動監視・再起動スクリプト
Write-Host "🚀 ngrok自動監視開始..." -ForegroundColor Green

while ($true) {
    # ngrokプロセス確認
    $ngrokProcess = Get-Process ngrok -ErrorAction SilentlyContinue
    
    if ($ngrokProcess) {
        Write-Host "✅ ngrok動作中: PID $($ngrokProcess.Id)" -ForegroundColor Green
    } else {
        Write-Host "❌ ngrok停止検出 - 再起動中..." -ForegroundColor Red
        
        # ngrok再起動
        try {
            Start-Process ngrok -ArgumentList "http 5013" -WindowStyle Hidden
            Write-Host "🔄 ngrok再起動完了" -ForegroundColor Yellow
            Start-Sleep 10  # 起動待機
        } catch {
            Write-Host "🚨 ngrok再起動失敗: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    Start-Sleep 30  # 30秒間隔で監視
}

