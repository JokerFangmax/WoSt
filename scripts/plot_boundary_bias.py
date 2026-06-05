#!/usr/bin/env python3
"""Plot a center slice from boundary_bias_detector VTK output."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vtk", default="results/boundary_bias_detector.vtk")
    parser.add_argument("--summary", default="results/boundary_bias_summary.csv")
    parser.add_argument("--out", default="results/boundary_bias_detector.png")
    return parser.parse_args()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.colors import LogNorm  # type: ignore

        return plt, LogNorm
    except Exception as exc:
        raise SystemExit("matplotlib is required for plot_boundary_bias.py") from exc


def parse_structured_vtk(path: Path) -> tuple[tuple[int, int, int], dict[str, np.ndarray]]:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run --mode bias_detector first.")
    lines = path.read_text().splitlines()
    dims = None
    fields: dict[str, np.ndarray] = {}
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if parts[:1] == ["DIMENSIONS"]:
            dims = tuple(int(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["SCALARS"]:
            if dims is None:
                raise SystemExit("VTK SCALARS appeared before DIMENSIONS.")
            name = parts[1]
            i += 2  # skip LOOKUP_TABLE
            n = dims[0] * dims[1] * dims[2]
            values = []
            for _ in range(n):
                token = lines[i].strip()
                values.append(float(token) if token.lower() != "nan" else np.nan)
                i += 1
            fields[name] = np.array(values, dtype=float).reshape((dims[2], dims[1], dims[0]))
        else:
            i += 1
    if dims is None:
        raise SystemExit("Could not find DIMENSIONS in VTK file.")
    return dims, fields


def read_summary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else {}


def main() -> None:
    args = parse_args()
    vtk_path = (ROOT / args.vtk).resolve() if not Path(args.vtk).is_absolute() else Path(args.vtk)
    summary_path = (ROOT / args.summary).resolve() if not Path(args.summary).is_absolute() else Path(args.summary)
    out_path = (ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)

    dims, fields = parse_structured_vtk(vtk_path)
    summary = read_summary(summary_path)
    plt, LogNorm = require_matplotlib()

    panels = [
        ("solution_epsilon", "u(epsilon)", False),
        ("solution_epsilon_half", "u(epsilon/2)", False),
        ("bias_indicator", "|u_eps - u_half|", True),
        ("normalized_bias", "normalized bias", True),
        ("mean_steps_epsilon", "mean steps", False),
        ("abs_error_epsilon", "abs error", True),
    ]
    z = dims[2] // 2
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 7.2), constrained_layout=True)
    for ax, (field, title, use_log) in zip(axes.ravel(), panels):
        data = fields.get(field)
        if data is None:
            ax.set_title(f"missing: {field}")
            ax.axis("off")
            continue
        img = data[z, :, :]
        norm = None
        if use_log:
            finite = img[np.isfinite(img) & (img > 0)]
            if finite.size:
                norm = LogNorm(vmin=max(float(finite.min()), 1e-8), vmax=float(finite.max()))
        im = ax.imshow(img, origin="lower", cmap="viridis", norm=norm)
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.82)

    if summary:
        text = (
            f"epsilon={summary.get('epsilon', '?')}, walks={summary.get('walks', '?')}, "
            f"high-bias ratio={float(summary.get('high_bias_ratio', 0.0)):.3f}"
        )
        fig.suptitle("Boundary Bias Detector: center z-slice\n" + text, fontsize=13)
    else:
        fig.suptitle("Boundary Bias Detector: center z-slice", fontsize=13)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

