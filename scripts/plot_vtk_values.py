#!/usr/bin/env python3
"""Visualize WoSt/Zombie ASCII VTK scalar outputs as PNG and interactive 3D HTML."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class VTKData:
    path: Path
    dataset: str
    points: np.ndarray
    fields: dict[str, np.ndarray]
    dims: tuple[int, int, int] | None = None
    origin: tuple[float, float, float] | None = None
    spacing: tuple[float, float, float] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--vtk", help="Single ASCII VTK file to visualize")
    src.add_argument("--root", help="Experiment root to scan recursively for VTK files")
    parser.add_argument("--scope", choices=["wost", "zombie", "all"], default="wost",
                        help="When --root is used, choose which result folders to include")
    parser.add_argument("--out-dir", default="",
                        help="Output directory. Defaults to <root>/vtk_value_views or results/vtk_value_views")
    parser.add_argument("--field", default="", help="Initial field for HTML and first PNG panel")
    parser.add_argument("--html", action="store_true", help="Write interactive 3D HTML viewers")
    parser.add_argument("--no-png", action="store_true", help="Skip PNG summary panels")
    parser.add_argument("--with-mesh", action="store_true", help="Overlay Bunny/Spot mesh when it can be inferred")
    parser.add_argument("--mesh-obj", default="", help="Mesh OBJ for a single --vtk visualization")
    parser.add_argument("--cube", type=float, default=0.0, help="Outer cube half extent for a single --vtk")
    parser.add_argument("--max-points", type=int, default=20000,
                        help="Maximum points embedded in each HTML viewer")
    parser.add_argument("--max-mesh-faces", type=int, default=18000,
                        help="Maximum mesh wireframe faces embedded in each HTML viewer")
    return parser.parse_args()


def resolve_path(text: str | Path) -> Path:
    path = Path(text)
    return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def vtk_float(token: str) -> float:
    token = token.strip()
    if token.lower() in {"nan", "-nan", "inf", "+inf", "infinity", "+infinity"}:
        return float(token)
    return float(token)


def read_numeric_block(lines: list[str], start: int, count: int) -> tuple[list[float], int]:
    values: list[float] = []
    i = start
    while i < len(lines) and len(values) < count:
        for token in lines[i].split():
            values.append(vtk_float(token))
            if len(values) == count:
                break
        i += 1
    if len(values) != count:
        raise SystemExit(f"Expected {count} VTK scalar values, found {len(values)}")
    return values, i


def parse_vtk(path: Path) -> VTKData:
    if not path.exists():
        raise SystemExit(f"Missing VTK file: {path}")
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    dataset = ""
    dims: tuple[int, int, int] | None = None
    origin = (0.0, 0.0, 0.0)
    spacing = (1.0, 1.0, 1.0)
    points: np.ndarray | None = None
    fields: dict[str, np.ndarray] = {}
    point_data_count: int | None = None

    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if not parts:
            i += 1
            continue
        if parts[:1] == ["DATASET"]:
            dataset = parts[1]
            i += 1
        elif parts[:1] == ["DIMENSIONS"]:
            dims = tuple(int(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["ORIGIN"]:
            origin = tuple(float(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["SPACING"]:
            spacing = tuple(float(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["POINTS"]:
            count = int(parts[1])
            values, i = read_numeric_block(lines, i + 1, count * 3)
            points = np.asarray(values, dtype=float).reshape((count, 3))
        elif parts[:1] == ["POINT_DATA"]:
            point_data_count = int(parts[1])
            i += 1
        elif parts[:1] == ["SCALARS"]:
            if point_data_count is None:
                raise SystemExit(f"SCALARS appeared before POINT_DATA in {path}")
            name = parts[1]
            i += 1
            if i < len(lines) and lines[i].split()[:1] == ["LOOKUP_TABLE"]:
                i += 1
            values, i = read_numeric_block(lines, i, point_data_count)
            fields[name] = np.asarray(values, dtype=float)
        else:
            i += 1

    if dataset == "STRUCTURED_POINTS":
        if dims is None:
            raise SystemExit(f"Structured VTK has no DIMENSIONS: {path}")
        nx, ny, nz = dims
        xs = origin[0] + spacing[0] * np.arange(nx)
        ys = origin[1] + spacing[1] * np.arange(ny)
        zs = origin[2] + spacing[2] * np.arange(nz)
        zz, yy, xx = np.meshgrid(zs, ys, xs, indexing="ij")
        points = np.column_stack([xx.ravel(order="C"), yy.ravel(order="C"), zz.ravel(order="C")])
    if points is None:
        raise SystemExit(f"Could not parse POINTS from {path}")
    if not dataset:
        dataset = "UNKNOWN"
    return VTKData(path=path, dataset=dataset, points=points, fields=fields,
                   dims=dims, origin=origin, spacing=spacing)


def finite_range(values: np.ndarray) -> dict[str, float | None]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"min": None, "max": None, "positive_min": None}
    positive = finite[finite > 0]
    return {
        "min": float(finite.min()),
        "max": float(finite.max()),
        "positive_min": float(positive.min()) if positive.size else None,
    }


def valid_mask(data: VTKData) -> np.ndarray:
    mask = np.ones(data.points.shape[0], dtype=bool)
    if "is_valid" in data.fields:
        is_valid = data.fields["is_valid"]
        mask &= np.isfinite(is_valid) & (is_valid >= 0.5)
    any_finite = np.zeros(data.points.shape[0], dtype=bool)
    for values in data.fields.values():
        any_finite |= np.isfinite(values)
    return mask & any_finite


def preferred_fields(data: VTKData, initial: str = "") -> list[str]:
    names = list(data.fields)
    priority = [
        initial,
        "abs_error",
        "abs_error_epsilon",
        "abs_error_epsilon_half",
        "normalized_bias",
        "bias_indicator",
        "std_error",
        "std_error_epsilon",
        "sample_variance",
        "mean_steps",
        "samples_used",
        "solution",
    ]
    ordered: list[str] = []
    for name in priority:
        if name and name in names and name not in ordered:
            ordered.append(name)
    for name in names:
        if name not in ordered and name != "is_valid":
            ordered.append(name)
    if "is_valid" in names:
        ordered.append("is_valid")
    return ordered


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.colors import LogNorm  # type: ignore

        return plt, LogNorm
    except Exception as exc:
        raise SystemExit("matplotlib is required for PNG output") from exc


def plot_png(data: VTKData, out_path: Path, initial_field: str) -> None:
    plt, LogNorm = require_matplotlib()
    fields = preferred_fields(data, initial_field)[:6]
    if not fields:
        return
    cols = 3
    rows = math.ceil(len(fields) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.2 * cols, 3.8 * rows), squeeze=False)
    mask = valid_mask(data)

    for ax, field in zip(axes.ravel(), fields):
        values = data.fields[field].copy()
        values[~mask] = np.nan
        finite = values[np.isfinite(values)]
        if data.dataset == "STRUCTURED_POINTS" and data.dims is not None:
            nx, ny, nz = data.dims
            arr = values.reshape((nz, ny, nx))
            z_index = nz // 2
            image = arr[z_index, :, :]
            if finite.size and field != "solution" and np.nanmin(image) >= 0 and np.nanmax(image) > 0:
                positive = image[np.isfinite(image) & (image > 0)]
                norm = LogNorm(vmin=float(positive.min()), vmax=float(positive.max())) if positive.size else None
            else:
                norm = None
            im = ax.imshow(image, origin="lower", cmap="viridis", norm=norm)
            ax.set_title(f"{field} (center z slice)")
            ax.set_xlabel("x index")
            ax.set_ylabel("y index")
            fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        else:
            pts = data.points[mask]
            vals = values[mask]
            finite_pts = np.isfinite(vals)
            pts = pts[finite_pts]
            vals = vals[finite_pts]
            if vals.size and field != "solution" and np.nanmin(vals) >= 0 and np.nanmax(vals) > 0:
                positive = vals[vals > 0]
                norm = LogNorm(vmin=float(positive.min()), vmax=float(positive.max())) if positive.size else None
            else:
                norm = None
            sc = ax.scatter(pts[:, 0], pts[:, 1], c=vals, s=15, cmap="viridis", norm=norm, linewidths=0)
            ax.set_aspect("equal", adjustable="box")
            ax.set_title(f"{field} (x-y projection)")
            ax.set_xlabel("x")
            ax.set_ylabel("y")
            fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
        ax.grid(True, alpha=0.2)

    for ax in axes.ravel()[len(fields):]:
        ax.axis("off")
    rel = data.path.relative_to(ROOT) if data.path.is_relative_to(ROOT) else data.path
    fig.suptitle(str(rel), fontsize=11)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)
    print(f"Wrote {out_path}")


def infer_mesh_and_cube(vtk_path: Path) -> tuple[Path | None, float]:
    text = str(vtk_path).lower()
    if "bunny" in text:
        return ROOT / "obj" / "Bunny.obj", 0.22
    if "spot" in text:
        return ROOT / "spot" / "spot_triangulated.obj", 1.1
    return None, 0.0


def read_obj_mesh(path: Path, max_faces: int) -> dict[str, list]:
    if not path.exists():
        return {"vertices": [], "faces": []}
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                parts = line.split()
                if len(parts) >= 4:
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif line.startswith("f "):
                indices = []
                for token in line.split()[1:]:
                    raw = token.split("/")[0]
                    if not raw:
                        continue
                    idx = int(raw)
                    idx = len(vertices) + idx if idx < 0 else idx - 1
                    if 0 <= idx < len(vertices):
                        indices.append(idx)
                for j in range(1, len(indices) - 1):
                    faces.append([indices[0], indices[j], indices[j + 1]])
    if max_faces > 0 and len(faces) > max_faces:
        stride = math.ceil(len(faces) / max_faces)
        faces = faces[::stride]
    return {"vertices": vertices, "faces": faces}


def decimate_indices(mask: np.ndarray, max_points: int) -> np.ndarray:
    indices = np.flatnonzero(mask)
    if max_points > 0 and indices.size > max_points:
        take = np.linspace(0, indices.size - 1, max_points).astype(int)
        indices = indices[take]
    return indices


def html_scene(data: VTKData, initial_field: str, args: argparse.Namespace) -> dict:
    mask = valid_mask(data)
    indices = decimate_indices(mask, args.max_points)
    fields = {name: [None if not np.isfinite(v) else float(v) for v in values[indices]]
              for name, values in data.fields.items()}
    ranges = {name: finite_range(values[indices]) for name, values in data.fields.items()}
    mesh_path: Path | None = None
    cube = args.cube
    if args.mesh_obj:
        mesh_path = resolve_path(args.mesh_obj)
    elif args.with_mesh:
        mesh_path, inferred_cube = infer_mesh_and_cube(data.path)
        cube = cube or inferred_cube
    mesh = read_obj_mesh(mesh_path, args.max_mesh_faces) if mesh_path else {"vertices": [], "faces": []}
    if initial_field not in data.fields:
        choices = preferred_fields(data)
        initial_field = choices[0] if choices else ""
    pts = data.points[indices]
    finite_pts = pts[np.all(np.isfinite(pts), axis=1)]
    if finite_pts.size:
        mins = finite_pts.min(axis=0)
        maxs = finite_pts.max(axis=0)
    else:
        mins = np.array([-1.0, -1.0, -1.0])
        maxs = np.array([1.0, 1.0, 1.0])
    if cube > 0:
        mins = np.minimum(mins, [-cube, -cube, -cube])
        maxs = np.maximum(maxs, [cube, cube, cube])
    center = 0.5 * (mins + maxs)
    span = max(float((maxs - mins).max()), 1e-6)
    rel = data.path.relative_to(ROOT) if data.path.is_relative_to(ROOT) else data.path
    return {
        "title": str(rel),
        "dataset": data.dataset,
        "dims": list(data.dims) if data.dims else None,
        "points": pts.tolist(),
        "fields": fields,
        "ranges": ranges,
        "initialField": initial_field,
        "fieldOrder": preferred_fields(data, initial_field),
        "mesh": {
            "label": str(mesh_path.relative_to(ROOT)) if mesh_path and mesh_path.is_relative_to(ROOT) else str(mesh_path or ""),
            "vertices": mesh["vertices"],
            "faces": mesh["faces"],
        },
        "cube": cube,
        "bounds": {"center": center.tolist(), "span": span, "min": mins.tolist(), "max": maxs.tolist()},
    }


def write_html(data: VTKData, out_path: Path, initial_field: str, args: argparse.Namespace) -> None:
    scene = html_scene(data, initial_field, args)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(HTML_TEMPLATE.replace("__SCENE_JSON__", json.dumps(scene, separators=(",", ":"))),
                        encoding="utf-8")
    print(f"Wrote {out_path}")


def discover_vtks(root: Path, scope: str) -> list[Path]:
    vtks = sorted(root.rglob("*.vtk"))
    if scope == "all":
        return vtks
    needle = "wost_" if scope == "wost" else "zombie_"
    filtered = []
    for path in vtks:
        rel_parts = path.relative_to(root).parts if path.is_relative_to(root) else path.parts
        if any(part.lower().startswith(needle) for part in rel_parts):
            filtered.append(path)
    return filtered


def output_stem(vtk_path: Path, base: Path | None) -> str:
    if base and vtk_path.is_relative_to(base):
        rel = vtk_path.relative_to(base)
    elif vtk_path.is_relative_to(ROOT):
        rel = vtk_path.relative_to(ROOT)
    else:
        rel = vtk_path.name
    return "__".join(Path(rel).with_suffix("").parts)


def visualize_one(vtk_path: Path, out_dir: Path, initial_field: str, args: argparse.Namespace,
                  root_base: Path | None = None) -> None:
    data = parse_vtk(vtk_path)
    stem = output_stem(vtk_path, root_base)
    if not args.no_png:
        plot_png(data, out_dir / f"{stem}.png", initial_field)
    if args.html:
        write_html(data, out_dir / f"{stem}.html", initial_field, args)


def main() -> None:
    args = parse_args()
    if args.root:
        root = resolve_path(args.root)
        out_dir = resolve_path(args.out_dir) if args.out_dir else root / "vtk_value_views"
        vtks = discover_vtks(root, args.scope)
        if not vtks:
            raise SystemExit(f"No VTK files found under {root} for scope={args.scope}")
        for vtk_path in vtks:
            visualize_one(vtk_path, out_dir, args.field, args, root_base=root)
        print(f"Processed {len(vtks)} VTK files.")
    else:
        vtk_path = resolve_path(args.vtk)
        out_dir = resolve_path(args.out_dir) if args.out_dir else ROOT / "results" / "vtk_value_views"
        visualize_one(vtk_path, out_dir, args.field, args)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VTK Scalar Values 3D</title>
  <style>
    :root { color-scheme: light; --panel: rgba(255,255,255,.94); --line: rgba(15,23,42,.16); --text: #111827; --muted: #64748B; }
    * { box-sizing: border-box; }
    body { margin: 0; overflow: hidden; font-family: Segoe UI, system-ui, sans-serif; color: var(--text); background: #F8FAFC; }
    canvas { display: block; width: 100vw; height: 100vh; cursor: grab; touch-action: none; }
    canvas:active { cursor: grabbing; }
    .panel { position: fixed; left: 16px; top: 16px; width: min(420px, calc(100vw - 32px)); padding: 12px 14px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); box-shadow: 0 12px 36px rgba(15,23,42,.12); backdrop-filter: blur(8px); }
    h1 { margin: 0 0 8px; font-size: 15px; line-height: 1.3; font-weight: 700; }
    .meta { display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; color: var(--muted); font-size: 12px; margin-bottom: 10px; }
    .meta span:nth-child(odd) { color: #334155; font-weight: 600; }
    label { display: block; font-size: 12px; font-weight: 650; margin-top: 8px; color: #334155; }
    select, input[type="range"] { width: 100%; }
    select { height: 30px; border: 1px solid var(--line); border-radius: 6px; background: white; color: var(--text); padding: 0 8px; }
    .row { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center; }
    .checks { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 9px; font-size: 12px; color: #334155; }
    .checks label { display: inline-flex; align-items: center; gap: 5px; margin: 0; font-weight: 600; }
    .legend { height: 10px; border-radius: 999px; margin-top: 10px; background: linear-gradient(90deg,#440154,#31688e,#35b779,#fde725); border: 1px solid rgba(15,23,42,.1); }
    .hint { margin-top: 8px; font-size: 12px; color: var(--muted); line-height: 1.35; }
    .pill { font-size: 12px; color: #475569; }
    @media (max-width: 640px) { .panel { left: 10px; top: 10px; width: calc(100vw - 20px); } }
  </style>
</head>
<body>
  <canvas id="view"></canvas>
  <section class="panel">
    <h1 id="title"></h1>
    <div class="meta">
      <span>dataset</span><span id="dataset"></span>
      <span>points</span><span id="points"></span>
      <span>mesh</span><span id="mesh"></span>
      <span>range</span><span id="range"></span>
    </div>
    <label for="field">Scalar field</label>
    <select id="field"></select>
    <label for="threshold">Threshold <span id="thresholdText" class="pill"></span></label>
    <input id="threshold" type="range" min="0" max="100" value="0">
    <label for="pointSize">Point size <span id="pointSizeText" class="pill"></span></label>
    <input id="pointSize" type="range" min="1" max="8" value="3">
    <div class="checks">
      <label><input id="logScale" type="checkbox"> log color</label>
      <label><input id="showMesh" type="checkbox" checked> mesh</label>
      <label><input id="showCube" type="checkbox" checked> cube</label>
    </div>
    <div class="legend"></div>
    <div class="hint">Drag to rotate, wheel to zoom. Threshold hides low normalized values so hotspots and high-error regions become easier to isolate.</div>
  </section>
  <script>
const scene = __SCENE_JSON__;
const canvas = document.getElementById("view");
const ctx = canvas.getContext("2d");
const fieldSelect = document.getElementById("field");
const threshold = document.getElementById("threshold");
const thresholdText = document.getElementById("thresholdText");
const pointSize = document.getElementById("pointSize");
const pointSizeText = document.getElementById("pointSizeText");
const logScale = document.getElementById("logScale");
const showMesh = document.getElementById("showMesh");
const showCube = document.getElementById("showCube");
let yaw = -0.72, pitch = 0.48, zoom = 1.0, dragging = false, lastX = 0, lastY = 0;
const center = scene.bounds.center, span = scene.bounds.span || 1;

document.getElementById("title").textContent = scene.title;
document.getElementById("dataset").textContent = scene.dataset + (scene.dims ? " " + scene.dims.join("x") : "");
document.getElementById("points").textContent = scene.points.length.toLocaleString();
document.getElementById("mesh").textContent = scene.mesh.vertices.length ? scene.mesh.label + " (" + scene.mesh.faces.length.toLocaleString() + " faces)" : "none";

for (const name of scene.fieldOrder) {
  if (!(name in scene.fields)) continue;
  const option = document.createElement("option");
  option.value = name;
  option.textContent = name;
  fieldSelect.appendChild(option);
}
fieldSelect.value = scene.initialField;

function resize() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.floor(innerWidth * dpr));
  canvas.height = Math.max(1, Math.floor(innerHeight * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

function normalize(v, range) {
  if (v === null || Number.isNaN(v)) return null;
  const min = range.min, max = range.max;
  if (min === null || max === null || min === max) return 0.5;
  if (logScale.checked && range.positive_min !== null && max > 0) {
    const vv = Math.max(v, range.positive_min);
    return (Math.log(vv) - Math.log(range.positive_min)) / Math.max(1e-12, Math.log(max) - Math.log(range.positive_min));
  }
  return (v - min) / (max - min);
}

function viridis(t) {
  t = Math.max(0, Math.min(1, t));
  const stops = [[68,1,84],[49,104,142],[53,183,121],[253,231,37]];
  const x = t * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x));
  const f = x - i;
  const a = stops[i], b = stops[i + 1];
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return `rgb(${r},${g},${bl})`;
}

function project(p) {
  let x = (p[0] - center[0]) / span;
  let y = (p[1] - center[1]) / span;
  let z = (p[2] - center[2]) / span;
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  const x1 = cy * x + sy * z;
  const z1 = -sy * x + cy * z;
  const y1 = cp * y - sp * z1;
  const z2 = sp * y + cp * z1;
  const camera = 2.8 / zoom;
  const k = Math.min(innerWidth, innerHeight) * 0.92 / Math.max(0.3, camera - z2);
  return {x: innerWidth / 2 + x1 * k, y: innerHeight / 2 - y1 * k, z: z2};
}

function line3(a, b, color, width = 1) {
  const pa = project(a), pb = project(b);
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.beginPath();
  ctx.moveTo(pa.x, pa.y);
  ctx.lineTo(pb.x, pb.y);
  ctx.stroke();
}

function drawCube() {
  const c = scene.cube;
  if (!c || c <= 0) return;
  const v = [[-c,-c,-c],[c,-c,-c],[c,c,-c],[-c,c,-c],[-c,-c,c],[c,-c,c],[c,c,c],[-c,c,c]];
  const e = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
  for (const [a,b] of e) line3(v[a], v[b], "rgba(15,23,42,.55)", 1.2);
}

function drawMesh() {
  const mesh = scene.mesh;
  if (!mesh.vertices.length || !mesh.faces.length) return;
  ctx.strokeStyle = "rgba(71,85,105,.2)";
  ctx.lineWidth = 0.6;
  ctx.beginPath();
  for (const f of mesh.faces) {
    const a = project(mesh.vertices[f[0]]);
    const b = project(mesh.vertices[f[1]]);
    const c = project(mesh.vertices[f[2]]);
    ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.lineTo(c.x, c.y); ctx.lineTo(a.x, a.y);
  }
  ctx.stroke();
}

function drawPoints() {
  const field = fieldSelect.value;
  const values = scene.fields[field];
  const range = scene.ranges[field];
  const t0 = Number(threshold.value) / 100;
  const r = Number(pointSize.value);
  let shown = 0;
  const projected = [];
  for (let i = 0; i < scene.points.length; i++) {
    const t = normalize(values[i], range);
    if (t === null || t < t0) continue;
    const p = project(scene.points[i]);
    projected.push([p.z, p.x, p.y, t]);
  }
  projected.sort((a, b) => a[0] - b[0]);
  for (const p of projected) {
    ctx.fillStyle = viridis(p[3]);
    ctx.beginPath();
    ctx.arc(p[1], p[2], r, 0, Math.PI * 2);
    ctx.fill();
    shown++;
  }
  const min = range.min, max = range.max;
  document.getElementById("range").textContent = min === null ? "n/a" : `${min.toExponential(3)} .. ${max.toExponential(3)}; showing ${shown.toLocaleString()}`;
  thresholdText.textContent = `${threshold.value}%`;
  pointSizeText.textContent = `${pointSize.value}px`;
}

function draw() {
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  ctx.fillStyle = "#F8FAFC";
  ctx.fillRect(0, 0, innerWidth, innerHeight);
  if (showCube.checked) drawCube();
  if (showMesh.checked) drawMesh();
  drawPoints();
}

canvas.addEventListener("pointerdown", e => { dragging = true; lastX = e.clientX; lastY = e.clientY; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener("pointermove", e => {
  if (!dragging) return;
  yaw += (e.clientX - lastX) * 0.008;
  pitch += (e.clientY - lastY) * 0.008;
  pitch = Math.max(-1.45, Math.min(1.45, pitch));
  lastX = e.clientX; lastY = e.clientY;
  draw();
});
canvas.addEventListener("pointerup", e => { dragging = false; canvas.releasePointerCapture(e.pointerId); });
canvas.addEventListener("wheel", e => { e.preventDefault(); zoom *= Math.exp(-e.deltaY * 0.001); zoom = Math.max(0.25, Math.min(6, zoom)); draw(); }, {passive: false});
for (const el of [fieldSelect, threshold, pointSize, logScale, showMesh, showCube]) el.addEventListener("input", draw);
window.addEventListener("resize", resize);
resize();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
