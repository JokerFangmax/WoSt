# Controlled Geometry Findings

This report extends the correlation-style geometry analysis with distance-controlled query bins and epsilon-by-distance sweeps. Language is intentionally cautious: these experiments reduce confounding but do not prove causality.

## Stable Pointwise Observations

- Near-boundary queries are harder: mean Neumann error, mean steps, and sample variance are largest in the closest distance bins.
- Coarse epsilon increases boundary sensitivity, especially in close-distance bins.
- Nearest-surface distance remains a proxy; it is useful but not a full geometric explanation.

## Controlled Cross-Mesh Findings

| Distance bin | Bunny abs error | Spot abs error | Spot / Bunny | Bunny steps | Spot steps |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.041954 | 0.15954 | 3.803 | 81.750 | 192.906 |
| 2 | 0.029157 | 0.10611 | 3.639 | 55.688 | 75.750 |
| 3 | 0.020466 | 0.077553 | 3.789 | 28.406 | 28.219 |

Across matched distance bins, Spot's mean absolute Neumann error is about `3.74x` Bunny's. That supports remaining mesh, shape, reflection, or normal-error effects after reducing the query-distance confounder.

## Epsilon x Distance Findings

| Mesh | Distance bin | epsilon | walks | RMSE | mean bias | mean steps |
|---|---:|---:|---:|---:|---:|---:|

Interpretation:

- If RMSE and bias decrease sharply as epsilon decreases in close bins, the error is boundary/epsilon driven.
- If close-bin error remains high at small epsilon and high walks, the residual is likely tied to geometry, reflection behavior, normals, or shape-specific path behavior.

## Partial Correlation and Regression

| Mesh | Feature | Pearson | Spearman | Partial r controlling distance | n |
|---|---|---:|---:|---:|---:|
| bunny | nearest_distance_proxy_norm | -0.018 | -0.190 |  | 8 |
| bunny | local_normal_variation | -0.360 | -0.571 | -0.379 | 8 |
| bunny | local_edge_mean_norm | 0.281 | 0.286 | 0.332 | 8 |
| bunny | local_aspect_ratio | 0.158 | 0.095 | 0.178 | 8 |
| bunny | local_quality | 0.029 | 0.095 | 0.039 | 8 |
| spot | nearest_distance_proxy_norm | -0.535 | -0.486 |  | 6 |
| spot | local_normal_variation | -0.363 | 0.143 | nan | 6 |
| spot | local_edge_mean_norm | 0.127 | -0.200 | nan | 6 |
| spot | local_aspect_ratio | 0.711 | 0.714 | nan | 6 |
| spot | local_quality | -0.646 | -0.714 | nan | 6 |

Regression summaries:

- bunny abs_error: n=8, R2=0.251
- Not enough rows for spot abs_error.

After controlling for boundary proximity, local normal variation still has additional explanatory power in this descriptive run.

| Mesh | Term | standardized beta | R2 | n |
|---|---|---:|---:|---:|
| bunny | nearest_distance_proxy_norm | 0.0055613 | 0.251 | 8 |
| bunny | local_normal_variation | -0.0097142 | 0.251 | 8 |
| bunny | local_edge_mean_norm | -0.0034167 | 0.251 | 8 |
| bunny | local_aspect_ratio | 0.0076855 | 0.251 | 8 |

Random forest feature importance was skipped because scikit-learn was not available or there were not enough rows.

## Remeshed Variant Support

The pipeline records `mesh_variant` for every row. Supported config values include `original`, `decimated`, `subdivided`, and `smoothed_normals`; this script does not generate those meshes automatically.

Same-shape remeshed variants are needed to separate mesh-quality effects from shape and query-distribution effects. Bunny-vs-Spot comparisons still mix shape, scale, mesh density, local feature size, and query distribution.

## Remaining Limitations

- Nearest-surface distance is a nearest-centroid proxy, not an exact signed distance or local feature-size distance.
- Matching distance bins reduces one confounder but does not make Bunny and Spot the same shape.
- Bunny and Spot alone are not enough for universal geometry conclusions.
- Stronger causality requires remeshed variants of the same shape or synthetic stress-test meshes.

## Files

- `distance_controlled_neumann.csv`
- `distance_controlled_bias.csv`
- `epsilon_distance_sweep.csv`
- `controlled_geometry_correlations.csv`
- `geometry_regression_summary.md`
- `epsilon_distance_heatmaps/`
- `plots/`
- `controlled_geometry_config.json`
