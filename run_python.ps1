$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    & $venvPython (Join-Path $projectRoot "WoSt.py") --resolution 40 --walks 200
    exit $LASTEXITCODE
}

python (Join-Path $projectRoot "WoSt.py") --resolution 40 --walks 200
