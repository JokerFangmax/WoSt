param(
    [switch]$Apply,
    [switch]$ArchiveLegacyResults
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

function Test-SkippedPath {
    param([string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $root = $projectRoot.Path.TrimEnd([char[]]@('\', '/'))
    if (-not $resolved.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $relative = $resolved.Substring($root.Length).TrimStart([char[]]@('\', '/'))
    $firstSegment = ($relative -split '[\\/]')[0]

    return $(
        $firstSegment -eq ".git" -or
        $firstSegment -eq ".venv" -or
        $firstSegment -eq "build" -or
        $firstSegment -like "build-*" -or
        $firstSegment -eq "local_archive"
    )
}

function Show-Action {
    param(
        [string]$Action,
        [string]$Path,
        [string]$Target = ""
    )

    if ($Target) {
        Write-Host ("{0}: {1} -> {2}" -f $Action, $Path, $Target)
    }
    else {
        Write-Host ("{0}: {1}" -f $Action, $Path)
    }
}

function Remove-IfExists {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) {
        Show-Action "remove" $Path
        if ($Apply) {
            Remove-Item -LiteralPath $Path -Recurse -Force
        }
    }
}

Write-Host "Repository cleanup inventory"
Write-Host ("Mode: {0}" -f ($(if ($Apply) { "APPLY" } else { "DRY RUN" })))
Write-Host ""

Get-ChildItem -Path . -Recurse -Force -Directory -Filter "__pycache__" |
    Where-Object { -not (Test-SkippedPath $_.FullName) } |
    ForEach-Object { Remove-IfExists $_.FullName }

Get-ChildItem -Path . -Recurse -Force -File -Include ".DS_Store", "*.pyc", "*.pyo" |
    Where-Object { -not (Test-SkippedPath $_.FullName) } |
    ForEach-Object { Remove-IfExists $_.FullName }

$rootBinaries = @(
    "hello_test.exe",
    "omp_test.exe"
)

foreach ($binary in $rootBinaries) {
    Remove-IfExists (Join-Path $projectRoot $binary)
}

if ($ArchiveLegacyResults) {
    $archiveRoot = Join-Path $projectRoot "local_archive"
    $legacyDirs = Get-ChildItem -Path . -Force -Directory |
        Where-Object { $_.Name -like "results_archive_*" -or $_.Name -eq "results_saved" }

    foreach ($dir in $legacyDirs) {
        $target = Join-Path $archiveRoot $dir.Name
        Show-Action "archive" $dir.FullName $target
        if ($Apply) {
            New-Item -ItemType Directory -Force -Path $archiveRoot | Out-Null
            Move-Item -LiteralPath $dir.FullName -Destination $target -Force
        }
    }
}

Write-Host ""
if ($Apply) {
    Write-Host "Cleanup complete."
}
else {
    Write-Host "Dry run only. Re-run with -Apply to perform these operations."
}
