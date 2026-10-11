#pragma once

#include <string>
#include <vector>

#include "INode.h"
#include "Geometry3DNodes.h"
#include "GeometryOpNodes.h"
#include "Mesh.h"

// Carries several geometry sources through one pin into Render 3D, so a scene
// is not capped at Render 3D's four geometry inputs. Unlike Join Geometry it
// does not merge anything: every child keeps its own mesh, material, texture,
// mapping and transform, and Render 3D draws each one as if it had its own
// pin. Groups can be patched into groups.
//
// To any other consumer (Transform, Join Geometry, Material, ...) it hands
// out its children baked into one mesh, each placed where Render 3D would
// draw it. That merged copy loses per-child materials (tints survive as
// vertex colour), so Render 3D keeps drawing the children individually.
class Group3DNode : public INode, public IGeometrySource
{
public:
   static const int kSlots = 8;

   static INode* Create() { return new Group3DNode(); }

   unsigned int GetOutputTexture() override { return 0; }
   int GetOutputWidth() const override { return 0; }
   int GetOutputHeight() const override { return 0; }
   // Render 3D cooks the children it flattens itself; anything else reaching
   // them through this group needs the group to pass the cook on.
   void CookIfNeeded(int frameId) override
   {
      if (mLastCookFrame == frameId)
         return; // also ends a group patched into itself
      mLastCookFrame = frameId;
      for (IGeometrySource* in : inputs)
         if (auto* upstream = dynamic_cast<INode*>(in))
            upstream->CookIfNeeded(frameId);
   }

   // Baked lazily: a group that only feeds Render 3D is never asked.
   const Mesh& GetMesh() override
   {
      RefreshBake();
      return mBaked;
   }
   unsigned long long MeshRevision() override
   {
      RefreshBake();
      return mRevision;
   }
   Mat4 GetModelMatrix() const override { return Mat4::Identity(); }
   Material GetMaterial() const override { return Material(); }

   // The connected inputs, in pin order.
   int GroupChildCount() const override
   {
      int count = 0;
      for (int i = 0; i < kSlots; i++)
         if (inputs[i] != nullptr)
            count++;
      return count;
   }
   IGeometrySource* GroupChild(int index) const override
   {
      for (int i = 0; i < kSlots; i++)
      {
         if (inputs[i] == nullptr)
            continue;
         if (index-- == 0)
            return inputs[i];
      }
      return nullptr;
   }

   IGeometrySource* inputs[kSlots] = {};
   IGeometrySource** GeometryInputSlot(int slot) override
   {
      return (slot >= 0 && slot < kSlots) ? &inputs[slot] : nullptr;
   }
   const char* InputLabel(int slot) const override
   {
      static const char* kNames[] = { "geo A", "geo B", "geo C", "geo D",
                                      "geo E", "geo F", "geo G", "geo H" };
      return (slot >= 0 && slot < kSlots) ? kNames[slot] : nullptr;
   }

   void VisitParams(ParamVisitor& /*v*/) override {}

private:
   void RefreshBake()
   {
      if (mBaking)
         return; // groups patched into each other: the inner ask sees the last bake
      mBaking = true;
      if (BakeGroupMesh(this, mSignature, mBaked) || mRevision == 0)
         mRevision = NextMeshRevision();
      mBaking = false;
   }

   Mesh mBaked;
   unsigned long long mSignature = 0;
   unsigned long long mRevision = 0;
   int mLastCookFrame = -1;
   bool mBaking = false;
};
