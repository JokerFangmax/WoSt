# Formal WoSt vs Zombie Bunny Comparison

Generated on 2026-06-02 from fresh formal runs.

## Setup

- Mesh: Stanford Bunny, 70,580 triangles.
- Domain: outer cube `[-0.22, 0.22]^3` minus inner Bunny mesh.
- Exact solution: `u(x,y,z) = x + y + z`, `Delta u = 0`.
- Dirichlet baseline: inner and outer boundaries use exact Dirichlet data.
- Mixed Neumann baseline: outer cube is Dirichlet, inner Bunny is Neumann with `h = grad(u) dot n`.
- WoSt executable: `build/Release/wost.exe`.
- Zombie scripts: `C:/THU/homework/zombie/scripts/zombie_bunny_baseline.py` and `zombie_neumann_bunny_baseline.py`.

Fresh output folders:

- WoSt Dirichlet: `experiments/formal_wost_dirichlet/results/`
- WoSt Neumann: `experiments/formal_wost_neumann/results/`
- Zombie Dirichlet: `experiments/formal_zombie_dirichlet/`
- Zombie Neumann: `experiments/formal_zombie_neumann/`

## Commands

WoSt Dirichlet:

```powershell
Set-Location experiments\formal_wost_dirichlet
..\..\build\Release\wost.exe --mode convergence --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode epsilon --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode grid --obj ..\..\obj\Bunny.obj --grid 16 --threads 8 --seed 12345 --cube 0.22
..\..\build\Release\wost.exe --mode geometry --obj ..\..\obj\Bunny.obj --queries 500 --threads 8 --seed 12345 --cube 0.22
```

WoSt Neumann:

```powershell
Set-Location experiments\formal_wost_neumann
..\..\build\Release\wost.exe --mode neumann --obj ..\..\obj\Bunny.obj --queries 100 --grid 8 --threads 8 --seed 32345 --cube 0.22
```

Zombie Dirichlet:

```powershell
C:\THU\homework\zombie\.venv\Scripts\python.exe C:\THU\homework\zombie\scripts\zombie_bunny_baseline.py --mode all --obj C:\THU\homework\zombie\obj\Bunny.obj --out experiments\formal_zombie_dirichlet --reference-results C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_dirichlet\results --queries 500 --geometry-queries 500 --grid 16 --seed 12345 --cube 0.22 --max-steps 512
```

Zombie Neumann:

```powershell
C:\THU\homework\zombie\.venv\Scripts\python.exe C:\THU\homework\zombie\scripts\zombie_neumann_bunny_baseline.py --mode all --obj C:\THU\homework\zombie\obj\Bunny.obj --out experiments\formal_zombie_neumann --reference-results C:\THU\projects\WoSt_Final_project-1\experiments\formal_wost_neumann\results --queries 100 --grid 8 --seed 32345 --cube 0.22 --max-steps 2048
```

## Dirichlet Convergence

| Walks | Zombie RMSE | WoSt RMSE | Zombie / WoSt RMSE | Zombie time (s) | WoSt time (s) |
|---:|---:|---:|---:|---:|---:|
| 16 | 0.03110 | 0.03042 | 1.022 | 0.24 | 0.85 |
| 64 | 0.01685 | 0.01570 | 1.073 | 0.99 | 3.31 |
| 256 | 0.00845 | 0.00778 | 1.085 | 3.88 | 13.18 |
| 1024 | 0.00403 | 0.00399 | 1.010 | 15.58 | 53.03 |

Both solvers follow the expected Monte Carlo convergence trend. WoSt is slightly more accurate in this run at all sample counts, while Zombie is faster for the Dirichlet solve loop.

Figure: `experiments/formal_zombie_dirichlet/rmse_vs_walks_comparison.png`

## Dirichlet Epsilon Sweep

| Epsilon | Zombie RMSE | WoSt RMSE | Zombie / WoSt RMSE | Zombie time (s) | WoSt time (s) |
|---:|---:|---:|---:|---:|---:|
| 1e-2 | 0.00897 | 0.00857 | 1.047 | 1.78 | 12.35 |
| 1e-3 | 0.00866 | 0.00806 | 1.075 | 3.01 | 12.90 |
| 1e-4 | 0.00844 | 0.00781 | 1.080 | 3.64 | 13.27 |
| 1e-5 | 0.00817 | 0.00765 | 1.068 | 4.25 | 13.62 |

WoSt again has slightly lower RMSE. The epsilon sweep is mostly sampling-noise limited for this linear Dirichlet problem, but both methods show increasing cost as epsilon tightens.

Figure: `experiments/formal_zombie_dirichlet/epsilon_tradeoff_comparison.png`

## Dirichlet Grid

| Metric | Zombie | WoSt |
|---|---:|---:|
| Grid | 16^3 | 16^3 |
| Valid points | 4018 | 4018 |
| RMSE | 0.00747 | 0.00730 |
| Runtime (s) | 23.74 | 87.60 |

