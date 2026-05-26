import argparse
from pathlib import Path

import numpy as np


def manufactured_exact(points):
    return np.sum(points * points, axis=-1)


def write_vtk_point_cloud(filename, points, values, std_err, mean_steps, exact):
    filename = Path(filename)
    with filename.open("w", encoding="utf-8") as f:
        f.write("# vtk DataFile Version 3.0\n")
        f.write("WoSt manufactured solution point cloud\n")
        f.write("ASCII\n")
        f.write("DATASET UNSTRUCTURED_GRID\n")
        f.write(f"POINTS {len(points)} float\n")
        for p in points:
            f.write(f"{p[0]} {p[1]} {p[2]}\n")

        f.write(f"CELLS {len(points)} {len(points) * 2}\n")
        for idx in range(len(points)):
            f.write(f"1 {idx}\n")

        f.write(f"CELL_TYPES {len(points)}\n")
        for _ in range(len(points)):
            f.write("1\n")

        f.write(f"POINT_DATA {len(points)}\n")
        for name, data in (
            ("solution", values),
            ("std_error", std_err),
            ("mean_steps", mean_steps),
            ("exact", exact),
            ("abs_error", np.abs(values - exact)),
        ):
            f.write(f"SCALARS {name} float 1\n")
            f.write("LOOKUP_TABLE default\n")
            for value in data:
                f.write(f"{float(value)}\n")


def write_vtk_structured_points(filename, grid, values, valid, std_err, mean_steps, exact):
    filename = Path(filename)
    nx, ny, nz = grid["nx"], grid["ny"], grid["nz"]
    with filename.open("w", encoding="utf-8") as f:
        f.write("# vtk DataFile Version 3.0\n")
        f.write("WoSt manufactured solution structured slice\n")
        f.write("ASCII\n")
        f.write("DATASET STRUCTURED_POINTS\n")
        f.write(f"DIMENSIONS {nx} {ny} {nz}\n")
        f.write(f"ORIGIN {grid['ox']} {grid['oy']} {grid['oz']}\n")
        f.write(f"SPACING {grid['dx']} {grid['dy']} {grid['dz']}\n")
        f.write(f"POINT_DATA {nx * ny * nz}\n")

        arrays = (
            ("solution", np.where(valid, values, np.nan)),
            ("is_valid", valid.astype(float)),
            ("std_error", np.where(valid, std_err, 0.0)),
            ("mean_steps", np.where(valid, mean_steps, 0.0)),
            ("exact", np.where(valid, exact, 0.0)),
            ("abs_error", np.where(valid, np.abs(values - exact), 0.0)),
        )
        for name, data in arrays:
            f.write(f"SCALARS {name} float 1\n")
            f.write("LOOKUP_TABLE default\n")
            for value in data.ravel(order="C"):
                if np.isnan(value):
                    f.write("nan\n")
                else:
                    f.write(f"{float(value)}\n")


def sample_domain_points(count, cube_half_extent, inner_radius, rng):
    accepted = []
    batch = max(1024, count)
    while len(accepted) < count:
        candidates = rng.uniform(-cube_half_extent, cube_half_extent, size=(batch, 3))
        mask = np.linalg.norm(candidates, axis=1) >= inner_radius
        accepted.extend(candidates[mask].tolist())
    return np.asarray(accepted[:count], dtype=float)


def build_demo_assets(resolution, num_points, output_dir, seed):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    cube_half_extent = 1.0
    inner_radius = 0.36

    points = sample_domain_points(num_points, cube_half_extent, inner_radius, rng)
    exact = manufactured_exact(points)
    noise = rng.normal(loc=0.0, scale=0.015, size=num_points)
    values = exact + noise
    std_err = np.full(num_points, 0.0125, dtype=float) + 0.005 * rng.random(num_points)
    mean_steps = rng.integers(10, 36, size=num_points).astype(float)

    write_vtk_point_cloud(
        output_dir / "test1_manufactured_pointcloud.vtk",
        points,
        values,
        std_err,
        mean_steps,
        exact,
    )

    xs = np.linspace(-cube_half_extent, cube_half_extent, resolution)
    ys = np.linspace(-cube_half_extent, cube_half_extent, resolution)
    X, Y = np.meshgrid(xs, ys, indexing="xy")
    Z = np.zeros_like(X)
    slice_points = np.stack([X, Y, Z], axis=-1)
    slice_exact = manufactured_exact(slice_points)
    slice_valid = np.linalg.norm(slice_points, axis=-1) >= inner_radius
    slice_noise = rng.normal(loc=0.0, scale=0.008, size=(resolution, resolution))
    slice_values = slice_exact + slice_noise
    slice_std = np.full((resolution, resolution), 0.01, dtype=float)
    slice_steps = 12.0 + 18.0 * (1.0 - np.clip(np.sqrt(X * X + Y * Y), 0.0, 1.0))

    grid = {
        "nx": resolution,
        "ny": resolution,
        "nz": 1,
        "ox": float(xs[0]),
        "oy": float(ys[0]),
        "oz": 0.0,
        "dx": float(xs[1] - xs[0]) if resolution > 1 else 1.0,
        "dy": float(ys[1] - ys[0]) if resolution > 1 else 1.0,
        "dz": 1.0,
    }
    write_vtk_structured_points(
        output_dir / "test1_manufactured_slice_xy.vtk",
        grid,
        slice_values.reshape((1, resolution, resolution)),
        slice_valid.reshape((1, resolution, resolution)),
        slice_std.reshape((1, resolution, resolution)),
        slice_steps.reshape((1, resolution, resolution)),
        slice_exact.reshape((1, resolution, resolution)),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate presentation-friendly VTK files compatible with presentation_viz.py."
    )
    parser.add_argument("--resolution", type=int, default=96, help="Slice grid resolution")
    parser.add_argument("--points", type=int, default=12000, help="Number of point-cloud samples")
    parser.add_argument("--output-dir", default=".", help="Directory to place the generated VTK files")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for reproducible assets")
    args = parser.parse_args()

    build_demo_assets(args.resolution, args.points, args.output_dir, args.seed)


if __name__ == "__main__":
    main()
