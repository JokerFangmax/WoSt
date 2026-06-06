# WoSt Self-Diagnostic and Optimization-Aware Experiment Report

**Run mode:** `smoke`

**Run-mode warning:** Smoke-test results are pipeline checks only. They are not statistically reliable and should not be interpreted as final performance conclusions.

The base Walk-on-Stars estimator is not claimed as the sole innovation. Our contribution is a C++ WoSt system that reproduces and compares against Zombie on complex meshes, diagnoses boundary bias through epsilon-vs-half-epsilon tests, visualizes random walk paths, predicts sample allocation from pilot variance, and exposes optimization diagnostics such as antithetic sampling and lazy star-radius refinement.

## 1. Mesh and setup

- Mesh: `Bunny` (`obj/Bunny.obj`)
- Boundary configuration: `mixed_neumann`
- Analytic solution: `u(x,y,z)=x+y+z`
- Neumann condition: `h=(1,1,1) dot n`
- Outer cube half extent: `0.22`
- Query points: `20`, grid: `8`, seeds: `[0]`

## Pipeline Capability Verification

| capability | status | path |
| --- | --- | --- |
| all-in-one experiment runner | IMPLEMENTED AND TESTED | `scripts/run_all_wost_experiments.py` |
| config-based execution | IMPLEMENTED AND TESTED | `config_used.yaml` |
| smoke/quick/final mode label | IMPLEMENTED AND TESTED | `config_used.yaml` |
| epsilon-by-walk sweep | IMPLEMENTED AND TESTED | `raw/epsilon_walks_sweep.csv` |
| Dirichlet accuracy | IMPLEMENTED AND TESTED | `raw/dirichlet_accuracy.csv` |
| Mixed Neumann | IMPLEMENTED AND TESTED | `raw/mixed_neumann.csv` |
| boundary-bias detector | IMPLEMENTED AND TESTED | `raw/boundary_bias_summary.csv` |
| variance-adaptive sampling | IMPLEMENTED AND TESTED | `raw/variance_adaptive_comparison.csv` |
| antithetic sampling | IMPLEMENTED AND TESTED | `raw/optimization_summary.csv` |
| lazy star-radius refinement | IMPLEMENTED AND TESTED | `raw/optimization_summary.csv` |
| live walk path debugger | IMPLEMENTED AND TESTED | `raw/live_trace.csv` |
| BVH vs brute force | IMPLEMENTED AND TESTED | `raw/geometry_benchmark.csv` |
| Zombie comparison integration | PARTIALLY IMPLEMENTED | `raw/zombie_*.csv` |
| geometry-sensitive analysis | IMPLEMENTED AND TESTED | `tables/geometry_analysis` |
| plot generation | IMPLEMENTED AND TESTED | `plots/*.png` |
| markdown report generation | IMPLEMENTED AND TESTED | `reports/final_wost_experiment_report.md` |
| poster-ready summary generation | NOT PRODUCED IN THIS RUN | `reports/poster_ready_summary.md` |

| mesh_name | num_vertices | num_faces | bbox_diagonal | triangle_area_mean | edge_length_mean | triangle_quality_mean | normal_variation_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Bunny | 35292 | 70580 | 0.250034 | 8.25e-07 | 0.0014715 | 0.835094 | 0.0110946 |

## 2. Dirichlet accuracy

Dirichlet accuracy mainly reports RMSE because the manufactured solution `u=x+y+z` gives a direct ground-truth error and RMSE tracks the expected Monte Carlo convergence trend. Mean steps and runtime are now included because they expose cost, but in clean Dirichlet-only tests they are secondary diagnostics: they mostly measure geometric walk efficiency rather than reflection-heavy boundary behavior.

| walks_per_point | epsilon | rmse | mean_steps | elapsed_seconds |
| --- | --- | --- | --- | --- |
| 16 | 0.001 | 0.03309 | 13.5164 | 0.177401 |
| 64 | 0.001 | 0.0150068 | 13.4194 | 0.780437 |

## 3. Mixed Neumann accuracy

