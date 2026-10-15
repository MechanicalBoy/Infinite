#include "ProximityLinesNode.h"

#include <algorithm>
#include <cmath>
#include <thread>

namespace
{
   const Mesh kEmptyMesh;
}

void ProximityLinesNode::FindLinks(const float* xyz, size_t count, float radius, int maxPerPoint,
                                   size_t maxLinks, std::vector<std::pair<unsigned int, unsigned int>>& out)
{
   out.clear();
   if (count < 2 || radius <= 0.0f || maxLinks == 0)
      return;
   const int K = std::clamp(maxPerPoint, 1, 16);

   float lo[3] = { xyz[0], xyz[1], xyz[2] }, hi[3] = { xyz[0], xyz[1], xyz[2] };
   for (size_t i = 1; i < count; i++)
      for (int a = 0; a < 3; a++)
      {
         lo[a] = std::min(lo[a], xyz[i * 3 + a]);
         hi[a] = std::max(hi[a], xyz[i * 3 + a]);
      }

   // A cell is never smaller than the radius, so every neighbour is in the 27 cells around
   // a point; when the radius is tiny against the extent the cells grow to keep the grid
   // under ~4M cells (more candidates per cell, still exact). Half-radius cells were tried
   // and are slower: more, emptier runs cost more than the saved distance tests.
   float cell = radius;
   for (;;)
   {
      double cells = 1.0;
      for (int a = 0; a < 3; a++)
         cells *= std::floor((hi[a] - lo[a]) / cell) + 1.0;
      if (cells <= 4.0e6)
         break;
      cell *= 1.5f;
   }
   int dim[3];
   for (int a = 0; a < 3; a++)
      dim[a] = (int)std::floor((hi[a] - lo[a]) / cell) + 1;
   const int h = 1; // cells to look out in each direction
   const float inv = 1.0f / cell;
   auto coord = [&](const float* p, int a) { return std::min(dim[a] - 1, (int)((p[a] - lo[a]) * inv)); };

   // Counting sort by cell; the positions are copied in cell order so a cell's points sit
   // together in memory.
   const size_t ncell = (size_t)dim[0] * dim[1] * dim[2];
   std::vector<unsigned int> start(ncell + 1, 0), order(count), cellOf(count);
   for (size_t i = 0; i < count; i++)
   {
      const float* p = &xyz[i * 3];
      cellOf[i] = (unsigned int)(((size_t)coord(p, 2) * dim[1] + coord(p, 1)) * dim[0] + coord(p, 0));
      start[cellOf[i] + 1]++;
   }
   for (size_t c = 0; c < ncell; c++)
      start[c + 1] += start[c];
   std::vector<float> sorted(count * 3);
   {
      std::vector<unsigned int> fill(start.begin(), start.end() - 1);
      for (size_t i = 0; i < count; i++)
      {
         const unsigned int s = fill[cellOf[i]]++;
         order[s] = (unsigned int)i;
         for (int a = 0; a < 3; a++)
            sorted[s * 3 + a] = xyz[i * 3 + a];
      }
   }

   // Every point reaches for its K nearest neighbours inside the radius (ties go to the
   // lower index, so the answer does not depend on thread timing). Each point writes only
   // its own row, so the sorted points split across threads with no locking.
   const float r2 = radius * radius;
   std::vector<unsigned int> nbr(count * (size_t)K);
   std::vector<unsigned char> nbrCount(count, 0);
   auto reach = [&](size_t from, size_t to)
   {
      float bd[16];
      unsigned int bi[16];
      for (size_t s = from; s < to; s++)
      {
         const float* p = &sorted[s * 3];
         const unsigned int self = order[s];
         int n = 0;
         const int cx = coord(p, 0), cy = coord(p, 1), cz = coord(p, 2);
         // Three cells in a row are neighbours in memory, so each (z, y) row is one run.
         const int x0 = std::max(0, cx - h), x1 = std::min(dim[0] - 1, cx + h);
         for (int z = std::max(0, cz - h); z <= std::min(dim[2] - 1, cz + h); z++)
            for (int y = std::max(0, cy - h); y <= std::min(dim[1] - 1, cy + h); y++)
            {
               const size_t row = ((size_t)z * dim[1] + y) * dim[0];
               for (unsigned int t = start[row + x0], tEnd = start[row + x1 + 1]; t < tEnd; t++)
               {
                  const float dx = sorted[t * 3] - p[0], dy = sorted[t * 3 + 1] - p[1], dz = sorted[t * 3 + 2] - p[2];
                  const float d2 = dx * dx + dy * dy + dz * dz;
                  if (d2 > r2)
                     continue;
                  const unsigned int id = order[t];
                  if (id == self)
                     continue;
                  if (n == K && !(d2 < bd[K - 1] || (d2 == bd[K - 1] && id < bi[K - 1])))
                     continue;
                  int m = n < K ? n++ : K - 1;
                  while (m > 0 && (bd[m - 1] > d2 || (bd[m - 1] == d2 && bi[m - 1] > id)))
                  {
                     bd[m] = bd[m - 1];
                     bi[m] = bi[m - 1];
                     m--;
                  }
                  bd[m] = d2;
                  bi[m] = id;
               }
            }
         std::copy(bi, bi + n, &nbr[(size_t)self * K]);
         nbrCount[self] = (unsigned char)n;
      }
   };
   const unsigned int hw = std::max(1u, std::min(8u, std::thread::hardware_concurrency()));
   const unsigned int workers = count >= 20000 ? hw : 1u;
   {
      std::vector<std::thread> pool;
      const size_t chunk = (count + workers - 1) / workers;
      for (unsigned int w = 1; w < workers; w++)
         pool.emplace_back(reach, std::min(count, w * chunk), std::min(count, (w + 1) * chunk));
      reach(0, std::min(count, chunk));
      for (std::thread& t : pool)
         t.join();
   }

   // A pair reached from either end is drawn once: from the lower index when both reach,
   // from whichever end reaches otherwise. Chunks are joined in index order, so the link
   // order is fixed.
   auto has = [&](unsigned int row, unsigned int id)
   {
      const unsigned int* r = &nbr[(size_t)row * K];
      for (int m = 0; m < nbrCount[row]; m++)
         if (r[m] == id)
            return true;
      return false;
   };
   std::vector<std::vector<std::pair<unsigned int, unsigned int>>> parts(workers);
   auto emit = [&](unsigned int w, size_t from, size_t to)
   {
      auto& v = parts[w];
      for (size_t i = from; i < to; i++)
         for (int m = 0; m < nbrCount[i]; m++)
         {
            const unsigned int j = nbr[i * K + m];
            if (i < j || !has(j, (unsigned int)i))
               v.push_back({ (unsigned int)std::min<size_t>(i, j), (unsigned int)std::max<size_t>(i, j) });
         }
   };
   {
      std::vector<std::thread> pool;
      const size_t chunk = (count + workers - 1) / workers;
      for (unsigned int w = 1; w < workers; w++)
         pool.emplace_back(emit, w, std::min(count, w * chunk), std::min(count, (w + 1) * chunk));
      emit(0, 0, std::min(count, chunk));
      for (std::thread& t : pool)
         t.join();
   }
   size_t total = 0;
   for (const auto& v : parts)
      total += v.size();
   out.reserve(std::min(total, maxLinks));
   for (const auto& v : parts)
      for (const auto& l : v)
      {
         if (out.size() >= maxLinks)
            return;
         out.push_back(l);
      }
}

