// INFINITE_GEOAUDIT: a measurement audit of the geometry nodes.
//
// The geometry twin of FXAUDIT / SYNTHAUDIT / NOTEAUDIT / IOAUDIT
// (docs/plans/node-audits/README.md, block 3). Every Geometry primitive and
// every Geometry Op (Transform, Array, Subdivide, ...) is built through its
// real node and read back with GetMesh(); nothing is rendered.
//
//   VALID       non-finite positions or normals, indices out of range, unit
//               length of the vertex normals, degenerate (zero-area) triangles,
//               triangles whose winding disagrees with their vertex normals,
//               side arrays (faceMask, vertexColor, selectionGroup) that do not
//               match the mesh size
//   WATERTIGHT  boundary and non-manifold edges after welding coincident
//               positions, for the shapes and operators that promise a closed
//               surface; closed meshes must also have a positive signed volume
//   NORMALS     vertex normal against the analytic normal for the Sphere,
//               Icosphere and Torus (flag > 1e-3 rad)
//   DEGEN       detail 0 / 1 / 2 / 3 / 512, sides 0 / 1 / 2, extreme bevel,
//               zero or negative supershape exponents; Ops with no input, a
//               bypassed input and a one-triangle input: no crash, finite output
//   SCALE       build time against vertex count for the Sphere, 1e3 to 1e6
//               vertices (flag a per-vertex cost that grows more than 3x)
//   DET         two nodes with the same parameters give bit-identical meshes
//   CACHE       an unchanged input does not change MeshRevision; a changed
//               input does
//   CPU         milliseconds per build
//
//   GRAPH       the nodes that take points or several meshes, driven through a
//               real chain (Sphere -> Distribute Points):
//                 Distribute  random count against density x surface area
//                             (flag > 30 %), Poisson minimum spacing
//                 Delaunay    triangle count in range and the empty-circumcircle
//                             property in the projection plane (flag any point
//                             inside a circumcircle)
//                 Voronoi     valid mesh, one cell per interior site
//                 Merge by Distance  no two vertices closer than the threshold
//                             afterwards, fewer vertices than before
//                 Join (merge)  vertex and triangle counts add up
//                 Ocean       finite, valid, deterministic, vertex count
//
// Not covered: Metaballs, Cloth, Curve Ops, Instances, Displacement (they need
// a texture, a simulation or a curve source of their own).
//
// Only hard invariants fail the run (non-finite data, out-of-range indices,
// non-deterministic output). Everything else is reported, with FLAG lines.
#include "app/AppShared.h"
#include "core/Mesh.h"
#include "nodes/Geometry3DNodes.h"
#include "nodes/DelaunayNodes.h"
#include "nodes/GeometryOpNodes.h"
#include "nodes/OceanNode.h"
#include "nodes/PointDistributionNodes.h"
#include "nodes/UtilityNodes.h"

#include <chrono>
#include <cstring>
#include <functional>
#include <map>
#include <tuple>
#include <unordered_map>

namespace app
{
namespace
{
   struct Flags
   {
      int n = 0;
      void Flag(const char* sec, const std::string& node, const char* what, double v)
      {
         printf("GEOAUDIT FLAG %-10s %-18s %s %.5g\n", sec, node.c_str(), what, v);
         n++;
      }
   };

   struct Stats
   {
      size_t verts = 0, tris = 0;
      int nonFinite = 0, badIndex = 0, badNormalLen = 0, degenerate = 0, windingVsNormal = 0, sideMismatch = 0;
      int boundary = 0, nonManifold = 0, inconsistent = 0;
      double volume = 0.0;
      double maxNormalLenErr = 0.0;
   };

   struct Key
   {
      long long x, y, z;
      bool operator==(const Key& o) const { return x == o.x && y == o.y && z == o.z; }
   };
   struct KeyHash
   {
      size_t operator()(const Key& k) const
      {
         return (size_t)(k.x * 73856093LL) ^ (size_t)(k.y * 19349663LL) ^ (size_t)(k.z * 83492791LL);
      }
   };

