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

# 環境変数でVercel設定
$env:VERCEL_ORG_ID = "team_hfdVMgcn7GojZhG8Cz5Pb3iA"
$env:VERCEL_PROJECT_NAME = "KHK-AI-DETECT-MONITOR"

try {
    # 非対話式でデプロイ
    Write-Host "📤 デプロイ実行中..." -ForegroundColor Cyan
    $deployResult = vercel --yes --prod --token $env:VERCEL_TOKEN 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ デプロイ成功！" -ForegroundColor Green
        Write-Host "🔗 固定URLが取得できました" -ForegroundColor Cyan
        Write-Host $deployResult -ForegroundColor White
    } else {
        Write-Host "❌ デプロイ失敗" -ForegroundColor Red
        Write-Host $deployResult -ForegroundColor Red
        Write-Host ""
        Write-Host "🔑 Vercelトークンが必要です" -ForegroundColor Yellow
        Write-Host "1. vercel.com/account/tokens でトークンを取得" -ForegroundColor White
        Write-Host "2. 環境変数 VERCEL_TOKEN に設定" -ForegroundColor White
    }
} catch {
    Write-Host "🚨 エラーが発生しました: $($_.Exception.Message)" -ForegroundColor Red
}
