import argparse

import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np

from WoSt import boundary_value, sample_direction, sdf_circle


def harmonic_exact(point):
    x, y = point
    return x * x - y * y


def walk_with_path(x0, eps=1e-4, max_steps=1000):
    x = np.array(x0, dtype=np.float64)
    path = [x.copy()]

    for _ in range(max_steps):
        radius = sdf_circle(x)
        if radius < eps:
            boundary = x / np.linalg.norm(x)
            path.append(boundary.copy())
            return boundary_value(boundary), np.asarray(path)

        direction = sample_direction()
        x = x + radius * direction
        path.append(x.copy())

    return 0.0, np.asarray(path)


def build_demo(walks, x0):
    values = []
    paths = []
    running = []

    total = 0.0
    for idx in range(walks):
        value, path = walk_with_path(x0)
        values.append(value)
        paths.append(path)
        total += value
        running.append(total / float(idx + 1))

    return np.asarray(values), paths, np.asarray(running)


def draw_poster(x0, exact, paths, running, output=None, show=True):
    bg = "#f7f1e7"
    panel = "#fffaf4"
    ink = "#18324a"
    accent = "#cb5c3f"
    blue = "#2f7ed8"
    green = "#2ca58d"

    plt.rcParams.update({
        "figure.facecolor": bg,
        "axes.facecolor": panel,
        "axes.edgecolor": ink,
        "axes.labelcolor": ink,
        "xtick.color": ink,
        "ytick.color": ink,
        "text.color": ink,
        "font.size": 11,
    })

    fig = plt.figure(figsize=(14, 6.8), facecolor=bg)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.1])
    ax_walk = fig.add_subplot(grid[0, 0])
    ax_conv = fig.add_subplot(grid[0, 1])

    theta = np.linspace(0.0, 2.0 * np.pi, 400)
    ax_walk.plot(np.cos(theta), np.sin(theta), color=ink, lw=2.2)
    ax_walk.scatter([x0[0]], [x0[1]], s=90, color=accent, zorder=5, label="query point")

    for path in paths[:-1]:
        ax_walk.plot(path[:, 0], path[:, 1], color=blue, alpha=0.15, lw=1.2)
        ax_walk.scatter(path[-1, 0], path[-1, 1], color=green, alpha=0.15, s=18)

    ax_walk.plot(paths[-1][:, 0], paths[-1][:, 1], color=accent, lw=2.8, label="latest WoSt path")
    ax_walk.scatter(paths[-1][-1, 0], paths[-1][-1, 1], color=green, s=52, zorder=6, label="boundary hit")

    ax_walk.set_aspect("equal")
    ax_walk.set_xlim(-1.12, 1.12)
    ax_walk.set_ylim(-1.12, 1.12)
    ax_walk.set_title("Walk-on-Stars Paths", fontweight="bold")
    ax_walk.legend(loc="upper right", frameon=False)

    xs = np.arange(1, len(running) + 1)
    ax_conv.plot(xs, running, color=blue, lw=2.5, label="Monte Carlo estimate")
    ax_conv.axhline(exact, color=accent, lw=2.0, ls="--", label="exact harmonic value")
    ax_conv.fill_between(xs, np.minimum(running, exact), np.maximum(running, exact), color=accent, alpha=0.08)
    ax_conv.set_title("Convergence During Demo", fontweight="bold")
    ax_conv.set_xlabel("number of walks")
    ax_conv.set_ylabel("u(x0)")
    ax_conv.legend(frameon=False)

    fig.suptitle("Live Demo Poster: Why Walk-on-Stars Feels Intuitive", fontsize=20, fontweight="bold", color=ink)
    fig.text(
        0.06,
        0.04,
        f"x0 = ({x0[0]:.2f}, {x0[1]:.2f})   exact = {exact:.5f}   final estimate = {running[-1]:.5f}   abs error = {abs(running[-1] - exact):.5f}",
        fontsize=11.5,
        color=accent,
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])

    if output:
        fig.savefig(output, dpi=220, bbox_inches="tight")
    if show:
        plt.show()


