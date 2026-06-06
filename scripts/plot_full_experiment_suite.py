#!/usr/bin/env python3
"""Plot an all-in-one WoSt experiment run directory."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_float(row: dict, key: str, default: float = float("nan")) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt
        from matplotlib.colors import LogNorm
        return plt, LogNorm
    except Exception as exc:
        raise SystemExit("matplotlib is required for plot_full_experiment_suite.py") from exc


def parse_structured_vtk(path: Path) -> tuple[tuple[int, int, int], dict[str, np.ndarray]]:
    if not path.exists():
        return (0, 0, 0), {}
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    dims = None
    fields: dict[str, np.ndarray] = {}
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if parts[:1] == ["DIMENSIONS"]:
            dims = tuple(int(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["SCALARS"] and dims:
            name = parts[1]
            i += 2
            n = dims[0] * dims[1] * dims[2]
            values = []
            for _ in range(n):
                token = lines[i].strip()
                values.append(float(token) if token.lower() != "nan" else np.nan)
                i += 1
            fields[name] = np.asarray(values, dtype=float).reshape((dims[2], dims[1], dims[0]))
        else:
            i += 1
    return dims or (0, 0, 0), fields


def save_metric_vs_walks(plt, rows: list[dict], out: Path, title: str) -> None:
    if not rows:
        return
    by_walks = {}
    for row in rows:
        by_walks[to_float(row, "walks_per_point")] = row
    data = [by_walks[k] for k in sorted(by_walks)]
    x = [to_float(r, "walks_per_point") for r in data]
    metrics = [
        ("rmse", "RMSE"),
        ("mean_steps", "mean steps"),
        ("elapsed_seconds", "runtime (s)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), constrained_layout=True)
    for ax, (key, label) in zip(axes, metrics):
        y = [to_float(r, key) for r in data]
        ax.plot(x, y, marker="o")
        ax.set_xscale("log")
        if key == "rmse":
            ax.set_yscale("log")
        ax.set_xlabel("walks")
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.25, which="both")
    fig.suptitle(title)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def save_heatmap(plt, matrix: np.ndarray, x_labels: list[str], y_labels: list[str], out: Path, title: str, cbar: str) -> None:
    if matrix.size == 0:
        return
    fig, ax = plt.subplots(figsize=(6.4, 4.8))
    im = ax.imshow(matrix, origin="lower", aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(x_labels)), x_labels)
    ax.set_yticks(range(len(y_labels)), y_labels)
    ax.set_xlabel("walks per point")
    ax.set_ylabel("epsilon")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label=cbar)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=180)
    plt.close(fig)


def plot_epsilon_walk_heatmaps(plt, case_rows: list[dict], fig_dir: Path) -> dict[str, str]:
    if not case_rows:
        return {}
    classifications: dict[str, str] = {}
    by_boundary: dict[str, list[dict]] = defaultdict(list)
    for row in case_rows:
        by_boundary[str(row.get("benchmark_name", "case"))].append(row)

    for boundary, rows in by_boundary.items():
        eps_values = sorted({to_float(r, "epsilon") for r in rows if math.isfinite(to_float(r, "epsilon"))})
        walk_values = sorted({to_float(r, "walks_per_point") for r in rows if math.isfinite(to_float(r, "walks_per_point"))})
        eps_labels = [f"{v:.0e}" for v in eps_values]
        walk_labels = [str(int(v)) for v in walk_values]
        matrices = {}
        for metric in ["rmse", "mean_steps", "elapsed_seconds"]:
            mat = np.full((len(eps_values), len(walk_values)), np.nan)
            for row in rows:
                ei = eps_values.index(to_float(row, "epsilon"))
                wi = walk_values.index(to_float(row, "walks_per_point"))
                mat[ei, wi] = to_float(row, metric)
            matrices[metric] = mat
            save_heatmap(
                plt,
                mat,
                walk_labels,
                eps_labels,
                fig_dir / f"{boundary}_{metric}_heatmap.png",
                f"{boundary}: {metric} heatmap",
                metric,
            )
        rmse = matrices.get("rmse")
        if rmse is not None and rmse.size:
            coarsest_eps = int(np.argmax(eps_values))
            finest_eps = int(np.argmin(eps_values))
            fewest_walks = int(np.argmin(walk_values))
            most_walks = int(np.argmax(walk_values))
            coarse_low = rmse[coarsest_eps, fewest_walks]
            coarse_high = rmse[coarsest_eps, most_walks]
            fine_high = rmse[finest_eps, most_walks]
            walk_gain = (coarse_low - coarse_high) / max(coarse_low, 1e-12)
            eps_gain = (coarse_high - fine_high) / max(coarse_high, 1e-12)
            if walk_gain > 0.25:
                label = "variance-dominated"
            elif eps_gain > 0.25:
                label = "epsilon-bias-dominated"
            else:
                label = "residual-bias/geometry-dominated"
            classifications[boundary] = label
    if len(by_boundary) >= 2:
        names = list(by_boundary.keys())
        a = by_boundary[names[0]]
        b = by_boundary[names[1]]
        joined = {}
        for row in a:
            joined[(to_float(row, "epsilon"), to_float(row, "walks_per_point"))] = to_float(row, "rmse")
        diffs = []
        eps_values = sorted({to_float(r, "epsilon") for r in case_rows})
        walk_values = sorted({to_float(r, "walks_per_point") for r in case_rows})
        mat = np.full((len(eps_values), len(walk_values)), np.nan)
        for row in b:
            key = (to_float(row, "epsilon"), to_float(row, "walks_per_point"))
            if key in joined:
                ei = eps_values.index(key[0])
                wi = walk_values.index(key[1])
                mat[ei, wi] = to_float(row, "rmse") - joined[key]
                diffs.append(mat[ei, wi])
        save_heatmap(
            plt,
            mat,
            [str(int(v)) for v in walk_values],
            [f"{v:.0e}" for v in eps_values],
            fig_dir / "wost_boundary_rmse_difference_heatmap.png",
            "WoSt RMSE difference between boundary modes",
            "RMSE difference",
        )
    return classifications


def plot_boundary_bias(plt, LogNorm, run_dir: Path, fig_dir: Path) -> None:
    vtk = run_dir / "raw" / "boundary_bias_detector.vtk"
    dims, fields = parse_structured_vtk(vtk)
    if not fields:
        return
    z = dims[2] // 2
    panels = [
        ("solution_epsilon", "u(epsilon)", False),
        ("solution_epsilon_half", "u(epsilon/2)", False),
        ("bias_indicator", "absolute bias", True),
        ("normalized_bias", "normalized bias", True),
        ("std_error_epsilon", "standard error", True),
        ("abs_error_epsilon", "absolute error", True),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.2), constrained_layout=True)
    finite_bias = fields.get("bias_indicator", np.asarray([]))
    shared_max = np.nanpercentile(finite_bias, 99) if finite_bias.size else None
    for ax, (field, title, use_log) in zip(axes.ravel(), panels):
        data = fields.get(field)
        if data is None:
            ax.axis("off")
            continue
        img = data[z, :, :]
        norm = None
        if use_log:
            finite = img[np.isfinite(img) & (img > 0)]
            if finite.size:
                vmax = float(shared_max) if field == "bias_indicator" and shared_max else float(np.nanmax(finite))
                norm = LogNorm(vmin=max(float(np.nanmin(finite)), 1e-8), vmax=max(vmax, 1e-8))
        im = ax.imshow(img, origin="lower", cmap="viridis", norm=norm)
        ax.contour(np.isfinite(img), levels=[0.5], colors="white", linewidths=0.5, alpha=0.7)
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.82)
    fig.suptitle("Boundary bias detector: center slice")
    fig.savefig(fig_dir / "boundary_bias_panels.png", dpi=180)
    plt.close(fig)

    bias = fields.get("bias_indicator")
    norm_bias = fields.get("normalized_bias")
    if bias is not None:
        valid = bias[np.isfinite(bias) & (bias > 0)]
        plt.figure(figsize=(6.2, 4.2))
        plt.hist(valid, bins=40, alpha=0.85)
        plt.xlabel("|u_epsilon - u_epsilon/2|")
        plt.ylabel("grid points")
        plt.title("Boundary bias histogram")
        plt.grid(True, axis="y", alpha=0.25)
        plt.tight_layout()
        plt.savefig(fig_dir / "boundary_bias_histogram.png", dpi=180)
        plt.close()
        flat = []
        norm_field = fields.get("normalized_bias")
        for index in np.argwhere(np.isfinite(bias)):
            iz, iy, ix = [int(v) for v in index]
            flat.append({
                "ix": ix,
                "iy": iy,
                "iz": iz,
                "bias_indicator": float(bias[iz, iy, ix]),
                "normalized_bias": float(norm_field[iz, iy, ix]) if norm_field is not None and np.isfinite(norm_field[iz, iy, ix]) else "",
            })
        flat.sort(key=lambda r: float(r["bias_indicator"]), reverse=True)
        top_path = run_dir / "tables" / "top_k_boundary_bias_points.csv"
        top_path.parent.mkdir(parents=True, exist_ok=True)
        with top_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["ix", "iy", "iz", "bias_indicator", "normalized_bias"])
            writer.writeheader()
            writer.writerows(flat[:25])
    if norm_bias is not None:
        valid = norm_bias[np.isfinite(norm_bias) & (norm_bias > 0)]
        plt.figure(figsize=(6.2, 4.2))
        plt.hist(valid, bins=40, alpha=0.85)
        plt.xlabel("normalized bias")
        plt.ylabel("grid points")
        plt.title("Normalized boundary bias histogram")
        plt.grid(True, axis="y", alpha=0.25)
        plt.tight_layout()
        plt.savefig(fig_dir / "boundary_bias_normalized_histogram.png", dpi=180)
        plt.close()


def plot_variance_adaptive(plt, run_dir: Path, fig_dir: Path) -> None:
    rows = read_csv(run_dir / "raw" / "variance_adaptive_comparison.csv")
    points = [r for r in read_csv(run_dir / "raw" / "variance_adaptive_points.csv") if r.get("is_valid", "1") == "1"]
    if rows:
        fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.3), constrained_layout=True)
        x = [to_float(r, "mean_samples_used") for r in rows]
        y = [to_float(r, "rmse") for r in rows]
        labels = [str(r.get("method", "")) for r in rows]
        axes[0].scatter(x, y, s=70)
        for xx, yy, label in zip(x, y, labels):
            axes[0].annotate(label, (xx, yy), xytext=(4, 4), textcoords="offset points", fontsize=8)
        axes[0].set_xlabel("mean samples used")
        axes[0].set_ylabel("RMSE")
        axes[0].set_title("Cost-accuracy tradeoff")
        axes[0].grid(True, alpha=0.25)
        axes[1].bar(labels, x)
        axes[1].set_ylabel("mean samples used")
        axes[1].tick_params(axis="x", rotation=25)
        axes[1].set_title("Adaptive sample budget")
        axes[1].grid(True, axis="y", alpha=0.25)
        fig.savefig(fig_dir / "variance_adaptive_tradeoff_extended.png", dpi=180)
        plt.close(fig)
    if points:
        sample_var = np.asarray([to_float(r, "sample_variance") for r in points])
        samples = np.asarray([to_float(r, "samples_used") for r in points])
        error = np.asarray([to_float(r, "abs_error") for r in points])
        fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.2), constrained_layout=True)
        axes[0, 0].scatter([to_float(r, "x") for r in points], [to_float(r, "y") for r in points], c=samples, s=16)
        axes[0, 0].set_title("samples used map")
        axes[0, 1].scatter(sample_var, samples, s=16, alpha=0.65)
        axes[0, 1].set_xlabel("pilot/final variance")
        axes[0, 1].set_ylabel("samples used")
        axes[1, 0].scatter(sample_var, error, s=16, alpha=0.65)
        axes[1, 0].set_xlabel("pilot/final variance")
        axes[1, 0].set_ylabel("final abs error")
        axes[1, 1].hist(samples[np.isfinite(samples)], bins=30)
        axes[1, 1].set_xlabel("samples used")
        axes[1, 1].set_ylabel("query points")
        for ax in axes.ravel():
            ax.grid(True, alpha=0.22)
        fig.savefig(fig_dir / "variance_adaptive_point_diagnostics.png", dpi=180)
        plt.close(fig)


def plot_antithetic_and_lazy(plt, run_dir: Path, fig_dir: Path) -> None:
    rows = read_csv(run_dir / "raw" / "optimization_summary.csv")
    if not rows:
        return
    for experiment, metric, filename, title in [
        ("antithetic_compare", "mean_sample_variance", "antithetic_variance.png", "Antithetic sample variance"),
        ("antithetic_compare", "rmse", "antithetic_rmse.png", "Antithetic RMSE"),
        ("antithetic_compare", "elapsed_seconds", "antithetic_runtime.png", "Antithetic runtime"),
        ("lazy_refinement", "rmse", "lazy_rmse.png", "Lazy refinement RMSE"),
        ("lazy_refinement", "elapsed_seconds", "lazy_runtime.png", "Lazy refinement runtime"),
    ]:
        data = [r for r in rows if r.get("experiment") == experiment]
        if not data:
            continue
        by_method: dict[str, list[float]] = defaultdict(list)
        for row in data:
            by_method[str(row.get("method"))].append(to_float(row, metric))
        labels = list(by_method.keys())
        values = [float(np.nanmean(by_method[label])) for label in labels]
        errors = [float(np.nanstd(by_method[label])) for label in labels]
        plt.figure(figsize=(7, 4.2))
        plt.bar(labels, values, yerr=errors, capsize=4)
        plt.ylabel(metric.replace("_", " "))
        plt.title(title)
        plt.xticks(rotation=20, ha="right")
        plt.grid(True, axis="y", alpha=0.25)
        plt.tight_layout()
        plt.savefig(fig_dir / filename, dpi=180)
        plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    raw = run_dir / "raw"
    fig_dir = run_dir / "plots"
    fig_dir.mkdir(parents=True, exist_ok=True)
    plt, LogNorm = require_matplotlib()

    save_metric_vs_walks(
        plt,
        read_csv(raw / "dirichlet_accuracy.csv"),
        fig_dir / "dirichlet_accuracy_rmse_steps_runtime.png",
        "Dirichlet accuracy: RMSE, steps, runtime",
    )
    save_metric_vs_walks(
        plt,
        read_csv(raw / "mixed_neumann.csv"),
        fig_dir / "mixed_neumann_rmse_steps_runtime.png",
        "Mixed Neumann: RMSE, steps, runtime",
    )
    classifications = plot_epsilon_walk_heatmaps(plt, read_csv(raw / "epsilon_walks_sweep.csv"), fig_dir)
    if classifications:
        with (run_dir / "epsilon_sweep_classification.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["benchmark_name", "classification"])
            writer.writeheader()
            for key, value in classifications.items():
                writer.writerow({"benchmark_name": key, "classification": value})
    plot_boundary_bias(plt, LogNorm, run_dir, fig_dir)
    plot_variance_adaptive(plt, run_dir, fig_dir)
    plot_antithetic_and_lazy(plt, run_dir, fig_dir)
    print(f"Wrote plots to {fig_dir}")


if __name__ == "__main__":
    main()
