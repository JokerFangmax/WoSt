// =============================================================================
// main.cpp
//
// Manufactured Poisson test on
//   Omega = { x : x inside cube [-L, L]^3 AND x outside the inner mesh }
//
// Exact solution:
//   u(x) = x^2 + y^2 + z^2
//   Delta u = 6
//
// Mixed boundary conditions:
//   Dirichlet on the complement of the selected Neumann patches
//   Neumann flux h = grad(u) . n = 2 x . n on the selected patches
//
// The run also compares plain Monte Carlo against antithetic variance reduction
// at one probe point, then writes the same VTK outputs used by the project
// presentation scripts.
// =============================================================================

#include "src/WoStGeometryBackend.hpp"
#include "src/CubeOuterBoundary.hpp"
#include "src/WoStKernel.hpp"
#include "src/utils.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

#ifdef _OPENMP
#include <omp.h>
#endif

using namespace wost;

namespace {

vec3 ChooseProbePoint(const WoStKernel& kernel) {
    const std::vector<vec3> candidates = {
        {0.75f, 0.00f, 0.00f},
        {0.60f, 0.20f, 0.10f},
        {0.35f, -0.45f, 0.20f},
        {-0.55f, 0.25f, -0.15f},
    };

    for (const vec3& p : candidates) {
        if (kernel.InDomain(p)) {
            return p;
        }
    }
    return {0.75f, 0.00f, 0.00f};
}

} // namespace

