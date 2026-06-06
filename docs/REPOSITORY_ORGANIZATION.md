# Repository Organization Notes

This repository has grown through several experiment/report iterations. The core code is still fairly compact; most of the clutter comes from generated benchmark outputs, copied report figures, and historical result snapshots.

## Current Repository Map

| Path | Role | Keep in repo? | Notes |
| --- | --- | --- | --- |
| `main.cpp` | Main C++ CLI and experiment modes | Yes | Currently owns many output defaults such as `results/*.csv` and `experiments/*.csv`. |
| `src/` | C++ solver, geometry backend, boundary helpers | Yes | Core implementation. |
| `CMakeLists.txt`, `build_cpp.ps1` | C++ build system | Yes | `build/` itself should stay ignored. |
| `WoSt.py`, `live_demo.py`, `presentation_viz.py` | Python demo and visualization utilities | Yes | Root placement is workable, but these could later move to `scripts/` once README commands are updated. |
| `scripts/` | Experiment orchestration and plotting | Yes | `run_all_wost_experiments.py` is the best current pipeline entry. |
| `configs/` | Smoke/quick/final experiment configs | Yes | Good canonical home for reproducible run parameters. |
| `obj/`, `spot/` | Mesh input assets | Yes | Consider renaming `obj/` to `assets/meshes/` in a future path-migration pass. |
| `results/` | Active scratch output from latest C++/plot runs | Usually no, except selected final snapshots | Many scripts still read/write this path directly. Treat as working output. |
| `results_saved/` | Older selected result snapshot | Archive or fold into `experiments/` | Mostly duplicates historical benchmark outputs. |
| `results_archive_*` | Iteration archives | No | Already ignored, but existing local directories remain on disk. |
| `experiments/` | Durable experiment runs, report figures, final reports | Yes | This is the right long-term home for report-grade artifacts. |
| `docs/` | Workflow notes, audit logs, result mapping | Yes | Some docs are historical logs and should be labeled as such rather than treated as current instructions. |
| `test1_manufactured_*.vtk`, `presentation_figure.png`, `live_demo.gif`, `live_demo_poster.png` | Generated presentation/demo artifacts | Maybe | Tracked today and referenced by README. Future generated copies should go under `artifacts/presentation/` or `experiments/<run>/figures/`. |
| `.venv/`, `build/`, `__pycache__/` | Local environment/build/cache | No | Ignored locally; tracked cache files should be removed in a cleanup commit. |

## Main Problems

1. Root directory mixes source, demos, generated VTK/PNG/GIF files, binaries, and report inputs.
2. `results/` acts both as live scratch space and as a source for final figures.
3. `experiments/` contains canonical final runs, copied historical baselines, generated figures, PDFs, and obsolete reports in one namespace.
4. Several output paths are hardcoded in `main.cpp` and plotting scripts, so moving `results/` or root presentation assets without a path-migration pass would break existing commands.
5. Git currently tracks files that should be disposable: `.DS_Store`, `__pycache__/*.pyc`, `hello_test.exe`, and `omp_test.exe`.

## Recommended Target Layout

```text
.
├── src/                         # C++ implementation
├── scripts/                     # Python/PowerShell orchestration and plotting
├── configs/                     # Reproducible experiment configs
├── assets/
│   └── meshes/                  # Bunny, Spot, generated sphere inputs
├── results/                     # Local scratch outputs, ignored or mostly ignored
├── experiments/
│   ├── bunny_smoke/             # One self-contained run
│   ├── spot_mesh_report_20260603/
│   └── final_cross_mesh_report_20260603/
├── docs/                        # Current docs plus historical logs
├── reports/                     # Optional future home for polished PDFs/posters
└── local_archive/               # Ignored local-only archives
```

## Safe Cleanup Already Supported

The `.gitignore` now covers local build directories, virtual environments, Python caches, OS metadata, local binaries, and local archives.

The script `scripts/cleanup_repository.ps1` provides a dry-run cleanup inventory. It defaults to preview mode and only performs file operations when called with `-Apply`.

Examples:

```powershell
.\scripts\cleanup_repository.ps1
.\scripts\cleanup_repository.ps1 -Apply
.\scripts\cleanup_repository.ps1 -ArchiveLegacyResults -Apply
```

## Suggested Next Migration Pass

1. Remove tracked junk in one commit:

   ```powershell
   git rm .DS_Store src/.DS_Store __pycache__/WoSt.cpython-312.pyc scripts/__pycache__/plot_benchmarks.cpython-313.pyc hello_test.exe omp_test.exe
   ```

2. Decide whether `results/` should remain tracked. If not, preserve report-grade CSV/PNG/VTK files under `experiments/<run-name>/raw`, `plots`, and `reports`, then ignore `results/`.
3. Move root generated presentation outputs into a dedicated directory only after updating README and `generate_real_presentation_assets.ps1`.
4. Refactor `main.cpp` and plotting scripts to accept a single output directory consistently. That will make `results/` purely disposable.
5. Add a short `docs/CURRENT_STATUS.md` or update README to distinguish current workflows from historical benchmark logs.

## Practical Rule

Use this policy going forward:

- Source, configs, scripts, mesh inputs, and final reports are tracked.
- Reproducible final experiment outputs live under `experiments/<name>/`.
- Fresh command outputs go to `results/` and are copied into `experiments/<name>/` only when they become evidence for a report.
- Build products, caches, archives, and one-off binaries stay untracked.
