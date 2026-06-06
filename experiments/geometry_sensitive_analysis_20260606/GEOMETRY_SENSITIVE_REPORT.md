# Geometry-Sensitive Rerun Analysis

This analysis is saved separately from the original rerun results. It reads the 2026-06-06 rerun outputs and writes derived geometry-correlation tables, binned summaries, plots, and an extra coarse-epsilon boundary-bias detector run.

## What to Supplement

- Add geometry-causality diagnostics: correlate pointwise Neumann error, epsilon bias, mean steps, pilot variance, and sample allocation with local mesh features.
- Add pointwise Neumann diagnostics, not only summary RMSE tables.
- Add coarse-vs-finer boundary-bias maps to separate epsilon bias from Monte Carlo variance.
- Add mesh-quality/normal-variation summaries so Bunny and Spot conclusions are tied to measurable mesh properties.
- Optional future work: add more meshes or remeshed variants to avoid overclaiming Bunny/Spot-specific correlations.

## Mesh Feature Comparison

| Mesh | Faces | bbox diag | edge mean norm | normal variation mean | local normal variation mean | quality mean | aspect p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| bunny | 70580 | 0.250034 | 0.00588519 | 0.0110946 | 0.0110946 | 0.835094 | 2.04474 |
| spot | 5856 | 2.58809 | 0.0184246 | 0.0222255 | 0.0222255 | 0.835319 | 2.61664 |

## Main Sensitivity Evidence

| Mesh | Case | Key ratio / metric | Interpretation |
|---|---|---:|---|
| bunny | dirichlet 16->1024 | 7.628 | expected Dirichlet convergence |
| bunny | neumann 16->1024 | 3.629 | Monte Carlo convergence; low value indicates residual floor |
| bunny | dirichlet_epsilon_sweep 1e-2 / 1e-4 | 1.098 | large means coarse-epsilon bias dominates |
| bunny | neumann_epsilon_sweep 1e-2 / 1e-4 | 12.249 | large means coarse-epsilon bias dominates |
| spot | dirichlet 16->1024 | 7.633 | expected Dirichlet convergence |
| spot | neumann 16->1024 | 1.509 | Monte Carlo convergence; low value indicates residual floor |
| spot | dirichlet_epsilon_sweep 1e-2 / 1e-4 | 0.995 | large means coarse-epsilon bias dominates |
| spot | neumann_epsilon_sweep 1e-2 / 1e-4 | 3.357 | large means coarse-epsilon bias dominates |

## Extra Boundary-Bias Runs

| Mesh | Epsilon | Mean bias | Max bias | RMSE eps | RMSE eps/2 |
|---|---:|---:|---:|---:|---:|
| bunny | 1e-02 | 0.03847 | 1.61495 | 0.19977 | 0.11089 |
| bunny | 1e-03 | 0.00942 | 0.19949 | 0.03247 | 0.02280 |
| spot | 1e-02 | 0.10919 | 1.38271 | 0.53977 | 0.35781 |
| spot | 1e-03 | 0.04337 | 0.60245 | 0.19807 | 0.17550 |

## Strongest Correlations

### Neumann Pointwise Error

| Mesh | Feature | Pearson r | n |
|---|---|---:|---:|
| spot | nearest_distance_proxy_norm | -0.560 | 94 |
| bunny | nearest_distance_proxy_norm | -0.361 | 99 |
| spot | local_normal_variation | -0.121 | 94 |
| spot | local_edge_mean_norm | 0.097 | 94 |
| spot | local_area_norm | 0.081 | 94 |
| bunny | local_normal_variation | 0.043 | 99 |
| bunny | local_aspect_ratio | 0.042 | 99 |
| bunny | local_area_norm | 0.034 | 99 |

### Boundary Bias

| Mesh | Dataset | Feature | Pearson r | n |
|---|---|---|---:|---:|
| spot | bias_eps_1e-2 | nearest_distance_proxy_norm | -0.600 | 3876 |
| bunny | bias_eps_1e-2 | nearest_distance_proxy_norm | -0.548 | 4018 |
| bunny | bias_eps_1e-3 | nearest_distance_proxy_norm | -0.512 | 4018 |
| spot | bias_eps_1e-3 | nearest_distance_proxy_norm | -0.461 | 3876 |
| spot | bias_eps_1e-2 | local_normal_variation | -0.193 | 3876 |
| spot | bias_eps_1e-3 | local_normal_variation | -0.152 | 3876 |
| spot | bias_eps_1e-2 | local_aspect_ratio | 0.118 | 3876 |
| spot | bias_eps_1e-3 | local_edge_mean_norm | 0.107 | 3876 |
| spot | bias_eps_1e-3 | local_area_norm | 0.099 | 3876 |
| spot | bias_eps_1e-2 | local_quality | -0.090 | 3876 |

### Adaptive Variance

| Mesh | Feature | Pearson r with sample variance | n |
|---|---|---:|---:|
| bunny | nearest_distance_proxy_norm | -0.438 | 490 |
| spot | nearest_distance_proxy_norm | -0.289 | 459 |
| spot | local_edge_mean_norm | 0.227 | 459 |
| spot | local_area_norm | 0.208 | 459 |
| spot | local_aspect_ratio | 0.153 | 459 |
| spot | local_normal_variation | -0.143 | 459 |
| bunny | local_aspect_ratio | 0.122 | 490 |
| bunny | local_quality | -0.116 | 490 |

