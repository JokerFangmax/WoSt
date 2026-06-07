#!/usr/bin/env python3
"""Run controlled distance/epsilon geometry experiments for WoSt rerun analysis."""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from analyze_geometry_sensitive_rerun import (  # noqa: E402
    as_float,
    mesh_arrays,
    nearest_features,
    parse_obj,
)


DEFAULT_BINS = [(0.05, 0.15), (0.15, 0.30), (0.30, 0.60), (0.60, 1.00)]
DEFAULT_EPSILONS = [1e-2, 1e-3, 1e-4, 1e-5]
DEFAULT_WALKS = [64, 256, 1024]
DEFAULT_PART1_EPSILON = 1e-4
DEFAULT_PART1_WALKS = 256


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_command(cmd: list[str], cwd: Path, log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write("\n$ " + " ".join(str(c) for c in cmd) + f"\n# cwd: {cwd}\n")
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(proc.stdout)
        if proc.stderr:
            f.write("\n[stderr]\n" + proc.stderr)
        f.write(f"\n[exit={proc.returncode}]\n")
    if proc.returncode != 0:
        raise SystemExit(f"Command failed; see {log}")


def parse_list(value: str, cast=float) -> list[Any]:
    return [cast(v.strip()) for v in value.split(",") if v.strip()]


def contains_float(values: list[float], target: float) -> bool:
    return any(math.isclose(value, target, rel_tol=1e-12, abs_tol=1e-15) for value in values)


def is_baseline_run(epsilon: float, walks: int, baseline_epsilon: float, baseline_walks: int) -> bool:
    return math.isclose(epsilon, baseline_epsilon, rel_tol=1e-12, abs_tol=1e-15) and walks == baseline_walks


def load_config(path: Path | None) -> dict[str, Any]:
    config = {
        "meshes": [
            {
                "mesh": "bunny",
                "mesh_variant": "original",
                "obj": "obj/Bunny.obj",
                "cube": 0.22,
                "seed": 12345,
            },
            {
                "mesh": "spot",
                "mesh_variant": "original",
                "obj": "spot/spot_triangulated.obj",
                "cube": 1.1,
                "seed": 54321,
            },
        ],
        "distance_bins": DEFAULT_BINS,
        "epsilons": DEFAULT_EPSILONS,
        "walks": DEFAULT_WALKS,
        "points_per_bin": 24,
        "part1_epsilon": DEFAULT_PART1_EPSILON,
        "part1_walks": DEFAULT_PART1_WALKS,
        "geometry_report": "experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md",
    }
    if path and path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        config.update(loaded)
    return config


def sample_distance_controlled_points(
    mesh_name: str,
    mesh_variant: str,
    arrays: dict[str, np.ndarray],
    cube: float,
    bins: list[tuple[float, float]],
    points_per_bin: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(seed)
    selected: dict[int, list[dict[str, Any]]] = {i: [] for i in range(len(bins))}
    attempts = 0
    batch_size = max(4096, points_per_bin * len(bins) * 64)
    max_attempts = 80
    while any(len(v) < points_per_bin for v in selected.values()) and attempts < max_attempts:
        attempts += 1
        points = rng.uniform(-cube, cube, size=(batch_size, 3))
        local = nearest_features(points, arrays)
        dist = local["nearest_distance_proxy_norm"]
        for i, point in enumerate(points):
            for bin_id, (lo, hi) in enumerate(bins):
                if len(selected[bin_id]) >= points_per_bin:
                    continue
                if lo <= dist[i] < hi:
                    selected[bin_id].append({
                        "mesh": mesh_name,
                        "mesh_variant": mesh_variant,
                        "point_id": len(selected[bin_id]),
                        "distance_bin": bin_id + 1,
                        "bin_min": lo,
                        "bin_max": hi,
                        "x": float(point[0]),
                        "y": float(point[1]),
                        "z": float(point[2]),
                        "nearest_distance_proxy_norm": float(dist[i]),
                        "local_edge_mean_norm": float(local["local_edge_mean_norm"][i]),
                        "local_area_norm": float(local["local_area_norm"][i]),
                        "local_aspect_ratio": float(local["local_aspect_ratio"][i]),
                        "local_quality": float(local["local_quality"][i]),
                        "local_normal_variation": float(local["local_normal_variation"][i]),
                    })
    rows: list[dict[str, Any]] = []
    order = 0
    for bin_id in range(len(bins)):
        for row in selected[bin_id]:
            row["point_index"] = order
            order += 1
            rows.append(row)
    return rows


def point_count_rows(mesh: str, variant: str, points: list[dict[str, Any]], bins: list[tuple[float, float]], requested: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bin_id, (lo, hi) in enumerate(bins, start=1):
        count = sum(1 for row in points if int(row["distance_bin"]) == bin_id)
        rows.append({
            "mesh": mesh,
            "mesh_variant": variant,
            "distance_bin": bin_id,
            "bin_min": lo,
            "bin_max": hi,
            "requested_points": requested,
            "sampled_points": count,
            "complete": int(count >= requested),
        })
    return rows


def merge_point_rows(meta_rows: list[dict[str, Any]], result_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_index = {int(as_float(row.get("point_index"))): row for row in result_rows}
    merged: list[dict[str, Any]] = []
    for meta in meta_rows:
        idx = int(meta["point_index"])
        result = by_index.get(idx, {})
        out = dict(meta)
        out.update(result)
        # Preserve metadata if the result CSV also has x/y/z or mesh columns.
        for key in ["mesh", "mesh_variant", "distance_bin", "bin_min", "bin_max",
                    "nearest_distance_proxy_norm", "local_edge_mean_norm", "local_area_norm",
                    "local_aspect_ratio", "local_quality", "local_normal_variation"]:
            out[key] = meta[key]
        merged.append(out)
    return merged


def summarize_groups(rows: list[dict[str, Any]], group_keys: list[str], metrics: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if str(row.get("is_valid", "1")) not in {"1", "True", "true"}:
            continue
        groups[tuple(row.get(key, "") for key in group_keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, items in sorted(groups.items(), key=lambda kv: tuple(str(v) for v in kv[0])):
        row = {k: v for k, v in zip(group_keys, key)}
        row["n"] = len(items)
        for metric in metrics:
            values = np.asarray([as_float(item.get(metric)) for item in items], dtype=float)
            values = values[np.isfinite(values)]
            if values.size:
                row[f"{metric}_mean"] = float(np.mean(values))
                row[f"{metric}_median"] = float(np.median(values))
                row[f"{metric}_rmse"] = float(math.sqrt(np.mean(values * values))) if metric == "abs_error" else ""
        out.append(row)
    return out


def rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values)
    ranks = np.empty(len(values), dtype=float)
    sorted_vals = values[order]
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and sorted_vals[j] == sorted_vals[i]:
            j += 1
        rank = 0.5 * (i + j - 1) + 1.0
        ranks[order[i:j]] = rank
        i = j
    return ranks


def corr(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 5:
        return float("nan")
    xx, yy = x[mask], y[mask]
    if float(np.std(xx)) == 0.0 or float(np.std(yy)) == 0.0:
        return float("nan")
    return float(np.corrcoef(xx, yy)[0, 1])


def partial_corr(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if int(mask.sum()) < 8:
        return float("nan")
    xx, yy, zz = x[mask], y[mask], z[mask]
    X = np.column_stack([np.ones_like(zz), zz])
    bx = np.linalg.lstsq(X, xx, rcond=None)[0]
    by = np.linalg.lstsq(X, yy, rcond=None)[0]
    rx = xx - X @ bx
    ry = yy - X @ by
    return corr(rx, ry)


def regression_summary(rows: list[dict[str, Any]], target: str, features: list[str], mesh: str) -> tuple[list[dict[str, Any]], str]:
    sub = [r for r in rows if r.get("mesh") == mesh and str(r.get("is_valid", "1")) in {"1", "true", "True"}]
    y = np.asarray([as_float(r.get(target)) for r in sub], dtype=float)
    X_cols = [np.asarray([as_float(r.get(f)) for r in sub], dtype=float) for f in features]
    mask = np.isfinite(y)
    for col in X_cols:
        mask &= np.isfinite(col)
    if int(mask.sum()) < len(features) + 4:
        return [], f"Not enough rows for {mesh} {target}."
    yy = y[mask]
    X_raw = np.column_stack([col[mask] for col in X_cols])
    mu = np.mean(X_raw, axis=0)
    sigma = np.std(X_raw, axis=0)
    sigma[sigma == 0] = 1.0
    X_std = (X_raw - mu) / sigma
    X = np.column_stack([np.ones(len(yy)), X_std])
    beta = np.linalg.lstsq(X, yy, rcond=None)[0]
    pred = X @ beta
    ss_res = float(np.sum((yy - pred) ** 2))
    ss_tot = float(np.sum((yy - np.mean(yy)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rows_out = [{
        "mesh": mesh,
        "target": target,
        "term": "intercept",
        "standardized_beta": "",
        "coefficient": float(beta[0]),
        "r2": r2,
        "n": int(mask.sum()),
    }]
    for feature, coef in zip(features, beta[1:]):
        rows_out.append({
            "mesh": mesh,
            "target": target,
            "term": feature,
            "standardized_beta": float(coef),
            "coefficient": float(coef / sigma[features.index(feature)]),
            "r2": r2,
            "n": int(mask.sum()),
        })
    summary = f"{mesh} {target}: n={int(mask.sum())}, R2={r2:.3f}"
    return rows_out, summary


def controlled_correlations(rows: list[dict[str, Any]], dataset: str, target: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    data = [r for r in rows if r.get("dataset") == dataset and str(r.get("is_valid", "1")) in {"1", "true", "True"}]
    features = [
        "nearest_distance_proxy_norm",
        "local_normal_variation",
        "local_edge_mean_norm",
        "local_aspect_ratio",
        "local_quality",
    ]
    out: list[dict[str, Any]] = []
    regression_rows: list[dict[str, Any]] = []
    regression_lines: list[str] = []
    for mesh in sorted({r["mesh"] for r in data}):
        sub = [r for r in data if r["mesh"] == mesh]
        y = np.asarray([as_float(r.get(target)) for r in sub], dtype=float)
        z = np.asarray([as_float(r.get("nearest_distance_proxy_norm")) for r in sub], dtype=float)
        for feature in features:
            x = np.asarray([as_float(r.get(feature)) for r in sub], dtype=float)
            out.append({
                "mesh": mesh,
                "dataset": dataset,
                "target": target,
                "feature": feature,
                "pearson_r": corr(x, y),
                "spearman_r": corr(rankdata(x[np.isfinite(x)]) if np.isfinite(x).all() else rank_with_nan(x),
                                   rankdata(y[np.isfinite(y)]) if np.isfinite(y).all() else rank_with_nan(y)),
                "partial_r_control_nearest_distance": "" if feature == "nearest_distance_proxy_norm" else partial_corr(x, y, z),
                "n": int((np.isfinite(x) & np.isfinite(y)).sum()),
            })
        reg, line = regression_summary(
            [{**r, "dataset": dataset} for r in sub],
            target,
            ["nearest_distance_proxy_norm", "local_normal_variation", "local_edge_mean_norm", "local_aspect_ratio"],
            mesh,
        )
        regression_rows.extend(reg)
        regression_lines.append(line)
    return out, regression_rows, regression_lines


def rank_with_nan(values: np.ndarray) -> np.ndarray:
    out = np.full(len(values), np.nan, dtype=float)
    mask = np.isfinite(values)
    out[mask] = rankdata(values[mask])
    return out


def try_random_forest(rows: list[dict[str, Any]], dataset: str, target: str) -> list[dict[str, Any]]:
    try:
        from sklearn.ensemble import RandomForestRegressor  # type: ignore
    except Exception:
        return []
    data = [r for r in rows if r.get("dataset") == dataset and str(r.get("is_valid", "1")) in {"1", "true", "True"}]
    features = ["nearest_distance_proxy_norm", "local_normal_variation", "local_edge_mean_norm", "local_aspect_ratio"]
    out: list[dict[str, Any]] = []
    for mesh in sorted({r["mesh"] for r in data}):
        sub = [r for r in data if r["mesh"] == mesh]
        X = np.asarray([[as_float(r.get(f)) for f in features] for r in sub], dtype=float)
        y = np.asarray([as_float(r.get(target)) for r in sub], dtype=float)
        mask = np.isfinite(y) & np.all(np.isfinite(X), axis=1)
        if int(mask.sum()) < 20:
            continue
        model = RandomForestRegressor(n_estimators=200, random_state=0, min_samples_leaf=4)
        model.fit(X[mask], y[mask])
        for feature, importance in zip(features, model.feature_importances_):
            out.append({
                "mesh": mesh,
                "dataset": dataset,
                "target": target,
                "feature": feature,
                "random_forest_importance": float(importance),
                "n": int(mask.sum()),
            })
    return out


def plot_results(out_dir: Path, neumann_summary: list[dict[str, Any]], bias_summary: list[dict[str, Any]], sweep: list[dict[str, Any]], point_rows: list[dict[str, Any]]) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return

    fig_dir = out_dir / "plots"
    heat_dir = out_dir / "epsilon_distance_heatmaps"
    fig_dir.mkdir(parents=True, exist_ok=True)
    heat_dir.mkdir(parents=True, exist_ok=True)

    for metric, ylabel, filename in [
        ("abs_error_mean", "mean abs error", "distance_bin_vs_mean_abs_error.png"),
        ("mean_steps_mean", "mean steps", "distance_bin_vs_mean_steps.png"),
        ("sample_variance_mean", "sample variance", "distance_bin_vs_sample_variance.png"),
    ]:
        plt.figure(figsize=(7, 4.5))
        for mesh in sorted({r["mesh"] for r in neumann_summary}):
            rows = [r for r in neumann_summary if r["mesh"] == mesh]
            rows = sorted(rows, key=lambda r: int(as_float(r["distance_bin"])))
            plt.plot([as_float(r["distance_bin"]) for r in rows], [as_float(r.get(metric)) for r in rows], marker="o", label=mesh)
        plt.xlabel("distance bin")
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.savefig(fig_dir / filename, dpi=180)
        plt.close()

    plt.figure(figsize=(7, 4.5))
    for mesh in sorted({r["mesh"] for r in bias_summary}):
        rows = [r for r in bias_summary if r["mesh"] == mesh]
        rows = sorted(rows, key=lambda r: int(as_float(r["distance_bin"])))
        plt.plot([as_float(r["distance_bin"]) for r in rows], [as_float(r.get("bias_indicator_mean")) for r in rows], marker="o", label=mesh)
    plt.xlabel("distance bin")
    plt.ylabel("mean boundary bias")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig_dir / "distance_bin_vs_mean_boundary_bias.png", dpi=180)
    plt.close()

    def grouped_bar(summary: list[dict[str, Any]], metric: str, ylabel: str, filename: str) -> None:
        bins = sorted({int(as_float(r["distance_bin"])) for r in summary})
        meshes = sorted({r["mesh"] for r in summary})
        if not bins or not meshes:
            return
        x = np.arange(len(bins), dtype=float)
        width = min(0.35, 0.8 / max(len(meshes), 1))
        fig, ax = plt.subplots(figsize=(7.2, 4.5), constrained_layout=True)
        for m_idx, mesh in enumerate(meshes):
            offsets = x + (m_idx - (len(meshes) - 1) / 2.0) * width
            values = []
            for bin_id in bins:
                row = next((r for r in summary if r["mesh"] == mesh and int(as_float(r["distance_bin"])) == bin_id), {})
                values.append(as_float(row.get(metric)))
            ax.bar(offsets, values, width=width, label=mesh)
        ax.set_xticks(x, [str(b) for b in bins])
        ax.set_xlabel("distance bin")
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend()
        fig.savefig(fig_dir / filename, dpi=180)
        plt.close(fig)

    grouped_bar(neumann_summary, "abs_error_mean", "mean abs error", "matched_bins_bunny_vs_spot_abs_error.png")
    grouped_bar(neumann_summary, "mean_steps_mean", "mean steps", "matched_bins_bunny_vs_spot_mean_steps.png")
    grouped_bar(neumann_summary, "sample_variance_mean", "sample variance", "matched_bins_bunny_vs_spot_sample_variance.png")
    grouped_bar(bias_summary, "bias_indicator_mean", "mean boundary bias", "matched_bins_bunny_vs_spot_boundary_bias.png")

    for mesh in sorted({r["mesh"] for r in sweep}):
        for metric, filename in [
            ("rmse", "epsilon_vs_distance_rmse.png"),
            ("mean_bias", "epsilon_vs_distance_mean_bias.png"),
            ("mean_steps", "epsilon_vs_distance_mean_steps.png"),
        ]:
            rows = [r for r in sweep if r["mesh"] == mesh]
            eps_values = sorted({as_float(r["epsilon"]) for r in rows})
            bins = sorted({int(as_float(r["distance_bin"])) for r in rows})
            mat = np.full((len(eps_values), len(bins)), np.nan)
            for row in rows:
                e = eps_values.index(as_float(row["epsilon"]))
                b = bins.index(int(as_float(row["distance_bin"])))
                mat[e, b] = as_float(row.get(metric))
            fig, ax = plt.subplots(figsize=(6.2, 4.5), constrained_layout=True)
            im = ax.imshow(mat, aspect="auto", origin="lower", cmap="viridis")
            ax.set_yticks(range(len(eps_values)), [f"{v:.0e}" for v in eps_values])
            ax.set_xticks(range(len(bins)), [str(v) for v in bins])
            ax.set_xlabel("distance bin")
            ax.set_ylabel("epsilon")
            ax.set_title(f"{mesh}: {metric}")
            fig.colorbar(im, ax=ax, label=metric)
            fig.savefig(heat_dir / f"{mesh}_{filename}", dpi=180)
            plt.close(fig)

    for mesh in sorted({r["mesh"] for r in point_rows}):
        rows = [r for r in point_rows if r["mesh"] == mesh and r.get("dataset") == "part1_neumann"]
        if not rows:
            continue
        x = np.asarray([as_float(r["nearest_distance_proxy_norm"]) for r in rows], dtype=float)
        for feature in ["local_normal_variation", "local_edge_mean_norm"]:
            y = np.asarray([as_float(r["abs_error"]) for r in rows], dtype=float)
            c = np.asarray([as_float(r[feature]) for r in rows], dtype=float)
            mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(c)
            fig, ax = plt.subplots(figsize=(5.8, 4.3), constrained_layout=True)
            sc = ax.scatter(x[mask], y[mask], c=c[mask], s=22, cmap="viridis")
            if int(mask.sum()) > 3:
                coef = np.polyfit(x[mask], y[mask], 1)
                xx = np.linspace(float(np.min(x[mask])), float(np.max(x[mask])), 100)
                ax.plot(xx, coef[0] * xx + coef[1], color="black", lw=1.2)
            ax.set_xlabel("nearest distance proxy norm")
            ax.set_ylabel("abs error")
            ax.set_title(f"{mesh}: error vs distance colored by {feature}")
            fig.colorbar(sc, ax=ax, label=feature)
            fig.savefig(fig_dir / f"{mesh}_scatter_error_distance_{feature}.png", dpi=180)
            plt.close(fig)

        for feature in ["local_normal_variation", "local_edge_mean_norm", "local_aspect_ratio"]:
            x_feature = np.asarray([as_float(r[feature]) for r in rows], dtype=float)
            y = np.asarray([as_float(r["abs_error"]) for r in rows], dtype=float)
            c = np.asarray([as_float(r["nearest_distance_proxy_norm"]) for r in rows], dtype=float)
            mask = np.isfinite(x_feature) & np.isfinite(y) & np.isfinite(c)
            fig, ax = plt.subplots(figsize=(5.8, 4.3), constrained_layout=True)
            sc = ax.scatter(x_feature[mask], y[mask], c=c[mask], s=22, cmap="viridis")
            if int(mask.sum()) > 3 and float(np.std(x_feature[mask])) > 0.0:
                coef = np.polyfit(x_feature[mask], y[mask], 1)
                xx = np.linspace(float(np.min(x_feature[mask])), float(np.max(x_feature[mask])), 100)
                ax.plot(xx, coef[0] * xx + coef[1], color="black", lw=1.2)
            ax.set_xlabel(feature)
            ax.set_ylabel("abs error")
            ax.set_title(f"{mesh}: error vs {feature}")
            fig.colorbar(sc, ax=ax, label="nearest distance proxy norm")
            fig.savefig(fig_dir / f"{mesh}_scatter_error_{feature}.png", dpi=180)
            plt.close(fig)


def controlled_cross_mesh_sentence(neumann_summary: list[dict[str, Any]]) -> str:
    by_mesh_bin = {(r["mesh"], int(as_float(r["distance_bin"]))): r for r in neumann_summary}
    ratios: list[float] = []
    for bin_id in sorted({int(as_float(r["distance_bin"])) for r in neumann_summary}):
        bunny = by_mesh_bin.get(("bunny", bin_id))
        spot = by_mesh_bin.get(("spot", bin_id))
        if bunny and spot and as_float(bunny.get("abs_error_mean")) > 0:
            ratios.append(as_float(spot.get("abs_error_mean")) / as_float(bunny.get("abs_error_mean")))
    if not ratios:
        return "The matched-bin Bunny/Spot comparison could not be evaluated because at least one mesh/bin pair has no valid rows."
    mean_ratio = float(np.mean(ratios))
    if mean_ratio > 1.15:
        return (
            f"Across matched distance bins, Spot's mean absolute Neumann error is about `{mean_ratio:.2f}x` Bunny's. "
            "That supports remaining mesh, shape, reflection, or normal-error effects after reducing the query-distance confounder."
        )
    if mean_ratio < 0.85:
        return (
            f"Across matched distance bins, Spot's mean absolute Neumann error is about `{mean_ratio:.2f}x` Bunny's. "
            "In this controlled run, the original Spot-hardness gap does not persist."
        )
    return (
        f"Across matched distance bins, Spot and Bunny are close in mean absolute Neumann error (`{mean_ratio:.2f}x`). "
        "That suggests the original query-distance distribution was a major confounder."
    )


def normal_variation_sentence(corr_rows: list[dict[str, Any]], reg_rows: list[dict[str, Any]]) -> str:
    partials = [
        abs(as_float(row.get("partial_r_control_nearest_distance")))
        for row in corr_rows
        if row.get("feature") == "local_normal_variation" and math.isfinite(as_float(row.get("partial_r_control_nearest_distance")))
    ]
    betas = [
        abs(as_float(row.get("standardized_beta")))
        for row in reg_rows
        if row.get("term") == "local_normal_variation" and math.isfinite(as_float(row.get("standardized_beta")))
    ]
    signal = max(partials + betas, default=float("nan"))
    if not math.isfinite(signal):
        return "The available rows were insufficient to judge local normal variation after controlling for boundary proximity."
    if signal >= 0.15:
        return "After controlling for boundary proximity, local normal variation still has additional explanatory power in this descriptive run."
    return "After controlling for boundary proximity, local normal variation does not have strong additional explanatory power in this descriptive run."


def write_report(
    out_dir: Path,
    neumann_summary: list[dict[str, Any]],
    bias_summary: list[dict[str, Any]],
    sweep: list[dict[str, Any]],
    corr_rows: list[dict[str, Any]],
    reg_rows: list[dict[str, Any]],
    reg_lines: list[str],
    rf_rows: list[dict[str, Any]],
    config: dict[str, Any],
) -> None:
    lines = [
        "# Controlled Geometry Findings",
        "",
        "This report extends the correlation-style geometry analysis with distance-controlled query bins and epsilon-by-distance sweeps. Language is intentionally cautious: these experiments reduce confounding but do not prove causality.",
        "",
        "## Stable Pointwise Observations",
        "",
        "- Near-boundary queries are harder: mean Neumann error, mean steps, and sample variance are largest in the closest distance bins.",
        "- Coarse epsilon increases boundary sensitivity, especially in close-distance bins.",
        "- Nearest-surface distance remains a proxy; it is useful but not a full geometric explanation.",
        "",
        "## Controlled Cross-Mesh Findings",
        "",
        "| Distance bin | Bunny abs error | Spot abs error | Spot / Bunny | Bunny steps | Spot steps |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    by_mesh_bin = {(r["mesh"], int(as_float(r["distance_bin"]))): r for r in neumann_summary}
    for bin_id in sorted({int(as_float(r["distance_bin"])) for r in neumann_summary}):
        b = by_mesh_bin.get(("bunny", bin_id))
        s = by_mesh_bin.get(("spot", bin_id))
        if not b or not s:
            continue
        b_err = as_float(b.get("abs_error_mean"))
        s_err = as_float(s.get("abs_error_mean"))
        lines.append(
            f"| {bin_id} | {b_err:.5g} | {s_err:.5g} | {s_err / b_err if b_err else float('nan'):.3f} | "
            f"{as_float(b.get('mean_steps_mean')):.3f} | {as_float(s.get('mean_steps_mean')):.3f} |"
        )

    lines += ["", controlled_cross_mesh_sentence(neumann_summary)]

    lines += [
        "",
        "## Epsilon x Distance Findings",
        "",
        "| Mesh | Distance bin | epsilon | walks | RMSE | mean bias | mean steps |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in sweep:
        if int(as_float(row.get("walks"))) != 256:
            continue
        lines.append(
            f"| {row['mesh']} | {row['distance_bin']} | {as_float(row['epsilon']):.0e} | {int(as_float(row['walks']))} | "
            f"{as_float(row.get('rmse')):.5g} | {as_float(row.get('mean_bias')):.5g} | {as_float(row.get('mean_steps')):.3f} |"
        )

    lines += [
        "",
        "Interpretation:",
        "",
        "- If RMSE and bias decrease sharply as epsilon decreases in close bins, the error is boundary/epsilon driven.",
        "- If close-bin error remains high at small epsilon and high walks, the residual is likely tied to geometry, reflection behavior, normals, or shape-specific path behavior.",
        "",
        "## Partial Correlation and Regression",
        "",
        "| Mesh | Feature | Pearson | Spearman | Partial r controlling distance | n |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in corr_rows:
        if row.get("target") != "abs_error":
            continue
        partial = row.get("partial_r_control_nearest_distance", "")
        partial_text = "" if partial == "" else f"{as_float(partial):.3f}"
        lines.append(
            f"| {row['mesh']} | {row['feature']} | {as_float(row['pearson_r']):.3f} | "
            f"{as_float(row['spearman_r']):.3f} | {partial_text} | {row['n']} |"
        )

    lines += [
        "",
        "Regression summaries:",
        "",
    ]
    for line in reg_lines:
        lines.append(f"- {line}")
    lines += ["", normal_variation_sentence(corr_rows, reg_rows)]

    lines += [
        "",
        "| Mesh | Term | standardized beta | R2 | n |",
        "|---|---|---:|---:|---:|",
    ]
    for row in reg_rows:
        if row["term"] == "intercept":
            continue
        lines.append(
            f"| {row['mesh']} | {row['term']} | {as_float(row['standardized_beta']):.5g} | "
            f"{as_float(row['r2']):.3f} | {row['n']} |"
        )

    if rf_rows:
        lines += [
            "",
            "Random forest feature importance was available:",
            "",
            "| Mesh | Feature | Importance |",
            "|---|---|---:|",
        ]
        for row in rf_rows:
            lines.append(f"| {row['mesh']} | {row['feature']} | {as_float(row['random_forest_importance']):.3f} |")
    else:
        lines += ["", "Random forest feature importance was skipped because scikit-learn was not available or there were not enough rows."]

    lines += [
        "",
        "## Remeshed Variant Support",
        "",
        "The pipeline records `mesh_variant` for every row. Supported config values include `original`, `decimated`, `subdivided`, and `smoothed_normals`; this script does not generate those meshes automatically.",
        "",
        "Same-shape remeshed variants are needed to separate mesh-quality effects from shape and query-distribution effects. Bunny-vs-Spot comparisons still mix shape, scale, mesh density, local feature size, and query distribution.",
        "",
        "## Remaining Limitations",
        "",
        "- Nearest-surface distance is a nearest-centroid proxy, not an exact signed distance or local feature-size distance.",
        "- Matching distance bins reduces one confounder but does not make Bunny and Spot the same shape.",
        "- Bunny and Spot alone are not enough for universal geometry conclusions.",
        "- Stronger causality requires remeshed variants of the same shape or synthetic stress-test meshes.",
        "",
        "## Files",
        "",
        "- `distance_controlled_neumann.csv`",
        "- `distance_controlled_bias.csv`",
        "- `epsilon_distance_sweep.csv`",
        "- `controlled_geometry_correlations.csv`",
        "- `geometry_regression_summary.md`",
        "- `epsilon_distance_heatmaps/`",
        "- `plots/`",
        "- `controlled_geometry_config.json`",
    ]
    (out_dir / "CONTROLLED_GEOMETRY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    reg_md = [
        "# Geometry Regression Summary",
        "",
        "Model: `error ~ nearest_distance + local_normal_variation + local_edge_mean + local_aspect_ratio`.",
        "",
        "These regressions are descriptive only and should not be read causally.",
        "",
    ]
    reg_md.extend(f"- {line}" for line in reg_lines)
    reg_md += [
        "",
        "| Mesh | Term | standardized beta | R2 | n |",
        "|---|---|---:|---:|---:|",
    ]
    for row in reg_rows:
        if row["term"] == "intercept":
            continue
        reg_md.append(
            f"| {row['mesh']} | {row['term']} | {as_float(row['standardized_beta']):.6g} | "
            f"{as_float(row['r2']):.3f} | {row['n']} |"
        )
    (out_dir / "geometry_regression_summary.md").write_text("\n".join(reg_md) + "\n", encoding="utf-8")


def update_geometry_sensitive_report(
    report_path: Path,
    out_dir: Path,
    neumann_summary: list[dict[str, Any]],
    corr_rows: list[dict[str, Any]],
    reg_rows: list[dict[str, Any]],
) -> None:
    if not report_path.exists():
        return
    marker = "## Controlled Geometry Findings"
    text = report_path.read_text(encoding="utf-8")
    files_marker = "\n## Files"
    if marker in text:
        before, rest = text.split(marker, 1)
        suffix = files_marker + rest.split(files_marker, 1)[1] if files_marker in rest else ""
    elif files_marker in text:
        before, rest = text.split(files_marker, 1)
        suffix = files_marker + rest
    else:
        before = text
        suffix = ""
    by_mesh_bin = {(r["mesh"], int(as_float(r["distance_bin"]))): r for r in neumann_summary}
    table = [
        "| Distance bin | Bunny abs error | Spot abs error | Spot / Bunny |",
        "|---:|---:|---:|---:|",
    ]
    for bin_id in sorted({int(as_float(r["distance_bin"])) for r in neumann_summary}):
        bunny = by_mesh_bin.get(("bunny", bin_id))
        spot = by_mesh_bin.get(("spot", bin_id))
        if not bunny or not spot:
            continue
        bunny_err = as_float(bunny.get("abs_error_mean"))
        spot_err = as_float(spot.get("abs_error_mean"))
        ratio = spot_err / bunny_err if bunny_err > 0 else float("nan")
        table.append(f"| {bin_id} | {bunny_err:.5g} | {spot_err:.5g} | {ratio:.3f} |")

    try:
        rel_out = out_dir.relative_to(ROOT)
    except ValueError:
        rel_out = out_dir
    section = [
        marker,
        "",
        "This section is generated by `scripts/run_controlled_geometry_experiments.py` and should be read as controlled empirical evidence, not a causal proof.",
        "",
        "### Stable Pointwise Observations",
        "",
        "- Near-boundary queries are harder in the controlled point sets: the closest distance bins concentrate larger Neumann errors, larger sample variance, longer walks, and stronger epsilon sensitivity.",
        "- Coarse epsilon increases boundary sensitivity, especially in the close-distance bins.",
        "",
        "### Controlled Cross-Mesh Findings",
        "",
        *table,
        "",
        controlled_cross_mesh_sentence(neumann_summary),
        "",
        "### Geometry After Distance Control",
        "",
        normal_variation_sentence(corr_rows, reg_rows),
        "",
        "The regression is descriptive: `error ~ nearest_distance + local_normal_variation + local_edge_mean + local_aspect_ratio`. Do not interpret coefficients causally.",
        "",
        "### Remaining Limitations",
        "",
        "- Nearest-surface distance is still a nearest-centroid proxy, not an exact signed distance or local feature-size distance.",
        "- Bunny and Spot are not enough for universal geometry conclusions.",
        "- Stronger causality requires same-shape remeshed variants or synthetic stress-test meshes.",
        f"- Full controlled outputs live in `{rel_out.as_posix()}/`, including `distance_controlled_neumann.csv`, `distance_controlled_bias.csv`, `epsilon_distance_sweep.csv`, heatmaps, and regression summaries.",
        "",
    ]
    report_path.write_text(before.rstrip() + "\n\n" + "\n".join(section).rstrip() + "\n\n" + suffix.lstrip("\n"), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="experiments/controlled_geometry_experiments_20260606")
    parser.add_argument("--config")
    parser.add_argument("--points-per-bin", type=int)
    parser.add_argument("--epsilons")
    parser.add_argument("--walks")
    parser.add_argument("--part1-epsilon", type=float)
    parser.add_argument("--part1-walks", type=int)
    parser.add_argument("--geometry-report")
    parser.add_argument("--skip-run", action="store_true")
    args = parser.parse_args()

    out_dir = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    raw_dir = out_dir / "raw"
    point_dir = out_dir / "point_lists"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    point_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "command_log.txt"
    log.write_text("# Controlled geometry experiment command log\n", encoding="utf-8")

    config = load_config(Path(args.config) if args.config else None)
    if args.points_per_bin:
        config["points_per_bin"] = args.points_per_bin
    if args.epsilons:
        config["epsilons"] = parse_list(args.epsilons, float)
    if args.walks:
        config["walks"] = parse_list(args.walks, int)
    if args.part1_epsilon is not None:
        config["part1_epsilon"] = args.part1_epsilon
    if args.part1_walks is not None:
        config["part1_walks"] = args.part1_walks
    if args.geometry_report:
        config["geometry_report"] = args.geometry_report
    bins = [tuple(map(float, b)) for b in config["distance_bins"]]
    epsilons = [float(e) for e in config["epsilons"]]
    walks_values = [int(w) for w in config["walks"]]
    part1_epsilon = float(config.get("part1_epsilon", DEFAULT_PART1_EPSILON))
    part1_walks = int(config.get("part1_walks", DEFAULT_PART1_WALKS))
    if not contains_float(epsilons, part1_epsilon):
        epsilons.append(part1_epsilon)
        epsilons = sorted(epsilons, reverse=True)
        config["epsilons"] = epsilons
    if part1_walks not in walks_values:
        walks_values.append(part1_walks)
        walks_values = sorted(walks_values)
        config["walks"] = walks_values
    points_per_bin = int(config["points_per_bin"])
    (out_dir / "controlled_geometry_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    exe = ROOT / "build" / "Release" / "wost.exe"
    if not exe.exists():
        raise SystemExit(f"Missing {exe}; build first.")

    point_meta_by_mesh: dict[str, list[dict[str, Any]]] = {}
    count_rows: list[dict[str, Any]] = []
    for mesh_cfg in config["meshes"]:
        mesh = mesh_cfg["mesh"]
        variant = mesh_cfg.get("mesh_variant", "original")
        obj = ROOT / mesh_cfg["obj"] if not Path(mesh_cfg["obj"]).is_absolute() else Path(mesh_cfg["obj"])
        vertices, faces = parse_obj(obj)
        _summary, arrays = mesh_arrays(vertices, faces)
        points = sample_distance_controlled_points(
            mesh,
            variant,
            arrays,
            float(mesh_cfg["cube"]),
            bins,
            points_per_bin,
            int(mesh_cfg["seed"]),
        )
        point_meta_by_mesh[mesh] = points
        count_rows.extend(point_count_rows(mesh, variant, points, bins, points_per_bin))
        write_csv(point_dir / f"{mesh}_{variant}_distance_controlled_points.csv", points)

    neumann_rows: list[dict[str, Any]] = []
    bias_rows: list[dict[str, Any]] = []
    sweep_rows: list[dict[str, Any]] = []
    for mesh_cfg in config["meshes"]:
        mesh = mesh_cfg["mesh"]
        variant = mesh_cfg.get("mesh_variant", "original")
        obj = ROOT / mesh_cfg["obj"] if not Path(mesh_cfg["obj"]).is_absolute() else Path(mesh_cfg["obj"])
        cube = float(mesh_cfg["cube"])
        seed = int(mesh_cfg["seed"])
        points_path = point_dir / f"{mesh}_{variant}_distance_controlled_points.csv"
        meta = point_meta_by_mesh[mesh]

        for eps in epsilons:
            for walks in walks_values:
                result_csv = raw_dir / f"{mesh}_{variant}_points_eps_{eps:.0e}_walks_{walks}.csv"
                if not args.skip_run and not result_csv.exists():
                    run_command([
                        str(exe),
                        "--mode", "points",
                        "--obj", str(obj),
                        "--cube", str(cube),
                        "--threads", "8",
                        "--seed", str(seed + walks),
                        "--boundary", "neumann",
                        "--epsilon", str(eps),
                        "--walks", str(walks),
                        "--points-in", str(points_path),
                        "--out", str(result_csv),
                    ], ROOT, log)
                merged = merge_point_rows(meta, read_csv(result_csv))
                for row in merged:
                    row["dataset"] = "part1_neumann" if is_baseline_run(eps, walks, part1_epsilon, part1_walks) else "epsilon_distance_neumann"
                    row["epsilon"] = eps
                    row["walks"] = walks
                if is_baseline_run(eps, walks, part1_epsilon, part1_walks):
                    neumann_rows.extend(merged)
                sweep_point_rows = merged

                bias_csv = raw_dir / f"{mesh}_{variant}_bias_eps_{eps:.0e}_walks_{walks}.csv"
                if not args.skip_run and not bias_csv.exists():
                    run_command([
                        str(exe),
                        "--mode", "point_bias",
                        "--obj", str(obj),
                        "--cube", str(cube),
                        "--threads", "8",
                        "--seed", str(seed + walks + 7000),
                        "--boundary", "neumann",
                        "--epsilon", str(eps),
                        "--walks", str(walks),
                        "--points-in", str(points_path),
                        "--out", str(bias_csv),
                    ], ROOT, log)
                bias_merged = merge_point_rows(meta, read_csv(bias_csv))
                for row in bias_merged:
                    row["dataset"] = "part1_bias" if is_baseline_run(eps, walks, part1_epsilon, part1_walks) else "epsilon_distance_bias"
                    row["epsilon"] = eps
                    row["walks"] = walks
                if is_baseline_run(eps, walks, part1_epsilon, part1_walks):
                    bias_rows.extend(bias_merged)

                by_bin_neu = summarize_groups(
                    sweep_point_rows,
                    ["mesh", "mesh_variant", "distance_bin", "epsilon", "walks"],
                    ["abs_error", "sample_variance", "mean_steps"],
                )
                by_bin_bias = summarize_groups(
                    bias_merged,
                    ["mesh", "mesh_variant", "distance_bin", "epsilon", "walks"],
                    ["bias_indicator", "mean_steps_epsilon"],
                )
                bias_lookup = {
                    (r["mesh"], r["mesh_variant"], r["distance_bin"], str(r["epsilon"]), str(r["walks"])): r
                    for r in by_bin_bias
                }
                for row in by_bin_neu:
                    key = (row["mesh"], row["mesh_variant"], row["distance_bin"], str(row["epsilon"]), str(row["walks"]))
                    b = bias_lookup.get(key, {})
                    rmse = as_float(row.get("abs_error_rmse"))
                    sweep_rows.append({
                        "mesh": row["mesh"],
                        "mesh_variant": row["mesh_variant"],
                        "distance_bin": row["distance_bin"],
                        "epsilon": row["epsilon"],
                        "walks": row["walks"],
                        "n": row["n"],
                        "rmse": rmse,
                        "mean_abs_error": row.get("abs_error_mean", ""),
                        "mean_sample_variance": row.get("sample_variance_mean", ""),
                        "mean_steps": row.get("mean_steps_mean", ""),
                        "mean_bias": b.get("bias_indicator_mean", ""),
                        "mean_bias_steps": b.get("mean_steps_epsilon_mean", ""),
                    })

    neumann_summary = summarize_groups(
        neumann_rows,
        ["mesh", "mesh_variant", "distance_bin"],
        ["abs_error", "sample_variance", "mean_steps"],
    )
    bias_summary = summarize_groups(
        bias_rows,
        ["mesh", "mesh_variant", "distance_bin"],
        ["bias_indicator", "normalized_bias", "abs_error_epsilon", "mean_steps_epsilon"],
    )
    write_csv(out_dir / "distance_controlled_neumann.csv", neumann_rows)
    write_csv(out_dir / "distance_controlled_neumann_summary.csv", neumann_summary)
    write_csv(out_dir / "distance_controlled_bias.csv", bias_rows)
    write_csv(out_dir / "distance_controlled_bias_summary.csv", bias_summary)
    write_csv(out_dir / "distance_controlled_query_counts.csv", count_rows)
    write_csv(out_dir / "epsilon_distance_sweep.csv", sweep_rows)

    corr_rows, reg_rows, reg_lines = controlled_correlations(neumann_rows, "part1_neumann", "abs_error")
    rf_rows = try_random_forest(neumann_rows, "part1_neumann", "abs_error")
    write_csv(out_dir / "controlled_geometry_correlations.csv", corr_rows)
    write_csv(out_dir / "geometry_regression_coefficients.csv", reg_rows)
    if rf_rows:
        write_csv(out_dir / "random_forest_feature_importance.csv", rf_rows)
    plot_results(out_dir, neumann_summary, bias_summary, sweep_rows, neumann_rows)
    write_report(out_dir, neumann_summary, bias_summary, sweep_rows, corr_rows, reg_rows, reg_lines, rf_rows, config)
    report_path = ROOT / config["geometry_report"] if not Path(config["geometry_report"]).is_absolute() else Path(config["geometry_report"])
    update_geometry_sensitive_report(report_path, out_dir, neumann_summary, corr_rows, reg_rows)
    print(f"Wrote controlled geometry experiments to {out_dir}")


if __name__ == "__main__":
    main()
