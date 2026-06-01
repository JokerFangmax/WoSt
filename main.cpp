#include "src/WoStGeometryBackend.hpp"
#include "src/CubeOuterBoundary.hpp"
#include "src/WoStKernel.hpp"
#include "src/utils.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <sstream>
#include <string>
#include <vector>

#ifdef _OPENMP
#  include <omp.h>
#endif

using namespace wost;

namespace {

struct CliOptions {
    std::string mode = "all";
    std::string objFile = "./spot/spot_triangulated.obj";
    int numQueryPoints = 20000;
    int gridRes = 48;
    int numThreads = 0;
    uint64_t seed = 12345;
    float cubeHalfExtent = 1.0f;
};

struct BenchmarkMetrics {
    std::string benchmarkName;
    std::string meshName;
    int numQueryPoints = 0;
    int validPoints = 0;
    int walksPerPoint = 0;
    float epsilon = 0.f;
    int maxSteps = 0;
    int numThreads = 1;
    double elapsedSeconds = 0.0;
    double pointsPerSecond = 0.0;
    double walksPerSecond = 0.0;
    double rmse = 0.0;
    double mae = 0.0;
    double maxAbsError = 0.0;
    double meanStdError = 0.0;
    double meanSteps = 0.0;
    int divergedCount = 0;
    double meanSamplesUsed = 0.0;
};

struct GeometryMetrics {
    std::string benchmarkName;
    std::string meshName;
    std::string backendName;
    uint32_t triangleCount = 0;
    int numQueries = 0;
    int numThreads = 1;
    double elapsedSeconds = 0.0;
    double queriesPerSecond = 0.0;
    double checksum = 0.0;
};

std::string CsvEscape(const std::string& s) {
    if (s.find_first_of(",\"\n\r") == std::string::npos) return s;
    std::string out = "\"";
    for (char c : s) {
        if (c == '"') out += "\"\"";
        else out += c;
    }
    out += '"';
    return out;
}

uint64_t SplitMix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ull;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
    return x ^ (x >> 31);
}

uint32_t SeedFor(uint64_t baseSeed, uint64_t index, uint64_t stream = 0) {
    uint64_t mixed = SplitMix64(baseSeed ^ (index * 0xD1B54A32D192ED03ull) ^ stream);
    uint32_t seed = static_cast<uint32_t>(mixed & 0xffffffffu);
    return seed == 0 ? 1u : seed;
}

float LinearExact(const vec3& p) {
    return p.x + p.y + p.z;
}

vec3 RandomPointInCube(FastRNG& rng, float L) {
    return {
        rng.randFloat() * 2.0f * L - L,
        rng.randFloat() * 2.0f * L - L,
        rng.randFloat() * 2.0f * L - L
    };
}

std::vector<vec3> GenerateQueryPoints(int count, float L, uint64_t seed) {
    std::vector<vec3> points;
    points.reserve(std::max(0, count));
    FastRNG rng(SeedFor(seed, 0, 0xA11CEu));
    for (int i = 0; i < count; ++i) {
        points.push_back(RandomPointInCube(rng, L));
    }
    return points;
}

int CurrentThreadCount() {
#ifdef _OPENMP
    return omp_get_max_threads();
#else
    return 1;
#endif
}

std::string ResolveObjPath(const std::string& requested) {
    namespace fs = std::filesystem;
    if (fs::exists(requested)) return requested;

    const fs::path p(requested);
    if (p.is_relative()) {
        fs::path parentPath = fs::path("..") / p;
        if (fs::exists(parentPath)) return parentPath.string();
    }

    const fs::path defaultRoot = fs::path("spot") / "spot_triangulated.obj";
    if (fs::exists(defaultRoot)) return defaultRoot.string();

    const fs::path defaultFromBuild = fs::path("..") / "spot" / "spot_triangulated.obj";
    if (fs::exists(defaultFromBuild)) return defaultFromBuild.string();

    return requested;
}

void PrintUsage(const char* exe) {
    std::cout
        << "Usage: " << exe << " [--mode convergence|epsilon|grid|adaptive|threads|geometry|all] "
        << "[--obj path] [--queries N] [--grid N] [--threads N] [--seed N] [--cube L]\n";
}

