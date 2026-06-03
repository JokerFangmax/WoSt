# Report Results to Command Sources, 2026-06

This document maps the reported experiment results to the commands that generated them. It is intended for reproducing the tables and figures in:

- `experiments/optimization_report.md`
- `experiments/formal_comparison_report.md`
- `experiments/final_integrated_report.md`
- the `Experimental Results & Conclusions` section in `poster.tex`

All commands should be run from `C:\THU\projects\WoSt_Final_project-1` unless a `Set-Location` command is shown.

## 1. Build Used by All WoSt Results

```powershell
powershell -ExecutionPolicy Bypass -File .\build_cpp.ps1
```

Executable:

```text
build\Release\wost.exe
```

## 2. WoSt Optimization Report

Report:

```text
experiments/optimization_report.md
```

CSV sources:

```text
experiments/optimization_summary.csv
experiments/optimization_points.csv
experiments/neumann_normal_diagnostics.csv
```

Figure folder:

```text
experiments/figures/
```

Generation command:

```powershell
.\build\Release\wost.exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
.\.venv\Scripts\python.exe .\scripts\plot_optimization_experiments.py
```

Equivalent convenience command:

```powershell
.\scripts\run_optimization_experiments.ps1
```

### 2.1 Adaptive Sampling Results

Reported in:

```text
experiments/optimization_report.md
poster.tex
experiments/final_integrated_report.md
```

CSV rows:

```text
experiment = adaptive_compare
method = fixed
method = old_absolute_stderr
method = relative_stderr
```

Figures:

```text
experiments/figures/adaptive_rmse_errorbars.png
experiments/figures/adaptive_samples_errorbars.png
experiments/final_report_figures/optimization_adaptive_rmse_errorbars.png
experiments/final_report_figures/optimization_adaptive_samples_errorbars.png
```

### 2.2 Antithetic Sampling Results

CSV rows:

```text
experiment = antithetic_compare
method = normal
method = antithetic
```

Figures:

```text
experiments/figures/antithetic_rmse_errorbars.png
experiments/figures/antithetic_variance_errorbars.png
experiments/figures/antithetic_pointwise_variance.png
experiments/final_report_figures/optimization_antithetic_rmse_errorbars.png
experiments/final_report_figures/optimization_antithetic_variance_errorbars.png
experiments/final_report_figures/optimization_antithetic_pointwise_variance.png
```

### 2.3 Lazy Star-Radius Refinement Results

CSV rows:

```text
experiment = lazy_refinement
method = full_exact
method = lazy_threshold_x1
method = lazy_threshold_x4
method = lazy_threshold_x16
```

Figures:

```text
experiments/figures/lazy_refinement_ratio_errorbars.png
experiments/figures/lazy_refinement_spatial_xy.png
experiments/figures/lazy_rmse_errorbars.png
experiments/figures/lazy_tradeoff_rmse_vs_refinement.png
experiments/final_report_figures/optimization_lazy_refinement_ratio_errorbars.png
experiments/final_report_figures/optimization_lazy_refinement_spatial_xy.png
experiments/final_report_figures/optimization_lazy_tradeoff_rmse_vs_refinement.png
```

### 2.4 Epsilon Extrapolation Results

CSV rows:

```text
experiment = epsilon_extrapolation
method = epsilon
method = epsilon_half
```

Figures:

```text
experiments/figures/epsilon_rmse_errorbars.png
experiments/figures/epsilon_sensitivity_histogram.png
experiments/figures/epsilon_sensitivity_spatial_xy.png
experiments/final_report_figures/optimization_epsilon_rmse_errorbars.png
experiments/final_report_figures/optimization_epsilon_sensitivity_histogram.png
experiments/final_report_figures/optimization_epsilon_sensitivity_spatial_xy.png
```

### 2.5 Neumann Normal Convention Sanity Test

CSV rows:

```text
experiment = neumann_sanity
method = sphere_cube
```

