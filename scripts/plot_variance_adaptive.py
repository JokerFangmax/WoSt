#!/usr/bin/env python3
"""Plot variance-predicted adaptive sampling outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", default="results/variance_adaptive_comparison.csv")
    parser.add_argument("--points", default="results/variance_adaptive_points.csv")
    parser.add_argument("--tradeoff-out", default="results/variance_adaptive_tradeoff.png")
    parser.add_argument("--samples-out", default="results/variance_adaptive_samples_map.png")
    return parser.parse_args()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception as exc:
        raise SystemExit("matplotlib is required for plot_variance_adaptive.py") from exc


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run --mode variance_adaptive first.")
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    args = parse_args()
    comparison_path = (ROOT / args.comparison).resolve() if not Path(args.comparison).is_absolute() else Path(args.comparison)
    points_path = (ROOT / args.points).resolve() if not Path(args.points).is_absolute() else Path(args.points)
    tradeoff_out = (ROOT / args.tradeoff_out).resolve() if not Path(args.tradeoff_out).is_absolute() else Path(args.tradeoff_out)
    samples_out = (ROOT / args.samples_out).resolve() if not Path(args.samples_out).is_absolute() else Path(args.samples_out)

    comparison = read_csv(comparison_path)
    points = [r for r in read_csv(points_path) if r.get("is_valid") == "1"]
    plt = require_matplotlib()

    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    for row in comparison:
        x = float(row["mean_samples_used"])
        y = float(row["rmse"])
        method = row["method"]
        marker = "s" if method == "fixed_1024" else "o"
        size = 90 if method == "fixed_1024" else 55
        ax.scatter([x], [y], s=size, marker=marker)
        ax.annotate(method, (x, y), xytext=(5, 5), textcoords="offset points", fontsize=8)
    ax.set_xlabel("mean samples used")
    ax.set_ylabel("RMSE")
    ax.set_title("Variance-Predicted Adaptive Sampling Trade-off")
    ax.grid(True, alpha=0.28)
    tradeoff_out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(tradeoff_out, dpi=180)

    fig2, axes = plt.subplots(1, 2, figsize=(12.0, 5.1), constrained_layout=True)
    xs = [float(r["x"]) for r in points]
    ys = [float(r["y"]) for r in points]
    samples = [float(r["samples_used"]) for r in points]
    sc = axes[0].scatter(xs, ys, c=samples, s=18, cmap="viridis")
    axes[0].set_title("Variance-Predicted Adaptive Sampling")
    axes[0].set_xlabel("x")
    axes[0].set_ylabel("y")
    axes[0].set_aspect("equal", adjustable="box")
    fig2.colorbar(sc, ax=axes[0], label="samples used")

    variance = [float(r["sample_variance"]) for r in points]
    axes[1].scatter(variance, samples, s=18, alpha=0.7)
    axes[1].set_xlabel("pilot/final sample variance")
    axes[1].set_ylabel("samples used")
    axes[1].set_title("Higher variance receives more samples")
    axes[1].grid(True, alpha=0.28)
    samples_out.parent.mkdir(parents=True, exist_ok=True)
    fig2.savefig(samples_out, dpi=180)
    print(f"Wrote {tradeoff_out}")
    print(f"Wrote {samples_out}")


if __name__ == "__main__":
    main()

