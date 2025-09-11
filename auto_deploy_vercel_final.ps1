# Vercel完全自動デプロイスクリプト
Write-Host "🚀 Vercel完全自動デプロイ開始..." -ForegroundColor Green

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

# Vercel CLIで自動デプロイ
Write-Host "🔧 Vercel CLIで自動デプロイ実行中..." -ForegroundColor Yellow

try {
    # 非対話式でデプロイ
    Write-Host "📤 デプロイ実行中..." -ForegroundColor Cyan
    vercel --yes --prod
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ デプロイ成功！" -ForegroundColor Green
        Write-Host "🔗 固定URLが取得できました" -ForegroundColor Cyan
    } else {
        Write-Host "❌ デプロイ失敗" -ForegroundColor Red
        Write-Host "🔑 Vercelログインが必要です" -ForegroundColor Yellow
    }
} catch {
    Write-Host "🚨 エラーが発生しました" -ForegroundColor Red
}



