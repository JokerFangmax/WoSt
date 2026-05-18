#include "CubeOuterBoundary.hpp"
#include <cmath>

namespace wost {

CubeOuterBoundary::CubeOuterBoundary(const vec3& bmin, const vec3& bmax) : bmin(bmin), bmax(bmax) 
{}

float CubeOuterBoundary::ClosestPoint(const vec3& x, BoundaryPoint& bp) const 
{
    // Check if the point is strictly inside the cube
    bool inside = IsInside(x);

    if (inside) {
        // Distance to the 6 faces
        float dx0 = x.x - bmin.x;
        float dx1 = bmax.x - x.x;
        float dy0 = x.y - bmin.y;
        float dy1 = bmax.y - x.y;
        float dz0 = x.z - bmin.z;
        float dz1 = bmax.z - x.z;

        float minDist = dx0;
        vec3 normal(-1.f, 0.f, 0.f);

        if (dx1 < minDist) { minDist = dx1; normal = vec3(1.f, 0.f, 0.f); }
        if (dy0 < minDist) { minDist = dy0; normal = vec3(0.f, -1.f, 0.f); }
        if (dy1 < minDist) { minDist = dy1; normal = vec3(0.f, 1.f, 0.f); }
        if (dz0 < minDist) { minDist = dz0; normal = vec3(0.f, 0.f, -1.f); }
        if (dz1 < minDist) { minDist = dz1; normal = vec3(0.f, 0.f, 1.f); }

        bp.dist = minDist;
        bp.normal = normal; // Normal points OUTWARDS from the cube
        
        // Position on the boundary
        bp.position.x = x.x + normal.x * minDist;
        bp.position.y = x.y + normal.y * minDist;
        bp.position.z = x.z + normal.z * minDist;
        bp.triIdx = ~0u; // No triangles on this geometry
        
        return minDist;
    } else {
        // Point is outside the cube (clamps to nearest point on AABB)
        vec3 p = x;
        p.x = std::max(bmin.x, std::min(bmax.x, p.x));
        p.y = std::max(bmin.y, std::min(bmax.y, p.y));
        p.z = std::max(bmin.z, std::min(bmax.z, p.z));

        float dx = x.x - p.x;
        float dy = x.y - p.y;
        float dz = x.z - p.z;
        float dist = std::sqrt(dx*dx + dy*dy + dz*dz);

        bp.dist = dist;
        bp.position = p;
        bp.triIdx = ~0u;

        if (dist > 1e-8f) {
            bp.normal = vec3(dx/dist, dy/dist, dz/dist);
        } else {
            bp.normal = vec3(1.f, 0.f, 0.f); // Fallback if exactly on edge/corner
        }
        return dist;
    }
}

float CubeOuterBoundary::StarRadius(const vec3& x) const 
{
    BoundaryPoint bp;
    return ClosestPoint(x, bp);
}

float CubeOuterBoundary::StarRadius(const vec3& x, BoundaryPoint& closestBoundary) const 
{
    // A cube is convex. Evaluated from the inside, there are no silhouette edges.
    return ClosestPoint(x, closestBoundary);
}

bool CubeOuterBoundary::IntersectRay(const vec3& origin, const vec3& dir, float tMax,
                                     float& t, vec3& hitNormal) const 
{
    float tmin = 0.0f;
    float tmax = tMax;
    vec3 normal_min(0.f, 0.f, 0.f);

    // Slab intersection testing for X, Y, Z axes
    // X Axis
    if (std::abs(dir.x) > 1e-8f) {
        float invD = 1.0f / dir.x;
        float t0 = (bmin.x - origin.x) * invD;
        float t1 = (bmax.x - origin.x) * invD;
        vec3 n0(-1.f, 0.f, 0.f);
        vec3 n1(1.f, 0.f, 0.f);
        
        if (t0 > t1) { std::swap(t0, t1); std::swap(n0, n1); }

        if (t0 > tmin) { tmin = t0; normal_min = n0; }
        tmax = std::min(tmax, t1);
        if (tmin > tmax) return false;
    } else if (origin.x < bmin.x || origin.x > bmax.x) return false;

    // Y Axis
    if (std::abs(dir.y) > 1e-8f) {
        float invD = 1.0f / dir.y;
        float t0 = (bmin.y - origin.y) * invD;
        float t1 = (bmax.y - origin.y) * invD;
        vec3 n0(0.f, -1.f, 0.f);
        vec3 n1(0.f, 1.f, 0.f);
        
        if (t0 > t1) { std::swap(t0, t1); std::swap(n0, n1); }

        if (t0 > tmin) { tmin = t0; normal_min = n0; }
        tmax = std::min(tmax, t1);
        if (tmin > tmax) return false;
    } else if (origin.y < bmin.y || origin.y > bmax.y) return false;

    // Z Axis
    if (std::abs(dir.z) > 1e-8f) {
        float invD = 1.0f / dir.z;
        float t0 = (bmin.z - origin.z) * invD;
        float t1 = (bmax.z - origin.z) * invD;
        vec3 n0(0.f, 0.f, -1.f);
        vec3 n1(0.f, 0.f, 1.f);
        
        if (t0 > t1) { std::swap(t0, t1); std::swap(n0, n1); }

        if (t0 > tmin) { tmin = t0; normal_min = n0; }
        tmax = std::min(tmax, t1);
        if (tmin > tmax) return false;
    } else if (origin.z < bmin.z || origin.z > bmax.z) return false;

    t = tmin;
    hitNormal = normal_min;
    return true;
}

bool CubeOuterBoundary::IsInside(const vec3& x) const 
{
    return (x.x >= bmin.x && x.x <= bmax.x &&
            x.y >= bmin.y && x.y <= bmax.y &&
            x.z >= bmin.z && x.z <= bmax.z);
}

} // namespace wost