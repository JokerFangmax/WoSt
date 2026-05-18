#ifndef WOST_GEOMETRY_BACKEND_HPP
#define WOST_GEOMETRY_BACKEND_HPP

#include "utils.hpp"
#include <string>
#include <vector>

#ifdef __AVX512F__
#include <immintrin.h>
#endif

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
    // --- AVX-512 SoA silhouette data ----------------------------------------
    struct SilhouetteSoA {
        std::vector<float> v0x, v0y, v0z;
        std::vector<float> v1x, v1y, v1z;
        std::vector<float> n0x, n0y, n0z;
        std::vector<float> n1x, n1y, n1z;

        void build(const std::vector<SilhouetteEdge>& silhouettes) {
            size_t n = silhouettes.size();
            v0x.resize(n); v0y.resize(n); v0z.resize(n);
            v1x.resize(n); v1y.resize(n); v1z.resize(n);
            n0x.resize(n); n0y.resize(n); n0z.resize(n);
            n1x.resize(n); n1y.resize(n); n1z.resize(n);
            
            for (size_t i = 0; i < n; ++i) {
                v0x[i] = silhouettes[i].v0.x; v0y[i] = silhouettes[i].v0.y; v0z[i] = silhouettes[i].v0.z;
                v1x[i] = silhouettes[i].v1.x; v1y[i] = silhouettes[i].v1.y; v1z[i] = silhouettes[i].v1.z;
                n0x[i] = silhouettes[i].n0.x; n0y[i] = silhouettes[i].n0.y; n0z[i] = silhouettes[i].n0.z;
                n1x[i] = silhouettes[i].n1.x; n1y[i] = silhouettes[i].n1.y; n1z[i] = silhouettes[i].n1.z;
            }
        }
    };
    SilhouetteSoA silhouetteSoA;
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
#ifdef __AVX512F__
    float ClosestSilhouetteSIMD(const vec3& x, BoundaryPoint& out) const;
#endif
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
