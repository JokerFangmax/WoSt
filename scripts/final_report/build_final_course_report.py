#!/usr/bin/env python3
"""Build the unified final course report from existing experiment outputs."""

from __future__ import annotations

import csv
import math
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports"
ASSET_DIR = REPORT_DIR / "final_assets"
RERUN = ROOT / "experiments" / "rerun_cross_mesh_20260606"
GEOM = ROOT / "experiments" / "geometry_sensitive_analysis_20260606"
CONTROLLED = ROOT / "experiments" / "controlled_geometry_experiments_20260606"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def f(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def finite(values: list[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def mean(values: list[float]) -> float:
    values = finite(values)
    return float(np.mean(values)) if values else float("nan")


def std(values: list[float]) -> float:
    values = finite(values)
    return float(np.std(values, ddof=1)) if len(values) > 1 else float("nan")


def se(values: list[float]) -> float:
    values = finite(values)
    return std(values) / math.sqrt(len(values)) if len(values) > 1 else float("nan")


def ci95(values: list[float]) -> tuple[float, float]:
    m = mean(values)
    s = se(values)
    if not math.isfinite(m) or not math.isfinite(s):
        return float("nan"), float("nan")
    delta = 1.96 * s
    return m - delta, m + delta


def rmse(values: list[float]) -> float:
    values = finite(values)
    return math.sqrt(float(np.mean(np.square(values)))) if values else float("nan")


def fmt(value: Any, digits: int = 4) -> str:
    x = f(value)
    if not math.isfinite(x):
        return "NA"
    if abs(x) >= 100:
        return f"{x:.2f}"
    if abs(x) >= 10:
        return f"{x:.3f}"
    if abs(x) >= 1:
        return f"{x:.3f}"
    return f"{x:.{digits}f}"


def md_table(rows: list[dict[str, Any]], fields: list[str], labels: list[str] | None = None) -> list[str]:
    labels = labels or fields
    out = ["| " + " | ".join(labels) + " |", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return out


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def asset_ref(path: Path) -> str:
    return path.relative_to(REPORT_DIR).as_posix()


def copy_asset(src: Path, name: str) -> Path:
    dst = ASSET_DIR / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def plot_setup():
    import matplotlib.pyplot as plt  # type: ignore

    plt.rcParams.update({
        "figure.dpi": 140,
        "savefig.dpi": 180,
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.25,
    })
    return plt


def zombie_summary(mesh: str, boundary: str) -> list[dict[str, str]]:
    if boundary == "dirichlet":
        return read_csv(RERUN / f"zombie_{mesh}_dirichlet" / "zombie_vs_wost_summary.csv")
    return read_csv(RERUN / f"zombie_{mesh}_neumann" / "zombie_vs_wost_neumann_summary.csv")


def plot_rmse_panel(boundary: str, out_name: str) -> Path:
    plt = plot_setup()
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), constrained_layout=True, sharey=False)
    for ax, mesh in zip(axes, ["bunny", "spot"]):
        rows = zombie_summary(mesh, boundary)
        key = "convergence" if boundary == "dirichlet" else "neumann_convergence"
        rows = [row for row in rows if row["benchmark_name"] == key]
        rows = sorted(rows, key=lambda row: f(row["walks_per_point"]))
        walks = [f(row["walks_per_point"]) for row in rows]
        ax.plot(walks, [f(row["wost_rmse"]) for row in rows], marker="o", label="WoSt")
        ax.plot(walks, [f(row["zombie_rmse"]) for row in rows], marker="s", label="Zombie")
        ax.set_xscale("log", base=2)
        ax.set_xlabel("walks per point")
        ax.set_ylabel("RMSE")
        ax.set_title(mesh.capitalize())
        ax.legend()
    title = "Dirichlet RMSE vs walks" if boundary == "dirichlet" else "Mixed Neumann RMSE vs walks"
    fig.suptitle(title)
    path = ASSET_DIR / out_name
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_epsilon_panel(out_name: str) -> Path:
    plt = plot_setup()
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), constrained_layout=True, sharey=False)
    for ax, mesh in zip(axes, ["bunny", "spot"]):
        rows = [row for row in zombie_summary(mesh, "neumann") if row["benchmark_name"] == "neumann_epsilon"]
        rows = sorted(rows, key=lambda row: f(row["epsilon"]), reverse=True)
        eps = [f(row["epsilon"]) for row in rows]
        labels = [f"{value:.0e}" for value in eps]
        x = np.arange(len(rows))
        width = 0.36
        ax.bar(x - width / 2, [f(row["wost_rmse"]) for row in rows], width, label="WoSt")
        ax.bar(x + width / 2, [f(row["zombie_rmse"]) for row in rows], width, label="Zombie")
        ax.set_xticks(x, labels)
        ax.set_xlabel("epsilon")
        ax.set_ylabel("RMSE")
        ax.set_title(mesh.capitalize())
        ax.legend()
    fig.suptitle("Mixed Neumann epsilon sweep at 256 walks")
    path = ASSET_DIR / out_name
    fig.savefig(path)
    plt.close(fig)
    return path


