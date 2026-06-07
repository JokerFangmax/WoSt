# Live Demo Instructions for Poster Session

## Recommendation

Yes, this repository has material suitable for a poster-session live demo. The strongest choice is not a full experiment rerun, but a short diagnostic demo built around the existing Walk Path Debugger and precomputed live-trace figures.

Recommended demo stack:

1. **Primary live demo:** show the precomputed Spot mixed-Neumann live trace figure.
2. **Optional executable demo:** rerun a small `demo_point` trace if the audience asks to see something live.
3. **Backup visual:** use the 2D Python animation or GIF to explain the Walk-on-Stars intuition.

This matches the final report story: Dirichlet validation is clean, mixed Neumann behavior is geometry-sensitive, and live traces are qualitative diagnostics for reflection-heavy paths. The demo should not be presented as new statistical evidence or as a standalone mechanism explanation.

## What To Show

### Best Main Demo: Spot Mixed-Neumann Trace

Use:

```text
reports/final_assets/fig11_spot_live_trace.png
```

or the original:

```text
experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/live_trace_plot.png
```

Why this works:

- It comes from the same controlled experiment stack used in the final report.
- It shows a difficult mixed-Neumann path behavior directly.
- It connects to the poster claim that near-boundary Neumann queries can be high-risk.
- It is fast and reliable because it is already generated.

How to describe it:

> This trace shows a representative Spot mixed-Neumann query. The orange reflection markers show where the random walk interacts with the Neumann boundary. I use this only as a qualitative diagnostic: it helps explain what reflection-heavy paths look like, but it does not by itself establish the error mechanism.

### Secondary Demo: 2D Walk-on-Stars Animation

Use this if you need to quickly explain the basic algorithm to someone unfamiliar with WoSt:

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --animate
```

Backup GIF:

```text
live_demo.gif
```

Static backup:

```text
live_demo_poster.png
```

How to describe it:

> This 2D animation is a teaching demo. It shows the intuition of Walk-on-Stars: from a query point, the walk takes large safe steps until it reaches the boundary, and many such walks form a Monte Carlo estimate. My actual report experiments use the C++ 3D mesh solver, not this toy 2D disk.

### Optional Real C++ Demo

If you want to show that the C++ solver can generate a trace on demand, use the compact wrapper:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64
```

This runs:

- `build/Release/wost.exe --mode demo_point`
- one small mixed-Neumann trace
- `scripts/plot_live_trace.py`
- output to `results/live_trace_plot.png`
- animated output to `results/live_trace_walks.gif`

For a 3D view instead of the default x-y projection:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64 --view 3d
```

This writes:

```text
results/live_trace_plot_3d.png
results/live_trace_walks_3d.gif
results/live_trace_interactive_3d.html
```

Other available presets:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset dirichlet16
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset dirichlet256
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset antithetic64
```

Use `neumann64` for the report story. Use `dirichlet16` only if you want the simplest sanity-check demonstration.

The `neumann64` preset uses the Spot mesh, `cube=1.1`, and the report trace point `(0.8, 0.0, 0.2)`. The Dirichlet presets use the Bunny mesh with the smaller `cube=0.22` point `(0.05, 0.02, 0.08)`.

By default, the wrapper writes both a static PNG and an animated GIF. Use `--no-gif` if you only need the static plot.

Use `--view both` if you want the old 2D projection and the 3D view from the same run.

The interactive HTML view can be rotated with mouse drag controls, zoomed with the wheel, and played over time with the timeline controls. It includes the outer cube boundary plus the inner OBJ mesh, so it is the clearest option for explaining why the flat projection can be misleading.

## Suggested Poster-Session Flow

### 20-Second Version

1. Point to the Dirichlet RMSE figure.
2. Say: Dirichlet validates the Monte Carlo pipeline.
3. Point to the mixed-Neumann RMSE figure.
4. Say: mixed Neumann is harder and geometry-sensitive.
5. Show the Spot live trace.
6. Say: this is what a difficult reflection-heavy path can look like.

Script:

> The baseline Dirichlet test behaves normally, so the solver pipeline is credible. The hard part appears under mixed Neumann conditions, where paths interact with boundary normals. This live trace is a qualitative diagnostic from Spot: the reflections show why boundary proximity and surface geometry can matter. It is not statistical evidence by itself, but it makes the failure mode visible.

### 60-Second Version

1. Start with `fig1_dirichlet_rmse_vs_walks.png`.
2. Move to `fig2_mixed_neumann_rmse_vs_walks.png`.
3. Show `fig6_matched_bin_abs_error_ci.png`.
4. Show `fig11_spot_live_trace.png`.

Script:

