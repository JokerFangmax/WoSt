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
    walk_colors = plt.cm.tab10.colors
    event_styles = {
        "start": ("*", "black", 120, "start"),
        "sphere_step": ("o", "#2563EB", 18, "sphere step"),
        "neumann_reflect": ("D", "#F97316", 42, "Neumann reflection"),
        "dirichlet_hit": ("X", "#16A34A", 70, "Dirichlet termination"),
        "max_step": ("s", "#DC2626", 52, "max-step termination"),
        "end": ("x", "#111827", 36, "end"),
    }

    for idx, (walk_id, pts) in enumerate(sorted(walks.items())):
        pts = sorted(pts, key=lambda r: int(r["step_id"]))
        xs = [float(r["x"]) for r in pts]
        ys = [float(r["y"]) for r in pts]
        ax.plot(xs, ys, lw=1.1, alpha=0.42, color=walk_colors[idx % len(walk_colors)])

    seen_labels = set()
    for event, (marker, color, size, label) in event_styles.items():
        event_rows = [r for r in rows if r["event_type"] == event]
        if not event_rows:
            continue
        label_arg = label if label not in seen_labels else None
        seen_labels.add(label)
        ax.scatter(
            [float(r["x"]) for r in event_rows],
            [float(r["y"]) for r in event_rows],
            s=size,
            marker=marker,
            color=color,
            edgecolor="black" if event in {"neumann_reflect", "dirichlet_hit", "max_step"} else None,
            linewidth=0.45,
            label=label_arg,
            zorder=5 if event != "sphere_step" else 3,
            alpha=0.9 if event != "sphere_step" else 0.55,
        )

    ax.set_title("Walk Path Debugger: traced random walks")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

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
