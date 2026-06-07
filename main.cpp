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
#include <stdexcept>
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
    int minSamples = 64;
    int maxSamples = 1024;
    int batchSize = 32;
    float targetRSE = 0.05f;
    float rseEps = 1e-3f;
    float lazyRefineDistance = 0.0f;
    float lazySuspiciousRatio = 0.0f;
    vec3 demoPoint = {0.05f, 0.02f, 0.08f};
    int walks = 256;
    float epsilon = 1e-4f;
    std::string boundaryMode = "dirichlet";
    std::string traceOut = "results/live_trace.csv";
    std::string summaryOut = "results/live_demo_summary.csv";
    std::string outPath = "";
    std::string csvPath = "";
    std::string pointsIn = "";
    int traceWalks = 8;
    float biasThreshold = 2.0f;
    int pilotSamples = 32;
    float targetStdError = 0.005f;
    bool useAntithetic = false;
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

struct ExperimentMetrics {
    std::string experimentName;
    std::string methodName;
    std::string meshName;
    uint64_t seed = 0;
    int numQueryPoints = 0;
    int validPoints = 0;
    int walksPerPoint = 0;
    float epsilon = 0.f;
    int minSamples = 0;
    int maxSamples = 0;
    int batchSize = 0;
    float targetRSE = 0.f;
    double elapsedSeconds = 0.0;
    double rmse = 0.0;
    double mae = 0.0;
    double meanRelativeError = 0.0;
    double meanStdError = 0.0;
    double meanSampleVariance = 0.0;
    double meanSamplesUsed = 0.0;
    double medianSamplesUsed = 0.0;
    int minSamplesUsed = 0;
    int maxSamplesUsed = 0;
    double meanSteps = 0.0;
    int divergedCount = 0;
    uint64_t starQueries = 0;
    uint64_t fastOnlyStarQueries = 0;
    uint64_t exactStarQueries = 0;
    double refinementRatio = 0.0;
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

struct BoundarySetup {
    DirichletFn gInner;
    DirichletFn gOuter;
    NeumannPredFn isInnerNeumann;
    NeumannFn hInner;
    SourceFn source;
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

BoundarySetup MakeLinearDirichletProblem() {
    BoundarySetup b;
    b.gInner = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    b.gOuter = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    b.isInnerNeumann = [](const BoundaryPoint&) { return false; };
    b.hInner = [](const BoundaryPoint&) { return 0.0f; };
    b.source = [](const vec3&) { return 0.0f; };
    return b;
}

BoundarySetup MakeLinearInnerNeumannProblem() {
    BoundarySetup b;
    b.gInner = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    b.gOuter = [](const BoundaryPoint& bp) { return LinearExact(bp.position); };
    b.isInnerNeumann = [](const BoundaryPoint&) { return true; };
    b.hInner = [](const BoundaryPoint& bp) {
        const vec3 grad(1.0f, 1.0f, 1.0f);
        return dot3(grad, bp.normal);
    };
    b.source = [](const vec3&) { return 0.0f; };
    return b;
}

BoundarySetup BoundaryFromMode(const std::string& mode);

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

std::vector<vec3> ReadPointListCsv(const std::string& path) {
    std::vector<vec3> points;
    std::ifstream in(path);
    if (!in.is_open()) {
        std::cerr << "Failed to open point list: " << path << "\n";
        return points;
    }
    std::string line;
    if (!std::getline(in, line)) return points;

    std::vector<std::string> headers;
    {
        std::stringstream ss(line);
        std::string token;
        while (std::getline(ss, token, ',')) headers.push_back(token);
    }
    int ix = -1, iy = -1, iz = -1;
    for (int i = 0; i < static_cast<int>(headers.size()); ++i) {
        if (headers[i] == "x") ix = i;
        else if (headers[i] == "y") iy = i;
        else if (headers[i] == "z") iz = i;
    }
    if (ix < 0 || iy < 0 || iz < 0) {
        std::cerr << "Point list must contain x,y,z columns: " << path << "\n";
        return points;
    }

    while (std::getline(in, line)) {
        if (line.empty()) continue;
        std::vector<std::string> cols;
        std::stringstream ss(line);
        std::string token;
        while (std::getline(ss, token, ',')) cols.push_back(token);
        const int need = std::max(ix, std::max(iy, iz));
        if (static_cast<int>(cols.size()) <= need) continue;
        try {
            points.push_back({std::stof(cols[ix]), std::stof(cols[iy]), std::stof(cols[iz])});
        } catch (...) {
            continue;
        }
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
        << "Usage: " << exe << " [--mode convergence|epsilon|grid|adaptive|neumann|threads|geometry|case|"
        << "adaptive_compare|antithetic|lazy|epsilon_extrapolation|neumann_sanity|optimization|"
        << "demo_point|bias_detector|variance_adaptive|points|point_bias|all] "
        << "[--obj path] [--queries N] [--grid N] [--threads N] [--seed N] [--cube L]\n"
        << "Optimization knobs: [--min-samples N] [--max-samples N] [--batch-size N] "
        << "[--target-rse X] [--rse-eps X] [--lazy-threshold X] [--lazy-ratio X]\n"
        << "Demo/diagnostic knobs: [--point X Y Z] [--walks N] [--epsilon X] "
        << "[--boundary dirichlet|neumann] [--trace-out path] [--summary-out path] "
        << "[--out path] [--csv path] [--trace-walks N] [--bias-threshold X] "
        << "[--pilot-samples N] [--target-std-error X] [--points-in path] [--antithetic]\n";
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
        } else if (arg == "--min-samples") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.minSamples = std::max(1, std::stoi(v));
        } else if (arg == "--max-samples") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.maxSamples = std::max(1, std::stoi(v));
        } else if (arg == "--batch-size") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.batchSize = std::max(1, std::stoi(v));
        } else if (arg == "--target-rse") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.targetRSE = std::max(1e-6f, std::stof(v));
        } else if (arg == "--rse-eps") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.rseEps = std::max(1e-12f, std::stof(v));
        } else if (arg == "--lazy-threshold") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.lazyRefineDistance = std::max(0.0f, std::stof(v));
        } else if (arg == "--lazy-ratio") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.lazySuspiciousRatio = std::max(0.0f, std::stof(v));
        } else if (arg == "--point") {
            const char* x = needValue(arg);
            if (!x) return false;
            const char* y = needValue(arg);
            if (!y) return false;
            const char* z = needValue(arg);
            if (!z) return false;
            opts.demoPoint = {std::stof(x), std::stof(y), std::stof(z)};
        } else if (arg == "--walks") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.walks = std::max(1, std::stoi(v));
        } else if (arg == "--epsilon") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.epsilon = std::max(1e-8f, std::stof(v));
        } else if (arg == "--boundary") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.boundaryMode = v;
            if (opts.boundaryMode != "dirichlet" && opts.boundaryMode != "neumann") {
                std::cerr << "--boundary must be dirichlet or neumann\n";
                return false;
            }
        } else if (arg == "--trace-out") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.traceOut = v;
        } else if (arg == "--summary-out") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.summaryOut = v;
        } else if (arg == "--out") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.outPath = v;
        } else if (arg == "--csv") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.csvPath = v;
        } else if (arg == "--points-in") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.pointsIn = v;
        } else if (arg == "--trace-walks") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.traceWalks = std::max(0, std::stoi(v));
        } else if (arg == "--bias-threshold") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.biasThreshold = std::max(0.0f, std::stof(v));
        } else if (arg == "--pilot-samples") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.pilotSamples = std::max(1, std::stoi(v));
        } else if (arg == "--target-std-error") {
            const char* v = needValue(arg);
            if (!v) return false;
            opts.targetStdError = std::max(1e-8f, std::stof(v));
        } else if (arg == "--antithetic") {
            opts.useAntithetic = true;
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

void AppendExperimentCsv(const ExperimentMetrics& m) {
    namespace fs = std::filesystem;
    fs::create_directories("experiments");
    const fs::path csvPath = fs::path("experiments") / "optimization_summary.csv";
    const bool writeHeader = !fs::exists(csvPath) || fs::file_size(csvPath) == 0;

    std::ofstream out(csvPath, std::ios::app);
    if (!out.is_open()) {
        std::cerr << "Failed to open " << csvPath.string() << " for writing\n";
        return;
    }

    if (writeHeader) {
        out << "experiment,method,mesh,seed,num_query_points,valid_points,walks_per_point,"
            << "epsilon,min_samples,max_samples,batch_size,target_rse,elapsed_seconds,"
            << "rmse,mae,mean_relative_error,mean_std_error,mean_sample_variance,"
            << "mean_samples_used,median_samples_used,min_samples_used,max_samples_used,"
            << "mean_steps,diverged_count,star_queries,fast_only_star_queries,"
            << "exact_star_queries,refinement_ratio\n";
    }

    out << CsvEscape(m.experimentName) << ','
        << CsvEscape(m.methodName) << ','
        << CsvEscape(m.meshName) << ','
        << m.seed << ','
        << m.numQueryPoints << ','
        << m.validPoints << ','
        << m.walksPerPoint << ','
        << std::setprecision(9) << m.epsilon << ','
        << m.minSamples << ','
        << m.maxSamples << ','
        << m.batchSize << ','
        << m.targetRSE << ','
        << std::setprecision(12) << m.elapsedSeconds << ','
        << m.rmse << ','
        << m.mae << ','
        << m.meanRelativeError << ','
        << m.meanStdError << ','
        << m.meanSampleVariance << ','
        << m.meanSamplesUsed << ','
        << m.medianSamplesUsed << ','
        << m.minSamplesUsed << ','
        << m.maxSamplesUsed << ','
        << m.meanSteps << ','
        << m.divergedCount << ','
        << m.starQueries << ','
        << m.fastOnlyStarQueries << ','
        << m.exactStarQueries << ','
        << m.refinementRatio << '\n';
}

void AppendExperimentPointCsv(const std::string& experimentName,
                              const std::string& methodName,
                              uint64_t seed,
                              const std::vector<PointSolution>& solutions,
                              const std::vector<char>& validFlags) {
    namespace fs = std::filesystem;
    fs::create_directories("experiments");
    const fs::path csvPath = fs::path("experiments") / "optimization_points.csv";
    const bool writeHeader = !fs::exists(csvPath) || fs::file_size(csvPath) == 0;

    std::ofstream out(csvPath, std::ios::app);
    if (!out.is_open()) {
        std::cerr << "Failed to open " << csvPath.string() << " for writing\n";
        return;
    }

    if (writeHeader) {
        out << "experiment,method,seed,point_index,x,y,z,value,exact,abs_error,"
            << "std_error,sample_variance,samples_used,mean_steps,star_queries,"
            << "fast_only_star_queries,exact_star_queries\n";
    }

    for (size_t i = 0; i < solutions.size(); ++i) {
        if (!validFlags[i]) continue;
        const auto& s = solutions[i];
        out << CsvEscape(experimentName) << ','
            << CsvEscape(methodName) << ','
            << seed << ','
            << i << ','
            << std::setprecision(9) << s.pos.x << ','
            << s.pos.y << ','
            << s.pos.z << ','
            << s.value << ','
            << s.exact << ','
            << std::abs(s.value - s.exact) << ','
            << s.stdErr << ','
            << s.sampleVariance << ','
            << s.samplesUsed << ','
            << s.meanSteps << ','
            << s.starQueries << ','
            << s.fastOnlyStarQueries << ','
            << s.exactStarQueries << '\n';
    }
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
                                   const BoundarySetup& boundary,
                                   bool writePointCloud = false,
                                   const std::string& pointCloudPath = "results/linear_dirichlet_pointcloud.vtk") {
    const auto queries = GenerateQueryPoints(numQueryPoints, L, baseSeed);
    std::vector<PointSolution> solutions(numQueryPoints);
    std::vector<char> validFlags(numQueryPoints, 0);
    std::vector<char> divergedFlags(numQueryPoints, 0);

    const auto t0 = std::chrono::high_resolution_clock::now();

#pragma omp parallel for schedule(dynamic, 64)
    for (int i = 0; i < numQueryPoints; ++i) {
        const vec3 point = queries[i];
        if (!kernel.InDomain(point)) continue;

        WoStParams pointParams = params;
        pointParams.seed = SeedFor(baseSeed, static_cast<uint64_t>(i), 0xBEEFu);
        WalkResult r = kernel.SolvePoisson(point,
                                           boundary.gInner,
                                           boundary.isInnerNeumann,
                                           boundary.hInner,
                                           boundary.gOuter,
                                           boundary.source,
                                           pointParams);

        PointSolution ps;
        ps.pos = point;
        ps.value = r.value;
        ps.stdErr = r.stdErr;
        ps.sampleVariance = r.sampleVariance;
        ps.meanSteps = r.meanSteps;
        ps.samplesUsed = r.samplesUsed;
        ps.exact = LinearExact(point);
        ps.starQueries = r.starQueries;
        ps.fastOnlyStarQueries = r.fastOnlyStarQueries;
        ps.exactStarQueries = r.exactStarQueries;
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
        if (WriteVTKPointCloud(pointCloudPath, compact, true)) {
            std::cout << "Wrote " << pointCloudPath << "\n";
        }
    }

    return metrics;
}

void WritePointListResultCsv(const std::string& path,
                             const std::string& meshName,
                             const std::string& boundaryMode,
                             const WoStParams& params,
                             uint64_t baseSeed,
                             const std::vector<PointSolution>& solutions,
                             const std::vector<char>& validFlags,
                             const std::vector<char>& divergedFlags) {
    namespace fs = std::filesystem;
    fs::path outPath(path.empty() ? "results/point_list_results.csv" : path);
    fs::create_directories(outPath.parent_path());
    std::ofstream out(outPath);
    if (!out.is_open()) {
        std::cerr << "Failed to write point results: " << outPath.string() << "\n";
        return;
    }
    out << "mesh,boundary,seed,point_index,x,y,z,value,exact,abs_error,std_error,"
        << "sample_variance,samples_used,mean_steps,diverged,epsilon,walks_per_point,"
        << "star_queries,fast_only_star_queries,exact_star_queries,is_valid\n";
    for (size_t i = 0; i < solutions.size(); ++i) {
        const PointSolution& s = solutions[i];
        const bool valid = validFlags[i] != 0;
        out << CsvEscape(meshName) << ','
            << CsvEscape(boundaryMode) << ','
            << baseSeed << ','
            << i << ','
            << std::setprecision(9) << s.pos.x << ','
            << s.pos.y << ','
            << s.pos.z << ',';
        if (valid) {
            out << s.value << ','
                << s.exact << ','
                << std::abs(s.value - s.exact) << ','
                << s.stdErr << ','
                << s.sampleVariance << ','
                << s.samplesUsed << ','
                << s.meanSteps << ','
                << (divergedFlags[i] ? 1 : 0) << ','
                << params.eps << ','
                << params.numSamples << ','
                << s.starQueries << ','
                << s.fastOnlyStarQueries << ','
                << s.exactStarQueries << ",1\n";
        } else {
            out << ",,,,,,,,"
                << params.eps << ','
                << params.numSamples
                << ",,,0\n";
        }
    }
    std::cout << "Wrote " << outPath.string() << "\n";
}

void AppendPointListSummaryCsv(const std::string& path,
                               const BenchmarkMetrics& m,
                               const std::string& runLabel) {
    if (path.empty()) return;
    namespace fs = std::filesystem;
    fs::path outPath(path);
    fs::create_directories(outPath.parent_path());
    const bool writeHeader = !fs::exists(outPath) || fs::file_size(outPath) == 0;
    std::ofstream out(outPath, std::ios::app);
    if (!out.is_open()) {
        std::cerr << "Failed to write summary CSV: " << outPath.string() << "\n";
        return;
    }
    if (writeHeader) {
        out << "run_label,benchmark_name,mesh_name,num_query_points,valid_points,walks_per_point,"
            << "epsilon,max_steps,num_threads,elapsed_seconds,rmse,mae,max_abs_error,"
            << "mean_std_error,mean_steps,diverged_count,mean_samples_used\n";
    }
    out << CsvEscape(runLabel) << ','
        << CsvEscape(m.benchmarkName) << ','
        << CsvEscape(m.meshName) << ','
        << m.numQueryPoints << ','
        << m.validPoints << ','
        << m.walksPerPoint << ','
        << std::setprecision(9) << m.epsilon << ','
        << m.maxSteps << ','
        << m.numThreads << ','
        << m.elapsedSeconds << ','
        << m.rmse << ','
        << m.mae << ','
        << m.maxAbsError << ','
        << m.meanStdError << ','
        << m.meanSteps << ','
        << m.divergedCount << ','
        << m.meanSamplesUsed << '\n';
}

BenchmarkMetrics RunPointListBenchmark(const WoStKernel& kernel,
                                       const CliOptions& opts,
                                       const std::string& meshName) {
    const std::vector<vec3> queries = ReadPointListCsv(opts.pointsIn);
    if (queries.empty()) {
        throw std::runtime_error("No points loaded for --mode points");
    }
    const BoundarySetup boundary = BoundaryFromMode(opts.boundaryMode);
    WoStParams params;
    params.numSamples = 256;
    params.maxSteps = 512;
    params.eps = 1e-4f;
    params.adaptiveSampling = false;
    params.numSamples = opts.walks;
    params.eps = opts.epsilon;
    params.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;
    params.useAntitheticSampling = opts.useAntithetic;

    const int n = static_cast<int>(queries.size());
    std::vector<PointSolution> solutions(n);
    std::vector<char> validFlags(n, 0);
    std::vector<char> divergedFlags(n, 0);
    for (int i = 0; i < n; ++i) {
        solutions[i].pos = queries[i];
        solutions[i].exact = LinearExact(queries[i]);
    }

    const auto t0 = std::chrono::high_resolution_clock::now();
#pragma omp parallel for schedule(dynamic, 32)
    for (int i = 0; i < n; ++i) {
        const vec3 point = queries[i];
        if (!kernel.InDomain(point)) continue;
        WoStParams pointParams = params;
        pointParams.seed = SeedFor(opts.seed, static_cast<uint64_t>(i), 0xB17B1ull);
        WalkResult r = kernel.SolvePoisson(point,
                                           boundary.gInner,
                                           boundary.isInnerNeumann,
                                           boundary.hInner,
                                           boundary.gOuter,
                                           boundary.source,
                                           pointParams);
        PointSolution ps;
        ps.pos = point;
        ps.value = r.value;
        ps.stdErr = r.stdErr;
        ps.sampleVariance = r.sampleVariance;
        ps.meanSteps = r.meanSteps;
        ps.samplesUsed = r.samplesUsed;
        ps.exact = LinearExact(point);
        ps.starQueries = r.starQueries;
        ps.fastOnlyStarQueries = r.fastOnlyStarQueries;
        ps.exactStarQueries = r.exactStarQueries;
        solutions[i] = ps;
        validFlags[i] = 1;
        divergedFlags[i] = r.anyDiverged ? 1 : 0;
    }
    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();
    BenchmarkMetrics metrics = AccumulateMetrics(
        "point_list", meshName, n, params, elapsed, solutions, validFlags, divergedFlags);
    PrintMetrics(metrics);
    WritePointListResultCsv(opts.outPath, meshName, opts.boundaryMode, params, opts.seed,
                            solutions, validFlags, divergedFlags);
    AppendPointListSummaryCsv(opts.csvPath, metrics, "point_list");
    return metrics;
}

void RunPointListBias(const WoStKernel& kernel,
                      const CliOptions& opts,
                      const std::string& meshName) {
    const std::vector<vec3> queries = ReadPointListCsv(opts.pointsIn);
    if (queries.empty()) {
        throw std::runtime_error("No points loaded for --mode point_bias");
    }
    const BoundarySetup boundary = BoundaryFromMode(opts.boundaryMode);
    WoStParams base;
    base.numSamples = 256;
    base.maxSteps = 512;
    base.eps = 1e-4f;
    base.adaptiveSampling = false;
    base.numSamples = opts.walks;
    base.eps = opts.epsilon;
    base.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;
    base.useAntitheticSampling = opts.useAntithetic;

    struct BiasPointResult {
        vec3 pos;
        bool valid = false;
        bool divergedEps = false;
        bool divergedHalf = false;
        float valueEps = 0.f;
        float valueHalf = 0.f;
        float stdErrEps = 0.f;
        float stdErrHalf = 0.f;
        float varEps = 0.f;
        float varHalf = 0.f;
        float stepsEps = 0.f;
        float stepsHalf = 0.f;
        int samplesEps = 0;
        int samplesHalf = 0;
    };

    const int n = static_cast<int>(queries.size());
    std::vector<BiasPointResult> results(n);
    const auto t0 = std::chrono::high_resolution_clock::now();
#pragma omp parallel for schedule(dynamic, 16)
    for (int i = 0; i < n; ++i) {
        const vec3 point = queries[i];
        BiasPointResult out;
        out.pos = point;
        if (kernel.InDomain(point)) {
            WoStParams p1 = base;
            p1.seed = SeedFor(opts.seed, static_cast<uint64_t>(i), 0xB1A5u);
            WalkResult r1 = kernel.SolvePoisson(point,
                                                boundary.gInner,
                                                boundary.isInnerNeumann,
                                                boundary.hInner,
                                                boundary.gOuter,
                                                boundary.source,
                                                p1);
            WoStParams p2 = base;
            p2.eps = opts.epsilon * 0.5f;
            p2.seed = SeedFor(opts.seed, static_cast<uint64_t>(i), 0xB1A6u);
            WalkResult r2 = kernel.SolvePoisson(point,
                                                boundary.gInner,
                                                boundary.isInnerNeumann,
                                                boundary.hInner,
                                                boundary.gOuter,
                                                boundary.source,
                                                p2);
            out.valid = true;
            out.divergedEps = r1.anyDiverged;
            out.divergedHalf = r2.anyDiverged;
            out.valueEps = r1.value;
            out.valueHalf = r2.value;
            out.stdErrEps = r1.stdErr;
            out.stdErrHalf = r2.stdErr;
            out.varEps = r1.sampleVariance;
            out.varHalf = r2.sampleVariance;
            out.stepsEps = r1.meanSteps;
            out.stepsHalf = r2.meanSteps;
            out.samplesEps = r1.samplesUsed;
            out.samplesHalf = r2.samplesUsed;
        }
        results[i] = out;
    }
    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    namespace fs = std::filesystem;
    fs::path outPath(opts.outPath.empty() ? "results/point_bias.csv" : opts.outPath);
    fs::create_directories(outPath.parent_path());
    std::ofstream out(outPath);
    if (!out.is_open()) {
        std::cerr << "Failed to write point bias CSV: " << outPath.string() << "\n";
        return;
    }
    out << "mesh,boundary,seed,point_index,x,y,z,exact,epsilon,epsilon_half,"
        << "value_epsilon,value_epsilon_half,bias_indicator,normalized_bias,"
        << "abs_error_epsilon,abs_error_epsilon_half,std_error_epsilon,std_error_epsilon_half,"
        << "sample_variance_epsilon,sample_variance_epsilon_half,mean_steps_epsilon,"
        << "mean_steps_epsilon_half,samples_epsilon,samples_epsilon_half,diverged_epsilon,"
        << "diverged_epsilon_half,is_valid\n";

    int valid = 0;
    double sumBias = 0.0, sumSq1 = 0.0, sumSq2 = 0.0, sumSteps = 0.0;
    for (int i = 0; i < n; ++i) {
        const auto& r = results[i];
        const float exact = LinearExact(r.pos);
        out << CsvEscape(meshName) << ','
            << CsvEscape(opts.boundaryMode) << ','
            << opts.seed << ','
            << i << ','
            << std::setprecision(9) << r.pos.x << ','
            << r.pos.y << ','
            << r.pos.z << ','
            << exact << ','
            << opts.epsilon << ','
            << opts.epsilon * 0.5f << ',';
        if (r.valid) {
            const float bias = std::abs(r.valueEps - r.valueHalf);
            const float normBias = bias / (r.stdErrEps + r.stdErrHalf + 1e-6f);
            const float err1 = std::abs(r.valueEps - exact);
            const float err2 = std::abs(r.valueHalf - exact);
            out << r.valueEps << ','
                << r.valueHalf << ','
                << bias << ','
                << normBias << ','
                << err1 << ','
                << err2 << ','
                << r.stdErrEps << ','
                << r.stdErrHalf << ','
                << r.varEps << ','
                << r.varHalf << ','
                << r.stepsEps << ','
                << r.stepsHalf << ','
                << r.samplesEps << ','
                << r.samplesHalf << ','
                << (r.divergedEps ? 1 : 0) << ','
                << (r.divergedHalf ? 1 : 0) << ",1\n";
            ++valid;
            sumBias += bias;
            sumSq1 += static_cast<double>(r.valueEps - exact) * static_cast<double>(r.valueEps - exact);
            sumSq2 += static_cast<double>(r.valueHalf - exact) * static_cast<double>(r.valueHalf - exact);
            sumSteps += r.stepsEps;
        } else {
            for (int c = 0; c < 16; ++c) out << ',';
            out << "0\n";
        }
    }
    std::cout << "\n=== point_bias ===\n"
              << "valid: " << valid << " / " << n << "\n"
              << "mean_bias: " << (valid ? sumBias / valid : 0.0)
              << "  rmse_epsilon: " << (valid ? std::sqrt(sumSq1 / valid) : 0.0)
              << "  rmse_epsilon_half: " << (valid ? std::sqrt(sumSq2 / valid) : 0.0)
              << "  mean_steps: " << (valid ? sumSteps / valid : 0.0)
              << "  elapsed_seconds: " << elapsed << "\n"
              << "Wrote " << outPath.string() << "\n";
}

ExperimentMetrics AccumulateExperimentMetrics(const std::string& experimentName,
                                              const std::string& methodName,
                                              const std::string& meshName,
                                              uint64_t seed,
                                              int numQueryPoints,
                                              const WoStParams& params,
                                              double elapsedSeconds,
                                              const std::vector<PointSolution>& solutions,
                                              const std::vector<char>& validFlags,
                                              const std::vector<char>& divergedFlags) {
    ExperimentMetrics m;
    m.experimentName = experimentName;
    m.methodName = methodName;
    m.meshName = meshName;
    m.seed = seed;
    m.numQueryPoints = numQueryPoints;
    m.walksPerPoint = params.adaptiveSampling ? params.maxSamples : params.numSamples;
    m.epsilon = params.eps;
    m.minSamples = params.minSamples;
    m.maxSamples = params.maxSamples;
    m.batchSize = params.batchSize;
    m.targetRSE = params.targetRSE;
    m.elapsedSeconds = elapsedSeconds;

    std::vector<int> sampleCounts;
    double sumSq = 0.0;
    double sumAbs = 0.0;
    double sumRel = 0.0;
    double sumStdErr = 0.0;
    double sumVar = 0.0;
    double sumSamples = 0.0;
    double sumSteps = 0.0;

    for (size_t i = 0; i < solutions.size(); ++i) {
        if (!validFlags[i]) continue;
        const PointSolution& s = solutions[i];
        const double err = static_cast<double>(s.value) - static_cast<double>(s.exact);
        const double absErr = std::abs(err);
        sumSq += err * err;
        sumAbs += absErr;
        sumRel += absErr / std::max(std::abs(static_cast<double>(s.exact)), 1e-6);
        sumStdErr += s.stdErr;
        sumVar += s.sampleVariance;
        sumSamples += s.samplesUsed;
        sumSteps += s.meanSteps;
        sampleCounts.push_back(s.samplesUsed);
        ++m.validPoints;
        if (divergedFlags[i]) ++m.divergedCount;
        m.starQueries += s.starQueries;
        m.fastOnlyStarQueries += s.fastOnlyStarQueries;
        m.exactStarQueries += s.exactStarQueries;
    }

    if (m.validPoints > 0) {
        const double invN = 1.0 / static_cast<double>(m.validPoints);
        m.rmse = std::sqrt(sumSq * invN);
        m.mae = sumAbs * invN;
        m.meanRelativeError = sumRel * invN;
        m.meanStdError = sumStdErr * invN;
        m.meanSampleVariance = sumVar * invN;
        m.meanSamplesUsed = sumSamples * invN;
        m.meanSteps = sumSteps * invN;

        std::sort(sampleCounts.begin(), sampleCounts.end());
        m.minSamplesUsed = sampleCounts.front();
        m.maxSamplesUsed = sampleCounts.back();
        const size_t mid = sampleCounts.size() / 2;
        m.medianSamplesUsed = sampleCounts.size() % 2
            ? static_cast<double>(sampleCounts[mid])
            : 0.5 * (sampleCounts[mid - 1] + sampleCounts[mid]);
    }

    if (m.starQueries > 0) {
        m.refinementRatio = static_cast<double>(m.exactStarQueries) /
                            static_cast<double>(m.starQueries);
    }

    return m;
}

ExperimentMetrics RunExperimentCase(const WoStKernel& kernel,
                                    const std::string& meshName,
                                    const std::string& experimentName,
                                    const std::string& methodName,
                                    int numQueryPoints,
                                    const WoStParams& params,
                                    uint64_t baseSeed,
                                    float L,
                                    const BoundarySetup& boundary,
                                    bool writePoints = false,
                                    const std::string& vtkPath = "") {
    const auto queries = GenerateQueryPoints(numQueryPoints, L, baseSeed);
    std::vector<PointSolution> solutions(numQueryPoints);
    std::vector<char> validFlags(numQueryPoints, 0);
    std::vector<char> divergedFlags(numQueryPoints, 0);

    const auto t0 = std::chrono::high_resolution_clock::now();

#pragma omp parallel for schedule(dynamic, 64)
    for (int i = 0; i < numQueryPoints; ++i) {
        const vec3 point = queries[i];
        if (!kernel.InDomain(point)) continue;

        WoStParams pointParams = params;
        pointParams.seed = SeedFor(baseSeed, static_cast<uint64_t>(i), 0xBEEFu);
        WalkResult r = kernel.SolvePoisson(point,
                                           boundary.gInner,
                                           boundary.isInnerNeumann,
                                           boundary.hInner,
                                           boundary.gOuter,
                                           boundary.source,
                                           pointParams);

        PointSolution ps;
        ps.pos = point;
        ps.value = r.value;
        ps.stdErr = r.stdErr;
        ps.sampleVariance = r.sampleVariance;
        ps.meanSteps = r.meanSteps;
        ps.samplesUsed = r.samplesUsed;
        ps.exact = LinearExact(point);
        ps.starQueries = r.starQueries;
        ps.fastOnlyStarQueries = r.fastOnlyStarQueries;
        ps.exactStarQueries = r.exactStarQueries;
        solutions[i] = ps;
        validFlags[i] = 1;
        divergedFlags[i] = r.anyDiverged ? 1 : 0;
    }

    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    ExperimentMetrics metrics = AccumulateExperimentMetrics(
        experimentName, methodName, meshName, baseSeed, numQueryPoints,
        params, elapsed, solutions, validFlags, divergedFlags);
    AppendExperimentCsv(metrics);
    if (writePoints) {
        AppendExperimentPointCsv(experimentName, methodName, baseSeed, solutions, validFlags);
    }

    if (!vtkPath.empty()) {
        std::vector<PointSolution> compact;
        compact.reserve(metrics.validPoints);
        for (int i = 0; i < numQueryPoints; ++i) {
            if (validFlags[i]) compact.push_back(solutions[i]);
        }
        if (WriteVTKPointCloud(vtkPath, compact, true)) {
            std::cout << "Wrote " << vtkPath << "\n";
        }
    }

    std::cout << "\n=== " << experimentName << " / " << methodName << " ===\n"
              << "seed: " << baseSeed << "  valid: " << metrics.validPoints
              << " / " << metrics.numQueryPoints << "\n"
              << "RMSE: " << metrics.rmse << "  MAE: " << metrics.mae
              << "  rel_error: " << metrics.meanRelativeError << "\n"
              << "mean samples: " << metrics.meanSamplesUsed
              << "  median/min/max: " << metrics.medianSamplesUsed << " / "
              << metrics.minSamplesUsed << " / " << metrics.maxSamplesUsed << "\n"
              << "mean variance: " << metrics.meanSampleVariance
              << "  mean std_error: " << metrics.meanStdError << "\n"
              << "refinement ratio: " << metrics.refinementRatio
              << "  elapsed_seconds: " << metrics.elapsedSeconds << "\n";

    return metrics;
}

BenchmarkMetrics RunGridBenchmark(const WoStKernel& kernel,
                                  const std::string& meshName,
                                  const std::string& benchmarkName,
                                  int gridRes,
                                  const WoStParams& params,
                                  uint64_t baseSeed,
                                  float L,
                                  const BoundarySetup& boundary,
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
            WalkResult r = kernel.SolvePoisson(point,
                                               boundary.gInner,
                                               boundary.isInnerNeumann,
                                               boundary.hInner,
                                               boundary.gOuter,
                                               boundary.source,
                                               pointParams);

            gp.value = r.value;
            gp.stdErr = r.stdErr;
            gp.sampleVariance = r.sampleVariance;
            gp.meanSteps = r.meanSteps;
            gp.samplesUsed = r.samplesUsed;
            gp.exact = LinearExact(point);
            gp.valid = true;

            PointSolution ps;
            ps.pos = point;
            ps.value = r.value;
            ps.stdErr = r.stdErr;
            ps.sampleVariance = r.sampleVariance;
            ps.meanSteps = r.meanSteps;
            ps.samplesUsed = r.samplesUsed;
            ps.exact = gp.exact;
            ps.starQueries = r.starQueries;
            ps.fastOnlyStarQueries = r.fastOnlyStarQueries;
            ps.exactStarQueries = r.exactStarQueries;
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
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    for (int M : {16, 64, 256, 1024}) {
        WoStParams p = BaseLinearParams();
        p.numSamples = M;
        RunPointBenchmark(kernel, meshName, "convergence", opts.numQueryPoints, p,
                          opts.seed ^ 0xC011CEu, opts.cubeHalfExtent, boundary, M == 256,
                          "results/linear_dirichlet_pointcloud.vtk");
    }
}

void RunEpsilonSweep(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    for (float eps : {1e-2f, 1e-3f, 1e-4f, 1e-5f}) {
        WoStParams p = BaseLinearParams();
        p.numSamples = 256;
        p.eps = eps;
        RunPointBenchmark(kernel, meshName, "epsilon", opts.numQueryPoints, p,
                          opts.seed ^ 0xE95110u, opts.cubeHalfExtent, boundary);
    }
}

void RunSingleCaseBenchmark(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    const BoundarySetup boundary = BoundaryFromMode(opts.boundaryMode);
    WoStParams p = BaseLinearParams();
    p.numSamples = opts.walks;
    p.eps = opts.epsilon;
    p.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;

    const std::string name = opts.boundaryMode == "neumann"
        ? "case_mixed_neumann"
        : "case_dirichlet";
    RunPointBenchmark(kernel, meshName, name, opts.numQueryPoints, p,
                      opts.seed ^ 0xCA5E0001u, opts.cubeHalfExtent, boundary);
}

void RunNeumannBenchmark(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    namespace fs = std::filesystem;
    fs::create_directories("results");

    const BoundarySetup boundary = MakeLinearInnerNeumannProblem();

    for (int M : {16, 64, 256, 1024}) {
        WoStParams p = BaseLinearParams();
        p.numSamples = M;
        p.maxSteps = 2048;
        RunPointBenchmark(kernel, meshName, "neumann_convergence", opts.numQueryPoints, p,
                          opts.seed ^ 0xA11CE2u, opts.cubeHalfExtent, boundary, M == 256,
                          "results/neumann_mixed_pointcloud.vtk");
    }

    for (float eps : {1e-2f, 1e-3f, 1e-4f, 1e-5f}) {
        WoStParams p = BaseLinearParams();
        p.numSamples = 256;
        p.maxSteps = 2048;
        p.eps = eps;
        RunPointBenchmark(kernel, meshName, "neumann_epsilon", opts.numQueryPoints, p,
                          opts.seed ^ 0x0E0001u, opts.cubeHalfExtent, boundary);
    }

    WoStParams gridParams = BaseLinearParams();
    gridParams.numSamples = 256;
    gridParams.maxSteps = 2048;
    RunGridBenchmark(kernel, meshName, "neumann_mixed_grid", opts.gridRes, gridParams,
                     opts.seed ^ 0x0E006Du, opts.cubeHalfExtent, boundary,
                     "results/neumann_mixed_grid.vtk");
}

void RunGrid(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    namespace fs = std::filesystem;
    fs::create_directories("results");
    WoStParams p = BaseLinearParams();
    p.numSamples = 256;
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    RunGridBenchmark(kernel, meshName, "linear_dirichlet_grid", opts.gridRes, p, opts.seed,
                     opts.cubeHalfExtent, boundary, "results/linear_dirichlet_grid.vtk");
}

void RunAdaptive(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    namespace fs = std::filesystem;
    fs::create_directories("results");

    WoStParams fixed = BaseLinearParams();
    fixed.numSamples = 1024;
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    RunPointBenchmark(kernel, meshName, "adaptive_fixed", opts.numQueryPoints, fixed,
                      opts.seed ^ 0xADA9715u, opts.cubeHalfExtent, boundary);

    WoStParams adaptive = BaseLinearParams();
    adaptive.adaptiveSampling = true;
    adaptive.numSamples = 1024;
    adaptive.minSamples = 32;
    adaptive.maxSamples = 1024;
    adaptive.batchSize = 32;
    adaptive.targetStdErr = 1e-3f;
    RunPointBenchmark(kernel, meshName, "adaptive", opts.numQueryPoints, adaptive,
                      opts.seed ^ 0xADA9715u, opts.cubeHalfExtent, boundary);

    RunGridBenchmark(kernel, meshName, "adaptive_grid", opts.gridRes, adaptive,
                     opts.seed ^ 0x6A1Du, opts.cubeHalfExtent, boundary, "results/adaptive_sampling_grid.vtk");
}

WoStParams ExperimentBaseParams(const CliOptions& opts) {
    WoStParams p = BaseLinearParams();
    p.numSamples = opts.maxSamples;
    p.minSamples = opts.minSamples;
    p.maxSamples = opts.maxSamples;
    p.batchSize = opts.batchSize;
    p.targetRSE = opts.targetRSE;
    p.rseEps = opts.rseEps;
    p.lazyRefineDistance = opts.lazyRefineDistance;
    p.lazySuspiciousRatio = opts.lazySuspiciousRatio;
    return p;
}

BoundarySetup BoundaryFromMode(const std::string& mode) {
    return mode == "neumann" ? MakeLinearInnerNeumannProblem() : MakeLinearDirichletProblem();
}

void EnsureParentDirectory(const std::string& path) {
    namespace fs = std::filesystem;
    const fs::path p(path);
    const fs::path parent = p.parent_path();
    if (!parent.empty()) fs::create_directories(parent);
}

void WriteTraceCsv(const std::string& path, const std::vector<WalkTraceRow>& rows) {
    EnsureParentDirectory(path);
    std::ofstream out(path);
    if (!out.is_open()) {
        std::cerr << "Failed to write trace CSV: " << path << "\n";
        return;
    }
    out << "walk_id,step_id,x,y,z,radius,event_type,boundary_type\n";
    out << std::setprecision(9);
    for (const auto& r : rows) {
        out << r.walkId << ',' << r.stepId << ','
            << r.pos.x << ',' << r.pos.y << ',' << r.pos.z << ','
            << r.radius << ',' << CsvEscape(r.eventType) << ','
            << CsvEscape(r.boundaryType) << '\n';
    }
}

void RunDemoPoint(const WoStKernel& kernel, const CliOptions& opts) {
    const BoundarySetup boundary = BoundaryFromMode(opts.boundaryMode);
    const vec3 point = opts.demoPoint;
    if (!kernel.InDomain(point)) {
        std::cerr << "demo_point query is outside the computational domain: "
                  << point.x << ", " << point.y << ", " << point.z << "\n";
        return;
    }

    WoStParams p = BaseLinearParams();
    p.numSamples = opts.walks;
    p.eps = opts.epsilon;
    p.seed = opts.seed;
    p.useAntitheticSampling = opts.useAntithetic;
    p.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;

    const auto t0 = std::chrono::high_resolution_clock::now();
    WalkResult r = kernel.SolvePoisson(point,
                                       boundary.gInner,
                                       boundary.isInnerNeumann,
                                       boundary.hInner,
                                       boundary.gOuter,
                                       boundary.source,
                                       p);
    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    const int traceWalks = std::min(opts.traceWalks, opts.walks);
    WoStParams traceParams = p;
    traceParams.numSamples = traceWalks;
    const std::vector<WalkTraceRow> trace = kernel.TraceWalks(point,
                                                              boundary.gInner,
                                                              boundary.isInnerNeumann,
                                                              boundary.hInner,
                                                              boundary.gOuter,
                                                              boundary.source,
                                                              traceParams,
                                                              traceWalks);
    WriteTraceCsv(opts.traceOut, trace);

    EnsureParentDirectory(opts.summaryOut);
    std::ofstream summary(opts.summaryOut);
    summary << "boundary,seed,walks,trace_walks,epsilon,estimated_value,exact_value,"
            << "absolute_error,standard_error,sample_variance,mean_steps,runtime_seconds,"
            << "samples_used,any_diverged\n";
    const float exact = LinearExact(point);
    summary << CsvEscape(opts.boundaryMode) << ','
            << opts.seed << ','
            << opts.walks << ','
            << traceWalks << ','
            << std::setprecision(9) << opts.epsilon << ','
            << r.value << ','
            << exact << ','
            << std::abs(r.value - exact) << ','
            << r.stdErr << ','
            << r.sampleVariance << ','
            << r.meanSteps << ','
            << std::setprecision(12) << elapsed << ','
            << r.samplesUsed << ','
            << (r.anyDiverged ? 1 : 0) << '\n';

    std::cout << "\n=== demo_point ===\n"
              << "boundary: " << opts.boundaryMode << "\n"
              << "point: (" << point.x << ", " << point.y << ", " << point.z << ")\n"
              << "estimate: " << r.value << "  exact: " << exact
              << "  abs_error: " << std::abs(r.value - exact) << "\n"
              << "std_error: " << r.stdErr << "  mean_steps: " << r.meanSteps
              << "  runtime_seconds: " << elapsed << "\n"
              << "wrote " << opts.traceOut << "\n"
              << "wrote " << opts.summaryOut << "\n";
}

struct BiasGridPoint {
    float solutionEps = 0.f;
    float solutionHalf = 0.f;
    float bias = 0.f;
    float normalizedBias = 0.f;
    float stdErrEps = 0.f;
    float stdErrHalf = 0.f;
    float meanStepsEps = 0.f;
    float meanStepsHalf = 0.f;
    float exact = 0.f;
    float absErrEps = 0.f;
    float absErrHalf = 0.f;
    bool valid = false;
};

bool WriteBiasVTK(const std::string& path, const GridInfo& gi, const std::vector<BiasGridPoint>& grid) {
    if (static_cast<int>(grid.size()) != gi.nx * gi.ny * gi.nz) return false;
    EnsureParentDirectory(path);
    std::ofstream f(path);
    if (!f.is_open()) return false;
    f.precision(8);
    f << "# vtk DataFile Version 3.0\n"
      << "WoSt boundary bias detector\n"
      << "ASCII\n"
      << "DATASET STRUCTURED_POINTS\n";
    f << "DIMENSIONS " << gi.nx << ' ' << gi.ny << ' ' << gi.nz << '\n';
    f << "ORIGIN " << gi.ox << ' ' << gi.oy << ' ' << gi.oz << '\n';
    f << "SPACING " << gi.dx << ' ' << gi.dy << ' ' << gi.dz << '\n';
    f << "POINT_DATA " << grid.size() << '\n';

    auto writeScalar = [&](const char* name, auto getter) {
        f << "SCALARS " << name << " float 1\nLOOKUP_TABLE default\n";
        for (const auto& g : grid) f << getter(g) << '\n';
    };
    const float nan = std::numeric_limits<float>::quiet_NaN();
    writeScalar("solution_epsilon", [&](const BiasGridPoint& g) { return g.valid ? g.solutionEps : nan; });
    writeScalar("solution_epsilon_half", [&](const BiasGridPoint& g) { return g.valid ? g.solutionHalf : nan; });
    writeScalar("bias_indicator", [&](const BiasGridPoint& g) { return g.valid ? g.bias : nan; });
    writeScalar("normalized_bias", [&](const BiasGridPoint& g) { return g.valid ? g.normalizedBias : nan; });
    writeScalar("std_error_epsilon", [&](const BiasGridPoint& g) { return g.valid ? g.stdErrEps : 0.f; });
    writeScalar("std_error_epsilon_half", [&](const BiasGridPoint& g) { return g.valid ? g.stdErrHalf : 0.f; });
    writeScalar("mean_steps_epsilon", [&](const BiasGridPoint& g) { return g.valid ? g.meanStepsEps : 0.f; });
    writeScalar("mean_steps_epsilon_half", [&](const BiasGridPoint& g) { return g.valid ? g.meanStepsHalf : 0.f; });
    writeScalar("exact", [&](const BiasGridPoint& g) { return g.valid ? g.exact : 0.f; });
    writeScalar("abs_error_epsilon", [&](const BiasGridPoint& g) { return g.valid ? g.absErrEps : 0.f; });
    writeScalar("abs_error_epsilon_half", [&](const BiasGridPoint& g) { return g.valid ? g.absErrHalf : 0.f; });
    writeScalar("is_valid", [&](const BiasGridPoint& g) { return g.valid ? 1.f : 0.f; });
    return f.good();
}

void RunBiasDetector(const WoStKernel& kernel, const CliOptions& opts) {
    const BoundarySetup boundary = BoundaryFromMode(opts.boundaryMode);
    const std::string vtkPath = opts.outPath.empty() ? "results/boundary_bias_detector.vtk" : opts.outPath;
    const std::string csvPath = opts.csvPath.empty() ? "results/boundary_bias_summary.csv" : opts.csvPath;

    GridInfo gi;
    gi.nx = opts.gridRes;
    gi.ny = opts.gridRes;
    gi.nz = opts.gridRes;
    gi.ox = -opts.cubeHalfExtent;
    gi.oy = -opts.cubeHalfExtent;
    gi.oz = -opts.cubeHalfExtent;
    gi.dx = (2.0f * opts.cubeHalfExtent) / static_cast<float>(opts.gridRes - 1);
    gi.dy = gi.dx;
    gi.dz = gi.dx;
    const int totalPoints = gi.nx * gi.ny * gi.nz;
    std::vector<BiasGridPoint> grid(totalPoints);

    WoStParams base = BaseLinearParams();
    base.numSamples = opts.walks;
    base.eps = opts.epsilon;
    base.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;

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
        if (!kernel.InDomain(point)) continue;

        WoStParams p1 = base;
        p1.seed = SeedFor(opts.seed, static_cast<uint64_t>(idx), 0xB1A5u);
        WalkResult r1 = kernel.SolvePoisson(point, boundary.gInner, boundary.isInnerNeumann,
                                            boundary.hInner, boundary.gOuter, boundary.source, p1);
        WoStParams p2 = p1;
        p2.eps = opts.epsilon * 0.5f;
        p2.seed = p1.seed;
        WalkResult r2 = kernel.SolvePoisson(point, boundary.gInner, boundary.isInnerNeumann,
                                            boundary.hInner, boundary.gOuter, boundary.source, p2);

        BiasGridPoint bg;
        bg.solutionEps = r1.value;
        bg.solutionHalf = r2.value;
        bg.bias = std::abs(r1.value - r2.value);
        bg.normalizedBias = bg.bias / (r1.stdErr + r2.stdErr + 1e-6f);
        bg.stdErrEps = r1.stdErr;
        bg.stdErrHalf = r2.stdErr;
        bg.meanStepsEps = r1.meanSteps;
        bg.meanStepsHalf = r2.meanSteps;
        bg.exact = LinearExact(point);
        bg.absErrEps = std::abs(r1.value - bg.exact);
        bg.absErrHalf = std::abs(r2.value - bg.exact);
        bg.valid = true;
        grid[idx] = bg;
    }
    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();

    int valid = 0;
    int highBias = 0;
    double sumBias = 0.0;
    double maxBias = 0.0;
    double sumNorm = 0.0;
    double sumSqEps = 0.0;
    double sumSqHalf = 0.0;
    std::vector<float> biasValues;
    std::vector<float> normalizedBiasValues;
    for (const auto& g : grid) {
        if (!g.valid) continue;
        ++valid;
        sumBias += g.bias;
        maxBias = std::max(maxBias, static_cast<double>(g.bias));
        sumNorm += g.normalizedBias;
        biasValues.push_back(g.bias);
        normalizedBiasValues.push_back(g.normalizedBias);
        sumSqEps += static_cast<double>(g.absErrEps) * g.absErrEps;
        sumSqHalf += static_cast<double>(g.absErrHalf) * g.absErrHalf;
        if (g.normalizedBias > opts.biasThreshold) ++highBias;
    }
    auto percentile = [](std::vector<float> values, double pct) -> double {
        if (values.empty()) return 0.0;
        std::sort(values.begin(), values.end());
        const double pos = (pct / 100.0) * static_cast<double>(values.size() - 1);
        const size_t lo = static_cast<size_t>(std::floor(pos));
        const size_t hi = static_cast<size_t>(std::ceil(pos));
        if (lo == hi) return values[lo];
        const double t = pos - static_cast<double>(lo);
        return (1.0 - t) * values[lo] + t * values[hi];
    };
    const double p95Bias = percentile(biasValues, 95.0);
    const double p95Norm = percentile(normalizedBiasValues, 95.0);
    const double maxNorm = normalizedBiasValues.empty()
        ? 0.0
        : *std::max_element(normalizedBiasValues.begin(), normalizedBiasValues.end());

    WriteBiasVTK(vtkPath, gi, grid);
    EnsureParentDirectory(csvPath);
    std::ofstream csv(csvPath);
    csv << "boundary,epsilon,epsilon_half,walks,grid,valid_points,mean_bias,max_bias,"
        << "p95_bias,mean_normalized_bias,max_normalized_bias,p95_normalized_bias,"
        << "high_bias_point_count,high_bias_ratio,warning_threshold_ratio,rmse_epsilon,"
        << "rmse_epsilon_half,runtime_seconds,bias_threshold\n";
    const double inv = valid > 0 ? 1.0 / static_cast<double>(valid) : 0.0;
    csv << CsvEscape(opts.boundaryMode) << ','
        << std::setprecision(9) << opts.epsilon << ','
        << opts.epsilon * 0.5f << ','
        << opts.walks << ','
        << opts.gridRes << ','
        << valid << ','
        << sumBias * inv << ','
        << maxBias << ','
        << p95Bias << ','
        << sumNorm * inv << ','
        << maxNorm << ','
        << p95Norm << ','
        << highBias << ','
        << (valid > 0 ? static_cast<double>(highBias) * inv : 0.0) << ','
        << (valid > 0 ? static_cast<double>(highBias) * inv : 0.0) << ','
        << (valid > 0 ? std::sqrt(sumSqEps * inv) : 0.0) << ','
        << (valid > 0 ? std::sqrt(sumSqHalf * inv) : 0.0) << ','
        << std::setprecision(12) << elapsed << ','
        << opts.biasThreshold << '\n';

    std::cout << "\n=== bias_detector ===\n"
              << "boundary: " << opts.boundaryMode
              << "  valid: " << valid << " / " << totalPoints << "\n"
              << "mean_bias: " << sumBias * inv
              << "  mean_normalized_bias: " << sumNorm * inv
              << "  high_bias_ratio: " << (valid > 0 ? static_cast<double>(highBias) * inv : 0.0) << "\n"
              << "wrote " << vtkPath << "\n"
              << "wrote " << csvPath << "\n";
}

