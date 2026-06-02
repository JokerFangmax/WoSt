#!/usr/bin/env python3
"""Plot optimization experiments and write a short markdown report."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments"
FIG = EXP / "figures"
SUMMARY = EXP / "optimization_summary.csv"
POINTS = EXP / "optimization_points.csv"
REPORT = EXP / "optimization_report.md"


NUMERIC = {
    "seed",
    "num_query_points",
    "valid_points",
    "walks_per_point",
    "epsilon",
    "min_samples",
    "max_samples",
    "batch_size",
    "target_rse",
    "elapsed_seconds",
    "rmse",
    "mae",
    "mean_relative_error",
    "mean_std_error",
    "mean_sample_variance",
    "mean_samples_used",
    "median_samples_used",
    "min_samples_used",
    "max_samples_used",
    "mean_steps",
    "diverged_count",
    "star_queries",
    "fast_only_star_queries",
    "exact_star_queries",
    "refinement_ratio",
}


def load_csv(path: Path, numeric: set[str]) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run the C++ optimization modes first.")
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in numeric:
            if key in row and row[key] != "":
                row[key] = float(row[key])
    return rows


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception as exc:
        raise SystemExit("matplotlib is required for plots.") from exc


def grouped(rows: list[dict], experiment: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("experiment") == experiment:
            out[str(row.get("method"))].append(row)
    return out


def latest_repeats(rows: list[dict], repeats: int = 3) -> list[dict]:
    """Keep the latest repeated seeds for each experiment/method pair.

    The C++ executable appends rows to preserve previous runs. Reports and plots
    should reflect the most recent batch without deleting older experiment data.
    """
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        buckets[(str(row.get("experiment")), str(row.get("method")))].append(row)

    out: list[dict] = []
    for items in buckets.values():
        out.extend(items[-repeats:])
    return out


def avg_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return mean(values), stdev(values)


def method_stats(rows: list[dict], metric: str) -> tuple[list[str], list[float], list[float]]:
    methods = sorted(grouped_by_method := grouped(rows, str(rows[0]["experiment"])).keys())
    vals, errs = [], []
    for method in methods:
        m, s = avg_std([float(r[metric]) for r in grouped_by_method[method]])
        vals.append(m)
        errs.append(s)
    return methods, vals, errs


def bar_error(plt, rows: list[dict], experiment: str, metric: str, output: str, title: str, ylabel: str):
    data = [r for r in rows if r.get("experiment") == experiment]
    if not data:
        print(f"No {experiment} rows; skipping {output}")
        return
    by_method = grouped(rows, experiment)
    methods = list(by_method.keys())
    vals, errs = [], []
    for method in methods:
        m, s = avg_std([float(r[metric]) for r in by_method[method]])
        vals.append(m)
        errs.append(s)

    plt.figure(figsize=(7, 4.4))
    colors = ["#3B82F6", "#F97316", "#10B981", "#8B5CF6", "#EF4444"]
    plt.bar(methods, vals, yerr=errs, capsize=4, color=colors[: len(methods)])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, axis="y", alpha=0.25)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(FIG / output, dpi=180)
    plt.close()


def plot_lazy_tradeoff(plt, rows: list[dict]):
    data = [r for r in rows if r.get("experiment") == "lazy_refinement"]
    if not data:
        return
    by_method = grouped(rows, "lazy_refinement")
    xs, ys, labels = [], [], []
    for method, items in by_method.items():
        x, _ = avg_std([float(r["refinement_ratio"]) for r in items])
        y, yerr = avg_std([float(r["rmse"]) for r in items])
        xs.append(x)
        ys.append(y)
        labels.append((method, yerr))

    plt.figure(figsize=(6.5, 4.4))
    plt.scatter(xs, ys, s=70, color="#2563EB")
    for x, y, (label, _) in zip(xs, ys, labels):
        plt.annotate(label, (x, y), textcoords="offset points", xytext=(6, 5), fontsize=8)
    plt.xlabel("exact refinement ratio")
    plt.ylabel("RMSE")
    plt.title("Lazy star-radius trade-off")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG / "lazy_tradeoff_rmse_vs_refinement.png", dpi=180)
    plt.close()


def load_points() -> list[dict]:
    if not POINTS.exists():
        return []
    numeric = {
        "seed",
        "point_index",
        "x",
        "y",
        "z",
        "value",
        "exact",
        "abs_error",
        "std_error",
        "sample_variance",
        "samples_used",
        "mean_steps",
        "star_queries",
        "fast_only_star_queries",
        "exact_star_queries",
    }
    return load_csv(POINTS, numeric)


def plot_antithetic_variance_scatter(plt, points: list[dict]):
    normal = {
        (r["seed"], r["point_index"]): r
        for r in points
        if r.get("experiment") == "antithetic_compare" and r.get("method") == "normal"
    }
    anti = [
        r
        for r in points
        if r.get("experiment") == "antithetic_compare" and r.get("method") == "antithetic"
        and (r["seed"], r["point_index"]) in normal
    ]
    if not anti:
        return
    x = [float(normal[(r["seed"], r["point_index"])]["sample_variance"]) for r in anti]
    y = [float(r["sample_variance"]) for r in anti]
    hi = max(x + y) if x or y else 1.0

    plt.figure(figsize=(5.4, 5.0))
    plt.scatter(x, y, s=12, alpha=0.55, color="#0F766E")
    plt.plot([0, hi], [0, hi], "--", color="#6B7280", linewidth=1)
    plt.xlabel("normal sample variance")
    plt.ylabel("antithetic sample variance")
    plt.title("Pointwise variance comparison")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG / "antithetic_pointwise_variance.png", dpi=180)
    plt.close()


def plot_lazy_spatial(plt, points: list[dict]):
    rows = [
        r for r in points
        if r.get("experiment") == "lazy_refinement" and r.get("method") == "lazy_threshold_x1"
    ]
    if not rows:
        return
    x = [float(r["x"]) for r in rows]
    y = [float(r["y"]) for r in rows]
    c = [float(r["exact_star_queries"]) / max(float(r["star_queries"]), 1.0) for r in rows]
    plt.figure(figsize=(5.8, 5.0))
    sc = plt.scatter(x, y, c=c, s=14, cmap="magma", alpha=0.85)
    plt.colorbar(sc, label="point refinement ratio")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Where lazy refinement triggers")
    plt.axis("equal")
    plt.tight_layout()
    plt.savefig(FIG / "lazy_refinement_spatial_xy.png", dpi=180)
    plt.close()


def plot_epsilon_sensitivity(plt, points: list[dict]):
    eps = {
        (r["seed"], r["point_index"]): r
        for r in points
        if r.get("experiment") == "epsilon_extrapolation" and r.get("method") == "epsilon"
    }
    half = [
        r
        for r in points
        if r.get("experiment") == "epsilon_extrapolation" and r.get("method") == "epsilon_half"
        and (r["seed"], r["point_index"]) in eps
    ]
    if not half:
        return
    diff = [abs(float(r["value"]) - float(eps[(r["seed"], r["point_index"])]["value"])) for r in half]
    plt.figure(figsize=(6.2, 4.2))
    plt.hist(diff, bins=35, color="#7C3AED", alpha=0.85)
    plt.xlabel("|u_epsilon - u_epsilon/2|")
    plt.ylabel("query points")
    plt.title("Epsilon sensitivity histogram")
    plt.grid(True, axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG / "epsilon_sensitivity_histogram.png", dpi=180)
    plt.close()

    x = [float(r["x"]) for r in half]
    y = [float(r["y"]) for r in half]
    plt.figure(figsize=(5.8, 5.0))
    sc = plt.scatter(x, y, c=diff, s=14, cmap="viridis", alpha=0.85)
    plt.colorbar(sc, label="epsilon sensitivity")
    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Spatial epsilon sensitivity")
    plt.axis("equal")
    plt.tight_layout()
    plt.savefig(FIG / "epsilon_sensitivity_spatial_xy.png", dpi=180)
    plt.close()


def plot_neumann_diagnostics(plt):
    diag = EXP / "neumann_normal_diagnostics.csv"
    if not diag.exists():
        return
    rows = load_csv(diag, {"h", "expected_h", "normal_dot"})
    labels = [str(i) for i in range(len(rows))]
    h = [float(r["h"]) for r in rows]
    expected = [float(r["expected_h"]) for r in rows]
    dots = [float(r["normal_dot"]) for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].plot(labels, h, marker="o", label="solver h")
    axes[0].plot(labels, expected, marker="s", label="expected h")
    axes[0].set_title("Neumann h sign check")
    axes[0].set_xlabel("probe")
    axes[0].set_ylabel("grad dot normal")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend()

    axes[1].bar(labels, dots, color="#16A34A")
    axes[1].axhline(0.95, linestyle="--", color="#6B7280")
    axes[1].set_title("normal dot expected radial")
    axes[1].set_xlabel("probe")
    axes[1].set_ylim(0, 1.05)
    axes[1].grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    plt.savefig(FIG / "neumann_normal_diagnostics.png", dpi=180)
    plt.close()


def write_report(rows: list[dict]):
    by_exp_method = defaultdict(list)
    for row in rows:
        by_exp_method[(row["experiment"], row["method"])].append(row)

    def line(experiment: str, method: str, metric: str) -> str:
        vals = [float(r[metric]) for r in by_exp_method.get((experiment, method), [])]
        m, s = avg_std(vals)
        return f"{m:.6g} +/- {s:.3g}"

    figures = sorted(p.relative_to(ROOT).as_posix() for p in FIG.glob("*.png"))
    lines = [
        "# WoSt Optimization Experiments",
        "",
        "This report is generated from `experiments/optimization_summary.csv`; plots and tables use the latest three appended rows for each experiment/method pair.",
        "",
        "## Reproducibility",
        "",
        "Each comparison uses Common Random Numbers: query points come from the experiment seed, and each point uses `SeedFor(experiment_seed, point_index, stream)` for its random walk stream. Methods in the same comparison reuse the same experiment seed and point index stream.",
        "",
        "Default command:",
        "",
        "```powershell",
        ".\\build\\Release\\wost.exe --mode optimization --queries 1000 --threads 8 --max-samples 512 --min-samples 64 --batch-size 32 --target-rse 0.05 --rse-eps 0.001",
        ".\\.venv\\Scripts\\python.exe .\\scripts\\plot_optimization_experiments.py",
        "```",
        "",
        "## Key Results",
        "",
        "| experiment | method | RMSE | MAE | mean samples | runtime |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for (experiment, method), _items in sorted(by_exp_method.items()):
        lines.append(
            f"| {experiment} | {method} | {line(experiment, method, 'rmse')} | "
            f"{line(experiment, method, 'mae')} | {line(experiment, method, 'mean_samples_used')} | "
            f"{line(experiment, method, 'elapsed_seconds')} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- Adaptive sampling now supports relative standard error: `std_error / max(abs(mean), rse_eps) < target_rse`, while preserving `min_samples`, `max_samples`, and `batch_size`.",
        "- The old absolute-standard-error adaptive mode is still available as `old_absolute_stderr` in the adaptive comparison.",
        "- Antithetic sampling runs paired walks using direction streams `d` and `-d`; odd sample limits fall back to one final unpaired walk.",
        "- Lazy star-radius refinement records total, fast-only, and exact refinement query counts. Full exact mode sets `useLazyStarRefinement=false`.",
        "- Epsilon extrapolation compares `epsilon=1e-2` with `epsilon/2`; large pointwise differences indicate likely boundary bias and can motivate adaptive epsilon refinement near complex Neumann boundaries.",
        "- The Neumann sanity test generates an inner sphere OBJ and checks mesh normals against the expected radial normal before running the sphere/cube solve.",
        "",
        "## Figures",
        "",
    ]
    for fig in figures:
        lines.append(f"- `{fig}`")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rows = latest_repeats(load_csv(SUMMARY, NUMERIC))
    points = load_points()
    plt = require_matplotlib()

    bar_error(plt, rows, "adaptive_compare", "rmse", "adaptive_rmse_errorbars.png", "Fixed vs adaptive RMSE", "RMSE")
    bar_error(plt, rows, "adaptive_compare", "mean_samples_used", "adaptive_samples_errorbars.png", "Fixed vs adaptive samples", "mean samples used")
    bar_error(plt, rows, "antithetic_compare", "rmse", "antithetic_rmse_errorbars.png", "Normal vs antithetic RMSE", "RMSE")
    bar_error(plt, rows, "antithetic_compare", "mean_sample_variance", "antithetic_variance_errorbars.png", "Normal vs antithetic variance", "mean sample variance")
    bar_error(plt, rows, "lazy_refinement", "rmse", "lazy_rmse_errorbars.png", "Full vs lazy star-radius RMSE", "RMSE")
    bar_error(plt, rows, "lazy_refinement", "refinement_ratio", "lazy_refinement_ratio_errorbars.png", "Lazy refinement trigger ratio", "exact refinement ratio")
    bar_error(plt, rows, "epsilon_extrapolation", "rmse", "epsilon_rmse_errorbars.png", "Epsilon extrapolation RMSE", "RMSE")
    bar_error(plt, rows, "neumann_sanity", "rmse", "neumann_sanity_rmse_errorbars.png", "Neumann sphere/cube sanity", "RMSE")

    plot_lazy_tradeoff(plt, rows)
    plot_antithetic_variance_scatter(plt, points)
    plot_lazy_spatial(plt, points)
    plot_epsilon_sensitivity(plt, points)
    plot_neumann_diagnostics(plt)
    write_report(rows)
    print(f"Wrote figures to {FIG}")
    print(f"Wrote report to {REPORT}")


if __name__ == "__main__":
    main()
