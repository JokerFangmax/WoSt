# Presentation Notes

## What the repo already has

- `main.cpp` is already acting as a testcase for a manufactured Poisson problem.
- The testcase checks the Monte Carlo solution against an analytic ground truth.
- `src/utils.hpp` already supports both point-cloud VTK output and structured-grid VTK output.

Before this update, `main.cpp` only wrote the point cloud. It now also writes:

- `test1_manufactured_pointcloud.vtk`
- `test1_manufactured_slice_xy.vtk`

That makes the presentation story much stronger because you can show:

1. stochastic samples in 3D
2. a clean slice through the field
3. absolute error against the manufactured solution

## Fancy visualization recipe

### Best presentation stack

Use two visual layers together:

1. `presentation_viz.py`
   This turns the raw VTK outputs into one polished summary figure for slides.
2. ParaView
   Use it for the final hero shot with lighting, camera motion, and interactive rotation.

### Why this works

Point clouds alone look noisy and technical.

For presentation, the audience usually needs three things at once:

1. a clear scalar field
2. evidence that the solver is correct
3. a reminder that the computation is genuinely volumetric and stochastic

The slice + error + point-cloud combination gives you all three in one frame.

## Commands

### Build the slide-ready figure from the real testcase

Preferred path:

```powershell
.\generate_real_presentation_assets.ps1
```

That route builds the C++ solver, runs the actual `main.cpp` testcase, and then creates `presentation_figure.png` from the resulting VTK files.

### Current real-run snapshot

The current checked-in visualization assets were regenerated from the real `main.cpp` testcase on May 27, 2026.

Key numbers from that run:

- attempted random query points: `100000`
- valid domain points written to the point cloud: `91025`
- slice resolution: `96 x 96 x 1`
- wall-clock solve time: `203.68 s`
- reported max absolute error: `10.003481`
- reported mean absolute error: `2.636646`

Generated assets from that run:

- `test1_manufactured_pointcloud.vtk`
- `test1_manufactured_slice_xy.vtk`
- `presentation_figure.png`
- `live_demo.gif`
- `live_demo_poster.png`

### How to talk about these numbers

Recommended framing:

1. `91025` valid samples means the 3D point cloud is coming from the actual annular Spot-domain testcase, not a toy stand-in.
2. `96 x 96` on the slice is dense enough to show the field structure clearly on a slide.
3. `203.68 s` is a good reminder that the live talk should use precomputed assets, not a full rerun.
4. The current error numbers are useful as diagnostics, but they should be presented carefully because the manufactured-test boundary setup in `main.cpp` is not yet a perfectly clean validation benchmark.

Suggested one-line script:

`This figure comes from the real C++ Walk-on-Stars testcase on the Spot geometry: about 91k valid 3D samples plus a 96 by 96 verification slice.`

### Fallback: build the figure from stand-in data

If you do not yet have a working C++ toolchain, generate presentation-ready stand-in data first:

```powershell
.\.venv\Scripts\python.exe .\generate_presentation_data.py
```

Then build the figure:

```powershell
.\.venv\Scripts\python.exe .\presentation_viz.py --slice test1_manufactured_slice_xy.vtk --pointcloud test1_manufactured_pointcloud.vtk --output presentation_figure.png
```

### Build the intuitive live-demo poster

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --save live_demo_poster.png --no-show
```

### Run the actual live animation

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --animate
```

### Export a GIF backup for the presentation

```powershell
.\.venv\Scripts\python.exe .\live_demo.py --walks 40 --animate --save live_demo.gif
```

## How to make the demo feel strong on stage

### Recommended flow

1. Start with the 2D live demo.
   Show how one query point jumps by maximal safe spheres until it lands on the boundary.
2. Then state the punchline.
   "That exact idea scales to our 3D geometry solver."
3. Switch to the 3D result.
   Show the point cloud first for stochastic flavor.
4. Immediately reveal the polished slice and error view.
   This is where the audience understands both the field and the validation.
   Mention that the displayed figure is precomputed from the real `main.cpp` run, not from the Python stand-in generator.
5. End with a rotating ParaView shot of the Spot domain.

### What not to do live

- Do not rely on a full heavy 3D recomputation on stage.
- Do not make the audience parse raw terminal output for too long.
- Do not show only a noisy point cloud without a cleaner scalar slice.
- Do not oversell the absolute-error number as a polished benchmark until the manufactured boundary conditions in `main.cpp` are tightened up.

## A reliable live-demo structure

Use this split:

1. Live
   `live_demo.py --animate`
2. Precomputed but interactive
   Open the VTK outputs in ParaView and rotate or scrub slices live.
3. Static safety backup
   Keep `presentation_figure.png` and `live_demo.gif` on a slide in case something lags.

## ParaView ideas

For the point cloud:

- color by `solution`
- set small sphere glyphs
- use opacity around `0.25` to `0.45`
- add a clip plane
- add a second view with `abs_error`

For the structured slice:

- use `solution` with a bold colormap like `Turbo`
- overlay `Contours`
- keep background light, not black
- lock one camera angle and animate only one slow rotate near the end