struct VariancePointRow {
    int pointId = 0;
    vec3 pos{};
    float exact = 0.f;
    float value = 0.f;
    float absError = 0.f;
    float stdError = 0.f;
    float sampleVariance = 0.f;
    int predictedSamples = 0;
    int samplesUsed = 0;
    float meanSteps = 0.f;
    bool valid = false;
};

struct VarianceSummary {
    std::string method;
    int queries = 0;
    int validPoints = 0;
    float epsilon = 0.f;
    int pilotSamples = 0;
    int minSamples = 0;
    int maxSamples = 0;
    float targetStdError = 0.f;
    double rmse = 0.0;
    double mae = 0.0;
    double maxAbsError = 0.0;
    double meanStdError = 0.0;
    double meanSampleVariance = 0.0;
    double meanPredictedSamples = 0.0;
    double meanSamplesUsed = 0.0;
    double meanSteps = 0.0;
    double runtimeSeconds = 0.0;
};

void WriteVariancePointsCsv(const std::string& path, const std::vector<VariancePointRow>& rows) {
    EnsureParentDirectory(path);
    std::ofstream out(path);
    out << "point_id,x,y,z,exact,value,abs_error,std_error,sample_variance,"
        << "predicted_samples,samples_used,mean_steps,is_valid\n";
    out << std::setprecision(9);
    for (const auto& r : rows) {
        out << r.pointId << ','
            << r.pos.x << ',' << r.pos.y << ',' << r.pos.z << ','
            << r.exact << ',' << r.value << ',' << r.absError << ','
            << r.stdError << ',' << r.sampleVariance << ','
            << r.predictedSamples << ',' << r.samplesUsed << ','
            << r.meanSteps << ',' << (r.valid ? 1 : 0) << '\n';
    }
}

