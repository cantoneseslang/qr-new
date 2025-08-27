# Vercelブラウザ自動デプロイスクリプト
Write-Host "🚀 Vercelブラウザ自動デプロイ開始..." -ForegroundColor Green

# プロジェクトディレクトリに移動
Set-Location "KHK-AI-DETECT-MONITOR"

# ファイル存在確認
$requiredFiles = @("app.py", "vercel.json", "requirements.txt", "README.md")
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file 確認済み" -ForegroundColor Green
    } else {
        Write-Host "❌ $file が見つかりません" -ForegroundColor Red
        exit 1
    }
}

Write-Host "📁 プロジェクトファイル準備完了" -ForegroundColor Green
Write-Host ""

# ブラウザでVercelを開く
Write-Host "🌐 ブラウザでVercelを開いています..." -ForegroundColor Yellow

try {
    # デフォルトブラウザでVercelを開く
    Start-Process "https://vercel.com/kirii"
    
    Write-Host "✅ ブラウザが開きました！" -ForegroundColor Green
    Write-Host ""
    Write-Host "🔧 次の手順を実行してください:" -ForegroundColor Cyan
    Write-Host "1. ログイン" -ForegroundColor White
    Write-Host "2. 'New Project' をクリック" -ForegroundColor White
    Write-Host "3. プロジェクト名: KHK-AI-DETECT-MONITOR" -ForegroundColor White
    Write-Host "4. 以下のファイルをアップロード:" -ForegroundColor White
    
    Get-ChildItem | ForEach-Object {
        Write-Host "   • $($_.Name) ($($_.Length) bytes)" -ForegroundColor White
    }
    
    Write-Host "5. 'Deploy' をクリック" -ForegroundColor White
    Write-Host ""
    Write-Host "🎯 デプロイ完了後、固定URLが取得できます！" -ForegroundColor Green
    
} catch {
    Write-Host "🚨 エラーが発生しました: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "📋 手動で vercel.com/kirii にアクセスしてください" -ForegroundColor Yellow
}
