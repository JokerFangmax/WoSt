# Poster Results Section

## Final Figures to Use

| Figure | Caption |
|---|---|
| `final_assets/fig1_dirichlet_rmse_vs_walks.png` | Dirichlet RMSE decreases with walks on Bunny and Spot, validating the baseline Monte Carlo pipeline. |
| `final_assets/fig2_mixed_neumann_rmse_vs_walks.png` | Mixed Neumann RMSE is less uniform than Dirichlet RMSE and exposes mesh-sensitive behavior, especially on Spot. |
| `final_assets/fig6_matched_bin_abs_error_ci.png` | Under matched nearest-distance proxy bins, Spot remains higher-error in bins 1-3, but the gap shrinks with distance. |
| `final_assets/fig7_matched_bin_boundary_bias_ci.png` | Boundary-bias indicators are larger near the boundary and higher on Spot in matched bins. |
| `final_assets/fig9b_spot_epsilon_distance_rmse.png` | The epsilon-distance heatmap shows coarse epsilon is most damaging near the boundary. |

## Three Main Takeaways

1. Dirichlet validation behaves normally, so the basic Monte Carlo setup is credible.
2. Mixed Neumann behavior is geometry-sensitive, with boundary proximity and epsilon playing central roles.
3. Distance-controlled bins reduce the query-distribution confounder: Spot remains harder in bins 1-3, but the gap shrinks with distance.

## 30-Second Explanation

The base WoSt pipeline behaves normally on Dirichlet validation, but mixed Neumann problems are much more sensitive. The strongest pointwise predictor is normalized nearest-boundary-distance proxy. After matching Bunny and Spot by distance bins, Spot still has higher error in bins 1-3, though the gap shrinks, so query placement explains much of the original gap but not all of it.

## Two-Minute Explanation

I first validated the reproduced solver on Dirichlet problems. Both Bunny and Spot show ordinary Monte Carlo convergence and close agreement with Zombie, so the baseline pipeline is credible. The difficult behavior appears in the mixed Neumann setting, where paths interact with boundary normals and reflection rather than simply terminating at Dirichlet values.

Pointwise geometry diagnostics show that the normalized nearest-surface-distance proxy is the strongest available predictor of high error, high variance, long paths, and boundary-bias indicators. Local normal variation is secondary: it may add descriptive signal, but it does not explain the behavior alone.

To reduce the query-distance confounder, I sampled controlled distance bins for Bunny and Spot. Spot remains higher-error in matched bins 1-3, but the Spot/Bunny error ratio shrinks from about 3.38x and 3.68x in close/mid bins to about 1.37x in bin 3. Spot bin 4 is unavailable, so far-boundary conclusions are incomplete. Epsilon sweeps show that coarse epsilon can dominate near-boundary Neumann error, and the boundary-bias indicator is strongest near the boundary.

The final message is cautious: mixed Neumann WoSt needs boundary-distance, epsilon, and geometry diagnostics. Optimization tools like adaptive sampling, antithetic sampling, lazy refinement, BVH acceleration, and live tracing are useful engineering tools, but not guaranteed accuracy fixes.

## Warnings: What Not To Claim

- Do not claim WoSt is consistently more accurate than Zombie.
- Do not claim Bunny-vs-Spot establishes geometry causality.
- Use nearest-distance proxy wording; it is not exact signed distance.
- Do not call the epsilon-vs-half-epsilon value exact bias; call it a boundary-bias indicator or epsilon sensitivity indicator.
- Do not present matched-bin ratios as statistically definitive without repeated-seed confidence intervals.
- Do not claim shorter paths imply lower error.