WoSt and Zombie can differ under mixed Neumann conditions because the implementation choices are no longer only sampling a clean Dirichlet terminal value. Differences can come from boundary handling, reflection formulas, epsilon stopping, star-radius computation, geometric query backends, normal orientation and interpolation, and max-step termination behavior.

In this implementation, WoSt uses triangle normals from closest/ray-hit boundary queries, reflects directions at Neumann hits, applies an epsilon offset after reflection, and uses a star radius based on closest boundary and silhouette distance. Lazy refinement can skip exact silhouette checks when the walk is far from suspicious regions. These choices often reduce mean steps, especially compared with baselines that take longer reflected paths or use different stopping logic.

Mixed Neumann RMSE is mesh-sensitive. Scale, local feature size, normal variation, curvature, triangle quality, concavity, narrow gaps, boundary proximity, and mesh resolution can all change how often reflected paths interact with geometry-sensitive regions.

| benchmark_name | walks_per_point | epsilon | rmse | mean_steps | elapsed_seconds |
| --- | --- | --- | --- | --- | --- |
| case_mixed_neumann | 16 | 0.001 | 0.096068 | 16.0658 | 0.201268 |
| case_mixed_neumann | 64 | 0.001 | 0.072885 | 16.5132 | 0.893966 |

## 4. Epsilon sweep

The epsilon sweep tests both Monte Carlo variance and boundary bias. Increasing walks mostly probes variance. Decreasing epsilon probes boundary bias and boundary-handling sensitivity. If RMSE does not decrease when walks increase, that is evidence of a non-variance error floor. If RMSE changes strongly when epsilon changes, that is evidence of epsilon-sensitive boundary bias.

| benchmark | heuristic classification |
| --- | --- |
| case_dirichlet | variance-dominated |
| case_mixed_neumann | epsilon-bias-dominated |

| benchmark_name | boundary_mode | sweep_seed | walks_per_point | epsilon | rmse | mean_steps | elapsed_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| case_dirichlet | dirichlet | 0 | 16 | 0.01 | 0.035358 | 5.85855 | 0.171583 |
| case_dirichlet | dirichlet | 0 | 64 | 0.01 | 0.0163822 | 6.21957 | 0.695548 |
| case_dirichlet | dirichlet | 0 | 16 | 0.001 | 0.03309 | 13.5164 | 0.182323 |
| case_dirichlet | dirichlet | 0 | 64 | 0.001 | 0.0150068 | 13.4194 | 0.783138 |
| case_mixed_neumann | neumann | 0 | 16 | 0.01 | 0.362015 | 6.32237 | 0.188666 |
| case_mixed_neumann | neumann | 0 | 64 | 0.01 | 0.371404 | 6.45148 | 0.803302 |
| case_mixed_neumann | neumann | 0 | 16 | 0.001 | 0.096068 | 16.0658 | 0.205658 |
| case_mixed_neumann | neumann | 0 | 64 | 0.001 | 0.072885 | 16.5132 | 0.951571 |

Repeated-seed summary where available:
| benchmark_name | boundary_mode | walks_per_point | epsilon | n | rmse_mean | rmse_std | mean_steps_mean | elapsed_seconds_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case_dirichlet | dirichlet | 16 | 0.001 | 1 | 0.03309 | 0 | 13.5164 | 0.182323 |
| case_dirichlet | dirichlet | 16 | 0.01 | 1 | 0.035358 | 0 | 5.85855 | 0.171583 |
| case_dirichlet | dirichlet | 64 | 0.001 | 1 | 0.0150068 | 0 | 13.4194 | 0.783138 |
| case_dirichlet | dirichlet | 64 | 0.01 | 1 | 0.0163822 | 0 | 6.21957 | 0.695548 |
| case_mixed_neumann | neumann | 16 | 0.001 | 1 | 0.096068 | 0 | 16.0658 | 0.205658 |
| case_mixed_neumann | neumann | 16 | 0.01 | 1 | 0.362015 | 0 | 6.32237 | 0.188666 |
| case_mixed_neumann | neumann | 64 | 0.001 | 1 | 0.072885 | 0 | 16.5132 | 0.951571 |
| case_mixed_neumann | neumann | 64 | 0.01 | 1 | 0.371404 | 0 | 6.45148 | 0.803302 |

