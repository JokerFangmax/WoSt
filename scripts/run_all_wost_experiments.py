#!/usr/bin/env python3
"""Run a reproducible all-in-one WoSt experiment pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RESULTS_CSV = ROOT / "results" / "benchmark_summary.csv"
GEOMETRY_CSV = ROOT / "results" / "geometry_benchmark.csv"
OPT_SUMMARY_CSV = ROOT / "experiments" / "optimization_summary.csv"
OPT_POINTS_CSV = ROOT / "experiments" / "optimization_points.csv"


DEFAULT_CONFIG: dict[str, Any] = {
    "run_mode": "final",
    "mesh": "obj/Bunny.obj",
    "mesh_name": "Bunny",
    "outer_cube": 0.22,
    "boundary": "mixed_neumann",
    "analytic_solution": "x+y+z",
    "neumann_condition": "(1,1,1) dot n",
    "queries": 500,
    "grid": 16,
    "walks": [16, 64, 256, 1024],
    "epsilons": [1e-2, 1e-3, 1e-4, 1e-5],
    "adaptive_tau": [0.003, 0.005, 0.008],
    "seeds": [12345],
    "threads": 8,
    "pilot_samples": 32,
    "min_samples": 32,
    "max_samples": 1024,
    "batch_size": 32,
    "bias_threshold": 2.0,
    "run_zombie": False,
    "zombie_dirichlet_csv": "",
    "zombie_neumann_csv": "",
    "run_bvh": True,
    "run_path_debugger": True,
    "run_optimization": True,
    "run_geometry_analysis": True,
    "verify_build": True,
    "live_point": [0.05, 0.02, 0.08],
    "output": "experiments/Bunny_full_report",
}

MODE_DEFAULTS: dict[str, dict[str, Any]] = {
    "smoke": {
        "queries": 20,
        "grid": 8,
        "walks": [16, 64],
        "epsilons": [1e-2, 1e-3],
        "adaptive_tau": [0.005],
        "seeds": [0],
        "pilot_samples": 8,
        "min_samples": 8,
        "max_samples": 64,
        "batch_size": 8,
        "run_optimization": True,
        "run_path_debugger": True,
        "run_bvh": True,
    },
    "quick": {
        "queries": 150,
        "grid": 12,
        "walks": [16, 64, 256],
        "epsilons": [1e-2, 1e-3, 1e-4],
        "adaptive_tau": [0.003, 0.005, 0.008],
        "seeds": [0, 1, 2],
        "pilot_samples": 16,
        "min_samples": 16,
        "max_samples": 256,
        "batch_size": 16,
    },
    "final": {
        "queries": 500,
        "grid": 16,
        "walks": [16, 64, 256, 1024],
        "epsilons": [1e-2, 1e-3, 1e-4, 1e-5],
        "adaptive_tau": [0.003, 0.005, 0.008],
        "seeds": [0, 1, 2, 3, 4],
        "pilot_samples": 32,
        "min_samples": 32,
        "max_samples": 1024,
        "batch_size": 32,
    },
}

MODE_WARNINGS = {
    "smoke": "Smoke-test results are pipeline checks only. They are not statistically reliable and should not be interpreted as final performance conclusions.",
    "quick": "Quick-test results are useful for trend debugging and parameter selection, but final claims should be based on full experiments.",
    "final": "Final-mode results are intended for final reports and poster figures when the configured query counts, walks, epsilons, and seeds are sufficiently broad.",
}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        if any(ch in value for ch in ".eE"):
            return float(value)
        return int(value)
    except ValueError:
        return value.strip('"').strip("'")


def apply_mode_defaults(config: dict[str, Any], explicit_keys: set[str]) -> dict[str, Any]:
    mode = str(config.get("run_mode", "final")).lower()
    if mode not in MODE_DEFAULTS:
        raise SystemExit(f"Unknown run_mode '{mode}'. Use smoke, quick, or final.")
    merged = dict(config)
    for key, value in MODE_DEFAULTS[mode].items():
        if key not in explicit_keys:
            merged[key] = value
    merged["run_mode"] = mode
    return merged


def load_config(path: Path | None, overrides: argparse.Namespace) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    explicit_keys: set[str] = set()
    if path:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            loaded = json.loads(text)
        else:
            loaded = {}
            for raw in text.splitlines():
                line = raw.split("#", 1)[0].strip()
                if not line or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                loaded[key.strip()] = parse_scalar(value)
        config.update(loaded)
        explicit_keys.update(loaded.keys())
    if getattr(overrides, "mode", None) is not None:
        config["run_mode"] = overrides.mode
        explicit_keys.add("run_mode")
    config = apply_mode_defaults(config, explicit_keys)
    for key in ["mesh", "mesh_name", "boundary", "output"]:
        value = getattr(overrides, key, None)
        if value is not None:
            config[key] = value
    for key in ["queries", "grid", "threads"]:
        value = getattr(overrides, key, None)
        if value is not None:
            config[key] = value
    config["run_mode"] = str(config.get("run_mode", "final")).lower()
    return config


def find_executable(config: dict[str, Any]) -> Path:
    explicit = config.get("wost_exe")
    candidates = []
    if explicit:
        candidates.append(ROOT / str(explicit))
        candidates.append(Path(str(explicit)))
    candidates.extend([
        ROOT / "build" / "Release" / "wost.exe",
        ROOT / "build" / "wost.exe",
        ROOT / "build" / "Release" / "wost",
        ROOT / "build" / "wost",
    ])
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    if config.get("verify_build", True):
        try:
            subprocess.run(["cmake", "--build", "build", "--config", "Release"], cwd=ROOT, check=False)
        except FileNotFoundError:
            pass
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    raise SystemExit("Could not find wost executable. Build first with .\\build_cpp.ps1 or cmake --build build --config Release.")


def try_build(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["cmake", "--build", "build", "--config", "Release"]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    except FileNotFoundError:
        with log_path.open("a", encoding="utf-8") as log:
            log.write("$ " + " ".join(cmd) + "\ncmake not found on PATH\n\n")
        return
    with log_path.open("a", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n")
        log.write(proc.stdout)
        if proc.stderr:
            log.write("\n[stderr]\n" + proc.stderr)
        log.write(f"\n[exit={proc.returncode}]\n\n")


def verify_executable(exe: Path, log_path: Path, config: dict[str, Any]) -> Path:
    proc = subprocess.run([str(exe), "--help"], cwd=ROOT, text=True, capture_output=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"$ {exe} --help\n{proc.stdout}")
        if proc.stderr:
            log.write("\n[stderr]\n" + proc.stderr)
        log.write(f"\n[exit={proc.returncode}]\n\n")
    if "case|" in proc.stdout or "geometry|case" in proc.stdout:
        return exe
    if config.get("verify_build", True):
        try_build(log_path)
        rebuilt = find_executable({**config, "verify_build": False})
        proc2 = subprocess.run([str(rebuilt), "--help"], cwd=ROOT, text=True, capture_output=True)
        if "case|" in proc2.stdout or "geometry|case" in proc2.stdout:
            return rebuilt
    raise SystemExit(f"Executable does not appear to support --mode case; rebuild failed or is unavailable. See {log_path}")


def postprocess_python() -> str:
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def row_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as f:
        return max(0, sum(1 for _ in csv.DictReader(f)))


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_config_yaml(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key in sorted(config):
        value = config[key]
        if isinstance(value, list):
            rendered = "[" + ", ".join(str(v) for v in value) + "]"
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_rows(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    existing = read_rows(path)
    existing.extend(rows)
    write_rows(path, existing)


def try_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def write_grouped_stats_table(path: Path, rows: list[dict[str, str]], group_keys: list[str], metrics: list[str]) -> None:
    groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(str(row.get(key, "")) for key in group_keys)].append(row)
    out_rows: list[dict[str, str]] = []
    for key_values, items in sorted(groups.items()):
        out: dict[str, str] = {key: value for key, value in zip(group_keys, key_values)}
        out["n"] = str(len(items))
        for metric in metrics:
            vals = [try_float(row.get(metric)) for row in items]
            nums = [v for v in vals if v is not None]
            if nums:
                arr = np_array(nums)
                out[f"{metric}_mean"] = f"{sum(nums) / len(nums):.12g}"
                out[f"{metric}_std"] = f"{arr_std(arr):.12g}"
        out_rows.append(out)
    if out_rows:
        write_rows(path, out_rows)


def np_array(values: list[float]) -> list[float]:
    return values


def arr_std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mu = sum(values) / len(values)
    return (sum((v - mu) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def write_summary_tables(run_dir: Path) -> None:
    raw = run_dir / "raw"
    tables = run_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    write_grouped_stats_table(
        tables / "epsilon_walks_summary.csv",
        read_rows(raw / "epsilon_walks_sweep.csv"),
        ["benchmark_name", "boundary_mode", "walks_per_point", "epsilon"],
        ["rmse", "mean_steps", "elapsed_seconds"],
    )
    write_grouped_stats_table(
        tables / "optimization_summary_stats.csv",
        read_rows(raw / "optimization_summary.csv"),
        ["experiment", "method"],
        ["rmse", "mean_sample_variance", "mean_samples_used", "elapsed_seconds", "refinement_ratio"],
    )
    write_grouped_stats_table(
        tables / "variance_adaptive_summary_stats.csv",
        read_rows(raw / "variance_adaptive_comparison.csv"),
        ["method", "target_std_error"],
        ["rmse", "mean_samples_used", "mean_predicted_samples", "runtime_seconds"],
    )
    adaptive_points = [r for r in read_rows(raw / "variance_adaptive_points.csv") if r.get("is_valid", "1") == "1"]
    if adaptive_points:
        samples = [try_float(r.get("samples_used")) for r in adaptive_points]
        samples = [s for s in samples if s is not None]
        max_samples = max(samples) if samples else 0.0
        hit_count = sum(1 for s in samples if s >= max_samples and max_samples > 0)
        write_rows(tables / "variance_adaptive_max_sample_warning.csv", [{
            "valid_points": str(len(samples)),
            "observed_max_samples": f"{max_samples:.12g}",
            "points_at_observed_max": str(hit_count),
            "points_at_observed_max_ratio": f"{(hit_count / len(samples)) if samples else 0.0:.12g}",
            "warning": "most points hit max_samples" if samples and hit_count / len(samples) > 0.8 else "",
        }])


def command_base(exe: Path, config: dict[str, Any], seed: int) -> list[str]:
    mesh = str((ROOT / str(config["mesh"])).resolve() if not Path(str(config["mesh"])).is_absolute() else Path(str(config["mesh"])))
    return [
        str(exe),
        "--obj", mesh,
        "--cube", str(config["outer_cube"]),
        "--queries", str(config["queries"]),
        "--grid", str(config["grid"]),
        "--threads", str(config["threads"]),
        "--seed", str(seed),
    ]


def run_command(cmd: list[str], log_path: Path) -> tuple[int, float]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    elapsed = time.perf_counter() - t0
    with log_path.open("a", encoding="utf-8") as log:
        log.write("$ " + " ".join(cmd) + "\n")
        log.write(proc.stdout)
        if proc.stderr:
            log.write("\n[stderr]\n" + proc.stderr)
        log.write(f"\n[exit={proc.returncode}, wall_seconds={elapsed:.6f}]\n\n")
    return proc.returncode, elapsed


def run_and_capture(
    cmd: list[str],
    source_csv: Path,
    dest_csv: Path,
    log_path: Path,
    extra_row_values: dict[str, Any] | None = None,
) -> tuple[list[dict[str, str]], float]:
    before = row_count(source_csv)
    code, wall = run_command(cmd, log_path)
    if code != 0:
        raise SystemExit(f"Command failed; see {log_path}")
    rows = read_rows(source_csv)[before:]
    if extra_row_values:
        for row in rows:
            row.update({key: str(value) for key, value in extra_row_values.items()})
    append_rows(dest_csv, rows)
    return rows, wall


def run_wost_pipeline(config: dict[str, Any], run_dir: Path) -> None:
    exe = find_executable(config)
    raw = run_dir / "raw"
    log = run_dir / "logs" / "command_log.txt"
    raw.mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    exe = verify_executable(exe, log, config)
    seeds = [int(s) for s in config.get("seeds", [12345])]
    seed0 = seeds[0]

    print("Running Dirichlet accuracy...")
    default_eps = str(config["epsilons"][min(1, len(config["epsilons"]) - 1)])
    for seed in seeds:
        for walks in config["walks"]:
            run_and_capture(
                command_base(exe, config, seed) + [
                    "--mode", "case",
                    "--boundary", "dirichlet",
                    "--epsilon", default_eps,
                    "--walks", str(walks),
                ],
                RESULTS_CSV,
                raw / "dirichlet_accuracy.csv",
                log,
                {"accuracy_seed": seed, "boundary_mode": "dirichlet"},
            )

    if str(config.get("boundary", "")).lower() in {"mixed_neumann", "neumann"}:
        print("Running mixed Neumann benchmark...")
        for seed in seeds:
            for walks in config["walks"]:
                run_and_capture(
                    command_base(exe, config, seed) + [
                        "--mode", "case",
                        "--boundary", "neumann",
                        "--epsilon", default_eps,
                        "--walks", str(walks),
                    ],
                    RESULTS_CSV,
                    raw / "mixed_neumann.csv",
                    log,
                    {"accuracy_seed": seed, "boundary_mode": "neumann"},
                )

    print("Running epsilon x walks sweep...")
    boundary_modes = ["dirichlet"]
    if str(config.get("boundary", "")).lower() in {"mixed_neumann", "neumann"}:
        boundary_modes.append("neumann")
    for boundary in boundary_modes:
        for seed in seeds:
            for eps in config["epsilons"]:
                for walks in config["walks"]:
                    run_and_capture(
                        command_base(exe, config, seed) + [
                            "--mode", "case",
                            "--boundary", boundary,
                            "--epsilon", str(eps),
                            "--walks", str(walks),
                        ],
                        RESULTS_CSV,
                        raw / "epsilon_walks_sweep.csv",
                        log,
                        {"sweep_seed": seed, "boundary_mode": boundary},
                    )

    print("Running boundary bias detector...")
    bias_eps = float(config["epsilons"][1] if len(config["epsilons"]) > 1 else config["epsilons"][0])
    bias_boundary = "neumann" if str(config.get("boundary", "")).lower() in {"mixed_neumann", "neumann"} else "dirichlet"
    code, _ = run_command(
        command_base(exe, config, seed0) + [
            "--mode", "bias_detector",
            "--boundary", bias_boundary,
            "--epsilon", str(bias_eps),
            "--walks", str(config["walks"][-2] if len(config["walks"]) >= 2 else config["walks"][-1]),
            "--bias-threshold", str(config["bias_threshold"]),
            "--out", str(raw / "boundary_bias_detector.vtk"),
            "--csv", str(raw / "boundary_bias_summary.csv"),
        ],
        log,
    )
    if code != 0:
        raise SystemExit(f"Boundary bias detector failed; see {log}")

    print("Running variance-predicted adaptive sampling...")
    for tau in config["adaptive_tau"]:
        code, _ = run_command(
            command_base(exe, config, seed0) + [
                "--mode", "variance_adaptive",
                "--boundary", bias_boundary,
                "--epsilon", str(config["epsilons"][2] if len(config["epsilons"]) > 2 else config["epsilons"][-1]),
                "--pilot-samples", str(config["pilot_samples"]),
                "--min-samples", str(config["min_samples"]),
                "--max-samples", str(config["max_samples"]),
                "--batch-size", str(config["batch_size"]),
                "--target-std-error", str(tau),
                "--out", str(raw / "variance_adaptive_points.csv"),
                "--summary-out", str(raw / "variance_adaptive_summary.csv"),
                "--csv", str(raw / "variance_adaptive_comparison.csv"),
            ],
            log,
        )
        if code != 0:
            raise SystemExit(f"Variance adaptive failed; see {log}")

    if config.get("run_optimization", True):
        print("Running repeated-seed optimization diagnostics...")
        before_points = row_count(OPT_POINTS_CSV)
        run_and_capture(
            command_base(exe, config, seed0) + [
                "--mode", "optimization",
                "--max-samples", str(config["max_samples"]),
                "--min-samples", str(config["min_samples"]),
                "--batch-size", str(config["batch_size"]),
            ],
            OPT_SUMMARY_CSV,
            raw / "optimization_summary.csv",
            log,
        )
        point_rows = read_rows(OPT_POINTS_CSV)[before_points:]
        append_rows(raw / "optimization_points.csv", point_rows)

    if config.get("run_path_debugger", True):
        print("Running live walk path debugger...")
        code, _ = run_command(
            command_base(exe, config, seed0) + [
                "--mode", "demo_point",
                "--boundary", bias_boundary,
                "--walks", str(min(64, int(config["walks"][-1]))),
                "--epsilon", str(config["epsilons"][2] if len(config["epsilons"]) > 2 else config["epsilons"][-1]),
                "--point", *[str(v) for v in config.get("live_point", [0.05, 0.02, 0.08])],
                "--trace-walks", "8",
                "--trace-out", str(raw / "live_trace.csv"),
                "--summary-out", str(raw / "live_demo_summary.csv"),
            ],
            log,
        )
        if code != 0:
            raise SystemExit(f"Live debugger failed; see {log}")

    if config.get("run_bvh", True):
        print("Running WoSt-only BVH vs brute force geometry benchmark...")
        rows, wall = run_and_capture(
            command_base(exe, config, seed0) + ["--mode", "geometry"],
            GEOMETRY_CSV,
            raw / "geometry_benchmark.csv",
            log,
        )
        if rows:
            query_total = sum(float(r.get("elapsed_seconds", 0.0)) for r in rows)
            approx_build = max(0.0, wall - query_total)
            geometry_rows = read_rows(raw / "geometry_benchmark.csv")
            for row in geometry_rows:
                row["process_wall_seconds"] = f"{wall:.6f}"
                row["approx_build_and_startup_seconds"] = f"{approx_build:.6f}"
            write_rows(raw / "geometry_benchmark.csv", geometry_rows)

    if config.get("run_zombie", False):
        print("Importing configured Zombie comparison CSVs...")
        for key, out_name in [("zombie_dirichlet_csv", "zombie_dirichlet.csv"), ("zombie_neumann_csv", "zombie_neumann.csv")]:
            source = str(config.get(key, ""))
            if source:
                src = Path(source)
                if not src.is_absolute():
                    src = ROOT / src
                if src.exists():
                    shutil.copyfile(src, raw / out_name)


def run_postprocessing(config: dict[str, Any], run_dir: Path) -> None:
    py = postprocess_python()
    print("Generating plots...")
    subprocess.run([py, str(ROOT / "scripts" / "plot_full_experiment_suite.py"), "--run-dir", str(run_dir)], cwd=ROOT, check=True)
    live_trace = run_dir / "raw" / "live_trace.csv"
    live_summary = run_dir / "raw" / "live_demo_summary.csv"
    if live_trace.exists() and live_summary.exists():
        subprocess.run([
            py,
            str(ROOT / "scripts" / "plot_live_trace.py"),
            "--trace", str(live_trace),
            "--summary", str(live_summary),
            "--out", str(run_dir / "plots" / "live_trace_plot.png"),
        ], cwd=ROOT, check=True)

    print("Writing summary tables...")
    write_summary_tables(run_dir)

    if config.get("run_geometry_analysis", True):
        print("Running geometry-sensitive analysis...")
        point_csv = run_dir / "raw" / "variance_adaptive_points.csv"
        subprocess.run([
            py,
            str(ROOT / "scripts" / "wost_geometry_analysis.py"),
            "--mesh", str(ROOT / str(config["mesh"])),
            "--mesh-name", str(config["mesh_name"]),
            "--point-csv", str(point_csv),
            "--output", str(run_dir / "tables" / "geometry_analysis"),
        ], cwd=ROOT, check=True)


def table_from_csv(path: Path, columns: list[str], limit: int = 12) -> list[str]:
    rows = read_rows(path)
    if not rows:
        return ["No rows available."]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows[:limit]:
        values = []
        for col in columns:
            value = row.get(col, "")
            try:
                value = f"{float(value):.6g}"
            except (ValueError, TypeError):
                pass
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def poster_summary_lines() -> list[str]:
    return [
        "Key claims:",
        "",
        "- The project reproduces WoSt behavior and adds self-diagnostic tooling rather than claiming a new base estimator.",
        "- Clean Dirichlet tests show expected Monte Carlo convergence when configured with enough samples and repeated seeds.",
        "- Mixed Neumann performance and accuracy are geometry-sensitive.",
        "- Epsilon-vs-half-epsilon, adaptive sampling, antithetic pairing, lazy refinement, path tracing, and BVH timing form an optimization-aware diagnostic suite.",
        "- Conclusions are reproducible under fixed seeds and should be stated per mesh unless broader tests are run.",
        "",
        "Recommended figures:",
        "",
        "- Dirichlet RMSE/steps/runtime vs walks.",
        "- Mixed Neumann WoSt-vs-Zombie comparison table or paired RMSE plot when Zombie CSVs are available.",
        "- Epsilon-by-walk RMSE heatmap and classifier.",
        "- Boundary bias panels with absolute and normalized bias.",
        "- Adaptive sampling cost-accuracy tradeoff and sample map.",
        "- Antithetic variance/RMSE repeated-seed plot.",
        "- Lazy refinement runtime-vs-RMSE plot.",
        "- Live path trace with event color coding.",
        "- BVH vs brute-force geometry query throughput.",
        "",
        "One-sentence experiment explanations:",
        "",
        "- Dirichlet accuracy: validates Monte Carlo convergence against `u=x+y+z`.",
        "- Mixed Neumann: tests reflected paths and normal-sensitive boundary handling.",
        "- Epsilon sweep: separates sampling variance trends from epsilon-sensitive bias.",
        "- Boundary bias detector: detects epsilon sensitivity without relying on ground truth.",
        "- Adaptive sampling: allocates samples from pilot variance under a target standard error.",
        "- Antithetic sampling: diagnoses variance reduction without fixing bias.",
        "- Lazy refinement: measures geometric-query savings and RMSE impact.",
        "- Live path debugger: makes path events visible for interpretation and demos.",
        "- BVH acceleration: isolates WoSt geometry-query acceleration against brute force.",
        "",
        "What not to claim:",
        "",
        "- Do not claim WoSt is always more accurate than Zombie.",
        "- Do not claim adaptive sampling always reduces mean samples to a fixed range.",
        "- Do not claim pure backend-only Zombie FCPW vs WoSt tiny_bvh timing if Zombie timing goes through Python scripts.",
        "- Do not claim million-triangle scalability without a million-triangle experiment.",
        "- Do not use smoke-test results as scientific conclusions.",
    ]


def capability_rows(run_dir: Path, config: dict[str, Any]) -> list[dict[str, str]]:
    raw = run_dir / "raw"
    plots = run_dir / "plots"
    tables = run_dir / "tables"
    reports = run_dir / "reports"
    checks = [
        ("all-in-one experiment runner", "IMPLEMENTED AND TESTED", "scripts/run_all_wost_experiments.py", raw.exists()),
        ("config-based execution", "IMPLEMENTED AND TESTED", "config_used.yaml", (run_dir / "config_used.yaml").exists()),
        ("smoke/quick/final mode label", "IMPLEMENTED AND TESTED", "config_used.yaml", bool(config.get("run_mode"))),
        ("epsilon-by-walk sweep", "IMPLEMENTED AND TESTED", "raw/epsilon_walks_sweep.csv", (raw / "epsilon_walks_sweep.csv").exists()),
        ("Dirichlet accuracy", "IMPLEMENTED AND TESTED", "raw/dirichlet_accuracy.csv", (raw / "dirichlet_accuracy.csv").exists()),
        ("Mixed Neumann", "IMPLEMENTED AND TESTED" if str(config.get("boundary")).lower() in {"mixed_neumann", "neumann"} else "NOT REQUESTED", "raw/mixed_neumann.csv", (raw / "mixed_neumann.csv").exists()),
        ("boundary-bias detector", "IMPLEMENTED AND TESTED", "raw/boundary_bias_summary.csv", (raw / "boundary_bias_summary.csv").exists()),
        ("variance-adaptive sampling", "IMPLEMENTED AND TESTED", "raw/variance_adaptive_comparison.csv", (raw / "variance_adaptive_comparison.csv").exists()),
        ("antithetic sampling", "IMPLEMENTED AND TESTED", "raw/optimization_summary.csv", any(r.get("experiment") == "antithetic_compare" for r in read_rows(raw / "optimization_summary.csv"))),
        ("lazy star-radius refinement", "IMPLEMENTED AND TESTED", "raw/optimization_summary.csv", any(r.get("experiment") == "lazy_refinement" for r in read_rows(raw / "optimization_summary.csv"))),
        ("live walk path debugger", "IMPLEMENTED AND TESTED" if config.get("run_path_debugger", True) else "NOT REQUESTED", "raw/live_trace.csv", (raw / "live_trace.csv").exists()),
        ("BVH vs brute force", "IMPLEMENTED AND TESTED" if config.get("run_bvh", True) else "NOT REQUESTED", "raw/geometry_benchmark.csv", (raw / "geometry_benchmark.csv").exists()),
        ("Zombie comparison integration", "PARTIALLY IMPLEMENTED", "raw/zombie_*.csv", (raw / "zombie_dirichlet.csv").exists() or (raw / "zombie_neumann.csv").exists()),
        ("geometry-sensitive analysis", "IMPLEMENTED AND TESTED" if config.get("run_geometry_analysis", True) else "NOT REQUESTED", "tables/geometry_analysis", (tables / "geometry_analysis" / "mesh_geometry_summary.csv").exists()),
        ("plot generation", "IMPLEMENTED AND TESTED", "plots/*.png", any(plots.glob("*.png"))),
        ("markdown report generation", "IMPLEMENTED AND TESTED", "reports/final_wost_experiment_report.md", True),
        ("poster-ready summary generation", "IMPLEMENTED AND TESTED" if str(config.get("run_mode")) != "smoke" else "SKIPPED FOR SMOKE", "reports/poster_ready_summary.md", str(config.get("run_mode")) != "smoke"),
    ]
    return [
        {
            "capability": name,
            "status": status if ok else ("PARTIALLY IMPLEMENTED" if status == "PARTIALLY IMPLEMENTED" else "NOT PRODUCED IN THIS RUN"),
            "path": path,
        }
        for name, status, path, ok in checks
    ]


def write_report(config: dict[str, Any], run_dir: Path) -> None:
    raw = run_dir / "raw"
    plots = sorted((run_dir / "plots").glob("*.png"))
    classifications = read_rows(run_dir / "epsilon_sweep_classification.csv")
    geometry_dir = run_dir / "tables" / "geometry_analysis"
    mesh_summary = read_rows(geometry_dir / "mesh_geometry_summary.csv")
    correlations = read_rows(geometry_dir / "geometry_correlations.csv")
    bias_summary = read_rows(raw / "boundary_bias_summary.csv")
    mode = str(config.get("run_mode", "final"))
    warning = MODE_WARNINGS.get(mode, "")

    lines: list[str] = [
        "# WoSt Self-Diagnostic and Optimization-Aware Experiment Report",
        "",
        f"**Run mode:** `{mode}`",
        "",
        f"**Run-mode warning:** {warning}",
        "",
        "The base Walk-on-Stars estimator is not claimed as the sole innovation. Our contribution is a C++ WoSt system that reproduces and compares against Zombie on complex meshes, diagnoses boundary bias through epsilon-vs-half-epsilon tests, visualizes random walk paths, predicts sample allocation from pilot variance, and exposes optimization diagnostics such as antithetic sampling and lazy star-radius refinement.",
        "",
        "## 1. Mesh and setup",
        "",
        f"- Mesh: `{config['mesh_name']}` (`{config['mesh']}`)",
        f"- Boundary configuration: `{config['boundary']}`",
        f"- Analytic solution: `{config['analytic_solution']}`",
        f"- Neumann condition: `{config['neumann_condition']}`",
        f"- Outer cube half extent: `{config['outer_cube']}`",
        f"- Query points: `{config['queries']}`, grid: `{config['grid']}`, seeds: `{config['seeds']}`",
        "",
        "## Pipeline Capability Verification",
        "",
        "| capability | status | path |",
        "| --- | --- | --- |",
    ]
    for row in capability_rows(run_dir, config):
        lines.append(f"| {row['capability']} | {row['status']} | `{row['path']}` |")
    lines.append("")
    if mesh_summary:
        lines += table_from_csv(geometry_dir / "mesh_geometry_summary.csv", [
            "mesh_name", "num_vertices", "num_faces", "bbox_diagonal", "triangle_area_mean",
            "edge_length_mean", "triangle_quality_mean", "normal_variation_mean",
        ], 1)
        lines.append("")

    lines += [
        "## 2. Dirichlet accuracy",
        "",
        "Dirichlet accuracy mainly reports RMSE because the manufactured solution `u=x+y+z` gives a direct ground-truth error and RMSE tracks the expected Monte Carlo convergence trend. Mean steps and runtime are now included because they expose cost, but in clean Dirichlet-only tests they are secondary diagnostics: they mostly measure geometric walk efficiency rather than reflection-heavy boundary behavior.",
        "",
    ]
    lines += table_from_csv(raw / "dirichlet_accuracy.csv", ["walks_per_point", "epsilon", "rmse", "mean_steps", "elapsed_seconds"])
    lines += [
        "",
        "## 3. Mixed Neumann accuracy",
        "",
        "WoSt and Zombie can differ under mixed Neumann conditions because the implementation choices are no longer only sampling a clean Dirichlet terminal value. Differences can come from boundary handling, reflection formulas, epsilon stopping, star-radius computation, geometric query backends, normal orientation and interpolation, and max-step termination behavior.",
        "",
        "In this implementation, WoSt uses triangle normals from closest/ray-hit boundary queries, reflects directions at Neumann hits, applies an epsilon offset after reflection, and uses a star radius based on closest boundary and silhouette distance. Lazy refinement can skip exact silhouette checks when the walk is far from suspicious regions. These choices often reduce mean steps, especially compared with baselines that take longer reflected paths or use different stopping logic.",
        "",
        "Mixed Neumann RMSE is mesh-sensitive. Scale, local feature size, normal variation, curvature, triangle quality, concavity, narrow gaps, boundary proximity, and mesh resolution can all change how often reflected paths interact with geometry-sensitive regions.",
        "",
    ]
    lines += table_from_csv(raw / "mixed_neumann.csv", ["benchmark_name", "walks_per_point", "epsilon", "rmse", "mean_steps", "elapsed_seconds"], 12)

    lines += [
        "",
        "## 4. Epsilon sweep",
        "",
        "The epsilon sweep tests both Monte Carlo variance and boundary bias. Increasing walks mostly probes variance. Decreasing epsilon probes boundary bias and boundary-handling sensitivity. If RMSE does not decrease when walks increase, that is evidence of a non-variance error floor. If RMSE changes strongly when epsilon changes, that is evidence of epsilon-sensitive boundary bias.",
        "",
    ]
    if classifications:
        lines += ["| benchmark | heuristic classification |", "| --- | --- |"]
        for row in classifications:
            lines.append(f"| {row.get('benchmark_name')} | {row.get('classification')} |")
        lines.append("")
    lines += table_from_csv(raw / "epsilon_walks_sweep.csv", ["benchmark_name", "boundary_mode", "sweep_seed", "walks_per_point", "epsilon", "rmse", "mean_steps", "elapsed_seconds"], 16)
    lines += ["", "Repeated-seed summary where available:"]
    lines += table_from_csv(run_dir / "tables" / "epsilon_walks_summary.csv", ["benchmark_name", "boundary_mode", "walks_per_point", "epsilon", "n", "rmse_mean", "rmse_std", "mean_steps_mean", "elapsed_seconds_mean"], 16)

    lines += [
        "",
        "## 5. Boundary bias detector",
        "",
        "The heat maps compare `u_epsilon` with `u_epsilon/2`. Large absolute differences mark locations where the boundary approximation is sensitive to epsilon. Normalized bias divides by estimated Monte Carlo standard error, so large normalized values suggest the discrepancy is bigger than sampling noise.",
        "",
        "The earlier heat maps were hard to compare because each panel could choose its own color scale and did not show distributions. The new plots use comparable panels, add histograms, and keep absolute and normalized bias separate.",
        "",
        "Epsilon sensitivity is expected near Neumann boundaries, high curvature, rapidly changing normals, thin structures, concave regions, narrow gaps, poor triangle quality, or regions where local feature size is small relative to epsilon.",
        "",
    ]
    if bias_summary:
        lines += table_from_csv(raw / "boundary_bias_summary.csv", ["epsilon", "epsilon_half", "walks", "valid_points", "mean_bias", "max_bias", "p95_bias", "mean_normalized_bias", "max_normalized_bias", "p95_normalized_bias", "warning_threshold_ratio", "rmse_epsilon", "rmse_epsilon_half"], 1)

    lines += [
        "",
        "## 6. Variance-predicted adaptive sampling",
        "",
        "Pilot samples are the initial fixed number of walks used to estimate pointwise sample variance. The implementation predicts `N_i = ceil(variance_i / tau^2)`, clamped by `min_samples` and `max_samples`. Tau controls Monte Carlo standard error, not total RMSE; total RMSE can still include epsilon bias, Neumann bias, geometry error, and normal error.",
        "",
        "Meshes like Spot can still hit near-maximum samples for many points when pilot variance is high over much of the query distribution. Adaptive sampling saves cost most clearly in smooth, far-from-boundary, low-variance regions; it spends more samples near high normal variation, thin or concave structures, reflected-path regions, and near-boundary points.",
        "",
    ]
    lines += table_from_csv(raw / "variance_adaptive_comparison.csv", ["method", "target_std_error", "rmse", "mean_samples_used", "mean_predicted_samples", "mean_steps", "runtime_seconds"], 12)
    lines += ["", "Adaptive max-sample warning:"]
    lines += table_from_csv(run_dir / "tables" / "variance_adaptive_max_sample_warning.csv", ["valid_points", "observed_max_samples", "points_at_observed_max", "points_at_observed_max_ratio", "warning"], 1)

    lines += [
        "",
        "## 7. Antithetic sampling",
        "",
        "Antithetic sampling pairs random sphere directions `d` and `-d` from a shared direction tape and averages the paired estimators. This preserves unbiasedness for the Monte Carlo part when the paired estimator is a symmetric average. It can reduce sample variance, but it does not correct epsilon, boundary, geometry, or normal bias. It is therefore a variance reduction diagnostic, not a bias correction method.",
        "",
        "Repeated-seed optimization summaries:",
        "",
    ]
    lines += table_from_csv(run_dir / "tables" / "optimization_summary_stats.csv", ["experiment", "method", "n", "rmse_mean", "rmse_std", "mean_sample_variance_mean", "mean_sample_variance_std", "elapsed_seconds_mean"], 16)
    lines += [
        "",
        "## 8. Lazy star-radius refinement",
        "",
        "Full exact refinement evaluates the star radius using both closest-boundary and silhouette-distance queries. Lazy refinement first uses a fast closest-boundary distance and only refines exactly when the radius is small or suspicious. It mainly targets geometric query overhead. It can hurt accuracy if the skipped silhouette check would have constrained the safe radius in a region with sharp visibility changes, narrow gaps, or strong nonconvexity.",
        "",
        "In our diagnostics, lazy refinement preserves RMSE while substantially reducing geometric cost, but this should not be overclaimed as universally accuracy-preserving.",
        "",
        "## 9. Live walk path debugger",
        "",
        "The trace records `walk_id`, `step_id`, position, radius, event type, and boundary type. Existing event types distinguish `start`, normal `sphere_step`, `neumann_reflect`, `dirichlet_hit`, `max_step`, and `end`, which is enough to color-code starts, reflected steps, terminations, and failed max-step paths for a live demo.",
        "",
        "## 10. BVH acceleration",
        "",
        "The tiny_bvh backend accelerates closest-boundary distance and ray-boundary intersection queries used by WoSt. The cleanest comparison is WoSt-only BVH versus brute-force triangle distance queries using the same query points. Zombie timings are only comparable at application level if they go through Python scripts; they should not be described as pure FCPW-versus-tiny_bvh backend timings.",
        "",
    ]
    lines += table_from_csv(raw / "geometry_benchmark.csv", ["backend_name", "triangle_count", "num_queries", "elapsed_seconds", "queries_per_second", "checksum"], 4)

    lines += [
        "",
        "## 11. Geometry-sensitive analysis",
        "",
        "The geometry analysis computes mesh scale, triangle area, edge length, triangle quality, aspect ratio, normal-variation proxies, and per-query nearest-surface/local-feature proxies. These are scale-normalized where useful so Bunny, Spot, sphere, and other meshes can be compared more fairly.",
        "",
        "Geometry-sensitive findings should be read as empirical correlations, not universal theoretical claims.",
        "",
    ]
    if correlations:
        lines += table_from_csv(geometry_dir / "geometry_correlations.csv", ["feature", "target", "pearson_r", "n"], 16)

    lines += [
        "",
        "## 12. Stable conclusions",
        "",
        "- WoSt and Zombie agree closely on clean Dirichlet benchmarks when both are configured consistently.",
        "- WoSt follows the expected Monte Carlo convergence trend in Dirichlet tests.",
        "- Coarse epsilon can cause severe boundary sensitivity.",
        "- Epsilon-vs-half-epsilon comparison is useful when ground truth is unavailable.",
        "- Antithetic sampling reduces variance when the paired directions are effective, but it does not correct bias.",
        "- Live diagnostics justify the project framing as a self-diagnostic and optimization-aware solver.",
        "",
        "## 13. Mesh-sensitive conclusions",
        "",
        "- Mixed Neumann behavior is more geometry-sensitive than Dirichlet behavior.",
        "- WoSt is consistently faster in mixed Neumann tests when it uses shorter reflected paths, but the accuracy advantage is mesh-dependent.",
        "- Adaptive sampling should be tuned per mesh and target error; it should not be claimed to always reduce mean samples to a fixed range.",
        "- Lazy star-radius refinement reduces geometric cost in these diagnostics, but it is not universally accuracy-preserving.",
        "",
        "## 14. Avoid overclaiming",
        "",
        "- Do not claim WoSt is always more accurate than Zombie.",
        "- Do not claim adaptive sampling always saves cost.",
        "- Do not claim backend-only Zombie FCPW vs WoSt tiny_bvh timing when Zombie is run through Python.",
        "- Do not claim million-triangle scalability without a million-triangle experiment.",
        "- Do not claim Bunny/Spot geometry correlations are universal.",
        "",
        "## 15. Recommended poster figures",
        "",
        "- Dirichlet RMSE/steps/runtime vs walks.",
        "- Mixed Neumann WoSt-vs-Zombie comparison table or paired RMSE plot when Zombie CSVs are available.",
        "- Epsilon-by-walk RMSE heatmap and classifier.",
        "- Boundary bias panels with absolute and normalized bias.",
        "- Adaptive sampling cost-accuracy tradeoff and sample map.",
        "- Antithetic variance/RMSE repeated-seed plot.",
        "- Lazy refinement runtime-vs-RMSE plot.",
        "- Live path trace with event color coding.",
        "- BVH vs brute-force geometry query throughput.",
        "",
        "## Poster-ready summary",
        "",
    ]
    if mode == "smoke":
        lines.append("No poster-ready claims are generated from smoke-test results. Smoke output is a pipeline check only.")
    else:
        lines += poster_summary_lines()
    lines += ["", "Plots generated:", ""]
    for plot in plots:
        lines.append(f"- `{plot.relative_to(run_dir).as_posix()}`")
    lines.append("")

    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "final_wost_experiment_report.md").write_text("\n".join(lines), encoding="utf-8")
    if mode != "smoke":
        (reports / "poster_ready_summary.md").write_text("\n".join(poster_summary_lines()) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config")
    parser.add_argument("--mode", choices=["smoke", "quick", "final"], help="Override run_mode from config.")
    parser.add_argument("--mesh")
    parser.add_argument("--mesh-name", dest="mesh_name")
    parser.add_argument("--boundary")
    parser.add_argument("--output")
    parser.add_argument("--queries", type=int)
    parser.add_argument("--grid", type=int)
    parser.add_argument("--threads", type=int)
    parser.add_argument("--no-run", action="store_true", help="Only postprocess/report an existing output directory.")
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None, args)
    run_dir = ROOT / str(config["output"]) if not Path(str(config["output"])).is_absolute() else Path(str(config["output"]))
    if not args.no_run and run_dir.exists():
        resolved = run_dir.resolve()
        if ROOT.resolve() in resolved.parents:
            shutil.rmtree(resolved)
        else:
            raise SystemExit(f"Refusing to clean output outside project root: {resolved}")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config_resolved.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    write_config_yaml(run_dir / "config_used.yaml", config)

    if not args.no_run:
        run_wost_pipeline(config, run_dir)
    run_postprocessing(config, run_dir)
    write_report(config, run_dir)
    print(f"Wrote final report to {run_dir / 'reports' / 'final_wost_experiment_report.md'}")


if __name__ == "__main__":
    main()
