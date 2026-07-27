$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$url = "http://127.0.0.1:8080/Capstone_project_13_Cross-Platform-Mobile-Test-Script-Generator"
$logDir = Join-Path $projectRoot "artifacts\logs"
$stdoutLog = Join-Path $logDir "live_demo_stdout.log"
$stderrLog = Join-Path $logDir "live_demo_stderr.log"

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
    Write-Output "Cross-Platform Mobile Test Script Generator Live Demo is already running at $url"
    exit 0
}

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

$venvPythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
if (Test-Path $venvPythonw) {
    $pythonExe = $venvPythonw
}

New-Item -ItemType Directory -Path $logDir -Force | Out-Null

Write-Output "Starting Cross-Platform Mobile Test Script Generator Live Demo server using $pythonExe ..."
Start-Process -FilePath $pythonExe -ArgumentList "live_demo.py" -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

$maxAttempts = 90
for ($i = 1; $i -le $maxAttempts; $i++) {
    if (Test-LiveDemoUp -TargetUrl $url) {
        Write-Output "Cross-Platform Mobile Test Script Generator Live Demo is up at $url"
        Write-Output "Logs: $stdoutLog and $stderrLog"
        exit 0
    }
    Start-Sleep -Seconds 1
}

Write-Output "Server start triggered, but URL is not reachable yet."
Write-Output "Open manually after a few seconds: $url"
Write-Output "Logs: $stdoutLog and $stderrLog"
exit 0