void WriteVarianceSummaryCsv(const std::string& path, const std::vector<VarianceSummary>& rows) {
    EnsureParentDirectory(path);
    std::ofstream out(path);
    out << "method,queries,valid_points,epsilon,pilot_samples,min_samples,max_samples,"
        << "target_std_error,rmse,mae,max_abs_error,mean_std_error,mean_sample_variance,"
        << "mean_predicted_samples,mean_samples_used,mean_steps,runtime_seconds\n";
    out << std::setprecision(12);
    for (const auto& s : rows) {
        out << CsvEscape(s.method) << ','
            << s.queries << ','
            << s.validPoints << ','
            << s.epsilon << ','
            << s.pilotSamples << ','
            << s.minSamples << ','
            << s.maxSamples << ','
            << s.targetStdError << ','
            << s.rmse << ','
            << s.mae << ','
            << s.maxAbsError << ','
            << s.meanStdError << ','
            << s.meanSampleVariance << ','
            << s.meanPredictedSamples << ','
            << s.meanSamplesUsed << ','
            << s.meanSteps << ','
            << s.runtimeSeconds << '\n';
    }
}

VarianceSummary AccumulateVarianceSummary(const std::string& method,
                                          const CliOptions& opts,
                                          int valid,
                                          double elapsed,
                                          const std::vector<VariancePointRow>& rows,
                                          float targetStdError) {
    VarianceSummary s;
    s.method = method;
    s.queries = opts.numQueryPoints;
    s.validPoints = valid;
    s.epsilon = opts.epsilon;
    s.pilotSamples = opts.pilotSamples;
    s.minSamples = opts.minSamples;
    s.maxSamples = opts.maxSamples;
    s.targetStdError = targetStdError;
    s.runtimeSeconds = elapsed;

    double sumSq = 0.0;
    double sumAbs = 0.0;
    double sumStd = 0.0;
    double sumVar = 0.0;
    double sumPred = 0.0;
    double sumUsed = 0.0;
    double sumSteps = 0.0;
    for (const auto& r : rows) {
        if (!r.valid) continue;
        sumSq += static_cast<double>(r.absError) * r.absError;
        sumAbs += r.absError;
        s.maxAbsError = std::max(s.maxAbsError, static_cast<double>(r.absError));
        sumStd += r.stdError;
        sumVar += r.sampleVariance;
        sumPred += r.predictedSamples;
        sumUsed += r.samplesUsed;
        sumSteps += r.meanSteps;
    }
    if (valid > 0) {
        const double inv = 1.0 / static_cast<double>(valid);
        s.rmse = std::sqrt(sumSq * inv);
        s.mae = sumAbs * inv;
        s.meanStdError = sumStd * inv;
        s.meanSampleVariance = sumVar * inv;
        s.meanPredictedSamples = sumPred * inv;
        s.meanSamplesUsed = sumUsed * inv;
        s.meanSteps = sumSteps * inv;
    }
    return s;
}

