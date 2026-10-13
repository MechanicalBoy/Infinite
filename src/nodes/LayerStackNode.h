#pragma once

#include <string>
#include <vector>

#include "INode.h"
#include "ImageCable.h"
#include "GLUtil.h"

// Multi-input compositing node: four image cables stacked bottom-to-top, each
// with its own blend mode and opacity, resolved in one shader pass. Blend
// handles the two-input case; this is the "many cables into one node" case.
class LayerStackNode : public INode
{
public:
   static const int kSlots = 4;

   static INode* Create() { return new LayerStackNode(); }

   ~LayerStackNode() override;

   unsigned int GetOutputTexture() override { return GLUtil::FboTexture(mOut); }
   int GetOutputWidth() const override { return mOut.w; }
   int GetOutputHeight() const override { return mOut.h; }
   void CookIfNeeded(int frameId) override;

   ImageCable& Input(int slot) { return mInputs[slot]; }

   // Swaps two layers wholesale - cable, mode and opacity - so reordering in
   // the UI moves the whole layer rather than just its settings.
   void SwapLayers(int a, int b);

   // How a layer whose aspect differs from the canvas (the first connected
   // layer's size) is placed. Stretch is how every patch saved before this
   // option existed composited, so PatchLoad sets it before reading a record
   // that has no "fit" key; a new node starts at Fit.
   enum Fit
   {
      kStretch = 0, // fill the canvas, distorting the aspect
      kFit,         // whole layer visible, aspect kept, transparent bars
      kFill,        // canvas covered, aspect kept, overflow cropped
   };
   static const std::vector<std::string>& FitNames();
   int fit = kFit;

   // 0 on a patch saved before the Overlay / Soft Light / Hard Light / Hard Mix fix
   // (old maths, BlendModes::LegacyMode); 1 on a new node. Not a control.
   int blendFix = 1;

   int modes[kSlots] = { 0, 0, 0, 0 };
   float opacities[kSlots] = { 1.0f, 1.0f, 1.0f, 1.0f };
   bool linear = true; // composite in linear light
   bool headroom = true; // light above 1.0 survives (GLUtil::WithClampedOutput)

   // Patches saved before these existed keep the look they were made with
   // (stretched, gamma-space, old blend maths, clipped).
   void BeforeLoadParams() override { fit = kStretch; linear = false; blendFix = 0; headroom = false; }

   void VisitParams(ParamVisitor& v) override
   {
      v.Bool("linear", linear);
      v.Bool("headroom", headroom);
      static const char* kModeKeys[kSlots] = { "mode0", "mode1", "mode2", "mode3" };
      static const char* kOpKeys[kSlots] = { "opacity0", "opacity1", "opacity2", "opacity3" };
      v.Int("fit", fit);
      v.Int("blendFix", blendFix);
      for (int i = 0; i < kSlots; i++)
      {
         v.Int(kModeKeys[i], modes[i]);
         v.Float(kOpKeys[i], opacities[i]);
      }
   }

private:
   bool EnsureShader();

   ImageCable mInputs[kSlots];
   GLUtil::Fbo mOut;
   unsigned int mProgram = 0;
   bool mShaderTried = false;
   int mLastCookFrame = -1;
};
