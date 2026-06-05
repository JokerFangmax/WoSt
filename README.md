# WoSt Final Project

This repository currently has two runnable entry points:

1. `WoSt.py`
   A lightweight Python demo of a 2D Walk-on-Stars Laplace solver.
2. `main.cpp`
   The full C++ project built with CMake.

## Python demo

Recommended on Windows:

```powershell
.\setup_env.ps1
.\run_python.ps1
```

The quick script uses a smaller default workload (`--resolution 40 --walks 200`) so the first run finishes much faster.

Manual commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\WoSt.py --resolution 40 --walks 200
```

## Real testcase visualization

If you want the presentation assets generated from the actual `main.cpp` testcase instead of the stand-in Python data, use:

```powershell
.\generate_real_presentation_assets.ps1
```

This script will:

- build the C++ solver with the Visual Studio toolchain
- run `main.cpp` to produce:
  - `test1_manufactured_pointcloud.vtk`
  - `test1_manufactured_slice_xy.vtk`
- generate:
  - `presentation_figure.png`
  - `live_demo.gif`
  - `live_demo_poster.png`

Requirements:

- Visual Studio Build Tools 2022
- MSVC C++ compiler tools (`cl.exe`)
- CMake
- a ready Python virtual environment at `.venv`

## C++ build

Windows prerequisites:

- Visual Studio Build Tools 2022
- MSVC C++ compiler tools (`cl.exe`)
- CMake

Build with:

```powershell
.\build_cpp.ps1
```

If `build_cpp.ps1` reports that `cl` or `cmake` is missing, install the C++ workload/components into your existing Visual Studio Build Tools installation first, then rerun the script.

After a successful build, the solver can also be run manually before generating the presentation figure:

```powershell
.\build\Release\wost.exe
.\.venv\Scripts\python.exe .\presentation_viz.py --slice test1_manufactured_slice_xy.vtk --pointcloud test1_manufactured_pointcloud.vtk --output presentation_figure.png
```

## Benchmarks & Results

The C++ executable now runs a clean Dirichlet-only Laplace benchmark on

```text
Omega = outer AABB cube - inner triangle mesh
u(x,y,z) = x + y + z
Delta u = 0
```

Both the inner mesh boundary and outer cube boundary use the same exact Dirichlet value, and the Neumann predicate is disabled. This is the primary accuracy benchmark because the analytic solution is unambiguous.

Build:

```powershell
mkdir build
cd build
cmake ..
cmake --build . -j
cd ..
```

Run all benchmarks from the project root:

```powershell
.\build\wost.exe --mode all --queries 20000 --grid 48 --threads 8
```

With Visual Studio multi-config builds, the executable may be under `build\Release`:

```powershell
.\build\Release\wost.exe --mode all --queries 20000 --grid 48 --threads 8
```

Run individual benchmark modes:

```powershell
.\build\wost.exe --mode convergence --queries 20000 --threads 8
.\build\wost.exe --mode epsilon --queries 20000 --threads 8
.\build\wost.exe --mode grid --grid 48 --threads 8
.\build\wost.exe --mode adaptive --queries 20000 --grid 48 --threads 8
.\build\wost.exe --mode neumann --queries 100 --grid 8 --threads 8 --cube 0.22
.\build\wost.exe --mode threads --queries 5000 --threads 8
.\build\wost.exe --mode geometry --queries 1000 --threads 8
```

Useful options:

```text
--obj ./spot/spot_triangulated.obj
--queries 20000
--grid 48
--threads 8
--seed 12345
--cube 1.0
```

Benchmark rows are appended to:

```text
results/benchmark_summary.csv
```

The CSV includes runtime, throughput, RMSE, MAE, max absolute error, mean standard error, mean walk steps, divergence count, and mean samples used.

Generate plots:

```powershell
python .\scripts\plot_benchmarks.py
```

This writes:

```text
results/rmse_vs_walks.png
results/epsilon_tradeoff.png
results/adaptive_vs_fixed.png
results/neumann_rmse_vs_walks.png
results/neumann_epsilon_tradeoff.png
results/thread_speedup.png
results/bvh_vs_bruteforce.png
```

The plotting script uses `pandas` if available, falls back to Python's `csv` module, and requires `matplotlib` for image output.

Structured VTK diagnostics are written for ParaView:

```text
results/linear_dirichlet_grid.vtk
results/adaptive_sampling_grid.vtk
```

Open these files in ParaView with `File > Open`, then color by one of the scalar fields:

- `solution`: Monte Carlo estimate.
- `std_error`: estimated standard error of the Monte Carlo mean.
- `mean_steps`: average walk length per query point.
- `samples_used`: actual random walks used at the point.
- `exact`: analytic value `x + y + z`.
- `abs_error`: absolute error against the analytic solution.
- `is_valid`: `1` inside the simulation domain, `0` outside.

The adaptive sampling benchmark is a small innovation over fixed sampling. Instead of assigning the same number of random walks to every point, the solver estimates standard error online and stops early in low-variance regions, up to the configured maximum sample count.

## Optimization experiments

The optimized C++ solver also has experiment modes for the project report:

```powershell
.\build\Release\wost.exe --mode adaptive_compare --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
.\build\Release\wost.exe --mode antithetic --queries 1000 --threads 8 --max-samples 512
.\build\Release\wost.exe --mode lazy --queries 1000 --threads 8 --max-samples 512
.\build\Release\wost.exe --mode epsilon_extrapolation --queries 1000 --threads 8 --max-samples 512
.\build\Release\wost.exe --mode neumann_sanity --queries 1000 --threads 8 --max-samples 512
```

Run the full batch and generate figures/report:

```powershell
.\build\Release\wost.exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
python .\scripts\plot_optimization_experiments.py
```

or, if script execution is enabled:

```powershell
.\scripts\run_optimization_experiments.ps1
```

Outputs are written to:

```text
experiments/optimization_summary.csv
experiments/optimization_points.csv
experiments/optimization_report.md
experiments/figures/
```

Common Random Numbers are used in these comparisons. Each repeated experiment has a global experiment seed, query points are generated from that seed, and each query point receives `SeedFor(experiment_seed, point_index, stream)`. Methods within the same comparison reuse the same experiment seed and point-index stream, so fixed/adaptive, normal/antithetic, full/lazy, and epsilon/epsilon-half comparisons are paired fairly.

For the high-resolution Bunny workflow, including the `obj/Bunny.obj` commands and expected outputs, see:

```text
docs/BUNNY_BENCHMARK_WORKFLOW.md
```

For the mixed Neumann boundary benchmark and results, see:

```text
docs/NEUMANN_BENCHMARK_REPORT.md
```

## Final Live Demo and Innovation Features

The final project contribution is not only reproducing the base Walk-on-Stars estimator. We reposition the C++ implementation as:

```text
A Self-Diagnostic and Optimization-Aware Walk-on-Stars Solver for Complex Mesh Domains
```

The new demo and diagnostic modes make the solver easier to explain, debug, and tune on complex meshes.

### 1. Walk Path Debugger

`demo_point` solves the analytic benchmark at one query point and records a small number of random-walk paths. The trace shows sphere steps, boundary hits, and Neumann reflections when mixed-boundary mode is enabled.

```powershell
.\build\Release\wost.exe --mode demo_point --obj .\obj\Bunny.obj --cube 0.22 --point 0.05 0.02 0.08 --walks 64 --epsilon 1e-4 --seed 12345 --trace-out results\live_trace.csv --summary-out results\live_demo_summary.csv