def controlled_stats() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    neumann = [row for row in read_csv(CONTROLLED / "distance_controlled_neumann.csv") if row.get("is_valid") == "1"]
    bias = [row for row in read_csv(CONTROLLED / "distance_controlled_bias.csv") if row.get("is_valid") == "1"]
    bias_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in bias:
        bias_by_key[(row["mesh"], row["distance_bin"])].append(row)

    rows: list[dict[str, Any]] = []
    keys = sorted({(row["mesh"], row["distance_bin"]) for row in neumann}, key=lambda item: (item[0], int(item[1])))
    for mesh, bin_id in keys:
        nr = [row for row in neumann if row["mesh"] == mesh and row["distance_bin"] == bin_id]
        br = bias_by_key.get((mesh, bin_id), [])
        err = [f(row["abs_error"]) for row in nr]
        steps = [f(row["mean_steps"]) for row in nr]
        var = [f(row["sample_variance"]) for row in nr]
        dist = [f(row["nearest_distance_proxy_norm"]) for row in nr]
        bind = [f(row["bias_indicator"]) for row in br]
        lo, hi = ci95(err)
        blo, bhi = ci95(bind)
        rows.append({
            "mesh": mesh,
            "distance_bin": int(bin_id),
            "n": len(nr),
            "mean_nearest_distance_proxy": mean(dist),
            "mean_abs_error": mean(err),
            "abs_error_std": std(err),
            "abs_error_se": se(err),
            "abs_error_ci95_low": lo,
            "abs_error_ci95_high": hi,
            "rmse": rmse(err),
            "mean_steps": mean(steps),
            "mean_sample_variance": mean(var),
            "mean_boundary_bias_indicator": mean(bind),
            "boundary_bias_std": std(bind),
            "boundary_bias_se": se(bind),
            "boundary_bias_ci95_low": blo,
            "boundary_bias_ci95_high": bhi,
        })

    by = {(row["mesh"], row["distance_bin"]): row for row in rows}
    ratios: list[dict[str, Any]] = []
    for bin_id in sorted({row["distance_bin"] for row in rows}):
        bunny = by.get(("bunny", bin_id))
        spot = by.get(("spot", bin_id))
        if not bunny or not spot:
            ratios.append({"distance_bin": bin_id, "status": "missing mesh/bin pair"})
            continue
        ratios.append({
            "distance_bin": bin_id,
            "spot_over_bunny_error": spot["mean_abs_error"] / bunny["mean_abs_error"],
            "spot_over_bunny_bias_indicator": spot["mean_boundary_bias_indicator"] / bunny["mean_boundary_bias_indicator"],
            "spot_over_bunny_steps": spot["mean_steps"] / bunny["mean_steps"],
            "status": "descriptive matched-bin ratio",
        })
    return rows, ratios


def plot_controlled_metric(stats: list[dict[str, Any]], metric: str, ci_low: str | None, ci_high: str | None, ylabel: str, out_name: str) -> Path:
    plt = plot_setup()
    fig, ax = plt.subplots(figsize=(6.8, 4.1), constrained_layout=True)
    bins = sorted({row["distance_bin"] for row in stats})
    x = np.arange(len(bins))
    width = 0.34
    for offset, mesh in [(-width / 2, "bunny"), (width / 2, "spot")]:
        vals = []
        yerr_low = []
        yerr_high = []
        labels_x = []
        for bin_id in bins:
            row = next((item for item in stats if item["mesh"] == mesh and item["distance_bin"] == bin_id), None)
            if row is None:
                vals.append(np.nan)
                yerr_low.append(0.0)
                yerr_high.append(0.0)
            else:
                value = row[metric]
                vals.append(value)
                if ci_low and ci_high and math.isfinite(row[ci_low]) and math.isfinite(row[ci_high]):
                    yerr_low.append(max(0.0, value - row[ci_low]))
                    yerr_high.append(max(0.0, row[ci_high] - value))
                else:
                    yerr_low.append(0.0)
                    yerr_high.append(0.0)
            labels_x.append(str(bin_id))
        ax.bar(x + offset, vals, width, yerr=[yerr_low, yerr_high], capsize=3, label=mesh.capitalize())
    ax.set_xticks(x, [str(bin_id) for bin_id in bins])
    ax.set_xlabel("normalized nearest-distance bin")
    ax.set_ylabel(ylabel)
    ax.legend()
    path = ASSET_DIR / out_name
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_boundary_bias_summary(out_name: str) -> Path:
    rows = [
        {"mesh": "bunny", **row}
        for row in read_csv(RERUN / "wost_bunny" / "diagnostics" / "boundary_bias_summary.csv")
    ] + [
        {"mesh": "spot", **row}
        for row in read_csv(RERUN / "wost_spot" / "diagnostics" / "boundary_bias_summary.csv")
    ]
    plt = plot_setup()
    fig, ax = plt.subplots(figsize=(5.5, 3.8), constrained_layout=True)
    labels = [row["mesh"].capitalize() for row in rows]
    x = np.arange(len(rows))
    ax.bar(x - 0.18, [f(row["mean_bias"]) for row in rows], 0.36, label="mean indicator")
    ax.bar(x + 0.18, [f(row["max_bias"]) for row in rows], 0.36, label="max indicator")
    ax.set_xticks(x, labels)
    ax.set_ylabel("epsilon-vs-half-epsilon difference")
    ax.set_title("Boundary-bias indicator summary")
    ax.legend()
    path = ASSET_DIR / out_name
    fig.savefig(path)
    plt.close(fig)
    return path


