$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$url = "http://localhost:8080/live-demo-fixed"

function Test-LiveDemoUp {
    param([string]$TargetUrl)
    try {
        $response = Invoke-WebRequest -Uri $TargetUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

if (Test-LiveDemoUp -TargetUrl $url) {
    Write-Output "Live demo server already running. Opening URL..."
    Start-Process $url
    exit 0
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

Write-Output "Starting live demo server using $pythonExe ..."
Start-Process -FilePath $pythonExe -ArgumentList "live_demo.py" -WorkingDirectory $projectRoot

$maxAttempts = 90
for ($i = 1; $i -le $maxAttempts; $i++) {
    if (Test-LiveDemoUp -TargetUrl $url) {
        Write-Output "Live demo is up. Opening URL..."
        Start-Process $url
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Output "Server start triggered, but URL is not reachable yet."
Write-Output "Open manually after a few seconds: $url"
exit 0