bool ParseArgs(int argc, char** argv, CliOptions& opts) {
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        auto needValue = [&](const std::string& name) -> const char* {
            if (i + 1 >= argc) {
                std::cerr << "Missing value for " << name << "\n";
                return nullptr;
            }
            return argv[++i];
        };

        if (arg == "--help" || arg == "-h") {
            PrintUsage(argv[0]);
            return false;
        } else if (arg == "--mode") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.mode = v;
        } else if (arg == "--obj") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.objFile = v;
        } else if (arg == "--queries") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.numQueryPoints = std::max(1, std::stoi(v));
        } else if (arg == "--grid") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.gridRes = std::max(2, std::stoi(v));
        } else if (arg == "--threads") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.numThreads = std::max(1, std::stoi(v));
        } else if (arg == "--seed") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.seed = static_cast<uint64_t>(std::stoull(v));
        } else if (arg == "--cube") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.cubeHalfExtent = std::max(1e-4f, std::stof(v));
        } else {
            std::cerr << "Unknown argument: " << arg << "\n";
            PrintUsage(argv[0]);
            return false;
        }
    }
    return true;
}

void AppendBenchmarkCsv(const BenchmarkMetrics& m) {
    namespace fs = std::filesystem;
    fs::create_directories("results");
    const fs::path csvPath = fs::path("results") / "benchmark_summary.csv";
    const bool writeHeader = !fs::exists(csvPath) || fs::file_size(csvPath) == 0;

    std::ofstream out(csvPath, std::ios::app);
    if (!out.is_open()) {
        std::cerr << "Failed to open " << csvPath.string() << " for writing\n";
        return;
    }

    if (writeHeader) {
        out << "benchmark_name,mesh_name,num_query_points,valid_points,walks_per_point,"
            << "epsilon,max_steps,num_threads,elapsed_seconds,points_per_second,"
            << "walks_per_second,rmse,mae,max_abs_error,mean_std_error,mean_steps,"
            << "diverged_count,mean_samples_used\n";
    }

    out << CsvEscape(m.benchmarkName) << ','
        << CsvEscape(m.meshName) << ','
        << m.numQueryPoints << ','
        << m.validPoints << ','
        << m.walksPerPoint << ','
        << std::setprecision(9) << m.epsilon << ','
        << m.maxSteps << ','
        << m.numThreads << ','
        << std::setprecision(12) << m.elapsedSeconds << ','
        << m.pointsPerSecond << ','
        << m.walksPerSecond << ','
        << m.rmse << ','
        << m.mae << ','
        << m.maxAbsError << ','
        << m.meanStdError << ','
        << m.meanSteps << ','
        << m.divergedCount << ','
        << m.meanSamplesUsed << '\n';
}

void AppendGeometryCsv(const GeometryMetrics& m) {
    namespace fs = std::filesystem;
    fs::create_directories("results");
    const fs::path csvPath = fs::path("results") / "geometry_benchmark.csv";
    const bool writeHeader = !fs::exists(csvPath) || fs::file_size(csvPath) == 0;

    std::ofstream out(csvPath, std::ios::app);
    if (!out.is_open()) {
        std::cerr << "Failed to open " << csvPath.string() << " for writing\n";
        return;
    }

    if (writeHeader) {
        out << "benchmark_name,mesh_name,backend_name,triangle_count,num_queries,"
            << "num_threads,elapsed_seconds,queries_per_second,checksum\n";
    }

    out << CsvEscape(m.benchmarkName) << ','
        << CsvEscape(m.meshName) << ','
        << CsvEscape(m.backendName) << ','
        << m.triangleCount << ','
        << m.numQueries << ','
        << m.numThreads << ','
        << std::setprecision(12) << m.elapsedSeconds << ','
        << m.queriesPerSecond << ','
        << m.checksum << '\n';
}