void ProximityLinesNode::RebuildIfNeeded()
{
   if (input == nullptr)
   {
      if (!mCache.vertices.empty())
      {
         mCache = Mesh();
         mLinks = 0;
         mMeshRevision = NextMeshRevision();
      }
      mBuiltInput = nullptr;
      return;
   }

   const std::vector<Particle>* cloud = input->GetPointCloud();
   const unsigned long long upstream = cloud ? input->PointCloudRevision() : input->MeshRevision();
   if (mBuiltInput == input && mBuiltUpstream == upstream && mBuiltRadius == radius &&
       mBuiltThickness == thickness && mBuiltMaxPerPoint == maxPerPoint && mBuiltMaxLinks == maxLinks &&
       mBuiltAliveOnly == aliveOnly)
      return;

   std::vector<float> pos, col;
   bool anyColor = false;
   if (cloud != nullptr)
   {
      pos.reserve(cloud->size() * 3);
      for (const Particle& p : *cloud)
         if (!(aliveOnly && !p.alive))
            anyColor = anyColor || p.hasColor;
      if (anyColor)
         col.reserve(cloud->size() * 3);
      for (const Particle& p : *cloud)
      {
         if (aliveOnly && !p.alive)
            continue;
         pos.push_back(p.px); pos.push_back(p.py); pos.push_back(p.pz);
         if (anyColor)
         {
            col.push_back(p.r); col.push_back(p.g); col.push_back(p.b);
         }
      }
   }
   else
   {
      const Mesh& src = input->GetMesh();
      pos.reserve(src.vertices.size() * 3);
      for (const Vertex& v : src.vertices)
      {
         pos.push_back(v.px); pos.push_back(v.py); pos.push_back(v.pz);
      }
      if (src.vertexColor.size() == src.vertices.size() * 3)
      {
         anyColor = true;
         col = src.vertexColor;
      }
   }

   std::vector<std::pair<unsigned int, unsigned int>> links;
   FindLinks(pos.data(), pos.size() / 3, radius, maxPerPoint, (size_t)std::clamp(maxLinks, 1, 200000), links);

   // One three-sided prism per link: six vertices, six triangles. Vertex colour (when the
   // points had real colour) rides alongside, one triple per vertex, so the line fades
   // between its two ends.
   Mesh out;
   out.vertices.reserve(links.size() * 6);
   out.indices.reserve(links.size() * 18);
   if (anyColor)
      out.vertexColor.reserve(links.size() * 18);
   const float t = std::max(0.0005f, thickness);
   for (const auto& l : links)
   {
      const float* a = &pos[l.first * 3];
      const float* b = &pos[l.second * 3];
      float d[3] = { b[0] - a[0], b[1] - a[1], b[2] - a[2] };
      const float len = std::sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2]);
      if (len < 1e-8f)
         continue;
      for (float& c : d) c /= len;
      float up[3] = { 0, 1, 0 };
      if (std::fabs(d[1]) > 0.9f) { up[0] = 1; up[1] = 0; }
      float s[3] = { d[1] * up[2] - d[2] * up[1], d[2] * up[0] - d[0] * up[2], d[0] * up[1] - d[1] * up[0] };
      const float sl = std::sqrt(s[0] * s[0] + s[1] * s[1] + s[2] * s[2]);
      for (float& c : s) c /= sl;
      const float o[3] = { d[1] * s[2] - d[2] * s[1], d[2] * s[0] - d[0] * s[2], d[0] * s[1] - d[1] * s[0] };
      const unsigned int base = (unsigned int)out.vertices.size();
      for (int end = 0; end < 2; end++)
      {
         const float* p = end == 0 ? a : b;
         const unsigned int idx = end == 0 ? l.first : l.second;
         for (int k = 0; k < 3; k++)
         {
            const float ang = 6.2831853f * (float)k / 3.0f;
            const float cs = std::cos(ang), sn = std::sin(ang);
            Vertex v;
            v.nx = s[0] * cs + o[0] * sn; v.ny = s[1] * cs + o[1] * sn; v.nz = s[2] * cs + o[2] * sn;
            v.px = p[0] + v.nx * t; v.py = p[1] + v.ny * t; v.pz = p[2] + v.nz * t;
            v.u = (float)end; v.v = (float)k / 3.0f;
            out.vertices.push_back(v);
            if (anyColor)
            {
               out.vertexColor.push_back(col[idx * 3]);
               out.vertexColor.push_back(col[idx * 3 + 1]);
               out.vertexColor.push_back(col[idx * 3 + 2]);
            }
         }
      }
      for (unsigned int k = 0; k < 3; k++)
      {
         const unsigned int k1 = (k + 1) % 3;
         out.indices.insert(out.indices.end(), { base + k, base + k1, base + 3 + k1,
                                                 base + k, base + 3 + k1, base + 3 + k });
      }
   }

   mLinks = out.vertices.size() / 6;
   mCache = std::move(out);
   mBuiltInput = input;
   mBuiltUpstream = upstream;
   mBuiltRadius = radius;
   mBuiltThickness = thickness;
   mBuiltMaxPerPoint = maxPerPoint;
   mBuiltMaxLinks = maxLinks;
   mBuiltAliveOnly = aliveOnly;
   mMeshRevision = NextMeshRevision();
}

