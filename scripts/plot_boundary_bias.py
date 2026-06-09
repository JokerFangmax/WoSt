#!/usr/bin/env python3
"""Plot a center slice from boundary_bias_detector VTK output."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vtk", default="results/boundary_bias_detector.vtk")
    parser.add_argument("--summary", default="results/boundary_bias_summary.csv")
    parser.add_argument("--out", default="results/boundary_bias_detector.png")
    parser.add_argument("--html-3d", default="", help="Optional interactive 3D HTML output path")
    parser.add_argument("--field", default="bias_indicator", help="Initial scalar field for the 3D HTML view")
    parser.add_argument("--mesh-obj", default="", help="Optional OBJ mesh to overlay in the 3D HTML view")
    parser.add_argument("--cube", type=float, default=0.0, help="Optional outer cube half extent for the 3D HTML view")
    return parser.parse_args()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib.colors import LogNorm  # type: ignore

        return plt, LogNorm
    except Exception as exc:
        raise SystemExit("matplotlib is required for plot_boundary_bias.py") from exc


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return (ROOT / path).resolve() if not path.is_absolute() else path


def parse_structured_vtk(path: Path) -> tuple[tuple[int, int, int], tuple[float, float, float],
                                              tuple[float, float, float], dict[str, np.ndarray]]:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run --mode bias_detector first.")
    lines = path.read_text().splitlines()
    dims = None
    origin = (0.0, 0.0, 0.0)
    spacing = (1.0, 1.0, 1.0)
    fields: dict[str, np.ndarray] = {}
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        if parts[:1] == ["DIMENSIONS"]:
            dims = tuple(int(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["ORIGIN"]:
            origin = tuple(float(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["SPACING"]:
            spacing = tuple(float(v) for v in parts[1:4])
            i += 1
        elif parts[:1] == ["SCALARS"]:
            if dims is None:
                raise SystemExit("VTK SCALARS appeared before DIMENSIONS.")
            name = parts[1]
            i += 2  # skip LOOKUP_TABLE
            n = dims[0] * dims[1] * dims[2]
            values = []
            for _ in range(n):
                token = lines[i].strip()
                values.append(float(token) if token.lower() != "nan" else np.nan)
                i += 1
            fields[name] = np.array(values, dtype=float).reshape((dims[2], dims[1], dims[0]))
        else:
            i += 1
    if dims is None:
        raise SystemExit("Could not find DIMENSIONS in VTK file.")
    return dims, origin, spacing, fields


def read_summary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else {}


def read_obj_mesh(path: Path) -> dict[str, list]:
    if not path.exists():
        raise SystemExit(f"Missing OBJ mesh: {path}")

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
                for i in range(1, len(indices) - 1):
                    faces.append([indices[0], indices[i], indices[i + 1]])
    return {"vertices": vertices, "faces": faces}


def finite_or_none(value: float) -> float | None:
    return float(value) if np.isfinite(value) else None


def field_range(values: list[float | None]) -> dict[str, float | None]:
    finite = np.asarray([v for v in values if v is not None and np.isfinite(v)], dtype=float)
    if finite.size == 0:
        return {"min": None, "max": None, "positive_min": None}
    positive = finite[finite > 0]
    return {
        "min": float(finite.min()),
        "max": float(finite.max()),
        "positive_min": float(positive.min()) if positive.size else None,
    }


def build_point_cloud(dims: tuple[int, int, int],
                      origin: tuple[float, float, float],
                      spacing: tuple[float, float, float],
                      fields: dict[str, np.ndarray]) -> tuple[list[list[float]], dict[str, list[float | None]], dict[str, dict]]:
    nx, ny, nz = dims
    valid = fields.get("is_valid")
    points: list[list[float]] = []
    values_by_field: dict[str, list[float | None]] = {name: [] for name in fields}

    for iz in range(nz):
        z = origin[2] + spacing[2] * iz
        for iy in range(ny):
            y = origin[1] + spacing[1] * iy
            for ix in range(nx):
                x = origin[0] + spacing[0] * ix
                is_valid = bool(valid[iz, iy, ix] >= 0.5) if valid is not None and np.isfinite(valid[iz, iy, ix]) else True
                if not is_valid:
                    continue
                has_any = any(np.isfinite(arr[iz, iy, ix]) for arr in fields.values())
                if not has_any:
                    continue
                points.append([float(x), float(y), float(z)])
                for name, arr in fields.items():
                    values_by_field[name].append(finite_or_none(arr[iz, iy, ix]))

    ranges = {name: field_range(values) for name, values in values_by_field.items()}
    return points, values_by_field, ranges


def grid_bounds(dims: tuple[int, int, int],
                origin: tuple[float, float, float],
                spacing: tuple[float, float, float],
                cube_half_extent: float) -> dict[str, list[float] | float]:
    if cube_half_extent > 0.0:
        mins = np.asarray([-cube_half_extent, -cube_half_extent, -cube_half_extent], dtype=float)
        maxs = np.asarray([cube_half_extent, cube_half_extent, cube_half_extent], dtype=float)
    else:
        mins = np.asarray(origin, dtype=float)
        maxs = mins + np.asarray(spacing, dtype=float) * (np.asarray(dims, dtype=float) - 1.0)
    center = 0.5 * (mins + maxs)
    span = max(float((maxs - mins).max()), 1e-3)
    return {"min": mins.tolist(), "max": maxs.tolist(), "center": center.tolist(), "span": span}


def write_interactive_html(dims: tuple[int, int, int],
                           origin: tuple[float, float, float],
                           spacing: tuple[float, float, float],
                           fields: dict[str, np.ndarray],
                           summary: dict[str, str],
                           out_path: Path,
                           initial_field: str,
                           mesh_obj: str,
                           cube_half_extent: float) -> None:
    points, values_by_field, ranges = build_point_cloud(dims, origin, spacing, fields)
    mesh: dict[str, list] = {"vertices": [], "faces": []}
    mesh_label = "none"
    if mesh_obj:
        mesh_path = resolve_path(mesh_obj)
        mesh = read_obj_mesh(mesh_path)
        mesh_label = str(mesh_path.relative_to(ROOT)) if mesh_path.is_relative_to(ROOT) else str(mesh_path)

    if initial_field not in values_by_field and values_by_field:
        initial_field = next(iter(values_by_field))

    scene = {
        "title": "Boundary bias detector 3D",
        "dims": list(dims),
        "origin": list(origin),
        "spacing": list(spacing),
        "summary": summary,
        "points": points,
        "fields": values_by_field,
        "ranges": ranges,
        "initialField": initial_field,
        "mesh": {
            "label": mesh_label,
            "vertices": mesh.get("vertices", []),
            "faces": mesh.get("faces", []),
        },
        "bounds": grid_bounds(dims, origin, spacing, cube_half_extent),
        "cube": {"halfExtent": cube_half_extent},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        BOUNDARY_BIAS_HTML_TEMPLATE.replace("__SCENE_JSON__", json.dumps(scene, separators=(",", ":"))),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")


BOUNDARY_BIAS_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Boundary Bias Detector 3D</title>
  <style>
    :root {
      color-scheme: light;
      --panel: rgba(255, 255, 255, 0.93);
      --line: rgba(15, 23, 42, 0.16);
      --text: #111827;
      --muted: #64748B;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      overflow: hidden;
      font-family: Segoe UI, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      background: #F8FAFC;
    }
    canvas {
      display: block;
      width: 100vw;
      height: 100vh;
      cursor: grab;
      touch-action: none;
    }
    canvas:active { cursor: grabbing; }
    .panel {
      position: fixed;
      left: 16px;
      top: 16px;
      width: min(390px, calc(100vw - 32px));
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
      backdrop-filter: blur(10px);
    }
    .title {
      margin: 0 0 8px;
      font-size: 15px;
      font-weight: 700;
    }
    .meta {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 4px 12px;
      margin-bottom: 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .row {
      display: grid;
      grid-template-columns: 92px 1fr;
      align-items: center;
      gap: 8px;
      margin: 8px 0;
      font-size: 13px;
    }
    select, input[type="range"] {
      width: 100%;
      accent-color: #2563EB;
    }
    select {
      height: 30px;
      border: 1px solid rgba(15, 23, 42, 0.18);
      border-radius: 6px;
      background: #FFFFFF;
      color: var(--text);
      font: inherit;
      font-size: 13px;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 10px;
      margin-top: 10px;
      font-size: 13px;
    }
    label {
      display: flex;
      align-items: center;
      gap: 7px;
      min-width: 0;
      white-space: nowrap;
    }
    input[type="checkbox"] {
      width: 15px;
      height: 15px;
      margin: 0;
      accent-color: #2563EB;
    }
    button {
      height: 30px;
      border: 1px solid rgba(37, 99, 235, 0.35);
      border-radius: 6px;
      background: #EFF6FF;
      color: #1D4ED8;
      font: inherit;
      font-size: 13px;
    }
    .hint {
      margin-top: 9px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .scale {
      position: fixed;
      left: 16px;
      bottom: 16px;
      width: min(360px, calc(100vw - 32px));
      padding: 9px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.10);
      font-size: 12px;
      color: var(--muted);
    }
    .bar {
      height: 11px;
      margin: 6px 0;
      border-radius: 999px;
      background: linear-gradient(90deg, #440154, #31688E, #35B779, #FDE725);
      border: 1px solid rgba(15, 23, 42, 0.14);
    }
    .scale-labels {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-variant-numeric: tabular-nums;
    }
  </style>
</head>
<body>
  <canvas id="view"></canvas>
  <section class="panel" aria-label="Viewer controls">
    <h1 class="title">Boundary Bias Detector 3D</h1>
    <div class="meta" id="meta"></div>
    <div class="row">
      <span>Field</span>
      <select id="field"></select>
    </div>
    <div class="row">
      <span>Point size</span>
      <input id="pointSize" type="range" min="1" max="8" step="0.5" value="3">
    </div>
    <div class="row">
      <span>Threshold</span>
      <input id="threshold" type="range" min="0" max="0.98" step="0.01" value="0">
    </div>
    <div class="controls">
      <label><input type="checkbox" data-toggle="logScale" checked>Log color</label>
      <label><input type="checkbox" data-toggle="mesh" checked>Mesh surface</label>
      <label><input type="checkbox" data-toggle="meshWire">Mesh wire</label>
      <label><input type="checkbox" data-toggle="cube" checked>Outer cube</label>
      <label><input type="checkbox" data-toggle="points" checked>Bias points</label>
      <button id="reset" type="button">Reset view</button>
    </div>
    <div class="hint">Drag to rotate. Wheel to zoom. Threshold filters out low-valued points for the selected field; the old PNG is only the center z-slice.</div>
  </section>
  <div class="scale">
    <div id="scaleTitle"></div>
    <div class="bar"></div>
    <div class="scale-labels"><span id="scaleMin"></span><span id="scaleMax"></span></div>
  </div>

  <script>
    const scene = __SCENE_JSON__;
    const canvas = document.getElementById("view");
    const ctx = canvas.getContext("2d");
    const state = {
      yaw: -0.75,
      pitch: 0.45,
      zoom: 1.0,
      pointSize: 3,
      threshold: 0,
      field: scene.initialField,
      logScale: true,
      mesh: true,
      meshWire: false,
      cube: true,
      points: true,
    };
    const cubeEdges = [
      [0, 1], [0, 2], [0, 4], [3, 1], [3, 2], [3, 7],
      [5, 1], [5, 4], [5, 7], [6, 2], [6, 4], [6, 7],
    ];
    const palette = [
      [68, 1, 84],
      [59, 82, 139],
      [33, 145, 140],
      [94, 201, 98],
      [253, 231, 37],
    ];

    function resize() {
      const dpr = Math.max(1, window.devicePixelRatio || 1);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      render();
    }

    function cubeCorners() {
      const h = scene.cube.halfExtent || 0;
      if (h <= 0) return [];
      const out = [];
      for (const x of [-h, h]) for (const y of [-h, h]) for (const z of [-h, h]) out.push([x, y, z]);
      return out;
    }

    function rotatePoint(p) {
      const c = scene.bounds.center;
      let x = p[0] - c[0];
      let y = p[1] - c[1];
      let z = p[2] - c[2];
      const cy = Math.cos(state.yaw);
      const sy = Math.sin(state.yaw);
      const cp = Math.cos(state.pitch);
      const sp = Math.sin(state.pitch);
      const x1 = cy * x - sy * y;
      const y1 = sy * x + cy * y;
      const z1 = z;
      return [x1, cp * y1 - sp * z1, sp * y1 + cp * z1];
    }

    function project(p) {
      const r = rotatePoint(p);
      const scale = Math.min(window.innerWidth, window.innerHeight) / (scene.bounds.span * 1.55) * state.zoom;
      return {
        x: window.innerWidth * 0.55 + r[0] * scale,
        y: window.innerHeight * 0.53 - r[1] * scale,
        z: r[2],
      };
    }

    function lerp(a, b, t) {
      return a + (b - a) * t;
    }

    function colorRamp(t) {
      const v = Math.max(0, Math.min(1, t));
      const scaled = v * (palette.length - 1);
      const i = Math.min(palette.length - 2, Math.floor(scaled));
      const f = scaled - i;
      const a = palette[i];
      const b = palette[i + 1];
      return `rgb(${Math.round(lerp(a[0], b[0], f))},${Math.round(lerp(a[1], b[1], f))},${Math.round(lerp(a[2], b[2], f))})`;
    }

    function valueToT(value) {
      const range = scene.ranges[state.field] || {};
      if (value === null || !Number.isFinite(value) || range.min === null || range.max === null) return null;
      if (state.logScale && range.positive_min !== null && range.max > 0 && value > 0) {
        const lo = Math.log10(Math.max(range.positive_min, 1e-12));
        const hi = Math.log10(Math.max(range.max, range.positive_min));
        if (hi <= lo) return 0.5;
        return (Math.log10(value) - lo) / (hi - lo);
      }
      if (range.max <= range.min) return 0.5;
      return (value - range.min) / (range.max - range.min);
    }

    function formatValue(value) {
      if (value === null || value === undefined) return "n/a";
      const abs = Math.abs(value);
      if (abs !== 0 && (abs < 0.001 || abs >= 10000)) return Number(value).toExponential(2);
      return Number(value).toPrecision(4);
    }

    function currentScaleBounds() {
      const range = scene.ranges[state.field] || {};
      if (state.logScale && range.positive_min !== null && range.max !== null) {
        return [range.positive_min, range.max];
      }
      return [range.min, range.max];
    }

    function drawLine(a, b, color, width, alpha = 1) {
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      ctx.restore();
    }

    function drawCube() {
      const corners = cubeCorners().map(project);
      if (!corners.length) return;
      for (const [a, b] of cubeEdges) drawLine(corners[a], corners[b], "#0F172A", 1.35, 0.62);
    }

    function drawMesh() {
      const vertices = scene.mesh.vertices;
      const faces = scene.mesh.faces;
      if (!vertices.length || !faces.length || (!state.mesh && !state.meshWire)) return;
      const projected = vertices.map(project);
      const ordered = faces.map((face) => ({
        face,
        depth: (projected[face[0]].z + projected[face[1]].z + projected[face[2]].z) / 3,
      })).sort((a, b) => a.depth - b.depth);

      for (const item of ordered) {
        const a = projected[item.face[0]];
        const b = projected[item.face[1]];
        const c = projected[item.face[2]];
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.lineTo(c.x, c.y);
        ctx.closePath();
        if (state.mesh) {
          ctx.fillStyle = "rgba(100, 116, 139, 0.15)";
          ctx.fill();
        }
        if (state.meshWire) {
          ctx.strokeStyle = "rgba(51, 65, 85, 0.20)";
          ctx.lineWidth = 0.65;
          ctx.stroke();
        }
      }
    }

    function drawPoints() {
      if (!state.points) return;
      const values = scene.fields[state.field] || [];
      const projected = scene.points.map((point, index) => ({
        index,
        p: project(point),
        value: values[index],
      })).sort((a, b) => a.p.z - b.p.z);

      for (const item of projected) {
        const t = valueToT(item.value);
        if (t === null) continue;
        if (t < state.threshold) continue;
        ctx.fillStyle = colorRamp(t);
        ctx.globalAlpha = 0.80;
        ctx.beginPath();
        ctx.arc(item.p.x, item.p.y, state.pointSize, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    }

    function draw() {
      ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
      const gradient = ctx.createLinearGradient(0, 0, 0, window.innerHeight);
      gradient.addColorStop(0, "#F8FAFC");
      gradient.addColorStop(1, "#E2E8F0");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);
      drawMesh();
      if (state.cube) drawCube();
      drawPoints();
    }

    function updateScale() {
      const [lo, hi] = currentScaleBounds();
      document.getElementById("scaleTitle").textContent =
        `${state.field}${state.logScale ? " (log color)" : ""}, showing >= ${Math.round(state.threshold * 100)}%`;
      document.getElementById("scaleMin").textContent = formatValue(lo);
      document.getElementById("scaleMax").textContent = formatValue(hi);
    }

    function render() {
      updateScale();
      draw();
    }

    function initText() {
      const meta = document.getElementById("meta");
      const highBiasRatio = scene.summary.high_bias_ratio !== undefined
        ? Number(scene.summary.high_bias_ratio).toPrecision(4)
        : "n/a";
      meta.innerHTML = `
        <div>dims: ${scene.dims.join(" x ")}</div>
        <div>valid points: ${scene.points.length}</div>
        <div>epsilon: ${scene.summary.epsilon || "n/a"}</div>
        <div>walks: ${scene.summary.walks || "n/a"}</div>
        <div>high-bias ratio: ${highBiasRatio}</div>
        <div>mesh faces: ${scene.mesh.faces.length}</div>
        <div style="grid-column: 1 / -1;">mesh: ${scene.mesh.label}</div>
      `;

      const fieldSelect = document.getElementById("field");
      Object.keys(scene.fields).forEach((name) => {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        option.selected = name === state.field;
        fieldSelect.appendChild(option);
      });
    }

    function bindControls() {
      document.getElementById("field").addEventListener("change", (event) => {
        state.field = event.target.value;
        render();
      });
      document.getElementById("pointSize").addEventListener("input", (event) => {
        state.pointSize = Number(event.target.value) || 3;
        render();
      });
      document.getElementById("threshold").addEventListener("input", (event) => {
        state.threshold = Number(event.target.value) || 0;
        render();
      });
      document.querySelectorAll("input[data-toggle]").forEach((input) => {
        input.addEventListener("change", () => {
          state[input.dataset.toggle] = input.checked;
          render();
        });
      });
      document.getElementById("reset").addEventListener("click", () => {
        state.yaw = -0.75;
        state.pitch = 0.45;
        state.zoom = 1.0;
        render();
      });
    }

    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    canvas.addEventListener("pointerdown", (event) => {
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
      canvas.setPointerCapture(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      state.yaw += dx * 0.008;
      state.pitch = Math.max(-1.45, Math.min(1.45, state.pitch + dy * 0.008));
      render();
    });
    canvas.addEventListener("pointerup", () => { dragging = false; });
    canvas.addEventListener("pointercancel", () => { dragging = false; });
    canvas.addEventListener("wheel", (event) => {
      event.preventDefault();
      state.zoom = Math.max(0.18, Math.min(8, state.zoom * Math.exp(-event.deltaY * 0.001)));
      render();
    }, { passive: false });

    initText();
    bindControls();
    window.addEventListener("resize", resize);
    resize();
    render();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    vtk_path = resolve_path(args.vtk)
    summary_path = resolve_path(args.summary)
    out_path = resolve_path(args.out)

    dims, origin, spacing, fields = parse_structured_vtk(vtk_path)
    summary = read_summary(summary_path)
    plt, LogNorm = require_matplotlib()

    panels = [
        ("solution_epsilon", "u(epsilon)", False),
        ("solution_epsilon_half", "u(epsilon/2)", False),
        ("bias_indicator", "|u_eps - u_half|", True),
        ("normalized_bias", "normalized bias", True),
        ("mean_steps_epsilon", "mean steps", False),
        ("abs_error_epsilon", "abs error", True),
    ]
    z = dims[2] // 2
    fig, axes = plt.subplots(2, 3, figsize=(12.0, 7.2), constrained_layout=True)
    for ax, (field, title, use_log) in zip(axes.ravel(), panels):
        data = fields.get(field)
        if data is None:
            ax.set_title(f"missing: {field}")
            ax.axis("off")
            continue
        img = data[z, :, :]
        norm = None
        if use_log:
            finite = img[np.isfinite(img) & (img > 0)]
            if finite.size:
                norm = LogNorm(vmin=max(float(finite.min()), 1e-8), vmax=float(finite.max()))
        im = ax.imshow(img, origin="lower", cmap="viridis", norm=norm)
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.82)

    if summary:
        text = (
            f"epsilon={summary.get('epsilon', '?')}, walks={summary.get('walks', '?')}, "
            f"high-bias ratio={float(summary.get('high_bias_ratio', 0.0)):.3f}"
        )
        fig.suptitle("Boundary Bias Detector: center z-slice\n" + text, fontsize=13)
    else:
        fig.suptitle("Boundary Bias Detector: center z-slice", fontsize=13)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path}")

    if args.html_3d:
        write_interactive_html(
            dims,
            origin,
            spacing,
            fields,
            summary,
            resolve_path(args.html_3d),
            args.field,
            args.mesh_obj,
            args.cube,
        )


if __name__ == "__main__":
    main()
