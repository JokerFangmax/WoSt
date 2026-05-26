$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$vswhere = "C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path $vswhere)) {
    throw "vswhere.exe was not found. Install Visual Studio Build Tools 2022 first."
}

$vsPath = & $vswhere -latest -products * -property installationPath
if (-not $vsPath) {
    throw "Visual Studio Build Tools 2022 was not found."
}

$devCmd = Join-Path $vsPath "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $devCmd)) {
    throw "VsDevCmd.bat was not found under $vsPath."
}

$buildDir = Join-Path $projectRoot "build"
$tempCmd = Join-Path $env:TEMP "wost_build.cmd"

$cmd = @"
@echo off
call "$devCmd" -host_arch=x64 -arch=x64
where cl >nul 2>nul || (echo Missing C++ compiler. Install the MSVC v143 x64/x86 build tools workload.& exit /b 1)
where cmake >nul 2>nul || (echo Missing CMake. Install the C++ CMake tools for Windows component or standalone CMake.& exit /b 1)
if not exist "$buildDir" mkdir "$buildDir"
cd /d "$buildDir"
cmake -S "$projectRoot" -B "$buildDir"
cmake --build "$buildDir" --config Release
"@

Set-Content -Path $tempCmd -Value $cmd -Encoding ASCII

try {
    & cmd /c $tempCmd
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Remove-Item $tempCmd -ErrorAction SilentlyContinue
}
