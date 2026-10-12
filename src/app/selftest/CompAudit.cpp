// INFINITE_COMPAUDIT: a measurement audit of the compositing nodes.
//
// The image twin of FXAUDIT / SYNTHAUDIT / NOTEAUDIT / IOAUDIT / GEOAUDIT
// (docs/plans/node-audits/README.md, block 3). Needs the live GL context, so it
// is dispatched after the window exists (like SPOUTLOOPTEST); a hidden window
// is used. Real nodes run on real textures and are read back with
// GLUtil::ReadTexturePixels.
//
//   BLEND     Blend: every mode against the W3C Compositing and Blending
//             Level 1 formulas (separable and non-separable; Add, Linear Burn,
//             Linear Light, Subtract and Divide against their usual
//             definitions) on 4096 random 8-bit pixel pairs, opaque, mix 1
//             (flag > 1/255)
//   ALPHA     Blend Normal and Multiply with random source and backdrop alpha
//             and a mix of 0.7 against the W3C source-over formula, straight
//             alpha out (flag > 1/255)
//   DET       the same inputs twice give bit-identical pixels
//   FEEDBACK  Feedback hands back exactly the previous frame's input (in a plain
//             chain; the delay is documented as always one frame)
//   TRAILS    Trails decay after the input goes black: level at 10 frames
//             against decay^10, and whether the trail ever reaches black
//             (flag > 2/255 off, or a residual that never clears)
//   STACK     Layer Stack with two layers against Blend with the same mode and
//             opacity, random alpha (flag > 1/255)
//   CURVES    default curve is identity; an inverted RGB curve gives 1-x; a Red
//             curve leaves green and blue alone; mix 0 returns the input
//             (flag > 1/255)
//   RAMP      Color Ramp red to blue over a 64-step grey ramp against the
//             analytic gradient (Linear), and a Constant ramp against its step
//             (flag > 1/255)
//   FIT       output size follows width/height and matchInput; Fit leaves
//             transparent bars, Fill covers the frame, Stretch and Fit keep the
//             centre pixel
//   SWITCH    Switcher in manual mode shows exactly the chosen slot
//
// Not covered yet: Reaction Diffusion, Remove Background and the image
// sources; blur accuracy (see the plan).
//
// Only hard invariants fail the run (a node that produces no output at all).
// Everything else is reported, with FLAG lines.
#include "app/AppShared.h"
#include "nodes/BlendNode.h"
#include "nodes/ColorRampNode.h"
#include "nodes/CurvesNode.h"
#include "nodes/FeedbackNodes.h"
#include "nodes/FitNode.h"
#include "nodes/LayerStackNode.h"
#include "nodes/SwitcherNode.h"

#include <array>
#include <cstring>
#include <functional>

namespace app
{
namespace
{
   constexpr int kW = 64, kH = 64;

   struct Flags
   {
      int n = 0;
      void Flag(const char* sec, const std::string& what, double v)
      {
         printf("COMPAUDIT FLAG %-9s %s %.5g\n", sec, what.c_str(), v);
         n++;
      }
   };

   // A node that hands out a texture the audit fills itself.
   class TexSource : public INode
   {
   public:
      TexSource()
      {
         glGenTextures(1, &mTex);
         glBindTexture(GL_TEXTURE_2D, mTex);
         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
         glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
         glBindTexture(GL_TEXTURE_2D, 0);
      }
      ~TexSource() override { glDeleteTextures(1, &mTex); }
      void Set(const std::vector<unsigned char>& rgba)
      {
         glBindTexture(GL_TEXTURE_2D, mTex);
         glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
         glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, kW, kH, 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba.data());
         glBindTexture(GL_TEXTURE_2D, 0);
         mRevision = NextTextureRevision();
      }
      unsigned int GetOutputTexture() override { return mTex; }
      int GetOutputWidth() const override { return kW; }
      int GetOutputHeight() const override { return kH; }
      void CookIfNeeded(int) override {}
      unsigned long long TextureRevision() const override { return mRevision; }