void PrintMetrics(const BenchmarkMetrics& m) {
    std::cout << "\n=== " << m.benchmarkName << " ===\n"
              << "mesh: " << m.meshName << "\n"
              << "valid points: " << m.validPoints << " / " << m.numQueryPoints << "\n"
              << "walks_per_point: " << m.walksPerPoint
              << "  epsilon: " << m.epsilon
              << "  max_steps: " << m.maxSteps << "\n"
              << "elapsed_seconds: " << m.elapsedSeconds << "\n"
              << "points_per_second: " << m.pointsPerSecond << "\n"
              << "walks_per_second: " << m.walksPerSecond << "\n"
              << "RMSE: " << m.rmse
              << "  MAE: " << m.mae
              << "  max_abs_error: " << m.maxAbsError << "\n"
              << "mean_std_error: " << m.meanStdError
              << "  mean_steps: " << m.meanSteps
              << "  mean_samples_used: " << m.meanSamplesUsed << "\n"
              << "diverged_count: " << m.divergedCount << "\n";
}

void PrintGeometryMetrics(const GeometryMetrics& m) {
    std::cout << "\n=== " << m.benchmarkName << " / " << m.backendName << " ===\n"
              << "mesh: " << m.meshName << "\n"
              << "triangles: " << m.triangleCount << "\n"
              << "queries: " << m.numQueries << "\n"
              << "threads: " << m.numThreads << "\n"
              << "elapsed_seconds: " << m.elapsedSeconds << "\n"
              << "queries_per_second: " << m.queriesPerSecond << "\n"
              << "checksum: " << m.checksum << "\n";
}

BenchmarkMetrics AccumulateMetrics(const std::string& benchmarkName,
                                   const std::string& meshName,
                                   int numQueryPoints,
                                   const WoStParams& params,
                                   double elapsedSeconds,
                                   const std::vector<PointSolution>& solutions,
                                   const std::vector<char>& validFlags,
                                   const std::vector<char>& divergedFlags) {
    BenchmarkMetrics m;
    m.benchmarkName = benchmarkName;
    m.meshName = meshName;
    m.numQueryPoints = numQueryPoints;
    m.walksPerPoint = params.adaptiveSampling ? params.maxSamples : params.numSamples;
    m.epsilon = params.eps;
    m.maxSteps = params.maxSteps;
    m.numThreads = CurrentThreadCount();
    m.elapsedSeconds = elapsedSeconds;

    double sumSq = 0.0;
    double sumAbs = 0.0;
    double sumStdErr = 0.0;
    double sumSteps = 0.0;
    double sumSamples = 0.0;
    double totalSamples = 0.0;

    for (size_t i = 0; i < solutions.size(); ++i) {
        if (!validFlags[i]) continue;
        const PointSolution& s = solutions[i];
        const double err = static_cast<double>(s.value) - static_cast<double>(s.exact);
        const double absErr = std::abs(err);
        sumSq += err * err;
        sumAbs += absErr;
        m.maxAbsError = std::max(m.maxAbsError, absErr);
        sumStdErr += s.stdErr;
        sumSteps += s.meanSteps;
        sumSamples += s.samplesUsed;
        totalSamples += s.samplesUsed;
        ++m.validPoints;
        if (divergedFlags[i]) ++m.divergedCount;
    }

    if (m.validPoints > 0) {
        const double invN = 1.0 / static_cast<double>(m.validPoints);
        m.rmse = std::sqrt(sumSq * invN);
        m.mae = sumAbs * invN;
        m.meanStdError = sumStdErr * invN;
        m.meanSteps = sumSteps * invN;
        m.meanSamplesUsed = sumSamples * invN;
    }

    if (elapsedSeconds > 0.0) {
        m.pointsPerSecond = static_cast<double>(numQueryPoints) / elapsedSeconds;
        m.walksPerSecond = totalSamples / elapsedSeconds;
    }

    return m;
}

