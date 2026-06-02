$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

$exe = ".\build\Release\wost.exe"
if (-not (Test-Path $exe)) {
    $exe = ".\build\wost.exe"
}
if (-not (Test-Path $exe)) {
    throw "Could not find wost.exe. Build first with .\build_cpp.ps1 or CMake."
}

& $exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python .\scripts\plot_optimization_experiments.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
