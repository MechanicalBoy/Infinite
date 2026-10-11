#include "CurvesNode.h"

#include "gl3.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace
{
   const std::vector<std::string> kChannelNames = { "RGB", "Red", "Green", "Blue" };
   // Float LUT, sampled at texel centres: 1024 entries in R16F keep the
   // curve finer than a half-float step on the 16F image chain.
   const int kLutSize = 1024;

   const char* kFragSrc =
      "#version 150\n"
      "in vec2 vUv;\n"
      "out vec4 fragColor;\n"
      "uniform sampler2D uSrc;\n"
      "uniform sampler2D uLut;\n"
      "uniform float uMix;\n"
      "const float N = 1024.0;\n"
      "float L(float x, float row) { return texture(uLut, vec2((clamp(x, 0.0, 1.0) * (N - 1.0) + 0.5) / N, row)).r; }\n"
      "void main() {\n"
      "   vec4 c = texture(uSrc, vUv);\n"
      "   // row 0 is the master curve, rows 1-3 are per-channel\n"
      "   float r = L(c.r, 0.125);\n"
      "   float g = L(c.g, 0.375);\n"
      "   float b = L(c.b, 0.625);\n"
      "   r = L(r, 0.875);\n"
      "   g = L(g, 0.875);\n"
      "   b = L(b, 0.875);\n"
      "   fragColor = vec4(mix(c.rgb, vec3(r, g, b), uMix), c.a);\n"
      "}\n";
}

const std::vector<std::string>& CurvesNode::ChannelNames()
{
   return kChannelNames;
}

CurvesNode::CurvesNode()
{
   for (int c = 0; c < kChannelCount; c++)
      ResetChannel(c);
   SetExactLine(true);
}

CurvesNode::~CurvesNode()
{
   GLUtil::DestroyFbo(mOut);
   if (mLutTex != 0)
      glDeleteTextures(1, &mLutTex);
   if (mProgram != 0)
      glDeleteProgram(mProgram);
}

void CurvesNode::ResetChannel(int channel)
{
   if (channel < 0 || channel >= kChannelCount)
      return;
   mShapes[channel].Reset();
}

int CurvesNode::AddPoint(int channel, float x, float y)
{
   if (channel < 0 || channel >= kChannelCount)
      return -1;
   return mShapes[channel].AddPoint(x, y);
}

void CurvesNode::MovePoint(int channel, int index, float x, float y)
{
   if (channel < 0 || channel >= kChannelCount)
      return;
   mShapes[channel].MovePoint(index, x, y);
}

void CurvesNode::RemovePoint(int channel, int index)
{
   if (channel < 0 || channel >= kChannelCount)
      return;
   mShapes[channel].RemovePoint(index);
}

float CurvesNode::Evaluate(int channel, float x) const
{
   if (channel < 0 || channel >= kChannelCount)
      return x;
   return mShapes[channel].Evaluate(x);
}

void CurvesNode::RebuildLut()
{
   // one row per channel: R, G, B, then the master curve applied last
   std::vector<float> lut(kLutSize * 4, 0.0f);
   const int rowChannel[4] = { kRed, kGreen, kBlue, kRGB };
   for (int row = 0; row < 4; row++)
   {
      for (int i = 0; i < kLutSize; i++)
      {
         const float x = (float)i / (float)(kLutSize - 1);
         const float y = Evaluate(rowChannel[row], x);
         lut[row * kLutSize + i] = std::min(1.0f, std::max(0.0f, y));
      }
   }

   if (mLutTex == 0)
      glGenTextures(1, &mLutTex);
   glBindTexture(GL_TEXTURE_2D, mLutTex);
   glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
   glTexImage2D(GL_TEXTURE_2D, 0, GL_R16F, kLutSize, 4, 0, GL_RED, GL_FLOAT, lut.data());
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
   glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
   glBindTexture(GL_TEXTURE_2D, 0);

   for (int c = 0; c < kChannelCount; c++)
      mLutVersion[c] = mShapes[c].version;
   mLutRebuildCount++;
}

bool CurvesNode::EnsureShader()
{
   if (mShaderTried)
      return mProgram != 0;
   mShaderTried = true;
   mProgram = GLUtil::CompileProgram(GLUtil::WithClampedOutput(kFragSrc).c_str());
   return mProgram != 0;
}

void CurvesNode::CookIfNeeded(int frameId)
{
   if (mLastCookFrame == frameId)
      return;
   mLastCookFrame = frameId;

   unsigned int srcTex = mInput.Pull(frameId);
   if (srcTex == 0)
   {
      GLUtil::DestroyFbo(mOut);
      return;
   }
   if (!EnsureShader())
      return;
   bool lutStale = mLutTex == 0;
   for (int c = 0; c < kChannelCount && !lutStale; c++)
      lutStale = mLutVersion[c] != mShapes[c].version;
   if (lutStale)
      RebuildLut();
   if (!GLUtil::EnsureFbo(mOut, mInput.Width(), mInput.Height(), GLUtil::ImageWorkingFormat(), "Curves"))
      return;

   GLUtil::RunShaderPass(mOut, mProgram, [this, srcTex]()
   {
      glActiveTexture(GL_TEXTURE0);
      glBindTexture(GL_TEXTURE_2D, srcTex);
      glUniform1i(glGetUniformLocation(mProgram, "uSrc"), 0);
      glActiveTexture(GL_TEXTURE1);
      glBindTexture(GL_TEXTURE_2D, mLutTex);
      glUniform1i(glGetUniformLocation(mProgram, "uLut"), 1);
      glUniform1f(glGetUniformLocation(mProgram, "uMix"), mix);
   });
}