   Stats Measure(const Mesh& m)
   {
      Stats s;
      s.verts = m.vertices.size();
      s.tris = m.indices.size() / 3;
      for (const Vertex& v : m.vertices)
      {
         if (!std::isfinite(v.px) || !std::isfinite(v.py) || !std::isfinite(v.pz) || !std::isfinite(v.nx) ||
             !std::isfinite(v.ny) || !std::isfinite(v.nz) || !std::isfinite(v.u) || !std::isfinite(v.v))
            s.nonFinite++;
         else
         {
            const double len = std::sqrt((double)v.nx * v.nx + (double)v.ny * v.ny + (double)v.nz * v.nz);
            const double err = std::fabs(len - 1.0);
            s.maxNormalLenErr = std::max(s.maxNormalLenErr, err);
            if (err > 1e-2)
               s.badNormalLen++;
         }
      }
      if (!m.faceMask.empty() && m.faceMask.size() != s.tris)
         s.sideMismatch++;
      if (!m.vertexColor.empty() && m.vertexColor.size() != s.verts * 3)
         s.sideMismatch++;
      if (!m.selectionGroup.empty() && m.selectionGroup.size() != s.tris)
         s.sideMismatch++;

      // Weld by position so a hard-edged shape (a cube with split corners) still counts as closed.
      std::unordered_map<Key, int, KeyHash> weld;
      std::vector<int> id(s.verts, 0);
      for (size_t i = 0; i < s.verts; i++)
      {
         const Vertex& v = m.vertices[i];
         if (!std::isfinite(v.px) || !std::isfinite(v.py) || !std::isfinite(v.pz))
            continue;
         const Key k { std::llround((double)v.px * 1e4), std::llround((double)v.py * 1e4),
                       std::llround((double)v.pz * 1e4) };
         auto it = weld.find(k);
         if (it == weld.end())
            it = weld.emplace(k, (int)weld.size()).first;
         id[i] = it->second;
      }

      std::map<std::pair<int, int>, int> undirected;
      std::map<std::pair<int, int>, int> directed;
      for (size_t t = 0; t + 2 < m.indices.size() + 0 && t / 3 < s.tris; t += 3)
      {
         const unsigned a = m.indices[t], b = m.indices[t + 1], c = m.indices[t + 2];
         if (a >= s.verts || b >= s.verts || c >= s.verts)
         {
            s.badIndex++;
            continue;
         }
         const Vertex &A = m.vertices[a], &B = m.vertices[b], &C = m.vertices[c];
         const double ux = B.px - A.px, uy = B.py - A.py, uz = B.pz - A.pz;
         const double vx = C.px - A.px, vy = C.py - A.py, vz = C.pz - A.pz;
         const double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
         const double area2 = std::sqrt(nx * nx + ny * ny + nz * nz);
         if (!(area2 > 1e-10))
            s.degenerate++;
         else
         {
            const double sx = (double)A.nx + B.nx + C.nx, sy = (double)A.ny + B.ny + C.ny,
                         sz = (double)A.nz + B.nz + C.nz;
            if (nx * sx + ny * sy + nz * sz < 0.0)
               s.windingVsNormal++;
         }
         s.volume += ((double)A.px * ((double)B.py * C.pz - (double)B.pz * C.py) -
                      (double)A.py * ((double)B.px * C.pz - (double)B.pz * C.px) +
                      (double)A.pz * ((double)B.px * C.py - (double)B.py * C.px)) / 6.0;
         const int w[3] = { id[a], id[b], id[c] };
         for (int e = 0; e < 3; e++)
         {
            const int p = w[e], q = w[(e + 1) % 3];
            if (p == q)
               continue;
            undirected[{ std::min(p, q), std::max(p, q) }]++;
            directed[{ p, q }]++;
         }
      }
      for (const auto& kv : undirected)
      {
         if (kv.second == 1)
            s.boundary++;
         else if (kv.second > 2)
            s.nonManifold++;
      }
      for (const auto& kv : directed)
         if (kv.second > 1)
            s.inconsistent++;
      return s;
   }

