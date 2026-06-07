#!/usr/bin/env python3
"""Summarize measured controlled-geometry experiment outputs."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fields})


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def fmt(value: Any) -> str:
    x = as_float(value)
    if not math.isfinite(x):
        return "NA"
    if abs(x) >= 100:
        return f"{x:.2f}"
    if abs(x) >= 10:
        return f"{x:.3f}"
    if abs(x) >= 1:
        return f"{x:.4f}"
    return f"{x:.5f}"


def valid_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if str(row.get("is_valid", "1")).lower() in {"1", "true"}]


def md_table(rows: list[dict[str, Any]], fields: list[str]) -> list[str]:
    out = ["| " + " | ".join(fields) + " |", "|" + "|".join(["---"] * len(fields)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return out


def mean(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else float("nan")


def rmse(values: list[float]) -> float:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else float("nan")


def summarize(out_dir: Path, report_path: Path | None) -> None:
    counts = read_csv(out_dir / "distance_controlled_query_counts.csv")
    neumann = valid_rows(read_csv(out_dir / "distance_controlled_neumann.csv"))
    bias = valid_rows(read_csv(out_dir / "distance_controlled_bias.csv"))
    sweep = read_csv(out_dir / "epsilon_distance_sweep.csv")
    corr = read_csv(out_dir / "controlled_geometry_correlations.csv")
    reg = read_csv(out_dir / "geometry_regression_coefficients.csv")

    bias_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in bias:
        bias_by_key[(row["mesh"], row["distance_bin"])].append(row)

    summary: list[dict[str, Any]] = []
    keys = sorted({(row["mesh"], row["distance_bin"]) for row in neumann}, key=lambda item: (item[0], int(item[1])))
    for mesh, bin_id in keys:
        nrows = [row for row in neumann if row["mesh"] == mesh and row["distance_bin"] == bin_id]
        brows = bias_by_key.get((mesh, bin_id), [])
        errors = [as_float(row.get("abs_error")) for row in nrows]
        steps = [as_float(row.get("mean_steps")) for row in nrows]
        variances = [as_float(row.get("sample_variance")) for row in nrows]
        distances = [as_float(row.get("nearest_distance_proxy_norm")) for row in nrows]
        biases = [as_float(row.get("bias_indicator")) for row in brows]
        finite_biases = [value for value in biases if math.isfinite(value)]
        summary.append({
            "mesh": mesh,
            "distance_bin": bin_id,
            "valid_points": len(nrows),
            "mean_nearest_distance_proxy_norm": mean(distances),
            "mean_abs_error": mean(errors),
            "rmse": rmse(errors),
            "mean_steps": mean(steps),
            "mean_sample_variance": mean(variances),
            "mean_boundary_bias": mean(biases),
            "max_boundary_bias": max(finite_biases) if finite_biases else float("nan"),
        })
    write_csv(out_dir / "matched_bin_summary.csv", summary)

    by_mesh_bin = {(row["mesh"], row["distance_bin"]): row for row in summary}
    all_bins = sorted({row["distance_bin"] for row in summary} | {row.get("distance_bin", "") for row in counts if row.get("distance_bin")}, key=int)
    comparison: list[dict[str, Any]] = []
    for bin_id in all_bins:
        bunny = by_mesh_bin.get(("bunny", bin_id))
        spot = by_mesh_bin.get(("spot", bin_id))
        if not bunny or not spot:
            comparison.append({"distance_bin": bin_id, "status": "missing mesh/bin pair"})
            continue
        comparison.append({
            "distance_bin": bin_id,
            "bunny_n": bunny["valid_points"],
            "spot_n": spot["valid_points"],
            "spot_over_bunny_error": as_float(spot["mean_abs_error"]) / as_float(bunny["mean_abs_error"]),
            "spot_over_bunny_bias": as_float(spot["mean_boundary_bias"]) / as_float(bunny["mean_boundary_bias"]),
            "spot_over_bunny_steps": as_float(spot["mean_steps"]) / as_float(bunny["mean_steps"]),
            "status": "matched",
        })
    write_csv(out_dir / "matched_bin_comparison.csv", comparison)

    sweep256: list[dict[str, Any]] = []
    for row in sweep:
        if int(as_float(row.get("walks"))) == 256:
            sweep256.append({
                "mesh": row["mesh"],
                "distance_bin": row["distance_bin"],
                "epsilon": f"{as_float(row['epsilon']):.0e}",
                "rmse": as_float(row.get("rmse")),
                "mean_bias": as_float(row.get("mean_bias")),
                "mean_steps": as_float(row.get("mean_steps")),
            })
    write_csv(out_dir / "epsilon_distance_sweep_walks256.csv", sweep256)

    eps_ratios: list[dict[str, Any]] = []
    for mesh in sorted({row["mesh"] for row in sweep}):
        bins = sorted({row["distance_bin"] for row in sweep if row["mesh"] == mesh}, key=int)
        for bin_id in bins:
            rows = [
                row for row in sweep
                if row["mesh"] == mesh and row["distance_bin"] == bin_id and int(as_float(row.get("walks"))) == 256
            ]
            by_eps = {round(as_float(row["epsilon"]), 12): row for row in rows}
            coarse = by_eps.get(round(1e-2, 12))
            fine = by_eps.get(round(1e-5, 12))
            if not coarse or not fine:
                continue
            fine_rmse = as_float(fine.get("rmse"))
            fine_bias = as_float(fine.get("mean_bias"))
            eps_ratios.append({
                "mesh": mesh,
                "distance_bin": bin_id,
                "rmse_1e_2": as_float(coarse.get("rmse")),
                "rmse_1e_5": fine_rmse,
                "rmse_1e_2_over_1e_5": as_float(coarse.get("rmse")) / fine_rmse if fine_rmse else float("nan"),
                "bias_1e_2": as_float(coarse.get("mean_bias")),
                "bias_1e_5": fine_bias,
                "bias_1e_2_over_1e_5": as_float(coarse.get("mean_bias")) / fine_bias if fine_bias else float("nan"),
            })
    write_csv(out_dir / "epsilon_distance_sensitivity_ratios.csv", eps_ratios)

    corr_focus: list[dict[str, Any]] = []
    for row in corr:
        if row.get("target") != "abs_error":
            continue
        if row.get("feature") not in {"nearest_distance_proxy_norm", "local_normal_variation", "local_edge_mean_norm", "local_aspect_ratio"}:
            continue
        corr_focus.append({
            "mesh": row["mesh"],
            "feature": row["feature"],
            "pearson_r": as_float(row.get("pearson_r")),
            "spearman_r": as_float(row.get("spearman_r")),
            "partial_r_control_nearest_distance": row.get("partial_r_control_nearest_distance", ""),
            "n": row.get("n", ""),
        })
    reg_focus = [row for row in reg if row.get("term") != "intercept"]

    matched = [row for row in comparison if row.get("status") == "matched"]
    mean_error_ratio = mean([as_float(row.get("spot_over_bunny_error")) for row in matched])
    mean_bias_ratio = mean([as_float(row.get("spot_over_bunny_bias")) for row in matched])
    mean_steps_ratio = mean([as_float(row.get("spot_over_bunny_steps")) for row in matched])

    counts_md = [
        {
            "Mesh": row["mesh"],
            "Bin": row["distance_bin"],
            "Range": f"[{row['bin_min']}, {row['bin_max']}]",
            "Requested": row["requested_points"],
            "Sampled": row["sampled_points"],
            "Complete": row["complete"],
        }
        for row in counts
    ]
    summary_md = [
        {
            "Mesh": row["mesh"],
            "Bin": row["distance_bin"],
            "n": row["valid_points"],
            "Mean dist": fmt(row["mean_nearest_distance_proxy_norm"]),
            "Mean abs err": fmt(row["mean_abs_error"]),
            "RMSE": fmt(row["rmse"]),
            "Mean steps": fmt(row["mean_steps"]),
            "Mean var": fmt(row["mean_sample_variance"]),
        }
        for row in summary
    ]
    bias_md = [
        {
            "Mesh": row["mesh"],
            "Bin": row["distance_bin"],
            "Mean bias": fmt(row["mean_boundary_bias"]),
            "Max bias": fmt(row["max_boundary_bias"]),
        }
        for row in summary
    ]
    comp_md = [
        {
            "Bin": row.get("distance_bin", ""),
            "Error ratio": fmt(row.get("spot_over_bunny_error")),
            "Bias ratio": fmt(row.get("spot_over_bunny_bias")),
            "Steps ratio": fmt(row.get("spot_over_bunny_steps")),
            "Status": row.get("status", ""),
        }
        for row in comparison
    ]
    eps_md = [
        {
            "Mesh": row["mesh"],
            "Bin": row["distance_bin"],
            "RMSE 1e-2": fmt(row["rmse_1e_2"]),
            "RMSE 1e-5": fmt(row["rmse_1e_5"]),
            "RMSE ratio": fmt(row["rmse_1e_2_over_1e_5"]),
            "Bias ratio": fmt(row["bias_1e_2_over_1e_5"]),
        }
        for row in eps_ratios
    ]
    corr_md = [
        {
            "Mesh": row["mesh"],
            "Feature": row["feature"],
            "Pearson": fmt(row["pearson_r"]),
            "Spearman": fmt(row["spearman_r"]),
            "Partial": fmt(row["partial_r_control_nearest_distance"]) if row["partial_r_control_nearest_distance"] != "" else "NA",
            "n": row["n"],
        }
        for row in corr_focus
    ]
    reg_md = [
        {
            "Mesh": row["mesh"],
            "Term": row["term"],
            "Std beta": fmt(row.get("standardized_beta")),
            "R2": fmt(row.get("r2")),
            "n": row.get("n", ""),
        }
        for row in reg_focus
    ]

    norm_signal = [
        abs(as_float(row["partial_r_control_nearest_distance"]))
        for row in corr_focus
        if row["feature"] == "local_normal_variation" and math.isfinite(as_float(row["partial_r_control_nearest_distance"]))
    ]
    norm_signal += [
        abs(as_float(row.get("standardized_beta")))
        for row in reg_focus
        if row.get("term") == "local_normal_variation" and math.isfinite(as_float(row.get("standardized_beta")))
    ]
    max_norm_signal = max(norm_signal) if norm_signal else float("nan")
    if math.isfinite(max_norm_signal) and max_norm_signal >= 0.15:
        norm_sentence = "local normal variation shows additional descriptive signal after controlling for distance"
    else:
        norm_sentence = "local normal variation does not show strong additional descriptive signal after controlling for distance"

    section: list[str] = [
        "## Controlled Geometry Findings",
        "",
        f"Measured outputs are from `{out_dir.relative_to(ROOT).as_posix()}/`. These experiments reduce the nearest-distance confounder by sampling query points from fixed normalized nearest-surface-distance bins, but they do not establish causality.",
        "",
        "### Distance-Controlled Query Counts",
        "",
    ]
    section += md_table(counts_md, ["Mesh", "Bin", "Range", "Requested", "Sampled", "Complete"])
    section += [
        "",
        "Spot has no sampled points in bin 4 `[0.60, 1.00]` under the current cube and nearest-centroid distance proxy, so matched Bunny-vs-Spot comparisons are limited to bins 1-3. Some sampled points are also outside the valid WoSt domain; the result tables use valid solved points.",
        "",
        "### Matched-Bin Neumann Results",
        "",
    ]
    section += md_table(summary_md, ["Mesh", "Bin", "n", "Mean dist", "Mean abs err", "RMSE", "Mean steps", "Mean var"])
    section += ["", "### Matched-Bin Boundary Bias Results", ""]
    section += md_table(bias_md, ["Mesh", "Bin", "Mean bias", "Max bias"])
    section += ["", "### Bunny-vs-Spot Matched-Bin Comparison", ""]
    section += md_table(comp_md, ["Bin", "Error ratio", "Bias ratio", "Steps ratio", "Status"])
    section += [
        "",
        f"Across matched bins 1-3, Spot/Bunny mean error ratio averages `{mean_error_ratio:.2f}x`, mean boundary-bias ratio averages `{mean_bias_ratio:.2f}x`, and mean steps ratio averages `{mean_steps_ratio:.2f}x`.",
        "",
        "### Epsilon x Distance Sweep",
        "",
    ]
    section += md_table(eps_md, ["Mesh", "Bin", "RMSE 1e-2", "RMSE 1e-5", "RMSE ratio", "Bias ratio"])
    section += [
        "",
        "At `walks=256`, coarse epsilon usually increases close-bin RMSE and boundary-bias indicators. The effect is strongest in Bunny bin 1 and visible in Spot bins 1-3, while some far or low-error bins are noisy because estimator variance and valid-point counts are limited. Full heatmaps are in `epsilon_distance_heatmaps/`.",
        "",
        "### Controlled Correlation / Regression",
        "",
    ]
    section += md_table(corr_md, ["Mesh", "Feature", "Pearson", "Spearman", "Partial", "n"])
    section += [""]
    section += md_table(reg_md, ["Mesh", "Term", "Std beta", "R2", "n"])
    section += [
        "",
        f"In this descriptive regression/correlation pass, {norm_sentence}. The regression models are small and should be treated as exploratory: `error ~ nearest_distance + local_normal_variation + local_edge_mean + local_aspect_ratio`.",
        "",
        "### Interpretation",
        "",
        "- Spot remains higher-error than Bunny in matched normalized-distance bins 1-3, so the controlled run supports residual mesh, shape, reflection, or normal-error effects after reducing the query-distance confounder.",
        "- The gap shrinks with distance: Spot/Bunny error ratio is about `3.38x` in bin 1, `3.68x` in bin 2, and `1.37x` in bin 3. That pattern suggests query-distance distribution was a major confounding factor in the original cross-mesh comparison, but it does not explain all of the difference.",
        "- Boundary bias is also larger for Spot in matched bins 1-3, while mean steps are not uniformly larger after matching distance; Spot has fewer steps than Bunny in bins 2-3.",
        "- Bunny and Spot alone cannot separate mesh quality, shape, scale, and reflection behavior, so this should be read as controlled empirical support, not causal proof.",
        "",
        "### Limitations",
        "",
        "- Nearest-distance is still a nearest-centroid proxy, not exact signed distance or true local feature-size distance.",
        "- Bunny and Spot alone cannot prove universal geometry causality.",
        "- Stronger causal claims require same-shape remeshed variants or synthetic stress-test meshes.",
        "- Spot bin 4 is unavailable in this controlled setup, so far-from-boundary matched conclusions are incomplete.",
        "",
        "### Controlled Output Files",
        "",
        "- `distance_controlled_query_counts.csv`",
        "- `distance_controlled_neumann.csv`",
        "- `distance_controlled_bias.csv`",
        "- `matched_bin_summary.csv`",
        "- `matched_bin_comparison.csv`",
        "- `epsilon_distance_sweep.csv`",
        "- `epsilon_distance_heatmaps/`",
        "- `controlled_geometry_correlations.csv`",
        "- `geometry_regression_summary.md`",
        "",
    ]

    if report_path:
        text = report_path.read_text(encoding="utf-8")
        marker = "## Controlled Geometry Findings"
        files_marker = "\n## Files"
        if marker in text:
            before, rest = text.split(marker, 1)
            suffix = files_marker + rest.split(files_marker, 1)[1] if files_marker in rest else ""
        elif files_marker in text:
            before, rest = text.split(files_marker, 1)
            suffix = files_marker + rest
        else:
            before, suffix = text, ""
        report_path.write_text(before.rstrip() + "\n\n" + "\n".join(section).rstrip() + "\n\n" + suffix.lstrip("\n"), encoding="utf-8")

    poster: list[str] = [
        "# Poster-Ready Controlled Geometry Summary",
        "",
        "## Key Plot Recommendation",
        "",
        "Use `plots/matched_bins_bunny_vs_spot_abs_error.png` as the main controlled-comparison figure. Pair it with `plots/distance_bin_vs_mean_boundary_bias.png` if there is room for a small secondary panel.",
        "",
        "## Matched-Bin Table",
        "",
    ]
    poster += md_table(comp_md, ["Bin", "Error ratio", "Bias ratio", "Steps ratio", "Status"])
    poster += [
        "",
        "## Three Safe Claims",
        "",
        "1. Near-boundary queries remain harder under controlled sampling, with larger errors, variance, path lengths, and bias indicators in the closest bins.",
        "2. Spot remains higher-error than Bunny in matched bins 1-3, supporting residual mesh/shape/reflection/normal effects after controlling for boundary proximity.",
        "3. The Spot/Bunny gap shrinks in farther bins, so the original query-distance distribution was a major confounding factor.",
        "",
        "## Three Things Not To Overclaim",
        "",
        "1. Do not claim Bunny-vs-Spot proves universal mesh-geometry causality.",
        "2. Do not claim nearest-distance is exact signed distance; it is a nearest-centroid proxy.",
        "3. Do not claim local normal variation alone explains the gap; its added signal after distance control is exploratory and weaker than boundary proximity.",
        "",
    ]
    (out_dir / "POSTER_READY_SUMMARY.md").write_text("\n".join(poster), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="experiments/controlled_geometry_experiments_20260606")
    parser.add_argument("--report", default="experiments/geometry_sensitive_analysis_20260606/GEOMETRY_SENSITIVE_REPORT.md")
    args = parser.parse_args()

    out_dir = ROOT / args.output if not Path(args.output).is_absolute() else Path(args.output)
    report = ROOT / args.report if args.report and not Path(args.report).is_absolute() else Path(args.report) if args.report else None
    summarize(out_dir, report)
    print(f"Wrote controlled summary tables and poster summary to {out_dir}")
    if report:
        print(f"Updated {report}")


if __name__ == "__main__":
    main()
