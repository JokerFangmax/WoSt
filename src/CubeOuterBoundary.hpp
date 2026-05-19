#ifndef WOST_CUBE_OUTER_BOUNDARY_HPP
#define WOST_CUBE_OUTER_BOUNDARY_HPP

#include "utils.hpp"
#include <algorithm>
#include <limits>

namespace wost {

// ===========================================================================
// CubeOuterBoundary
// Represents an Axis-Aligned Bounding Box (AABB) acting as the outer 
// boundary of the PDE domain.
// ===========================================================================
class CubeOuterBoundary {
public:
    // -----------------------------------------------------------------------
    // Construction
    // -----------------------------------------------------------------------
    CubeOuterBoundary(const vec3& bmin, const vec3& bmax);
    ~CubeOuterBoundary() = default;

    // -----------------------------------------------------------------------
    // (1) Closest point on the cube boundary
    //     Evaluates the distance to the 6 planes and returns the minimum.
    // -----------------------------------------------------------------------
    float ClosestPoint(const vec3& x, BoundaryPoint& bp) const;

    // -----------------------------------------------------------------------
    // (2) Star-shaped ball radius
    //     Because a cube is convex, from the interior, there are no 
    //     silhouettes obstructing visibility. The StarRadius is exactly 
    //     the closest boundary distance.
    // -----------------------------------------------------------------------
    float StarRadius(const vec3& x) const;
    float StarRadius(const vec3& x, BoundaryPoint& closestBoundary) const;

    // -----------------------------------------------------------------------
    // (2b) FastStarRadius – scalar only, no BoundaryPoint allocation.
    //     For a convex AABB there are no silhouettes, so StarRadius equals
    //     the closest face distance. Used in the walk hot-path to avoid
    //     writing a BoundaryPoint on every step (deferred until absorption).
    // -----------------------------------------------------------------------
    inline float FastStarRadius(const vec3& x) const noexcept {
        float d = x.x - bmin.x;
        d = std::min(d, bmax.x - x.x);
        d = std::min(d, x.y - bmin.y);
        d = std::min(d, bmax.y - x.y);
        d = std::min(d, x.z - bmin.z);
        d = std::min(d, bmax.z - x.z);
        return d;
    }

    // -----------------------------------------------------------------------
    // (3) Ray–boundary intersection
    //     Slab method for Ray-AABB intersection. 
    //     Returns true if the ray hits the boundary.
    // -----------------------------------------------------------------------
    bool IntersectRay(const vec3& origin, const vec3& dir, float tMax,
                      float& t, vec3& hitNormal) const;

    // -----------------------------------------------------------------------
    // (4) Inside/outside test
    //     Simple AABB bounds check.
    // -----------------------------------------------------------------------
    bool IsInside(const vec3& x) const;

private:
    vec3 bmin;
    vec3 bmax;
};

} // namespace wost

#endif // WOST_CUBE_OUTER_BOUNDARY_HPP