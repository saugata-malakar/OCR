param(
    [string]$Image = "PaddleOCR-main\docs\images\ppocrv4_en.jpg",
    [string]$OutputDir = "ocr_demo_output",
    [ValidateSet("paddle", "transformers")]
    [string]$Engine = "paddle"
)

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$demoScript = Join-Path $repoRoot "PaddleOCR-main\run_ocr_demo.py"

if (-not (Test-Path $python)) {
    throw "Python interpreter not found: $python"
}

if (-not (Test-Path $demoScript)) {
    throw "Demo script not found: $demoScript"
}

$imagePath = if ([System.IO.Path]::IsPathRooted($Image)) {
    $Image
} else {
    Join-Path $repoRoot $Image
}

$outputPath = if ([System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir
} else {
    Join-Path $repoRoot $OutputDir
}

& $python $demoScript --image $imagePath --output-dir $outputPath --engine $Engine
exit $LASTEXITCODE