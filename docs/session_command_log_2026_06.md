# Session Command Log, 2026-06

This document records the terminal commands that were used or reconstructed from this working session. It focuses on commands that affected code, experiments, generated figures, reports, or verification.

Notes:

- Manual code edits were made through patches and are described by the resulting files, but patch payloads themselves are not shell commands.
- Some exploratory reads such as `Get-Content`, `Select-String`, and `rg` are grouped by purpose instead of being repeated every time they were run.
- Paths are written for the WoSt workspace `C:\THU\projects\WoSt_Final_project-1`.

## 1. Project Inspection

```powershell
Get-ChildItem -Force
rg --files
git status --short
```

```powershell
Get-Content main.cpp
Get-Content src\WoStKernel.cpp
Get-Content src\WoStKernel.hpp
Get-Content src\utils.hpp
Get-Content CMakeLists.txt
Get-Content README.md
Get-Content src\WoStGeometryBackend.hpp
Get-Content src\CubeOuterBoundary.hpp
Get-Content src\CubeOuterBoundary.cpp
```

```powershell
Select-String -Path src\utils.hpp -Pattern "adaptiveSampling|samplesUsed|SCALARS samples_used"
Select-String -Path src\WoStKernel.cpp -Pattern "sampleLimit|adaptiveSampling|reflect\(|finalise"
Select-String -Path main.cpp -Pattern "struct CliOptions|RunPointBenchmark|RunGridBenchmark|RunConvergence|RunAdaptive|int main"
Select-String -Path scripts\plot_benchmarks.py -Pattern "def plot_rmse|def plot_epsilon|def plot_adaptive|def main"
```

## 2. Build and Toolchain Checks

The direct CMake build was attempted first:

```powershell
cmake --build build --config Release -j
```

The project build helper was inspected and then run with PowerShell execution-policy bypass:

```powershell
Get-Content build_cpp.ps1
.\build_cpp.ps1
powershell -ExecutionPolicy Bypass -File .\build_cpp.ps1
```

The final runnable executable used for experiments was:

```text
build\Release\wost.exe
```

## 3. Directory Creation

```powershell
New-Item -ItemType Directory -Force scripts
New-Item -ItemType Directory -Force docs
New-Item -ItemType Directory -Force experiments
New-Item -ItemType Directory -Force experiments\figures
New-Item -ItemType Directory -Force experiments\final_report_figures
```

## 4. Lightweight WoSt Sanity Tests

```powershell
.\build\Release\wost.exe --mode convergence --queries 20 --threads 2 --seed 7
.\build\Release\wost.exe --mode grid --grid 4 --threads 2 --seed 7
.\build\Release\wost.exe --mode adaptive --queries 20 --grid 4 --threads 2 --seed 7
```

Plotting dependency checks:

```powershell
python scripts\plot_benchmarks.py
if (Test-Path .venv\Scripts\python.exe) { .\.venv\Scripts\python.exe -c "import matplotlib; print(matplotlib.__version__)" } else { 'no venv python' }
Get-Content requirements.txt
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

## 5. Bunny Mesh Checks

```powershell
Get-ChildItem obj
(Select-String -Path obj\Bunny.obj -Pattern '^f ').Count
(Select-String -Path obj\Bunny.obj -Pattern '^v ').Count
Get-Content obj\Bunny.obj | Select-Object -First 8
```

```powershell
@'
from pathlib import Path
mins=[float('inf')]*3
maxs=[float('-inf')]*3
for line in Path('obj/Bunny.obj').read_text().splitlines():
    if line.startswith('v '):
        vals=list(map(float,line.split()[1:4]))
        for i,v in enumerate(vals):
            mins[i]=min(mins[i],v); maxs[i]=max(maxs[i],v)
print('mins', mins)
print('maxs', maxs)
print('extent', [maxs[i]-mins[i] for i in range(3)])
'@ | python -
```

## 6. Results Cleanup and Archiving Pattern

This pattern was used when starting clean result folders:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'; if (Test-Path results) { Move-Item results "results_archive_$stamp" }; New-Item -ItemType Directory -Force results | Out-Null; Write-Output "Clean results ready. Previous results archived as results_archive_$stamp"
```

## 7. WoSt Optimization Experiments

Individual experiment modes:

```powershell
.\build\Release\wost.exe --mode adaptive_compare --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
.\build\Release\wost.exe --mode antithetic --queries 1000 --threads 8 --max-samples 512
.\build\Release\wost.exe --mode lazy --queries 1000 --threads 8 --max-samples 512
.\build\Release\wost.exe --mode epsilon_extrapolation --queries 1000 --threads 8 --max-samples 512
.\build\Release\wost.exe --mode neumann_sanity --queries 1000 --threads 8 --max-samples 512
```

Full optimization batch and plotting:

```powershell
.\build\Release\wost.exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
.\.venv\Scripts\python.exe .\scripts\plot_optimization_experiments.py
```

Convenience script:

```powershell
.\scripts\run_optimization_experiments.ps1
```

## 8. Original Bunny Dirichlet and Neumann Runs

Dirichlet Bunny formal-style commands used before the cross-project formal folders:

```powershell
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode epsilon --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode grid --obj .\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode adaptive --obj .\obj\Bunny.obj --queries 500 --grid 16 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode threads --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 2000 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 3000 --threads 8 --seed 12345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

Neumann smoke and formal-style runs:

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 40 --grid 6 --threads 8 --seed 12345 --cube 0.22
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 20 --grid 5 --threads 8 --seed 22345 --cube 0.22
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

Neumann smoke rows were filtered out of the shared benchmark CSV before plotting:

```powershell
$rows = Import-Csv results\benchmark_summary.csv; $filtered = $rows | Where-Object { if ($_.benchmark_name -like 'neumann*') { ($_.benchmark_name -eq 'neumann_mixed_grid' -and $_.num_query_points -eq '512') -or ($_.benchmark_name -ne 'neumann_mixed_grid' -and $_.num_query_points -eq '100') } else { $true } }; $filtered | Export-Csv results\benchmark_summary.csv -NoTypeInformation
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

## 9. Fresh Formal WoSt Runs

WoSt Dirichlet formal run:

```powershell
Set-Location experiments\formal_wost_dirichlet
..\..\build\Release\wost.exe --mode convergence --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode epsilon --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode grid --obj ..\..\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode geometry --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
Set-Location ..\..
```

WoSt Neumann formal run:

```powershell
Set-Location experiments\formal_wost_neumann
..\..\build\Release\wost.exe --mode neumann --obj ..\..\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
Set-Location ..\..
```

## 10. Fresh Formal Zombie Runs

Zombie Dirichlet formal run:

```powershell
C:\THU\homework\zombie\.venv\Scripts\python.exe C:\THU\homework\zombie\scripts\zombie_bunny_baseline.py --mode all --obj C:\THU\homework\zombie\obj\Bunny.obj --out experiments\formal_zombie_dirichlet --reference-results C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_dirichlet\results --queries 500 --geometry-queries 500 --grid 16 --seed 12345 --cube 0.22 --max-steps 512
```

Zombie Neumann formal run:

```powershell
C:\THU\homework\zombie\.venv\Scripts\python.exe C:\THU\homework\zombie\scripts\zombie_neumann_bunny_baseline.py --mode all --obj C:\THU\homework\zombie\obj\Bunny.obj --out experiments\formal_zombie_neumann --reference-results C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_neumann\results --queries 100 --grid 8 --seed 32345 --cube 0.22 --max-steps 2048
```

## 11. Report and Figure Integration

The integrated report used these source files:

```powershell
Get-Content C:\THU\homework\zombie\results_zombie_final_report\ZOMBIE_VS_WOST_FINAL_REPORT.md
Get-Content experiments\optimization_report.md
Get-Content experiments\formal_comparison_report.md
```

Figures were collected into one folder:

```powershell
New-Item -ItemType Directory -Force experiments\final_report_figures
Copy-Item experiments\formal_zombie_dirichlet\rmse_vs_walks_comparison.png experiments\final_report_figures\formal_dirichlet_rmse_vs_walks_comparison.png
Copy-Item experiments\formal_zombie_dirichlet\epsilon_tradeoff_comparison.png experiments\final_report_figures\formal_dirichlet_epsilon_tradeoff_comparison.png
Copy-Item experiments\formal_zombie_neumann\neumann_rmse_vs_walks_comparison.png experiments\final_report_figures\formal_neumann_rmse_vs_walks_comparison.png
Copy-Item experiments\formal_zombie_neumann\neumann_epsilon_tradeoff_comparison.png experiments\final_report_figures\formal_neumann_epsilon_tradeoff_comparison.png
Copy-Item experiments\figures\*.png experiments\final_report_figures\
```

Historical figures from the Zombie final report were also copied into `experiments\final_report_figures\` with `historical_...` file names.

Report checks:

```powershell
Select-String -Path experiments\final_integrated_report.md -Pattern "!\[|final_report_figures|optimization_"
```

## 12. Poster Editing and Verification

The poster file was read-only, so the read-only flag was removed before editing:

```powershell
Set-ItemProperty -Path poster.tex -Name IsReadOnly -Value $false
```

Text-level checks after adding the `Experimental Results & Conclusions` section:

```powershell
Select-String -Path poster.tex -Pattern "Experimental Results|includegraphics|end{document}"
```

Compilation was attempted but failed because `pdflatex` was not installed or not on `PATH`:

```powershell
pdflatex poster.tex
```

## 13. Current Command-Documentation Pass

Commands used while preparing these command-reference documents:

```powershell
rg -n "wost\.exe|python|powershell|\.ps1|--mode|convergence|epsilon|grid|geometry|adaptive|antithetic|lazy|neumann|zombie|command|命令|run" experiments README.md docs main.cpp scripts -S
Get-ChildItem -Path experiments -Recurse -File | Select-Object FullName
Get-ChildItem -Path . -File | Select-Object FullName
Get-Content -Path docs\SESSION_COMMAND_LOG.md -TotalCount 220
Get-Content -Path docs\RESULTS_COMMAND_MAPPING.md -TotalCount 260
Get-Content -Path experiments\formal_comparison_report.md -TotalCount 260
Get-Content -Path experiments\optimization_report.md -TotalCount 260
Get-Content -Path experiments\final_integrated_report.md -TotalCount 220
Get-Content -Path scripts\run_optimization_experiments.ps1
Get-Content -Path experiments\formal_zombie_dirichlet\README.md -TotalCount 200
Get-Content -Path experiments\formal_zombie_neumann\ZOMBIE_VS_WOST_NEUMANN_COMPARISON.md -TotalCount 180
```