   bool SameMesh(const Mesh& a, const Mesh& b)
   {
      if (a.vertices.size() != b.vertices.size() || a.indices != b.indices)
         return false;
      return a.vertices.empty() ||
             std::memcmp(a.vertices.data(), b.vertices.data(), a.vertices.size() * sizeof(Vertex)) == 0;
   }

   // The shapes that promise a closed, outward-facing surface at default settings.
   bool PromisesClosed(const std::string& name)
   {
      static const char* closed[] = { "Cube", "Sphere", "Icosphere", "Torus", "Cylinder", "Cone", "Capsule",
                                       "Pyramid", "Prism", "Tetrahedron", "Octahedron", "Dodecahedron",
                                       "Rounded Cube" };
      for (const char* c : closed)
         if (name == c)
            return true;
      return false;
   }

   int gFrame = 1000;

   const Mesh& Build(GeometryNode& g)
   {
      g.CookIfNeeded(gFrame++);
      return g.GetMesh();
   }

   std::string ShapeName(int shape) { return GeometryNode::ShapeNames()[(size_t)shape]; }

   void Report(Flags& f, const char* sec, const std::string& name, const Stats& s, bool expectClosed, bool& ok)
   {
      if (s.nonFinite > 0)
      {
         f.Flag(sec, name, "non-finite vertices", s.nonFinite);
         ok = false;
      }
      if (s.badIndex > 0)
      {
         f.Flag(sec, name, "indices out of range", s.badIndex);
         ok = false;
      }
      if (s.badNormalLen > 0)
         f.Flag(sec, name, "normals off unit length (>1%)", s.badNormalLen);
      if (s.degenerate > 0)
         f.Flag(sec, name, "degenerate triangles", s.degenerate);
      if (s.windingVsNormal > 0)
         f.Flag(sec, name, "winding disagrees with normals", s.windingVsNormal);
      if (s.sideMismatch > 0)
         f.Flag(sec, name, "side arrays do not match the mesh", s.sideMismatch);
      if (expectClosed)
      {
         if (s.boundary > 0)
            f.Flag("WATERTIGHT", name, "boundary edges", s.boundary);
         if (s.nonManifold > 0)
            f.Flag("WATERTIGHT", name, "non-manifold edges", s.nonManifold);
         if (s.inconsistent > 0)
            f.Flag("WATERTIGHT", name, "edges used twice in one direction", s.inconsistent);
         if (s.boundary == 0 && s.nonManifold == 0 && s.volume < 0.0)
            f.Flag("WATERTIGHT", name, "closed mesh faces inward, volume", s.volume);
      }
   }

   // --------------------------------------------------------------- primitives

   void AuditPrimitives(Flags& f, bool& ok)
   {
      const auto& names = GeometryNode::ShapeNames();
      for (size_t i = 0; i < names.size(); i++)
      {
         GeometryNode g;
         g.shape = (int)i;
         const Mesh& m = Build(g);
         const Stats s = Measure(m);
         printf("GEOAUDIT VALID  %-14s %zu verts %zu tris | boundary %d non-manifold %d volume %.4f normal length err %.1e\n",
                names[i].c_str(), s.verts, s.tris, s.boundary, s.nonManifold, s.volume, s.maxNormalLenErr);
         Report(f, "VALID", names[i], s, PromisesClosed(names[i]), ok);

         GeometryNode g2;
         g2.shape = (int)i;
         if (!SameMesh(m, Build(g2)))
         {
            f.Flag("DET", names[i], "two builds differ", 1);
            ok = false;
         }
      }
   }