void RunVarianceAdaptiveMethod(const WoStKernel& kernel,
                               const CliOptions& opts,
                               const BoundarySetup& boundary,
                               const std::vector<vec3>& queries,
                               const std::string& method,
                               int fixedSamples,
                               float targetStdError,
                               bool writePoints,
                               const std::string& pointPath,
                               std::vector<VarianceSummary>& summaries) {
    const bool adaptive = fixedSamples <= 0;
    std::vector<VariancePointRow> rows(queries.size());
    int valid = 0;
    const auto t0 = std::chrono::high_resolution_clock::now();

#pragma omp parallel for schedule(dynamic, 64)
    for (int i = 0; i < static_cast<int>(queries.size()); ++i) {
        const vec3 point = queries[i];
        VariancePointRow row;
        row.pointId = i;
        row.pos = point;
        row.exact = LinearExact(point);
        if (!kernel.InDomain(point)) {
            rows[i] = row;
            continue;
        }

        int predicted = fixedSamples;
        uint32_t seed = SeedFor(opts.seed, static_cast<uint64_t>(i), 0xF00Du);
        if (adaptive) {
            WoStParams pilot = BaseLinearParams();
            pilot.numSamples = opts.pilotSamples;
            pilot.eps = opts.epsilon;
            pilot.seed = seed;
            pilot.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;
            WalkResult pilotResult = kernel.SolvePoisson(point, boundary.gInner, boundary.isInnerNeumann,
                                                         boundary.hInner, boundary.gOuter, boundary.source, pilot);
            const double denom = std::max(static_cast<double>(targetStdError) * targetStdError, 1e-12);
            predicted = static_cast<int>(std::ceil(static_cast<double>(pilotResult.sampleVariance) / denom));
            predicted = std::clamp(predicted, opts.minSamples, opts.maxSamples);
        }

        WoStParams p = BaseLinearParams();
        p.numSamples = predicted;
        p.eps = opts.epsilon;
        p.seed = seed;
        p.maxSteps = opts.boundaryMode == "neumann" ? 2048 : 512;
        p.useAntitheticSampling = opts.useAntithetic;
        WalkResult r = kernel.SolvePoisson(point, boundary.gInner, boundary.isInnerNeumann,
                                           boundary.hInner, boundary.gOuter, boundary.source, p);
        row.value = r.value;
        row.absError = std::abs(r.value - row.exact);
        row.stdError = r.stdErr;
        row.sampleVariance = r.sampleVariance;
        row.predictedSamples = predicted;
        row.samplesUsed = r.samplesUsed;
        row.meanSteps = r.meanSteps;
        row.valid = true;
        rows[i] = row;
    }

    const auto t1 = std::chrono::high_resolution_clock::now();
    const double elapsed = std::chrono::duration<double>(t1 - t0).count();
    for (const auto& r : rows) if (r.valid) ++valid;

    summaries.push_back(AccumulateVarianceSummary(method, opts, valid, elapsed, rows, targetStdError));
    if (writePoints) {
        WriteVariancePointsCsv(pointPath, rows);
    }

    const auto& s = summaries.back();
    std::cout << "\n=== variance_adaptive / " << method << " ===\n"
              << "valid: " << s.validPoints << " / " << s.queries
              << "  RMSE: " << s.rmse
              << "  mean_samples: " << s.meanSamplesUsed
              << "  runtime_seconds: " << s.runtimeSeconds << "\n";
}

