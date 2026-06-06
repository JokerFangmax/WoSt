# WoSt Experiment Pipeline Audit

Project framing:

> A Self-Diagnostic and Optimization-Aware WoSt Solver: Reproducing WoSt and Systematically Investigating Its Behavior Across Complex Meshes, Dirichlet/Neumann Boundaries, Epsilon, Sampling Variance, Path Length, and Geometric Query Cost.

The base Walk-on-Stars estimator is not claimed as the sole innovation. The contribution is a C++ WoSt system that reproduces and compares against Zombie on complex meshes, diagnoses boundary bias through epsilon-vs-half-epsilon tests, visualizes random walk paths, predicts sample allocation from pilot variance, and exposes optimization diagnostics such as antithetic sampling and lazy star-radius refinement.

## Current Structure

- `main.cpp` contains the C++ CLI modes for convergence, epsilon, mixed Neumann, geometry timing, live path tracing, boundary-bias detection, variance-adaptive sampling, and optimization diagnostics.
- `src/WoStKernel.cpp` implements reflection, epsilon stopping, antithetic direction pairing, adaptive stopping, lazy star-radius refinement, and trace-event recording.
- `src/WoStGeometryBackend.cpp` implements tiny_bvh closest-point/ray queries, brute-force helper comparisons, normals, silhouettes, and star-radius support.
- Existing plotting scripts generate benchmark, optimization, boundary-bias, adaptive, and live-trace figures.
- New pipeline scripts add config-driven orchestration, epsilon-by-walk sweeps, geometry-sensitive post-processing, and cautious markdown report generation.

## Experiment Notes

### 1. Dirichlet Accuracy

RMSE is the primary metric because the manufactured solution `u=x+y+z` gives pointwise ground truth and RMSE exposes Monte Carlo convergence. Mean steps and runtime should also be reported because they explain cost. In Dirichlet-only problems, steps/time are meaningful but secondary; they become more diagnostic in Neumann/reflection-heavy settings where path length and boundary interactions dominate.

### 2. Mixed Neumann

WoSt and Zombie can differ because of implementation-level choices in boundary handling, reflection, epsilon stopping, star-radius computation, geometry-query backend, normal usage, and path termination. WoSt often uses fewer mean steps because reflected paths and star-radius handling can terminate or move through the domain with shorter trajectories. RMSE is mesh-sensitive and can depend on scale, local feature size, normal variation, curvature, triangle quality, concavity, narrow gaps, boundary proximity, and resolution.

### 3. Epsilon Sweep

The epsilon sweep probes both Monte Carlo variance and boundary bias. Increasing walks tests variance reduction; decreasing epsilon tests boundary sensitivity. If RMSE does not improve with more walks, the result likely has a bias or geometry-driven floor. If RMSE changes strongly with epsilon, the result is epsilon-bias-sensitive. The new `case` mode supports a 2D epsilon-by-walk sweep, and `plot_full_experiment_suite.py` classifies each boundary mode as variance-dominated, epsilon-bias-dominated, or residual-bias/geometry-dominated with a simple heuristic.

### 4. Boundary Bias Detector

The detector compares `u_epsilon` and `u_epsilon/2`. Absolute bias shows sensitivity magnitude; normalized bias compares that discrepancy to estimated Monte Carlo standard error. The improved summary includes mean, max, p95 bias, mean/max/p95 normalized bias, and percentage above the warning threshold. The plotter adds side-by-side maps and histograms. Epsilon sensitivity is expected near Neumann boundaries, high curvature, rapidly changing normals, thin structures, concave regions, narrow gaps, poor triangle quality, or small local feature size relative to epsilon.

### 5. Variance-Predicted Adaptive Sampling

Pilot samples are initial fixed walks used to estimate pointwise variance. The implementation predicts approximately `N_i = ceil(variance_i / tau^2)`, clamped by min/max samples. Tau controls Monte Carlo standard error, not total RMSE; epsilon bias, Neumann bias, geometry error, and normal error may remain. Meshes with high path variance can hit max samples across many points, which should be reported as a warning rather than a failure.

### 6. Antithetic Sampling

The current implementation pairs unit-sphere directions `d` and `-d` from a shared direction tape and averages the two walk estimates. This is a variance-reduction diagnostic. It can reduce sample variance and sometimes RMSE, but it cannot correct epsilon or boundary bias.

### 7. Lazy Star-Radius Refinement

Full exact refinement evaluates closest-boundary and silhouette distances for the safe star radius. Lazy refinement uses a faster boundary-distance proxy until the walk is close to a threshold or suspicious inner/outer distance ratio. It reduces geometric query overhead, but it could hurt accuracy in sharp visibility changes, narrow gaps, high curvature, or nonconvex regions if a skipped silhouette would have constrained the radius.

### 8. Live Walk Path Debugger

Trace rows record walk id, step id, position, radius, event type, and boundary type. The plot now color-codes starts, normal sphere steps, Neumann reflections, Dirichlet hits, max-step termination, and end points. This is suitable for a live demo and for explaining how paths interact with boundaries.

### 9. BVH Acceleration

tiny_bvh accelerates closest-boundary and ray-boundary queries used by WoSt. The clean comparison is WoSt-only tiny_bvh versus brute-force triangle queries on the same query set. Zombie timing should be described as application-level timing if it goes through Python scripts, not as a pure FCPW-versus-tiny_bvh backend comparison.

## Geometry-Sensitive Analysis

The new geometry module computes mesh scale, face/edge statistics, triangle quality, aspect ratio, normal variation, and query-local proxies such as nearest-surface distance, local triangle size, and local normal variation. It correlates these features with available error, epsilon sensitivity, pilot variance, and samples-used columns.

Use cautious language:

- In tested meshes, higher normal variation may correlate with larger epsilon sensitivity.
- Adaptive sampling assigns more samples to higher pilot-variance points; these often correlate with geometry-sensitive regions.
- These are empirical correlations, not universal theoretical claims.

## Safe Claims

- WoSt and Zombie agree closely on clean Dirichlet benchmarks when configured consistently.
- WoSt follows the expected Monte Carlo convergence trend.
- Mixed Neumann behavior is more geometry-sensitive than Dirichlet behavior.
- WoSt is faster in mixed Neumann tests when it uses shorter reflected paths.
- WoSt's Neumann accuracy advantage is mesh-dependent.
- Coarse epsilon can cause severe boundary bias.
- Epsilon-vs-half-epsilon comparison detects boundary sensitivity.
- Antithetic sampling reduces variance but does not correct bias.
- Lazy star-radius refinement reduces geometric cost in these diagnostics.
- Variance-predicted adaptive sampling should be tuned per mesh and target error.

## Avoid Overclaiming

- Do not claim WoSt is always more accurate than Zombie.
- Do not claim adaptive sampling always reduces mean samples to a fixed range.
- Do not claim pure backend-only Zombie FCPW vs WoSt tiny_bvh timing if Zombie timing goes through Python scripts.
- Do not claim million-triangle scalability without a million-triangle experiment.
- Do not claim Bunny/Spot geometry conclusions are universal.
