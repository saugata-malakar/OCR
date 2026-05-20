param(
    [int]$Port = 5000
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $repoRoot "..\.venv\Scripts\python.exe"
$app = Join-Path $repoRoot "app.py"

if (-not (Test-Path $python)) {
    throw "Python interpreter not found at $python"
}
if (-not (Test-Path $app)) {
    throw "App not found at $app"
}

Write-Host "Starting local PaddleOCR server on http://127.0.0.1:$Port"
Start-Process -NoNewWindow -FilePath $python -ArgumentList "$app"