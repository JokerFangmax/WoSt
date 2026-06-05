#!/usr/bin/env python3
"""Plot traced Walk-on-Stars paths from demo_point mode."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", default="results/live_trace.csv")
    parser.add_argument("--summary", default="results/live_demo_summary.csv")
    parser.add_argument("--out", default="results/live_trace_plot.png")
    return parser.parse_args()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception as exc:
        raise SystemExit("matplotlib is required for plot_live_trace.py") from exc


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run --mode demo_point first.")
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    args = parse_args()
    trace_path = (ROOT / args.trace).resolve() if not Path(args.trace).is_absolute() else Path(args.trace)
    summary_path = (ROOT / args.summary).resolve() if not Path(args.summary).is_absolute() else Path(args.summary)
    out_path = (ROOT / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)

    rows = read_csv(trace_path)
    summary_rows = read_csv(summary_path)
    summary = summary_rows[0] if summary_rows else {}

    walks: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        walks[int(row["walk_id"])].append(row)

    plt = require_matplotlib()
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    colors = plt.cm.tab10.colors

    for idx, (walk_id, pts) in enumerate(sorted(walks.items())):
        pts = sorted(pts, key=lambda r: int(r["step_id"]))
        xs = [float(r["x"]) for r in pts]
        ys = [float(r["y"]) for r in pts]
        ax.plot(xs, ys, lw=1.3, alpha=0.55, color=colors[idx % len(colors)])
        end = pts[-1]
        ax.scatter(float(end["x"]), float(end["y"]), s=25, marker="x", color=colors[idx % len(colors)])

        refl_x = [float(r["x"]) for r in pts if r["event_type"] == "neumann_reflect"]
        refl_y = [float(r["y"]) for r in pts if r["event_type"] == "neumann_reflect"]
        if refl_x:
            ax.scatter(refl_x, refl_y, s=34, marker="D", edgecolor="black",
                       facecolor=colors[idx % len(colors)], linewidth=0.5)

    starts = [r for r in rows if r["event_type"] == "start"]
    if starts:
        start = starts[0]
        ax.scatter(float(start["x"]), float(start["y"]), s=110, marker="*",
                   color="black", label="start", zorder=5)

    ax.set_title("Walk Path Debugger: traced random walks")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)

    box_lines = []
    for key, label in [
        ("estimated_value", "estimate"),
        ("exact_value", "exact"),
        ("absolute_error", "abs error"),
        ("standard_error", "std error"),
        ("mean_steps", "mean steps"),
        ("epsilon", "epsilon"),
        ("walks", "walks"),
    ]:
        if key in summary:
            try:
                value = float(summary[key])
                box_lines.append(f"{label}: {value:.4g}")
            except ValueError:
                box_lines.append(f"{label}: {summary[key]}")
    if box_lines:
        ax.text(0.02, 0.98, "\n".join(box_lines), transform=ax.transAxes,
                va="top", ha="left", fontsize=9,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.88, edgecolor="0.75"))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