> I first validate the solver on a manufactured Laplace problem with `u=x+y+z`. Under Dirichlet conditions, the Monte Carlo convergence looks normal. Under mixed Neumann conditions, the behavior changes: Spot remains much harder, and Zombie can outperform WoSt at high walk counts. The controlled distance-bin experiment reduces one confounder by comparing Bunny and Spot at matched nearest-distance proxy bins. Spot still has higher error in bins 1-3, but the gap shrinks with distance. This trace is a qualitative companion to that result: it shows the reflection-heavy behavior that can occur near difficult Neumann regions.

### 2-Minute Version

Use this when a professor stops and asks for the full story:

> The project asks how Walk-on-Stars behaves under mixed Neumann boundary conditions on mesh domains. The Dirichlet case is the sanity check: paths terminate at the boundary and evaluate a known boundary value, and the RMSE curves show ordinary Monte Carlo behavior.
>
> Mixed Neumann is different because the inner boundary prescribes normal derivative information. Paths can reflect or interact repeatedly with surface normals. That makes epsilon, boundary proximity, and mesh geometry important.
>
> The pointwise diagnostics show that normalized nearest-distance proxy is the strongest available predictor of error, variance, mean steps, and boundary-bias indicator. To reduce the query-distance confounder, I ran distance-controlled bins. Spot remains higher-error than Bunny in bins 1-3, but the gap shrinks with distance, so query distribution explains a large part of the previous difference.
>
> The live trace is my diagnostic view of the mechanism. It shows one representative reflection-heavy path on Spot. I do not treat this as statistical evidence by itself; it is useful because it lets us inspect what the solver is doing when Neumann boundary handling becomes difficult.

## Recommended Files To Keep Open

Open these before the poster session:

```text
reports/FINAL_COURSE_REPORT.md
reports/POSTER_RESULTS_SECTION.md
reports/final_assets/fig1_dirichlet_rmse_vs_walks.png
reports/final_assets/fig2_mixed_neumann_rmse_vs_walks.png
reports/final_assets/fig6_matched_bin_abs_error_ci.png
reports/final_assets/fig7_matched_bin_boundary_bias_ci.png
reports/final_assets/fig11_spot_live_trace.png
live_demo.gif
live_demo_poster.png
```

Optional if you use ParaView or image viewers:

```text
presentation_figure.png
experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/live_trace.csv
experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/live_demo_summary.csv
```

## Commands To Prepare Beforehand

Check that the executable and Python environment exist:

```powershell
Test-Path .\build\Release\wost.exe
Test-Path .\.venv\Scripts\python.exe
```

Generate or refresh the simple 2D GIF backup:

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --animate --save live_demo.gif
```

Generate or refresh the static 2D poster backup:

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --save live_demo_poster.png --no-show
```

Run the lightweight C++ trace demo:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_live_demo.py --preset neumann64
```

Open the outputs:

```text
results/live_trace_plot.png
results/live_trace_walks.gif
results/live_trace_plot_3d.png
results/live_trace_walks_3d.gif
results/live_trace_interactive_3d.html
```

## What Not To Do Live

- Do not rerun full controlled experiments during the poster session.
- Do not run `--mode all`, large grid sweeps, or full Zombie comparisons live.
- Do not rely on terminal output as the main demo.
- Do not present the live trace as standalone causality evidence.
- Do not claim WoSt is consistently more accurate than Zombie.
- Do not call the nearest-distance proxy exact signed distance.
- Do not call epsilon-vs-half-epsilon difference exact bias; call it a boundary-bias indicator or epsilon sensitivity indicator.

## Troubleshooting

### `wost.exe` is missing

Use the precomputed figures only. The demo story still works.

If build tools are available, build with:

```powershell
.\build_cpp.ps1
```

### Python cannot find matplotlib

Install dependencies into the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Live animation is slow

Use the GIF:

```text
live_demo.gif
```

or the static figure:

```text
live_demo_poster.png
```

### The C++ live trace takes too long

Skip it and use:

```text
reports/final_assets/fig11_spot_live_trace.png
```

The poster-session goal is explanation, not recomputation.

## Best Final Recommendation

For the actual poster session, use this order:

1. Show `fig1_dirichlet_rmse_vs_walks.png` for validation.
2. Show `fig2_mixed_neumann_rmse_vs_walks.png` for the hard case.
3. Show `fig6_matched_bin_abs_error_ci.png` for the controlled result.
4. Show `fig11_spot_live_trace.png` as the live-style diagnostic.
5. If the audience wants motion, play `live_demo.gif`.

This is the safest and clearest demo because it is visual, fast, tied to the report, and does not depend on a long computation during the session.