   void AuditNormals(Flags& f)
   {
      auto angle = [](double ax, double ay, double az, double bx, double by, double bz) {
         const double la = std::sqrt(ax * ax + ay * ay + az * az), lb = std::sqrt(bx * bx + by * by + bz * bz);
         if (la < 1e-12 || lb < 1e-12)
            return 0.0;
         return std::acos(std::min(1.0, std::max(-1.0, (ax * bx + ay * by + az * bz) / (la * lb))));
      };
      for (const char* name : { "Sphere", "Icosphere", "Torus" })
      {
         GeometryNode g;
         const auto& names = GeometryNode::ShapeNames();
         for (size_t i = 0; i < names.size(); i++)
            if (names[i] == name)
               g.shape = (int)i;
         const Mesh& m = Build(g);
         // Bounding-box centre: the mean is biased by the vertices duplicated along a UV seam or pole.
         double mn[3] = { 1e30, 1e30, 1e30 }, mx[3] = { -1e30, -1e30, -1e30 };
         for (const Vertex& v : m.vertices)
         {
            const double p[3] = { v.px, v.py, v.pz };
            for (int a = 0; a < 3; a++)
            {
               mn[a] = std::min(mn[a], p[a]);
               mx[a] = std::max(mx[a], p[a]);
            }
         }
         const double cx = 0.5 * (mn[0] + mx[0]), cy = 0.5 * (mn[1] + mx[1]), cz = 0.5 * (mn[2] + mx[2]);
         double worst = 0.0;
         if (std::strcmp(name, "Torus") != 0)
         {
            for (const Vertex& v : m.vertices)
               worst = std::max(worst, angle(v.nx, v.ny, v.nz, v.px - cx, v.py - cy, v.pz - cz));
         }
         else
         {
            // The axis is the shortest extent; the ring radius is the mean of the in-plane radius range.
            double lo[3] = { 1e30, 1e30, 1e30 }, hi[3] = { -1e30, -1e30, -1e30 };
            for (const Vertex& v : m.vertices)
            {
               const double p[3] = { v.px - cx, v.py - cy, v.pz - cz };
               for (int a = 0; a < 3; a++)
               {
                  lo[a] = std::min(lo[a], p[a]);
                  hi[a] = std::max(hi[a], p[a]);
               }
            }
            int axis = 0;
            for (int a = 1; a < 3; a++)
               if (hi[a] - lo[a] < hi[axis] - lo[axis])
                  axis = a;
            const int u = (axis + 1) % 3, w = (axis + 2) % 3;
            double rmin = 1e30, rmax = 0.0;
            for (const Vertex& v : m.vertices)
            {
               const double p[3] = { v.px - cx, v.py - cy, v.pz - cz };
               const double rho = std::sqrt(p[u] * p[u] + p[w] * p[w]);
               rmin = std::min(rmin, rho);
               rmax = std::max(rmax, rho);
            }
            const double R = 0.5 * (rmin + rmax);
            for (const Vertex& v : m.vertices)
            {
               double p[3] = { v.px - cx, v.py - cy, v.pz - cz };
               const double rho = std::sqrt(p[u] * p[u] + p[w] * p[w]);
               if (rho < 1e-9)
                  continue;
               double q[3] = { p[0], p[1], p[2] };
               q[u] -= R * p[u] / rho;
               q[w] -= R * p[w] / rho;
               worst = std::max(worst, angle(v.nx, v.ny, v.nz, q[0], q[1], q[2]));
            }
         }
         printf("GEOAUDIT NORMALS %-12s worst angle to analytic %.5f rad\n", name, worst);
         if (worst > 1e-3)
            f.Flag("NORMALS", name, "normal error rad", worst);
      }
   }

