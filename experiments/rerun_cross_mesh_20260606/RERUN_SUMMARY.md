# Cross-Mesh Experiment Rerun Summary, 2026-06-06

This directory contains a fresh rerun of the experiments referenced by:

```text
experiments_obsolete/final_cross_mesh_report_20260603/final_cross_mesh_report.md
```

## How It Was Run

Top-level command:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_cross_mesh_rerun_20260606.ps1
```

Full command log:

```text
experiments/rerun_cross_mesh_20260606/command_log.txt
```

After the main rerun completed, diagnostic plots were generated with:

```powershell
.\.venv\Scripts\python.exe .\scripts\plot_boundary_bias.py ...
.\.venv\Scripts\python.exe .\scripts\plot_variance_adaptive.py ...
.\.venv\Scripts\python.exe .\scripts\plot_live_trace.py ...
```

The rerun script has also been updated so future executions of the top-level command generate these diagnostic plots automatically.

The rerun used:

- WoSt project: `C:\THU\projects\WoSt_Final_project-1`
- Zombie baseline project: `C:\THU\homework\zombie`
- WoSt executable: `build\Release\wost.exe`
- Zombie Python: `C:\THU\homework\zombie\.venv\Scripts\python.exe`

## Output Layout

```text
experiments/rerun_cross_mesh_20260606/
  wost_bunny/
  wost_spot/
  zombie_bunny_dirichlet/
  zombie_bunny_neumann/
  zombie_spot_dirichlet/
  zombie_spot_neumann/
  command_log.txt
  RERUN_SUMMARY.md
