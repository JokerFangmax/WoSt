# Final Course Report: Geometry-Sensitive Walk-on-Stars under Mixed Neumann Boundary Conditions

## Abstract / Executive Summary

This report studies how a reproduced and extended Walk-on-Stars (WoSt) implementation behaves on Bunny and Spot meshes, with emphasis on mixed Neumann boundary conditions. The Dirichlet experiments serve as a sanity check: WoSt and the Zombie baseline show ordinary Monte Carlo convergence. Mixed Neumann experiments are more sensitive: error, variance, path length, and the epsilon-vs-half-epsilon boundary-bias indicator depend strongly on query placement near the inner boundary. Geometry-sensitive diagnostics identify the normalized nearest-surface-distance proxy as the strongest available pointwise predictor. A distance-controlled experiment reduces the query-distance confounder and shows that Spot remains higher-error than Bunny in matched bins 1-3, but the gap shrinks with distance. Optimization tools are useful for diagnosis and engineering, but they are not presented as general accuracy improvements.

## 1. Introduction and Research Question

**Research question:** How does Walk-on-Stars behave under mixed Neumann boundary conditions, and how are its errors affected by boundary proximity, epsilon, and mesh geometry?

The main scientific issue is that Neumann boundary handling depends on reflection and surface normals rather than simple boundary termination. This makes the solver more sensitive to local geometry and to how close query points are to the boundary. The goal is not to declare one solver globally better, but to identify where and why the mixed Neumann setting becomes difficult.

## 2. Background

A boundary value problem asks for a function inside a domain subject to conditions on the boundary. Dirichlet conditions prescribe the function value on the boundary; random-walk solvers can terminate at the boundary and evaluate that value. Neumann conditions prescribe normal derivative information. In a mixed setting, part of the boundary uses Dirichlet values and part uses Neumann reflection or derivative contributions.

Walk-on-Stars is a random-walk Monte Carlo method for solving PDE-style boundary value problems. Instead of stepping on a regular grid, it samples larger geometry-aware jumps. In a Dirichlet problem, each path is mostly a termination-and-estimation process. In a mixed Neumann problem, paths may interact repeatedly with the inner boundary, and errors can arise from reflection behavior, normal estimation, epsilon termination, and local mesh quality.

## 3. Problem Formulation and Physical Interpretation

The experiments study a boundary value problem on a three-dimensional domain `Omega`, represented as an outer axis-aligned cube with an inner triangle mesh removed. The manufactured reference solution used by the benchmark code is

```text
u(x, y, z) = x + y + z,    Delta u = 0.
```

For the Dirichlet validation, both the outer cube and inner mesh prescribe the value of `u` on the boundary. In the mixed Neumann benchmark, the outer cube remains Dirichlet, while the inner mesh prescribes normal derivative data. In the implementation this inner Neumann value is `grad u dot n`, where `grad u = (1, 1, 1)` and `n` is the local surface normal.

This distinction matters physically and numerically. A Dirichlet random walk can terminate when it reaches the boundary and evaluate the boundary value. A mixed Neumann walk may instead reflect or otherwise interact with the boundary normal, so the estimate depends on surface orientation, reflection behavior, and how close the query point lies to the boundary. Walk-on-Stars uses geometry-aware star-shaped steps rather than a regular grid, which is efficient but makes the geometry queries and boundary tolerance important parts of the numerical method.

The epsilon parameter should be interpreted as a numerical boundary thickness or termination tolerance. A coarse epsilon can stop or reflect paths before local boundary behavior is resolved, especially near the inner Neumann surface. RMSE is computed against the available analytic/reference value over valid query points; invalid points are excluded by the benchmark summaries.

### Connection to Physical Simulation Course Concepts

This project connects directly to Monte Carlo numerical methods, PDE boundary value problems, mesh-based geometry processing, and numerical error introduced by discretization and tolerance parameters. The mixed Neumann experiments also illustrate a common physical simulation theme: variance reduction and runtime acceleration are not the same as removing systematic error. Robust simulation algorithms need both statistical convergence checks and diagnostics for geometry-dependent failure modes.

## 4. Methods and Experimental Setup