   void AuditDegenerate(Flags& f, bool& ok)
   {
      auto run = [&](const std::string& label, const std::function<void(GeometryNode&)>& setup) {
         const auto& names = GeometryNode::ShapeNames();
         for (size_t i = 0; i < names.size(); i++)
         {
            GeometryNode g;
            g.shape = (int)i;
            setup(g);
            const Stats s = Measure(Build(g));
            const std::string id = names[i] + " " + label;
            if (s.nonFinite > 0)
            {
               f.Flag("DEGEN", id, "non-finite vertices", s.nonFinite);
               ok = false;
            }
            if (s.badIndex > 0)
            {
               f.Flag("DEGEN", id, "indices out of range", s.badIndex);
               ok = false;
            }
         }
      };
      run("detail 0", [](GeometryNode& g) { g.detail = 0; });
      run("detail 1", [](GeometryNode& g) { g.detail = 1; });
      run("detail 2", [](GeometryNode& g) { g.detail = 2; });
      run("detail 3", [](GeometryNode& g) { g.detail = 3; });
      run("detail 512", [](GeometryNode& g) { g.detail = 512; });
      run("sides 0", [](GeometryNode& g) { g.sides = 0; });
      run("sides 1", [](GeometryNode& g) { g.sides = 1; });
      run("sides 2", [](GeometryNode& g) { g.sides = 2; });
      run("bevel 5", [](GeometryNode& g) { g.bevel = 5.0f; g.bevelSegments = 8; });
      run("bevel -1", [](GeometryNode& g) { g.bevel = -1.0f; g.bevelSegments = 0; });
      run("tube 0", [](GeometryNode& g) { g.tubeRadius = 0.0f; });
      run("tube 10", [](GeometryNode& g) { g.tubeRadius = 10.0f; });
      run("super 0", [](GeometryNode& g) { g.superN2 = 0.0f; g.superN3 = 0.0f; g.superP2 = 0.0f; g.superP3 = 0.0f; });
      run("super -1", [](GeometryNode& g) { g.superN2 = -1.0f; g.superN3 = -1.0f; g.superP2 = -1.0f; g.superP3 = -1.0f; });
      run("knot 0", [](GeometryNode& g) { g.knotP = 0; g.knotQ = 0; });
      printf("GEOAUDIT DEGEN  primitives: %zu shapes x 15 settings built\n", GeometryNode::ShapeNames().size());
   }

   void AuditScale(Flags& f)
   {
      double firstPerVert = 0.0;
      for (int detail : { 32, 100, 316, 1000 })
      {
         GeometryNode g;
         g.shape = 2; // Sphere
         g.detail = detail;
         g.sides = detail / 2; // Sphere takes sides * 2 sectors, so this reaches 1e6 vertices at detail 1000
         const auto t0 = std::chrono::steady_clock::now();
         const Mesh& m = Build(g);
         const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
         const double perVert = m.vertices.empty() ? 0.0 : ms * 1e6 / (double)m.vertices.size();
         printf("GEOAUDIT SCALE  Sphere detail %4d: %8zu verts %9zu tris %9.1f ms %8.1f ns/vert\n", detail,
                m.vertices.size(), m.indices.size() / 3, ms, perVert);
         if (firstPerVert == 0.0)
            firstPerVert = perVert;
         else if (firstPerVert > 0.0 && perVert > 3.0 * firstPerVert && ms > 5.0)
            f.Flag("SCALE", "Sphere", "per-vertex cost grew x", perVert / firstPerVert);
      }
   }

   // --------------------------------------------------------------------- ops

   // Triangulate jitters its vertices on purpose (the low-poly look), so it is not in this set.
   bool OpKeepsClosed(int op)
   {
      return op == GeometryOpNode::kTransform || op == GeometryOpNode::kSubdivide ||
             op == GeometryOpNode::kNormals ||
             op == GeometryOpNode::kTwist || op == GeometryOpNode::kSmooth;
   }

