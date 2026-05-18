#ifndef DUAL_BOUNDARY_KERNEL_HPP
#define DUAL_BOUNDARY_KERNEL_HPP

// ===========================================================================
// WoStKernel
//
// Solves PDEs on an annular domain  Ω = { x : x inside cube AND outside mesh }
//
//   ∂Ω  =  Γ_inner (OBJ mesh surface)  ∪  Γ_outer (cube faces)
//
// Key insight – why we never ray-test the outer cube in the walk loop:
//   R = min(R_inner, R_outer).  Because the cube is convex, the ball B(x, R)
//   with R ≤ R_outer always fits entirely inside the cube.  A random step of
//   length R therefore never exits the cube.  The outer cube only contributes
//   via the ε-absorption shell: when R_outer < ε the walk has reached the
//   cube wall and we apply the outer Dirichlet BC directly.
//
// Only the inner (concave) mesh needs actual ray-intersection testing.
// ===========================================================================

#include "WoStGeometryBackend.hpp"
#include "CubeOuterBoundary.hpp"
#include "utils.hpp"

namespace wost {

class WoStKernel {
public:
    // Both geometry objects must outlive this kernel.
    WoStKernel(const WoStGeometryBackend& inner, const CubeOuterBoundary&   outer);

    // -----------------------------------------------------------------------
    // Domain predicate
    //   true  ↔  x is inside the cube AND outside the inner mesh.
    // -----------------------------------------------------------------------
    bool InDomain(const vec3& x) const;

    // -----------------------------------------------------------------------
    // (1) Laplace  Δu = 0
    //       u = g_inner  on Γ_inner  (OBJ mesh)
    //       u = g_outer  on Γ_outer  (cube faces)
    // -----------------------------------------------------------------------
    WalkResult SolveLaplace(const vec3&        x,
                            const DirichletFn& g_inner,
                            const DirichletFn& g_outer,
                            const WoStParams&  p = {}) const;

    // -----------------------------------------------------------------------
    // (2) Poisson  Δu = f
    //       u = g_inner  on Γ_inner
    //       u = g_outer  on Γ_outer
    //     Source correction per step:  acc -= (R² / 6) * f(x)   [3-D]
    //     Pass f = [](auto&){ return 0.f; } to recover Laplace.
    // -----------------------------------------------------------------------
    WalkResult SolvePoisson(const vec3&        x,
                            const DirichletFn& g_inner,
                            const DirichletFn& g_outer,
                            const SourceFn&    f,
                            const WoStParams&  p = {}) const;

private:
    // Assemble a BoundaryPoint for the outer cube (no triangle index).
    static BoundaryPoint makeCubeBP(const vec3& origin,
                                    const vec3& dir,
                                    float       t,
                                    const vec3& normal);

    const WoStGeometryBackend& inner_;
    const CubeOuterBoundary&   outer_;
};

} // namespace wost

#endif // DUAL_BOUNDARY_KERNEL_HPP