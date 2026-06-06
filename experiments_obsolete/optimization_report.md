# WoSt Optimization Experiments

This report is generated from `experiments/optimization_summary.csv`; plots and tables use the latest three appended rows for each experiment/method pair.

## Reproducibility

Each comparison uses Common Random Numbers: query points come from the experiment seed, and each point uses `SeedFor(experiment_seed, point_index, stream)` for its random walk stream. Methods in the same comparison reuse the same experiment seed and point index stream.

Default command:

```powershell
.\build\Release\wost.exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001
.\.venv\Scripts\python.exe .\scripts\plot_optimization_experiments.py
```

## Key Results

| experiment | method | RMSE | MAE | mean samples | runtime |
| --- | --- | ---: | ---: | ---: | ---: |
| adaptive_compare | fixed | 0.0767052 +/- 0.00907 | 0.0550516 +/- 0.00725 | 32 +/- 0 | 0.0716888 +/- 0.00804 |
| adaptive_compare | old_absolute_stderr | 0.0767052 +/- 0.00907 | 0.0550515 +/- 0.00725 | 31.7333 +/- 0.462 | 0.075861 +/- 0.0133 |
| adaptive_compare | relative_stderr | 0.0941641 +/- 0.0237 | 0.0712685 +/- 0.017 | 21.8099 +/- 0.281 | 0.0532781 +/- 0.00555 |
| antithetic_compare | antithetic | 0.0524905 +/- 0.0107 | 0.039686 +/- 0.00844 | 32 +/- 0 | 0.0707135 +/- 0.00431 |
| antithetic_compare | normal | 0.0711783 +/- 0.00934 | 0.0551952 +/- 0.00517 | 32 +/- 0 | 0.0733861 +/- 0.00807 |
| epsilon_extrapolation | epsilon | 0.0728671 +/- 0.0111 | 0.0559176 +/- 0.00958 | 32 +/- 0 | 0.0556032 +/- 0.00414 |
| epsilon_extrapolation | epsilon_half | 0.0782365 +/- 0.0165 | 0.0606246 +/- 0.00911 | 32 +/- 0 | 0.0545992 +/- 0.00486 |
| lazy_refinement | full_exact | 0.0812076 +/- 0.0137 | 0.0568162 +/- 0.00695 | 32 +/- 0 | 0.569725 +/- 0.0366 |
| lazy_refinement | lazy_threshold_x1 | 0.0812076 +/- 0.0137 | 0.0568162 +/- 0.00695 | 32 +/- 0 | 0.0692144 +/- 0.0039 |
| lazy_refinement | lazy_threshold_x16 | 0.0812076 +/- 0.0137 | 0.0568162 +/- 0.00695 | 32 +/- 0 | 0.239115 +/- 0.0327 |
| lazy_refinement | lazy_threshold_x4 | 0.0812076 +/- 0.0137 | 0.0568162 +/- 0.00695 | 32 +/- 0 | 0.141874 +/- 0.00892 |
| neumann_sanity | sphere_cube | 0.155795 +/- 0.027 | 0.111169 +/- 0.0244 | 32 +/- 0 | 0.0639536 +/- 0.013 |

## Notes

- Adaptive sampling now supports relative standard error: `std_error / max(abs(mean), rse_eps) < target_rse`, while preserving `min_samples`, `max_samples`, and `batch_size`.
- The old absolute-standard-error adaptive mode is still available as `old_absolute_stderr` in the adaptive comparison.
- Antithetic sampling runs paired walks using direction streams `d` and `-d`; odd sample limits fall back to one final unpaired walk.
- Lazy star-radius refinement records total, fast-only, and exact refinement query counts. Full exact mode sets `useLazyStarRefinement=false`.
- Epsilon extrapolation compares `epsilon=1e-2` with `epsilon/2`; large pointwise differences indicate likely boundary bias and can motivate adaptive epsilon refinement near complex Neumann boundaries.
- The Neumann sanity test generates an inner sphere OBJ and checks mesh normals against the expected radial normal before running the sphere/cube solve.

## Figures

- `experiments/figures/adaptive_rmse_errorbars.png`
- `experiments/figures/adaptive_samples_errorbars.png`
- `experiments/figures/antithetic_pointwise_variance.png`
- `experiments/figures/antithetic_rmse_errorbars.png`
- `experiments/figures/antithetic_variance_errorbars.png`
- `experiments/figures/epsilon_rmse_errorbars.png`
- `experiments/figures/epsilon_sensitivity_histogram.png`
- `experiments/figures/epsilon_sensitivity_spatial_xy.png`
- `experiments/figures/lazy_refinement_ratio_errorbars.png`
- `experiments/figures/lazy_refinement_spatial_xy.png`
- `experiments/figures/lazy_rmse_errorbars.png`
- `experiments/figures/lazy_tradeoff_rmse_vs_refinement.png`
- `experiments/figures/neumann_normal_diagnostics.png`
- `experiments/figures/neumann_sanity_rmse_errorbars.png`