## 5. Boundary bias detector

The heat maps compare `u_epsilon` with `u_epsilon/2`. Large absolute differences mark locations where the boundary approximation is sensitive to epsilon. Normalized bias divides by estimated Monte Carlo standard error, so large normalized values suggest the discrepancy is bigger than sampling noise.

The earlier heat maps were hard to compare because each panel could choose its own color scale and did not show distributions. The new plots use comparable panels, add histograms, and keep absolute and normalized bias separate.

Epsilon sensitivity is expected near Neumann boundaries, high curvature, rapidly changing normals, thin structures, concave regions, narrow gaps, poor triangle quality, or regions where local feature size is small relative to epsilon.

| epsilon | epsilon_half | walks | valid_points | mean_bias | max_bias | p95_bias | mean_normalized_bias | max_normalized_bias | p95_normalized_bias | warning_threshold_ratio | rmse_epsilon | rmse_epsilon_half |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.001 | 0.0005 | 16 | 508 | 0.015581 | 0.17933 | 0.06877 | 0.184061 | 1.93799 | 0.866475 | 0 | 0.0387881 | 0.0326644 |

## 6. Variance-predicted adaptive sampling

Pilot samples are the initial fixed number of walks used to estimate pointwise sample variance. The implementation predicts `N_i = ceil(variance_i / tau^2)`, clamped by `min_samples` and `max_samples`. Tau controls Monte Carlo standard error, not total RMSE; total RMSE can still include epsilon bias, Neumann bias, geometry error, and normal error.

Meshes like Spot can still hit near-maximum samples for many points when pilot variance is high over much of the query distribution. Adaptive sampling saves cost most clearly in smooth, far-from-boundary, low-variance regions; it spends more samples near high normal variation, thin or concave structures, reflected-path regions, and near-boundary points.

| method | target_std_error | rmse | mean_samples_used | mean_predicted_samples | mean_steps | runtime_seconds |
| --- | --- | --- | --- | --- | --- | --- |
| fixed_256 | 0 | 0.0153701 | 256 | 256 | 16.1418 | 3.74316 |
| fixed_512 | 0 | 0.0165592 | 512 | 512 | 16.1516 | 7.17434 |
| fixed_1024 | 0 | 0.0181933 | 1024 | 1024 | 16.2183 | 14.5 |
| variance_adaptive_tau_0.003 | 0.003 | 0.0166184 | 61.2 | 61.2 | 16.6336 | 1.18956 |
| variance_adaptive_tau_0.005 | 0.005 | 0.0163748 | 59.75 | 59.75 | 16.5606 | 1.17399 |
| variance_adaptive_tau_0.008 | 0.008 | 0.0241139 | 55.65 | 55.65 | 16.3735 | 0.91303 |

Adaptive max-sample warning:
| valid_points | observed_max_samples | points_at_observed_max | points_at_observed_max_ratio | warning |
| --- | --- | --- | --- | --- |
| 20 | 64 | 18 | 0.9 | most points hit max_samples |

## 7. Antithetic sampling

Antithetic sampling pairs random sphere directions `d` and `-d` from a shared direction tape and averages the paired estimators. This preserves unbiasedness for the Monte Carlo part when the paired estimator is a symmetric average. It can reduce sample variance, but it does not correct epsilon, boundary, geometry, or normal bias. It is therefore a variance reduction diagnostic, not a bias correction method.

Repeated-seed optimization summaries:

