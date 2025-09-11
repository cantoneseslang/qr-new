# 監視システム 簡単起動スクリプト
# 作成日: 2025-08-30

Write-Host "🏭 KIRII CCTV監視システム 起動" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green

# オプション選択
Write-Host "起動方法を選択してください:" -ForegroundColor Cyan
Write-Host "1. 通常起動（手動監視）" -ForegroundColor Yellow
Write-Host "2. 自動監視起動（推奨）" -ForegroundColor Green
Write-Host "3. 既存プロセス確認" -ForegroundColor Cyan

$choice = Read-Host "選択 (1-3)"

switch ($choice) {
    "1" {
        Write-Host "🚀 通常起動を開始..." -ForegroundColor Yellow
        python cctv_streaming_fixed.py
    }
    "2" {
        Write-Host "🤖 自動監視起動を開始..." -ForegroundColor Green
        .\monitor_service.ps1
    }
    "3" {
        Write-Host "🔍 既存プロセス確認中..." -ForegroundColor Cyan
        
        $pythonProcess = Get-Process python -ErrorAction SilentlyContinue
        if ($pythonProcess) {
            Write-Host "✅ Pythonプロセス実行中:" -ForegroundColor Green
            $pythonProcess | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize
        } else {
            Write-Host "❌ Pythonプロセスが見つかりません" -ForegroundColor Red
        }
        
        $listening = netstat -ano | findstr ":5013.*LISTENING"
        if ($listening) {
            Write-Host "✅ ポート5013でリッスン中:" -ForegroundColor Green
            Write-Host $listening -ForegroundColor Cyan
        } else {
            Write-Host "❌ ポート5013でリッスンしていません" -ForegroundColor Red
        }
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:5013" -TimeoutSec 5 -ErrorAction Stop
            Write-Host "✅ HTTP応答正常 (Status: $($response.StatusCode))" -ForegroundColor Green
        } catch {
            Write-Host "❌ HTTP応答なし" -ForegroundColor Red
        }
        
        Read-Host "Enterキーで終了"
    }
    default {
        Write-Host "❌ 無効な選択です" -ForegroundColor Red
    }
}