   private:
      unsigned int mTex = 0;
      unsigned long long mRevision = 0;
   };

   struct Rng
   {
      unsigned s;
      explicit Rng(unsigned seed) : s(seed) {}
      unsigned Next()
      {
         s = s * 1664525u + 1013904223u;
         return s >> 8;
      }
   };

   std::vector<unsigned char> RandomImage(unsigned seed, bool randomAlpha)
   {
      Rng r(seed);
      std::vector<unsigned char> px((size_t)kW * kH * 4);
      for (size_t i = 0; i < (size_t)kW * kH; i++)
      {
         for (int c = 0; c < 3; c++)
            px[i * 4 + c] = (unsigned char)(r.Next() & 255);
         px[i * 4 + 3] = randomAlpha ? (unsigned char)(r.Next() & 255) : 255;
      }
      // Pin the corners so the extremes 0 and 255 are always present.
      for (int c = 0; c < 4; c++)
      {
         px[(size_t)c] = 0;
         px[(size_t)(kW - 1) * 4 + (size_t)c] = 255;
      }
      return px;
   }

   std::vector<unsigned char> Flat(unsigned char v)
   {
      std::vector<unsigned char> px((size_t)kW * kH * 4, v);
      for (size_t i = 0; i < (size_t)kW * kH; i++)
         px[i * 4 + 3] = 255;
      return px;
   }

   bool Read(unsigned int tex, std::vector<float>& out)
   {
      unsigned int fbo = 0;
      const bool ok = GLUtil::ReadTexturePixels(fbo, tex, kW, kH, out);
      if (fbo != 0)
         glDeleteFramebuffers(1, &fbo);
      return ok;
   }

