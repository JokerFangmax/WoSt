param(
    [string]$OutRoot = "experiments\rerun_cross_mesh_20260606",
    [switch]$SkipWost,
    [switch]$SkipZombie
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ZombieRoot = "C:\THU\homework\zombie"
$WostExe = Join-Path $ProjectRoot "build\Release\wost.exe"
$ZombiePython = Join-Path $ZombieRoot ".venv\Scripts\python.exe"
$OutRootPath = if ([System.IO.Path]::IsPathRooted($OutRoot)) { $OutRoot } else { Join-Path $ProjectRoot $OutRoot }
$LogPath = Join-Path $OutRootPath "command_log.txt"

function Ensure-Dir([string]$Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

function Run-Step([string]$Name, [string]$WorkingDir, [string[]]$Command) {
    Ensure-Dir $OutRootPath
    Ensure-Dir $WorkingDir
    $cmdText = ($Command | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }) -join " "

    Add-Content -Path $LogPath -Encoding UTF8 -Value ""
    Add-Content -Path $LogPath -Encoding UTF8 -Value "## $Name"
    Add-Content -Path $LogPath -Encoding UTF8 -Value ("time: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
    Add-Content -Path $LogPath -Encoding UTF8 -Value "cwd: $WorkingDir"
    Add-Content -Path $LogPath -Encoding UTF8 -Value ("$ " + $cmdText)

    $stdout = Join-Path $OutRootPath "_stdout.tmp"
    $stderr = Join-Path $OutRootPath "_stderr.tmp"
    $start = Get-Date
    $proc = Start-Process -FilePath $Command[0] `
        -ArgumentList ($Command[1..($Command.Count - 1)]) `
        -WorkingDirectory $WorkingDir `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr
    $elapsed = ((Get-Date) - $start).TotalSeconds

    if (Test-Path $stdout) {
        Get-Content $stdout | Add-Content -Path $LogPath -Encoding UTF8
        Remove-Item $stdout -Force
    }
    if ((Test-Path $stderr) -and ((Get-Item $stderr).Length -gt 0)) {
        Add-Content -Path $LogPath -Encoding UTF8 -Value "[stderr]"
        Get-Content $stderr | Add-Content -Path $LogPath -Encoding UTF8
    }
    if (Test-Path $stderr) {
        Remove-Item $stderr -Force
    }
    Add-Content -Path $LogPath -Encoding UTF8 -Value ("[exit={0}, wall_seconds={1:n3}]" -f $proc.ExitCode, $elapsed)

    if ($proc.ExitCode -ne 0) {
        throw "Step failed: $Name"
    }
}

function Run-Wost-Formal([string]$MeshLabel, [string]$MeshPath, [double]$Cube, [int]$DirSeed, [int]$NeuSeed, [int]$OptSeed) {
    $work = Join-Path $OutRootPath ("wost_" + $MeshLabel)
    Ensure-Dir $work
    Run-Step "WoSt $MeshLabel dirichlet convergence" $work @($WostExe, "--mode", "convergence", "--obj", $MeshPath, "--queries", "500", "--threads", "8", "--seed", "$DirSeed", "--cube", "$Cube")
    Run-Step "WoSt $MeshLabel dirichlet epsilon" $work @($WostExe, "--mode", "epsilon", "--obj", $MeshPath, "--queries", "500", "--threads", "8", "--seed", "$DirSeed", "--cube", "$Cube")
    Run-Step "WoSt $MeshLabel dirichlet grid" $work @($WostExe, "--mode", "grid", "--obj", $MeshPath, "--grid", "16", "--threads", "8", "--seed", "$DirSeed", "--cube", "$Cube")
    Run-Step "WoSt $MeshLabel geometry benchmark" $work @($WostExe, "--mode", "geometry", "--obj", $MeshPath, "--queries", "500", "--threads", "8", "--seed", "$DirSeed", "--cube", "$Cube")
    Run-Step "WoSt $MeshLabel mixed Neumann" $work @($WostExe, "--mode", "neumann", "--obj", $MeshPath, "--queries", "100", "--grid", "8", "--threads", "8", "--seed", "$NeuSeed", "--cube", "$Cube")
    Run-Step "WoSt $MeshLabel optimization diagnostics" $work @($WostExe, "--mode", "optimization", "--obj", $MeshPath, "--queries", "500", "--threads", "8", "--seed", "$OptSeed", "--cube", "$Cube", "--max-samples", "512", "--min-samples", "64", "--batch-size", "32", "--target-rse", "0.05", "--rse-eps", "0.001")
}

function Run-Wost-Diagnostics([string]$MeshLabel, [string]$MeshPath, [double]$Cube, [int]$Seed, [double[]]$Point) {
    $work = Join-Path $OutRootPath ("wost_" + $MeshLabel)
    $diag = Join-Path $work "diagnostics"
    Ensure-Dir $diag
    Run-Step "WoSt $MeshLabel boundary bias detector" $work @($WostExe, "--mode", "bias_detector", "--obj", $MeshPath, "--queries", "500", "--grid", "16", "--threads", "8", "--seed", "$Seed", "--cube", "$Cube", "--boundary", "neumann", "--epsilon", "0.001", "--walks", "128", "--bias-threshold", "2.0", "--out", (Join-Path $diag "boundary_bias_detector.vtk"), "--csv", (Join-Path $diag "boundary_bias_summary.csv"))
    foreach ($tau in @("0.003", "0.005", "0.008")) {
        Run-Step "WoSt $MeshLabel variance adaptive tau=$tau" $work @($WostExe, "--mode", "variance_adaptive", "--obj", $MeshPath, "--queries", "500", "--grid", "16", "--threads", "8", "--seed", "$Seed", "--cube", "$Cube", "--boundary", "dirichlet", "--epsilon", "0.0001", "--pilot-samples", "32", "--min-samples", "32", "--max-samples", "1024", "--batch-size", "32", "--target-std-error", "$tau", "--out", (Join-Path $diag "variance_adaptive_points.csv"), "--summary-out", (Join-Path $diag "variance_adaptive_summary.csv"), "--csv", (Join-Path $diag "variance_adaptive_comparison.csv"))
    }
    Run-Step "WoSt $MeshLabel live trace" $work @($WostExe, "--mode", "demo_point", "--obj", $MeshPath, "--queries", "500", "--grid", "16", "--threads", "8", "--seed", "$Seed", "--cube", "$Cube", "--boundary", "neumann", "--walks", "64", "--epsilon", "0.0001", "--point", "$($Point[0])", "$($Point[1])", "$($Point[2])", "--trace-walks", "8", "--trace-out", (Join-Path $diag "live_trace.csv"), "--summary-out", (Join-Path $diag "live_demo_summary.csv"))
}

function Run-Zombie([string]$MeshLabel, [string]$MeshPath, [double]$Cube, [int]$DirSeed, [int]$NeuSeed) {
    $wostResults = Join-Path $OutRootPath ("wost_" + $MeshLabel + "\results")
    $dirOut = Join-Path $OutRootPath ("zombie_" + $MeshLabel + "_dirichlet")
    $neuOut = Join-Path $OutRootPath ("zombie_" + $MeshLabel + "_neumann")
    Run-Step "Zombie $MeshLabel dirichlet baseline" $ZombieRoot @($ZombiePython, (Join-Path $ZombieRoot "scripts\zombie_bunny_baseline.py"), "--mode", "all", "--obj", $MeshPath, "--out", $dirOut, "--reference-results", $wostResults, "--queries", "500", "--geometry-queries", "500", "--grid", "16", "--seed", "$DirSeed", "--cube", "$Cube", "--max-steps", "512")
    Run-Step "Zombie $MeshLabel mixed Neumann baseline" $ZombieRoot @($ZombiePython, (Join-Path $ZombieRoot "scripts\zombie_neumann_bunny_baseline.py"), "--mode", "all", "--obj", $MeshPath, "--out", $neuOut, "--reference-results", $wostResults, "--queries", "100", "--grid", "8", "--seed", "$NeuSeed", "--cube", "$Cube", "--max-steps", "2048")
}

function Run-Diagnostic-Plots([string]$MeshLabel) {
    $work = Join-Path $OutRootPath ("wost_" + $MeshLabel)
    $diag = Join-Path $work "diagnostics"
    $Py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $Py)) {
        $Py = "python"
    }
    Run-Step "Plot $MeshLabel boundary bias" $ProjectRoot @($Py, (Join-Path $ProjectRoot "scripts\plot_boundary_bias.py"), "--vtk", (Join-Path $diag "boundary_bias_detector.vtk"), "--summary", (Join-Path $diag "boundary_bias_summary.csv"), "--out", (Join-Path $diag "boundary_bias_detector.png"))
    Run-Step "Plot $MeshLabel variance adaptive" $ProjectRoot @($Py, (Join-Path $ProjectRoot "scripts\plot_variance_adaptive.py"), "--comparison", (Join-Path $diag "variance_adaptive_comparison.csv"), "--points", (Join-Path $diag "variance_adaptive_points.csv"), "--tradeoff-out", (Join-Path $diag "variance_adaptive_tradeoff.png"), "--samples-out", (Join-Path $diag "variance_adaptive_samples_map.png"))
    Run-Step "Plot $MeshLabel live trace" $ProjectRoot @($Py, (Join-Path $ProjectRoot "scripts\plot_live_trace.py"), "--trace", (Join-Path $diag "live_trace.csv"), "--summary", (Join-Path $diag "live_demo_summary.csv"), "--out", (Join-Path $diag "live_trace_plot.png"))
}

Ensure-Dir $OutRootPath
Set-Content -Path $LogPath -Encoding UTF8 -Value ("# Cross-mesh rerun command log`nstarted: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))

if (-not (Test-Path $WostExe)) {
    Run-Step "Build WoSt Release" $ProjectRoot @("powershell", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $ProjectRoot "build_cpp.ps1"))
}

$BunnyObj = Join-Path $ProjectRoot "obj\Bunny.obj"
$SpotObj = Join-Path $ProjectRoot "spot\spot_triangulated.obj"

if (-not $SkipWost) {
    Run-Wost-Formal "bunny" $BunnyObj 0.22 12345 32345 52345
    Run-Wost-Diagnostics "bunny" $BunnyObj 0.22 12345 @(0.05, 0.02, 0.08)
    Run-Wost-Formal "spot" $SpotObj 1.1 54321 64321 74321
    Run-Wost-Diagnostics "spot" $SpotObj 1.1 54321 @(0.8, 0.0, 0.2)
}

if (-not $SkipZombie) {
    Run-Zombie "bunny" $BunnyObj 0.22 12345 32345
    Run-Zombie "spot" $SpotObj 1.1 54321 64321
}

if (-not $SkipWost) {
    Run-Diagnostic-Plots "bunny"
    Run-Diagnostic-Plots "spot"
}

Add-Content -Path $LogPath -Encoding UTF8 -Value ("finished: " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Write-Host "Rerun complete: $OutRootPath"