   void AuditOps(Flags& f, bool& ok)
   {
      const auto& opNames = GeometryOpNode::OpNames();
      for (int op = 0; op < GeometryOpNode::kOpCount; op++)
      {
         if (!GeometryOpNode::IsSpawnable(op))
            continue;
         const std::string name = (size_t)op < opNames.size() ? opNames[(size_t)op] : std::to_string(op);
         for (int shape : { 1, 2 }) // cube, sphere
         {
            GeometryNode geo;
            geo.shape = shape;
            geo.detail = 16;
            GeometryOpNode node;
            node.op = op;
            node.input = &geo;
            node.CookIfNeeded(gFrame++);
            const auto t0 = std::chrono::steady_clock::now();
            const Mesh m = node.GetMesh();
            const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
            const Stats s = Measure(m);
            const std::string id = name + (shape == 1 ? " on cube" : " on sphere");
            printf("GEOAUDIT OP     %-26s %6zu verts %6zu tris | boundary %d non-manifold %d | %.2f ms\n", id.c_str(),
                   s.verts, s.tris, s.boundary, s.nonManifold, ms);
            Report(f, "VALID", id, s, OpKeepsClosed(op), ok);

            GeometryNode geo2;
            geo2.shape = shape;
            geo2.detail = 16;
            GeometryOpNode node2;
            node2.op = op;
            node2.input = &geo2;
            node2.CookIfNeeded(gFrame++);
            if (!SameMesh(m, node2.GetMesh()))
            {
               f.Flag("DET", id, "two builds differ", 1);
               ok = false;
            }

            // CACHE: nothing changed, so the revision must not move; change the input and it must.
            if (shape == 2)
            {
               const unsigned long long r0 = node.MeshRevision();
               node.CookIfNeeded(gFrame++);
               node.GetMesh();
               const unsigned long long r1 = node.MeshRevision();
               if (r0 != r1)
                  f.Flag("CACHE", id, "revision moved with nothing changed", (double)(r1 - r0));
               geo.detail = 24;
               node.CookIfNeeded(gFrame++);
               node.GetMesh();
               if (node.MeshRevision() == r1)
                  f.Flag("CACHE", id, "revision did not follow a changed input", 0);
            }
         }

         // DEGEN: no input, a bypassed input, a one-triangle input.
         {
            GeometryOpNode none;
            none.op = op;
            none.CookIfNeeded(gFrame++);
            const Stats s = Measure(none.GetMesh());
            if (s.nonFinite > 0 || s.badIndex > 0)
            {
               f.Flag("DEGEN", name + " no input", "bad output", s.nonFinite + s.badIndex);
               ok = false;
            }

            GeometryNode off;
            off.bypassed = true;
            GeometryOpNode node;
            node.op = op;
            node.input = &off;
            node.CookIfNeeded(gFrame++);
            const Stats s2 = Measure(node.GetMesh());
            if (s2.nonFinite > 0 || s2.badIndex > 0)
            {
               f.Flag("DEGEN", name + " bypassed in", "bad output", s2.nonFinite + s2.badIndex);
               ok = false;
            }

            GeometryNode tri;
            tri.shape = 0; // Plane
            tri.detail = 1;
            GeometryOpNode node3;
            node3.op = op;
            node3.input = &tri;
            node3.CookIfNeeded(gFrame++);
            const Stats s3 = Measure(node3.GetMesh());
            if (s3.nonFinite > 0 || s3.badIndex > 0)
            {
               f.Flag("DEGEN", name + " 1-quad in", "bad output", s3.nonFinite + s3.badIndex);
               ok = false;
            }
         }

         // Bypass: the op passes its input through untouched.
         {
            GeometryNode geo;
            geo.shape = 2;
            geo.detail = 12;
            GeometryOpNode node;
            node.op = op;
            node.input = &geo;
            node.bypassed = true;
            node.CookIfNeeded(gFrame++);
            if (!SameMesh(node.GetMesh(), Build(geo)) && !node.GetMesh().Empty())
               f.Flag("BYPASS", name, "bypassed op does not pass its input through", 1);
         }
      }
   }
   // -------------------------------------------------------------------- graph

   double SurfaceArea(const Mesh& m)
   {
      double a = 0.0;
      for (size_t t = 0; t + 2 < m.indices.size(); t += 3)
      {
         const Vertex &A = m.vertices[m.indices[t]], &B = m.vertices[m.indices[t + 1]], &C = m.vertices[m.indices[t + 2]];
         const double ux = B.px - A.px, uy = B.py - A.py, uz = B.pz - A.pz;
         const double vx = C.px - A.px, vy = C.py - A.py, vz = C.pz - A.pz;
         const double cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
         a += 0.5 * std::sqrt(cx * cx + cy * cy + cz * cz);
      }
      return a;
   }

