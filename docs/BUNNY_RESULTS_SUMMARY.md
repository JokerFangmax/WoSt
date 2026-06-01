# Bunny Benchmark Results Summary

This summary records the Bunny benchmark run completed on 2026-06-01.

## Configuration

```text
mesh: obj/Bunny.obj
vertices: 35,292
faces: 70,580
cube half extent: 0.22
query points: 500
grid resolution: 16^3
threads: 8
seed: 12345
```

The Bunny model is much smaller than the default `[-1,1]^3` cube, so the run uses:

```text
--cube 0.22
```

This makes the structured grid visualization more informative around the inner boundary.

## Generated Files

```text
results/benchmark_summary.csv
results/geometry_benchmark.csv
results/linear_dirichlet_pointcloud.vtk
results/linear_dirichlet_grid.vtk
results/adaptive_sampling_grid.vtk
results/rmse_vs_walks.png
results/epsilon_tradeoff.png
results/adaptive_vs_fixed.png
results/thread_speedup.png
results/bvh_vs_bruteforce.png
```

## Accuracy Convergence

The clean Dirichlet-only analytic benchmark uses:

```text
u(x,y,z) = x + y + z
Delta u = 0
```

Observed RMSE:

| Walks per point | RMSE |
|---:|---:|
| 16 | 0.03042 |
| 64 | 0.01570 |
| 256 | 0.00778 |
| 1024 | 0.00399 |

This follows the expected Monte Carlo trend: increasing `M` by 4x roughly halves RMSE.

## Epsilon Sweep

| Epsilon | RMSE | Mean steps |
|---:|---:|---:|
| 1e-2 | 0.00857 | 6.24 |
| 1e-3 | 0.00806 | 13.79 |
| 1e-4 | 0.00781 | 21.39 |
| 1e-5 | 0.00765 | 28.83 |

The expected tradeoff is visible: smaller epsilon increases mean walk length. RMSE changes only mildly because Monte Carlo noise is still a major error source at 256 walks per point.

## Structured Grid Output

For `grid=16`, the structured grid contains:

```text
total grid points: 4096
valid domain points: 4018
invalid points: 78
RMSE: 0.00730
mean steps: 15.39
```

Open `results/linear_dirichlet_grid.vtk` in ParaView and color by:

```text
solution
exact
abs_error
is_valid
mean_steps
std_error
```

## Adaptive Sampling

Point benchmark:

| Mode | RMSE | Mean samples used | Runtime |
|---|---:|---:|---:|
| fixed | 0.00398 | 1024.0 | 55.85 s |
| adaptive | 0.00399 | 997.71 | 54.38 s |

Structured adaptive grid:

```text
RMSE: 0.00371
mean samples used: 689.90
mean std error: 0.00290
```

The point benchmark has little room to stop early, but the grid benchmark shows a clear sample reduction from 1024 to about 690 samples on average while preserving low RMSE.

Open `results/adaptive_sampling_grid.vtk` in ParaView and color by:

```text
samples_used
std_error
abs_error
mean_steps
```

## Thread Scaling

| Threads | Runtime | Speedup |
|---:|---:|---:|
| 1 | 83.44 s | 1.00x |
| 2 | 42.46 s | 1.97x |
| 4 | 23.84 s | 3.50x |
| 8 | 13.62 s | 6.13x |

The solver shows strong OpenMP scaling on this Bunny benchmark, though not perfectly linear at 8 threads.

## BVH vs Brute Force Geometry Query

Latest geometry microbenchmark:

| Backend | Queries/sec |
|---|---:|
| tiny_bvh | 794,428 |
| brute_force | 6,169 |

The tiny_bvh closest-distance query is about 129x faster than the brute-force triangle traversal in this microbenchmark. Both checksums match, indicating the two methods produced the same aggregate distance result for the query set.

## Result Check

No major issue was found in the final results:

- RMSE convergence trend is correct.
- Epsilon sweep shows increasing mean steps as epsilon decreases.
- No diverged walks were reported.
- VTK files contain all expected scalar fields.
- Adaptive sampling preserves accuracy and reduces average grid samples.
- Thread scaling has clear speedup.
- BVH and brute-force checksums match.

One caveat: this is a reduced-size run (`queries=500`, `grid=16`) chosen to finish in a practical amount of time on the local machine. For final high-quality plots, rerun with `queries=5000` and `grid=32` if time allows.

