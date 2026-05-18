// =============================================================================
// test_poisson.cpp
//
// Two Walk-on-Stars Poisson tests on the annular domain
//   Ω = { x : x inside cube [-L,L]³  AND  x outside sphere of radius R_sph }
//
// ── Test 1: Manufactured solution (quantitative verification) ───────────────
//   PDE:   Δu  = 6              (constant source)
//   BC:    u   = |x|²           on both boundaries
//   Exact: u(x) = x² + y² + z²  (a polynomial satisfying Δ(|x|²) = 6)
//   The MC estimate at each grid point is compared to the exact value.
//   Expected: |error| ~ std_err (Monte Carlo noise only, no bias).
//
// ── Test 2: Physical heat problem ───────────────────────────────────────────
//   PDE:   Δu  = 0              (steady-state heat, no volumetric source)
//   BC:    u   = 1  on inner sphere  (hot inclusion)
//          u   = 0  on outer cube    (cold walls)
//   This is a pure Laplace problem with a physically intuitive solution:
//   temperature field between a hot sphere and cold box.
//
// Output:
//   test1_manufactured.vtk   – structured grid, includes exact & abs_error
//   test2_heat_laplace.vtk   – structured grid
//   test1_pointcloud.vtk     – unstructured point cloud for test 1
// =============================================================================

// NOTE: TINYBVH_IMPLEMENTATION is already defined in WoStGeometryBackend.cpp.
//       Do NOT redefine it here.
#include "src/tiny_bvh.h"
#include "src/WoStGeometryBackend.hpp"
#include "src/CubeOuterBoundary.hpp"
#include "src/WoStKernel.hpp"
#include "src/utils.hpp"

#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
#include <algorithm>
#include <chrono>

#ifdef _OPENMP
#  include <omp.h>
#endif

#ifndef M_PI
#  define M_PI 3.14159265358979323846
#endif

using namespace wost;

int main(){
    std::string objfile = "./spot/spot_triangulated.obj";
    unsigned int numSamples = 1000;
    float L = 10.0f;

    WoStGeometryBackend interior(objfile);
    CubeOuterBoundary exterior(-L, L);
    WoStKernel kernel(interior, exterior);

    Random rnd;

    // =========================================================================
    // Test 1: Manufactured solution (quantitative verification)
    //   PDE:   Δu = 6              (constant source)
    //   BC:    u = |x|²           on both boundaries
    //   Exact: u(x) = x² + y² + z²
    // =========================================================================
    {
        printf("\n=== Test 1: Manufactured Solution ===\n");
        

        auto g_inner = [](const BoundaryPoint& bp) -> float {
            return dot3(bp.position, bp.position);
        };
        auto g_outer = [](const BoundaryPoint& bp) -> float {
            return dot3(bp.position, bp.position);
        };
        
        // Define source term: f(x) = 6 (constant)
        auto f = [](const vec3& x) -> float {
            (void)x;
            return 6.0f;
        };
        
        std::vector<PointSolution> pointcloud;
        
        WoStParams params;
        params.numSamples = numSamples;
        params.maxSteps = 512;
        params.eps = 1e-4f;
        
        auto start_time = std::chrono::high_resolution_clock::now();
        
        // Solve on structured grid
        int valid_count = 0;
        #pragma omp parallel for
        for (uint32_t idx = 0; idx < numSamples; ++idx) {

            float x = rnd.randDouble(-L, L);
            float y = rnd.randDouble(-L, L);
            float z = rnd.randDouble(-L, L);    
            vec3 point = {x, y, z};
                    
            if (kernel.InDomain(point)) {
                WalkResult result = kernel.SolvePoisson(point, g_inner, g_outer, f, params);
                PointSolution ps;
                ps.pos = point;
                ps.value = result.value;
                ps.stdErr = result.stdErr;
                ps.meanSteps = result.meanSteps;
                ps.exact = dot3(point, point);
                pointcloud.push_back(ps);
                        
                valid_count++;

            }
        }
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        
        printf("Valid points: %d / %d\n", valid_count, numSamples);
        printf("Computation time: %.2f seconds\n", elapsed.count());
        printf("Average samples per point: %d\n", numSamples);
        

        // Write point cloud output
        if (WriteVTKPointCloud("test1_manufactured_pointcloud.vtk", pointcloud, true)) {
            printf("✓ Point cloud written to test1_manufactured_pointcloud.vtk\n");
        } else {
            printf("✗ Failed to write point cloud\n");
        }
        
        // Print some statistics
        float max_error = 0.0f;
        float total_error = 0.0f;
        for (const auto& ps : pointcloud) {
            float error = std::abs(ps.value - ps.exact);
            max_error = std::max(max_error, error);
            total_error += error;
        }
        printf("Max absolute error: %.6f\n", max_error);
        printf("Mean absolute error: %.6f\n", total_error / pointcloud.size());
    }
    return 0;
}