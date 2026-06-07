# WoSt Final Project

This repository contains a reproduced and extended Walk-on-Stars (WoSt) solver for a physical simulation course project. The final report focuses on this question:

```text
How does Walk-on-Stars behave under mixed Neumann boundary conditions,
and how are its errors affected by boundary proximity, epsilon, and mesh geometry?
```

The current final story is:

- Dirichlet benchmarks validate the basic Monte Carlo pipeline.
- Mixed Neumann boundary conditions expose geometry-sensitive behavior.
- Boundary proximity and epsilon explain a large part of the observed error.
- Distance-controlled bins show that Spot remains harder than Bunny in matched bins 1-3, but the gap shrinks with distance.
- Adaptive sampling, antithetic sampling, lazy refinement, BVH acceleration, and live tracing are diagnostic/engineering tools, not general accuracy guarantees.

## Repository Map

Important entry points:

```text
WoSt.py                         2D Python teaching demo
main.cpp                        C++ WoSt experiment driver
src/                            C++ solver and geometry backend
obj/Bunny.obj                   Bunny mesh
spot/spot_triangulated.obj      Spot mesh
scripts/                        plotting, rerun, and analysis scripts
docs/                           older workflow and audit notes
reports/FINAL_COURSE_REPORT.md  final course report
reports/POSTER_RESULTS_SECTION.md
reports/LIVE_DEMO_INSTRUCTIONS.md
reports/final_assets/           selected final-report figures and tables
```

Key experiment outputs:

```text
experiments/rerun_cross_mesh_20260606/
experiments/geometry_sensitive_analysis_20260606/
experiments/controlled_geometry_experiments_20260606/
```

## Environment Setup

The project is developed on Windows with PowerShell.

### Python Requirements

Required Python packages are listed in:

```text
requirements.txt
```

Current requirements:

```text
numpy
matplotlib
```

Create or refresh the virtual environment:

```powershell
.\setup_env.ps1
```

Manual equivalent:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Check that Python is ready:

```powershell
Test-Path .\.venv\Scripts\python.exe
```

### C++ Requirements

Required tools:

- Visual Studio Build Tools 2022
- MSVC C++ compiler tools
- CMake

Build the C++ solver:

```powershell
.\build_cpp.ps1
```

The build script locates Visual Studio through `vswhere`, enters the Visual Studio developer environment, configures CMake, and builds Release mode.

Expected executable:

```text
build/Release/wost.exe
```

Check that the solver exists:

```powershell
Test-Path .\build\Release\wost.exe
```

If the build script reports missing `cl` or `cmake`, install the C++ workload/components for Visual Studio Build Tools first.

## Quick Start

### 1. Run the 2D Teaching Demo

This is a lightweight demo for explaining Walk-on-Stars intuition. It is not the final 3D experiment.

```powershell
.\setup_env.ps1
.\run_python.ps1
```

Manual command:

```powershell
.\.venv\Scripts\python.exe .\WoSt.py --resolution 40 --walks 200
```

### 2. Build the C++ Solver

```powershell
.\build_cpp.ps1
```

### 3. Run a Small C++ Live Trace

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64
```

This writes:

```text
results/live_trace.csv
results/live_demo_summary.csv
results/live_trace_plot.png
results/live_trace_walks.gif
```

For a 3D trace view instead of the default x-y projection:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64 --view 3d
```

This writes:

```text
results/live_trace_plot_3d.png
results/live_trace_walks_3d.gif
results/live_trace_interactive_3d.html
```

## Live Demo for Poster Session

For poster presentation, do not rerun large experiments live. Use the precomputed figures and, only if needed, a small trace demo.

Detailed instructions are in:

```text
reports/LIVE_DEMO_INSTRUCTIONS.md
```

Recommended live-demo order:

1. Show `reports/final_assets/fig1_dirichlet_rmse_vs_walks.png`.
2. Show `reports/final_assets/fig2_mixed_neumann_rmse_vs_walks.png`.
3. Show `reports/final_assets/fig6_matched_bin_abs_error_ci.png`.
4. Show `reports/final_assets/fig11_spot_live_trace.png`.
5. If motion helps, play `live_demo.gif`.

