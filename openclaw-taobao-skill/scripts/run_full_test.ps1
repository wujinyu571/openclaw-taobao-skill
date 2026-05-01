# 一键测试脚本 - 完整流程自动化
# 运行方式: .\scripts\run_full_test.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Taobao Skill Complete Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check if Feishu mock server is running
Write-Host "[1/4] Checking Feishu mock server..." -ForegroundColor Yellow
$serverStarted = $false
$maxRetries = 10

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/api/results" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "   [OK] Feishu mock server is running" -ForegroundColor Green
        $serverStarted = $true
        break
    } catch {
        if ($i -eq 1) {
            Write-Host "   [INFO] Server not running, starting..." -ForegroundColor Yellow
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "python scripts/feishu_mock_server.py"
        }
        Write-Host "   [WAIT] Waiting for server to start... ($i/$maxRetries)" -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

if (-not $serverStarted) {
    Write-Host "   [ERROR] Failed to start Feishu mock server" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 2. Send test task
Write-Host "[2/4] Sending test task..." -ForegroundColor Yellow

# Read configuration from .env file with UTF-8 encoding
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
$envConfig = @{}

if (Test-Path $envFile) {
    # 关键修复：使用 UTF-8 编码读取文件
    Get-Content $envFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -and !$line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            if ($parts.Count -eq 2) {
                $key = $parts[0].Trim()
                $value = $parts[1].Trim()
                $envConfig[$key] = $value
            }
        }
    }

    # Extract values with defaults
    $keyword = if ($envConfig['DEFAULT_KEYWORD']) { $envConfig['DEFAULT_KEYWORD'] } else { "索尼耳机" }
    $minRate = if ($envConfig['DEFAULT_MIN_POSITIVE_RATE']) { [int]$envConfig['DEFAULT_MIN_POSITIVE_RATE'] } else { 99 }
    $maxItems = if ($envConfig['DEFAULT_MAX_ITEMS']) { [int]$envConfig['DEFAULT_MAX_ITEMS'] } else { 3 }

    Write-Host "   [INFO] Loaded config from .env" -ForegroundColor Gray
    Write-Host "   - DEFAULT_KEYWORD: $keyword" -ForegroundColor Gray
    Write-Host "   - DEFAULT_MIN_POSITIVE_RATE: $minRate%" -ForegroundColor Gray
    Write-Host "   - DEFAULT_MAX_ITEMS: $maxItems" -ForegroundColor Gray
} else {
    Write-Host "   [WARN] .env file not found, using defaults" -ForegroundColor Yellow
    $keyword = "索尼耳机"
    $minRate = 99
    $maxItems = 3
}

$taskParams = @{
    keyword = $keyword
    min_positive_rate = $minRate
    max_items = $maxItems
    task_id = "test-task-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
}

$retryCount = 0
$maxSendRetries = 5
$taskSent = $false

