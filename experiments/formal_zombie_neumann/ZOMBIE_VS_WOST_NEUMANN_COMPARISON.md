# Zombie vs WoSt Mixed Neumann Bunny Benchmark

Generated on 2026-06-02.

## Data Sources

- Zombie baseline: `experiments\formal_zombie_neumann`
- WoSt reference: `C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_neumann\results`
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
| 16 | 0.04048 | 0.04140 | 0.978 | 282.19 | 30.93 |
| 64 | 0.02254 | 0.02497 | 0.903 | 227.22 | 33.52 |
| 256 | 0.01726 | 0.01308 | 1.319 | 238.82 | 34.46 |
| 1024 | 0.01309 | 0.01141 | 1.148 | 239.65 | 34.47 |

## Epsilon Comparison

| Epsilon | Zombie RMSE | WoSt RMSE | Zombie / WoSt | Zombie mean steps | WoSt mean steps |
|---:|---:|---:|---:|---:|---:|
| 1e-02 | 0.01664 | 0.15294 | 0.109 | 109.81 | 6.75 |
| 1e-03 | 0.01280 | 0.02676 | 0.478 | 235.35 | 15.90 |
| 1e-04 | 0.01532 | 0.01249 | 1.227 | 251.10 | 32.21 |
| 1e-05 | 0.01418 | 0.01398 | 1.014 | 257.10 | 48.88 |

## Structured Grid

| Metric | Zombie | WoSt |
|---|---:|---:|
| RMSE | 0.01227 | 0.01196 |
| Mean steps | 139.35 | 19.62 |

Relevant VTK files:

- Zombie: `neumann_mixed_grid.vtk`, `neumann_mixed_pointcloud.vtk`
- WoSt: `C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_neumann\results\neumann_mixed_grid.vtk`

## Notes

- Zombie and WoSt both show decreasing RMSE as walk count increases.
- The epsilon sweep shows the expected cost/accuracy tradeoff through increasing mean steps.
- Neumann handling is more sensitive to normal convention, reflection details, and max walk length than the Dirichlet-only benchmark, so this is primarily a mixed-boundary baseline comparison rather than a bitwise-equivalent implementation comparison.