```

## Visual Overview

This report is organized as figures first and tables second. The tables preserve exact values, while the figures make the cross-mesh trends easier to read.

| Question | Figure | Main reading |
|---|---|---|
| Does Dirichlet behave normally? | Bunny/Spot Dirichlet RMSE-vs-walks plots | WoSt and Zombie show the expected Monte Carlo convergence trend. |
| What changes under Mixed Neumann? | Bunny/Spot Neumann RMSE-vs-walks plots | Neumann convergence is less uniform and more mesh-sensitive. |
| How important is epsilon? | Bunny/Spot Neumann epsilon-tradeoff plots | Coarse epsilon can dominate Neumann error, especially on Spot. |
| Where does boundary bias appear? | Boundary-bias detector plots | Bias is spatially structured and stronger on Spot. |
| What do optimization diagnostics show? | Adaptive tradeoff/sample maps and live traces | These tools diagnose variance, sample allocation, and difficult path behavior rather than proving universal accuracy gains. |

WoSt main CSVs:

- `wost_bunny/results/benchmark_summary.csv`
- `wost_spot/results/benchmark_summary.csv`
- `wost_bunny/results/geometry_benchmark.csv`
- `wost_spot/results/geometry_benchmark.csv`

WoSt diagnostic CSVs:

- `wost_bunny/diagnostics/boundary_bias_summary.csv`
- `wost_spot/diagnostics/boundary_bias_summary.csv`
- `wost_bunny/diagnostics/variance_adaptive_comparison.csv`
- `wost_spot/diagnostics/variance_adaptive_comparison.csv`
- `wost_bunny/experiments/optimization_summary.csv`
- `wost_spot/experiments/optimization_summary.csv`
- `wost_bunny/diagnostics/live_trace.csv`
- `wost_spot/diagnostics/live_trace.csv`

WoSt diagnostic figures:

- `wost_bunny/diagnostics/boundary_bias_detector.png`
- `wost_spot/diagnostics/boundary_bias_detector.png`
- `wost_bunny/diagnostics/variance_adaptive_tradeoff.png`
- `wost_spot/diagnostics/variance_adaptive_tradeoff.png`
- `wost_bunny/diagnostics/variance_adaptive_samples_map.png`
- `wost_spot/diagnostics/variance_adaptive_samples_map.png`
- `wost_bunny/diagnostics/live_trace_plot.png`
- `wost_spot/diagnostics/live_trace_plot.png`

Zombie comparison CSVs:

- `zombie_bunny_dirichlet/zombie_vs_wost_summary.csv`
- `zombie_bunny_neumann/zombie_vs_wost_neumann_summary.csv`
- `zombie_spot_dirichlet/zombie_vs_wost_summary.csv`
- `zombie_spot_neumann/zombie_vs_wost_neumann_summary.csv`

## Main WoSt Results

### Dirichlet Convergence

![Bunny Dirichlet convergence](zombie_bunny_dirichlet/rmse_vs_walks_comparison.png)

**Figure.** Bunny Dirichlet results show normal Monte Carlo convergence and close agreement between WoSt and Zombie.

![Spot Dirichlet convergence](zombie_spot_dirichlet/rmse_vs_walks_comparison.png)

**Figure.** Spot Dirichlet results also converge normally, supporting the baseline validity of the rerun.

| Mesh | Walks | WoSt RMSE | Zombie RMSE | Zombie / WoSt |
|---|---:|---:|---:|---:|
| Bunny | 16 | 0.03042 | 0.03494 | 1.148 |
| Bunny | 64 | 0.01570 | 0.01750 | 1.115 |
| Bunny | 256 | 0.00778 | 0.00755 | 0.970 |
| Bunny | 1024 | 0.00399 | 0.00412 | 1.032 |
| Spot | 16 | 0.11582 | 0.12212 | 1.054 |
| Spot | 64 | 0.05978 | 0.06718 | 1.124 |
| Spot | 256 | 0.03078 | 0.03295 | 1.071 |
| Spot | 1024 | 0.01517 | 0.01418 | 0.934 |

### Mixed Neumann Convergence

![Bunny Mixed Neumann convergence](zombie_bunny_neumann/neumann_rmse_vs_walks_comparison.png)

**Figure.** Bunny Mixed Neumann convergence is less clean than Dirichlet convergence, showing the extra sensitivity introduced by reflection and Neumann boundary handling.

![Spot Mixed Neumann convergence](zombie_spot_neumann/neumann_rmse_vs_walks_comparison.png)

**Figure.** Spot Mixed Neumann remains much harder than Spot Dirichlet, motivating the later geometry-sensitive and distance-controlled analyses.

| Mesh | Walks | WoSt RMSE | Zombie RMSE | Zombie / WoSt | WoSt steps | Zombie steps |
|---|---:|---:|---:|---:|---:|---:|
| Bunny | 16 | 0.04140 | 0.03739 | 0.903 | 30.93 | 249.87 |
| Bunny | 64 | 0.02497 | 0.01931 | 0.773 | 33.52 | 246.84 |
| Bunny | 256 | 0.01308 | 0.01599 | 1.222 | 34.46 | 246.45 |
| Bunny | 1024 | 0.01141 | 0.01404 | 1.231 | 34.47 | 245.96 |
| Spot | 16 | 0.25217 | 0.70026 | 2.777 | 107.89 | 332.62 |
| Spot | 64 | 0.19335 | 0.27582 | 1.427 | 104.43 | 364.66 |
| Spot | 256 | 0.17442 | 0.14248 | 0.817 | 107.59 | 362.43 |
| Spot | 1024 | 0.16710 | 0.11072 | 0.663 | 106.16 | 368.60 |

### Mixed Neumann Epsilon Sweep at 256 Walks

![Bunny Mixed Neumann epsilon tradeoff](zombie_bunny_neumann/neumann_epsilon_tradeoff_comparison.png)

**Figure.** Bunny Neumann error is highly sensitive to coarse epsilon, with much larger RMSE at `1e-2`.

![Spot Mixed Neumann epsilon tradeoff](zombie_spot_neumann/neumann_epsilon_tradeoff_comparison.png)

**Figure.** Spot shows stronger absolute epsilon sensitivity, with coarse epsilon producing very large Neumann error.

| Mesh | Epsilon | WoSt RMSE | Zombie RMSE | Zombie / WoSt | WoSt steps | Zombie steps |
|---|---:|---:|---:|---:|---:|---:|
| Bunny | 1e-2 | 0.15294 | 0.02224 | 0.145 | 6.75 | 110.43 |
| Bunny | 1e-3 | 0.02676 | 0.01505 | 0.562 | 15.90 | 224.78 |
| Bunny | 1e-4 | 0.01249 | 0.01539 | 1.233 | 32.21 | 252.78 |
| Bunny | 1e-5 | 0.01398 | 0.01765 | 1.262 | 48.88 | 265.13 |
| Spot | 1e-2 | 0.62693 | 0.16639 | 0.265 | 11.71 | 353.28 |
| Spot | 1e-3 | 0.23421 | 0.17964 | 0.767 | 38.62 | 363.57 |
| Spot | 1e-4 | 0.18677 | 0.15186 | 0.813 | 102.31 | 366.48 |
| Spot | 1e-5 | 0.18768 | 0.20176 | 1.075 | 134.84 | 377.11 |

## Diagnostics

### Boundary Bias Detector

![Bunny boundary bias detector](wost_bunny/diagnostics/boundary_bias_detector.png)

**Figure.** Bunny boundary-bias detector shows spatially localized epsilon sensitivity at the diagnostic grid points.

![Spot boundary bias detector](wost_spot/diagnostics/boundary_bias_detector.png)

**Figure.** Spot has larger boundary-bias magnitude in the rerun, consistent with its harder Mixed Neumann behavior.

| Mesh | Grid | Walks | Epsilon | Mean bias | Max bias | RMSE eps | RMSE eps/2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Bunny | 16 | 128 | 1e-3 | 0.00942 | 0.19949 | 0.03247 | 0.02280 |
| Spot | 16 | 128 | 1e-3 | 0.04337 | 0.60245 | 0.19807 | 0.17550 |

### Variance-Predicted Adaptive Sampling

![Bunny variance-adaptive tradeoff](wost_bunny/diagnostics/variance_adaptive_tradeoff.png)

**Figure.** Bunny adaptive sampling shows the expected tradeoff between fewer samples and increasing error as the tolerance is relaxed.

![Spot variance-adaptive tradeoff](wost_spot/diagnostics/variance_adaptive_tradeoff.png)

**Figure.** Spot adaptive sampling remains close to the maximum sample count, reflecting higher or more persistent variance in the sampled query set.

![Bunny adaptive sample map](wost_bunny/diagnostics/variance_adaptive_samples_map.png)

**Figure.** Bunny sample allocation is spatially nonuniform, supporting the use of adaptive sampling as a variance diagnostic.

![Spot adaptive sample map](wost_spot/diagnostics/variance_adaptive_samples_map.png)

**Figure.** Spot requires high sample allocation over much of the tested region, matching the higher variance and harder Neumann/geometry-sensitive behavior.

| Mesh | Method | RMSE | Mean samples | Runtime |
|---|---|---:|---:|---:|
| Bunny | fixed_1024 | 0.00404 | 1024.00 | 53.39s |
| Bunny | tau=0.003 | 0.00442 | 794.80 | 46.61s |
| Bunny | tau=0.005 | 0.00543 | 562.48 | 33.62s |
| Bunny | tau=0.008 | 0.00880 | 263.78 | 16.78s |
| Spot | fixed_1024 | 0.01473 | 1024.00 | 6.46s |
| Spot | tau=0.003 | 0.01480 | 985.80 | 6.25s |
| Spot | tau=0.005 | 0.01495 | 949.71 | 6.05s |
| Spot | tau=0.008 | 0.01529 | 899.92 | 5.90s |

### Optimization Diagnostics

The optimization rows below are best interpreted as diagnostic and engineering evidence. Antithetic sampling, lazy refinement, and BVH acceleration help analyze variance and runtime behavior, but they are not universal accuracy guarantees.

| Mesh | Diagnostic | Key result |
|---|---|---|
| Bunny | Antithetic | mean variance 0.01762 -> 0.00494 |
| Spot | Antithetic | mean variance 0.24709 -> 0.06820 |
| Bunny | Lazy x1 | full exact 237.46s -> 26.09s, same mean RMSE 0.00596 |
| Spot | Lazy x1 | full exact 25.62s -> 3.12s, same mean RMSE 0.02194 |

### Live Trace

![Bunny live path trace](wost_bunny/diagnostics/live_trace_plot.png)

**Figure.** Bunny live trace gives a qualitative view of the reflected random-walk paths used by the Neumann solver.

![Spot live path trace](wost_spot/diagnostics/live_trace_plot.png)

**Figure.** Spot live trace shows a representative difficult Neumann point with larger error, useful as a qualitative diagnostic rather than a statistical conclusion.

| Mesh | Point | Walks | Runtime | Absolute error |
|---|---|---:|---:|---:|
| Bunny | `(0.05, 0.02, 0.08)` | 64 | 0.143s | 0.06463 |
| Spot | `(0.8, 0.0, 0.2)` | 64 | 0.029s | 0.22723 |

## Figure Takeaways

- The Dirichlet plots validate the baseline: WoSt and Zombie agree closely and improve with more walks on both meshes.
- The Mixed Neumann plots show the main difficulty: convergence is less uniform, and Spot remains much harder than Bunny.
- The epsilon plots show that coarse epsilon can dominate Neumann error, especially in the Spot case.
- Boundary-bias detector images make the epsilon sensitivity spatial: the problem is not just a scalar RMSE shift, but a geometry-dependent boundary effect.
- Adaptive sampling and live-trace figures are most useful as diagnostics: they explain where variance and long paths appear, but should not be overclaimed as universal fixes.

## Notes

- The rerun reproduces the main WoSt values from the 2026-06-03 cross-mesh report closely; many rows are bitwise-identical because fixed seeds were reused.
- Zombie baseline was rerun for both Bunny and Spot, Dirichlet and mixed Neumann.
- Dirichlet agreement remains close across meshes.
- Mixed Neumann remains mesh-sensitive. WoSt uses much shorter paths, but Zombie can be more accurate on Spot at high walk counts.
- Runtime should be interpreted as application-level runtime. Zombie timings are Python-script-level timings, not a pure FCPW-vs-tiny_bvh backend microbenchmark.
