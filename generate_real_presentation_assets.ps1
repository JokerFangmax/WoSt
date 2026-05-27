$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Missing virtual environment at .venv. Run .\setup_env.ps1 first."
}

Write-Host "[1/4] Building C++ solver with Visual Studio toolchain..."
& (Join-Path $projectRoot "build_cpp.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$exeCandidates = @(
    (Join-Path $projectRoot "build\Release\wost.exe"),
    (Join-Path $projectRoot "build\wost.exe")
)
$solverExe = $exeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $solverExe) {
    throw "Could not find wost.exe under build\\ after compilation."
}

Write-Host "[2/4] Running main.cpp testcase to generate VTK outputs..."
& $solverExe
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[3/4] Generating presentation figure from real VTK outputs..."
& $venvPython ".\presentation_viz.py" `
    --slice "test1_manufactured_slice_xy.vtk" `
    --pointcloud "test1_manufactured_pointcloud.vtk" `
    --output "presentation_figure.png"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[4/4] Generating live demo assets..."
& $venvPython ".\live_demo.py" --walks 40 --animate --save "live_demo.gif"
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
& $venvPython ".\live_demo.py" --walks 40 --save "live_demo_poster.png" --no-show
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Done. Generated assets:"
Write-Host "  - test1_manufactured_pointcloud.vtk"
Write-Host "  - test1_manufactured_slice_xy.vtk"
Write-Host "  - presentation_figure.png"
Write-Host "  - live_demo.gif"
Write-Host "  - live_demo_poster.png"
