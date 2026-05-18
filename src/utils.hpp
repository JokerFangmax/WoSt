
#ifndef UTILS_HPP
#define UTILS_HPP

#include "tiny_bvh.h"
#include <functional>
#include <cstdint>
#include <random>
#include <ctime>
#include <iostream>
#include <fstream>


using vec3 = tinybvh::bvhvec3;
using vec4 = tinybvh::bvhvec4;

// ---------------------------------------------------------------------------
// BoundaryPoint – result of closest-point / ray-hit queries
// ---------------------------------------------------------------------------
struct BoundaryPoint {
    vec3 position;        // point on ∂Ω
    vec3 normal;          // outward unit normal
    float dist   = 0.f;   // distance from the query point x
    uint32_t triIdx = ~0u;   // flat triangle index (vertex = triangles[triIdx*3+k])
};

// ---------------------------------------------------------------------------
// SilhouetteEdge – precomputed for the mesh topology
//
// An edge shared by two triangles with outward normals n0, n1.
// From query point x the edge is a silhouette when the signs of
//   dot(n0, x - v0)  and  dot(n1, x - v0)
// differ, i.e. one face points toward x and the other points away.
// The WoSt star radius is min(closest-boundary, closest-silhouette).
// ---------------------------------------------------------------------------
struct SilhouetteEdge {
    vec3 v0, v1;   // endpoints
    vec3 n0, n1;   // face normals of the two adjacent triangles
};

// ===========================================================================
// Callback types
// ===========================================================================

/// Dirichlet BC:  boundary-point → scalar value g(p)
using DirichletFn = std::function<float(const BoundaryPoint&)>;

/// Neumann BC:    boundary-point → outward normal derivative h(p)
using NeumannFn = std::function<float(const BoundaryPoint&)>;

/// Volume source: interior point  → f(x)   (right-hand side of Δu = f)
using SourceFn = std::function<float(const vec3&)>;

/// Predicate – returns true if a boundary point lies on the Neumann region ΓN
using NeumannPredFn = std::function<bool(const BoundaryPoint&)>;

// ===========================================================================
// Walk parameters
// ===========================================================================
struct WoStParams {
    int numSamples = 256;   ///< independent random walks per query point
    int maxSteps   = 512;   ///< safety cap on walk length
    float eps = 1e-4f; ///< absorption radius near ∂Ω
    uint64_t seed = 0xDEADBEEF; ///< base RNG seed (varied per sample)
};

// ===========================================================================
// Per-query result
// ===========================================================================
struct WalkResult {
    float value       = 0.f;  ///< Monte Carlo estimate  E[u(x)]
    float stdErr      = 0.f;  ///< standard error  σ / sqrt(N)
    float meanSteps   = 0.f;  ///< average walk length in steps
    bool anyDiverged = false;///< true if any walk hit maxSteps limit
};

struct Random{
    std::mt19937 rnd;
    inline void init(int seed){
        rnd = std::mt19937(seed);
    }
    inline void init_rd(){
        rnd = std::mt19937(std::random_device{}());
    }
    inline std::mt19937& get_rnd(){ return rnd; }

    // 返回一个[_min, _max)的均匀实数
    inline double randDouble(double _min = 0, double _max = 1){
        return std::uniform_real_distribution<>(_min, _max)(rnd);
    }

    // 返回一个[_min, _max]的均匀整数
    inline int randInt(int _min = 0, int _max = 0x7fffffff){
        return std::uniform_int_distribution<>(_min, _max)(rnd);
    }
    Random(int x){ init(x); }
    Random(){ init_rd(); }
};

inline vec3 sampleUnitSphere(Random& rng) {
    float x, y, z, r2;
    do {    
        x  = 2.f * rng.randDouble() - 1.f;
        y  = 2.f * rng.randDouble() - 1.f;
        z  = 2.f * rng.randDouble() - 1.f;
        r2 = x*x + y*y + z*z;
    } while (r2 < 1e-12f || r2 > 1.f);
    float inv = 1.f / std::sqrt(r2);
    return { x * inv, y * inv, z * inv };
}

// ============================================================================
// Internal math aliases (avoid repeating the tinybvh_ prefix everywhere)
// ============================================================================
static inline float dot3  (const vec3& a, const vec3& b) { return tinybvh::tinybvh_dot(a, b); }
static inline float len3  (const vec3& a)                { return tinybvh::tinybvh_length(a); }
static inline vec3 norm3 (const vec3& a)                { return tinybvh::tinybvh_normalize(a); }
static inline vec3 cross3(const vec3& a, const vec3& b) { return tinybvh::tinybvh_cross(a, b); }

