# Cross-Mesh Consistency Analysis: Bunny Report vs Spot Report

This note compares:

- Old integrated Bunny report: `experiments/final_integrated_report.md`
- New Spot report: `experiments/spot_mesh_report_20260603/spot_experiment_report.md`

The goal is to check whether the main experimental conclusions remain valid after changing the mesh from Bunny to Spot.

## Summary Judgment

The two reports are **mostly consistent on the core Dirichlet and diagnostic conclusions**, but the Spot experiment reveals that some Neumann and adaptive-sampling claims are **mesh-sensitive**.

The final project story should therefore be slightly refined:

```text
WoSt agrees well with Zombie on clean Dirichlet problems across both Bunny and Spot.
For mixed Neumann problems, WoSt is consistently faster and uses shorter paths, but accuracy depends strongly on mesh geometry, epsilon, and reflection behavior.
The new self-diagnostic tools are useful precisely because they expose this mesh-dependent bias/variance behavior.
```

## Conclusions That Are Consistent

### 1. Dirichlet Accuracy Agreement

Both Bunny and Spot show that WoSt and Zombie agree closely on the clean Dirichlet benchmark.

| Mesh | Key result |
|---|---|
| Bunny | At 1024 walks: Zombie RMSE `0.00403`, WoSt RMSE `0.00399` |
| Spot | At 1024 walks: Zombie RMSE `0.01426`, WoSt RMSE `0.01517` |

Analysis:

- The exact winner changes slightly, but the difference is small.
- Both solvers show the expected Monte Carlo convergence trend.
- This supports the stable conclusion that the WoSt implementation is externally validated on complex mesh domains.

Consistent claim:

```text
WoSt and Zombie closely agree on Dirichlet analytic benchmarks, and both show expected Monte Carlo convergence.
```

### 2. Monte Carlo Convergence Trend

Both reports show RMSE decreasing as walks increase.

Spot Dirichlet WoSt:

| Walks | RMSE |
|---:|---:|
| 16 | 0.11582 |
| 64 | 0.05978 |
| 256 | 0.03078 |
| 1024 | 0.01517 |

Bunny Dirichlet WoSt:

| Walks | RMSE |
|---:|---:|
| 16 | 0.03042 |
| 64 | 0.01570 |
| 256 | 0.00778 |
| 1024 | 0.00399 |

Analysis:

- Spot has larger absolute error because its domain scale is larger and the query distribution differs.
- The convergence pattern is still consistent.

Consistent claim:

```text
The estimator follows the expected Monte Carlo error reduction as sample count increases.
```

### 3. Tiny BVH Geometry Acceleration

Both reports support the value of accelerated geometry queries.

| Mesh | tiny_bvh | brute force | Speedup |
|---|---:|---:|---:|
| Bunny | 338,364 q/s | 5,417 q/s | about 62.5x |
| Spot | 1,153,935 q/s | 64,848 q/s | about 17.8x |

Analysis:

- Spot is much smaller than Bunny, so brute force is less catastrophic.
- tiny_bvh remains clearly faster.

Consistent claim:

```text
BVH acceleration is important for WoSt geometry queries, although the speedup depends on mesh size.
```

### 4. Coarse-Epsilon Neumann Bias

Both reports show that WoSt can suffer strong mixed-Neumann boundary bias at coarse epsilon.

| Mesh | epsilon | WoSt Neumann RMSE |
|---|---:|---:|
| Bunny | 1e-2 | 0.15294 |
| Bunny | 1e-4 | 0.01249 |
| Spot | 1e-2 | 0.62693 |
| Spot | 1e-4 | 0.18677 |

Analysis:

- The same qualitative effect appears on both meshes.
- Spot makes the effect stronger.
- This directly supports the boundary-bias detector as a meaningful innovation.

Consistent claim:

```text
Comparing epsilon and epsilon/2 is useful because coarse epsilon can introduce significant boundary bias, especially for mixed Neumann problems.
```

### 5. Antithetic Sampling and Lazy Refinement Diagnostics

Both reports show that:

- antithetic sampling reduces variance;
- lazy star-radius refinement can preserve RMSE while reducing runtime.

Spot examples:

| Diagnostic | Spot result |
|---|---|
| Antithetic variance | normal mean variance `0.24709`, antithetic mean variance `0.06820` |
| Lazy refinement | full exact runtime about `26.43s`, lazy threshold x1 about `3.32s`, same RMSE |

Bunny report shows the same qualitative pattern.

Consistent claim:

```text
Antithetic sampling and lazy refinement are robust optimization diagnostics across meshes.
```

## Conclusions That Need Refinement

### 1. Neumann Accuracy Is Not Uniformly Better for WoSt

