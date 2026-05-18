#include "WoStKernel.hpp"
#include <algorithm>

namespace wost {

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
// Helper – make a BoundaryPoint for an outer-cube hit (no triangle)
// ---------------------------------------------------------------------------
BoundaryPoint WoStKernel::makeCubeBP(const vec3& origin,
                                              const vec3& dir,
                                              float       t,
                                              const vec3& normal)
{
    BoundaryPoint bp;
    bp.position = madd(origin, dir, t);
    bp.normal   = normal;
    bp.dist     = t;
    bp.triIdx   = ~0u;   // no triangle
    return bp;
}

// ===========================================================================
// (1) SolveLaplace
// ===========================================================================
WalkResult WoStKernel::SolveLaplace(const vec3& x0,
                                             const DirichletFn& g_inner,
                                             const DirichletFn& g_outer,
                                             const WoStParams&  params) const
{
    WalkResult result;
    double sumV = 0.0, sumV2 = 0.0;
    int sumSteps = 0;
    Random rng;
    for (int s = 0; s < params.numSamples; ++s) {

        vec3  x    = x0;
        float acc  = 0.f;
        int   steps = 0;
        bool  done  = false;

        for (int step = 0; step < params.maxSteps; ++step) {
            ++steps;

            // ── Dual star radius ────────────────────────────────────────
            BoundaryPoint bndBP_inner, silBP_inner;
            float R_inner = inner_.StarRadius(x, bndBP_inner, silBP_inner);

            BoundaryPoint bndBP_outer;
            float R_outer = outer_.StarRadius(x, bndBP_outer);

            float R            = std::min(R_inner, R_outer);
            bool  outerCloser  = (R_outer <= R_inner);

            // Corrected check: Only absorb if close to an actual boundary
            float distToActualBoundary = outerCloser ? bndBP_outer.dist : bndBP_inner.dist; 
            if (distToActualBoundary < params.eps) {
                if (outerCloser) acc += g_outer(bndBP_outer);
                else acc += g_inner(bndBP_inner);
                done = true;
                break;
            }

            // ── Random walk step ─────────────────────────────────────────
            //   Sample a direction; ray-test only the inner mesh.
            //   Reason: the ball B(x, R) with R ≤ R_outer always fits inside
            //   the convex cube, so no step of length R can exit the cube.
            vec3 dir = sampleUnitSphere(rng);

            float    t_inner;
            vec3     n_inner;
            uint32_t prim_inner;
            bool hit = inner_.IntersectRay(x, dir, R, t_inner, n_inner, prim_inner);

            if (hit) {
                // Boundary hit before reaching R → apply inner Dirichlet BC.
                acc += g_inner(makeBP(x, dir, t_inner, n_inner, prim_inner));
                done = true;
                break;
            } else {
                // Free path: advance to sphere surface S(x, R).
                x = madd(x, dir, R);
            }
        } // walk steps

        if (!done) {
            // Safety fallback: walk hit maxSteps; use nearest boundary.
            BoundaryPoint bp_i, bp_o;
            float d_i = inner_.ClosestPoint(x, bp_i);
            float d_o = outer_.ClosestPoint(x, bp_o);
            acc += (d_o <= d_i) ? g_outer(bp_o) : g_inner(bp_i);
            result.anyDiverged = true;
        }

        sumV     += acc;
        sumV2    += static_cast<double>(acc) * acc;
        sumSteps += steps;
    }

    finalise(result, sumV, sumV2, sumSteps, params.numSamples);
    return result;
}

// ===========================================================================
// (2) SolvePoisson
//
// Walk accumulator:
//   acc  +=  g(hit point)                     [boundary contribution]
//   acc  -=  (stepLen² / 6) * f(x)            [volume source, 3-D formula]
//
// 'stepLen' is the actual step taken (t_inner if boundary was hit, else R).
// Using the actual step length rather than the full R is more accurate when
// R was limited by silhouettes rather than the boundary distance itself.
// ===========================================================================
WalkResult WoStKernel::SolvePoisson(const vec3&        x0,
                                              const DirichletFn& g_inner,
                                              const DirichletFn& g_outer,
                                              const SourceFn&    f,
                                              const WoStParams&  params) const
{
    WalkResult result;
    double sumV = 0.0, sumV2 = 0.0;
    int sumSteps = 0;
    Random rng;
    for (int s = 0; s < params.numSamples; ++s) {

        vec3  x    = x0;
        float acc  = 0.f;
        int   steps = 0;
        bool  done  = false;

        for (int step = 0; step < params.maxSteps; ++step) {
            ++steps;

            // ── Dual star radius ────────────────────────────────────────
            BoundaryPoint bndBP_inner, silBP_inner;
            float R_inner = inner_.StarRadius(x, bndBP_inner, silBP_inner);

            BoundaryPoint bndBP_outer;
            float R_outer = outer_.StarRadius(x, bndBP_outer);

            float R           = std::min(R_inner, R_outer);
            bool  outerCloser = (R_outer <= R_inner);

            // Corrected check: Only absorb if close to an actual boundary
            float distToActualBoundary = outerCloser ? bndBP_outer.dist : bndBP_inner.dist; 
            if (distToActualBoundary < params.eps) {
                if (outerCloser) acc += g_outer(bndBP_outer);
                else acc += g_inner(bndBP_inner);
                done = true;
                break;
            }

            // ── Random walk step ─────────────────────────────────────────
            vec3 dir = sampleUnitSphere(rng);

            float    t_inner;
            vec3     n_inner;
            uint32_t prim_inner;
            bool hit = inner_.IntersectRay(x, dir, R, t_inner, n_inner, prim_inner);

            // Effective step length (≤ R).
            float stepLen = hit ? t_inner : R;

            // ── Poisson source contribution ──────────────────────────────
            //   Mean-value formula for Δu = f in 3-D:
            //     u(x) = MeanValue(u, S(x,R)) - (R²/6) f(x) + O(R³)
            acc -= (stepLen * stepLen / 6.f) * f(x);

            if (hit) {
                acc += g_inner(makeBP(x, dir, t_inner, n_inner, prim_inner));
                done = true;
                break;
            } else {
                x = madd(x, dir, R);
            }
        } // walk steps

        if (!done) {
            BoundaryPoint bp_i, bp_o;
            float d_i = inner_.ClosestPoint(x, bp_i);
            float d_o = outer_.ClosestPoint(x, bp_o);
            acc += (d_o <= d_i) ? g_outer(bp_o) : g_inner(bp_i);
            result.anyDiverged = true;
        }

        sumV     += acc;
        sumV2    += static_cast<double>(acc) * acc;
        sumSteps += steps;
    }

    finalise(result, sumV, sumV2, sumSteps, params.numSamples);
    return result;
}

} // namespace wost