static inline vec3 sub(const vec3& a, const vec3& b) {
    return { a.x - b.x, a.y - b.y, a.z - b.z };
}
static inline vec3 add(const vec3& a, const vec3& b) {
    return { a.x + b.x, a.y + b.y, a.z + b.z };
}
static inline vec3 scale(const vec3& a, float s) {
    return { a.x * s, a.y * s, a.z * s };
}
static inline float dist2(const vec3& a, const vec3& b) {
    vec3 d = sub(a, b);
    return dot3(d, d);
}
inline vec3 scale3(const vec3& a, float s) noexcept {
    return { a.x * s, a.y * s, a.z * s };
}
// x + s * d
inline vec3 madd(const vec3& x, const vec3& d, float s) noexcept {
    return { x.x + d.x * s, x.y + d.y * s, x.z + d.z * s };
}
// reflect incident direction `d` about outward normal `n`
inline vec3 reflect(const vec3& d, const vec3& n) noexcept {
    float dn = dot3(d, n);
    return { d.x - 2.f * dn * n.x,
             d.y - 2.f * dn * n.y,
             d.z - 2.f * dn * n.z };
}

// -----------------------------------------------------------------------
// Assemble a BoundaryPoint from a successful IntersectRay result.
// -----------------------------------------------------------------------
inline BoundaryPoint makeBP(const vec3& origin, const vec3& dir, float t, const vec3& normal, uint32_t prim) {
    BoundaryPoint bp;
    bp.position = madd(origin, dir, t);
    bp.normal   = normal;
    bp.dist     = t;
    bp.triIdx   = prim;
    return bp;
}

// -----------------------------------------------------------------------
// Finalise statistics from accumulated sums.
// -----------------------------------------------------------------------
inline void finalise(WalkResult& r, double sumV, double sumV2, int sumSteps, int N) {
    r.value     = static_cast<float>(sumV / N);
    r.meanSteps = static_cast<float>(sumSteps) / static_cast<float>(N);

    double mean  = sumV / N;
    double var   = std::max(0.0, sumV2 / N - mean * mean);
    double sigma = std::sqrt(var);                     // population std-dev
    r.stdErr     = static_cast<float>(sigma / std::sqrt(static_cast<double>(N)));
}

// ===========================================================================
// VTKWriter.hpp  –  header-only legacy ASCII VTK writers
//
// Two output modes:
//
//   (A) WriteVTKPointCloud
//       DATASET UNSTRUCTURED_GRID, one VTK_VERTEX cell per point.
//       Suitable for scattered / irregular query points.
//       Open in ParaView → apply "Resample to Image" for volume rendering.
//
//   (B) WriteVTKStructuredPoints
//       DATASET STRUCTURED_POINTS on a regular Cartesian grid.
//       Better for slice planes, iso-surfaces, and volume rendering.
//       Invalid domain points are written as NaN (ParaView masks them).
//
// Both writers emit:
//   • solution     – Monte Carlo estimate of u(x)
//   • std_error    – σ / √N  (Monte Carlo noise level)
//   • mean_steps   – average walk length (diagnostic)
//   • is_valid     – 1.0 inside domain, 0.0 outside  (structured writer only)
// ===========================================================================

struct PointSolution {
    vec3  pos;
    float value;
    float stdErr;
    float meanSteps;
    float exact;   // optional analytic value (0 if unknown); written only when hasExact=true
};

// ---------------------------------------------------------------------------
// GridInfo – describes the regular Cartesian grid for the structured writer
// ---------------------------------------------------------------------------
struct GridInfo {
    int  nx, ny, nz;             // number of nodes in each direction
    float ox, oy, oz;             // grid origin (corner)
    float dx, dy, dz;             // cell spacing
};