void RunVarianceAdaptive(const WoStKernel& kernel, const CliOptions& opts) {
    const BoundarySetup boundary = BoundaryFromMode(opts.boundaryMode);
    const std::string pointsPath = opts.outPath.empty() ? "results/variance_adaptive_points.csv" : opts.outPath;
    const std::string summaryPath = opts.summaryOut == "results/live_demo_summary.csv"
        ? "results/variance_adaptive_summary.csv"
        : opts.summaryOut;
    const std::string comparisonPath = opts.csvPath.empty()
        ? "results/variance_adaptive_comparison.csv"
        : opts.csvPath;
    const std::vector<vec3> queries = GenerateQueryPoints(opts.numQueryPoints, opts.cubeHalfExtent, opts.seed ^ 0xA9A9u);
    std::vector<VarianceSummary> summaries;

    RunVarianceAdaptiveMethod(kernel, opts, boundary, queries, "fixed_256", 256, 0.0f, false, pointsPath, summaries);
    RunVarianceAdaptiveMethod(kernel, opts, boundary, queries, "fixed_512", 512, 0.0f, false, pointsPath, summaries);
    RunVarianceAdaptiveMethod(kernel, opts, boundary, queries, "fixed_1024", 1024, 0.0f, false, pointsPath, summaries);

    std::vector<float> taus = {0.003f, 0.005f, 0.008f};
    bool hasRequestedTau = false;
    for (float tau : taus) {
        if (std::abs(tau - opts.targetStdError) < 1e-7f) hasRequestedTau = true;
    }
    if (!hasRequestedTau) taus.push_back(opts.targetStdError);
    for (float tau : taus) {
        std::ostringstream method;
        method << "variance_adaptive_tau_" << std::fixed << std::setprecision(3) << tau;
        const bool writePoints = std::abs(tau - opts.targetStdError) < 1e-7f;
        RunVarianceAdaptiveMethod(kernel, opts, boundary, queries, method.str(), 0, tau,
                                  writePoints, pointsPath, summaries);
    }

    WriteVarianceSummaryCsv(summaryPath, summaries);
    WriteVarianceSummaryCsv(comparisonPath, summaries);
    std::cout << "wrote " << pointsPath << "\n"
              << "wrote " << summaryPath << "\n"
              << "wrote " << comparisonPath << "\n";
}