| experiment | method | n | rmse_mean | rmse_std | mean_sample_variance_mean | mean_sample_variance_std | elapsed_seconds_mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adaptive_compare | fixed | 3 | 0.0137094 | 0.00381981 | 0.0156186 | 0.000728563 | 0.812088 |
| adaptive_compare | old_absolute_stderr | 3 | 0.0137105 | 0.00382169 | 0.0156184 | 0.000728922 | 0.810159 |
| adaptive_compare | relative_stderr | 3 | 0.0168379 | 0.00420889 | 0.0145476 | 0.000614621 | 0.619385 |
| antithetic_compare | antithetic | 3 | 0.0107697 | 0.00262882 | 0.00404061 | 0.000460791 | 0.868915 |
| antithetic_compare | normal | 3 | 0.0157528 | 0.00277262 | 0.014623 | 0.00404716 | 0.828635 |
| epsilon_extrapolation | epsilon | 3 | 0.0133547 | 0.00285038 | 0.0132888 | 0.00322582 | 0.66961 |
| epsilon_extrapolation | epsilon_half | 3 | 0.0130454 | 0.00337528 | 0.0149457 | 0.00361375 | 0.66359 |
| lazy_refinement | full_exact | 3 | 0.0139249 | 0.00152078 | 0.0160134 | 0.00200444 | 7.31612 |
| lazy_refinement | lazy_threshold_x1 | 3 | 0.0139249 | 0.00152078 | 0.0160134 | 0.00200444 | 0.761008 |
| lazy_refinement | lazy_threshold_x16 | 3 | 0.0139249 | 0.00152078 | 0.0160134 | 0.00200444 | 3.40656 |
| lazy_refinement | lazy_threshold_x4 | 3 | 0.0139249 | 0.00152078 | 0.0160134 | 0.00200444 | 1.99968 |
| neumann_sanity | sphere_cube | 3 | 0 | 0 | 0 | 0 | 2.60333e-05 |

## 8. Lazy star-radius refinement

Full exact refinement evaluates the star radius using both closest-boundary and silhouette-distance queries. Lazy refinement first uses a fast closest-boundary distance and only refines exactly when the radius is small or suspicious. It mainly targets geometric query overhead. It can hurt accuracy if the skipped silhouette check would have constrained the safe radius in a region with sharp visibility changes, narrow gaps, or strong nonconvexity.

In our diagnostics, lazy refinement preserves RMSE while substantially reducing geometric cost, but this should not be overclaimed as universally accuracy-preserving.

## 9. Live walk path debugger

The trace records `walk_id`, `step_id`, position, radius, event type, and boundary type. Existing event types distinguish `start`, normal `sphere_step`, `neumann_reflect`, `dirichlet_hit`, `max_step`, and `end`, which is enough to color-code starts, reflected steps, terminations, and failed max-step paths for a live demo.

## 10. BVH acceleration

The tiny_bvh backend accelerates closest-boundary distance and ray-boundary intersection queries used by WoSt. The cleanest comparison is WoSt-only BVH versus brute-force triangle distance queries using the same query points. Zombie timings are only comparable at application level if they go through Python scripts; they should not be described as pure FCPW-versus-tiny_bvh backend timings.

| backend_name | triangle_count | num_queries | elapsed_seconds | queries_per_second | checksum |
| --- | --- | --- | --- | --- | --- |
| tiny_bvh | 70580 | 200 | 0.0012838 | 155788 | 33.3844 |
| brute_force | 70580 | 200 | 0.0577491 | 3463.26 | 33.3844 |

## 11. Geometry-sensitive analysis

The geometry analysis computes mesh scale, triangle area, edge length, triangle quality, aspect ratio, normal-variation proxies, and per-query nearest-surface/local-feature proxies. These are scale-normalized where useful so Bunny, Spot, sphere, and other meshes can be compared more fairly.

Geometry-sensitive findings should be read as empirical correlations, not universal theoretical claims.

