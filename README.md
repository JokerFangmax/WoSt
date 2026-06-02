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