void RunAdaptiveComparison(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    for (int rep = 0; rep < 3; ++rep) {
        const uint64_t expSeed = opts.seed + static_cast<uint64_t>(rep) * 1009ull + 0xAD0000u;
        const bool writePoints = (rep == 0);

        WoStParams fixed = ExperimentBaseParams(opts);
        fixed.adaptiveSampling = false;
        fixed.numSamples = opts.maxSamples;
        RunExperimentCase(kernel, meshName, "adaptive_compare", "fixed",
                          opts.numQueryPoints, fixed, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);

        WoStParams oldAdaptive = ExperimentBaseParams(opts);
        oldAdaptive.adaptiveSampling = true;
        oldAdaptive.useRelativeStdErr = false;
        oldAdaptive.targetStdErr = 1e-3f;
        RunExperimentCase(kernel, meshName, "adaptive_compare", "old_absolute_stderr",
                          opts.numQueryPoints, oldAdaptive, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);

        WoStParams rseAdaptive = ExperimentBaseParams(opts);
        rseAdaptive.adaptiveSampling = true;
        rseAdaptive.useRelativeStdErr = true;
        RunExperimentCase(kernel, meshName, "adaptive_compare", "relative_stderr",
                          opts.numQueryPoints, rseAdaptive, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints,
                          rep == 0 ? "experiments/adaptive_relative_points.vtk" : "");
    }
}

