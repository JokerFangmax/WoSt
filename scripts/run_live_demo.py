#!/usr/bin/env python3
"""Run a few small live-demo presets and generate the trace plot."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=["dirichlet16", "dirichlet256", "neumann64", "antithetic64"],
                        default="dirichlet16")
    parser.add_argument("--exe", default="build/Release/wost.exe")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    exe = ROOT / args.exe
    if not exe.exists():
        fallback = ROOT / "build" / "wost.exe"
        exe = fallback if fallback.exists() else exe
    if not exe.exists():
        raise SystemExit("Could not find wost.exe. Build the C++ project first.")

    base = [
        str(exe), "--mode", "demo_point",
        "--point", "0.05", "0.02", "0.08",
        "--epsilon", "1e-4",
        "--seed", "12345",
        "--trace-out", "results/live_trace.csv",
        "--summary-out", "results/live_demo_summary.csv",
    ]
    presets = {
        "dirichlet16": ["--boundary", "dirichlet", "--walks", "16", "--trace-walks", "8"],
        "dirichlet256": ["--boundary", "dirichlet", "--walks", "256", "--trace-walks", "8"],
        "neumann64": ["--boundary", "neumann", "--walks", "64", "--trace-walks", "8"],
        "antithetic64": ["--boundary", "dirichlet", "--walks", "64", "--trace-walks", "8", "--antithetic"],
    }
    subprocess.run(base + presets[args.preset], cwd=ROOT, check=True)
    subprocess.run([
        "python", "scripts/plot_live_trace.py",
        "--trace", "results/live_trace.csv",
        "--summary", "results/live_demo_summary.csv",
        "--out", "results/live_trace_plot.png",
    ], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