- **WoSt implementation:** C++ implementation in this repository, run through `build/Release/wost.exe`.
- **Zombie baseline:** Python-driven Zombie baseline under `C:/THU/homework/zombie`, used for cross-method comparison.
- **Meshes:** Bunny (`obj/Bunny.obj`) and Spot (`spot/spot_triangulated.obj`). Spot is coarser in normalized edge length and has higher normal variation in the geometry-sensitive analysis.
- **Query sampling:** Standard rerun queries are random/grid-based depending on the benchmark. Controlled experiments sample query points by normalized nearest-surface-distance proxy bins.
- **Walk counts:** Main convergence sweeps use 16, 64, 256, and 1024 walks per point.
- **Epsilon:** Main epsilon sweeps use 1e-2, 1e-3, 1e-4, and 1e-5.
- **Metrics:** RMSE, mean steps, sample variance, mean samples, and epsilon-vs-half-epsilon boundary-bias indicator.
- **Nearest-distance proxy:** The geometry analysis uses a normalized nearest-surface-distance proxy based on nearest triangle/centroid-style geometry features. It should not be read as exact signed distance.

## 5. Experiment 1: Dirichlet Sanity Check

![Dirichlet RMSE vs walks](final_assets/fig1_dirichlet_rmse_vs_walks.png)

**Figure 1.** Dirichlet RMSE versus walks for Bunny and Spot, comparing WoSt with the Zombie baseline. The intended reading is the convergence trend, not a claim that one method is better in every setting.

**Main claim:** the Dirichlet experiments show ordinary Monte Carlo behavior on both meshes, validating the baseline pipeline before interpreting mixed Neumann sensitivity.

The Dirichlet panels show that increasing walks reduces RMSE for both Bunny and Spot, and WoSt/Zombie agreement is close across the tested walk counts. This is the sanity check: the later Neumann difficulty is not simply a failed experiment pipeline.

## 6. Experiment 2: Mixed Neumann Sensitivity

![Mixed Neumann RMSE vs walks](final_assets/fig2_mixed_neumann_rmse_vs_walks.png)

**Figure 2.** Mixed Neumann RMSE versus walks for Bunny and Spot. Compared with the Dirichlet panel, this figure highlights less uniform convergence and the harder Spot case.

**Main claim:** mixed Neumann behavior is less uniform than Dirichlet behavior and is strongly mesh-sensitive.

Bunny shows improvement with more walks, but the high-walk Neumann error does not drop as cleanly as the Dirichlet case. Spot is substantially harder: WoSt RMSE remains high even at larger walk counts.

### Why can Zombie outperform WoSt on Spot at high walk counts?

In Spot mixed Neumann convergence, Zombie has lower RMSE than WoSt at higher walk counts. At 256 walks, Spot Zombie RMSE is `0.14248` while WoSt RMSE is `0.17442`; at 1024 walks, Zombie RMSE is `0.11072` while WoSt RMSE is `0.16710`. WoSt uses much shorter mean paths than Zombie, but shorter paths do not guarantee lower error. This suggests possible residual systematic error from reflection, epsilon handling, local geometry, or implementation differences. This remains an important limitation and future investigation point.

#### Hypotheses rather than conclusions

This anomaly is not treated as evidence of a bug or evidence that Zombie is generally better. Several explanations are plausible: WoSt uses shorter paths, but more aggressive geometry-aware steps may be more sensitive to radius, normal, or reflection errors near rough boundaries. Spot is coarser and has higher normal variation, so Neumann reflection may accumulate systematic error. Zombie's longer paths may be more conservative, reducing some boundary-handling error at high walk counts. Implementation differences such as geometry query backend, reflection handling, and epsilon treatment may also matter.

These hypotheses are consistent with the diagnostics but are not proven by the current Bunny/Spot experiments. A stronger answer would require same-shape remeshing, exact signed-distance diagnostics, or per-path reflection-density comparisons.

## 7. Experiment 3: Epsilon and Boundary-Bias Indicator

![Mixed Neumann epsilon sweep](final_assets/fig3_neumann_epsilon_sweep.png)

**Figure 3.** Mixed Neumann RMSE under different epsilon values at 256 walks. Coarse epsilon produces the largest errors in the tested setup.

![Boundary-bias indicator summary](final_assets/fig4_boundary_bias_indicator_summary.png)

**Figure 4.** Epsilon-vs-half-epsilon boundary-bias indicator summary. The quantity is an epsilon sensitivity indicator rather than an exact bias decomposition.

**Main claim:** coarse epsilon can dominate mixed Neumann error, and the epsilon-vs-half-epsilon boundary-bias indicator is larger on Spot.