while ($retryCount -lt $maxSendRetries -and -not $taskSent) {
    try {
        Invoke-RestMethod -Uri "http://localhost:8080/api/add_task" -Method Post -Body ($taskParams | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 10
        Write-Host "   [OK] Task sent successfully" -ForegroundColor Green
        Write-Host "   - Task ID: $($taskParams.task_id)" -ForegroundColor Gray
        Write-Host "   - Keyword: $($taskParams.keyword)" -ForegroundColor Gray
        Write-Host "   - Min Rate: $($taskParams.min_positive_rate)%" -ForegroundColor Gray
        $taskSent = $true
    } catch {
        $retryCount++
        Write-Host "   [RETRY] Send failed, retrying ($retryCount/$maxSendRetries)..." -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
}

if (-not $taskSent) {
    Write-Host "   [ERROR] Failed to send task after $maxSendRetries attempts" -ForegroundColor Red
    exit 1
}

Write-Host ""

# 3. Run Skill
Write-Host "[3/4] Starting Taobao Skill..." -ForegroundColor Yellow
Write-Host "   TIP: Complete QR login in browser window if needed" -ForegroundColor Gray
Write-Host ""

$skillProcess = Start-Process python -ArgumentList "-m", "skill.main" -PassThru -NoNewWindow

# Wait for execution (max 5 minutes)
$timeout = 300
$elapsed = 0
while (!$skillProcess.HasExited -and $elapsed -lt $timeout) {
    Start-Sleep -Seconds 2
    $elapsed += 2
    Write-Host "`r   [RUNNING] Elapsed: $elapsed/$timeout seconds" -ForegroundColor Cyan -NoNewline
}

if ($skillProcess.HasExited) {
    Write-Host "`r   [OK] Skill execution completed" -ForegroundColor Green
} else {
    Write-Host "`r   [WARN] Execution timeout, forcing termination" -ForegroundColor Red
    Stop-Process -Id $skillProcess.Id -Force
}

Write-Host ""

# 4. View results
Write-Host "[4/4] Fetching test results..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

try {
    $results = Invoke-RestMethod -Uri "http://localhost:8080/api/results" -TimeoutSec 10

    if ($results.count -eq 0) {
        Write-Host "   [WARN] No results received yet" -ForegroundColor Yellow
    } else {
        Write-Host "   [OK] Received $($results.count) result(s)" -ForegroundColor Green
        Write-Host ""

        # Get the latest result record
        $latestRecord = $results.results[-1]
        $resultData = $latestRecord.result

        # Check if it's a webhook message or direct RunResult
        if ($resultData.msg_type -eq "text") {
            # It's a webhook message from Feishu
            Write-Host "   Latest Webhook Message:" -ForegroundColor Cyan
            Write-Host "   $($resultData.content.text)" -ForegroundColor White
            Write-Host ""

            # Try to extract info from the text message
            $text = $resultData.content.text
            if ($text -match "task_id=(\S+)") {
                Write-Host "   - Task ID: $($matches[1])" -ForegroundColor Gray
            }
            if ($text -match "success=(\w+)") {
                $successVal = $matches[1]
                $color = if($successVal -eq "True") { "Green" } else { "Red" }
                Write-Host "   - Success: $successVal" -ForegroundColor $color
            }
            if ($text -match "message=(\S+)") {
                Write-Host "   - Message: $($matches[1])" -ForegroundColor Gray
            }
            if ($text -match "added=(\d+)") {
                Write-Host "   - Added to Cart: $($matches[1])" -ForegroundColor Gray
            }
        } else {
            # It's a direct RunResult object
            Write-Host "   Latest Result:" -ForegroundColor Cyan
            Write-Host "   - Task ID: $($resultData.task_id)" -ForegroundColor White

            if ($null -ne $resultData.success) {
                $successColor = if($resultData.success) { "Green" } else { "Red" }
                Write-Host "   - Success: $($resultData.success)" -ForegroundColor $successColor
            }

            if ($resultData.message) {
                Write-Host "   - Message: $($resultData.message)" -ForegroundColor White
            }

            if ($null -ne $resultData.matched_items) {
                Write-Host "   - Matched Items: $($resultData.matched_items.Count)" -ForegroundColor White
            }

            if ($null -ne $resultData.added_to_cart_count) {
                Write-Host "   - Added to Cart: $($resultData.added_to_cart_count)" -ForegroundColor White
            }

            if ($resultData.artifacts -and $resultData.artifacts.screenshot) {
                Write-Host "   - Screenshot: $($resultData.artifacts.screenshot)" -ForegroundColor White
            }
        }

        Write-Host ""
        Write-Host "   Full result JSON saved in Feishu mock server console" -ForegroundColor Gray
    }
} catch {
    Write-Host "   [ERROR] Failed to fetch results: $_" -ForegroundColor Red
    Write-Host "   TIP: Check Feishu mock server console for results" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Test Completed!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check Feishu mock server window for detailed logs" -ForegroundColor Gray
Write-Host "  2. View screenshots in logs/ directory" -ForegroundColor Gray
Write-Host "  3. Check logs/run.log for full execution log" -ForegroundColor Gray
