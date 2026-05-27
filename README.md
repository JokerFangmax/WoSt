# WoSt Final Project

This repository currently has two runnable entry points:

1. `WoSt.py`
   A lightweight Python demo of a 2D Walk-on-Stars Laplace solver.
2. `main.cpp`
   The full C++ project built with CMake.

## Python demo

Recommended on Windows:

```powershell
.\setup_env.ps1
.\run_python.ps1
```

The quick script uses a smaller default workload (`--resolution 40 --walks 200`) so the first run finishes much faster.

Manual commands:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\WoSt.py --resolution 40 --walks 200
```

## Real testcase visualization

If you want the presentation assets generated from the actual `main.cpp` testcase instead of the stand-in Python data, use:

```powershell
.\generate_real_presentation_assets.ps1
```

This script will:

- build the C++ solver with the Visual Studio toolchain
- run `main.cpp` to produce:
  - `test1_manufactured_pointcloud.vtk`
  - `test1_manufactured_slice_xy.vtk`
- generate:
  - `presentation_figure.png`
  - `live_demo.gif`
  - `live_demo_poster.png`

Requirements:

- Visual Studio Build Tools 2022
- MSVC C++ compiler tools (`cl.exe`)
- CMake
- a ready Python virtual environment at `.venv`

## C++ build

Windows prerequisites:

- Visual Studio Build Tools 2022
- MSVC C++ compiler tools (`cl.exe`)
- CMake

Build with:

```powershell
.\build_cpp.ps1
```

If `build_cpp.ps1` reports that `cl` or `cmake` is missing, install the C++ workload/components into your existing Visual Studio Build Tools installation first, then rerun the script.

After a successful build, the solver can also be run manually before generating the presentation figure:

```powershell
.\build\Release\wost.exe
.\.venv\Scripts\python.exe .\presentation_viz.py --slice test1_manufactured_slice_xy.vtk --pointcloud test1_manufactured_pointcloud.vtk --output presentation_figure.png
```