BenchmarkMetrics RunPointBenchmark(const WoStKernel& kernel,
                                   const std::string& meshName,
                                   const std::string& benchmarkName,
                                   int numQueryPoints,
                                   const WoStParams& params,
                                   uint64_t baseSeed,
                                   float L,
                                   bool writePointCloud = false) {
    const auto queries = GenerateQueryPoints(numQueryPoints, L, baseSeed);
    std::vector<PointSolution> solutions(numQueryPoints);
    std::vector<char> validFlags(numQueryPoints, 0);
    std::vector<char> divergedFlags(numQueryPoints, 0);

    const DirichletFn gInner = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    const DirichletFn gOuter = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    const NeumannPredFn noNeumann = [](const BoundaryPoint&) { return false; };
    const NeumannFn zeroNeumann = [](const BoundaryPoint&) { return 0.0f; };
    const SourceFn zeroSource = [](const vec3&) { return 0.0f; };

    const auto t0 = std::chrono::high_resolution_clock::now();

#pragma omp parallel for schedule(dynamic, 64)
    for (int i = 0; i < numQueryPoints; ++i) {
        const vec3 point = queries[i];
        if (!kernel.InDomain(point)) continue;

        WoStParams pointParams = params;
        pointParams.seed = SeedFor(baseSeed, static_cast<uint64_t>(i), 0xBEEFu);
        WalkResult r = kernel.SolvePoisson(point, gInner, noNeumann, zeroNeumann, gOuter, zeroSource, pointParams);

        PointSolution ps;
        ps.pos = point;
        ps.value = r.value;
        ps.stdErr = r.stdErr;
        ps.meanSteps = r.meanSteps;
        ps.samplesUsed = r.samplesUsed;
        ps.exact = LinearExact(point);
        solutions[i] = ps;
        validFlags[i] = 1;
        divergedFlags[i] = r.anyDiverged ? 1 : 0;
    }

    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    BenchmarkMetrics metrics = AccumulateMetrics(
        benchmarkName, meshName, numQueryPoints, params, elapsed, solutions, validFlags, divergedFlags);

    PrintMetrics(metrics);
    AppendBenchmarkCsv(metrics);

    if (writePointCloud) {
        std::vector<PointSolution> compact;
        compact.reserve(metrics.validPoints);
        for (int i = 0; i < numQueryPoints; ++i) {
            if (validFlags[i]) compact.push_back(solutions[i]);
        }
        if (WriteVTKPointCloud("results/linear_dirichlet_pointcloud.vtk", compact, true)) {
            std::cout << "Wrote results/linear_dirichlet_pointcloud.vtk\n";
        }
    }

    return metrics;
}

BenchmarkMetrics RunGridBenchmark(const WoStKernel& kernel,
                                  const std::string& meshName,
                                  const std::string& benchmarkName,
                                  int gridRes,
                                  const WoStParams& params,
                                  uint64_t baseSeed,
                                  float L,
                                  const std::string& vtkPath) {
    GridInfo gi;
    gi.nx = gridRes;
    gi.ny = gridRes;
    gi.nz = gridRes;
    gi.ox = -L;
    gi.oy = -L;
    gi.oz = -L;
    gi.dx = (2.0f * L) / static_cast<float>(gridRes - 1);
    gi.dy = gi.dx;
    gi.dz = gi.dx;

    const int totalPoints = gi.nx * gi.ny * gi.nz;
    std::vector<GridPoint> grid(totalPoints);
    std::vector<PointSolution> solutions(totalPoints);
    std::vector<char> validFlags(totalPoints, 0);
    std::vector<char> divergedFlags(totalPoints, 0);

    const DirichletFn gInner = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    const DirichletFn gOuter = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    const NeumannPredFn noNeumann = [](const BoundaryPoint&) { return false; };
    const NeumannFn zeroNeumann = [](const BoundaryPoint&) { return 0.0f; };
    const SourceFn zeroSource = [](const vec3&) { return 0.0f; };

    const auto t0 = std::chrono::high_resolution_clock::now();

#pragma omp parallel for schedule(dynamic, 32)
    for (int idx = 0; idx < totalPoints; ++idx) {
        const int ix = idx % gi.nx;
        const int iy = (idx / gi.nx) % gi.ny;
        const int iz = idx / (gi.nx * gi.ny);
        const vec3 point = {
            gi.ox + gi.dx * static_cast<float>(ix),
            gi.oy + gi.dy * static_cast<float>(iy),
            gi.oz + gi.dz * static_cast<float>(iz)
        };

        GridPoint gp;
        if (kernel.InDomain(point)) {
            WoStParams pointParams = params;
            pointParams.seed = SeedFor(baseSeed, static_cast<uint64_t>(idx), 0xC0FFEEu);
            WalkResult r = kernel.SolvePoisson(point, gInner, noNeumann, zeroNeumann, gOuter, zeroSource, pointParams);

            gp.value = r.value;
            gp.stdErr = r.stdErr;
            gp.meanSteps = r.meanSteps;
            gp.samplesUsed = r.samplesUsed;
            gp.exact = LinearExact(point);
            gp.valid = true;

            PointSolution ps;
            ps.pos = point;
            ps.value = r.value;
            ps.stdErr = r.stdErr;
            ps.meanSteps = r.meanSteps;
            ps.samplesUsed = r.samplesUsed;
            ps.exact = gp.exact;
            solutions[idx] = ps;
            validFlags[idx] = 1;
            divergedFlags[idx] = r.anyDiverged ? 1 : 0;
        }
        grid[idx] = gp;
    }

    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    BenchmarkMetrics metrics = AccumulateMetrics(
        benchmarkName, meshName, totalPoints, params, elapsed, solutions, validFlags, divergedFlags);

    PrintMetrics(metrics);
    AppendBenchmarkCsv(metrics);

    if (WriteVTKStructuredPoints(vtkPath, gi, grid, true)) {
        std::cout << "Wrote " << vtkPath << "\n";
    } else {
        std::cerr << "Failed to write " << vtkPath << "\n";
    }

    return metrics;
}

