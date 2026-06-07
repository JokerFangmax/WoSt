# Poster-Ready Final Summary

This summary uses only the final rerun and controlled-geometry experiment results. Smoke-test outputs are excluded.

## Final Concise Claims

1. Dirichlet validation behaves normally: Bunny and Spot show expected Monte Carlo convergence in the reproduced Dirichlet tests, so the base estimator and comparison pipeline are credible.
2. Mixed Neumann behavior is geometry-sensitive: Neumann error, variance, path length, and epsilon sensitivity vary strongly with where queries sit relative to the inner boundary.
3. Normalized nearest-surface distance is the strongest pointwise predictor found in these runs: closer queries have higher error, higher variance, longer paths, and larger boundary-bias indicators.
4. Distance-controlled bins reduce the query-distribution confounder: Spot remains higher-error than Bunny in matched bins 1-3, but the gap shrinks with distance.
5. Epsilon x distance sweeps show that coarse epsilon creates boundary bias, especially near the boundary; reducing epsilon helps, but close-bin residual error remains nontrivial.
6. Antithetic sampling, lazy refinement, adaptive sampling, BVH acceleration, and live path tracing should be presented as diagnostics and optimization-aware tools, not as universal accuracy guarantees.

## Recommended Poster Figures

| Priority | Figure | Caption |
|---:|---|---|
| 1 | `experiments/controlled_geometry_experiments_20260606/plots/matched_bins_bunny_vs_spot_abs_error.png` | Under matched normalized distance bins, Spot remains higher-error than Bunny in bins 1-3, but the gap narrows in farther bins. |
| 2 | `experiments/controlled_geometry_experiments_20260606/plots/distance_bin_vs_mean_boundary_bias.png` | Boundary-bias indicators are largest near the inner boundary and are consistently higher for Spot in matched bins. |
| 3 | `experiments/controlled_geometry_experiments_20260606/epsilon_distance_heatmaps/bunny_epsilon_vs_distance_rmse.png` and `experiments/controlled_geometry_experiments_20260606/epsilon_distance_heatmaps/spot_epsilon_vs_distance_rmse.png` | Coarse epsilon amplifies error most strongly near the boundary, separating boundary bias from pure Monte Carlo variance. |
| 4 | `experiments/rerun_cross_mesh_20260606/zombie_bunny_dirichlet/rmse_vs_walks_comparison.png` and `experiments/rerun_cross_mesh_20260606/zombie_spot_dirichlet/rmse_vs_walks_comparison.png` | Dirichlet benchmarks show expected convergence, validating the baseline experimental setup before studying Neumann sensitivity. |
| 5 | `experiments/rerun_cross_mesh_20260606/zombie_bunny_neumann/neumann_rmse_vs_walks_comparison.png` and `experiments/rerun_cross_mesh_20260606/zombie_spot_neumann/neumann_rmse_vs_walks_comparison.png` | Mixed Neumann convergence is less uniform than Dirichlet convergence and depends strongly on geometry and boundary interaction. |
| 6 | `experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/variance_adaptive_tradeoff.png` and `experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/variance_adaptive_tradeoff.png` | Adaptive sampling is best framed as a variance diagnostic and allocation tool rather than a universal improvement in every region. |
| 7 | `experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/live_trace_plot.png` | Live path traces provide qualitative evidence for long reflection-heavy paths near difficult Neumann boundary regions. |

## Matched-Bin Table

| Distance bin | Spot/Bunny error | Spot/Bunny bias | Spot/Bunny steps | Status |
|---:|---:|---:|---:|---|
| 1 | 3.38x | 3.33x | 1.28x | matched |
| 2 | 3.68x | 2.37x | 0.76x | matched |
| 3 | 1.37x | 1.83x | 0.75x | matched |
| 4 | NA | NA | NA | missing Spot bin |

## Final Limitations Paragraph

These experiments support a cautious geometry-sensitive interpretation, not a universal causal theorem. The normalized nearest-distance variable is a nearest-centroid proxy rather than exact signed distance or local feature size. Bunny and Spot differ in shape, scale, triangulation density, normal variation, and feasible query distribution, so the controlled bins reduce but do not eliminate confounding. Stronger causal claims require same-shape remeshed variants, controlled normal perturbations, or synthetic stress-test geometries with known boundary-distance and curvature structure.

## Avoid-Overclaiming Checklist

- Do not claim WoSt is always more accurate than Zombie; the safe claim is that the reproduced Dirichlet tests validate normal convergence while Neumann behavior is more sensitive.
- Do not claim Spot difficulty is caused only by mesh quality; distance distribution, shape, reflection behavior, and normal estimates are still entangled.
- Do not claim local normal variation alone explains error; nearest-boundary distance is the strongest stable predictor in these runs.
- Do not claim exact distance-to-boundary analysis; the current distance is a nearest-surface proxy.
- Do not claim universal geometry causality from Bunny and Spot alone.
- Do not present adaptive sampling, antithetic sampling, lazy refinement, BVH, or live tracing as guaranteed accuracy improvements; frame them as diagnostics, controls, and performance tools.
- Do not use smoke-test outputs as evidence in the final poster or report.

## Two-Minute Presentation Script

I start from a reproduced Walk-on-Stars pipeline and ask where it is reliable and where it becomes sensitive. The first sanity check is Dirichlet: on Bunny and Spot, the Dirichlet experiments show the expected Monte Carlo convergence, which gives us confidence that the implementation and comparison pipeline are behaving normally.

The interesting behavior appears in the mixed Neumann setting. The same solver becomes much more geometry-sensitive: errors, variance, mean path length, and boundary-bias indicators all increase near the inner boundary. In the pointwise analysis, normalized nearest-surface distance is the strongest and most stable predictor. Local mesh features matter less consistently on their own.

To test whether the Spot-vs-Bunny gap was just a query-distribution artifact, I ran a distance-controlled experiment. I sampled queries from the same normalized distance bins on each mesh. Spot still has higher error than Bunny in matched bins 1-3: about 3.38x in bin 1, 3.68x in bin 2, and 1.37x in bin 3. So Spot remains harder after matching distance, but the gap shrinks as we move away from the boundary. That means the original query distribution was a major confounder, but not the whole story.

The epsilon-by-distance sweep adds the second piece. Coarse epsilon creates large boundary bias, especially in close bins. Reducing epsilon helps, but close-boundary residual error can remain high, suggesting remaining effects from reflection behavior, shape, normals, or mesh geometry.

The takeaway is cautious: Dirichlet validates the estimator; mixed Neumann exposes geometry-sensitive behavior; boundary proximity is the strongest predictor; and the optimization tools help diagnose and control the computation rather than proving universal superiority.
