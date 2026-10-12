// Cook times overlay (View > Cook times). Each node gets its CPU cook time in ms; audio nodes show their share of the
// audio callback instead. Nodes that cost a real share of their budget (the frame, or the audio block) get a heat tint. Off by default and saved in settings, not in patches.
// While off nothing here runs and CookProbe / the audio thread do no timing.
#include "app/AppShared.h"
#include "audio/AudioEngine.h"
#include "audio/AudioNode.h"

namespace app
{
namespace
{
   // Heat is absolute, never relative to the slowest node: relative heat painted the cheapest patch's slowest node red
   // at 0.09 ms. Tint starts at 5% of the budget and is full at 50%.
   constexpr float kFrameMs = 1000.0f / 60.0f;
   constexpr float kHeatLo = 0.05f, kHeatHi = 0.5f;
   bool sApplied = false;

   AudioNode* AudioOf(INode* n)
   {
      if (auto* s = dynamic_cast<IAudioSource*>(n)) return s->GetAudioNode();
      if (auto* s = dynamic_cast<INoteSource*>(n)) return s->GetAudioNode();
      return nullptr;
   }
}

void DrawCookOverlay()
{
   static const bool sEnv = std::getenv("INFINITE_COOKTIMES") != nullptr;   // review hook
   const bool on = sEnv || CategoryColors::GetCookTimes();
   if (on != sApplied)
   {
      sApplied = on;
      CookProbe::gOn.store(on, std::memory_order_relaxed);
      AudioEngine::Instance().SetNodeCostMeasure(on);
      if (!on) CookProbe::Clear();
   }
   if (!on || gNodes.empty())
      return;

   struct Row { const GraphNode* gn; float v; bool audio; };
   static std::vector<Row> rows;
   rows.clear();
   const float budget = std::max(0.001f, AudioEngine::Instance().BlockBudgetMs());
   for (const GraphNode& gn : gNodes)
   {
      if (gn.node == nullptr || gn.node->bypassed || dynamic_cast<GroupNode*>(gn.node.get()) != nullptr) continue;   // a group cooks nothing; its box is the size of its members
      if (AudioNode* an = AudioOf(gn.node.get()))
      {
         const float share = an->costMs.load(std::memory_order_relaxed) / budget;
         rows.push_back({ &gn, share, true });
      }
      else
      {
         const float ms = CookProbe::Ms(gn.node.get());
         if (ms < 0.0f) continue;
         rows.push_back({ &gn, ms, false });
      }
   }

   ImDrawList* dl = ImGui::GetForegroundDrawList();
   const ImVec2 br(gGraphScreenTL.x + gGraphScreenSize.x, gGraphScreenTL.y + gGraphScreenSize.y);
   dl->PushClipRect(gGraphScreenTL, br, true);
   // ed::GetCurrentZoom() is the node editor's InvScale (1 / zoom), so it must never scale a size: corners go through
   // CanvasToScreen, and the on-screen scale is its inverse.
   const float scale = 1.0f / std::max(0.001f, ed::GetCurrentZoom());
   const CategoryColors::UiTheme& t = CategoryColors::CurrentUiTheme();
   const ImU32 pillBg = ImGui::GetColorU32(ImVec4(t.panelBg.r, t.panelBg.g, t.panelBg.b, 0.92f));
   const ImU32 pillText = ImGui::GetColorU32(ImVec4(t.text.r, t.text.g, t.text.b, 1.0f));
   for (const Row& r : rows)
   {
      const ImVec2 cp = ed::GetNodePosition(r.gn->NodeId());
      const ImVec2 cs = ed::GetNodeSize(r.gn->NodeId());
      const ImVec2 p = ed::CanvasToScreen(cp);
      const ImVec2 p2 = ed::CanvasToScreen(ImVec2(cp.x + cs.x, cp.y + cs.y));
      if (p2.x < gGraphScreenTL.x || p.x > br.x || p2.y < gGraphScreenTL.y || p.y > br.y) continue;
      const float share = r.audio ? r.v : r.v / kFrameMs;
      if (share > kHeatLo)   // heat: warm tint that grows with the share of the budget
      {
         const float a = std::clamp((share - kHeatLo) / (kHeatHi - kHeatLo), 0.0f, 1.0f);
         dl->AddRectFilled(p, p2, ImGui::GetColorU32(ImVec4(0.95f, 0.45f - 0.25f * a, 0.1f, 0.10f + 0.22f * a)), 8.0f * scale);
         dl->AddRect(p, p2, ImGui::GetColorU32(ImVec4(0.95f, 0.45f - 0.25f * a, 0.1f, 0.35f + 0.5f * a)), 8.0f * scale, 0, 1.5f);
      }
      if (scale < 0.35f) continue;   // too small to read: tint only
      char buf[24];
      if (r.audio) std::snprintf(buf, sizeof buf, "%.1f%% cb", r.v * 100.0f);
      else std::snprintf(buf, sizeof buf, r.v < 10.0f ? "%.2f ms" : "%.0f ms", r.v);
      const ImVec2 ts = ImGui::CalcTextSize(buf);
      const ImVec2 q0(p2.x - ts.x - 10.0f, p.y - ts.y - 8.0f), q1(p2.x, p.y - 2.0f);
      dl->AddRectFilled(q0, q1, pillBg, 4.0f);
      dl->AddText(ImVec2(q0.x + 5.0f, q0.y + 3.0f), pillText, buf);
   }
   dl->PopClipRect();
}
}