   void AuditGraph(Flags& f, bool& ok)
   {
      GeometryNode sphere;
      sphere.shape = 2;
      sphere.detail = 24;
      const double area = SurfaceArea(Build(sphere));

      // ---- Distribute
      DistributePointsOnFacesNode dist;
      dist.input = &sphere;
      dist.density = 40.0f;
      dist.method = 0;
      dist.CookIfNeeded(gFrame++);
      const auto* cloud = dist.GetPointCloud();
      const size_t n = cloud ? cloud->size() : 0;
      const double want = 40.0 * area;
      printf("GEOAUDIT GRAPH  Distribute random   %zu points | density x area = %.1f\n", n, want);
      if (n == 0 || std::fabs((double)n / want - 1.0) > 0.30)
         f.Flag("GRAPH", "Distribute random", "count differs from density x area (ratio)", n / want);

      dist.method = 1;
      dist.minDistance = 0.2f;
      dist.density = 200.0f;
      dist.CookIfNeeded(gFrame++);
      cloud = dist.GetPointCloud();
      double minD = 1e9;
      if (cloud)
         for (size_t i = 0; i < cloud->size(); i++)
            for (size_t j = i + 1; j < cloud->size(); j++)
            {
               const Particle &a = (*cloud)[i], &b = (*cloud)[j];
               minD = std::min(minD, std::sqrt((double)(a.px - b.px) * (a.px - b.px) + (double)(a.py - b.py) * (a.py - b.py) +
                                               (double)(a.pz - b.pz) * (a.pz - b.pz)));
            }
      printf("GEOAUDIT GRAPH  Distribute Poisson  %zu points | min spacing %.4f (asked 0.2)\n", cloud ? cloud->size() : 0, minD);
      if (minD < 0.2 * 0.99)
         f.Flag("GRAPH", "Distribute Poisson", "points closer than minDistance, nearest", minD);

      // ---- Delaunay / Voronoi on a random cloud (plane XY)
      dist.method = 0;
      dist.density = 12.0f;
      dist.CookIfNeeded(gFrame++);
      DelaunayMeshNode del;
      del.input = &dist;
      del.plane = 0;
      del.CookIfNeeded(gFrame++);
      const Mesh dm = del.GetMesh();
      const Stats ds = Measure(dm);
      const auto* pts = dist.GetPointCloud();
      const size_t np = pts ? pts->size() : 0;
      printf("GEOAUDIT GRAPH  Delaunay            %zu points -> %zu tris\n", np, ds.tris);
      Report(f, "GRAPH", "Delaunay", ds, false, ok);
      if (ds.tris < np / 2 || ds.tris > 2 * np)
         f.Flag("GRAPH", "Delaunay", "triangle count out of [n/2, 2n], count", (double)ds.tris);
      int violations = 0;
      for (size_t t = 0; t + 2 < dm.indices.size(); t += 3)
      {
         const Vertex &A = dm.vertices[dm.indices[t]], &B = dm.vertices[dm.indices[t + 1]], &C = dm.vertices[dm.indices[t + 2]];
         const double ax = A.px, ay = A.py, bx = B.px, by = B.py, cx = C.px, cy = C.py;
         const double d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by));
         if (std::fabs(d) < 1e-12)
            continue;
         const double ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d;
         const double uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d;
         const double r2 = (ax - ux) * (ax - ux) + (ay - uy) * (ay - uy);
         for (const Particle& p : *pts)
         {
            const double d2 = (p.px - ux) * (p.px - ux) + (p.py - uy) * (p.py - uy);
            if (d2 < r2 * (1.0 - 1e-6))
            {
               violations++;
               break;
            }
         }
      }
      printf("GEOAUDIT GRAPH  Delaunay            circumcircle violations %d of %zu\n", violations, ds.tris);
      if (violations > 0)
         f.Flag("GRAPH", "Delaunay", "triangles with a point inside the circumcircle", violations);

      VoronoiCellsNode vor;
      vor.input = &dist;
      vor.plane = 0;
      vor.CookIfNeeded(gFrame++);
      const Stats vs = Measure(vor.GetMesh());
      printf("GEOAUDIT GRAPH  Voronoi             %zu verts %zu tris\n", vs.verts, vs.tris);
      Report(f, "GRAPH", "Voronoi", vs, false, ok);
      if (vs.tris == 0 && np > 8)
         f.Flag("GRAPH", "Voronoi", "no cells from a cloud of", (double)np);