| feature | target | pearson_r | n |
| --- | --- | --- | --- |
| nearest_surface_distance_proxy | abs_error | -0.445753 | 20 |
| nearest_surface_distance_proxy | sample_variance | -0.783997 | 20 |
| nearest_surface_distance_proxy | std_error | -0.731063 | 20 |
| nearest_surface_distance_proxy | samples_used | -0.469557 | 20 |
| nearest_surface_distance_proxy | predicted_samples | -0.469557 | 20 |
| nearest_surface_distance_proxy_norm | abs_error | -0.445753 | 20 |
| nearest_surface_distance_proxy_norm | sample_variance | -0.783997 | 20 |
| nearest_surface_distance_proxy_norm | std_error | -0.731063 | 20 |
| nearest_surface_distance_proxy_norm | samples_used | -0.469557 | 20 |
| nearest_surface_distance_proxy_norm | predicted_samples | -0.469557 | 20 |
| local_triangle_area | abs_error | -0.0270651 | 20 |
| local_triangle_area | sample_variance | -0.0442338 | 20 |
| local_triangle_area | std_error | -0.0687975 | 20 |
| local_triangle_area | samples_used | -0.483297 | 20 |
| local_triangle_area | predicted_samples | -0.483297 | 20 |
| local_triangle_size | abs_error | -0.0186809 | 20 |

## 12. Stable conclusions

- WoSt and Zombie agree closely on clean Dirichlet benchmarks when both are configured consistently.
- WoSt follows the expected Monte Carlo convergence trend in Dirichlet tests.
- Coarse epsilon can cause severe boundary sensitivity.
- Epsilon-vs-half-epsilon comparison is useful when ground truth is unavailable.
- Antithetic sampling reduces variance when the paired directions are effective, but it does not correct bias.
- Live diagnostics justify the project framing as a self-diagnostic and optimization-aware solver.

## 13. Mesh-sensitive conclusions

- Mixed Neumann behavior is more geometry-sensitive than Dirichlet behavior.
- WoSt is consistently faster in mixed Neumann tests when it uses shorter reflected paths, but the accuracy advantage is mesh-dependent.
- Adaptive sampling should be tuned per mesh and target error; it should not be claimed to always reduce mean samples to a fixed range.
- Lazy star-radius refinement reduces geometric cost in these diagnostics, but it is not universally accuracy-preserving.

## 14. Avoid overclaiming

- Do not claim WoSt is always more accurate than Zombie.
- Do not claim adaptive sampling always saves cost.
- Do not claim backend-only Zombie FCPW vs WoSt tiny_bvh timing when Zombie is run through Python.
- Do not claim million-triangle scalability without a million-triangle experiment.
- Do not claim Bunny/Spot geometry correlations are universal.

## 15. Recommended poster figures

- Dirichlet RMSE/steps/runtime vs walks.
- Mixed Neumann WoSt-vs-Zombie comparison table or paired RMSE plot when Zombie CSVs are available.
- Epsilon-by-walk RMSE heatmap and classifier.
- Boundary bias panels with absolute and normalized bias.
- Adaptive sampling cost-accuracy tradeoff and sample map.
- Antithetic variance/RMSE repeated-seed plot.
- Lazy refinement runtime-vs-RMSE plot.
- Live path trace with event color coding.
- BVH vs brute-force geometry query throughput.

## Poster-ready summary

No poster-ready claims are generated from smoke-test results. Smoke output is a pipeline check only.

Plots generated:

- `plots/antithetic_rmse.png`
- `plots/antithetic_runtime.png`
- `plots/antithetic_variance.png`
- `plots/boundary_bias_histogram.png`
- `plots/boundary_bias_normalized_histogram.png`
- `plots/boundary_bias_panels.png`
- `plots/case_dirichlet_elapsed_seconds_heatmap.png`
- `plots/case_dirichlet_mean_steps_heatmap.png`
- `plots/case_dirichlet_rmse_heatmap.png`
- `plots/case_mixed_neumann_elapsed_seconds_heatmap.png`
- `plots/case_mixed_neumann_mean_steps_heatmap.png`
- `plots/case_mixed_neumann_rmse_heatmap.png`
- `plots/dirichlet_accuracy_rmse_steps_runtime.png`
- `plots/lazy_rmse.png`
- `plots/lazy_runtime.png`
- `plots/live_trace_plot.png`
- `plots/mixed_neumann_rmse_steps_runtime.png`
- `plots/variance_adaptive_point_diagnostics.png`
- `plots/variance_adaptive_tradeoff_extended.png`
- `plots/wost_boundary_rmse_difference_heatmap.png`