.\.venv\Scripts\python.exe .\scripts\plot_live_trace.py --trace results\live_trace.csv --summary results\live_demo_summary.csv --out results\live_trace_plot.png
```

Useful optional flags:

```powershell
--boundary dirichlet
--boundary neumann
--trace-walks 8
--antithetic
```

Outputs:

```text
results/live_trace.csv
results/live_demo_summary.csv
results/live_trace_plot.png
```

### 2. Boundary Bias Detector

`bias_detector` compares `u_epsilon(x)` with `u_epsilon/2(x)` on a grid. Large pointwise differences indicate that the boundary approximation may be too coarse at that location.

```powershell
.\build\Release\wost.exe --mode bias_detector --obj .\obj\Bunny.obj --cube 0.22 --epsilon 1e-3 --walks 256 --grid 32 --threads 8 --out results\boundary_bias_detector.vtk --csv results\boundary_bias_summary.csv

.\.venv\Scripts\python.exe .\scripts\plot_boundary_bias.py --vtk results\boundary_bias_detector.vtk --summary results\boundary_bias_summary.csv --out results\boundary_bias_detector.png
```

The VTK file contains:

```text
solution_epsilon
solution_epsilon_half
bias_indicator
normalized_bias
std_error_epsilon
std_error_epsilon_half
mean_steps_epsilon
mean_steps_epsilon_half
exact
abs_error_epsilon
abs_error_epsilon_half
is_valid
```

Outputs:

```text
results/boundary_bias_detector.vtk
results/boundary_bias_summary.csv
results/boundary_bias_detector.png
```

### 3. Variance-Predicted Adaptive Sampling

`variance_adaptive` uses a two-stage strategy. A pilot stage estimates sample variance at each query point, then the solver predicts the number of walks needed to reach a target standard error:

```text
M_i = ceil(variance_i / target_std_error^2)
```

The predicted count is clamped between `--min-samples` and `--max-samples`. The mode compares fixed baselines against several target standard-error values.

```powershell
.\build\Release\wost.exe --mode variance_adaptive --obj .\obj\Bunny.obj --cube 0.22 --queries 500 --epsilon 1e-4 --pilot-samples 32 --min-samples 32 --max-samples 1024 --target-std-error 0.005 --threads 8 --out results\variance_adaptive_points.csv

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

For a compact live-demo wrapper:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset dirichlet16
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset dirichlet256
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset antithetic64
```