The epsilon sweep shows much larger RMSE at coarse epsilon in the mixed Neumann setting. The boundary-bias indicator compares epsilon and half-epsilon estimates; it is an epsilon sensitivity indicator, not an exact bias decomposition. It is spatially and mesh dependent, which is consistent with the later controlled distance-bin results.

## 8. Experiment 4: Geometry-Sensitive Pointwise Diagnostics

![Top geometry correlations](final_assets/fig5_top10_geometry_correlations.png)

**Figure 5.** Simplified top-10 geometry correlations by absolute Pearson correlation. The dominant trend is that normalized nearest-distance proxy is the strongest observed predictor; local normal variation appears as a secondary descriptor rather than a standalone explanation.

![Pointwise Neumann error scatter](final_assets/fig5b_pointwise_error_scatter.png)

**Figure 6.** Pointwise Neumann absolute error scatter. The scatter view shows that near-boundary regions contain many of the difficult points, but it should be read as diagnostic evidence rather than a mechanism claim.

**Main claim:** the normalized nearest-surface-distance proxy is the strongest observed pointwise predictor of high error, high variance, long paths, and boundary-bias indicators.

The geometry-sensitive analysis shows that points close to the inner boundary are consistently harder. Local normal variation and related mesh features are useful secondary descriptors, but they are not a standalone explanation. This motivates distance-controlled comparisons before attributing the Bunny/Spot gap to mesh geometry alone.

## 9. Experiment 5: Distance-Controlled Bins

![Matched-bin mean absolute error](final_assets/fig6_matched_bin_abs_error_ci.png)

**Figure 7.** Matched-bin mean absolute error with across-query 95% confidence intervals. Spot remains higher-error in bins 1-3, while the gap shrinks with distance.

![Matched-bin boundary-bias indicator](final_assets/fig7_matched_bin_boundary_bias_ci.png)

**Figure 8.** Matched-bin boundary-bias indicator with across-query 95% confidence intervals. The close-boundary bins show larger epsilon sensitivity, especially for Spot.

![Matched-bin mean steps](final_assets/fig8_matched_bin_mean_steps.png)

**Figure 9.** Mean WoSt steps by matched nearest-distance proxy bin. Longer paths concentrate near the boundary, but path length alone does not determine RMSE.

**Main claim:** Spot remains higher-error than Bunny in matched bins 1-3, but the gap shrinks with distance.

The controlled experiment samples query points by normalized nearest-surface-distance proxy bins:

- **Bin 1:** `[0.05, 0.15]`
- **Bin 2:** `[0.15, 0.30]`
- **Bin 3:** `[0.30, 0.60]`
- **Bin 4:** `[0.60, 1.00]`

Spot remains higher-error in matched bins 1-3, with descriptive Spot/Bunny error ratios of about 3.38x, 3.68x, and 1.37x. This supports residual mesh, shape, reflection, or normal effects after reducing the query-distance confounder. However, the shrinking ratio shows that query-distance distribution was a major confounding factor. Spot has no valid sampled points in bin 4 under the current setup, so far-boundary matched conclusions are incomplete.

The 95% confidence intervals shown here are computed across valid query points within each distance bin. They should be interpreted as spatial/query variability, not as repeated-seed Monte Carlo confidence intervals. Repeated-seed confidence intervals remain future work. Spot bin 1 has especially high variability, which suggests that the near-boundary region is heterogeneous and may include a few very difficult query points.

### Controlled matched-bin ratios

| bin | Spot/Bunny error | Spot/Bunny bias indicator | Spot/Bunny steps | status |
|---|---|---|---|---|
| 1 | 3.383 | 3.334 | 1.280 | descriptive matched-bin ratio |
| 2 | 3.685 | 2.371 | 0.7649 | descriptive matched-bin ratio |
| 3 | 1.371 | 1.833 | 0.7462 | descriptive matched-bin ratio |
| 4 | NA | NA | NA | missing mesh/bin pair |

### Recomputed per-query matched-bin statistics