Best lightweight command:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64
```

This preset uses the Spot mesh, `cube=1.1`, and the report trace point `(0.8, 0.0, 0.2)`. It writes both a static plot and an animated GIF:

```text
results/live_trace_plot.png
results/live_trace_walks.gif
```

To generate both the original 2D projection and the 3D view:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64 --view both
```

The interactive 3D HTML includes the traced walks, the outer cube boundary, and the inner OBJ mesh. It also has a play/pause timeline for watching the walks appear over time. Open:

```text
results/live_trace_interactive_3d.html
```

If you only want the static plot:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64 --no-gif
```

Other presets:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset dirichlet16
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset dirichlet256
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset antithetic64
```

2D animation backup:

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --animate
```

GIF backup:

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --animate --save live_demo.gif
```

Static backup:

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --save live_demo_poster.png --no-show
```

Live-demo caution:

- The 2D animation is for intuition only.
- The Spot live trace is qualitative diagnostic evidence only.
- Do not present a live trace as standalone causality evidence.
- Do not claim WoSt is consistently more accurate than Zombie.

## C++ Benchmark Modes

The C++ driver solves a manufactured Laplace benchmark:

```text
Omega = outer AABB cube - inner triangle mesh
u(x,y,z) = x + y + z
Delta u = 0
```

For Dirichlet validation, both the inner mesh and the outer cube use the exact Dirichlet value. For mixed Neumann experiments, the outer cube remains Dirichlet and the inner mesh uses normal derivative data.

Common executable path:

```powershell
$Wost = ".\build\Release\wost.exe"
```

Useful options:

```text
--obj ./spot/spot_triangulated.obj
--obj ./obj/Bunny.obj
--queries 500
--grid 16
--threads 8
--seed 12345
--cube 1.1
--epsilon 1e-4
--walks 256
--boundary dirichlet
--boundary neumann
```

### Lightweight Individual Runs

Dirichlet convergence:

```powershell
.\build\Release\wost.exe --mode convergence --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
```

Dirichlet epsilon sweep:

```powershell
.\build\Release\wost.exe --mode epsilon --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
```

Mixed Neumann:

```powershell
.\build\Release\wost.exe --mode neumann --obj .\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
```

Geometry backend benchmark:

```powershell
.\build\Release\wost.exe --mode geometry --obj .\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
```

Plot benchmark outputs:

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_benchmarks.py
```

Typical output directory:

```text
results/
```

Typical generated plots:

```text
results/rmse_vs_walks.png
results/epsilon_tradeoff.png
results/adaptive_vs_fixed.png
results/neumann_rmse_vs_walks.png
results/neumann_epsilon_tradeoff.png
results/thread_speedup.png
results/bvh_vs_bruteforce.png
```

## Diagnostic and Optimization Modes

These modes support the final report's diagnostic story. They should be interpreted as tools for understanding variance, runtime, and path behavior, not as general accuracy fixes.

### Walk Path Debugger

Records a small number of random-walk paths at one query point.

```powershell
.\build\Release\wost.exe --mode demo_point --obj .\obj\Bunny.obj --cube 0.22 --boundary neumann --point 0.05 0.02 0.08 --walks 64 --trace-walks 8 --epsilon 1e-4 --seed 12345 --trace-out results\live_trace.csv --summary-out results\live_demo_summary.csv

.\.venv\Scripts\python.exe .\scripts\plot_live_trace.py --trace results\live_trace.csv --summary results\live_demo_summary.csv --out results\live_trace_plot.png
```

Generate a 3D static plot and 3D animated GIF from the same trace:

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_live_trace.py --trace results\live_trace.csv --summary results\live_demo_summary.csv --skip-2d --out-3d results\live_trace_plot_3d.png --gif-3d results\live_trace_walks_3d.gif
```

Generate an interactive 3D HTML viewer with the inner mesh and outer cube:

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_live_trace.py --trace results\live_trace.csv --summary results\live_demo_summary.csv --skip-2d --html-3d results\live_trace_interactive_3d.html --mesh-obj spot\spot_triangulated.obj --cube 1.1
```

