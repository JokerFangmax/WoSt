#!/usr/bin/env python3
"""Run a few small live-demo presets and generate the trace plot."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=["dirichlet16", "dirichlet256", "neumann64", "antithetic64"],
                        default="dirichlet16")
    parser.add_argument("--exe", default="build/Release/wost.exe")
    parser.add_argument("--png", default="results/live_trace_plot.png", help="Static trace plot output path")
    parser.add_argument("--gif", default="results/live_trace_walks.gif", help="Animated trace GIF output path")
    parser.add_argument("--png-3d", default="results/live_trace_plot_3d.png", help="Static 3D trace plot output path")
    parser.add_argument("--gif-3d", default="results/live_trace_walks_3d.gif", help="Animated 3D trace GIF output path")
    parser.add_argument("--html-3d", default="results/live_trace_interactive_3d.html",
                        help="Interactive 3D HTML output path")
    parser.add_argument("--view", choices=["2d", "3d", "both"], default="2d",
                        help="Which trace visualization to generate")
    parser.add_argument("--no-gif", action="store_true", help="Only write the static PNG")
    parser.add_argument("--no-html", action="store_true", help="Do not write the interactive 3D HTML")
    parser.add_argument("--interval", type=int, default=400, help="GIF frame interval in milliseconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exe = ROOT / args.exe
    if not exe.exists():
        fallback = ROOT / "build" / "wost.exe"
        exe = fallback if fallback.exists() else exe
    if not exe.exists():
        raise SystemExit("Could not find wost.exe. Build the C++ project first.")

    common = [
        str(exe), "--mode", "demo_point",
        "--epsilon", "1e-4",
        "--trace-out", "results/live_trace.csv",
        "--summary-out", "results/live_demo_summary.csv",
    ]
    presets = {
        "dirichlet16": [
            "--obj", "obj/Bunny.obj", "--cube", "0.22", "--point", "0.05", "0.02", "0.08",
            "--seed", "12345", "--boundary", "dirichlet", "--walks", "16", "--trace-walks", "8",
        ],
        "dirichlet256": [
            "--obj", "obj/Bunny.obj", "--cube", "0.22", "--point", "0.05", "0.02", "0.08",
            "--seed", "12345", "--boundary", "dirichlet", "--walks", "256", "--trace-walks", "8",
        ],
        "neumann64": [
            "--obj", "spot/spot_triangulated.obj", "--cube", "1.1", "--point", "0.8", "0.0", "0.2",
            "--seed", "54321", "--boundary", "neumann", "--walks", "64", "--trace-walks", "8",
        ],
        "antithetic64": [
            "--obj", "obj/Bunny.obj", "--cube", "0.22", "--point", "0.05", "0.02", "0.08",
            "--seed", "12345", "--boundary", "dirichlet", "--walks", "64", "--trace-walks", "8",
            "--antithetic",
        ],
    }
    preset_meta = {
        "dirichlet16": {"obj": "obj/Bunny.obj", "cube": 0.22},
        "dirichlet256": {"obj": "obj/Bunny.obj", "cube": 0.22},
        "neumann64": {"obj": "spot/spot_triangulated.obj", "cube": 1.1},
        "antithetic64": {"obj": "obj/Bunny.obj", "cube": 0.22},
    }
    subprocess.run(common + presets[args.preset], cwd=ROOT, check=True)

    trace = ROOT / "results" / "live_trace.csv"
    summary = ROOT / "results" / "live_demo_summary.csv"
    if not trace.exists() or not summary.exists():
        raise SystemExit(
            "demo_point did not produce trace outputs. Check that the preset point is inside the domain."
        )

    plot_cmd = [
        sys.executable, "scripts/plot_live_trace.py",
        "--trace", "results/live_trace.csv",
        "--summary", "results/live_demo_summary.csv",
        "--out", args.png,
    ]
    if args.view == "3d":
        plot_cmd += ["--skip-2d"]
    if args.view in {"3d", "both"}:
        plot_cmd += ["--out-3d", args.png_3d]
    if args.view in {"3d", "both"} and not args.no_html:
        meta = preset_meta[args.preset]
        plot_cmd += [
            "--html-3d", args.html_3d,
            "--mesh-obj", meta["obj"],
            "--cube", str(meta["cube"]),
        ]
    if not args.no_gif and args.view in {"2d", "both"}:
        plot_cmd += ["--gif", args.gif, "--interval", str(args.interval)]
    elif not args.no_gif:
        plot_cmd += ["--interval", str(args.interval)]
    if not args.no_gif and args.view in {"3d", "both"}:
        plot_cmd += ["--gif-3d", args.gif_3d]
    subprocess.run(plot_cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
