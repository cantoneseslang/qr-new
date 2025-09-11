# Monitor System Auto-Recovery Script
# Created: 2025-08-30
# Purpose: Auto-start and auto-recovery

param(
    [int]$CheckInterval = 30,  # Check interval (seconds)
    [int]$MaxRetries = 5       # Max retry count
)

Write-Host "Auto-Recovery Monitor Service Starting" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green
Write-Host "Check Interval: $CheckInterval seconds" -ForegroundColor Cyan
Write-Host "Max Retries: $MaxRetries" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Green

$retryCount = 0
$processName = "python"
$scriptPath = "cctv_streaming_fixed.py"
$targetPort = 5013

function Start-MonitorSystem {
    Write-Host "Starting Monitor System..." -ForegroundColor Yellow
    
    # Stop existing processes
    Get-Process $processName -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    
    # Clear port
    $portProcesses = netstat -ano | findstr ":$targetPort"
    if ($portProcesses) {
        $portProcesses | ForEach-Object {
            if ($_ -match '\s+(\d+)$') {
                $pid = $matches[1]
                taskkill /PID $pid /F 2>$null
            }
        }
    }
    
    Start-Sleep -Seconds 3
    
    # Start new process
    $process = Start-Process python -ArgumentList $scriptPath -WindowStyle Normal -PassThru
    Write-Host "Process Started (PID: $($process.Id))" -ForegroundColor Green
    
    return $process
}

function Test-SystemHealth {
    # 1. Check Python process
    $pythonProcess = Get-Process $processName -ErrorAction SilentlyContinue
    if (-not $pythonProcess) {
        return $false
    }
    
    # 2. Check port
    $listening = netstat -ano | findstr ":$targetPort.*LISTENING"
    if (-not $listening) {
        return $false
    }
    
    # 3. Check HTTP response
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$targetPort" -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            return $true
        }
    } catch {
        return $false
    }
    
    return $false
}

# Main loop
while ($true) {
    try {
        $isHealthy = Test-SystemHealth
        
        if ($isHealthy) {
            Write-Host "System Running OK ($(Get-Date -Format 'HH:mm:ss'))" -ForegroundColor Green
            $retryCount = 0  # Reset retry count on success
        } else {
            Write-Host "System Error Detected ($(Get-Date -Format 'HH:mm:ss'))" -ForegroundColor Red
            
            if ($retryCount -lt $MaxRetries) {
                $retryCount++
                Write-Host "Auto-Restarting... (Attempt $retryCount/$MaxRetries)" -ForegroundColor Yellow
                
                $process = Start-MonitorSystem
                
                # Startup confirmation (max 60 seconds)
                $startupTimeout = 60
                $elapsed = 0
                
                while ($elapsed -lt $startupTimeout) {
                    Start-Sleep -Seconds 5
                    $elapsed += 5
                    
                    if (Test-SystemHealth) {
                        Write-Host "Restart Success! System Recovered" -ForegroundColor Green
                        break
                    }
                    
                    Write-Host "Checking startup... ($elapsed/$startupTimeout seconds)" -ForegroundColor Cyan
                }
                
                if ($elapsed -ge $startupTimeout) {
                    Write-Host "Startup Timeout" -ForegroundColor Red
                }
            } else {
                Write-Host "Max retry count reached. Contact administrator." -ForegroundColor Red
                Write-Host "Error: System cannot recover" -ForegroundColor Red
            }
        }
        
        Start-Sleep -Seconds $CheckInterval
        
    } catch {
        Write-Host "Monitor Script Error: $($_.Exception.Message)" -ForegroundColor Red
        Start-Sleep -Seconds $CheckInterval
    }
}