Outputs:

```text
results/live_trace.csv
results/live_demo_summary.csv
results/live_trace_plot.png
results/live_trace_walks.gif
results/live_trace_plot_3d.png
results/live_trace_walks_3d.gif
results/live_trace_interactive_3d.html
```

### Boundary-Bias Indicator

Compares `u_epsilon(x)` with `u_epsilon/2(x)`. This is an epsilon sensitivity indicator, not an exact bias decomposition.

```powershell
.\build\Release\wost.exe --mode bias_detector --obj .\obj\Bunny.obj --cube 0.22 --boundary neumann --epsilon 1e-3 --walks 256 --grid 32 --threads 8 --out results\boundary_bias_detector.vtk --csv results\boundary_bias_summary.csv

.\.venv\Scripts\python.exe .\scripts\plot_boundary_bias.py --vtk results\boundary_bias_detector.vtk --summary results\boundary_bias_summary.csv --out results\boundary_bias_detector.png
```

Outputs:

```text
results/boundary_bias_detector.vtk
results/boundary_bias_summary.csv
results/boundary_bias_detector.png
```

### Variance-Predicted Adaptive Sampling

Uses pilot samples to estimate pointwise variance and predicts the number of samples needed for a target standard error:

```text
M_i = ceil(variance_i / target_std_error^2)
```

The predicted count is clamped between `--min-samples` and `--max-samples`.

```powershell
.\build\Release\wost.exe --mode variance_adaptive --obj .\obj\Bunny.obj --cube 0.22 --boundary dirichlet --queries 500 --epsilon 1e-4 --pilot-samples 32 --min-samples 32 --max-samples 1024 --target-std-error 0.005 --threads 8 --out results\variance_adaptive_points.csv --summary-out results\variance_adaptive_summary.csv --csv results\variance_adaptive_comparison.csv

.\.venv\Scripts\python.exe .\scripts\plot_variance_adaptive.py --comparison results\variance_adaptive_comparison.csv --points results\variance_adaptive_points.csv --tradeoff-out results\variance_adaptive_tradeoff.png --samples-out results\variance_adaptive_samples_map.png
```

Outputs:

```text
results/variance_adaptive_points.csv
results/variance_adaptive_summary.csv
results/variance_adaptive_comparison.csv
results/variance_adaptive_tradeoff.png
results/variance_adaptive_samples_map.png
```

### Optimization Batch

Runs adaptive, antithetic, lazy refinement, epsilon extrapolation, and Neumann sanity diagnostics.

```powershell
.\build\Release\wost.exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001

.\.venv\Scripts\python.exe .\scripts\plot_optimization_experiments.py
```

or:

```powershell
.\scripts\run_optimization_experiments.ps1
```

Outputs:

```text
experiments/optimization_summary.csv
experiments/optimization_points.csv
experiments/optimization_report.md
experiments/figures/
```

## Reproducing the Report Experiments

The repository already contains final experiment outputs. Rerunning the full stack can take time, and the Zombie comparisons require a separate Zombie checkout.

If you only need to read or present the project, use the existing outputs under `experiments/` and `reports/`. If you rerun experiments, prefer a new output directory so the checked report evidence remains easy to compare.

### Cross-Mesh Rerun

Requires:

```text
C:\THU\homework\zombie
C:\THU\homework\zombie\.venv\Scripts\python.exe
```

Full Bunny/Spot WoSt + Zombie rerun:

```powershell
.\scripts\run_cross_mesh_rerun_20260606.ps1
```

WoSt-only rerun:

```powershell
.\scripts\run_cross_mesh_rerun_20260606.ps1 -SkipZombie
```

Output:

```text
experiments/rerun_cross_mesh_20260606/
```

Main report inside that directory:

```text
experiments/rerun_cross_mesh_20260606/RERUN_SUMMARY.md
```

### Geometry-Sensitive Analysis

Run from existing rerun outputs:

