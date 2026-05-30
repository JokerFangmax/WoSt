#include "WoStKernel.hpp"

#include <algorithm>
#include <cmath>

namespace wost {

namespace {

const NeumannFn kZeroNeumann = [](const BoundaryPoint&) -> float {
    return 0.0f;
};

const NeumannPredFn kNeverNeumann = [](const BoundaryPoint&) -> bool {
    return false;
};

struct TrajectorySample {
    float value = 0.0f;
    int steps = 0;
    bool diverged = false;
};

inline uint32_t MixSeed(uint64_t base, uint32_t stream) noexcept {
    uint64_t z = base + 0x9E3779B97F4A7C15ull * (static_cast<uint64_t>(stream) + 1ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    z ^= (z >> 31);
    const uint32_t mixed = static_cast<uint32_t>(z) ^ static_cast<uint32_t>(z >> 32);
    return mixed ? mixed : 1u;
}

inline vec3 DomainDirectionFromPoint(const vec3& x, const BoundaryPoint& bp, bool isOuterBoundary) {
    const vec3 delta = sub(x, bp.position);
    const float deltaLen = len3(delta);
    if (deltaLen > 1e-8f) {
        return scale3(delta, 1.0f / deltaLen);
    }
    return isOuterBoundary ? scale3(bp.normal, -1.0f) : bp.normal;
}

} // namespace

// ---------------------------------------------------------------------------
// Constructor
// ---------------------------------------------------------------------------
WoStKernel::WoStKernel(const WoStGeometryBackend& inner, const CubeOuterBoundary& outer)
    : inner_(inner), outer_(outer) {}

// ---------------------------------------------------------------------------
// Domain predicate
// ---------------------------------------------------------------------------
bool WoStKernel::InDomain(const vec3& x) const {
    return outer_.IsInside(x) && !inner_.IsInside(x);
}

// ---------------------------------------------------------------------------
// Helper - make a BoundaryPoint for an outer-cube hit (no triangle)
// ---------------------------------------------------------------------------
BoundaryPoint WoStKernel::makeCubeBP(const vec3& origin,
                                     const vec3& dir,
                                     float t,
                                     const vec3& normal) {
    BoundaryPoint bp;
    bp.position = madd(origin, dir, t);
    bp.normal   = normal;
    bp.dist     = t;
    bp.triIdx   = ~0u;
    return bp;
}

WalkResult WoStKernel::SolveLaplace(const vec3& x0,
                                    const DirichletFn& g_inner,
                                    const DirichletFn& g_outer,
                                    const WoStParams& params) const {
    return SolveLaplace(x0, g_inner, g_outer,
                        kZeroNeumann, kZeroNeumann,
                        kNeverNeumann, kNeverNeumann,
                        params);
}

WalkResult WoStKernel::SolveLaplace(const vec3& x0,
                                    const DirichletFn& g_inner,
                                    const DirichletFn& g_outer,
                                    const NeumannFn& h_inner,
                                    const NeumannFn& h_outer,
                                    const NeumannPredFn& is_neumann_inner,
                                    const NeumannPredFn& is_neumann_outer,
                                    const WoStParams& params) const {
    const SourceFn zeroSource = [](const vec3&) -> float {
        return 0.0f;
    };
    return SolvePoisson(x0, g_inner, g_outer,
                        h_inner, h_outer,
                        is_neumann_inner, is_neumann_outer,
                        zeroSource, params);
}

WalkResult WoStKernel::SolvePoisson(const vec3& x0,
                                    const DirichletFn& g_inner,
                                    const DirichletFn& g_outer,
                                    const SourceFn& f,
                                    const WoStParams& params) const {
    return SolvePoisson(x0, g_inner, g_outer,
                        kZeroNeumann, kZeroNeumann,
                        kNeverNeumann, kNeverNeumann,
                        f, params);
}

WalkResult WoStKernel::SolvePoisson(const vec3& x0,
                                    const DirichletFn& g_inner,
                                    const DirichletFn& g_outer,
                                    const NeumannFn& h_inner,
                                    const NeumannFn& h_outer,
                                    const NeumannPredFn& is_neumann_inner,
                                    const NeumannPredFn& is_neumann_outer,
                                    const SourceFn& f,
                                    const WoStParams& params) const {
    WalkResult result;
    if (params.numSamples <= 0) {
        result.anyDiverged = true;
        return result;
    }

    const float neumannOffset = std::max(params.neumannOffset, 2.0f * params.eps);

    auto handleBoundaryEvent = [&](const BoundaryPoint& bp,
                                   bool isOuterBoundary,
                                   vec3& x,
                                   float& acc) -> bool {
        const bool isNeumann = isOuterBoundary ? is_neumann_outer(bp) : is_neumann_inner(bp);
        if (!isNeumann) {
            acc += isOuterBoundary ? g_outer(bp) : g_inner(bp);
            return true;
        }

        const float flux = isOuterBoundary ? h_outer(bp) : h_inner(bp);
        const vec3 domainDir = DomainDirectionFromPoint(x, bp, isOuterBoundary);
        const float normalAlignment = dot3(domainDir, bp.normal);

        acc += (bp.dist - neumannOffset) * normalAlignment * flux;
        x = madd(bp.position, domainDir, neumannOffset);
        return false;
    };

    auto runTrajectory = [&](uint32_t streamIdx, bool useAntitheticDirections) -> TrajectorySample {
        FastRNG rng(MixSeed(params.seed, streamIdx));

        vec3 x = x0;
        float acc = 0.0f;
        int steps = 0;
        bool done = false;

        for (int step = 0; step < params.maxSteps; ++step) {
            ++steps;

            const float R_inner_approx = inner_.FastBoundaryDistance(x);
            const float R_outer = outer_.FastStarRadius(x);
            const float R_approx = std::min(R_inner_approx, R_outer);

            float R = R_approx;
            bool useAccurateRadius = false;
            BoundaryPoint innerBoundaryBP;

            if (R_approx < params.eps * 2.0f) {
                BoundaryPoint silhouetteBP;
                const float R_inner = inner_.StarRadius(x, innerBoundaryBP, silhouetteBP);
                R = std::min(R_inner, R_outer);
                const bool outerCloser = (R_outer <= R_inner);
                const float distToBoundary = outerCloser ? R_outer : innerBoundaryBP.dist;

                if (distToBoundary < params.eps) {
                    if (outerCloser) {
                        BoundaryPoint outerBoundaryBP;
                        outer_.ClosestPoint(x, outerBoundaryBP);
                        done = handleBoundaryEvent(outerBoundaryBP, true, x, acc);
                    } else {
                        done = handleBoundaryEvent(innerBoundaryBP, false, x, acc);
                    }

                    if (done) {
                        break;
                    }
                    continue;
                }

                useAccurateRadius = true;
            }

            vec3 dir = sampleUnitSphere(rng);
            if (useAntitheticDirections) {
                dir = scale3(dir, -1.0f);
            }

            float t_inner = 0.0f;
            vec3 n_inner = {};
            uint32_t prim_inner = ~0u;
            const bool hitInner = inner_.IntersectRay(x, dir, R, t_inner, n_inner, prim_inner);

            const float stepLen = hitInner ? t_inner : R;
            acc -= (stepLen * stepLen / 6.0f) * f(x);

            if (hitInner) {
                BoundaryPoint hitBP = makeBP(x, dir, t_inner, n_inner, prim_inner);
                done = handleBoundaryEvent(hitBP, false, x, acc);
                if (done) {
                    break;
                }
                continue;
            }

            x = madd(x, dir, useAccurateRadius ? R : R_approx);
        }

        if (!done) {
            BoundaryPoint innerBP;
            BoundaryPoint outerBP;
            const float dInner = inner_.ClosestPoint(x, innerBP);
            const float dOuter = outer_.ClosestPoint(x, outerBP);

            if (dOuter <= dInner) {
                acc += g_outer(outerBP);
            } else {
                acc += g_inner(innerBP);
            }

            return { acc, steps, true };
        }

        return { acc, steps, false };
    };

    double sumV = 0.0;
    double sumV2 = 0.0;
    int sumSteps = 0;
    int estimatorCount = 0;
    int trajectoryCount = 0;

    if (params.varianceReduction == VarianceReductionMode::Antithetic) {
        const int pairCount = params.numSamples / 2;
        for (int pairIdx = 0; pairIdx < pairCount; ++pairIdx) {
            const uint32_t streamIdx = static_cast<uint32_t>(pairIdx);
            const TrajectorySample a = runTrajectory(streamIdx, false);
            const TrajectorySample b = runTrajectory(streamIdx, true);
            const double pairedValue = 0.5 * (static_cast<double>(a.value) + static_cast<double>(b.value));

            sumV += pairedValue;
            sumV2 += pairedValue * pairedValue;
            sumSteps += a.steps + b.steps;
            estimatorCount += 1;
            trajectoryCount += 2;
            result.anyDiverged = result.anyDiverged || a.diverged || b.diverged;
        }

        if ((params.numSamples & 1) != 0) {
            const TrajectorySample solo = runTrajectory(static_cast<uint32_t>(pairCount), false);
            sumV += solo.value;
            sumV2 += static_cast<double>(solo.value) * solo.value;
            sumSteps += solo.steps;
            estimatorCount += 1;
            trajectoryCount += 1;
            result.anyDiverged = result.anyDiverged || solo.diverged;
        }
    } else {
        for (int sampleIdx = 0; sampleIdx < params.numSamples; ++sampleIdx) {
            const TrajectorySample sample = runTrajectory(static_cast<uint32_t>(sampleIdx), false);
            sumV += sample.value;
            sumV2 += static_cast<double>(sample.value) * sample.value;
            sumSteps += sample.steps;
            estimatorCount += 1;
            trajectoryCount += 1;
            result.anyDiverged = result.anyDiverged || sample.diverged;
        }
    }

    finalise(result, sumV, sumV2, sumSteps, estimatorCount, trajectoryCount);
    return result;
}

} // namespace wost
