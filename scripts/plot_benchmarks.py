#!/usr/bin/env python3
"""Generate benchmark plots from CSV files in results/."""

from __future__ import annotations

import csv
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
CSV_PATH = RESULTS / "benchmark_summary.csv"
GEOMETRY_CSV_PATH = RESULTS / "geometry_benchmark.csv"


def load_rows():
    if not CSV_PATH.exists():
        print(f"Missing {CSV_PATH}; skipping solver benchmark plots.")
        return []

    try:
        import pandas as pd  # type: ignore

        return pd.read_csv(CSV_PATH).to_dict("records")
    except Exception:
        with CSV_PATH.open(newline="") as f:
            rows = list(csv.DictReader(f))
        numeric = {
            "num_query_points",
            "valid_points",
            "walks_per_point",
            "epsilon",
            "max_steps",
            "num_threads",
            "elapsed_seconds",
            "points_per_second",
            "walks_per_second",
            "rmse",
            "mae",
            "max_abs_error",
            "mean_std_error",
            "mean_steps",
            "diverged_count",
            "mean_samples_used",
        }
        for row in rows:
            for key in numeric:
                if key in row and row[key] != "":
                    row[key] = float(row[key])
        return rows


def load_geometry_rows():
    if not GEOMETRY_CSV_PATH.exists():
        return []

    try:
        import pandas as pd  # type: ignore

        return pd.read_csv(GEOMETRY_CSV_PATH).to_dict("records")
    except Exception:
        with GEOMETRY_CSV_PATH.open(newline="") as f:
            rows = list(csv.DictReader(f))
        numeric = {
            "triangle_count",
            "num_queries",
            "num_threads",
            "elapsed_seconds",
            "queries_per_second",
            "checksum",
        }
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
        raise SystemExit("matplotlib is required to generate plots.") from exc


def latest_by_walks(rows, name):
    filtered = [r for r in rows if r.get("benchmark_name") == name]
    by_x = {}
    for row in filtered:
        by_x[float(row["walks_per_point"])] = row
    return [by_x[k] for k in sorted(by_x)]


def plot_rmse_vs_walks(rows, plt):
    data = latest_by_walks(rows, "convergence")
    if not data:
        print("No convergence rows found; skipping rmse_vs_walks.png")
        return

    x = [float(r["walks_per_point"]) for r in data]
    y = [float(r["rmse"]) for r in data]

    plt.figure(figsize=(6.5, 4.5))
    plt.loglog(x, y, marker="o", label="RMSE")

    if len(x) >= 2 and y[0] > 0:
        ref = [y[0] * math.sqrt(x[0] / xi) for xi in x]
        plt.loglog(x, ref, linestyle="--", label="O(1/sqrt(M))")

    plt.xlabel("walks per point (M)")
    plt.ylabel("RMSE")
    plt.title("Linear Dirichlet convergence")
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(RESULTS / "rmse_vs_walks.png", dpi=180)
    plt.close()


