# Geometry Regression Summary

Model: `error ~ nearest_distance + local_normal_variation + local_edge_mean + local_aspect_ratio`.

These regressions are descriptive only and should not be read causally.

- bunny abs_error: n=8, R2=0.251
- Not enough rows for spot abs_error.

| Mesh | Term | standardized beta | R2 | n |
|---|---|---:|---:|---:|
| bunny | nearest_distance_proxy_norm | 0.0055613 | 0.251 | 8 |
| bunny | local_normal_variation | -0.00971416 | 0.251 | 8 |
| bunny | local_edge_mean_norm | -0.00341674 | 0.251 | 8 |
| bunny | local_aspect_ratio | 0.00768547 | 0.251 | 8 |
