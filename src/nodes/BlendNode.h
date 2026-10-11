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

   // Patches saved before linear light existed lack the key: they keep the
   // gamma-space look they were made with. New nodes default on.
   void BeforeLoadParams() override { mLinear = false; }

   void VisitParams(ParamVisitor& v) override
   {
      v.Int("mode", mModeIndex); v.Float("mix", mMix); v.Bool("linear", mLinear);
   }

private:
   bool EnsureShader();

   ImageCable mInputA;
   ImageCable mInputB;
   int mModeIndex = 0;
   float mMix = 1.0f;
   bool mLinear = true;

   GLUtil::Fbo mOut;
   unsigned int mProgram = 0;
   bool mShaderTried = false;
   int mLastCookFrame = -1;
};