## Near-Boundary Binned Evidence

Rows are quartiles of the normalized nearest-surface distance proxy. Bin 1 is closest to the mesh. The monotone drop from bin 1 to bin 4 is the clearest pointwise evidence that near-boundary geometry drives high error, high bias, and long paths.

| Mesh | Dataset | Distance bin | Mean abs error | Mean bias | Mean sample variance | Mean samples | Mean steps |
|---|---|---:|---:|---:|---:|---:|---:|
| bunny | neumann_pointcloud | 1 | 0.013201 | nan | 0.042107 | 256 | 61.929 |
| bunny | neumann_pointcloud | 2 | 0.008777 | nan | 0.023182 | 256 | 31.09 |
| bunny | neumann_pointcloud | 3 | 0.0067897 | nan | 0.014013 | 256 | 22.81 |
| bunny | neumann_pointcloud | 4 | 0.0057042 | nan | 0.01037 | 256 | 21.863 |
| bunny | adaptive_dirichlet | 1 | 0.0060448 | nan | 0.02304 | 374.64 | 23.725 |
| bunny | adaptive_dirichlet | 2 | 0.0070316 | nan | 0.020938 | 330.58 | 21.933 |
| bunny | adaptive_dirichlet | 3 | 0.0070197 | nan | 0.014331 | 221.16 | 20.417 |
| bunny | adaptive_dirichlet | 4 | 0.0058393 | nan | 0.0079552 | 128.95 | 19.032 |
| bunny | bias_eps_1e-2 | 1 | nan | 0.11614 | nan | nan | nan |
| bunny | bias_eps_1e-2 | 2 | nan | 0.023854 | nan | nan | nan |
| bunny | bias_eps_1e-2 | 3 | nan | 0.010238 | nan | nan | nan |
| bunny | bias_eps_1e-2 | 4 | nan | 0.0036132 | nan | nan | nan |
| spot | neumann_pointcloud | 1 | 0.22578 | nan | 0.85291 | 256 | 205.34 |
| spot | neumann_pointcloud | 2 | 0.11571 | nan | 0.66534 | 256 | 117.97 |
| spot | neumann_pointcloud | 3 | 0.071742 | nan | 0.41302 | 256 | 71.657 |
| spot | neumann_pointcloud | 4 | 0.023893 | nan | 0.15985 | 256 | 34.323 |
| spot | adaptive_dirichlet | 1 | 0.010891 | nan | 0.24043 | 927.79 | 26.745 |
| spot | adaptive_dirichlet | 2 | 0.013502 | nan | 0.337 | 955.27 | 26.879 |
| spot | adaptive_dirichlet | 3 | 0.012556 | nan | 0.27302 | 988.55 | 26.202 |
| spot | adaptive_dirichlet | 4 | 0.009994 | nan | 0.134 | 728.56 | 23.615 |
| spot | bias_eps_1e-2 | 1 | nan | 0.27986 | nan | nan | nan |
| spot | bias_eps_1e-2 | 2 | nan | 0.10113 | nan | nan | nan |
| spot | bias_eps_1e-2 | 3 | nan | 0.045369 | nan | nan | nan |
| spot | bias_eps_1e-2 | 4 | nan | 0.010395 | nan | nan | nan |

## Conclusions

- The strongest and most stable pointwise predictor is proximity to the inner mesh. The normalized nearest-surface distance proxy has strong negative correlation with Neumann mean steps, sample variance, pointwise error, and boundary-bias magnitude: closer points are harder.
- Spot is harder in absolute error because its tested query distribution is much closer to the inner mesh in normalized units: the Spot neumann-pointcloud median distance proxy is about `0.176`, while Bunny's is about `0.654`. This places far more Spot queries in reflection-heavy, boundary-sensitive regions.
- Mesh-level features add another layer: compared with Bunny, Spot is much coarser relative to object scale (`edge_mean_norm_mean` about 3.1x larger), has about 2x mean normal variation, and has a larger p95 aspect ratio. These traits plausibly amplify Neumann sensitivity once paths interact with the boundary.
- Coarse epsilon is a first-order driver for Neumann error on both meshes. Spot has larger absolute coarse-epsilon RMSE and larger absolute boundary-bias magnitude, while Bunny has the larger relative `1e-2 / 1e-4` RMSE ratio because its fine-epsilon Neumann RMSE is much lower.
- Local normal variation is useful but incomplete as a pointwise proxy. It is weaker than nearest-surface distance in these tests, so the safest explanation is boundary proximity plus coarser/more angular mesh geometry, not normal variation alone.
- Adaptive sampling behavior is mostly variance-driven. Sample allocation correlates with pointwise sample variance and near-boundary distance more clearly than with any single triangle-quality scalar.
- These are empirical Bunny/Spot conclusions. A stronger causal claim would need remeshed variants of the same shape, synthetic narrow-gap/high-curvature meshes, or normal/orientation perturbation tests.

## Files

- `mesh_feature_comparison.csv`
- `all_point_geometry_features.csv`
- `geometry_correlations.csv`
- `geometry_binned_summaries.csv`
- `benchmark_sensitivity_summary.csv`
- `figures/`
