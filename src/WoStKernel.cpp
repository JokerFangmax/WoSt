#include "WoStKernel.hpp"
#include <algorithm>
#include <cmath>
#include <vector>

namespace wost {

WoStKernel::WoStKernel(const WoStGeometryBackend& inner, const CubeOuterBoundary& outer)
    : inner_(inner), outer_(outer) {}

bool WoStKernel::InDomain(const vec3& x) const {
    return outer_.IsInside(x) && !inner_.IsInside(x);
}

BoundaryPoint WoStKernel::makeCubeBP(const vec3& origin, const vec3& dir, float t, const vec3& normal) {
    BoundaryPoint bp;
    bp.position = madd(origin, dir, t);
    bp.normal   = normal;
    bp.dist     = t;
    bp.triIdx   = ~0u;
    return bp;
}

WalkResult WoStKernel::SolveLaplace(const vec3&          x0,
                                    const DirichletFn&   g_inner,
                                    const NeumannPredFn& is_inner_neumann,
                                    const NeumannFn&     h_inner,
                                    const DirichletFn&   g_outer,
                                    const WoStParams&    params) const
{
    return SolvePoisson(x0, g_inner, is_inner_neumann, h_inner, g_outer,
                        [](const vec3& x) { (void)x; return 0.f; }, params);
}

WalkResult WoStKernel::SolvePoisson(const vec3&          x0,
                                    const DirichletFn&   g_inner,
                                    const NeumannPredFn& is_inner_neumann,
                                    const NeumannFn&     h_inner,
                                    const DirichletFn&   g_outer,
                                    const SourceFn&      f,
                                    const WoStParams&    params) const
{
    struct SingleWalkResult {
        float value = 0.f;
        int steps = 0;
        bool diverged = false;
        uint64_t starQueries = 0;
        uint64_t fastOnlyStarQueries = 0;
        uint64_t exactStarQueries = 0;
    };

    WalkResult result;
    double sumV = 0.0, sumV2 = 0.0;
    int sumSteps = 0;
    int samplesUsed = 0;
    int estimatorCount = 0;
    FastRNG rng(static_cast<uint32_t>(params.seed));

    const int fixedSamples = std::max(1, params.numSamples);
    const int adaptiveMaxSamples = std::max(1, params.maxSamples);
    const int sampleLimit = params.adaptiveSampling ? adaptiveMaxSamples : fixedSamples;
    const int minSamples = std::min(sampleLimit, std::max(1, params.minSamples));
    const int batchSize = std::max(1, params.batchSize);

    auto drawDirection = [&](std::vector<vec3>* tape, size_t& cursor, int sign) -> vec3 {
        vec3 dir;
        if (tape) {
            if (cursor >= tape->size()) tape->push_back(sampleUnitSphere(rng));
            dir = (*tape)[cursor++];
        } else {
            dir = sampleUnitSphere(rng);
        }
        return sign < 0 ? scale(dir, -1.f) : dir;
    };

    auto runSingleWalk = [&](std::vector<vec3>* tape, int sign) -> SingleWalkResult {
        SingleWalkResult wr;
        size_t tapeCursor = 0;
        vec3 x = x0;
        float acc = 0.f;
        bool done = false;

        for (int step = 0; step < params.maxSteps; ++step) {
            ++wr.steps;
            ++wr.starQueries;

            const float R_outer = outer_.FastStarRadius(x);
            BoundaryPoint bndBP_inner, silBP_inner;
            float R_inner = 0.f;
            float R = 0.f;
            bool refined = false;

            const float fastInnerDist = inner_.FastBoundaryDistance(x);
            const float fastRadius = std::min(fastInnerDist, R_outer);
            const float refineDistance = params.lazyRefineDistance > 0.f
                ? params.lazyRefineDistance
                : params.eps * 2.0f;
            const bool ratioSuspicious = params.lazySuspiciousRatio > 0.f &&
                R_outer > 1e-12f &&
                fastInnerDist <= params.lazySuspiciousRatio * R_outer;
            const bool shouldRefine = !params.useLazyStarRefinement ||
                fastRadius < refineDistance || ratioSuspicious;

            if (shouldRefine) {
                R_inner = inner_.StarRadius(x, bndBP_inner, silBP_inner);
                R = std::min(R_inner, R_outer);
                refined = true;
                ++wr.exactStarQueries;
            } else {
                R_inner = fastInnerDist;
                R = fastRadius;
                bndBP_inner.dist = fastInnerDist;
                ++wr.fastOnlyStarQueries;
            }

            const bool outerCloser = (R_outer <= R_inner);
            float distToActualBoundary = outerCloser ? R_outer : bndBP_inner.dist;

            if (distToActualBoundary < params.eps) {
                if (outerCloser) {
                    BoundaryPoint bndBP_outer;
                    outer_.ClosestPoint(x, bndBP_outer);
                    acc += g_outer(bndBP_outer);
                    done = true;
                    break;
                }

                if (!refined) {
                    inner_.ClosestPoint(x, bndBP_inner);
                }

                if (is_inner_neumann(bndBP_inner)) {
                    const float jumpDist = std::max(params.eps * 100.0f, R_outer * 0.05f);
                    acc += h_inner(bndBP_inner) * jumpDist;
                    x = madd(bndBP_inner.position, bndBP_inner.normal, jumpDist);
                } else {
                    acc += g_inner(bndBP_inner);
                    done = true;
                    break;
                }
            }

            if (done) break;

            const vec3 dir = drawDirection(tape, tapeCursor, sign);
            float t_inner = 0.f;
            vec3 n_inner;
            uint32_t prim_inner = ~0u;
            const bool hit = inner_.IntersectRay(x, dir, R, t_inner, n_inner, prim_inner);

            acc -= (R * R / 6.f) * f(x);

            if (hit) {
                BoundaryPoint bp = makeBP(x, dir, t_inner, n_inner, prim_inner);
                if (is_inner_neumann(bp)) {
                    const float cosTheta = std::max(1e-4f, std::abs(dot3(dir, bp.normal)));
                    acc += h_inner(bp) * t_inner * (1.0f - t_inner / R) / cosTheta;

                    const vec3 reflectedDir = reflect(dir, bp.normal);
                    const float remainingDist = R - t_inner;
                    const vec3 newPos = madd(bp.position, reflectedDir, remainingDist);
                    x = madd(newPos, bp.normal, params.eps);
                } else {
                    acc += g_inner(bp);
                    done = true;
                    break;
                }
            } else {
                x = madd(x, dir, R);
            }
        }

        if (!done) {
            BoundaryPoint bp_i, bp_o;
            const float d_i = inner_.ClosestPoint(x, bp_i);
            const float d_o = outer_.ClosestPoint(x, bp_o);
            acc += (d_o <= d_i) ? g_outer(bp_o) : g_inner(bp_i);
            wr.diverged = true;
        }

        wr.value = acc;
        return wr;
    };

    auto addEstimator = [&](float value, int steps, int walks,
                            bool diverged, uint64_t starQueries,
                            uint64_t fastOnlyStarQueries,
                            uint64_t exactStarQueries) {
        sumV += value;
        sumV2 += static_cast<double>(value) * value;
        sumSteps += steps;
        samplesUsed += walks;
        ++estimatorCount;
        result.anyDiverged = result.anyDiverged || diverged;
        result.starQueries += starQueries;
        result.fastOnlyStarQueries += fastOnlyStarQueries;
        result.exactStarQueries += exactStarQueries;
    };

    auto addSample = [&](const SingleWalkResult& wr) {
        addEstimator(wr.value, wr.steps, 1, wr.diverged,
                     wr.starQueries, wr.fastOnlyStarQueries, wr.exactStarQueries);
    };

    auto addAntitheticPair = [&](const SingleWalkResult& a, const SingleWalkResult& b) {
        addEstimator(0.5f * (a.value + b.value),
                     a.steps + b.steps,
                     2,
                     a.diverged || b.diverged,
                     a.starQueries + b.starQueries,
                     a.fastOnlyStarQueries + b.fastOnlyStarQueries,
                     a.exactStarQueries + b.exactStarQueries);
    };

    auto adaptiveStopReached = [&]() -> bool {
        if (!params.adaptiveSampling || samplesUsed < minSamples || estimatorCount <= 0) return false;
        if (samplesUsed % batchSize != 0 && samplesUsed != sampleLimit) return false;

        const double mean = sumV / estimatorCount;
        const double var = std::max(0.0, sumV2 / estimatorCount - mean * mean);
        const double stdErr = std::sqrt(var) / std::sqrt(static_cast<double>(estimatorCount));
        if (params.useRelativeStdErr) {
            const double denom = std::max(std::abs(mean), static_cast<double>(params.rseEps));
            const double rse = stdErr / denom;
            return rse < static_cast<double>(params.targetRSE);
        }
        return stdErr < static_cast<double>(params.targetStdErr);
    };

    while (samplesUsed < sampleLimit) {
        if (params.useAntitheticSampling && samplesUsed + 1 < sampleLimit) {
            std::vector<vec3> directionTape;
            directionTape.reserve(static_cast<size_t>(std::min(params.maxSteps, 64)));
            const SingleWalkResult a = runSingleWalk(&directionTape, +1);
            const SingleWalkResult b = runSingleWalk(&directionTape, -1);
            addAntitheticPair(a, b);
        } else {
            addSample(runSingleWalk(nullptr, +1));
        }

        if (adaptiveStopReached()) break;
    }

    finalise(result, sumV, sumV2, sumSteps, estimatorCount);
    if (samplesUsed > 0) {
        result.meanSteps = static_cast<float>(sumSteps) / static_cast<float>(samplesUsed);
        result.samplesUsed = samplesUsed;
    }
    return result;
}

std::vector<WalkTraceRow> WoStKernel::TraceWalks(const vec3&          x0,
                                                 const DirichletFn&   g_inner,
                                                 const NeumannPredFn& is_inner_neumann,
                                                 const NeumannFn&     h_inner,
                                                 const DirichletFn&   g_outer,
                                                 const SourceFn&      f,
                                                 const WoStParams&    params,
                                                 int                 traceWalks) const
{
    (void)g_inner;
    (void)h_inner;
    (void)g_outer;
    std::vector<WalkTraceRow> rows;
    const int walks = std::max(0, traceWalks);
    rows.reserve(static_cast<size_t>(walks) * static_cast<size_t>(std::min(params.maxSteps + 2, 64)));
    FastRNG rng(static_cast<uint32_t>(params.seed));

    auto addRow = [&](int walkId, int stepId, const vec3& x, float radius,
                      const char* eventType, const char* boundaryType) {
        WalkTraceRow row;
        row.walkId = walkId;
        row.stepId = stepId;
        row.pos = x;
        row.radius = radius;
        row.eventType = eventType;
        row.boundaryType = boundaryType;
        rows.push_back(row);
    };

    for (int walkId = 0; walkId < walks; ++walkId) {
        vec3 x = x0;
        bool done = false;
        addRow(walkId, 0, x, 0.f, "start", "none");

        for (int step = 0; step < params.maxSteps; ++step) {
            BoundaryPoint bndBP_inner, silBP_inner;
            const float R_outer = outer_.FastStarRadius(x);
            const float R_inner = inner_.StarRadius(x, bndBP_inner, silBP_inner);
            const float R = std::min(R_inner, R_outer);
            const bool outerCloser = (R_outer <= R_inner);
            const float distToBoundary = outerCloser ? R_outer : bndBP_inner.dist;

            if (distToBoundary < params.eps) {
                if (outerCloser) {
                    BoundaryPoint bndBP_outer;
                    outer_.ClosestPoint(x, bndBP_outer);
                    addRow(walkId, step + 1, bndBP_outer.position, R, "dirichlet_hit", "outer");
                    done = true;
                    break;
                }

                inner_.ClosestPoint(x, bndBP_inner);
                if (is_inner_neumann(bndBP_inner)) {
                    const float jumpDist = std::max(params.eps * 100.0f, R_outer * 0.05f);
                    const vec3 reflected = madd(bndBP_inner.position, bndBP_inner.normal, jumpDist);
                    addRow(walkId, step + 1, bndBP_inner.position, R, "neumann_reflect", "neumann");
                    x = reflected;
                    addRow(walkId, step + 1, x, jumpDist, "sphere_step", "none");
                    continue;
                }

                addRow(walkId, step + 1, bndBP_inner.position, R, "dirichlet_hit", "inner");
                done = true;
                break;
            }

            const vec3 dir = sampleUnitSphere(rng);
            float t_inner = 0.f;
            vec3 n_inner;
            uint32_t prim_inner = ~0u;
            const bool hit = inner_.IntersectRay(x, dir, R, t_inner, n_inner, prim_inner);
            (void)f;

            if (hit) {
                BoundaryPoint bp = makeBP(x, dir, t_inner, n_inner, prim_inner);
                if (is_inner_neumann(bp)) {
                    const vec3 reflectedDir = reflect(dir, bp.normal);
                    const float remainingDist = R - t_inner;
                    const vec3 newPos = madd(bp.position, reflectedDir, remainingDist);
                    addRow(walkId, step + 1, bp.position, t_inner, "neumann_reflect", "neumann");
                    x = madd(newPos, bp.normal, params.eps);
                    addRow(walkId, step + 1, x, remainingDist, "sphere_step", "none");
                } else {
                    addRow(walkId, step + 1, bp.position, t_inner, "dirichlet_hit", "inner");
                    done = true;
                    break;
                }
            } else {
                x = madd(x, dir, R);
                addRow(walkId, step + 1, x, R, "sphere_step", "none");
            }
        }

        if (!done) {
            addRow(walkId, params.maxSteps, x, 0.f, "max_step", "none");
        }
        addRow(walkId, params.maxSteps + 1, x, 0.f, "end", "none");
    }

    return rows;
}

} // namespace wost
