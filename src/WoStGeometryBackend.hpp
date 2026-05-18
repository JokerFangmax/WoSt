#ifndef WOST_GEOMETRY_BACKEND_HPP
#define WOST_GEOMETRY_BACKEND_HPP

#include "utils.hpp"
#include <string>
#include <vector>

namespace wost {

// ===========================================================================
// WoStGeometryBackend
// ===========================================================================
class WoStGeometryBackend {
public:
    // -----------------------------------------------------------------------
    // Construction
    // -----------------------------------------------------------------------
    explicit WoStGeometryBackend(const std::string& objFile);
    ~WoStGeometryBackend();

    WoStGeometryBackend(const WoStGeometryBackend&)            = delete;
    WoStGeometryBackend& operator=(const WoStGeometryBackend&) = delete;

    // -----------------------------------------------------------------------
    // (1) Closest point on ∂Ω
    //     BVH traversal: O(log N) expected.
    //     Fill bp; return the Euclidean distance.
    // -----------------------------------------------------------------------
    float ClosestPoint(const vec3& x, BoundaryPoint& bp) const;

    // -----------------------------------------------------------------------
    // (2) Star-shaped ball radius
    //     = min( closest-boundary-dist, closest-silhouette-dist )
    //
    //     The two-argument overload also returns the two contributing points,
    //     which is useful for debugging and for reading Dirichlet BCs at
    //     termination.
    // -----------------------------------------------------------------------
    float StarRadius(const vec3& x) const;
    float StarRadius(const vec3& x,
                     BoundaryPoint& closestBoundary,
                     BoundaryPoint& closestSilhouette) const;

    // -----------------------------------------------------------------------
    // (3) Ray–boundary intersection
    //     Returns true if the ray [origin, origin + tMax*dir] hits ∂Ω.
    //     On hit, sets t (parametric), hitNormal (outward), primIdx.
    //     Wrap of BVH::Intersect with normal reconstruction from barycentric
    //     coordinates.
    // -----------------------------------------------------------------------
    bool IntersectRay(const vec3& origin, const vec3& dir, float tMax,
                      float& t, vec3& hitNormal, uint32_t& primIdx) const;

    // -----------------------------------------------------------------------
    // (4) Inside/outside test
    //     Ray-casting along a fixed direction; odd crossing count → inside.
    //     Uses BVH::Intersect in a loop until tMax is exhausted.
    // -----------------------------------------------------------------------
    bool IsInside(const vec3& x) const;

    // -----------------------------------------------------------------------
    // Accessors
    // -----------------------------------------------------------------------
    uint32_t TriangleCount() const { return numTriangles; }
    const vec4* Vertices()   const { return triangles;    }
    const vec3& TriNormal(uint32_t i) const { return triNormals[i]; }
    const std::vector<SilhouetteEdge>& Silhouettes() const { return silhouettes; }

    void MeshBounds(vec3& outMin, vec3& outMax) const {
        outMin = bvh.aabbMin; outMax = bvh.aabbMax;
    }

private:
    // --- geometry primitives ------------------------------------------------
    static vec3  ClosestPtOnTriangle(const vec3& p,
                                     const vec3& a, const vec3& b, const vec3& c);
    static float PointAABBDist2     (const vec3& p,
                                     const vec3& bmin, const vec3& bmax);
    static float PointSegDist2      (const vec3& p,
                                     const vec3& a, const vec3& b, vec3& closest);
    // --- BVH traversals -----------------------------------------------------
    float ClosestPointBVH   (const vec3& x, BoundaryPoint& out) const;
    float ClosestSilhouette (const vec3& x, BoundaryPoint& out) const;
    // --- build-time helpers -------------------------------------------------
    void LoadOBJ              (const std::string& path);
    void ComputeNormals       ();
    void BuildSilhouetteEdges ();

    // --- data ---------------------------------------------------------------
    tinybvh::BVH bvh;

    // Flat SOA: triangle i has vertices at triangles[i*3 + {0,1,2}]
    vec4*    triangles    = nullptr;
    uint32_t numTriangles = 0;
    uint32_t numVertices  = 0;

    std::vector<vec3>           triNormals;
    std::vector<SilhouetteEdge> silhouettes;
};

} // namespace wost

#endif
