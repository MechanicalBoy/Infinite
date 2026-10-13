#include "LayerStackNode.h"

#include "gl3.h"
#include <algorithm>
#include <string>

#include "BlendModes.h"

namespace
{
   const std::string& FragSrc()
   {
      static const std::string src =
         std::string(
            "#version 150\n"
            "in vec2 vUv;\n"
            "out vec4 fragColor;\n"
            "uniform sampler2D uTex0;\n"
            "uniform sampler2D uTex1;\n"
            "uniform sampler2D uTex2;\n"
            "uniform sampler2D uTex3;\n"
            "uniform int uActive[4];\n"
            "uniform int uModes[4];\n"
            "uniform float uOpacity[4];\n"
            "uniform vec2 uUvScale[4];\n"
            "uniform int uLinear;\n"
            "uniform int uW3C;\n"
            "uniform int uImgHeadroom;\n")
         + GLUtil::kSrgbGlsl
         + BlendModes::kBlendGLSL
         + "vec4 fetch(int i) {\n"
           // Per-layer aspect placement (see LayerStackNode::Fit); outside the layer is transparent.
           "   vec2 uv = (vUv - 0.5) * uUvScale[i] + 0.5;\n"
           "   if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) return vec4(0.0);\n"
           "   if (i == 0) return texture(uTex0, uv);\n"
           "   if (i == 1) return texture(uTex1, uv);\n"
           "   if (i == 2) return texture(uTex2, uv);\n"
           "   return texture(uTex3, uv);\n"
           "}\n"
           "void main() {\n"
           "   vec4 acc = vec4(0.0);\n"
           "   bool haveBase = false;\n"
           "   for (int i = 0; i < 4; i++) {\n"
           "      if (uActive[i] == 0) continue;\n"
           "      vec4 layer = fetch(i);\n"
           "      if (uLinear == 1) layer.rgb = SrgbDecode(layer.rgb);\n"
           "      float amt = uOpacity[i] * layer.a;\n"
           "      if (!haveBase) { acc = vec4(layer.rgb, layer.a * uOpacity[i]); haveBase = true; continue; }\n"
           "      if (uModes[i] == " + std::to_string(BlendModes::kEraseMode) + ") { acc.a *= (1.0 - amt); continue; }\n"
           "      if (uModes[i] == " + std::to_string(BlendModes::kAntiEraseMode) + ") { acc.a *= (1.0 - (1.0 - layer.a) * uOpacity[i]); continue; }\n"
           "      vec3 blended = blendModeImage(uModes[i], acc.rgb, layer.rgb, uW3C, uImgHeadroom);\n"
           "      vec3 cs = mix(layer.rgb, blended, acc.a);\n"
           "      float ar = amt + acc.a * (1.0 - amt);\n"
           "      vec3 cr = (ar > 1e-5) ? (cs * amt + acc.rgb * acc.a * (1.0 - amt)) / ar : vec3(0.0);\n"
           "      acc = vec4(cr, ar);\n"
           "   }\n"
           "   fragColor = acc;\n"
           "}\n";
      return src;
   }
}

const std::vector<std::string>& LayerStackNode::FitNames()
{
   static const std::vector<std::string> names = { "Stretch", "Fit", "Fill" };
   return names;
}

LayerStackNode::~LayerStackNode()
{
   GLUtil::DestroyFbo(mOut);
   if (mProgram != 0)
      glDeleteProgram(mProgram);
}

void LayerStackNode::SwapLayers(int a, int b)
{
   if (a < 0 || b < 0 || a >= kSlots || b >= kSlots || a == b)
      return;

   INode* srcA = mInputs[a].GetSource();
   INode* srcB = mInputs[b].GetSource();
   if (srcB != nullptr)
      mInputs[a].Connect(srcB);
   else
      mInputs[a].Disconnect();
   if (srcA != nullptr)
      mInputs[b].Connect(srcA);
   else
      mInputs[b].Disconnect();

   std::swap(modes[a], modes[b]);
   std::swap(opacities[a], opacities[b]);
}

bool LayerStackNode::EnsureShader()
{
   if (mShaderTried)
      return mProgram != 0;
   mShaderTried = true;
   mProgram = GLUtil::CompileProgram(GLUtil::WithClampedOutput(FragSrc(), "if (uLinear == 1) fragColor.rgb = SrgbEncode(fragColor.rgb);").c_str());
   return mProgram != 0;
}

void LayerStackNode::CookIfNeeded(int frameId)
{
   if (mLastCookFrame == frameId)
      return;
   mLastCookFrame = frameId;

   unsigned int tex[kSlots] = { 0, 0, 0, 0 };
   int active[kSlots] = { 0, 0, 0, 0 };
   int w = 0, h = 0;

   for (int i = 0; i < kSlots; i++)
   {
      tex[i] = mInputs[i].Pull(frameId);
      active[i] = tex[i] != 0 ? 1 : 0;
      if (active[i] && w == 0)
      {
         w = mInputs[i].Width();
         h = mInputs[i].Height();
      }
   }

   if (w == 0 || h == 0)
      return;

   // UV scale per layer about the centre: 1,1 is stretch. r > 1 means the layer is wider than the canvas.
   float uvScale[kSlots * 2];
   for (int i = 0; i < kSlots; i++)
   {
      float sx = 1.0f, sy = 1.0f;
      const int lw = mInputs[i].Width(), lh = mInputs[i].Height();
      if (active[i] && fit != kStretch && lw > 0 && lh > 0)
      {
         const float r = ((float)lw / (float)lh) / ((float)w / (float)h);
         if (fit == kFit)
         {
            // Whole layer visible: a wider layer gets bars above and below, a taller one at the sides.
            if (r > 1.0f)
               sy = r;
            else
               sx = 1.0f / r;
         }
         else
         {
            // Canvas covered: a wider layer is cropped at the sides, a taller one top and bottom.
            if (r > 1.0f)
               sx = 1.0f / r;
            else
               sy = r;
         }
      }
      uvScale[i * 2] = sx;
      uvScale[i * 2 + 1] = sy;
   }

   if (!EnsureShader())
      return;
   if (!GLUtil::EnsureFbo(mOut, w, h, GLUtil::ImageWorkingFormat(), "LayerStack"))
      return;

   GLUtil::RunShaderPass(mOut, mProgram, [this, &tex, &active, &uvScale]()
   {
      static const char* kTexNames[kSlots] = { "uTex0", "uTex1", "uTex2", "uTex3" };
      for (int i = 0; i < kSlots; i++)
      {
         glActiveTexture(GL_TEXTURE0 + i);
         glBindTexture(GL_TEXTURE_2D, tex[i]);
         glUniform1i(glGetUniformLocation(mProgram, kTexNames[i]), i);
      }
      glUniform1iv(glGetUniformLocation(mProgram, "uActive"), kSlots, active);
      int eff[kSlots];
      for (int i = 0; i < kSlots; i++)
         eff[i] = blendFix ? modes[i] : BlendModes::LegacyMode(modes[i]);
      glUniform1iv(glGetUniformLocation(mProgram, "uModes"), kSlots, eff);
      glUniform1fv(glGetUniformLocation(mProgram, "uOpacity"), kSlots, opacities);
      glUniform2fv(glGetUniformLocation(mProgram, "uUvScale"), kSlots, uvScale);
      glUniform1i(glGetUniformLocation(mProgram, "uLinear"), linear ? 1 : 0);
      glUniform1i(glGetUniformLocation(mProgram, "uW3C"), blendFix);
      GLUtil::SetImageHeadroom(mProgram, headroom);
   });
}
