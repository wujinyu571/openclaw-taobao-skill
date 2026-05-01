param(
    [string]$Task = "search=索尼耳机;rating=99;max_items=3",
    [switch]$Headful
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Python virtual environment not found. Please run: python -m venv .venv"
}

$cmd = ".\.venv\Scripts\python -m skill.main --task `"$Task`""
if ($Headful) {
    $cmd = "$cmd --headful"
}

Write-Host "Running: $cmd"
Invoke-Expression $cmd