def animate_demo(x0, exact, paths, running, interval_ms, output=None):
    bg = "#f7f1e7"
    panel = "#fffaf4"
    ink = "#18324a"
    accent = "#cb5c3f"
    blue = "#2f7ed8"
    green = "#2ca58d"

    plt.rcParams.update({
        "figure.facecolor": bg,
        "axes.facecolor": panel,
        "axes.edgecolor": ink,
        "axes.labelcolor": ink,
        "xtick.color": ink,
        "ytick.color": ink,
        "text.color": ink,
        "font.size": 11,
    })

    fig = plt.figure(figsize=(14, 6.8), facecolor=bg)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.1])
    ax_walk = fig.add_subplot(grid[0, 0])
    ax_conv = fig.add_subplot(grid[0, 1])

    theta = np.linspace(0.0, 2.0 * np.pi, 400)
    ax_walk.plot(np.cos(theta), np.sin(theta), color=ink, lw=2.2)
    ax_walk.scatter([x0[0]], [x0[1]], s=90, color=accent, zorder=5)
    ax_walk.set_aspect("equal")
    ax_walk.set_xlim(-1.12, 1.12)
    ax_walk.set_ylim(-1.12, 1.12)
    ax_walk.set_title("Walk-on-Stars Paths", fontweight="bold")

    ax_conv.axhline(exact, color=accent, lw=2.0, ls="--")
    ax_conv.set_xlim(1, len(running))
    ymin = min(np.min(running), exact) - 0.1
    ymax = max(np.max(running), exact) + 0.1
    ax_conv.set_ylim(ymin, ymax)
    ax_conv.set_title("Convergence During Demo", fontweight="bold")
    ax_conv.set_xlabel("number of walks")
    ax_conv.set_ylabel("u(x0)")

    walk_lines = []
    point_hits = []
    (run_line,) = ax_conv.plot([], [], color=blue, lw=2.5)
    info = fig.text(0.06, 0.04, "", fontsize=11.5, color=accent)

    def update(frame):
        while len(walk_lines) < frame:
            line, = ax_walk.plot([], [], color=blue, alpha=0.12, lw=1.2)
            walk_lines.append(line)
            hit = ax_walk.scatter([], [], color=green, alpha=0.12, s=18)
            point_hits.append(hit)

        for idx in range(frame):
            path = paths[idx]
            walk_lines[idx].set_data(path[:, 0], path[:, 1])
            point_hits[idx].set_offsets(path[-1:])

        if frame < len(paths):
            current = paths[frame]
            if len(walk_lines) == frame:
                line, = ax_walk.plot(current[:, 0], current[:, 1], color=accent, lw=2.6)
                walk_lines.append(line)
                hit = ax_walk.scatter(current[-1, 0], current[-1, 1], color=green, s=48, zorder=6)
                point_hits.append(hit)
            else:
                walk_lines[frame].set_data(current[:, 0], current[:, 1])
                walk_lines[frame].set_color(accent)
                walk_lines[frame].set_alpha(1.0)
                walk_lines[frame].set_linewidth(2.6)
                point_hits[frame].set_offsets(current[-1:])
                point_hits[frame].set_alpha(1.0)

        upto = frame + 1
        run_line.set_data(np.arange(1, upto + 1), running[:upto])
        info.set_text(
            f"walk {upto}/{len(running)}   estimate = {running[upto - 1]:.5f}   exact = {exact:.5f}   abs error = {abs(running[upto - 1] - exact):.5f}"
        )
        return walk_lines + point_hits + [run_line, info]

    ani = animation.FuncAnimation(fig, update, frames=len(paths), interval=interval_ms, blit=False, repeat=False)
    fig.suptitle("Live Demo: Monte Carlo Walks Converge to the Harmonic Solution", fontsize=20, fontweight="bold", color=ink)
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])

    if output:
        ani.save(output, writer="pillow", fps=max(1, int(1000 / interval_ms)))
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Presentation-friendly live demo for the 2D Walk-on-Stars Python solver.")
    parser.add_argument("--walks", type=int, default=40, help="Number of Monte Carlo walks to visualize")
    parser.add_argument("--x0", type=float, nargs=2, default=[0.35, 0.2], help="Query point inside the unit disk")
    parser.add_argument("--animate", action="store_true", help="Show an animation instead of a static poster")
    parser.add_argument("--interval", type=int, default=550, help="Animation frame interval in milliseconds")
    parser.add_argument("--save", default="", help="Optional output path (.png for poster, .gif for animation)")
    parser.add_argument("--no-show", action="store_true", help="Skip interactive display when saving poster")
    args = parser.parse_args()

    x0 = np.asarray(args.x0, dtype=float)
    exact = harmonic_exact(x0)
    _, paths, running = build_demo(args.walks, x0)

    if args.animate:
        animate_demo(x0, exact, paths, running, args.interval, output=args.save or None)
    else:
        draw_poster(x0, exact, paths, running, output=args.save or None, show=not args.no_show)


if __name__ == "__main__":
    main()