The old Bunny report concluded that WoSt is competitive or better than Zombie at practical epsilon values.

This is true on Bunny:

| Bunny Neumann | Zombie RMSE | WoSt RMSE |
|---:|---:|---:|
| 256 walks | 0.01726 | 0.01308 |
| 1024 walks | 0.01309 | 0.01141 |

But not fully true on Spot:

| Spot Neumann | Zombie RMSE | WoSt RMSE |
|---:|---:|---:|
| 256 walks | 0.18426 | 0.17442 |
| 1024 walks | 0.08007 | 0.16710 |

Analysis:

- At low and medium samples on Spot, WoSt is competitive or better.
- At 1024 walks, Zombie becomes substantially more accurate.
- WoSt remains much faster and uses shorter paths, but accuracy is mesh-sensitive.

Refined claim:

```text
WoSt is consistently faster and uses shorter reflected paths in mixed Neumann tests, but its accuracy advantage is mesh-dependent.
```

### 2. Variance-Predicted Adaptive Sampling Is Mesh-Sensitive

The Bunny innovation run showed a useful sample reduction:

| Bunny method | RMSE | Mean samples | Runtime |
|---|---:|---:|---:|
| fixed_1024 | 0.00404 | 1024.00 | 53.97s |
| adaptive tau=0.005 | 0.00543 | 562.48 | 33.20s |

Spot behaves differently:

| Spot method | RMSE | Mean samples | Runtime |
|---|---:|---:|---:|
| fixed_1024 | 0.01518 | 1024.00 | 7.96s |
| adaptive tau=0.005 | 0.01538 | 954.20 | 6.37s |

Analysis:

- On Bunny, the target standard error allows substantial sample reduction.
- On Spot, the pilot variance predicts that most points need near-maximum samples.
- The method still behaves logically: it allocates more samples to a harder variance landscape.
- But it is not universally a 300--700 sample method under the same `tau`.

Refined claim:

```text
Variance-predicted adaptive sampling is a useful diagnostic and allocation strategy, but the achieved sample reduction depends on the mesh and target standard error.
```

### 3. Boundary Bias Detector Shows Stronger Bias on Spot

Bunny demo:

```text
mean bias = 0.00601
max bias = 0.06463
```

Spot demo:

```text
mean bias = 0.02392
max bias = 0.20125
```

Analysis:

- Spot has higher epsilon sensitivity under the same grid/walk setting.
- This does not contradict the old report; it strengthens the need for diagnostics.

Refined claim:

```text
Boundary-bias detection is not just a visualization feature; it reveals real mesh-dependent sensitivity.
```

## Final Consistency Table

| Old Bunny conclusion | Spot result | Consistency |
|---|---|---|
| WoSt and Zombie agree on Dirichlet | They still agree closely | Consistent |
| RMSE decreases with walks | Spot Dirichlet RMSE also decreases cleanly | Consistent |
| BVH acceleration matters | tiny_bvh still faster than brute force | Consistent |
| Coarse epsilon causes Neumann bias | Spot shows even stronger coarse-epsilon bias | Consistent, strengthened |
| WoSt faster in Neumann | Spot WoSt is much faster than Zombie | Consistent |
| WoSt Neumann accuracy competitive/better | Spot: competitive at 256, worse at 1024 | Partially inconsistent; mesh-sensitive |
| Antithetic reduces variance | Spot confirms strong variance reduction | Consistent |
| Lazy refinement reduces runtime with same RMSE | Spot confirms this strongly | Consistent |
| Variance-adaptive reduces samples to about 300--700 | Spot keeps samples near 900--990 | Not universal; needs mesh-dependent tuning |

## Recommended Updated Wording

For the final report or presentation, the safest combined conclusion is:

```text
Across Bunny and Spot, WoSt agrees closely with Zombie on clean Dirichlet benchmarks and shows the expected Monte Carlo convergence trend. Mixed Neumann problems are more geometry-sensitive: WoSt consistently uses shorter reflected paths and is much faster, but its accuracy advantage depends on the mesh and epsilon. The Spot experiment strengthens the motivation for our self-diagnostic additions, because boundary bias and adaptive-sampling behavior visibly change across meshes. Antithetic sampling and lazy star-radius refinement remain robust optimization diagnostics, while variance-predicted adaptive sampling should be tuned per mesh and target error.
```

## Bottom Line

The new Spot report does **not** invalidate the old Bunny report. It makes the project story more nuanced and stronger:

- Dirichlet validation is stable.
- Neumann behavior is mesh-sensitive.
- The new diagnostic tools are justified because they reveal exactly these mesh-dependent effects.
- The final positioning as a **Self-Diagnostic and Optimization-Aware Walk-on-Stars Solver** is better supported after testing on Spot.