def generate_assets() -> dict[str, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    assets: dict[str, Path] = {}
    assets["dirichlet_panel"] = plot_rmse_panel("dirichlet", "fig1_dirichlet_rmse_vs_walks.png")
    assets["neumann_panel"] = plot_rmse_panel("neumann", "fig2_mixed_neumann_rmse_vs_walks.png")
    assets["epsilon_panel"] = plot_epsilon_panel("fig3_neumann_epsilon_sweep.png")
    assets["boundary_bias_bar"] = plot_boundary_bias_summary("fig4_boundary_bias_indicator_summary.png")

    stats, ratios = controlled_stats()
    write_csv(ASSET_DIR / "controlled_matched_bin_statistics.csv", stats)
    write_csv(ASSET_DIR / "controlled_matched_bin_ratios.csv", ratios)
    assets["matched_error_ci"] = plot_controlled_metric(
        stats, "mean_abs_error", "abs_error_ci95_low", "abs_error_ci95_high",
        "mean absolute error with 95% CI", "fig6_matched_bin_abs_error_ci.png",
    )
    assets["matched_bias_ci"] = plot_controlled_metric(
        stats, "mean_boundary_bias_indicator", "boundary_bias_ci95_low", "boundary_bias_ci95_high",
        "mean boundary-bias indicator with 95% CI", "fig7_matched_bin_boundary_bias_ci.png",
    )
    assets["matched_steps"] = plot_controlled_metric(
        stats, "mean_steps", None, None,
        "mean steps", "fig8_matched_bin_mean_steps.png",
    )

    copy_specs = {
        "correlations": (GEOM / "figures" / "strongest_geometry_correlations.png", "fig5_strongest_geometry_correlations.png"),
        "pointwise_error": (GEOM / "figures" / "neumann_pointcloud_abs_error_scatter.png", "fig5b_pointwise_error_scatter.png"),
        "bunny_heatmap": (CONTROLLED / "epsilon_distance_heatmaps" / "bunny_epsilon_vs_distance_rmse.png", "fig9a_bunny_epsilon_distance_rmse.png"),
        "spot_heatmap": (CONTROLLED / "epsilon_distance_heatmaps" / "spot_epsilon_vs_distance_rmse.png", "fig9b_spot_epsilon_distance_rmse.png"),
        "adaptive_bunny": (RERUN / "wost_bunny" / "diagnostics" / "variance_adaptive_tradeoff.png", "fig10a_bunny_adaptive_tradeoff.png"),
        "adaptive_spot": (RERUN / "wost_spot" / "diagnostics" / "variance_adaptive_tradeoff.png", "fig10b_spot_adaptive_tradeoff.png"),
        "live_trace_spot": (RERUN / "wost_spot" / "diagnostics" / "live_trace_plot.png", "fig11_spot_live_trace.png"),
        "bvh_reference": (ROOT / "results_obsolete" / "bvh_vs_bruteforce.png", "fig12_bvh_vs_bruteforce_supporting.png"),
    }
    for key, (src, name) in copy_specs.items():
        if src.exists():
            assets[key] = copy_asset(src, name)
    return assets


def source_inventory() -> list[dict[str, str]]:
    items = [
        ("experiments/rerun_cross_mesh_20260606/RERUN_SUMMARY.md", "Narrative rerun summary with benchmark tables and figure references.", "Used for final report structure and cross-mesh interpretation."),
        ("experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md", "Geometry-sensitive pointwise analysis report.", "Used for geometry predictor and boundary-proximity claims."),
        ("experiments/controlled_geometry_experiments_20260606/CONTROLLED_GEOMETRY_REPORT.md", "Controlled distance-bin and epsilon-distance report.", "Used for matched-bin and epsilon-distance claims."),
        ("experiments/rerun_cross_mesh_20260606/zombie_bunny_dirichlet/zombie_vs_wost_summary.csv", "Bunny Dirichlet WoSt/Zombie RMSE-vs-walks and epsilon comparison.", "Experiment 1 and Figure 1."),
        ("experiments/rerun_cross_mesh_20260606/zombie_spot_dirichlet/zombie_vs_wost_summary.csv", "Spot Dirichlet WoSt/Zombie RMSE-vs-walks and epsilon comparison.", "Experiment 1 and Figure 1."),
        ("experiments/rerun_cross_mesh_20260606/zombie_bunny_neumann/zombie_vs_wost_neumann_summary.csv", "Bunny Mixed Neumann WoSt/Zombie convergence and epsilon sweep.", "Experiments 2-3 and Figures 2-3."),
        ("experiments/rerun_cross_mesh_20260606/zombie_spot_neumann/zombie_vs_wost_neumann_summary.csv", "Spot Mixed Neumann WoSt/Zombie convergence and epsilon sweep.", "Experiments 2-3, Spot anomaly discussion, and Figures 2-3."),
        ("experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/boundary_bias_summary.csv", "Bunny epsilon-vs-half-epsilon boundary-bias indicator summary.", "Experiment 3 and Figure 4."),
        ("experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/boundary_bias_summary.csv", "Spot epsilon-vs-half-epsilon boundary-bias indicator summary.", "Experiment 3 and Figure 4."),
        ("experiments/geometry_sensitive_analysis_20260606/geometry_correlations.csv", "Pearson correlations between pointwise geometry proxies and error/bias/variance metrics.", "Experiment 4 and claim-evidence table."),
        ("experiments/geometry_sensitive_analysis_20260606/geometry_binned_summaries.csv", "Binned summaries by nearest-distance proxy and local geometry features.", "Experiment 4 and Appendix."),
        ("experiments/geometry_sensitive_analysis_20260606/all_point_geometry_features.csv", "Pointwise enriched features for Neumann, bias, and adaptive datasets.", "Experiment 4 and provenance."),
        ("experiments/controlled_geometry_experiments_20260606/distance_controlled_neumann.csv", "Per-query controlled-bin Neumann outputs.", "Experiment 5 statistics and error-bar plots."),
        ("experiments/controlled_geometry_experiments_20260606/distance_controlled_bias.csv", "Per-query controlled-bin epsilon sensitivity indicator outputs.", "Experiment 5 statistics and error-bar plots."),
        ("experiments/controlled_geometry_experiments_20260606/epsilon_distance_sweep.csv", "Epsilon x distance x walks sweep summary.", "Experiment 3/5 heatmap interpretation."),
        ("experiments/controlled_geometry_experiments_20260606/distance_controlled_query_counts.csv", "Feasible query counts by mesh and distance bin.", "Experiment 5 limitations and missing Spot bin 4."),
        ("experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/variance_adaptive_comparison.csv", "Bunny variance-adaptive sampling comparison.", "Diagnostic/optimization tools section."),
        ("experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/variance_adaptive_comparison.csv", "Spot variance-adaptive sampling comparison.", "Diagnostic/optimization tools section."),
        ("experiments/rerun_cross_mesh_20260606/wost_bunny/diagnostics/live_trace.csv", "Bunny live random-walk trace data.", "Live tracing diagnostic discussion."),
        ("experiments/rerun_cross_mesh_20260606/wost_spot/diagnostics/live_trace.csv", "Spot live random-walk trace data.", "Live tracing diagnostic discussion."),
        ("experiments/rerun_cross_mesh_20260606/command_log.txt", "Exact commands used for the cross-mesh rerun.", "Methods and provenance."),
        ("experiments/controlled_geometry_experiments_20260606/command_log.txt", "Exact commands used for controlled geometry experiments.", "Methods and provenance."),
    ]
    rows = []
    for path, contains, use in items:
        rows.append({"source file path": path, "what it contains": contains, "where used in final report": use})
    return rows


def write_provenance(asset_map: dict[str, Path]) -> None:
    rows = source_inventory()
    rows.extend(
        {"source file path": rel(path), "what it contains": "Generated final-report figure/table asset.", "where used in final report": "Main report or poster section."}
        for path in sorted(ASSET_DIR.glob("*"))
    )
    lines = ["# Final Report Provenance", ""]
    lines += md_table(rows, ["source file path", "what it contains", "where used in final report"])
    lines.append("")
    (REPORT_DIR / "final_report_provenance.md").write_text("\n".join(lines), encoding="utf-8")


def load_final_numbers() -> dict[str, Any]:
    spot_neu = zombie_summary("spot", "neumann")
    spot_high = [row for row in spot_neu if row["benchmark_name"] == "neumann_convergence" and row["walks_per_point"] in {"256", "1024"}]
    controlled_ratios = read_csv(ASSET_DIR / "controlled_matched_bin_ratios.csv")
    controlled_stats_rows = read_csv(ASSET_DIR / "controlled_matched_bin_statistics.csv")
    eps_ratios = read_csv(CONTROLLED / "epsilon_distance_sensitivity_ratios.csv")
    return {
        "spot_high": spot_high,
        "controlled_ratios": controlled_ratios,
        "controlled_stats": controlled_stats_rows,
        "eps_ratios": eps_ratios,
    }


def table_controlled_stats(rows: list[dict[str, str]]) -> list[str]:
    out_rows = []
    for row in rows:
        out_rows.append({
            "mesh": row["mesh"],
            "bin": row["distance_bin"],
            "n": row["n"],
            "mean abs err": fmt(row["mean_abs_error"]),
            "std": fmt(row["abs_error_std"]),
            "SE": fmt(row["abs_error_se"]),
            "95% CI": f"[{fmt(row['abs_error_ci95_low'])}, {fmt(row['abs_error_ci95_high'])}]",
            "RMSE": fmt(row["rmse"]),
            "mean steps": fmt(row["mean_steps"]),
            "mean var": fmt(row["mean_sample_variance"]),
            "mean bias indicator": fmt(row["mean_boundary_bias_indicator"]),
        })
    return md_table(out_rows, ["mesh", "bin", "n", "mean abs err", "std", "SE", "95% CI", "RMSE", "mean steps", "mean var", "mean bias indicator"])


def write_final_report(asset_map: dict[str, Path]) -> None:
    nums = load_final_numbers()
    stats = nums["controlled_stats"]
    ratios = nums["controlled_ratios"]

    ratios_rows = []
    for row in ratios:
        ratios_rows.append({
            "bin": row["distance_bin"],
            "Spot/Bunny error": fmt(row.get("spot_over_bunny_error")),
            "Spot/Bunny bias indicator": fmt(row.get("spot_over_bunny_bias_indicator")),
            "Spot/Bunny steps": fmt(row.get("spot_over_bunny_steps")),
            "status": row.get("status", ""),
        })

    claim_rows = [
        {
            "Claim": "Dirichlet validation",
            "Evidence": "Bunny and Spot Dirichlet RMSE decreases with walks in Figure 1 and the Zombie/WoSt summary CSVs.",
            "Limitation / caution": "This validates the baseline pipeline, not every boundary condition.",
        },
        {
            "Claim": "Mixed Neumann geometry sensitivity",
            "Evidence": "Figure 2 and Neumann tables show less uniform convergence and larger Spot errors.",
            "Limitation / caution": "Bunny and Spot differ in shape, mesh resolution, and query distribution.",
        },
        {
            "Claim": "Boundary proximity is the strongest observed predictor",
            "Evidence": "Geometry correlations and pointwise scatter plots identify normalized nearest-distance proxy as the strongest stable predictor.",
            "Limitation / caution": "The variable is a nearest-distance proxy, not exact signed distance.",
        },
        {
            "Claim": "Spot remains harder after distance matching",
            "Evidence": "Controlled bins 1-3 show Spot/Bunny error ratios of about 3.38x, 3.68x, and 1.37x.",
            "Limitation / caution": "Ratios are descriptive; Spot bin 4 is missing and repeated-seed confidence intervals are not available.",
        },
        {
            "Claim": "Coarse epsilon induces boundary-sensitive error",
            "Evidence": "Epsilon sweep and boundary-bias indicator figures show much larger error/indicator values at coarse epsilon.",
            "Limitation / caution": "The epsilon-vs-half-epsilon value is an indicator, not an exact bias decomposition.",
        },
        {
            "Claim": "Optimization tools are diagnostic, not general fixes",
            "Evidence": "Adaptive, antithetic, lazy refinement, BVH, and live-trace outputs expose variance/runtime/path behavior.",
            "Limitation / caution": "They should not be presented as guaranteed accuracy improvements.",
        },
    ]

    lines: list[str] = [
        "# Final Course Report: Geometry-Sensitive Walk-on-Stars under Mixed Neumann Boundary Conditions",
        "",
        "## Abstract / Executive Summary",
        "",
        "This report studies how a reproduced and extended Walk-on-Stars (WoSt) implementation behaves on Bunny and Spot meshes, with emphasis on mixed Neumann boundary conditions. The Dirichlet experiments serve as a sanity check: WoSt and the Zombie baseline show ordinary Monte Carlo convergence. Mixed Neumann experiments are more sensitive: error, variance, path length, and the epsilon-vs-half-epsilon boundary-bias indicator depend strongly on query placement near the inner boundary. Geometry-sensitive diagnostics identify the normalized nearest-surface-distance proxy as the strongest available pointwise predictor. A distance-controlled experiment reduces the query-distance confounder and shows that Spot remains higher-error than Bunny in matched bins 1-3, but the gap shrinks with distance. Optimization tools are useful for diagnosis and engineering, but they are not presented as general accuracy improvements.",
        "",
        "## 1. Introduction and Research Question",
        "",
        "**Research question:** How does Walk-on-Stars behave under mixed Neumann boundary conditions, and how are its errors affected by boundary proximity, epsilon, and mesh geometry?",
        "",
        "The main scientific issue is that Neumann boundary handling depends on reflection and surface normals rather than simple boundary termination. This makes the solver more sensitive to local geometry and to how close query points are to the boundary. The goal is not to declare one solver globally better, but to identify where and why the mixed Neumann setting becomes difficult.",
        "",
        "## 2. Background",
        "",
        "A boundary value problem asks for a function inside a domain subject to conditions on the boundary. Dirichlet conditions prescribe the function value on the boundary; random-walk solvers can terminate at the boundary and evaluate that value. Neumann conditions prescribe normal derivative information. In a mixed setting, part of the boundary uses Dirichlet values and part uses Neumann reflection or derivative contributions.",
        "",
        "Walk-on-Stars is a random-walk Monte Carlo method for solving PDE-style boundary value problems. Instead of stepping on a regular grid, it samples larger geometry-aware jumps. In a Dirichlet problem, each path is mostly a termination-and-estimation process. In a mixed Neumann problem, paths may interact repeatedly with the inner boundary, and errors can arise from reflection behavior, normal estimation, epsilon termination, and local mesh quality.",
        "",
        "## 3. Methods and Experimental Setup",
        "",
        "- **WoSt implementation:** C++ implementation in this repository, run through `build/Release/wost.exe`.",
        "- **Zombie baseline:** Python-driven Zombie baseline under `C:/THU/homework/zombie`, used for cross-method comparison.",
        "- **Meshes:** Bunny (`obj/Bunny.obj`) and Spot (`spot/spot_triangulated.obj`). Spot is coarser in normalized edge length and has higher normal variation in the geometry-sensitive analysis.",
        "- **Query sampling:** Standard rerun queries are random/grid-based depending on the benchmark. Controlled experiments sample query points by normalized nearest-surface-distance proxy bins.",
        "- **Walk counts:** Main convergence sweeps use 16, 64, 256, and 1024 walks per point.",
        "- **Epsilon:** Main epsilon sweeps use 1e-2, 1e-3, 1e-4, and 1e-5.",
        "- **Metrics:** RMSE, mean steps, sample variance, mean samples, and epsilon-vs-half-epsilon boundary-bias indicator.",
        "- **Nearest-distance proxy:** The geometry analysis uses a normalized nearest-surface-distance proxy based on nearest triangle/centroid-style geometry features. It should not be read as exact signed distance.",
        "",
        "## 4. Experiment 1: Dirichlet Sanity Check",
        "",
        f"![Dirichlet RMSE vs walks]({asset_ref(asset_map['dirichlet_panel'])})",
        "",
        "**Main claim:** the Dirichlet experiments show ordinary Monte Carlo behavior on both meshes, validating the baseline pipeline before interpreting mixed Neumann sensitivity.",
        "",
        "The Dirichlet panels show that increasing walks reduces RMSE for both Bunny and Spot, and WoSt/Zombie agreement is close across the tested walk counts. This is the sanity check: the later Neumann difficulty is not simply a failed experiment pipeline.",
        "",
        "## 5. Experiment 2: Mixed Neumann Sensitivity",
        "",
        f"![Mixed Neumann RMSE vs walks]({asset_ref(asset_map['neumann_panel'])})",
        "",
        "**Main claim:** mixed Neumann behavior is less uniform than Dirichlet behavior and is strongly mesh-sensitive.",
        "",
        "Bunny shows improvement with more walks, but the high-walk Neumann error does not drop as cleanly as the Dirichlet case. Spot is substantially harder: WoSt RMSE remains high even at larger walk counts.",
        "",
        "### Why can Zombie outperform WoSt on Spot at high walk counts?",
        "",
        "In Spot mixed Neumann convergence, Zombie has lower RMSE than WoSt at higher walk counts. At 256 walks, Spot Zombie RMSE is `0.14248` while WoSt RMSE is `0.17442`; at 1024 walks, Zombie RMSE is `0.11072` while WoSt RMSE is `0.16710`. WoSt uses much shorter mean paths than Zombie, but shorter paths do not guarantee lower error. This suggests possible residual systematic error from reflection, epsilon handling, local geometry, or implementation differences. This remains an important limitation and future investigation point.",
        "",
        "## 6. Experiment 3: Epsilon and Boundary-Bias Indicator",
        "",
        f"![Mixed Neumann epsilon sweep]({asset_ref(asset_map['epsilon_panel'])})",
        "",
        f"![Boundary-bias indicator summary]({asset_ref(asset_map['boundary_bias_bar'])})",
        "",
        "**Main claim:** coarse epsilon can dominate mixed Neumann error, and the epsilon-vs-half-epsilon boundary-bias indicator is larger on Spot.",
        "",
        "The epsilon sweep shows much larger RMSE at coarse epsilon in the mixed Neumann setting. The boundary-bias indicator compares epsilon and half-epsilon estimates; it is an epsilon sensitivity indicator, not an exact bias decomposition. It is spatially and mesh dependent, which is consistent with the later controlled distance-bin results.",
        "",
        "## 7. Experiment 4: Geometry-Sensitive Pointwise Diagnostics",
        "",
        f"![Strongest geometry correlations]({asset_ref(asset_map['correlations'])})",
        "",
        f"![Pointwise Neumann error scatter]({asset_ref(asset_map['pointwise_error'])})",
        "",
        "**Main claim:** the normalized nearest-surface-distance proxy is the strongest observed pointwise predictor of high error, high variance, long paths, and boundary-bias indicators.",
        "",
        "The geometry-sensitive analysis shows that points close to the inner boundary are consistently harder. Local normal variation and related mesh features are useful secondary descriptors, but they are not a standalone explanation. This motivates distance-controlled comparisons before attributing the Bunny/Spot gap to mesh geometry alone.",
        "",
        "## 8. Experiment 5: Distance-Controlled Bins",
        "",
        f"![Matched-bin mean absolute error]({asset_ref(asset_map['matched_error_ci'])})",
        "",
        f"![Matched-bin boundary-bias indicator]({asset_ref(asset_map['matched_bias_ci'])})",
        "",
        f"![Matched-bin mean steps]({asset_ref(asset_map['matched_steps'])})",
        "",
        "**Main claim:** Spot remains higher-error than Bunny in matched bins 1-3, but the gap shrinks with distance.",
        "",
        "The controlled experiment samples query points by normalized nearest-surface-distance proxy bins. Spot remains higher-error in matched bins 1-3, with descriptive Spot/Bunny error ratios of about 3.38x, 3.68x, and 1.37x. This supports residual mesh, shape, reflection, or normal effects after reducing the query-distance confounder. However, the shrinking ratio shows that query-distance distribution was a major confounding factor. Spot bin 4 is unavailable, so far-boundary matched conclusions are incomplete.",
        "",
        "### Controlled matched-bin ratios",
        "",
    ]
    lines += md_table(
        [
            {
                "bin": row["distance_bin"],
                "Spot/Bunny error": fmt(row.get("spot_over_bunny_error")),
                "Spot/Bunny bias indicator": fmt(row.get("spot_over_bunny_bias_indicator")),
                "Spot/Bunny steps": fmt(row.get("spot_over_bunny_steps")),
                "status": row.get("status", ""),
            }
            for row in ratios
        ],
        ["bin", "Spot/Bunny error", "Spot/Bunny bias indicator", "Spot/Bunny steps", "status"],
    )
    lines += [
        "",
        "### Recomputed per-query matched-bin statistics",
        "",
    ]
    lines += table_controlled_stats(stats)
    lines += [
        "",
        "## 9. Diagnostic and Optimization Tools",
        "",
        f"![Bunny adaptive sampling tradeoff]({asset_ref(asset_map['adaptive_bunny'])})",
        "",
        f"![Spot adaptive sampling tradeoff]({asset_ref(asset_map['adaptive_spot'])})",
        "",
        f"![Spot live trace]({asset_ref(asset_map['live_trace_spot'])})",
        "",
        "Adaptive sampling, antithetic sampling, lazy refinement, BVH acceleration, and live tracing are best framed as engineering and diagnostic tools. Adaptive sampling exposes where variance concentrates and how sample allocation changes. Antithetic sampling reduces variance in the reported diagnostic rows. Lazy refinement and BVH acceleration improve runtime behavior in the tested setup. Live traces give qualitative insight into path behavior. None of these results should be read as guaranteed accuracy improvements for every mesh or boundary condition.",
        "",
        "## 10. Discussion",
        "",
        "The main lesson is that Monte Carlo PDE solvers can look healthy under Dirichlet validation while becoming much more sensitive under mixed Neumann conditions. Dirichlet paths terminate at boundary values; mixed Neumann paths interact with normals and reflection behavior. That interaction makes boundary proximity, epsilon termination, and local mesh geometry more important.",
        "",
        "The strongest available pointwise signal is the normalized nearest-distance proxy. Mesh features such as local normal variation are plausible contributors, especially for a coarse mesh such as Spot, but Bunny and Spot alone do not isolate causality. The unresolved Spot high-walk anomaly is especially important: Zombie can outperform WoSt on Spot at high walk counts even though WoSt uses shorter paths. That points to residual systematic effects rather than pure Monte Carlo variance.",
        "",
        "## 11. Practical Takeaways",
        "",
        "- Run Dirichlet sanity checks before interpreting Neumann results.",
        "- Treat near-boundary mixed Neumann queries as high-risk.",
        "- Avoid coarse epsilon near the boundary.",
        "- Use adaptive sampling as a diagnostic of variance concentration.",
        "- Use live traces to inspect difficult path behavior.",
        "- Do not assume shorter paths imply better accuracy.",
        "",
        "## 12. Limitations",
        "",
        "- Only Bunny and Spot are tested in the controlled cross-mesh analysis.",
        "- Nearest-distance is a proxy, not exact signed distance.",
        "- Matched-bin valid sample counts are small, and matched-bin ratios are descriptive.",
        "- Spot bin 4 is missing in the controlled distance-bin experiment.",
        "- Fixed seeds and limited repeated-seed statistics restrict uncertainty analysis.",
        "- No same-shape remeshing or synthetic geometry stress tests were run.",
        "- The epsilon-vs-half-epsilon boundary-bias value is an indicator, not a true exact-solution bias decomposition.",
        "",
        "## 13. Claim-Evidence-Limitation Table",
        "",
    ]
    lines += md_table(claim_rows, ["Claim", "Evidence", "Limitation / caution"])
    lines += [
        "",
        "## 14. Conclusion",
        "",
        "The reproduced WoSt pipeline passes the basic Dirichlet sanity check, but mixed Neumann boundary conditions reveal strong geometry sensitivity. Boundary proximity and epsilon handling explain a large part of the error structure. Controlled distance bins show that Spot remains harder than Bunny in matched bins 1-3, while the shrinking gap confirms that the original query-distance distribution was a major confounder. The safest final interpretation is therefore not that one method or mesh property fully explains the behavior, but that mixed Neumann WoSt requires careful boundary-distance, epsilon, and geometry diagnostics.",
        "",
        "## Appendix A. Full Tables and Derived Assets",
        "",
        "- `reports/final_assets/controlled_matched_bin_statistics.csv`",
        "- `reports/final_assets/controlled_matched_bin_ratios.csv`",
        "- `reports/final_report_provenance.md`",
        "- Source reports: `experiments/rerun_cross_mesh_20260606/RERUN_SUMMARY.md`, `experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md`, `experiments/controlled_geometry_experiments_20260606/CONTROLLED_GEOMETRY_REPORT.md`",
        "",
        "## Appendix B. Extra Diagnostic Figures",
        "",
        f"![Bunny epsilon-distance RMSE heatmap]({asset_ref(asset_map['bunny_heatmap'])})",
        "",
        f"![Spot epsilon-distance RMSE heatmap]({asset_ref(asset_map['spot_heatmap'])})",
        "",
    ]
    if "bvh_reference" in asset_map:
        lines += [
            f"![BVH versus brute force supporting benchmark]({asset_ref(asset_map['bvh_reference'])})",
            "",
            "The BVH figure is supporting engineering evidence for acceleration inside the WoSt implementation; it is not used as a solver-accuracy claim.",
            "",
        ]
    lines += [
        "## Appendix C. File Provenance",
        "",
        "See `reports/final_report_provenance.md` for source files, generated assets, and where each is used.",
        "",
    ]
    (REPORT_DIR / "FINAL_COURSE_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def write_poster_section(asset_map: dict[str, Path]) -> None:
    lines = [
        "# Poster Results Section",
        "",
        "## Final Figures to Use",
        "",
        "| Figure | Caption |",
        "|---|---|",
        f"| `{asset_ref(asset_map['dirichlet_panel'])}` | Dirichlet RMSE decreases with walks on Bunny and Spot, validating the baseline Monte Carlo pipeline. |",
        f"| `{asset_ref(asset_map['neumann_panel'])}` | Mixed Neumann RMSE is less uniform than Dirichlet RMSE and exposes mesh-sensitive behavior, especially on Spot. |",
        f"| `{asset_ref(asset_map['matched_error_ci'])}` | Under matched nearest-distance proxy bins, Spot remains higher-error in bins 1-3, but the gap shrinks with distance. |",
        f"| `{asset_ref(asset_map['matched_bias_ci'])}` | Boundary-bias indicators are larger near the boundary and higher on Spot in matched bins. |",
        f"| `{asset_ref(asset_map['spot_heatmap'])}` | The epsilon-distance heatmap shows coarse epsilon is most damaging near the boundary. |",
        "",
        "## Three Main Takeaways",
        "",
        "1. Dirichlet validation behaves normally, so the basic Monte Carlo setup is credible.",
        "2. Mixed Neumann behavior is geometry-sensitive, with boundary proximity and epsilon playing central roles.",
        "3. Distance-controlled bins reduce the query-distribution confounder: Spot remains harder in bins 1-3, but the gap shrinks with distance.",
        "",
        "## 30-Second Explanation",
        "",
        "The base WoSt pipeline behaves normally on Dirichlet validation, but mixed Neumann problems are much more sensitive. The strongest pointwise predictor is normalized nearest-boundary-distance proxy. After matching Bunny and Spot by distance bins, Spot still has higher error in bins 1-3, though the gap shrinks, so query placement explains much of the original gap but not all of it.",
        "",
        "## Two-Minute Explanation",
        "",
        "I first validated the reproduced solver on Dirichlet problems. Both Bunny and Spot show ordinary Monte Carlo convergence and close agreement with Zombie, so the baseline pipeline is credible. The difficult behavior appears in the mixed Neumann setting, where paths interact with boundary normals and reflection rather than simply terminating at Dirichlet values.",
        "",
        "Pointwise geometry diagnostics show that the normalized nearest-surface-distance proxy is the strongest available predictor of high error, high variance, long paths, and boundary-bias indicators. Local normal variation is secondary: it may add descriptive signal, but it does not explain the behavior alone.",
        "",
        "To reduce the query-distance confounder, I sampled controlled distance bins for Bunny and Spot. Spot remains higher-error in matched bins 1-3, but the Spot/Bunny error ratio shrinks from about 3.38x and 3.68x in close/mid bins to about 1.37x in bin 3. Spot bin 4 is unavailable, so far-boundary conclusions are incomplete. Epsilon sweeps show that coarse epsilon can dominate near-boundary Neumann error, and the boundary-bias indicator is strongest near the boundary.",
        "",
        "The final message is cautious: mixed Neumann WoSt needs boundary-distance, epsilon, and geometry diagnostics. Optimization tools like adaptive sampling, antithetic sampling, lazy refinement, BVH acceleration, and live tracing are useful engineering tools, but not guaranteed accuracy fixes.",
        "",
        "## Warnings: What Not To Claim",
        "",
        "- Do not claim WoSt is consistently more accurate than Zombie.",
        "- Do not claim Bunny-vs-Spot establishes geometry causality.",
        "- Use nearest-distance proxy wording; it is not exact signed distance.",
        "- Do not call the epsilon-vs-half-epsilon value exact bias; call it a boundary-bias indicator or epsilon sensitivity indicator.",
        "- Do not present matched-bin ratios as statistically definitive without repeated-seed confidence intervals.",
        "- Do not claim shorter paths imply lower error.",
        "",
    ]
    (REPORT_DIR / "POSTER_RESULTS_SECTION.md").write_text("\n".join(lines), encoding="utf-8")


def quality_checks() -> list[str]:
    outputs = [
        REPORT_DIR / "FINAL_COURSE_REPORT.md",
        REPORT_DIR / "POSTER_RESULTS_SECTION.md",
        REPORT_DIR / "final_report_provenance.md",
    ]
    messages: list[str] = []
    sensitive = ["always", "prove", "caused by", "universal"]
    for path in outputs:
        text = path.read_text(encoding="utf-8").lower()
        hits = {}
        for word in sensitive:
            pattern = re.escape(word) if " " in word else rf"\b{re.escape(word)}\b"
            count = len(re.findall(pattern, text))
            if count:
                hits[word] = count
        messages.append(f"{rel(path)} sensitive-word hits: {hits}")
        if "bias" in text and "indicator" not in text:
            messages.append(f"WARNING: {rel(path)} uses bias without indicator context.")
        if "signed distance" in text and "not exact signed distance" not in text and "not be read as exact signed distance" not in text:
            messages.append(f"WARNING: {rel(path)} may overstate distance.")

        fig_paths = []
        for raw in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            fig_paths.append((path.parent / raw).resolve())
        missing = [str(p) for p in fig_paths if not p.exists()]
        messages.append(f"{rel(path)} figure refs: {len(fig_paths)}, missing: {len(missing)}")
        for item in missing:
            messages.append(f"  missing figure: {item}")
    return messages


def main() -> None:
    assets = generate_assets()
    write_provenance(assets)
    write_final_report(assets)
    write_poster_section(assets)
    checks = quality_checks()
    (REPORT_DIR / "final_report_quality_checks.txt").write_text("\n".join(checks) + "\n", encoding="utf-8")
    print("Generated final report outputs:")
    print(f"- {rel(REPORT_DIR / 'FINAL_COURSE_REPORT.md')}")
    print(f"- {rel(REPORT_DIR / 'POSTER_RESULTS_SECTION.md')}")
    print(f"- {rel(REPORT_DIR / 'final_report_provenance.md')}")
    print(f"- {rel(ASSET_DIR)}")
    print("Quality checks:")
    for line in checks:
        print(line)


if __name__ == "__main__":
    main()