```powershell
.\.venv\Scripts\python.exe .\scripts\analyze_geometry_sensitive_rerun.py
```

Output:

```text
experiments/geometry_sensitive_analysis_20260606/
```

Main report:

```text
experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md
```

### Controlled Geometry Experiments

Part-1 matched distance-bin run:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_controlled_geometry_experiments.py --output experiments/controlled_geometry_part1_20260606 --epsilons 1e-4 --walks 256
```

Full controlled experiment:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_controlled_geometry_experiments.py --output experiments/controlled_geometry_experiments_20260606
```

Summarize controlled outputs:

```powershell
.\.venv\Scripts\python.exe .\scripts\summarize_controlled_geometry_results.py --output experiments/controlled_geometry_experiments_20260606
```

Important outputs:

```text
experiments/controlled_geometry_experiments_20260606/distance_controlled_neumann.csv
experiments/controlled_geometry_experiments_20260606/distance_controlled_bias.csv
experiments/controlled_geometry_experiments_20260606/epsilon_distance_sweep.csv
experiments/controlled_geometry_experiments_20260606/CONTROLLED_GEOMETRY_REPORT.md
experiments/controlled_geometry_experiments_20260606/POSTER_READY_SUMMARY.md
```

## Final Report and Poster Assets

Final report:

```text
reports/FINAL_COURSE_REPORT.md
```

Poster summary:

```text
reports/POSTER_RESULTS_SECTION.md
```

Live demo instructions:

```text
reports/LIVE_DEMO_INSTRUCTIONS.md
```

Provenance:

```text
reports/final_report_provenance.md
```

Final selected figures and derived tables:

```text
reports/final_assets/
```

Regenerate final report assets from existing outputs:

```powershell
.\.venv\Scripts\python.exe .\scripts\final_report\build_final_course_report.py
```

This script does not rerun solver experiments. It reads existing CSVs and reports, copies selected figures, recomputes small aggregate tables, and writes:

```text
reports/FINAL_COURSE_REPORT.md
reports/POSTER_RESULTS_SECTION.md
reports/final_report_provenance.md
reports/final_report_quality_checks.txt
reports/final_assets/
```

## Presentation Assets

Precomputed assets:

```text
presentation_figure.png
live_demo.gif
live_demo_poster.png
```

Generate presentation assets from the real C++ testcase:

```powershell
.\generate_real_presentation_assets.ps1
```

This script builds the C++ solver, runs the current `main.cpp` testcase, and generates:

```text
test1_manufactured_pointcloud.vtk
test1_manufactured_slice_xy.vtk
presentation_figure.png
live_demo.gif
live_demo_poster.png
```

This can take several minutes. For a poster session, prefer the precomputed figures unless you are preparing offline.

## ParaView Outputs

Some modes write VTK files for visual inspection:

```text
results/linear_dirichlet_grid.vtk
results/adaptive_sampling_grid.vtk
results/boundary_bias_detector.vtk
```

Open them in ParaView and color by:

- `solution`
- `std_error`
- `mean_steps`
- `samples_used`
- `exact`
- `abs_error`
- `is_valid`
- `bias_indicator` when available

## Notes on Interpretation

- Use "nearest-distance proxy" rather than "exact signed distance" unless an exact signed-distance computation is added.
- Use "boundary-bias indicator" or "epsilon sensitivity indicator" for epsilon-vs-half-epsilon differences.
- Treat matched-bin ratios as descriptive unless repeated-seed confidence intervals are added.
- Do not claim WoSt is consistently more accurate than Zombie.
- Live traces are qualitative diagnostics, not standalone mechanism evidence.

## Further Documentation

```text
docs/BUNNY_BENCHMARK_WORKFLOW.md
docs/NEUMANN_BENCHMARK_REPORT.md
docs/EXPERIMENT_PIPELINE_AUDIT.md
docs/REPOSITORY_ORGANIZATION.md
reports/FINAL_COURSE_REPORT.md
reports/LIVE_DEMO_INSTRUCTIONS.md
reports/final_report_provenance.md
```