const Mesh& ProximityLinesNode::GetMesh()
{
   if (bypassed)
      return input ? input->GetMesh() : kEmptyMesh;
   RebuildIfNeeded();
   return mCache;
}

unsigned long long ProximityLinesNode::MeshRevision()
{
   if (bypassed)
      return input ? input->MeshRevision() : 0;
   RebuildIfNeeded();
   return mMeshRevision;
}

Material ProximityLinesNode::GetMaterial() const
{
   if (inheritMaterial && input != nullptr)
      return input->GetMaterial();
   Material m;
   m.color[0] = color[0]; m.color[1] = color[1]; m.color[2] = color[2];
   m.metallic = metallic;
   m.roughness = roughness;
   m.opacity = opacity;
   m.emissionColor[0] = emissionColor[0];
   m.emissionColor[1] = emissionColor[1];
   m.emissionColor[2] = emissionColor[2];
   m.emission = emission;
   return m;
}

unsigned long long ProximityLinesNode::MaterialRevision() const
{
   return ComputeContentRevision(GetMaterial(), mMaterialRevision, mLastMaterialHash);
}

void ProximityLinesNode::CookIfNeeded(int frameId)
{
   if (mLastCookFrame == frameId)
      return;
   mLastCookFrame = frameId;
   if (auto* upstream = dynamic_cast<INode*>(input))
      upstream->CookIfNeeded(frameId);
   RebuildIfNeeded();
}