void RunAntitheticComparison(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    for (int rep = 0; rep < 3; ++rep) {
        const uint64_t expSeed = opts.seed + static_cast<uint64_t>(rep) * 1009ull + 0xA771u;
        const bool writePoints = (rep == 0);

        WoStParams normal = ExperimentBaseParams(opts);
        normal.adaptiveSampling = false;
        normal.numSamples = opts.maxSamples;
        normal.useAntitheticSampling = false;
        RunExperimentCase(kernel, meshName, "antithetic_compare", "normal",
                          opts.numQueryPoints, normal, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);

        WoStParams anti = normal;
        anti.useAntitheticSampling = true;
        RunExperimentCase(kernel, meshName, "antithetic_compare", "antithetic",
                          opts.numQueryPoints, anti, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);
    }
}

void RunLazyRefinementComparison(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    const float baseThreshold = opts.lazyRefineDistance > 0.f ? opts.lazyRefineDistance : 2.0f * BaseLinearParams().eps;

    for (int rep = 0; rep < 3; ++rep) {
        const uint64_t expSeed = opts.seed + static_cast<uint64_t>(rep) * 1009ull + 0x1A2Bu;
        const bool writePoints = (rep == 0);

        WoStParams full = ExperimentBaseParams(opts);
        full.adaptiveSampling = false;
        full.numSamples = opts.maxSamples;
        full.useLazyStarRefinement = false;
        RunExperimentCase(kernel, meshName, "lazy_refinement", "full_exact",
                          opts.numQueryPoints, full, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);

        for (float mult : {1.0f, 4.0f, 16.0f}) {
            WoStParams lazy = full;
            lazy.useLazyStarRefinement = true;
            lazy.lazyRefineDistance = baseThreshold * mult;
            std::ostringstream name;
            name << "lazy_threshold_x" << static_cast<int>(mult);
            RunExperimentCase(kernel, meshName, "lazy_refinement", name.str(),
                              opts.numQueryPoints, lazy, expSeed, opts.cubeHalfExtent,
                              boundary, writePoints,
                              (rep == 0 && mult == 1.0f) ? "experiments/lazy_refinement_points.vtk" : "");
        }
    }
}