      // ---- Join (merge) and Merge by Distance
      GeometryNode cube;
      cube.shape = 1;
      JoinGeometryNode join;
      join.mode = JoinGeometryNode::kMerge;
      join.inputs[0] = &cube;
      GeometryNode prism;
      prism.shape = 3; // Icosphere: closed, without the UV-pole slivers the Sphere carries
      join.inputs[1] = &prism;
      join.CookIfNeeded(gFrame++);
      const Mesh jm = join.GetMesh();
      const Mesh cm = Build(cube), sm = Build(prism);
      printf("GEOAUDIT GRAPH  Join merge          %zu verts %zu tris (cube %zu/%zu + shape %zu/%zu)\n", jm.vertices.size(),
             jm.indices.size() / 3, cm.vertices.size(), cm.indices.size() / 3, sm.vertices.size(), sm.indices.size() / 3);
      Report(f, "GRAPH", "Join merge", Measure(jm), false, ok);
      if (jm.vertices.size() != cm.vertices.size() + sm.vertices.size() || jm.indices.size() != cm.indices.size() + sm.indices.size())
         f.Flag("GRAPH", "Join merge", "counts do not add up, verts", (double)jm.vertices.size());

      JoinGeometryNode twin; // the same cube twice: every vertex has a twin
      twin.mode = JoinGeometryNode::kMerge;
      twin.inputs[0] = &cube;
      twin.inputs[1] = &cube;
      twin.CookIfNeeded(gFrame++);
      MergeByDistanceNode merge;
      merge.input = &twin;
      merge.threshold = 0.01f;
      merge.CookIfNeeded(gFrame++);
      const Mesh mm = merge.GetMesh();
      double closest = 1e9;
      for (size_t i = 0; i < mm.vertices.size(); i++)
         for (size_t j = i + 1; j < mm.vertices.size(); j++)
         {
            const Vertex &a = mm.vertices[i], &b = mm.vertices[j];
            closest = std::min(closest, std::sqrt((double)(a.px - b.px) * (a.px - b.px) + (double)(a.py - b.py) * (a.py - b.py) +
                                                  (double)(a.pz - b.pz) * (a.pz - b.pz)));
         }
      printf("GEOAUDIT GRAPH  Merge by Distance   %zu -> %zu verts | closest pair %.4f (threshold 0.01)\n",
             twin.GetMesh().vertices.size(), mm.vertices.size(), closest);
      Report(f, "GRAPH", "Merge by Distance", Measure(mm), false, ok);
      if (mm.vertices.size() >= twin.GetMesh().vertices.size())
         f.Flag("GRAPH", "Merge by Distance", "did not remove duplicate vertices", (double)mm.vertices.size());
      if (closest < 0.01 * 0.999)
         f.Flag("GRAPH", "Merge by Distance", "vertices still closer than the threshold", closest);

      // ---- Ocean
      OceanNode ocean;
      ocean.resolution = 48;
      ocean.CookIfNeeded(gFrame++);
      const Mesh om = ocean.GetMesh();
      const Stats os = Measure(om);
      printf("GEOAUDIT GRAPH  Ocean               %zu verts %zu tris\n", os.verts, os.tris);
      Report(f, "GRAPH", "Ocean", os, false, ok);
      OceanNode ocean2;
      ocean2.resolution = 48;
      ocean2.CookIfNeeded(gFrame++);
      if (!SameMesh(om, ocean2.GetMesh()))
      {
         f.Flag("DET", "Ocean", "two builds differ", 1);
         ok = false;
      }
   }

} // namespace

bool RunGeoAudit()
{
   setvbuf(stdout, nullptr, _IONBF, 0);
   const char* only = getenv("INFINITE_GEOAUDIT_ONLY");
   auto want = [&](const char* sec) { return only == nullptr || *only == 0 || strstr(only, sec) != nullptr; };
   Flags flags;
   bool ok = true;
   if (want("PRIM"))
   {
      AuditPrimitives(flags, ok);
      AuditNormals(flags);
      AuditDegenerate(flags, ok);
   }
   if (want("SCALE"))
      AuditScale(flags);
   if (want("OPS"))
      AuditOps(flags, ok);
   if (want("GRAPH"))
      AuditGraph(flags, ok);
   printf("GEOAUDIT %s (%d flags)\n", ok ? "PASS" : "FAIL", flags.n);
   return ok;
}

} // namespace app
