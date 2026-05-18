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
// Output:
//   test1_manufactured.vtk   – structured grid, includes exact & abs_error
//   test1_pointcloud.vtk     – unstructured point cloud for test 1
// =============================================================================

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
    
    // Set OpenMP thread count to number of physical cores
    #ifdef _OPENMP
    int num_threads = omp_get_max_threads();
    printf("OpenMP threads: %d\n", num_threads);
    #endif

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
        
        WoStParams params;
        params.numSamples = 1024;
        params.maxSteps = 512;
        params.eps = 1e-4f;
        
        auto start_time = std::chrono::high_resolution_clock::now();
        
        // Solve on structured grid with optimized OpenMP parallelization
        int valid_count = 0;
        std::vector<PointSolution> pointcloud;
        pointcloud.reserve(numSamples);  // Pre-allocate to avoid reallocation
        
        #pragma omp parallel
        {
            // Thread-local random number generator to avoid contention
            #ifdef _OPENMP
            Random thread_rng(omp_get_thread_num() + static_cast<int>(time(nullptr)));
            #else
            Random thread_rng;
            #endif
            
            // Thread-local storage for results to minimize synchronization
            std::vector<PointSolution> local_results;
            #ifdef _OPENMP
            local_results.reserve(numSamples / omp_get_num_threads() + 1);
            #endif
            
            #pragma omp for schedule(dynamic, 64) nowait
            for (uint32_t idx = 0; idx < numSamples; ++idx) {
                float x = thread_rng.randDouble(-L, L);
                float y = thread_rng.randDouble(-L, L);
                float z = thread_rng.randDouble(-L, L);    
                vec3 point = {x, y, z};
                        
                if (kernel.InDomain(point)) {
                    WalkResult result = kernel.SolvePoisson(point, g_inner, g_outer, f, params);
                    PointSolution ps;
                    ps.pos = point;
                    ps.value = result.value;
                    ps.stdErr = result.stdErr;
                    ps.meanSteps = result.meanSteps;
                    ps.exact = dot3(point, point);
                    local_results.push_back(ps);
                }
            }
            
            // Merge thread-local results (minimize critical section)
            #pragma omp critical
            {
                pointcloud.insert(pointcloud.end(), 
                                 std::make_move_iterator(local_results.begin()),
                                 std::make_move_iterator(local_results.end()));
                valid_count += local_results.size();
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