#pragma once

#include <string>
#include <vector>

#include "INode.h"
#include "ImageCable.h"
#include "GLUtil.h"

// Compositing node: takes two upstream image cables and blends them using the
// full Affinity-style blend-mode list (Normal..Erase, ~30 modes) as one int
// uniform switch in a single shader - cheap to grow since it's just shader math,
// no new node classes.
class BlendNode : public INode
{
public:
   static INode* Create() { return new BlendNode(); }
   static const std::vector<std::string>& ModeNames();

   ~BlendNode() override;

   unsigned int GetOutputTexture() override { return GLUtil::FboTexture(mOut); }
   int GetOutputWidth() const override { return mOut.w; }
   int GetOutputHeight() const override { return mOut.h; }
   void CookIfNeeded(int frameId) override;

   ImageCable& InputA() { return mInputA; }
   ImageCable& InputB() { return mInputB; }
   int& ModeIndex() { return mModeIndex; }
   float& Mix() { return mMix; }
   bool& Linear() { return mLinear; }
   bool& W3CModes() { return mW3C; }
   bool& Headroom() { return mHeadroom; }

   // Patches saved before linear light existed lack the key: they keep the
   // gamma-space look they were made with. New nodes default on. Same for
   // the W3C fix of Overlay, Soft Light, Hard Light and Hard Mix, and for
   // headroom (light above 1.0 survives; old patches keep clipping).
   void BeforeLoadParams() override { mLinear = false; mW3C = false; mHeadroom = false; }

   void VisitParams(ParamVisitor& v) override
   {
      v.Int("mode", mModeIndex); v.Float("mix", mMix); v.Bool("linear", mLinear); v.Bool("w3cModes", mW3C);
      v.Bool("headroom", mHeadroom);
   }

private:
   bool EnsureShader();

   ImageCable mInputA;
   ImageCable mInputB;
   int mModeIndex = 0;
   float mMix = 1.0f;
   bool mLinear = true;
   bool mW3C = true;
   bool mHeadroom = true;

   GLUtil::Fbo mOut;
   unsigned int mProgram = 0;
   bool mShaderTried = false;
   int mLastCookFrame = -1;
};