Diagnostic source:

```text
experiments/neumann_normal_diagnostics.csv
experiments/generated/inner_sphere.obj
```

Figures:

```text
experiments/figures/neumann_normal_diagnostics.png
experiments/figures/neumann_sanity_rmse_errorbars.png
experiments/final_report_figures/optimization_neumann_normal_diagnostics.png
experiments/final_report_figures/optimization_neumann_sanity_rmse_errorbars.png
```

## 3. Fresh Formal WoSt Dirichlet Results

Report:

```text
experiments/formal_comparison_report.md
```

Output folder:

```text
experiments/formal_wost_dirichlet/results/
```

Commands:

```powershell
Set-Location experiments\formal_wost_dirichlet
..\..\build\Release\wost.exe --mode convergence --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode epsilon --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode grid --obj ..\..\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode geometry --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
Set-Location ..\..
```

CSV sources:

```text
experiments/formal_wost_dirichlet/results/benchmark_summary.csv
experiments/formal_wost_dirichlet/results/geometry_benchmark.csv
```

VTK sources:

```text
experiments/formal_wost_dirichlet/results/linear_dirichlet_pointcloud.vtk
experiments/formal_wost_dirichlet/results/linear_dirichlet_grid.vtk
```

Used for:

- Dirichlet convergence WoSt RMSE/time rows.
- Dirichlet epsilon sweep WoSt RMSE/time rows.
- Dirichlet grid WoSt RMSE/time row.
- WoSt geometry `tiny_bvh` and brute-force rows.

## 4. Fresh Formal Zombie Dirichlet Results

Output folder:

```text
experiments/formal_zombie_dirichlet/
```

Command:

```powershell
C:\THU\homework\zombie\.venv\Scripts\python.exe C:\THU\homework\zombie\scripts\zombie_bunny_baseline.py --mode all --obj C:\THU\homework\zombie\obj\Bunny.obj --out experiments\formal_zombie_dirichlet --reference-results C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_dirichlet\results --queries 500 --geometry-queries 500 --grid 16 --seed 12345 --cube 0.22 --max-steps 512
```

CSV sources:

```text
experiments/formal_zombie_dirichlet/benchmark_summary.csv
experiments/formal_zombie_dirichlet/geometry_benchmark.csv
experiments/formal_zombie_dirichlet/zombie_vs_wost_summary.csv
```

Figures:

```text
experiments/formal_zombie_dirichlet/rmse_vs_walks_comparison.png
experiments/formal_zombie_dirichlet/epsilon_tradeoff_comparison.png
experiments/final_report_figures/formal_dirichlet_rmse_vs_walks_comparison.png
experiments/final_report_figures/formal_dirichlet_epsilon_tradeoff_comparison.png
```

Used for:

- Formal Dirichlet convergence comparison table and figure.
- Formal Dirichlet epsilon sweep comparison table and figure.
- Formal Dirichlet grid table.
- Zombie FCPW geometry-query row.

## 5. Fresh Formal WoSt Neumann Results

Output folder:

```text
experiments/formal_wost_neumann/results/
```

Command:

```powershell
Set-Location experiments\formal_wost_neumann
..\..\build\Release\wost.exe --mode neumann --obj ..\..\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
Set-Location ..\..
```

CSV source:

```text
experiments/formal_wost_neumann/results/benchmark_summary.csv
```

VTK sources:

```text
experiments/formal_wost_neumann/results/neumann_mixed_pointcloud.vtk
experiments/formal_wost_neumann/results/neumann_mixed_grid.vtk
```

Used for:

- Mixed Neumann convergence WoSt RMSE/time/mean-steps rows.
- Mixed Neumann epsilon sweep WoSt RMSE/time/mean-steps rows.
- Mixed Neumann grid WoSt RMSE/time/mean-steps row.

## 6. Fresh Formal Zombie Neumann Results

Output folder:

```text
experiments/formal_zombie_neumann/
```

Command:

```powershell
C:\THU\homework\zombie\.venv\Scripts\python.exe C:\THU\homework\zombie\scripts\zombie_neumann_bunny_baseline.py --mode all --obj C:\THU\homework\zombie\obj\Bunny.obj --out experiments\formal_zombie_neumann --reference-results C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_neumann\results --queries 100 --grid 8 --seed 32345 --cube 0.22 --max-steps 2048
```

CSV sources:

```text
experiments/formal_zombie_neumann/benchmark_summary.csv
experiments/formal_zombie_neumann/zombie_vs_wost_neumann_summary.csv
```

Figures:

```text
experiments/formal_zombie_neumann/neumann_rmse_vs_walks_comparison.png
experiments/formal_zombie_neumann/neumann_epsilon_tradeoff_comparison.png
experiments/final_report_figures/formal_neumann_rmse_vs_walks_comparison.png
experiments/final_report_figures/formal_neumann_epsilon_tradeoff_comparison.png
```

Used for:

- Mixed Neumann convergence comparison table and figure.
- Mixed Neumann epsilon sweep comparison table and figure.
- Mixed Neumann grid comparison table.

## 7. Final Integrated Report

Report:

```text
experiments/final_integrated_report.md
```

Primary sources:

```text
experiments/formal_comparison_report.md
experiments/optimization_report.md
C:\THU\homework\zombie\results_zombie_final_report\ZOMBIE_VS_WOST_FINAL_REPORT.md
```

Figure collection folder:

```text
experiments/final_report_figures/
```

Figure-copy commands:

```powershell
New-Item -ItemType Directory -Force experiments\final_report_figures
Copy-Item experiments\formal_zombie_dirichlet\rmse_vs_walks_comparison.png experiments\final_report_figures\formal_dirichlet_rmse_vs_walks_comparison.png
Copy-Item experiments\formal_zombie_dirichlet\epsilon_tradeoff_comparison.png experiments\final_report_figures\formal_dirichlet_epsilon_tradeoff_comparison.png
Copy-Item experiments\formal_zombie_neumann\neumann_rmse_vs_walks_comparison.png experiments\final_report_figures\formal_neumann_rmse_vs_walks_comparison.png
Copy-Item experiments\formal_zombie_neumann\neumann_epsilon_tradeoff_comparison.png experiments\final_report_figures\formal_neumann_epsilon_tradeoff_comparison.png
Copy-Item experiments\figures\*.png experiments\final_report_figures\
```

Historical figure sources used as supporting visuals:

```text
C:\THU\homework\zombie\results_zombie_baseline\
C:\THU\homework\zombie\results_zombie_neumann_baseline\
```

These were copied into:

```text
experiments/final_report_figures/historical_*.png
```

## 8. Poster Experimental Results Section

Poster source:

```text
poster.tex
```

The poster section uses the same tables and figures as:

```text
experiments/final_integrated_report.md
```

Relevant figure paths embedded in `poster.tex`:

```text
experiments/final_report_figures/formal_dirichlet_rmse_vs_walks_comparison.png
experiments/final_report_figures/formal_neumann_rmse_vs_walks_comparison.png
experiments/final_report_figures/formal_neumann_epsilon_tradeoff_comparison.png
experiments/final_report_figures/historical_wost_bvh_vs_bruteforce.png
experiments/final_report_figures/optimization_adaptive_samples_errorbars.png
experiments/final_report_figures/optimization_antithetic_variance_errorbars.png
experiments/final_report_figures/optimization_lazy_tradeoff_rmse_vs_refinement.png
experiments/final_report_figures/optimization_neumann_normal_diagnostics.png
```

Verification command used:

```powershell
Select-String -Path poster.tex -Pattern "Experimental Results|includegraphics|end{document}"
```

Compilation was attempted with:

```powershell
pdflatex poster.tex
```

Result:

```text
pdflatex was not available on PATH in this environment, so only text-level verification was completed.
```