void RunEpsilonExtrapolation(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    const BoundarySetup boundary = MakeLinearDirichletProblem();
    for (int rep = 0; rep < 3; ++rep) {
        const uint64_t expSeed = opts.seed + static_cast<uint64_t>(rep) * 1009ull + 0xE95110u;
        const bool writePoints = (rep == 0);

        WoStParams eps = ExperimentBaseParams(opts);
        eps.adaptiveSampling = false;
        eps.numSamples = opts.maxSamples;
        eps.eps = 1e-2f;
        RunExperimentCase(kernel, meshName, "epsilon_extrapolation", "epsilon",
                          opts.numQueryPoints, eps, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);

        WoStParams half = eps;
        half.eps = eps.eps * 0.5f;
        RunExperimentCase(kernel, meshName, "epsilon_extrapolation", "epsilon_half",
                          opts.numQueryPoints, half, expSeed, opts.cubeHalfExtent,
                          boundary, writePoints);
    }
}

bool WriteSphereObj(const std::string& path, float radius, int slices, int stacks) {
    namespace fs = std::filesystem;
    fs::create_directories(fs::path(path).parent_path());
    std::ofstream out(path);
    if (!out.is_open()) return false;

    for (int j = 0; j <= stacks; ++j) {
        const float v = static_cast<float>(j) / static_cast<float>(stacks);
        const float theta = 3.14159265359f * v;
        const float z = radius * std::cos(theta);
        const float r = radius * std::sin(theta);
        for (int i = 0; i < slices; ++i) {
            const float u = static_cast<float>(i) / static_cast<float>(slices);
            const float phi = 6.28318530718f * u;
            out << "v " << r * std::cos(phi) << ' '
                << r * std::sin(phi) << ' ' << z << '\n';
        }
    }

    auto idx = [slices](int j, int i) {
        return j * slices + (i % slices) + 1;
    };

    for (int j = 0; j < stacks; ++j) {
        for (int i = 0; i < slices; ++i) {
            const int a = idx(j, i);
            const int b = idx(j, i + 1);
            const int c = idx(j + 1, i);
            const int d = idx(j + 1, i + 1);
            if (j > 0) out << "f " << a << ' ' << c << ' ' << b << '\n';
            if (j + 1 < stacks) out << "f " << b << ' ' << c << ' ' << d << '\n';
        }
    }
    return out.good();
}

void RunNeumannSanity(const CliOptions& opts) {
    const std::string spherePath = "experiments/generated/inner_sphere.obj";
    if (!WriteSphereObj(spherePath, 0.35f, 32, 16)) {
        std::cerr << "Failed to write " << spherePath << "\n";
        return;
    }

    WoStGeometryBackend sphere(spherePath);
    CubeOuterBoundary exterior({-opts.cubeHalfExtent, -opts.cubeHalfExtent, -opts.cubeHalfExtent},
                               { opts.cubeHalfExtent,  opts.cubeHalfExtent,  opts.cubeHalfExtent});
    WoStKernel kernel(sphere, exterior);

    BoundaryPoint bp;
    double sumDot = 0.0;
    double minDot = 1.0;
    const std::vector<vec3> probes = {
        {0.55f, 0.0f, 0.0f}, {0.0f, 0.55f, 0.0f}, {0.0f, 0.0f, 0.55f},
        {-0.45f, 0.2f, 0.1f}, {0.2f, -0.5f, 0.15f}, {0.15f, 0.2f, -0.5f}
    };
    namespace fs = std::filesystem;
    fs::create_directories("experiments");
    std::ofstream diag(fs::path("experiments") / "neumann_normal_diagnostics.csv");
    diag << "x,y,z,nx,ny,nz,expected_nx,expected_ny,expected_nz,h,expected_h,normal_dot\n";
    for (const vec3& p : probes) {
        sphere.ClosestPoint(p, bp);
        const vec3 expected = norm3(bp.position);
        const double ndot = dot3(bp.normal, expected);
        const double h = dot3(vec3(1.0f, 1.0f, 1.0f), bp.normal);
        const double expectedH = dot3(vec3(1.0f, 1.0f, 1.0f), expected);
        sumDot += ndot;
        minDot = std::min(minDot, ndot);
        diag << p.x << ',' << p.y << ',' << p.z << ','
             << bp.normal.x << ',' << bp.normal.y << ',' << bp.normal.z << ','
             << expected.x << ',' << expected.y << ',' << expected.z << ','
             << h << ',' << expectedH << ',' << ndot << '\n';
    }
    const double meanDot = sumDot / static_cast<double>(probes.size());
    std::cout << "Neumann normal convention check: mean normal dot expected radial = "
              << meanDot << ", min = " << minDot
              << (meanDot > 0.95 && minDot > 0.8 ? " PASS\n" : " CHECK SIGN\n");

    const BoundarySetup boundary = MakeLinearInnerNeumannProblem();
    for (int rep = 0; rep < 3; ++rep) {
        const uint64_t expSeed = opts.seed + static_cast<uint64_t>(rep) * 1009ull + 0x5A117u;
        WoStParams p = ExperimentBaseParams(opts);
        p.maxSteps = 2048;
        p.numSamples = opts.maxSamples;
        p.adaptiveSampling = false;
        RunExperimentCase(kernel, spherePath, "neumann_sanity", "sphere_cube",
                          opts.numQueryPoints, p, expSeed, opts.cubeHalfExtent,
                          boundary, rep == 0);
    }
}

void RunOptimizationExperiments(const WoStKernel& kernel, const CliOptions& opts, const std::string& meshName) {
    RunAdaptiveComparison(kernel, opts, meshName);
    RunAntitheticComparison(kernel, opts, meshName);
    RunLazyRefinementComparison(kernel, opts, meshName);
    RunEpsilonExtrapolation(kernel, opts, meshName);
    RunNeumannSanity(opts);
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
    const BoundarySetup boundary = MakeLinearDirichletProblem();

    for (int threads : ThreadSweepValues(opts.numThreads)) {
#ifdef _OPENMP
        omp_set_num_threads(threads);
#endif
        RunPointBenchmark(kernel, meshName, "thread_scaling", opts.numQueryPoints, p,
                          opts.seed ^ 0x71EADu, opts.cubeHalfExtent, boundary);
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
        mode != "adaptive" && mode != "neumann" && mode != "threads" &&
        mode != "geometry" && mode != "case" && mode != "adaptive_compare" &&
        mode != "antithetic" && mode != "lazy" &&
        mode != "epsilon_extrapolation" && mode != "neumann_sanity" &&
        mode != "optimization" && mode != "demo_point" &&
        mode != "bias_detector" && mode != "variance_adaptive" &&
        mode != "points" && mode != "point_bias" &&
        mode != "all") {
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
              << "seed: " << opts.seed << "\n"
              << "adaptive min/max/batch: " << opts.minSamples << " / "
              << opts.maxSamples << " / " << opts.batchSize
              << "  target_rse: " << opts.targetRSE
              << "  rse_eps: " << opts.rseEps << "\n"
              << "demo boundary: " << opts.boundaryMode
              << "  walks: " << opts.walks
              << "  epsilon: " << opts.epsilon << "\n";

    WoStGeometryBackend interior(opts.objFile);
    CubeOuterBoundary exterior({-opts.cubeHalfExtent, -opts.cubeHalfExtent, -opts.cubeHalfExtent},
                               { opts.cubeHalfExtent,  opts.cubeHalfExtent,  opts.cubeHalfExtent});
    WoStKernel kernel(interior, exterior);

    if (mode == "demo_point") {
        RunDemoPoint(kernel, opts);
        std::cout << "\nDemo outputs written under results/.\n";
        return 0;
    }
    if (mode == "bias_detector") {
        RunBiasDetector(kernel, opts);
        std::cout << "\nBoundary-bias outputs written under results/.\n";
        return 0;
    }
    if (mode == "variance_adaptive") {
        RunVarianceAdaptive(kernel, opts);
        std::cout << "\nVariance-adaptive outputs written under results/.\n";
        return 0;
    }
    if (mode == "points") {
        RunPointListBenchmark(kernel, opts, opts.objFile);
        return 0;
    }
    if (mode == "point_bias") {
        RunPointListBias(kernel, opts, opts.objFile);
        return 0;
    }
    if (mode == "case") {
        RunSingleCaseBenchmark(kernel, opts, opts.objFile);
        return 0;
    }

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
    if (mode == "neumann" || mode == "all") {
        RunNeumannBenchmark(kernel, opts, opts.objFile);
    }
    if (mode == "threads" || mode == "all") {
        RunThreadScaling(kernel, opts, opts.objFile);
    }
    if (mode == "geometry" || mode == "all") {
        RunGeometryBenchmark(interior, opts, opts.objFile);
    }
    if (mode == "adaptive_compare" || mode == "optimization") {
        RunAdaptiveComparison(kernel, opts, opts.objFile);
    }
    if (mode == "antithetic" || mode == "optimization") {
        RunAntitheticComparison(kernel, opts, opts.objFile);
    }
    if (mode == "lazy" || mode == "optimization") {
        RunLazyRefinementComparison(kernel, opts, opts.objFile);
    }
    if (mode == "epsilon_extrapolation" || mode == "optimization") {
        RunEpsilonExtrapolation(kernel, opts, opts.objFile);
    }
    if (mode == "neumann_sanity" || mode == "optimization") {
        RunNeumannSanity(opts);
    }

    std::cout << "\nBenchmark outputs written under results/. Optimization outputs written under experiments/.\n";
    return 0;
}