| mesh | bin | n | mean abs error | abs error std | abs error SE | abs error 95% CI | RMSE | mean steps | mean sample variance | mean bias indicator |
|---|---|---|---|---|---|---|---|---|---|---|
| bunny | 1 | 21 | 0.0357 | 0.0238 | 0.0052 | [0.0255, 0.0459] | 0.0426 | 99.088 | 0.0435 | 0.0156 |
| bunny | 2 | 22 | 0.0152 | 0.0110 | 0.0024 | [0.0106, 0.0198] | 0.0186 | 61.227 | 0.0363 | 0.0147 |
| bunny | 3 | 23 | 0.0120 | 0.0087 | 0.0018 | [0.0084, 0.0155] | 0.0147 | 37.956 | 0.0316 | 0.0129 |
| bunny | 4 | 24 | 0.0060 | 0.0060 | 0.0012 | [0.0036, 0.0084] | 0.0084 | 26.626 | 0.0199 | 0.0069 |
| spot | 1 | 22 | 0.1209 | 0.1165 | 0.0248 | [0.0722, 0.1695] | 0.1660 | 126.84 | 0.6902 | 0.0520 |
| spot | 2 | 24 | 0.0561 | 0.0505 | 0.0103 | [0.0359, 0.0763] | 0.0748 | 46.831 | 0.2288 | 0.0348 |
| spot | 3 | 24 | 0.0164 | 0.0154 | 0.0032 | [0.0102, 0.0226] | 0.0223 | 28.322 | 0.1083 | 0.0237 |

## 10. Diagnostic and Optimization Tools

![Bunny adaptive sampling tradeoff](final_assets/fig10a_bunny_adaptive_tradeoff.png)

**Figure 10.** Bunny adaptive sampling tradeoff. The figure asks where variance concentrates and how many samples the adaptive rule allocates relative to fixed-sample baselines.

![Spot adaptive sampling tradeoff](final_assets/fig10b_spot_adaptive_tradeoff.png)

**Figure 11.** Spot adaptive sampling tradeoff. Spot remains close to the maximum sample count, indicating widespread high variance in the sampled region.

![Spot live trace](final_assets/fig11_spot_live_trace.png)

**Figure 12.** Spot live path trace. The trace is qualitative evidence only: it illustrates reflection-heavy behavior near difficult Neumann regions but does not by itself establish a mechanism.

These tools are tied to the research question as diagnostics rather than accuracy guarantees. **Adaptive sampling** asks where variance concentrates. The fact that Spot remains close to the maximum sample count suggests that high variance is widespread in the sampled region, so adaptive sampling is less useful as a speedup but still useful as a variance diagnostic. **Antithetic sampling** asks whether paired samples can reduce estimator variance in diagnostic runs. **Lazy refinement** asks how much runtime can be saved without changing the tested mean RMSE in the diagnostic setting. **BVH acceleration** asks whether geometry querying is efficient enough for repeated WoSt experiments. **Live trace** asks what difficult reflection-heavy paths look like. The trace is qualitative evidence only. It illustrates reflection-heavy behavior near difficult Neumann regions but does not by itself establish a mechanism.

## 11. Discussion

The main lesson is that Monte Carlo PDE solvers can look healthy under Dirichlet validation while becoming much more sensitive under mixed Neumann conditions. Dirichlet paths terminate at boundary values; mixed Neumann paths interact with normals and reflection behavior. That interaction makes boundary proximity, epsilon termination, and local mesh geometry more important.

The strongest available pointwise signal is the normalized nearest-distance proxy. Mesh features such as local normal variation are plausible contributors, especially for a coarse mesh such as Spot, but Bunny and Spot alone do not isolate causality. The unresolved Spot high-walk anomaly is especially important: Zombie can outperform WoSt on Spot at high walk counts even though WoSt uses shorter paths. That points to residual systematic effects rather than pure Monte Carlo variance.

## 12. Practical Takeaways

- Run Dirichlet sanity checks as the first validation step before interpreting mixed Neumann failures.
- Inspect query-distance proxy distributions before comparing meshes.
- Treat near-boundary mixed Neumann queries as high-risk.
- Avoid coarse epsilon such as `1e-2` near the boundary in the tested setup.
- If adaptive sampling saturates near the maximum sample count, interpret it as widespread high variance rather than a failure of the sampler.
- Do not assume shorter paths imply lower RMSE.
- Use live traces only as qualitative diagnostics.

## 13. Limitations