int main() {
    const std::string objfile = "./spot/spot_triangulated.obj";
    const int numQueryPoints = 100000;
    const int walksPerPoint = 256;
    const float L = 1.0f;
    const int sliceResolution = 96;

    WoStGeometryBackend interior(objfile);
    CubeOuterBoundary exterior(-L, L);
    WoStKernel kernel(interior, exterior);

#ifdef _OPENMP
    std::printf("OpenMP threads: %d\n", omp_get_max_threads());
#endif

    const auto exact = [](const vec3& p) -> float {
        return dot3(p, p);
    };

    const auto g_inner = [&](const BoundaryPoint& bp) -> float {
        return exact(bp.position);
    };
    const auto g_outer = [&](const BoundaryPoint& bp) -> float {
        return exact(bp.position);
    };

    const auto h_inner = [](const BoundaryPoint& bp) -> float {
        return 2.0f * dot3(bp.position, bp.normal);
    };
    const auto h_outer = [](const BoundaryPoint& bp) -> float {
        return 2.0f * dot3(bp.position, bp.normal);
    };

    // Inner mesh: upper half uses Neumann, lower half stays Dirichlet.
    const auto is_neumann_inner = [](const BoundaryPoint& bp) -> bool {
        return bp.position.z >= 0.0f;
    };

    // Outer cube: +X face uses Neumann, the other five faces stay Dirichlet.
    const auto is_neumann_outer = [](const BoundaryPoint& bp) -> bool {
        return bp.normal.x > 0.9f;
    };

    const auto f = [](const vec3&) -> float {
        return 6.0f;
    };

    WoStParams baselineParams;
    baselineParams.numSamples = walksPerPoint;
    baselineParams.maxSteps = 512;
    baselineParams.eps = 1e-4f;
    baselineParams.neumannOffset = 5e-4f;
    baselineParams.seed = 0xDEADBEEF;
    baselineParams.varianceReduction = VarianceReductionMode::None;

    WoStParams vrParams = baselineParams;
    vrParams.varianceReduction = VarianceReductionMode::Antithetic;

    std::printf("\n=== Test 1: Manufactured Mixed Dirichlet/Neumann Solution ===\n");
    std::printf("Exact solution: u(x) = x^2 + y^2 + z^2, Delta u = 6\n");
    std::printf("Inner boundary: z >= 0 uses Neumann flux, remainder Dirichlet\n");
    std::printf("Outer boundary: +X face uses Neumann flux, remainder Dirichlet\n");

    const vec3 probe = ChooseProbePoint(kernel);
    const WalkResult probeBaseline = kernel.SolvePoisson(
        probe, g_inner, g_outer, h_inner, h_outer,
        is_neumann_inner, is_neumann_outer, f, baselineParams);
    const WalkResult probeReduced = kernel.SolvePoisson(
        probe, g_inner, g_outer, h_inner, h_outer,
        is_neumann_inner, is_neumann_outer, f, vrParams);

    std::printf("\nVariance reduction check at probe (%.3f, %.3f, %.3f)\n",
                probe.x, probe.y, probe.z);
    std::printf("  plain MC      : value = %.6f, stdErr = %.6f, meanSteps = %.2f\n",
                probeBaseline.value, probeBaseline.stdErr, probeBaseline.meanSteps);
    std::printf("  antithetic MC : value = %.6f, stdErr = %.6f, meanSteps = %.2f\n",
                probeReduced.value, probeReduced.stdErr, probeReduced.meanSteps);
    std::printf("  exact         : value = %.6f\n", exact(probe));

    auto start_time = std::chrono::high_resolution_clock::now();

    int valid_count = 0;
    std::vector<PointSolution> pointcloud;
    pointcloud.reserve(numQueryPoints);

#pragma omp parallel
    {
#ifdef _OPENMP
        FastRNG thread_rng(static_cast<uint32_t>(0x1234567u + omp_get_thread_num() * 977u));
#else
        FastRNG thread_rng(0x1234567u);
#endif

        std::vector<PointSolution> local_results;
#ifdef _OPENMP
        local_results.reserve(numQueryPoints / std::max(1, omp_get_max_threads()) + 1);
#else
        local_results.reserve(numQueryPoints);
#endif

#pragma omp for schedule(dynamic, 64) nowait
        for (int idx = 0; idx < numQueryPoints; ++idx) {
            const float x = thread_rng.randFloat() * 2.0f * L - L;
            const float y = thread_rng.randFloat() * 2.0f * L - L;
            const float z = thread_rng.randFloat() * 2.0f * L - L;
            const vec3 point = {x, y, z};

            if (!kernel.InDomain(point)) {
                continue;
            }

            const WalkResult result = kernel.SolvePoisson(
                point, g_inner, g_outer, h_inner, h_outer,
                is_neumann_inner, is_neumann_outer, f, vrParams);

            PointSolution ps;
            ps.pos = point;
            ps.value = result.value;
            ps.stdErr = result.stdErr;
            ps.meanSteps = result.meanSteps;
            ps.exact = exact(point);
            local_results.push_back(ps);
        }

#pragma omp critical
        {
            valid_count += static_cast<int>(local_results.size());
            pointcloud.insert(pointcloud.end(),
                              std::make_move_iterator(local_results.begin()),
                              std::make_move_iterator(local_results.end()));
        }
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;

    std::printf("\nValid points: %d / %d\n", valid_count, numQueryPoints);
    std::printf("Computation time: %.2f seconds\n", elapsed.count());
    std::printf("Walks per point: %d\n", walksPerPoint);

    GridInfo sliceInfo;
    sliceInfo.nx = sliceResolution;
    sliceInfo.ny = sliceResolution;
    sliceInfo.nz = 1;
    sliceInfo.ox = -L;
    sliceInfo.oy = -L;
    sliceInfo.oz = 0.0f;
    sliceInfo.dx = (2.0f * L) / static_cast<float>(sliceResolution - 1);
    sliceInfo.dy = (2.0f * L) / static_cast<float>(sliceResolution - 1);
    sliceInfo.dz = 1.0f;

    std::vector<GridPoint> xySlice(sliceInfo.nx * sliceInfo.ny * sliceInfo.nz);

#pragma omp parallel for schedule(dynamic, 8)
    for (int iy = 0; iy < sliceInfo.ny; ++iy) {
        for (int ix = 0; ix < sliceInfo.nx; ++ix) {
            const int flat = iy * sliceInfo.nx + ix;
            const float x = sliceInfo.ox + sliceInfo.dx * static_cast<float>(ix);
            const float y = sliceInfo.oy + sliceInfo.dy * static_cast<float>(iy);
            const vec3 point = {x, y, 0.0f};

            GridPoint gp{};
            if (kernel.InDomain(point)) {
                const WalkResult result = kernel.SolvePoisson(
                    point, g_inner, g_outer, h_inner, h_outer,
                    is_neumann_inner, is_neumann_outer, f, vrParams);
                gp.value = result.value;
                gp.stdErr = result.stdErr;
                gp.meanSteps = result.meanSteps;
                gp.exact = exact(point);
                gp.valid = true;
            } else {
                gp.value = 0.0f;
                gp.stdErr = 0.0f;
                gp.meanSteps = 0.0f;
                gp.exact = 0.0f;
                gp.valid = false;
            }
            xySlice[flat] = gp;
        }
    }

    if (WriteVTKPointCloud("test1_manufactured_pointcloud.vtk", pointcloud, true)) {
        std::printf("Point cloud written to test1_manufactured_pointcloud.vtk\n");
    } else {
        std::printf("Failed to write point cloud\n");
    }

    if (WriteVTKStructuredPoints("test1_manufactured_slice_xy.vtk", sliceInfo, xySlice, true)) {
        std::printf("XY slice written to test1_manufactured_slice_xy.vtk\n");
    } else {
        std::printf("Failed to write XY slice\n");
    }

    float max_error = 0.0f;
    float total_error = 0.0f;
    float total_std_err = 0.0f;
    for (const auto& ps : pointcloud) {
        const float error = std::abs(ps.value - ps.exact);
        max_error = std::max(max_error, error);
        total_error += error;
        total_std_err += ps.stdErr;
    }

    if (!pointcloud.empty()) {
        std::printf("Max absolute error: %.6f\n", max_error);
        std::printf("Mean absolute error: %.6f\n", total_error / static_cast<float>(pointcloud.size()));
        std::printf("Mean reported stdErr: %.6f\n", total_std_err / static_cast<float>(pointcloud.size()));
    }

    return 0;
}
