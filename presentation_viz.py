import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _extract_scalar(lines, start_idx):
    data = []
    idx = start_idx
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if line.startswith("SCALARS ") or line.startswith("VECTORS ") or line.startswith("FIELD "):
            break
        data.extend(float(x) for x in line.split())
        idx += 1
    return np.asarray(data, dtype=float), idx


def read_structured_points(path):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    dims = None
    scalars = {}
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("DIMENSIONS"):
            dims = tuple(int(v) for v in line.split()[1:4])
        elif line.startswith("SCALARS "):
            name = line.split()[1]
            idx += 2
            values, idx = _extract_scalar(lines, idx)
            scalars[name] = values
            continue
        idx += 1

    if dims is None:
        raise ValueError(f"Could not parse DIMENSIONS from {path}")

    nx, ny, nz = dims
    reshaped = {}
    for key, values in scalars.items():
        reshaped[key] = values.reshape((nz, ny, nx))
    return dims, reshaped


def read_point_cloud(path):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    points = None
    scalars = {}
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if line.startswith("POINTS "):
            num_points = int(line.split()[1])
            coords = []
            idx += 1
            while len(coords) < num_points * 3:
                coords.extend(float(x) for x in lines[idx].split())
                idx += 1
            points = np.asarray(coords, dtype=float).reshape((num_points, 3))
            continue
        if line.startswith("SCALARS "):
            name = line.split()[1]
            idx += 2
            values, idx = _extract_scalar(lines, idx)
            scalars[name] = values
            continue
        idx += 1

    if points is None:
        raise ValueError(f"Could not parse POINTS from {path}")

    return points, scalars


def make_figure(slice_path, point_path, output_path):
    slice_path = Path(slice_path)
    point_path = Path(point_path)
    missing = [str(path) for path in (slice_path, point_path) if not path.exists()]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(
            "Missing VTK input file(s): "
            f"{missing_text}. "
            "Generate them first with "
            "`python generate_presentation_data.py` "
            "or with the C++ solver once the build toolchain is ready."
        )

    dims, slice_scalars = read_structured_points(slice_path)
    points, point_scalars = read_point_cloud(point_path)

    solution = slice_scalars["solution"][0]
    validity = slice_scalars.get("is_valid", np.ones_like(slice_scalars["solution"]))[0] > 0.5
    solution = np.where(validity, solution, np.nan)

    abs_error = None
    if "abs_error" in slice_scalars:
        abs_error = slice_scalars["abs_error"][0]
        abs_error = np.where(validity, abs_error, np.nan)

    point_solution = point_scalars.get("solution")
    point_error = point_scalars.get("abs_error")

    bg = "#f6f1e8"
    panel = "#fffaf2"
    ink = "#17324d"
    accent = "#d95f43"

    plt.rcParams.update({
        "figure.facecolor": bg,
        "axes.facecolor": panel,
        "axes.edgecolor": ink,
        "axes.labelcolor": ink,
        "axes.titleweight": "bold",
        "xtick.color": ink,
        "ytick.color": ink,
        "text.color": ink,
        "font.size": 11,
    })

    fig = plt.figure(figsize=(15, 8), facecolor=bg)
    grid = fig.add_gridspec(2, 3, width_ratios=[1.05, 1.05, 1.35], height_ratios=[1, 0.22])

    ax_sol = fig.add_subplot(grid[0, 0])
    ax_err = fig.add_subplot(grid[0, 1])
    ax_cloud = fig.add_subplot(grid[0, 2], projection="3d")
    ax_text = fig.add_subplot(grid[1, :])
    ax_text.axis("off")

    im0 = ax_sol.imshow(solution, origin="lower", cmap="turbo")
    ax_sol.set_title("Solution Slice")
    ax_sol.set_xlabel("x")
    ax_sol.set_ylabel("y")
    plt.colorbar(im0, ax=ax_sol, fraction=0.046, pad=0.04)

    if abs_error is not None:
        im1 = ax_err.imshow(abs_error, origin="lower", cmap="magma")
        mean_error = float(np.nanmean(abs_error))
        max_error = float(np.nanmax(abs_error))
        ax_err.set_title("Absolute Error Slice")
        plt.colorbar(im1, ax=ax_err, fraction=0.046, pad=0.04)
    else:
        im1 = ax_err.imshow(np.nan_to_num(solution), origin="lower", cmap="cividis")
        mean_error = float("nan")
        max_error = float("nan")
        ax_err.set_title("Diagnostic Slice")
        plt.colorbar(im1, ax=ax_err, fraction=0.046, pad=0.04)
    ax_err.set_xlabel("x")
    ax_err.set_ylabel("y")

    order = np.argsort(points[:, 2])
    colors = point_solution[order] if point_solution is not None else points[order, 2]
    cloud = ax_cloud.scatter(
        points[order, 0],
        points[order, 1],
        points[order, 2],
        c=colors,
        cmap="viridis",
        s=10,
        alpha=0.75,
        linewidths=0.0,
    )
    ax_cloud.set_title("Monte Carlo Volume Samples")
    ax_cloud.set_xlabel("x")
    ax_cloud.set_ylabel("y")
    ax_cloud.set_zlabel("z")
    ax_cloud.view_init(elev=24, azim=38)
    ax_cloud.set_box_aspect((1, 1, 1))
    plt.colorbar(cloud, ax=ax_cloud, fraction=0.03, pad=0.08)

    n_points = points.shape[0]
    mean_std = float(np.mean(point_scalars["std_error"])) if "std_error" in point_scalars else float("nan")
    msg = (
        "Presentation framing: left panel shows the solution on a clean XY slice, "
        "middle panel proves correctness via the manufactured-solution error, "
        "and right panel keeps the stochastic 3D character visible."
    )
    stats = (
        f"Slice dims: {dims[0]} x {dims[1]} x {dims[2]}    "
        f"Point samples: {n_points}    "
        f"Mean std err: {mean_std:.4e}    "
        f"Mean abs err: {mean_error:.4e}    "
        f"Max abs err: {max_error:.4e}"
    )
    if point_error is not None:
        stats += f"    Point-cloud mean abs err: {float(np.mean(point_error)):.4e}"

    ax_text.text(0.01, 0.72, "WoSt Presentation Figure", fontsize=20, fontweight="bold", color=ink)
    ax_text.text(0.01, 0.36, msg, fontsize=11.5, color=ink)
    ax_text.text(0.01, 0.06, stats, fontsize=10.5, color=accent)

    fig.tight_layout()
    fig.savefig(output_path, dpi=220, bbox_inches="tight")


def main():
    parser = argparse.ArgumentParser(description="Create a presentation-ready figure from WoSt VTK outputs.")
    parser.add_argument("--slice", default="test1_manufactured_slice_xy.vtk", help="Structured-points slice VTK file")
    parser.add_argument("--pointcloud", default="test1_manufactured_pointcloud.vtk", help="Point-cloud VTK file")
    parser.add_argument("--output", default="presentation_figure.png", help="Output image path")
    args = parser.parse_args()

    make_figure(args.slice, args.pointcloud, args.output)


if __name__ == "__main__":
    main()