// ===========================================================================
// (A) Unstructured point-cloud writer
// ===========================================================================
inline bool WriteVTKPointCloud(const std::string&                filename,
                                const std::vector<PointSolution>& pts,
                                bool                              hasExact = false)
{
    std::ofstream f(filename);
    if (!f.is_open()) return false;
    f.precision(8);

    const size_t N = pts.size();

    // ----- header -----------------------------------------------------------
    f << "# vtk DataFile Version 3.0\n"
         "WoSt Poisson solution – point cloud\n"
         "ASCII\n"
         "DATASET UNSTRUCTURED_GRID\n";

    // ----- geometry ---------------------------------------------------------
    f << "POINTS " << N << " float\n";
    for (const auto& p : pts)
        f << p.pos.x << ' ' << p.pos.y << ' ' << p.pos.z << '\n';

    // One VTK_VERTEX cell per point (cell type = 1).
    f << "CELLS " << N << ' ' << (N * 2) << '\n';
    for (size_t i = 0; i < N; ++i)
        f << "1 " << i << '\n';

    f << "CELL_TYPES " << N << '\n';
    for (size_t i = 0; i < N; ++i)
        f << "1\n";   // VTK_VERTEX

    // ----- point data -------------------------------------------------------
    f << "POINT_DATA " << N << '\n';

    // solution
    f << "SCALARS solution float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& p : pts) f << p.value << '\n';

    // standard error
    f << "SCALARS std_error float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& p : pts) f << p.stdErr << '\n';

    // mean walk steps
    f << "SCALARS mean_steps float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& p : pts) f << p.meanSteps << '\n';

    // optional exact solution + absolute error
    if (hasExact) {
        f << "SCALARS exact float 1\n"
             "LOOKUP_TABLE default\n";
        for (const auto& p : pts) f << p.exact << '\n';

        f << "SCALARS abs_error float 1\n"
             "LOOKUP_TABLE default\n";
        for (const auto& p : pts) f << std::abs(p.value - p.exact) << '\n';
    }

    return f.good();
}

// ===========================================================================
// (B) Structured-points grid writer
//
// 'grid' has nx*ny*nz entries in C order: [iz][iy][ix] (x varies fastest,
// matching VTK STRUCTURED_POINTS ordering).
// Invalid points (outside domain) should have value = NaN.
// ===========================================================================
struct GridPoint {
    float value;      // NaN  if outside domain
    float stdErr;
    float meanSteps;
    float exact;      // optional
    bool  valid;      // false if outside domain
};

inline bool WriteVTKStructuredPoints(const std::string&           filename,
                                      const GridInfo&              gi,
                                      const std::vector<GridPoint>& grid,
                                      bool                         hasExact = false)
{
    if ((int)grid.size() != gi.nx * gi.ny * gi.nz) return false;

    std::ofstream f(filename);
    if (!f.is_open()) return false;
    f.precision(8);

    const size_t N = grid.size();

    // ----- header -----------------------------------------------------------
    f << "# vtk DataFile Version 3.0\n"
         "WoSt Poisson solution – structured grid\n"
         "ASCII\n"
         "DATASET STRUCTURED_POINTS\n";

    f << "DIMENSIONS " << gi.nx << ' ' << gi.ny << ' ' << gi.nz << '\n';
    f << "ORIGIN "     << gi.ox << ' ' << gi.oy << ' ' << gi.oz << '\n';
    f << "SPACING "    << gi.dx << ' ' << gi.dy << ' ' << gi.dz << '\n';

    // ----- point data -------------------------------------------------------
    f << "POINT_DATA " << N << '\n';

    // solution (NaN for invalid points → ParaView masks them automatically)
    f << "SCALARS solution float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& g : grid)
        f << (g.valid ? g.value : std::numeric_limits<float>::quiet_NaN()) << '\n';

    // validity mask (1 = inside domain, 0 = outside)
    f << "SCALARS is_valid float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& g : grid)
        f << (g.valid ? 1.f : 0.f) << '\n';

    // standard error
    f << "SCALARS std_error float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& g : grid)
        f << (g.valid ? g.stdErr : 0.f) << '\n';

    // mean steps
    f << "SCALARS mean_steps float 1\n"
         "LOOKUP_TABLE default\n";
    for (const auto& g : grid)
        f << (g.valid ? g.meanSteps : 0.f) << '\n';

    // optional exact + error
    if (hasExact) {
        f << "SCALARS exact float 1\n"
             "LOOKUP_TABLE default\n";
        for (const auto& g : grid)
            f << (g.valid ? g.exact : 0.f) << '\n';

        f << "SCALARS abs_error float 1\n"
             "LOOKUP_TABLE default\n";
        for (const auto& g : grid)
            f << (g.valid ? std::abs(g.value - g.exact) : 0.f) << '\n';
    }

    return f.good();
}

#endif