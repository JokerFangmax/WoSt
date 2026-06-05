# Zombie vs WoSt Mixed Neumann Bunny Benchmark

Generated on 2026-06-02.

## Data Sources

- Zombie baseline: `experiments\spot_mesh_report_20260603\zombie_neumann`
- WoSt reference: `C:\THU\projects\WoSt_Final_project-1\experiments\spot_mesh_report_20260603\results`
- PDE: `Delta u = 0`, analytic solution `u=x+y+z`
- Boundary setup: outer cube Dirichlet, inner Bunny Neumann
- Zombie solver: `WalkOnStars` with FCPW geometry queries

## Figures

![Neumann RMSE comparison](neumann_rmse_vs_walks_comparison.png)

![Neumann epsilon comparison](neumann_epsilon_tradeoff_comparison.png)

WoSt reference plots copied for local viewing:

![WoSt Neumann RMSE](wost_reference_plots/neumann_rmse_vs_walks.png)

![WoSt Neumann epsilon](wost_reference_plots/neumann_epsilon_tradeoff.png)

## Convergence Comparison

| Walks | Zombie RMSE | WoSt RMSE | Zombie / WoSt | Zombie mean steps | WoSt mean steps |
|---:|---:|---:|---:|---:|---:|
| 16 | 0.53373 | 0.25217 | 2.117 | 354.54 | 107.89 |
| 64 | 0.31045 | 0.19335 | 1.606 | 366.77 | 104.43 |
| 256 | 0.18426 | 0.17442 | 1.056 | 367.92 | 107.59 |
| 1024 | 0.08007 | 0.16710 | 0.479 | 367.82 | 106.16 |

## Epsilon Comparison

| Epsilon | Zombie RMSE | WoSt RMSE | Zombie / WoSt | Zombie mean steps | WoSt mean steps |
|---:|---:|---:|---:|---:|---:|
| 1e-02 | 0.19283 | 0.62693 | 0.308 | 353.11 | 11.71 |
| 1e-03 | 0.17747 | 0.23421 | 0.758 | 361.42 | 38.62 |
| 1e-04 | 0.15249 | 0.18677 | 0.816 | 369.35 | 102.31 |
| 1e-05 | 0.14985 | 0.18768 | 0.798 | 379.05 | 134.84 |

## Structured Grid

| Metric | Zombie | WoSt |
|---|---:|---:|
| RMSE | 0.14018 | 0.14054 |
| Mean steps | 243.85 | 58.73 |

Relevant VTK files:

- Zombie: `neumann_mixed_grid.vtk`, `neumann_mixed_pointcloud.vtk`
- WoSt: `C:\THU\projects\WoSt_Final_project-1\experiments\spot_mesh_report_20260603\results\neumann_mixed_grid.vtk`

## Notes

- Zombie and WoSt both show decreasing RMSE as walk count increases.
- The epsilon sweep shows the expected cost/accuracy tradeoff through increasing mean steps.
- Neumann handling is more sensitive to normal convention, reflection details, and max walk length than the Dirichlet-only benchmark, so this is primarily a mixed-boundary baseline comparison rather than a bitwise-equivalent implementation comparison.