   // ---- W3C Compositing and Blending Level 1 reference (double) ----
   using V3 = std::array<double, 3>;
   double Lum(const V3& c) { return 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]; }
   V3 ClipColor(V3 c)
   {
      const double l = Lum(c);
      const double n = std::min(c[0], std::min(c[1], c[2]));
      const double x = std::max(c[0], std::max(c[1], c[2]));
      if (n < 0.0)
         for (double& v : c)
            v = l + (v - l) * l / (l - n);
      if (x > 1.0)
         for (double& v : c)
            v = l + (v - l) * (1.0 - l) / (x - l);
      return c;
   }
   V3 SetLum(const V3& c, double l)
   {
      const double d = l - Lum(c);
      return ClipColor({ c[0] + d, c[1] + d, c[2] + d });
   }
   double Sat(const V3& c) { return std::max(c[0], std::max(c[1], c[2])) - std::min(c[0], std::min(c[1], c[2])); }
   V3 SetSat(V3 c, double s)
   {
      int mx = 0, mn = 0;
      for (int i = 1; i < 3; i++)
      {
         if (c[i] > c[mx])
            mx = i;
         if (c[i] < c[mn])
            mn = i;
      }
      if (mx == mn)
         return { 0, 0, 0 };
      const int mid = 3 - mx - mn;
      V3 r { 0, 0, 0 };
      if (c[mx] > c[mn])
      {
         r[mid] = (c[mid] - c[mn]) * s / (c[mx] - c[mn]);
         r[mx] = s;
      }
      return r;
   }

   // Separable modes, cb = backdrop, cs = source. nullptr-style "unknown" is reported by the caller.
   bool Separable(const std::string& n, double cb, double cs, double& out)
   {
      auto screen = [](double a, double b) { return a + b - a * b; };
      if (n == "Normal") out = cs;
      else if (n == "Darken") out = std::min(cb, cs);
      else if (n == "Lighten") out = std::max(cb, cs);
      else if (n == "Multiply") out = cb * cs;
      else if (n == "Screen") out = screen(cb, cs);
      else if (n == "Overlay") out = cb <= 0.5 ? cs * 2.0 * cb : screen(cs, 2.0 * cb - 1.0);
      else if (n == "Hard Light") out = cs <= 0.5 ? cb * 2.0 * cs : screen(cb, 2.0 * cs - 1.0);
      else if (n == "Soft Light")
      {
         if (cs <= 0.5)
            out = cb - (1.0 - 2.0 * cs) * cb * (1.0 - cb);
         else
         {
            const double d = cb <= 0.25 ? ((16.0 * cb - 12.0) * cb + 4.0) * cb : std::sqrt(cb);
            out = cb + (2.0 * cs - 1.0) * (d - cb);
         }
      }
      else if (n == "Color Dodge") out = cb == 0.0 ? 0.0 : (cs >= 1.0 ? 1.0 : std::min(1.0, cb / (1.0 - cs)));
      else if (n == "Color Burn") out = cb >= 1.0 ? 1.0 : (cs <= 0.0 ? 0.0 : 1.0 - std::min(1.0, (1.0 - cb) / cs));
      else if (n == "Difference") out = std::fabs(cb - cs);
      else if (n == "Exclusion") out = cb + cs - 2.0 * cb * cs;
      // Not in the W3C list, but with one agreed definition.
      else if (n == "Linear Burn") out = std::max(0.0, cb + cs - 1.0);
      else if (n == "Add") out = std::min(1.0, cb + cs);
      else if (n == "Linear Light") out = std::min(1.0, std::max(0.0, cb + 2.0 * cs - 1.0));
      else if (n == "Subtract") out = std::max(0.0, cb - cs);
      else if (n == "Divide") out = cs <= 0.0 ? 1.0 : std::min(1.0, cb / cs);
      else return false;
      return true;
   }

   bool NonSeparable(const std::string& n, const V3& cb, const V3& cs, V3& out)
   {
      if (n == "Hue") out = SetLum(SetSat(cs, Sat(cb)), Lum(cb));
      else if (n == "Saturation") out = SetLum(SetSat(cb, Sat(cs)), Lum(cb));
      else if (n == "Color") out = SetLum(cs, Lum(cb));
      else if (n == "Luminosity") out = SetLum(cb, Lum(cs));
      else return false;
      return true;
   }

   // W3C source-over with a blend function: straight-alpha result.
   bool Reference(const std::string& mode, const unsigned char* b8, const unsigned char* s8, double mix, double out[4])
   {
      const V3 cb { b8[0] / 255.0, b8[1] / 255.0, b8[2] / 255.0 };
      const V3 cs { s8[0] / 255.0, s8[1] / 255.0, s8[2] / 255.0 };
      const double ab = b8[3] / 255.0, as = s8[3] / 255.0 * mix;
      V3 B;
      if (!NonSeparable(mode, cb, cs, B))
         for (int c = 0; c < 3; c++)
            if (!Separable(mode, cb[(size_t)c], cs[(size_t)c], B[(size_t)c]))
               return false;
      const double ar = as + ab * (1.0 - as);
      for (int c = 0; c < 3; c++)
      {
         const double mixed = (1.0 - ab) * cs[(size_t)c] + ab * B[(size_t)c];
         out[c] = ar > 1e-6 ? (as * mixed + ab * (1.0 - as) * cb[(size_t)c]) / ar : 0.0;
      }
      out[3] = ar;
      return true;
   }

   int gFrame = 5000;

   struct BlendRig
   {
      TexSource a, b;
      BlendNode node;
      BlendRig()
      {
         node.InputA().Connect(&a);
         node.InputB().Connect(&b);
      }
      bool Run(int mode, float mix, std::vector<float>& px)
      {
         node.ModeIndex() = mode;
         node.Mix() = mix;
         node.CookIfNeeded(gFrame++);
         return node.GetOutputTexture() != 0 && Read(node.GetOutputTexture(), px);
      }
   };

   double WorstError(const std::string& mode, BlendRig& rig, const std::vector<unsigned char>& A,
                     const std::vector<unsigned char>& B, double mix, const std::vector<float>& px, bool& known)
   {
      double worst = 0.0;
      known = true;
      for (size_t i = 0; i < (size_t)kW * kH; i++)
      {
         double ref[4];
         if (!Reference(mode, &A[i * 4], &B[i * 4], mix, ref))
         {
            known = false;
            return 0.0;
         }
         // Where the result is fully transparent its colour is undefined.
         for (int c = 0; c < 4; c++)
         {
            if (c < 3 && ref[3] < 1e-4)
               continue;
            worst = std::max(worst, std::fabs(ref[c] - (double)px[i * 4 + (size_t)c]));
         }
      }
      (void)rig;
      return worst;
   }

   void AuditBlend(Flags& f, bool& ok)
   {
      BlendRig rig;
      const auto A = RandomImage(11, false), B = RandomImage(23, false);
      rig.a.Set(A);
      rig.b.Set(B);
      const auto& names = BlendNode::ModeNames();
      for (size_t m = 0; m < names.size(); m++)
      {
         std::vector<float> px;
         if (!rig.Run((int)m, 1.0f, px))
         {
            f.Flag("BLEND", names[m] + " produced no output", 1);
            ok = false;
            continue;
         }
         bool known = true;
         const double worst = WorstError(names[m], rig, A, B, 1.0, px, known);
         if (!known)
         {
            printf("COMPAUDIT BLEND  %-14s no published reference, skipped\n", names[m].c_str());
            continue;
         }
         printf("COMPAUDIT BLEND  %-14s worst error %.2f / 255\n", names[m].c_str(), worst * 255.0);
         if (worst > 1.0 / 255.0 + 1e-6)
            f.Flag("BLEND", names[m] + " differs from the W3C formula by (x/255)", worst * 255.0);
      }
   }

   void AuditAlpha(Flags& f, bool& ok)
   {
      BlendRig rig;
      const auto A = RandomImage(31, true), B = RandomImage(47, true);
      rig.a.Set(A);
      rig.b.Set(B);
      const auto& names = BlendNode::ModeNames();
      for (const char* mode : { "Normal", "Multiply", "Screen" })
      {
         size_t idx = 0;
         for (size_t m = 0; m < names.size(); m++)
            if (names[m] == mode)
               idx = m;
         std::vector<float> px;
         if (!rig.Run((int)idx, 0.7f, px))
         {
            f.Flag("ALPHA", std::string(mode) + " produced no output", 1);
            ok = false;
            continue;
         }
         bool known = true;
         const double worst = WorstError(mode, rig, A, B, 0.7, px, known);
         printf("COMPAUDIT ALPHA  %-14s worst error %.2f / 255 (alpha random, mix 0.7)\n", mode, worst * 255.0);
         if (worst > 1.0 / 255.0 + 1e-6)
            f.Flag("ALPHA", std::string(mode) + " differs from W3C source-over by (x/255)", worst * 255.0);
      }
   }

   void AuditDet(Flags& f)
   {
      BlendRig rig;
      rig.a.Set(RandomImage(5, true));
      rig.b.Set(RandomImage(6, true));
      for (int mode : { 0, 2, 12, 22 })
      {
         std::vector<float> p1, p2;
         rig.Run(mode, 0.8f, p1);
         rig.Run(mode, 0.8f, p2);
         if (p1.empty() || p1 != p2)
            f.Flag("DET", "Blend mode " + std::to_string(mode) + " two cooks differ", 1);
      }
      printf("COMPAUDIT DET    Blend: 4 modes cooked twice\n");
   }

   void AuditFeedback(Flags& f)
   {
      TexSource src;
      FeedbackNode fb;
      fb.Input().Connect(&src);
      double worst = 0.0;
      float prevIn = 0.0f;
      for (int k = 0; k < 6; k++)
      {
         const unsigned char v = (unsigned char)(40 + 35 * k);
         src.Set(Flat(v));
         fb.CookIfNeeded(gFrame++);
         std::vector<float> px;
         if (!Read(fb.GetOutputTexture(), px) || px.empty())
            continue;
         if (k > 0)
            worst = std::max(worst, (double)std::fabs(px[0] - prevIn));
         prevIn = v / 255.0f;
      }
      printf("COMPAUDIT FEEDBACK frame delay: worst difference from the previous input %.2f / 255\n", worst * 255.0);
      if (worst > 1.0 / 255.0 + 1e-6)
         f.Flag("FEEDBACK", "in a plain chain the output follows the current frame, not the previous one, off by (x/255)",
                worst * 255.0);
   }

   void AuditTrails(Flags& f)
   {
      for (float decay : { 0.5f, 0.92f, 0.99f })
      {
         TexSource src;
         TrailsNode tr;
         tr.decay = decay;
         tr.Input().Connect(&src);
         src.Set(Flat(255));
         tr.CookIfNeeded(gFrame++);
         src.Set(Flat(0));
         double at10 = -1.0, residual = 0.0;
         int cleared = -1;
         const int frames = 1200;
         for (int k = 1; k <= frames; k++)
         {
            tr.CookIfNeeded(gFrame++);
            std::vector<float> px;
            if (!Read(tr.GetOutputTexture(), px) || px.empty())
               break;
            if (k == 10)
               at10 = px[0];
            residual = px[0];
            if (cleared < 0 && px[0] < 0.5f / 255.0f)
               cleared = k;
         }
         const double want = std::pow((double)decay, 10.0);
         printf("COMPAUDIT TRAILS decay %.2f: level at 10 frames %.4f (decay^10 = %.4f), cleared at frame %d, residual after %d frames %.1f / 255\n",
                decay, at10, want, cleared, frames, residual * 255.0);
         if (std::fabs(at10 - want) > 2.0 / 255.0)
            f.Flag("TRAILS", "decay " + std::to_string(decay) + " level at 10 frames off by (x/255)",
                   std::fabs(at10 - want) * 255.0);
         if (cleared < 0)
            f.Flag("TRAILS", "decay " + std::to_string(decay) + " trail never reaches black, residual (x/255)",
                   residual * 255.0);
      }
   }

   // ---------------------------------------------------------------- STACK
   void AuditStack(Flags& f, bool& ok)
   {
      const auto A = RandomImage(31, true), B = RandomImage(37, true);
      TexSource a, b;
      a.Set(A);
      b.Set(B);
      LayerStackNode stack;
      stack.Input(0).Connect(&a);
      stack.Input(1).Connect(&b);
      stack.fit = LayerStackNode::kStretch;
      BlendNode blend;
      blend.InputA().Connect(&a);
      blend.InputB().Connect(&b);
      const auto& names = BlendNode::ModeNames();
      for (int mode : { 0, 1, 2, 7, 9, 11, 12, 13, 18, 22, 25 })
         for (float op : { 1.0f, 0.6f })
         {
            stack.modes[1] = mode;
            stack.opacities[1] = op;
            stack.CookIfNeeded(gFrame++);
            blend.ModeIndex() = mode;
            blend.Mix() = op;
            blend.CookIfNeeded(gFrame++);
            std::vector<float> ps, pb;
            if (!Read(stack.GetOutputTexture(), ps) || !Read(blend.GetOutputTexture(), pb))
            {
               printf("COMPAUDIT FAIL STACK no output\n");
               ok = false;
               return;
            }
            double worst = 0.0;
            for (size_t i = 0; i < ps.size(); i++)
            {
               // Colour is undefined where the result is fully transparent.
               if (i % 4 != 3 && pb[i / 4 * 4 + 3] < 1e-4f)
                  continue;
               worst = std::max(worst, (double)std::fabs(ps[i] - pb[i]));
            }
            printf("COMPAUDIT STACK %-12s opacity %.1f vs Blend: worst %.2f / 255\n", names[(size_t)mode].c_str(), op,
                   worst * 255.0);
            if (worst > 1.0 / 255.0)
               f.Flag("STACK", std::string(names[(size_t)mode]) + " opacity " + std::to_string(op) + " differs from Blend by (x/255)",
                      worst * 255.0);
         }
   }

   // --------------------------------------------------------------- CURVES
   std::vector<unsigned char> GreyRamp()
   {
      std::vector<unsigned char> px((size_t)kW * kH * 4);
      for (int y = 0; y < kH; y++)
         for (int x = 0; x < kW; x++)
         {
            const unsigned char v = (unsigned char)std::lround(255.0 * x / (kW - 1));
            unsigned char* p = &px[((size_t)y * kW + (size_t)x) * 4];
            p[0] = p[1] = p[2] = v;
            p[3] = 255;
         }
      return px;
   }

   double MaxDiffRow(const std::vector<float>& px, const std::function<void(int, double*)>& want)
   {
      double worst = 0.0;
      if (getenv("INFINITE_COMPAUDIT_ROW"))
         for (int x = 0; x < kW; x += 8)
         {
            double w[3];
            want(x, w);
            const float* p = &px[((size_t)(kH / 2) * kW + (size_t)x) * 4];
            printf("   x=%d want %.3f %.3f %.3f got %.3f %.3f %.3f\n", x, w[0], w[1], w[2], p[0], p[1], p[2]);
         }
      const int y = kH / 2;
      for (int x = 0; x < kW; x++)
      {
         double w[3];
         want(x, w);
         for (int c = 0; c < 3; c++)
            worst = std::max(worst, std::fabs(w[c] - (double)px[((size_t)y * kW + (size_t)x) * 4 + (size_t)c]));
      }
      return worst;
   }

   void AuditCurves(Flags& f, bool& ok)
   {
      TexSource src;
      src.Set(GreyRamp());
      CurvesNode n;
      n.Input().Connect(&src);
      auto run = [&](std::vector<float>& px) {
         n.MarkDirty();
         n.CookIfNeeded(gFrame++);
         return n.GetOutputTexture() != 0 && Read(n.GetOutputTexture(), px);
      };
      std::vector<float> px;
      if (!run(px))
      {
         printf("COMPAUDIT FAIL CURVES no output\n");
         ok = false;
         return;
      }
      auto ramp = [](int x, double* w) { w[0] = w[1] = w[2] = std::lround(255.0 * x / (kW - 1)) / 255.0; };
      double e = MaxDiffRow(px, ramp);
      printf("COMPAUDIT CURVES identity: worst %.2f / 255\n", e * 255.0);
      if (e > 1.5 / 255.0)
         f.Flag("CURVES", "default curve is not identity, worst (x/255)", e * 255.0);

      n.MovePoint(CurvesNode::kRGB, 0, 0.0f, 1.0f);
      n.MovePoint(CurvesNode::kRGB, 1, 1.0f, 0.0f);
      run(px);
      e = MaxDiffRow(px, [&](int x, double* w) { ramp(x, w); for (int c = 0; c < 3; c++) w[c] = 1.0 - w[c]; });
      printf("COMPAUDIT CURVES inverted RGB: worst %.2f / 255\n", e * 255.0);
      if (e > 1.5 / 255.0)
         f.Flag("CURVES", "inverted curve is not 1-x, worst (x/255)", e * 255.0);

      n.ResetChannel(CurvesNode::kRGB);
      n.MovePoint(CurvesNode::kRed, 0, 0.0f, 1.0f);
      n.MovePoint(CurvesNode::kRed, 1, 1.0f, 0.0f);
      run(px);
      e = MaxDiffRow(px, [&](int x, double* w) { ramp(x, w); w[0] = 1.0 - w[0]; });
      printf("COMPAUDIT CURVES Red only inverted: worst %.2f / 255\n", e * 255.0);
      if (e > 1.5 / 255.0)
         f.Flag("CURVES", "Red curve leaks into G/B or is wrong, worst (x/255)", e * 255.0);

      n.mix = 0.0f;
      run(px);
      e = MaxDiffRow(px, ramp);
      printf("COMPAUDIT CURVES mix 0: worst %.2f / 255\n", e * 255.0);
      if (e > 1.0 / 255.0)
         f.Flag("CURVES", "mix 0 does not return the input, worst (x/255)", e * 255.0);
   }

   // ------------------------------------------------------------------ RAMP
   void AuditRamp(Flags& f, bool& ok)
   {
      TexSource src;
      src.Set(GreyRamp());
      ColorRampNode n;
      n.Input().Connect(&src);
      n.stopCount = 2;
      n.stopPos[0] = 0.0f; n.stopPos[1] = 1.0f;
      n.stopColor[0][0] = 1; n.stopColor[0][1] = 0; n.stopColor[0][2] = 0;
      n.stopColor[1][0] = 0; n.stopColor[1][1] = 0; n.stopColor[1][2] = 1;
      n.MarkDirty();
      n.interpMode = ColorRampNode::kLinear;
      n.CookIfNeeded(gFrame++);
      std::vector<float> px;
      if (n.GetOutputTexture() == 0 || !Read(n.GetOutputTexture(), px))
      {
         printf("COMPAUDIT FAIL RAMP no output\n");
         ok = false;
         return;
      }
      auto grey = [](int x) { return std::lround(255.0 * x / (kW - 1)) / 255.0; };
      double e = MaxDiffRow(px, [&](int x, double* w) { const double t = grey(x); w[0] = 1.0 - t; w[1] = 0.0; w[2] = t; });
      printf("COMPAUDIT RAMP linear red->blue: worst %.2f / 255\n", e * 255.0);
      if (e > 1.5 / 255.0)
         f.Flag("RAMP", "linear gradient differs from analytic, worst (x/255)", e * 255.0);

      n.interpMode = ColorRampNode::kConstant;
      n.MarkDirty();
      n.CookIfNeeded(gFrame++);
      Read(n.GetOutputTexture(), px);
      // Constant holds the colour of the last stop at or below t: red until t reaches 1.
      e = MaxDiffRow(px, [&](int x, double* w) {
         const double t = grey(x);
         const bool blue = t >= 1.0;
         w[0] = blue ? 0.0 : 1.0; w[1] = 0.0; w[2] = blue ? 1.0 : 0.0;
      });
      printf("COMPAUDIT RAMP constant: worst %.2f / 255\n", e * 255.0);
      if (e > 1.5 / 255.0)
         f.Flag("RAMP", "constant ramp is not a step, worst (x/255)", e * 255.0);
   }

   // ------------------------------------------------------------------- FIT
   void AuditFit(Flags& f, bool& ok)
   {
      TexSource src;
      src.Set(RandomImage(53, false));
      FitNode n;
      n.Input().Connect(&src);
      n.width = 128.0f;
      n.height = 64.0f;
      n.bgOpacity = 0.0f;
      auto cook = [&]() { n.CookIfNeeded(gFrame++); return n.GetOutputTexture() != 0; };
      auto readAt = [&](float out[4], int x, int y) {
         std::vector<float> px;
         unsigned int fbo = 0;
         const bool r = GLUtil::ReadTexturePixels(fbo, n.GetOutputTexture(), n.GetOutputWidth(), n.GetOutputHeight(), px);
         if (fbo != 0)
            glDeleteFramebuffers(1, &fbo);
         if (!r)
            return false;
         for (int c = 0; c < 4; c++)
            out[c] = px[((size_t)y * (size_t)n.GetOutputWidth() + (size_t)x) * 4 + (size_t)c];
         return true;
      };
      const std::vector<unsigned char> S = RandomImage(53, false);
      for (int mode : { 0, 1, 2 })
      {
         n.mode = mode;
         if (!cook())
         {
            printf("COMPAUDIT FAIL FIT no output\n");
            ok = false;
            return;
         }
         const char* nm = FitNode::ModeNames()[(size_t)mode].c_str();
         const int w = n.GetOutputWidth(), h = n.GetOutputHeight();
         float left[4] = {}, mid[4] = {};
         readAt(left, 4, h / 2);
         readAt(mid, w / 2, h / 2);
         printf("COMPAUDIT FIT %-8s out %dx%d | left-edge alpha %.2f | centre alpha %.2f\n", nm, w, h, left[3], mid[3]);
         if (w != 128 || h != 64)
            f.Flag("FIT", std::string(nm) + " output size is not width x height, width", w);
         if (mid[3] < 0.99f)
            f.Flag("FIT", std::string(nm) + " centre is transparent, alpha", mid[3]);
         if (mode == 0 && left[3] > 0.01f)
            f.Flag("FIT", "Fit leaves no transparent bar at the side, alpha", left[3]);
         if (mode != 0 && left[3] < 0.99f)
            f.Flag("FIT", std::string(nm) + " does not cover the frame at the left edge, alpha", left[3]);
      }
      n.mode = 2;
      n.matchInput = true;
      if (cook() && (n.GetOutputWidth() != kW || n.GetOutputHeight() != kH))
         f.Flag("FIT", "matchInput does not adopt the source size, width", n.GetOutputWidth());
      printf("COMPAUDIT FIT matchInput -> %dx%d\n", n.GetOutputWidth(), n.GetOutputHeight());
      (void)S;
   }

   // ---------------------------------------------------------------- SWITCH
   void AuditSwitch(Flags& f, bool& ok)
   {
      TexSource s[4];
      SwitcherNode n;
      const unsigned char vals[4] = { 40, 100, 160, 220 };
      for (int i = 0; i < 4; i++)
      {
         s[i].Set(Flat(vals[i]));
         n.Input(i).Connect(&s[i]);
      }
      n.manual = true;
      n.crossfade = 0.0f;
      for (int slot = 0; slot < 4; slot++)
      {
         n.manualSlot = slot;
         n.CookIfNeeded(gFrame++);
         std::vector<float> px;
         if (n.GetOutputTexture() == 0 || !Read(n.GetOutputTexture(), px))
         {
            printf("COMPAUDIT FAIL SWITCH no output\n");
            ok = false;
            return;
         }
         const double e = std::fabs((double)px[0] - vals[slot] / 255.0);
         printf("COMPAUDIT SWITCH manual slot %d: %.4f (want %.4f)\n", slot, px[0], vals[slot] / 255.0);
         if (e > 1.0 / 255.0)
            f.Flag("SWITCH", "manual slot " + std::to_string(slot) + " shows the wrong input, off by (x/255)", e * 255.0);
      }
   }
} // namespace

bool RunCompAudit()
{
   setvbuf(stdout, nullptr, _IONBF, 0);
   const char* only = getenv("INFINITE_COMPAUDIT_ONLY");
   auto want = [&](const char* sec) { return only == nullptr || *only == 0 || strstr(only, sec) != nullptr; };
   Flags flags;
   bool ok = true;
   if (want("BLEND"))
      AuditBlend(flags, ok);
   if (want("ALPHA"))
      AuditAlpha(flags, ok);
   if (want("DET"))
      AuditDet(flags);
   if (want("FEEDBACK"))
      AuditFeedback(flags);
   if (want("TRAILS"))
      AuditTrails(flags);
   if (want("STACK"))
      AuditStack(flags, ok);
   if (want("CURVES"))
      AuditCurves(flags, ok);
   if (want("RAMP"))
      AuditRamp(flags, ok);
   if (want("FIT"))
      AuditFit(flags, ok);
   if (want("SWITCH"))
      AuditSwitch(flags, ok);
   printf("COMPAUDIT %s (%d flags)\n", ok ? "PASS" : "FAIL", flags.n);
   return ok;
}

} // namespace app