Both grids produce comparable accuracy. Zombie is faster on this grid solve; WoSt has slightly smaller RMSE.

## Geometry Distance Microbenchmark

| Backend | Queries | Query/s | Time (s) |
|---|---:|---:|---:|
| WoSt tiny_bvh | 500 | 338,364 | 0.00148 |
| WoSt brute force | 500 | 5,417 | 0.09231 |
| Zombie FCPW BVH | 500 | 265,788 | 0.00188 |

WoSt's `tiny_bvh` distance query path is about 62.5x faster than its brute-force baseline on this 500-query Bunny test. It is also about 1.27x faster than the Zombie FCPW distance query loop in this microbenchmark. The checksums differ between WoSt and Zombie because their geometry-query scripts measure different boundary sets/validity conventions, so the query-throughput comparison is more useful than the checksum comparison.

## Mixed Neumann Convergence

| Walks | Zombie RMSE | WoSt RMSE | Zombie / WoSt RMSE | Zombie mean steps | WoSt mean steps | Zombie time (s) | WoSt time (s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0.04048 | 0.04140 | 0.978 | 282.19 | 30.93 | 2.06 | 1.11 |
| 64 | 0.02254 | 0.02497 | 0.903 | 227.22 | 33.52 | 6.76 | 4.44 |
| 256 | 0.01726 | 0.01308 | 1.319 | 238.82 | 34.46 | 28.00 | 17.20 |
| 1024 | 0.01309 | 0.01141 | 1.148 | 239.65 | 34.47 | 111.35 | 71.06 |

Both methods converge as walk count increases. Zombie is slightly better at very low walk counts, while WoSt is better at 256 and 1024 walks. WoSt uses far fewer average walk steps in this Neumann setup, which translates into lower runtime at the same walk count.

Figure: `experiments/formal_zombie_neumann/neumann_rmse_vs_walks_comparison.png`

## Mixed Neumann Epsilon Sweep

| Epsilon | Zombie RMSE | WoSt RMSE | Zombie / WoSt RMSE | Zombie mean steps | WoSt mean steps | Zombie time (s) | WoSt time (s) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1e-2 | 0.01664 | 0.15294 | 0.109 | 109.81 | 6.75 | 59.52 | 9.67 |
| 1e-3 | 0.01280 | 0.02676 | 0.478 | 235.35 | 15.90 | 65.15 | 10.61 |
| 1e-4 | 0.01532 | 0.01249 | 1.227 | 251.10 | 32.21 | 29.13 | 15.15 |
| 1e-5 | 0.01418 | 0.01398 | 1.014 | 257.10 | 48.88 | 24.93 | 17.92 |

This sweep highlights different bias/cost behavior. Zombie is much more stable at coarse epsilon values but pays for it with much longer walks. WoSt is much faster and accurate at `1e-4` and `1e-5`, but its coarse `1e-2` Neumann result has large boundary bias.

Figure: `experiments/formal_zombie_neumann/neumann_epsilon_tradeoff_comparison.png`

## Mixed Neumann Grid

| Metric | Zombie | WoSt |
|---|---:|---:|
| Grid | 8^3 | 8^3 |
| Valid points | 508 | 508 |
| RMSE | 0.01227 | 0.01196 |
| Mean steps | 139.35 | 19.62 |
| Runtime (s) | 82.36 | 16.14 |

WoSt and Zombie have nearly identical grid RMSE in the mixed Neumann setting, but WoSt is about 5.1x faster on this grid run because it uses many fewer mean steps.

## WoSt-Only Adaptive Diagnostic

The formal WoSt Dirichlet adaptive point run completed before the adaptive-grid VTK stage timed out. The point comparison showed:

| Method | RMSE | Mean samples | Runtime (s) |
|---|---:|---:|---:|
| fixed 1024 | 0.00398 | 1024.0 | 54.83 |
| old absolute adaptive | 0.00399 | 997.7 | 54.48 |

This confirms the previous issue: the old absolute-standard-error adaptive criterion barely reduces samples on the Bunny Dirichlet setup. The new relative-standard-error mode is implemented in the solver, but a full Bunny-scale optimization batch was not run here because the formal cross-project comparison already took several long jobs.

## Conclusion

- Dirichlet: WoSt is marginally more accurate; Zombie is faster for the solve loop at this formal scale.
- Geometry microbenchmark: WoSt `tiny_bvh` is faster than WoSt brute force and faster than the Zombie FCPW query loop for the tested distance query path.
- Mixed Neumann: WoSt becomes faster than Zombie and competitive or better in accuracy at practical epsilon values (`1e-4`, `1e-5`), mainly because its average walk lengths are much shorter.
- Boundary bias: Zombie is more robust at very coarse Neumann epsilon, while WoSt needs smaller epsilon to avoid the large `1e-2` boundary-bias regime.
- Both projects produce ParaView-compatible VTK outputs and quantitative CSV summaries for the Bunny benchmark.