- Only Bunny and Spot are tested in the controlled cross-mesh analysis.
- The nearest-distance variable is a proxy. Exact signed distance or local feature size could change the quantitative bin assignment.
- Matched-bin confidence intervals are across query points, not repeated seeds.
- Matched-bin valid sample counts are small, and matched-bin ratios are descriptive.
- Spot bin 4 is unavailable, so far-from-boundary cross-mesh comparison is incomplete.
- Fixed seeds and limited repeated-seed statistics restrict uncertainty analysis.
- Bunny and Spot alone cannot establish general geometry causality.
- The Zombie-vs-WoSt anomaly remains unresolved.
- A stronger causal study would require same-shape remeshing, synthetic geometry stress tests, exact signed distance, or per-path reflection statistics.
- The epsilon-vs-half-epsilon boundary-bias value is an indicator, not a true exact-solution bias decomposition.

## 14. Claim-Evidence-Limitation Table

| Claim | Evidence | Limitation / caution |
|---|---|---|
| Dirichlet validation | Bunny and Spot Dirichlet RMSE decreases with walks in Figure 1 and the Zombie/WoSt summary CSVs. | This validates the baseline pipeline, not every boundary condition. |
| Mixed Neumann geometry sensitivity | Figure 2 and Neumann tables show less uniform convergence and larger Spot errors. | Bunny and Spot differ in shape, mesh resolution, and query distribution. |
| Boundary proximity is the strongest observed predictor | Geometry correlations and pointwise scatter plots identify normalized nearest-distance proxy as the strongest stable predictor. | The variable is a nearest-distance proxy, not exact signed distance. |
| Spot remains harder after distance matching | Controlled bins 1-3 show Spot/Bunny error ratios of about 3.38x, 3.68x, and 1.37x. | Ratios are descriptive; Spot bin 4 is missing and repeated-seed confidence intervals are not available. |
| Coarse epsilon induces boundary-sensitive error | Epsilon sweep and boundary-bias indicator figures show much larger error/indicator values at coarse epsilon. | The epsilon-vs-half-epsilon value is an indicator, not an exact bias decomposition. |
| Optimization tools are diagnostic, not general fixes | Adaptive, antithetic, lazy refinement, BVH, and live-trace outputs expose variance/runtime/path behavior. | They should not be presented as guaranteed accuracy improvements. |

## 15. Conclusion

The reproduced WoSt pipeline passes the basic Dirichlet sanity check, but mixed Neumann boundary conditions reveal strong geometry sensitivity. Boundary proximity and epsilon handling explain a large part of the error structure. Controlled distance bins show that Spot remains harder than Bunny in matched bins 1-3, while the shrinking gap indicates that the original query-distance distribution was a major confounder. The safest final interpretation is therefore not that one method or mesh property fully explains the behavior, but that mixed Neumann WoSt requires careful boundary-distance, epsilon, and geometry diagnostics.

## 16. Appendix

### Appendix A. Full Tables and Derived Assets

- `reports/final_assets/controlled_matched_bin_statistics.csv`
- `reports/final_assets/controlled_matched_bin_ratios.csv`
- `reports/final_report_provenance.md`
- Source reports: `experiments/rerun_cross_mesh_20260606/RERUN_SUMMARY.md`, `experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md`, `experiments/controlled_geometry_experiments_20260606/CONTROLLED_GEOMETRY_REPORT.md`

### Appendix B. Extra Diagnostic Figures

![Full geometry correlation figure](final_assets/fig5_strongest_geometry_correlations.png)

**Appendix Figure B1.** Full dense geometry-correlation figure. It is retained for provenance and detailed labels; the simplified top-10 version is used in the main text.


![Bunny epsilon-distance RMSE heatmap](final_assets/fig9a_bunny_epsilon_distance_rmse.png)

**Appendix Figure B2.** Bunny epsilon-distance RMSE heatmap, showing how epsilon sensitivity varies by nearest-distance proxy bin.

![Spot epsilon-distance RMSE heatmap](final_assets/fig9b_spot_epsilon_distance_rmse.png)

**Appendix Figure B3.** Spot epsilon-distance RMSE heatmap, showing stronger near-boundary sensitivity at coarse epsilon.

![BVH versus brute force supporting benchmark](final_assets/fig12_bvh_vs_bruteforce_supporting.png)

**Appendix Figure B4.** BVH versus brute-force geometry-query benchmark. This is supporting engineering evidence for acceleration inside the WoSt implementation; it is not used as a solver-accuracy claim.

### Appendix C. File Provenance

See `reports/final_report_provenance.md` for source files, generated assets, and where each is used.