WoStParams BaseLinearParams() {
    WoStParams p;
    p.numSamples = 256;
    p.maxSteps = 512;
    p.eps = 1e-4f;
    p.adaptiveSampling = false;
    return p;
}

vec3 ClosestPointOnTriangleLocal(const vec3& p, const vec3& a, const vec3& b, const vec3& c) {
    const vec3 ab = sub(b, a);
    const vec3 ac = sub(c, a);
    const vec3 ap = sub(p, a);
    const float d1 = dot3(ab, ap);
    const float d2 = dot3(ac, ap);
    if (d1 <= 0.f && d2 <= 0.f) return a;

    const vec3 bp = sub(p, b);
    const float d3 = dot3(ab, bp);
    const float d4 = dot3(ac, bp);
    if (d3 >= 0.f && d4 <= d3) return b;

    const float vc = d1 * d4 - d3 * d2;
    if (vc <= 0.f && d1 >= 0.f && d3 <= 0.f) {
        const float v = d1 / (d1 - d3);
        return add(a, scale(ab, v));
    }

    const vec3 cp = sub(p, c);
    const float d5 = dot3(ab, cp);
    const float d6 = dot3(ac, cp);
    if (d6 >= 0.f && d5 <= d6) return c;

    const float vb = d5 * d2 - d1 * d6;
    if (vb <= 0.f && d2 >= 0.f && d6 <= 0.f) {
        const float w = d2 / (d2 - d6);
        return add(a, scale(ac, w));
    }

    const float va = d3 * d6 - d5 * d4;
    if (va <= 0.f && (d4 - d3) >= 0.f && (d5 - d6) >= 0.f) {
        const float w = (d4 - d3) / ((d4 - d3) + (d5 - d6));
        return add(b, scale(sub(c, b), w));
    }

    const float denom = 1.f / (va + vb + vc);
    const float v = vb * denom;
    const float w = vc * denom;
    return add(a, add(scale(ab, v), scale(ac, w)));
}

float BruteForceBoundaryDistance(const WoStGeometryBackend& geometry, const vec3& p) {
    const vec4* verts = geometry.Vertices();
    const uint32_t triCount = geometry.TriangleCount();
    float bestD2 = std::numeric_limits<float>::max();

    for (uint32_t i = 0; i < triCount; ++i) {
        const vec3 a(verts[i * 3 + 0]);
        const vec3 b(verts[i * 3 + 1]);
        const vec3 c(verts[i * 3 + 2]);
        const vec3 q = ClosestPointOnTriangleLocal(p, a, b, c);
        bestD2 = std::min(bestD2, dist2(p, q));
    }

    return std::sqrt(bestD2);
}

