#!/usr/bin/env python3
"""Geometry-sensitive mesh and query analysis for WoSt experiments."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import mean

import numpy as np


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_obj(path: Path) -> tuple[np.ndarray, np.ndarray]:
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.strip().split()
            if not parts:
                continue
            if parts[0] == "v" and len(parts) >= 4:
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "f" and len(parts) >= 4:
                idx = []
                for token in parts[1:]:
                    raw = token.split("/")[0]
                    value = int(raw)
                    if value < 0:
                        value = len(vertices) + value + 1
                    idx.append(value - 1)
                for k in range(1, len(idx) - 1):
                    faces.append([idx[0], idx[k], idx[k + 1]])
    if not vertices or not faces:
        raise SystemExit(f"Could not parse vertices/faces from {path}")
    return np.asarray(vertices, dtype=float), np.asarray(faces, dtype=np.int64)


def finite_stats(values: np.ndarray, prefix: str) -> dict[str, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {
            f"{prefix}_mean": 0.0,
            f"{prefix}_min": 0.0,
            f"{prefix}_max": 0.0,
            f"{prefix}_std": 0.0,
            f"{prefix}_p95": 0.0,
        }
    return {
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_min": float(np.min(values)),
        f"{prefix}_max": float(np.max(values)),
        f"{prefix}_std": float(np.std(values)),
        f"{prefix}_p95": float(np.percentile(values, 95)),
    }


def mesh_features(vertices: np.ndarray, faces: np.ndarray) -> tuple[dict[str, float], dict[str, np.ndarray]]:
    tri = vertices[faces]
    e0 = tri[:, 1] - tri[:, 0]
    e1 = tri[:, 2] - tri[:, 1]
    e2 = tri[:, 0] - tri[:, 2]
    lengths = np.stack(
        [np.linalg.norm(e0, axis=1), np.linalg.norm(e1, axis=1), np.linalg.norm(e2, axis=1)],
        axis=1,
    )
    cross = np.cross(e0, tri[:, 2] - tri[:, 0])
    double_area = np.linalg.norm(cross, axis=1)
    area = 0.5 * double_area
    normals = np.divide(cross, double_area[:, None], out=np.zeros_like(cross), where=double_area[:, None] > 1e-15)
    perimeter_sq = np.sum(lengths * lengths, axis=1)
    quality = np.divide(4.0 * math.sqrt(3.0) * area, perimeter_sq, out=np.zeros_like(area), where=perimeter_sq > 0)
    min_edge = np.min(lengths, axis=1)
    max_edge = np.max(lengths, axis=1)
    aspect = np.divide(max_edge, min_edge, out=np.zeros_like(max_edge), where=min_edge > 1e-15)
    centroids = np.mean(tri, axis=1)

    edge_to_faces: dict[tuple[int, int], list[int]] = {}
    for face_id, face in enumerate(faces):
        for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
            key = (int(min(a, b)), int(max(a, b)))
            edge_to_faces.setdefault(key, []).append(face_id)

    face_var = np.zeros(len(faces), dtype=float)
    face_counts = np.zeros(len(faces), dtype=float)
    adjacency_values: list[float] = []
    boundary_edges = 0
    nonmanifold_edges = 0
    for adjacent in edge_to_faces.values():
        if len(adjacent) == 1:
            boundary_edges += 1
            continue
        if len(adjacent) > 2:
            nonmanifold_edges += 1
        for i in range(len(adjacent)):
            for j in range(i + 1, len(adjacent)):
                a = adjacent[i]
                b = adjacent[j]
                value = 1.0 - abs(float(np.dot(normals[a], normals[b])))
                adjacency_values.append(value)
                face_var[a] += value
                face_var[b] += value
                face_counts[a] += 1.0
                face_counts[b] += 1.0
    local_normal_variation = np.divide(face_var, face_counts, out=np.zeros_like(face_var), where=face_counts > 0)

    bbox_min = np.min(vertices, axis=0)
    bbox_max = np.max(vertices, axis=0)
    bbox_extent = bbox_max - bbox_min
    bbox_diag = float(np.linalg.norm(bbox_extent))
    total_area = float(np.sum(area))

    summary: dict[str, float] = {
        "num_vertices": float(len(vertices)),
        "num_faces": float(len(faces)),
        "bbox_min_x": float(bbox_min[0]),
        "bbox_min_y": float(bbox_min[1]),
        "bbox_min_z": float(bbox_min[2]),
        "bbox_max_x": float(bbox_max[0]),
        "bbox_max_y": float(bbox_max[1]),
        "bbox_max_z": float(bbox_max[2]),
        "bbox_diagonal": bbox_diag,
        "bbox_extent_x": float(bbox_extent[0]),
        "bbox_extent_y": float(bbox_extent[1]),
        "bbox_extent_z": float(bbox_extent[2]),
        "surface_area": total_area,
        "boundary_edge_count": float(boundary_edges),
        "nonmanifold_edge_count": float(nonmanifold_edges),
        "normal_variation_mean": float(mean(adjacency_values)) if adjacency_values else 0.0,
        "normal_variation_max": float(max(adjacency_values)) if adjacency_values else 0.0,
    }
    summary.update(finite_stats(area, "triangle_area"))
    summary.update(finite_stats(lengths.reshape(-1), "edge_length"))
    summary.update(finite_stats(aspect, "triangle_aspect_ratio"))
    summary.update(finite_stats(quality, "triangle_quality"))
    summary.update(finite_stats(local_normal_variation, "local_normal_variation"))

    arrays = {
        "centroids": centroids,
        "area": area,
        "edge_mean": np.mean(lengths, axis=1),
        "aspect": aspect,
        "quality": quality,
        "normal_variation": local_normal_variation,
    }
    return summary, arrays


def nearest_centroid_features(points: np.ndarray, arrays: dict[str, np.ndarray], bbox_diag: float) -> dict[str, np.ndarray]:
    centroids = arrays["centroids"]
    n = points.shape[0]
    best_dist2 = np.full(n, np.inf, dtype=float)
    best_idx = np.zeros(n, dtype=np.int64)
    centroid_chunk = 8192
    point_chunk = 1024
    for p_start in range(0, n, point_chunk):
        p_end = min(p_start + point_chunk, n)
        p = points[p_start:p_end]
        local_best = np.full(p.shape[0], np.inf, dtype=float)
        local_face = np.zeros(p.shape[0], dtype=np.int64)
        for c_start in range(0, centroids.shape[0], centroid_chunk):
            c = centroids[c_start : c_start + centroid_chunk]
            diff = p[:, None, :] - c[None, :, :]
            dist2 = np.sum(diff * diff, axis=2)
            idx = np.argmin(dist2, axis=1)
            d2 = dist2[np.arange(p.shape[0]), idx]
            mask = d2 < local_best
            local_best[mask] = d2[mask]
            local_face[mask] = c_start + idx[mask]
        best_dist2[p_start:p_end] = local_best
        best_idx[p_start:p_end] = local_face
    d = np.sqrt(best_dist2)
    scale = bbox_diag if bbox_diag > 0 else 1.0
    return {
        "nearest_surface_distance_proxy": d,
        "nearest_surface_distance_proxy_norm": d / scale,
        "local_triangle_area": arrays["area"][best_idx],
        "local_triangle_size": arrays["edge_mean"][best_idx],
        "local_triangle_size_norm": arrays["edge_mean"][best_idx] / scale,
        "local_triangle_aspect_ratio": arrays["aspect"][best_idx],
        "local_triangle_quality": arrays["quality"][best_idx],
        "local_normal_variation": arrays["normal_variation"][best_idx],
        "local_curvature_proxy": arrays["normal_variation"][best_idx],
    }


def numeric_column(rows: list[dict], key: str) -> np.ndarray | None:
    values = []
    for row in rows:
        try:
            values.append(float(row[key]))
        except (KeyError, TypeError, ValueError):
            values.append(np.nan)
    arr = np.asarray(values, dtype=float)
    if np.isfinite(arr).sum() == 0:
        return None
    return arr


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return float("nan")
    xx = x[mask]
    yy = y[mask]
    if float(np.std(xx)) == 0.0 or float(np.std(yy)) == 0.0:
        return float("nan")
    return float(np.corrcoef(xx, yy)[0, 1])


def analyze_query_rows(
    rows: list[dict[str, str]],
    arrays: dict[str, np.ndarray],
    mesh_summary: dict[str, float],
) -> tuple[list[dict], list[dict]]:
    if not rows:
        return [], []
    coords = []
    kept = []
    for row in rows:
        try:
            coords.append([float(row["x"]), float(row["y"]), float(row["z"])])
            kept.append(row)
        except (KeyError, ValueError):
            continue
    if not kept:
        return [], []
    points = np.asarray(coords, dtype=float)
    local = nearest_centroid_features(points, arrays, mesh_summary["bbox_diagonal"])
    enriched: list[dict] = []
    for i, row in enumerate(kept):
        out = dict(row)
        for key, values in local.items():
            out[key] = float(values[i])
        enriched.append(out)

    feature_keys = list(local.keys())
    target_keys = [
        "abs_error",
        "rmse",
        "sample_variance",
        "std_error",
        "samples_used",
        "predicted_samples",
        "bias_indicator",
        "normalized_bias",
        "epsilon_sensitivity",
    ]
    correlations: list[dict] = []
    for feature in feature_keys:
        x = np.asarray([float(row[feature]) for row in enriched], dtype=float)
        for target in target_keys:
            y = numeric_column(enriched, target)
            if y is None:
                continue
            correlations.append({
                "feature": feature,
                "target": target,
                "pearson_r": pearson(x, y),
                "n": int(np.isfinite(x).sum()),
            })
    return enriched, correlations


def plot_correlations(out_dir: Path, enriched: list[dict], correlations: list[dict]) -> None:
    if not enriched:
        return
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig_dir = out_dir / "plots"
    fig_dir.mkdir(parents=True, exist_ok=True)

    pairs = [
        ("nearest_surface_distance_proxy_norm", "abs_error", "distance_to_surface_vs_error.png"),
        ("local_normal_variation", "abs_error", "normal_variation_vs_error.png"),
        ("local_triangle_size_norm", "bias_indicator", "local_feature_size_vs_epsilon_sensitivity.png"),
        ("local_normal_variation", "sample_variance", "normal_variation_vs_pilot_variance.png"),
        ("sample_variance", "samples_used", "pilot_variance_vs_samples_used.png"),
    ]
    for x_key, y_key, filename in pairs:
        x = numeric_column(enriched, x_key)
        y = numeric_column(enriched, y_key)
        if x is None or y is None:
            continue
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() < 3:
            continue
        plt.figure(figsize=(5.8, 4.2))
        plt.scatter(x[mask], y[mask], s=14, alpha=0.65)
        plt.xlabel(x_key.replace("_", " "))
        plt.ylabel(y_key.replace("_", " "))
        plt.title(f"{x_key} vs {y_key}")
        plt.grid(True, alpha=0.25)
        plt.tight_layout()
        plt.savefig(fig_dir / filename, dpi=180)
        plt.close()


def run_analysis(mesh: Path, output: Path, mesh_name: str, point_csv: Path | None = None) -> None:
    vertices, faces = parse_obj(mesh)
    summary, arrays = mesh_features(vertices, faces)
    summary["mesh_name"] = mesh_name
    summary["mesh_path"] = str(mesh)
    write_csv(output / "mesh_geometry_summary.csv", [summary], list(summary.keys()))

    point_rows = read_csv(point_csv) if point_csv else []
    enriched, correlations = analyze_query_rows(point_rows, arrays, summary)
    if enriched:
        fields = list(enriched[0].keys())
        write_csv(output / "query_geometry_features.csv", enriched, fields)
    if correlations:
        write_csv(output / "geometry_correlations.csv", correlations, ["feature", "target", "pearson_r", "n"])
    plot_correlations(output, enriched, correlations)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--mesh-name", default="mesh")
    parser.add_argument("--point-csv")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run_analysis(
        Path(args.mesh),
        Path(args.output),
        args.mesh_name,
        Path(args.point_csv) if args.point_csv else None,
    )


if __name__ == "__main__":
    main()
