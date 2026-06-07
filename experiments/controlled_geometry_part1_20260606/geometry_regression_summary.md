# Geometry Regression Summary

Model: `error ~ nearest_distance + local_normal_variation + local_edge_mean + local_aspect_ratio`.

These regressions are descriptive only and should not be read causally.

- bunny abs_error: n=90, R2=0.333
- spot abs_error: n=70, R2=0.324

| Mesh | Term | standardized beta | R2 | n |
|---|---|---:|---:|---:|
| bunny | nearest_distance_proxy_norm | -0.00958725 | 0.333 | 90 |
| bunny | local_normal_variation | -0.0028928 | 0.333 | 90 |
| bunny | local_edge_mean_norm | 0.000998054 | 0.333 | 90 |
| bunny | local_aspect_ratio | 0.00185361 | 0.333 | 90 |
| spot | nearest_distance_proxy_norm | -0.0461301 | 0.324 | 70 |
| spot | local_normal_variation | -0.00595722 | 0.324 | 70 |
| spot | local_edge_mean_norm | 0.00763373 | 0.324 | 70 |
| spot | local_aspect_ratio | -0.00143793 | 0.324 | 70 |