GeometryMetrics RunGeometryDistanceBenchmark(const WoStGeometryBackend& geometry,
                                             const std::string& meshName,
                                             const std::string& backendName,
                                             int numQueries,
                                             uint64_t seed,
                                             float L) {
    const std::vector<vec3> queries = GenerateQueryPoints(numQueries, L, seed);
    std::vector<float> distances(numQueries, 0.f);

    const auto t0 = std::chrono::high_resolution_clock::now();

    if (backendName == "tiny_bvh") {
#pragma omp parallel for schedule(dynamic, 128)
        for (int i = 0; i < numQueries; ++i) {
            distances[i] = geometry.FastBoundaryDistance(queries[i]);
        }
    } else {
#pragma omp parallel for schedule(dynamic, 8)
        for (int i = 0; i < numQueries; ++i) {
            distances[i] = BruteForceBoundaryDistance(geometry, queries[i]);
        }
    }

    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    GeometryMetrics m;
    m.benchmarkName = "geometry_distance";
    m.meshName = meshName;
    m.backendName = backendName;
    m.triangleCount = geometry.TriangleCount();
    m.numQueries = numQueries;
    m.numThreads = CurrentThreadCount();
    m.elapsedSeconds = elapsed;
    m.queriesPerSecond = elapsed > 0.0 ? static_cast<double>(numQueries) / elapsed : 0.0;
    m.checksum = std::accumulate(distances.begin(), distances.end(), 0.0);

    PrintGeometryMetrics(m);
    AppendGeometryCsv(m);
    return m;
}

void RunConvergence(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    for (int M : {16, 64, 256, 1024}) {
        WoStParams p = BaseLinearParams();
        p.numSamples = M;
        RunPointBenchmark(kernel, meshName, "convergence", opts.numQueryPoints, p,
                          opts.seed ^ 0xC011CEu, opts.cubeHalfExtent, M == 256);
    }
}

void RunEpsilonSweep(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    for (float eps : {1e-2f, 1e-3f, 1e-4f, 1e-5f}) {
        WoStParams p = BaseLinearParams();
        p.numSamples = 256;
        p.eps = eps;
        RunPointBenchmark(kernel, meshName, "epsilon", opts.numQueryPoints, p,
                          opts.seed ^ 0xE95110u, opts.cubeHalfExtent);
    }
}

void RunGrid(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    namespace fs = std::filesystem;
    fs::create_directories("results");
    WoStParams p = BaseLinearParams();
    p.numSamples = 256;
    RunGridBenchmark(kernel, meshName, "linear_dirichlet_grid", opts.gridRes, p, opts.seed,
                     opts.cubeHalfExtent, "results/linear_dirichlet_grid.vtk");
}

void RunAdaptive(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    namespace fs = std::filesystem;
    fs::create_directories("results");

    WoStParams fixed = BaseLinearParams();
    fixed.numSamples = 1024;
    RunPointBenchmark(kernel, meshName, "adaptive_fixed", opts.numQueryPoints, fixed,
                      opts.seed ^ 0xADA9715u, opts.cubeHalfExtent);

    WoStParams adaptive = BaseLinearParams();
    adaptive.adaptiveSampling = true;
    adaptive.numSamples = 1024;
    adaptive.minSamples = 32;
    adaptive.maxSamples = 1024;
    adaptive.batchSize = 32;
    adaptive.targetStdErr = 1e-3f;
    RunPointBenchmark(kernel, meshName, "adaptive", opts.numQueryPoints, adaptive,
                      opts.seed ^ 0xADA9715u, opts.cubeHalfExtent);

    RunGridBenchmark(kernel, meshName, "adaptive_grid", opts.gridRes, adaptive,
                     opts.seed ^ 0x6A1Du, opts.cubeHalfExtent, "results/adaptive_sampling_grid.vtk");
}

std::vector<int> ThreadSweepValues(int requestedMaxThreads) {
    const int maxThreads = std::max(1, requestedMaxThreads > 0 ? requestedMaxThreads : CurrentThreadCount());
    std::vector<int> values;
    for (int t = 1; t <= maxThreads; t *= 2) {
        values.push_back(t);
    }
    if (values.empty() || values.back() != maxThreads) {
        values.push_back(maxThreads);
    }
    values.erase(std::unique(values.begin(), values.end()), values.end());
    return values;
}

