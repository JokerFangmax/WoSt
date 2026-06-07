#!/usr/bin/env python3
"""Plot traced Walk-on-Stars paths from demo_point mode."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", default="results/live_trace.csv")
    parser.add_argument("--summary", default="results/live_demo_summary.csv")
    parser.add_argument("--out", default="results/live_trace_plot.png")
    parser.add_argument("--gif", default="", help="Optional animated GIF output path")
    parser.add_argument("--out-3d", default="", help="Optional static 3D trace plot output path")
    parser.add_argument("--gif-3d", default="", help="Optional animated 3D trace GIF output path")
    parser.add_argument("--html-3d", default="", help="Optional interactive 3D HTML output path")
    parser.add_argument("--mesh-obj", default="", help="Optional OBJ mesh to include in the interactive 3D view")
    parser.add_argument("--cube", type=float, default=0.0, help="Optional outer cube half extent for the interactive view")
    parser.add_argument("--skip-2d", action="store_true", help="Do not write the default 2D static plot")
    parser.add_argument("--interval", type=int, default=140, help="GIF frame interval in milliseconds")
    parser.add_argument("--max-frames", type=int, default=180, help="Maximum GIF frames; long traces are subsampled")
    parser.add_argument("--elev", type=float, default=24.0, help="3D view elevation angle")
    parser.add_argument("--azim", type=float, default=-55.0, help="3D view azimuth angle")
    return parser.parse_args()


def require_matplotlib():
    try:
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception as exc:
        raise SystemExit("matplotlib is required for plot_live_trace.py") from exc


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Missing {path}. Run --mode demo_point first.")
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def resolve_output_path(path_text: str) -> Path:
    path = Path(path_text)
    return (ROOT / path).resolve() if not path.is_absolute() else path


def resolve_input_path(path_text: str) -> Path:
    path = Path(path_text)
    return (ROOT / path).resolve() if not path.is_absolute() else path


EVENT_STYLES = {
    "start": ("*", "black", 120, "start"),
    "sphere_step": ("o", "#2563EB", 18, "sphere step"),
    "neumann_reflect": ("D", "#F97316", 42, "Neumann reflection"),
    "dirichlet_hit": ("X", "#16A34A", 70, "Dirichlet termination"),
    "max_step": ("s", "#DC2626", 52, "max-step termination"),
    "end": ("x", "#111827", 36, "end"),
}

EVENT_COLORS = {
    "start": "#111827",
    "sphere_step": "#2563EB",
    "neumann_reflect": "#F97316",
    "dirichlet_hit": "#16A34A",
    "max_step": "#DC2626",
    "end": "#111827",
}


def grouped_walks(rows: list[dict[str, str]]) -> dict[int, list[dict[str, str]]]:
    walks: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        walks[int(row["walk_id"])].append(row)
    return {walk_id: sorted(pts, key=lambda r: int(r["step_id"])) for walk_id, pts in walks.items()}


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
                    if idx < 0:
                        idx = len(vertices) + idx
                    else:
                        idx -= 1
                    if 0 <= idx < len(vertices):
                        indices.append(idx)
                for i in range(1, len(indices) - 1):
                    faces.append([indices[0], indices[i], indices[i + 1]])
    return {"vertices": vertices, "faces": faces}


def cube_points(half_extent: float) -> list[list[float]]:
    if half_extent <= 0.0:
        return []
    h = half_extent
    return [[x, y, z] for x in (-h, h) for y in (-h, h) for z in (-h, h)]


def compute_scene_bounds(rows: list[dict[str, str]], mesh: dict[str, list], cube_half_extent: float) -> dict[str, list[float] | float]:
    points = [[float(r["x"]), float(r["y"]), float(r["z"])] for r in rows]
    points.extend(mesh.get("vertices", []))
    points.extend(cube_points(cube_half_extent))
    if not points:
        points = [[0.0, 0.0, 0.0]]

    arr = np.asarray(points, dtype=float)
    mins = arr.min(axis=0)
    maxs = arr.max(axis=0)
    center = 0.5 * (mins + maxs)
    span = max(float((maxs - mins).max()), 1e-3)
    return {
        "min": mins.tolist(),
        "max": maxs.tolist(),
        "center": center.tolist(),
        "span": span,
    }


def summary_box_lines(summary: dict[str, str]) -> list[str]:
    box_lines = []
    for key, label in [
        ("estimated_value", "estimate"),
        ("exact_value", "exact"),
        ("absolute_error", "abs error"),
        ("standard_error", "std error"),
        ("mean_steps", "mean steps"),
        ("epsilon", "epsilon"),
        ("walks", "walks"),
    ]:
        if key in summary:
            try:
                value = float(summary[key])
                box_lines.append(f"{label}: {value:.4g}")
            except ValueError:
                box_lines.append(f"{label}: {summary[key]}")
    return box_lines


def configure_axes(ax, rows: list[dict[str, str]]) -> None:
    xs = np.asarray([float(r["x"]) for r in rows], dtype=float)
    ys = np.asarray([float(r["y"]) for r in rows], dtype=float)
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = float(ys.min()), float(ys.max())
    span = max(xmax - xmin, ymax - ymin, 1e-3)
    pad = 0.08 * span
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_title("Walk Path Debugger: traced random walks")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)


def configure_axes_3d(ax, rows: list[dict[str, str]], elev: float, azim: float) -> None:
    xs = np.asarray([float(r["x"]) for r in rows], dtype=float)
    ys = np.asarray([float(r["y"]) for r in rows], dtype=float)
    zs = np.asarray([float(r["z"]) for r in rows], dtype=float)
    mins = np.asarray([xs.min(), ys.min(), zs.min()], dtype=float)
    maxs = np.asarray([xs.max(), ys.max(), zs.max()], dtype=float)
    center = 0.5 * (mins + maxs)
    span = max(float((maxs - mins).max()), 1e-3)
    half = 0.58 * span
    ax.set_xlim(center[0] - half, center[0] + half)
    ax.set_ylim(center[1] - half, center[1] + half)
    ax.set_zlim(center[2] - half, center[2] + half)
    ax.set_title("Walk Path Debugger: 3D traced random walks")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.view_init(elev=elev, azim=azim)
    try:
        ax.set_box_aspect((1, 1, 1))
    except AttributeError:
        pass
    ax.grid(True, alpha=0.25)


def draw_static_plot(plt, rows: list[dict[str, str]], summary: dict[str, str], out_path: Path) -> None:
    walks = grouped_walks(rows)
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    walk_colors = plt.cm.tab10.colors

    for idx, (walk_id, pts) in enumerate(sorted(walks.items())):
        xs = [float(r["x"]) for r in pts]
        ys = [float(r["y"]) for r in pts]
        ax.plot(xs, ys, lw=1.1, alpha=0.42, color=walk_colors[idx % len(walk_colors)])

    seen_labels = set()
    for event, (marker, color, size, label) in EVENT_STYLES.items():
        event_rows = [r for r in rows if r["event_type"] == event]
        if not event_rows:
            continue
        label_arg = label if label not in seen_labels else None
        seen_labels.add(label)
        ax.scatter(
            [float(r["x"]) for r in event_rows],
            [float(r["y"]) for r in event_rows],
            s=size,
            marker=marker,
            color=color,
            edgecolor="black" if event in {"neumann_reflect", "dirichlet_hit", "max_step"} else None,
            linewidth=0.45,
            label=label_arg,
            zorder=5 if event != "sphere_step" else 3,
            alpha=0.9 if event != "sphere_step" else 0.55,
        )

    configure_axes(ax, rows)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

    box_lines = summary_box_lines(summary)
    if box_lines:
        ax.text(0.02, 0.98, "\n".join(box_lines), transform=ax.transAxes,
                va="top", ha="left", fontsize=9,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.88, edgecolor="0.75"))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path}")
    plt.close(fig)


def draw_static_plot_3d(plt, rows: list[dict[str, str]], summary: dict[str, str],
                        out_path: Path, elev: float, azim: float) -> None:
    walks = grouped_walks(rows)
    fig = plt.figure(figsize=(8.4, 6.8))
    ax = fig.add_subplot(111, projection="3d")
    walk_colors = plt.cm.tab10.colors

    for idx, (walk_id, pts) in enumerate(sorted(walks.items())):
        xs = [float(r["x"]) for r in pts]
        ys = [float(r["y"]) for r in pts]
        zs = [float(r["z"]) for r in pts]
        ax.plot(xs, ys, zs, lw=1.2, alpha=0.55, color=walk_colors[idx % len(walk_colors)])

    seen_labels = set()
    for event, (marker, color, size, label) in EVENT_STYLES.items():
        event_rows = [r for r in rows if r["event_type"] == event]
        if not event_rows:
            continue
        label_arg = label if label not in seen_labels else None
        seen_labels.add(label)
        ax.scatter(
            [float(r["x"]) for r in event_rows],
            [float(r["y"]) for r in event_rows],
            [float(r["z"]) for r in event_rows],
            s=size,
            marker=marker,
            color=color,
            edgecolor="black" if event in {"neumann_reflect", "dirichlet_hit", "max_step"} else None,
            linewidth=0.45,
            label=label_arg,
            alpha=0.92 if event != "sphere_step" else 0.48,
            depthshade=False,
        )

    configure_axes_3d(ax, rows, elev, azim)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    box_lines = summary_box_lines(summary)
    if box_lines:
        ax.text2D(0.02, 0.98, "\n".join(box_lines), transform=ax.transAxes,
                  va="top", ha="left", fontsize=9,
                  bbox=dict(boxstyle="round", facecolor="white", alpha=0.88, edgecolor="0.75"))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    print(f"Wrote {out_path}")
    plt.close(fig)


def draw_gif(plt, rows: list[dict[str, str]], summary: dict[str, str], gif_path: Path,
             interval: int, max_frames: int) -> None:
    import matplotlib.animation as animation  # type: ignore

    walks = grouped_walks(rows)
    fig, ax = plt.subplots(figsize=(8.0, 6.2))
    configure_axes(ax, rows)
    walk_colors = plt.cm.tab10.colors

    max_step = max(int(r["step_id"]) for r in rows)
    if max_step + 1 <= max_frames:
        frame_steps = list(range(max_step + 1))
    else:
        frame_steps = sorted(set(np.linspace(0, max_step, max_frames, dtype=int).tolist()))

    lines = {}
    for idx, walk_id in enumerate(sorted(walks)):
        (line,) = ax.plot([], [], lw=1.4, alpha=0.72, color=walk_colors[idx % len(walk_colors)])
        lines[walk_id] = line

    scatters = {}
    seen_labels = set()
    for event, (marker, color, size, label) in EVENT_STYLES.items():
        label_arg = label if label not in seen_labels else None
        seen_labels.add(label)
        scatters[event] = ax.scatter(
            [], [], s=size, marker=marker, color=color,
            edgecolor="black" if event in {"neumann_reflect", "dirichlet_hit", "max_step"} else None,
            linewidth=0.45, label=label_arg,
            zorder=5 if event != "sphere_step" else 3,
            alpha=0.9 if event != "sphere_step" else 0.55,
        )

    box_lines = summary_box_lines(summary)
    if box_lines:
        ax.text(0.02, 0.98, "\n".join(box_lines), transform=ax.transAxes,
                va="top", ha="left", fontsize=9,
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.88, edgecolor="0.75"))
    frame_text = ax.text(0.02, 0.02, "", transform=ax.transAxes,
                         va="bottom", ha="left", fontsize=9,
                         bbox=dict(boxstyle="round", facecolor="white", alpha=0.82, edgecolor="0.75"))
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)

    def update(step_limit: int):
        for walk_id, pts in walks.items():
            visible = [r for r in pts if int(r["step_id"]) <= step_limit]
            if visible:
                lines[walk_id].set_data(
                    [float(r["x"]) for r in visible],
                    [float(r["y"]) for r in visible],
                )
            else:
                lines[walk_id].set_data([], [])

        for event, scatter in scatters.items():
            visible_rows = [r for r in rows if r["event_type"] == event and int(r["step_id"]) <= step_limit]
            if visible_rows:
                scatter.set_offsets(np.asarray([[float(r["x"]), float(r["y"])] for r in visible_rows]))
            else:
                scatter.set_offsets(np.empty((0, 2)))

        frame_text.set_text(f"showing steps <= {step_limit} / {max_step}")
        return list(lines.values()) + list(scatters.values()) + [frame_text]

    ani = animation.FuncAnimation(fig, update, frames=frame_steps, interval=interval, blit=False, repeat=True)
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    ani.save(gif_path, writer="pillow", fps=max(1, int(1000 / max(1, interval))))
    print(f"Wrote {gif_path}")
    plt.close(fig)


def draw_gif_3d(plt, rows: list[dict[str, str]], summary: dict[str, str], gif_path: Path,
                interval: int, max_frames: int, elev: float, azim: float) -> None:
    import matplotlib.animation as animation  # type: ignore

    walks = grouped_walks(rows)
    fig = plt.figure(figsize=(8.4, 6.8))
    ax = fig.add_subplot(111, projection="3d")
    configure_axes_3d(ax, rows, elev, azim)
    walk_colors = plt.cm.tab10.colors

    max_step = max(int(r["step_id"]) for r in rows)
    if max_step + 1 <= max_frames:
        frame_steps = list(range(max_step + 1))
    else:
        frame_steps = sorted(set(np.linspace(0, max_step, max_frames, dtype=int).tolist()))

    lines = {}
    for idx, walk_id in enumerate(sorted(walks)):
        (line,) = ax.plot([], [], [], lw=1.5, alpha=0.78, color=walk_colors[idx % len(walk_colors)])
        lines[walk_id] = line

    scatters = {}
    seen_labels = set()
    for event, (marker, color, size, label) in EVENT_STYLES.items():
        label_arg = label if label not in seen_labels else None
        seen_labels.add(label)
        scatters[event] = ax.scatter(
            [], [], [], s=size, marker=marker, color=color,
            edgecolor="black" if event in {"neumann_reflect", "dirichlet_hit", "max_step"} else None,
            linewidth=0.45, label=label_arg,
            alpha=0.92 if event != "sphere_step" else 0.48,
            depthshade=False,
        )

    box_lines = summary_box_lines(summary)
    if box_lines:
        ax.text2D(0.02, 0.98, "\n".join(box_lines), transform=ax.transAxes,
                  va="top", ha="left", fontsize=9,
                  bbox=dict(boxstyle="round", facecolor="white", alpha=0.88, edgecolor="0.75"))
    frame_text = ax.text2D(0.02, 0.02, "", transform=ax.transAxes,
                           va="bottom", ha="left", fontsize=9,
                           bbox=dict(boxstyle="round", facecolor="white", alpha=0.82, edgecolor="0.75"))
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    def update(step_limit: int):
        for walk_id, pts in walks.items():
            visible = [r for r in pts if int(r["step_id"]) <= step_limit]
            if visible:
                lines[walk_id].set_data(
                    [float(r["x"]) for r in visible],
                    [float(r["y"]) for r in visible],
                )
                lines[walk_id].set_3d_properties([float(r["z"]) for r in visible])
            else:
                lines[walk_id].set_data([], [])
                lines[walk_id].set_3d_properties([])

        for event, scatter in scatters.items():
            visible_rows = [r for r in rows if r["event_type"] == event and int(r["step_id"]) <= step_limit]
            if visible_rows:
                xs = [float(r["x"]) for r in visible_rows]
                ys = [float(r["y"]) for r in visible_rows]
                zs = [float(r["z"]) for r in visible_rows]
                scatter._offsets3d = (xs, ys, zs)
            else:
                scatter._offsets3d = ([], [], [])

        frame_text.set_text(f"showing steps <= {step_limit} / {max_step}")
        return list(lines.values()) + list(scatters.values()) + [frame_text]

    ani = animation.FuncAnimation(fig, update, frames=frame_steps, interval=interval, blit=False, repeat=True)
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    ani.save(gif_path, writer="pillow", fps=max(1, int(1000 / max(1, interval))))
    print(f"Wrote {gif_path}")
    plt.close(fig)


def build_interactive_scene(rows: list[dict[str, str]], summary: dict[str, str],
                            mesh: dict[str, list], mesh_label: str,
                            cube_half_extent: float) -> dict:
    walk_colors = [
        "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD",
        "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF",
    ]
    walks = []
    for idx, (walk_id, pts) in enumerate(sorted(grouped_walks(rows).items())):
        walks.append({
            "id": walk_id,
            "color": walk_colors[idx % len(walk_colors)],
            "points": [
                {
                    "x": float(r["x"]),
                    "y": float(r["y"]),
                    "z": float(r["z"]),
                    "step": int(r["step_id"]),
                    "event": r["event_type"],
                }
                for r in pts
            ],
        })

    non_end_steps = [int(r["step_id"]) for r in rows if r["event_type"] != "end"]
    return {
        "title": "WoSt interactive 3D trace",
        "summary": summary_box_lines(summary),
        "walks": walks,
        "eventColors": EVENT_COLORS,
        "mesh": {
            "label": mesh_label,
            "vertices": mesh.get("vertices", []),
            "faces": mesh.get("faces", []),
        },
        "cube": {"halfExtent": cube_half_extent},
        "bounds": compute_scene_bounds(rows, mesh, cube_half_extent),
        "animation": {
            "maxStep": max(non_end_steps) if non_end_steps else 0,
        },
        "counts": {
            "walks": len(walks),
            "traceRows": len(rows),
            "meshVertices": len(mesh.get("vertices", [])),
            "meshFaces": len(mesh.get("faces", [])),
        },
    }


def write_interactive_html(rows: list[dict[str, str]], summary: dict[str, str],
                           out_path: Path, mesh_obj: str, cube_half_extent: float) -> None:
    mesh: dict[str, list] = {"vertices": [], "faces": []}
    mesh_label = "none"
    if mesh_obj:
        mesh_path = resolve_input_path(mesh_obj)
        mesh = read_obj_mesh(mesh_path)
        mesh_label = str(mesh_path.relative_to(ROOT)) if mesh_path.is_relative_to(ROOT) else str(mesh_path)

    scene = build_interactive_scene(rows, summary, mesh, mesh_label, cube_half_extent)
    scene_json = json.dumps(scene, separators=(",", ":"))
    html = INTERACTIVE_HTML_TEMPLATE.replace("__SCENE_JSON__", scene_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")


INTERACTIVE_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WoSt Interactive 3D Trace</title>
  <style>
    :root {
      color-scheme: light;
      --panel: rgba(255, 255, 255, 0.92);
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
      width: min(360px, calc(100vw - 32px));
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
    .controls {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px 10px;
      font-size: 13px;
    }
    .timeline {
      display: grid;
      grid-template-columns: auto 1fr auto auto;
      align-items: center;
      gap: 8px;
      margin: 10px 0 9px;
    }
    .timeline button {
      width: 58px;
    }
    .timeline input[type="range"] {
      width: 100%;
      accent-color: #2563EB;
    }
    .timeline select {
      height: 30px;
      border: 1px solid rgba(15, 23, 42, 0.18);
      border-radius: 6px;
      background: #FFFFFF;
      color: var(--text);
      font: inherit;
      font-size: 13px;
    }
    .step-readout {
      min-width: 76px;
      text-align: right;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
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
    .legend {
      position: fixed;
      left: 16px;
      bottom: 16px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      max-width: calc(100vw - 32px);
      padding: 9px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.10);
      font-size: 12px;
      color: var(--muted);
    }
    .key { display: inline-flex; align-items: center; gap: 6px; }
    .swatch {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      border: 1px solid rgba(15, 23, 42, 0.35);
    }
  </style>
</head>
<body>
  <canvas id="view"></canvas>
  <section class="panel" aria-label="Viewer controls">
    <h1 class="title">WoSt interactive 3D trace</h1>
    <div class="meta" id="meta"></div>
    <div class="timeline">
      <button id="play" type="button">Play</button>
      <input id="frame" type="range" min="0" value="0" step="1">
      <span class="step-readout" id="stepReadout"></span>
      <select id="speed" aria-label="Animation speed">
        <option value="0.5">0.5x</option>
        <option value="1" selected>1x</option>
        <option value="2">2x</option>
        <option value="4">4x</option>
      </select>
    </div>
    <div class="controls">
      <label><input type="checkbox" data-toggle="mesh" checked>Mesh surface</label>
      <label><input type="checkbox" data-toggle="meshWire" checked>Mesh wire</label>
      <label><input type="checkbox" data-toggle="cube" checked>Outer cube</label>
      <label><input type="checkbox" data-toggle="trace" checked>Walk paths</label>
      <label><input type="checkbox" data-toggle="events" checked>Event points</label>
      <label><input type="checkbox" data-toggle="sphereSteps">Sphere points</label>
      <button id="reset" type="button">Reset view</button>
    </div>
    <div class="hint">Drag to rotate. Wheel to zoom. The mesh is the inner boundary; the cube is the outer Dirichlet boundary.</div>
  </section>
  <div class="legend" id="legend"></div>

  <script>
    const scene = __SCENE_JSON__;
    const canvas = document.getElementById("view");
    const ctx = canvas.getContext("2d");
    const state = {
      yaw: -0.75,
      pitch: 0.42,
      zoom: 1.0,
      mesh: true,
      meshWire: true,
      cube: true,
      trace: true,
      events: true,
      sphereSteps: false,
      frame: scene.animation.maxStep,
      playing: false,
      lastTime: 0,
      stepsPerSecond: 70,
      speed: 1,
    };
    const cubeEdges = [
      [0, 1], [0, 2], [0, 4], [3, 1], [3, 2], [3, 7],
      [5, 1], [5, 4], [5, 7], [6, 2], [6, 4], [6, 7],
    ];
    const eventLabels = {
      start: "start",
      sphere_step: "sphere step",
      neumann_reflect: "Neumann reflect",
      dirichlet_hit: "Dirichlet hit",
      max_step: "max step",
      end: "end",
    };

    function resize() {
      const dpr = Math.max(1, window.devicePixelRatio || 1);
      canvas.width = Math.floor(window.innerWidth * dpr);
      canvas.height = Math.floor(window.innerHeight * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
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
        x: window.innerWidth * 0.54 + r[0] * scale,
        y: window.innerHeight * 0.52 - r[1] * scale,
        z: r[2],
      };
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

    function drawMesh() {
      const vertices = scene.mesh.vertices;
      const faces = scene.mesh.faces;
      if (!vertices.length || !faces.length) return;
      const projected = vertices.map(project);
      const ordered = faces.map((face) => ({
        face,
        depth: (projected[face[0]].z + projected[face[1]].z + projected[face[2]].z) / 3,
      })).sort((a, b) => a.depth - b.depth);

      for (const item of ordered) {
        const a = projected[item.face[0]];
        const b = projected[item.face[1]];
        const c = projected[item.face[2]];
        if (state.mesh) {
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.lineTo(c.x, c.y);
          ctx.closePath();
          ctx.fillStyle = "rgba(100, 116, 139, 0.18)";
          ctx.fill();
        }
        if (state.meshWire) {
          ctx.strokeStyle = "rgba(51, 65, 85, 0.18)";
          ctx.lineWidth = 0.65;
          ctx.stroke();
        }
      }
    }

    function drawCube() {
      const corners = cubeCorners().map(project);
      if (!corners.length) return;
      for (const [a, b] of cubeEdges) drawLine(corners[a], corners[b], "#0F172A", 1.35, 0.62);
    }

    function drawTrace() {
      for (const walk of scene.walks) {
        const visiblePoints = walk.points.filter((pt) => (
          (pt.event === "end" && state.frame >= scene.animation.maxStep) ||
          (pt.event !== "end" && pt.step <= state.frame)
        ));
        if (state.trace && visiblePoints.length > 1) {
          ctx.save();
          ctx.strokeStyle = walk.color;
          ctx.lineWidth = 1.65;
          ctx.globalAlpha = 0.78;
          ctx.beginPath();
          visiblePoints.forEach((pt, idx) => {
            const q = project([pt.x, pt.y, pt.z]);
            if (idx === 0) ctx.moveTo(q.x, q.y);
            else ctx.lineTo(q.x, q.y);
          });
          ctx.stroke();
          ctx.restore();
        }
        if (state.events) {
          for (const pt of visiblePoints) {
            if (pt.event === "sphere_step" && !state.sphereSteps) continue;
            drawEventPoint(pt);
          }
        }
      }
    }

    function drawEventPoint(pt) {
      const q = project([pt.x, pt.y, pt.z]);
      const color = scene.eventColors[pt.event] || "#111827";
      const size = pt.event === "start" ? 6 : pt.event === "sphere_step" ? 2.5 : 5;
      ctx.save();
      ctx.fillStyle = color;
      ctx.strokeStyle = "rgba(15, 23, 42, 0.85)";
      ctx.lineWidth = 1;
      if (pt.event === "neumann_reflect") {
        ctx.beginPath();
        ctx.moveTo(q.x, q.y - size);
        ctx.lineTo(q.x + size, q.y);
        ctx.lineTo(q.x, q.y + size);
        ctx.lineTo(q.x - size, q.y);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else if (pt.event === "dirichlet_hit" || pt.event === "end") {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(q.x - size, q.y - size);
        ctx.lineTo(q.x + size, q.y + size);
        ctx.moveTo(q.x + size, q.y - size);
        ctx.lineTo(q.x - size, q.y + size);
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(q.x, q.y, size, 0, Math.PI * 2);
        ctx.fill();
        if (pt.event !== "sphere_step") ctx.stroke();
      }
      ctx.restore();
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
      drawTrace();
    }

    function updateTimeline() {
      const frameInput = document.getElementById("frame");
      const readout = document.getElementById("stepReadout");
      frameInput.value = String(Math.round(state.frame));
      readout.textContent = `step ${Math.round(state.frame)} / ${scene.animation.maxStep}`;
    }

    function render() {
      updateTimeline();
      draw();
    }

    function tick(time) {
      if (!state.playing) return;
      if (!state.lastTime) state.lastTime = time;
      const dt = Math.min(0.08, (time - state.lastTime) / 1000);
      state.lastTime = time;
      state.frame += state.stepsPerSecond * state.speed * dt;
      if (state.frame >= scene.animation.maxStep) {
        state.frame = scene.animation.maxStep;
        state.playing = false;
        document.getElementById("play").textContent = "Play";
      }
      render();
      if (state.playing) requestAnimationFrame(tick);
    }

    function initText() {
      const meta = document.getElementById("meta");
      const summary = scene.summary.slice(0, 6).map((line) => `<div>${line}</div>`).join("");
      meta.innerHTML = `
        <div>walks: ${scene.counts.walks}</div>
        <div>trace rows: ${scene.counts.traceRows}</div>
        <div>mesh faces: ${scene.counts.meshFaces}</div>
        <div>cube half: ${scene.cube.halfExtent || "none"}</div>
        <div style="grid-column: 1 / -1;">mesh: ${scene.mesh.label}</div>
        ${summary}
      `;
      const legend = document.getElementById("legend");
      legend.innerHTML = Object.entries(scene.eventColors).map(([event, color]) => (
        `<span class="key"><span class="swatch" style="background:${color}"></span>${eventLabels[event] || event}</span>`
      )).join("");
    }

    function bindControls() {
      const frameInput = document.getElementById("frame");
      frameInput.max = String(scene.animation.maxStep);
      frameInput.value = String(state.frame);
      frameInput.addEventListener("input", () => {
        state.frame = Number(frameInput.value);
        state.playing = false;
        state.lastTime = 0;
        document.getElementById("play").textContent = "Play";
        render();
      });
      document.getElementById("play").addEventListener("click", () => {
        if (state.frame >= scene.animation.maxStep) state.frame = 0;
        state.playing = !state.playing;
        state.lastTime = 0;
        document.getElementById("play").textContent = state.playing ? "Pause" : "Play";
        render();
        if (state.playing) requestAnimationFrame(tick);
      });
      document.getElementById("speed").addEventListener("change", (event) => {
        state.speed = Number(event.target.value) || 1;
      });
      document.querySelectorAll("input[data-toggle]").forEach((input) => {
        input.addEventListener("change", () => {
          state[input.dataset.toggle] = input.checked;
          render();
        });
      });
      document.getElementById("reset").addEventListener("click", () => {
        state.yaw = -0.75;
        state.pitch = 0.42;
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
    trace_path = resolve_input_path(args.trace)
    summary_path = resolve_input_path(args.summary)

    rows = read_csv(trace_path)
    summary_rows = read_csv(summary_path)
    summary = summary_rows[0] if summary_rows else {}

    needs_matplotlib = (not args.skip_2d and bool(args.out)) or bool(args.gif) or bool(args.out_3d) or bool(args.gif_3d)
    plt = require_matplotlib() if needs_matplotlib else None
    if not args.skip_2d and args.out:
        out_path = resolve_output_path(args.out)
        draw_static_plot(plt, rows, summary, out_path)
    if args.gif:
        gif_path = resolve_output_path(args.gif)
        draw_gif(plt, rows, summary, gif_path, args.interval, args.max_frames)
    if args.out_3d:
        out_3d_path = resolve_output_path(args.out_3d)
        draw_static_plot_3d(plt, rows, summary, out_3d_path, args.elev, args.azim)
    if args.gif_3d:
        gif_3d_path = resolve_output_path(args.gif_3d)
        draw_gif_3d(plt, rows, summary, gif_3d_path, args.interval, args.max_frames, args.elev, args.azim)
    if args.html_3d:
        html_3d_path = resolve_output_path(args.html_3d)
        write_interactive_html(rows, summary, html_3d_path, args.mesh_obj, args.cube)


if __name__ == "__main__":
    main()