def plot_named_rmse_vs_walks(rows, plt, benchmark_name, output_name, title):
    data = latest_by_walks(rows, benchmark_name)
    if not data:
        print(f"No {benchmark_name} rows found; skipping {output_name}")
        return

    x = [float(r["walks_per_point"]) for r in data]
    y = [float(r["rmse"]) for r in data]

    plt.figure(figsize=(6.5, 4.5))
    plt.loglog(x, y, marker="o", label="RMSE")
    if len(x) >= 2 and y[0] > 0:
        ref = [y[0] * math.sqrt(x[0] / xi) for xi in x]
        plt.loglog(x, ref, linestyle="--", label="O(1/sqrt(M))")
    plt.xlabel("walks per point (M)")
    plt.ylabel("RMSE")
    plt.title(title)
    plt.grid(True, which="both", alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(RESULTS / output_name, dpi=180)
    plt.close()


def plot_epsilon_tradeoff(rows, plt):
    data = latest_by_walks(rows, "epsilon")
    if not data:
        print("No epsilon rows found; skipping epsilon_tradeoff.png")
        return

    by_eps = {}
    for row in [r for r in rows if r.get("benchmark_name") == "epsilon"]:
        by_eps[float(row["epsilon"])] = row
    data = [by_eps[k] for k in sorted(by_eps, reverse=True)]

    eps = [float(r["epsilon"]) for r in data]
    rmse = [float(r["rmse"]) for r in data]
    steps = [float(r["mean_steps"]) for r in data]

    fig, ax1 = plt.subplots(figsize=(6.5, 4.5))
    ax1.set_xscale("log")
    ax1.plot(eps, rmse, marker="o", color="tab:blue", label="RMSE")
    ax1.set_xlabel("epsilon")
    ax1.set_ylabel("RMSE", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.grid(True, which="both", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(eps, steps, marker="s", color="tab:orange", label="mean steps")
    ax2.set_ylabel("mean steps", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    plt.title("Epsilon accuracy/runtime tradeoff")
    fig.tight_layout()
    plt.savefig(RESULTS / "epsilon_tradeoff.png", dpi=180)
    plt.close()


def plot_named_epsilon_tradeoff(rows, plt, benchmark_name, output_name, title):
    filtered = [r for r in rows if r.get("benchmark_name") == benchmark_name]
    if not filtered:
        print(f"No {benchmark_name} rows found; skipping {output_name}")
        return

    by_eps = {}
    for row in filtered:
        by_eps[float(row["epsilon"])] = row
    data = [by_eps[k] for k in sorted(by_eps, reverse=True)]

    eps = [float(r["epsilon"]) for r in data]
    rmse = [float(r["rmse"]) for r in data]
    steps = [float(r["mean_steps"]) for r in data]

    fig, ax1 = plt.subplots(figsize=(6.5, 4.5))
    ax1.set_xscale("log")
    ax1.plot(eps, rmse, marker="o", color="tab:blue", label="RMSE")
    ax1.set_xlabel("epsilon")
    ax1.set_ylabel("RMSE", color="tab:blue")
    ax1.tick_params(axis="y", labelcolor="tab:blue")
    ax1.grid(True, which="both", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(eps, steps, marker="s", color="tab:orange", label="mean steps")
    ax2.set_ylabel("mean steps", color="tab:orange")
    ax2.tick_params(axis="y", labelcolor="tab:orange")

    plt.title(title)
    fig.tight_layout()
    plt.savefig(RESULTS / output_name, dpi=180)
    plt.close()


def latest_named(rows, names):
    out = []
    for name in names:
        matches = [r for r in rows if r.get("benchmark_name") == name]
        if matches:
            out.append(matches[-1])
    return out


def plot_adaptive_vs_fixed(rows, plt):
    data = latest_named(rows, ["adaptive_fixed", "adaptive"])
    if len(data) < 2:
        print("Need adaptive_fixed and adaptive rows; skipping adaptive_vs_fixed.png")
        return

    labels = ["fixed", "adaptive"]
    runtime = [float(r["elapsed_seconds"]) for r in data]
    rmse = [float(r["rmse"]) for r in data]
    samples = [float(r["mean_samples_used"]) for r in data]

    fig, axes = plt.subplots(1, 3, figsize=(9, 3.5))
    for ax, values, title in zip(
        axes,
        [runtime, rmse, samples],
        ["runtime (s)", "RMSE", "mean samples"],
    ):
        ax.bar(labels, values, color=["#4C78A8", "#F58518"])
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.25)

    fig.suptitle("Adaptive sampling vs fixed sampling")
    fig.tight_layout()
    plt.savefig(RESULTS / "adaptive_vs_fixed.png", dpi=180)
    plt.close()


def plot_thread_speedup(rows, plt):
    filtered = [r for r in rows if r.get("benchmark_name") == "thread_scaling"]
    if not filtered:
        print("No thread_scaling rows found; skipping thread_speedup.png")
        return

    by_thread = {}
    for row in filtered:
        by_thread[int(float(row["num_threads"]))] = row
    data = [by_thread[k] for k in sorted(by_thread)]

    threads = [int(float(r["num_threads"])) for r in data]
    times = [float(r["elapsed_seconds"]) for r in data]
    base_time = by_thread.get(1, data[0])
    base = float(base_time["elapsed_seconds"])
    speedup = [base / t if t > 0 else 0.0 for t in times]
    ideal = [t / threads[0] for t in threads]

    plt.figure(figsize=(6.5, 4.5))
    plt.plot(threads, speedup, marker="o", label="measured")
    plt.plot(threads, ideal, linestyle="--", label="ideal linear")
    plt.xlabel("threads")
    plt.ylabel("speedup")
    plt.title("OpenMP thread scaling")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(RESULTS / "thread_speedup.png", dpi=180)
    plt.close()


def plot_bvh_vs_bruteforce(geometry_rows, plt):
    data = [r for r in geometry_rows if r.get("benchmark_name") == "geometry_distance"]
    if not data:
        print("No geometry benchmark rows found; skipping bvh_vs_bruteforce.png")
        return

    by_backend = {}
    for row in data:
        by_backend[str(row["backend_name"])] = row
    ordered_names = [name for name in ["tiny_bvh", "brute_force"] if name in by_backend]
    if not ordered_names:
        print("No recognized geometry backends found; skipping bvh_vs_bruteforce.png")
        return

    qps = [float(by_backend[name]["queries_per_second"]) for name in ordered_names]

    plt.figure(figsize=(6.5, 4.5))
    plt.bar(ordered_names, qps, color=["#4C78A8", "#E45756"][: len(ordered_names)])
    plt.ylabel("distance queries per second")
    plt.title("BVH vs brute-force geometry query throughput")
    plt.grid(True, axis="y", alpha=0.3)
    if len(ordered_names) == 2 and qps[1] > 0:
        ratio = qps[0] / qps[1]
        plt.text(0.5, max(qps) * 0.92, f"{ratio:.1f}x faster", ha="center")
    plt.tight_layout()
    plt.savefig(RESULTS / "bvh_vs_bruteforce.png", dpi=180)
    plt.close()


def main():
    RESULTS.mkdir(exist_ok=True)
    rows = load_rows()
    geometry_rows = load_geometry_rows()
    plt = require_matplotlib()
    plot_rmse_vs_walks(rows, plt)
    plot_epsilon_tradeoff(rows, plt)
    plot_named_rmse_vs_walks(
        rows,
        plt,
        "neumann_convergence",
        "neumann_rmse_vs_walks.png",
        "Mixed Neumann convergence",
    )
    plot_named_epsilon_tradeoff(
        rows,
        plt,
        "neumann_epsilon",
        "neumann_epsilon_tradeoff.png",
        "Mixed Neumann epsilon tradeoff",
    )
    plot_adaptive_vs_fixed(rows, plt)
    plot_thread_speedup(rows, plt)
    plot_bvh_vs_bruteforce(geometry_rows, plt)
    print(f"Wrote plots to {RESULTS}")


if __name__ == "__main__":
    main()