void RunThreadScaling(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    WoStParams p = BaseLinearParams();
    p.numSamples = 256;

    for (int threads : ThreadSweepValues(opts.numThreads)) {
#ifdef _OPENMP
        omp_set_num_threads(threads);
#endif
        RunPointBenchmark(kernel, meshName, "thread_scaling", opts.numQueryPoints, p,
                          opts.seed ^ 0x71EADu, opts.cubeHalfExtent);
    }
}

void RunGeometryBenchmark(const WoStGeometryBackend& interior,
                          const CliOptions& opts,
                          const std::string& meshName) {
    namespace fs = std::filesystem;
    fs::create_directories("results");

    const int geometryQueries = std::max(200, std::min(opts.numQueryPoints, 5000));
    RunGeometryDistanceBenchmark(interior, meshName, "tiny_bvh", geometryQueries,
                                 opts.seed ^ 0xBEE5u, opts.cubeHalfExtent);

    const uint64_t bruteWork = static_cast<uint64_t>(geometryQueries) *
                               static_cast<uint64_t>(std::max(1u, interior.TriangleCount()));
    if (bruteWork > 250000000ull) {
        std::cout << "\nSkipping brute_force distance benchmark because "
                  << geometryQueries << " queries * " << interior.TriangleCount()
                  << " triangles would be too slow. Re-run with fewer --queries "
                  << "if you need the exact brute-force data point.\n";
        return;
    }

    RunGeometryDistanceBenchmark(interior, meshName, "brute_force", geometryQueries,
                                 opts.seed ^ 0xBEE5u, opts.cubeHalfExtent);
}

} // namespace

int main(int argc, char** argv) {
    CliOptions opts;
    if (!ParseArgs(argc, argv, opts)) return 1;

    opts.objFile = ResolveObjPath(opts.objFile);

#ifdef _OPENMP
    if (opts.numThreads > 0) {
        omp_set_num_threads(opts.numThreads);
    }
#else
    if (opts.numThreads > 1) {
        std::cerr << "This build does not have OpenMP enabled; running single-threaded.\n";
    }
#endif

    const std::string mode = opts.mode;
    if (mode != "convergence" && mode != "epsilon" && mode != "grid" &&
        mode != "adaptive" && mode != "threads" && mode != "geometry" && mode != "all") {
        std::cerr << "Unknown mode: " << mode << "\n";
        PrintUsage(argv[0]);
        return 1;
    }

    std::cout << "WoSt linear Dirichlet benchmark\n"
              << "mode: " << mode << "\n"
              << "obj: " << opts.objFile << "\n"
              << "query points: " << opts.numQueryPoints << "\n"
              << "grid: " << opts.gridRes << "^3\n"
              << "cube half extent: " << opts.cubeHalfExtent << "\n"
              << "threads: " << CurrentThreadCount() << "\n"
              << "seed: " << opts.seed << "\n";

    WoStGeometryBackend interior(opts.objFile);
    CubeOuterBoundary exterior({-opts.cubeHalfExtent, -opts.cubeHalfExtent, -opts.cubeHalfExtent},
                               { opts.cubeHalfExtent,  opts.cubeHalfExtent,  opts.cubeHalfExtent});
    WoStKernel kernel(interior, exterior);

    if (mode == "convergence" || mode == "all") {
        RunConvergence(kernel, opts, opts.objFile);
    }
    if (mode == "epsilon" || mode == "all") {
        RunEpsilonSweep(kernel, opts, opts.objFile);
    }
    if (mode == "grid" || mode == "all") {
        RunGrid(kernel, opts, opts.objFile);
    }
    if (mode == "adaptive" || mode == "all") {
        RunAdaptive(kernel, opts, opts.objFile);
    }
    if (mode == "threads" || mode == "all") {
        RunThreadScaling(kernel, opts, opts.objFile);
    }
    if (mode == "geometry" || mode == "all") {
        RunGeometryBenchmark(interior, opts, opts.objFile);
    }

    std::cout << "\nBenchmark outputs written under results/.\n";
    return 0;
}
