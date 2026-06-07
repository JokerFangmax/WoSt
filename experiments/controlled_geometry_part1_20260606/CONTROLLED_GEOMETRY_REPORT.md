# Controlled Geometry Findings

This report extends the correlation-style geometry analysis with distance-controlled query bins and epsilon-by-distance sweeps. Language is intentionally cautious: these experiments reduce confounding but do not prove causality.

## Stable Pointwise Observations

- Near-boundary queries are harder: mean Neumann error, mean steps, and sample variance are largest in the closest distance bins.
- Coarse epsilon increases boundary sensitivity, especially in close-distance bins.
- Nearest-surface distance remains a proxy; it is useful but not a full geometric explanation.

## Controlled Cross-Mesh Findings

| Distance bin | Bunny abs error | Spot abs error | Spot / Bunny | Bunny steps | Spot steps |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.035723 | 0.12087 | 3.383 | 99.088 | 126.841 |
| 2 | 0.015223 | 0.056091 | 3.685 | 61.227 | 46.831 |
| 3 | 0.011952 | 0.016388 | 1.371 | 37.956 | 28.322 |

Across matched distance bins, Spot's mean absolute Neumann error is about `2.81x` Bunny's. That supports remaining mesh, shape, reflection, or normal-error effects after reducing the query-distance confounder.

## Epsilon x Distance Findings

| Mesh | Distance bin | epsilon | walks | RMSE | mean bias | mean steps |
|---|---:|---:|---:|---:|---:|---:|
| bunny | 1 | 1e-04 | 256 | 0.042618 | 0.015595 | 99.088 |
| bunny | 2 | 1e-04 | 256 | 0.018649 | 0.01469 | 61.227 |
| bunny | 3 | 1e-04 | 256 | 0.014692 | 0.012907 | 37.956 |
| bunny | 4 | 1e-04 | 256 | 0.0083849 | 0.0068745 | 26.626 |
| spot | 1 | 1e-04 | 256 | 0.16601 | 0.051998 | 126.841 |
| spot | 2 | 1e-04 | 256 | 0.074751 | 0.034829 | 46.831 |
| spot | 3 | 1e-04 | 256 | 0.022299 | 0.023656 | 28.322 |

Interpretation:

- If RMSE and bias decrease sharply as epsilon decreases in close bins, the error is boundary/epsilon driven.
- If close-bin error remains high at small epsilon and high walks, the residual is likely tied to geometry, reflection behavior, normals, or shape-specific path behavior.

## Partial Correlation and Regression

| Mesh | Feature | Pearson | Spearman | Partial r controlling distance | n |
|---|---|---:|---:|---:|---:|
| bunny | nearest_distance_proxy_norm | -0.550 | -0.605 |  | 90 |
| bunny | local_normal_variation | -0.208 | -0.248 | -0.156 | 90 |
| bunny | local_edge_mean_norm | 0.020 | 0.114 | 0.100 | 90 |
| bunny | local_aspect_ratio | -0.050 | -0.054 | 0.054 | 90 |
| bunny | local_quality | 0.150 | 0.139 | -0.001 | 90 |
| spot | nearest_distance_proxy_norm | -0.552 | -0.616 |  | 70 |
| spot | local_normal_variation | -0.196 | -0.035 | -0.127 | 70 |
| spot | local_edge_mean_norm | 0.020 | 0.065 | 0.144 | 70 |
| spot | local_aspect_ratio | 0.083 | 0.104 | -0.007 | 70 |
| spot | local_quality | -0.027 | -0.070 | 0.050 | 70 |

Regression summaries:

- bunny abs_error: n=90, R2=0.333
- spot abs_error: n=70, R2=0.324

After controlling for boundary proximity, local normal variation still has additional explanatory power in this descriptive run.

| Mesh | Term | standardized beta | R2 | n |
|---|---|---:|---:|---:|
| bunny | nearest_distance_proxy_norm | -0.0095872 | 0.333 | 90 |
| bunny | local_normal_variation | -0.0028928 | 0.333 | 90 |
| bunny | local_edge_mean_norm | 0.00099805 | 0.333 | 90 |
| bunny | local_aspect_ratio | 0.0018536 | 0.333 | 90 |
| spot | nearest_distance_proxy_norm | -0.04613 | 0.324 | 70 |
| spot | local_normal_variation | -0.0059572 | 0.324 | 70 |
| spot | local_edge_mean_norm | 0.0076337 | 0.324 | 70 |
| spot | local_aspect_ratio | -0.0014379 | 0.324 | 70 |

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
