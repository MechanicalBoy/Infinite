// Shared ONNX Runtime matting engine (u2netp salient-object model).
// Used on Windows (with DirectML GPU or CPU fallback) and Linux (CPU).

#include "SubjectMaskOnnx.h"
#include "PathOpen.h"

#include <onnxruntime_cxx_api.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <memory>
#include <mutex>

namespace OrtMatting
{
   namespace
   {
      ProviderHook gProviderHook = nullptr;

      // Holds the one-time-constructed session and everything needed to run it.
      struct OrtMattingSession
      {
         Ort::Env env{ ORT_LOGGING_LEVEL_WARNING, "Infinite" };
         std::unique_ptr<Ort::Session> session;
         std::string inputName;
         std::string outputName;
         int inputW = 320;
         int inputH = 320;
         bool usedGpu = false;
         std::string error;
      };

      // 0 = not built yet, 1 = GPU (DirectML), 2 = CPU, 3 = unavailable
      std::atomic<int> gMattingBackendKind{ 0 };

      OrtMattingSession& EnsureOrtSession(const std::string& modelPath)
      {
         static OrtMattingSession* holder = nullptr;
         static std::once_flag once;
         std::call_once(once, [&modelPath] {
            holder = new OrtMattingSession();

            if (modelPath.empty())
            {
               holder->error = "background removal model path is empty";
               gMattingBackendKind.store(3, std::memory_order_release);
               return;
            }

            try
            {
               Ort::SessionOptions options;
               options.SetIntraOpNumThreads(1);
               options.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);

               if (gProviderHook)
               {
                  try
                  {
                     gProviderHook(&options, holder->usedGpu);
                  }
                  catch (...)
                  {
                     holder->usedGpu = false;
                  }
               }

#if defined(_WIN32)
               std::wstring widePath = WinCommon::Utf8ToWide(modelPath);
               holder->session = std::make_unique<Ort::Session>(holder->env, widePath.c_str(), options);
#else
               holder->session = std::make_unique<Ort::Session>(holder->env, modelPath.c_str(), options);
#endif

               Ort::AllocatorWithDefaultOptions allocator;
               Ort::AllocatedStringPtr inName = holder->session->GetInputNameAllocated(0, allocator);
               Ort::AllocatedStringPtr outName = holder->session->GetOutputNameAllocated(0, allocator);
               holder->inputName = inName.get();
               holder->outputName = outName.get();

               const Ort::TypeInfo inputInfo = holder->session->GetInputTypeInfo(0);
               const std::vector<int64_t> shape = inputInfo.GetTensorTypeAndShapeInfo().GetShape();
               // NCHW; only trust H/W from the model if they're fixed (not -1).
               if (shape.size() == 4 && shape[2] > 0 && shape[3] > 0)
               {
                  holder->inputH = (int)shape[2];
                  holder->inputW = (int)shape[3];
               }
            }
            catch (const Ort::Exception& e)
            {
               holder->session.reset();
               holder->error = std::string("could not load background removal model: ") + e.what();
            }
            catch (const std::exception& e)
            {
               holder->session.reset();
               holder->error = std::string("could not load background removal model: ") + e.what();
            }

            gMattingBackendKind.store(
               holder->session ? (holder->usedGpu ? 1 : 2) : 3, std::memory_order_release);
         });
         return *holder;
      }

      // Bilinear-resamples RGBA (dropping alpha) into a planar CHW float tensor,
      // normalized the way U^2-Net's own preprocessing does: scaled to [0,1]
      // then per-channel mean/std (ImageNet statistics).
      void ResizeAndNormalize(const unsigned char* rgba, int srcW, int srcH, bool srcBottomUp,
                              float* chw, int dstW, int dstH)
      {
         static const float kMean[3] = { 0.485f, 0.456f, 0.406f };
         static const float kStd[3] = { 0.229f, 0.224f, 0.225f };
         const size_t srcStride = (size_t)srcW * 4;
         const size_t planeSize = (size_t)dstW * dstH;

         for (int y = 0; y < dstH; y++)
         {
            const float sy = (dstH > 1) ? ((float)y + 0.5f) * srcH / dstH - 0.5f : 0.0f;
            const int sy0 = std::clamp((int)std::floor(sy), 0, srcH - 1);
            const int sy1 = std::clamp(sy0 + 1, 0, srcH - 1);
            const float fy = std::clamp(sy - sy0, 0.0f, 1.0f);
            const int ry0 = srcBottomUp ? (srcH - 1 - sy0) : sy0;
            const int ry1 = srcBottomUp ? (srcH - 1 - sy1) : sy1;

            for (int x = 0; x < dstW; x++)
            {
               const float sx = (dstW > 1) ? ((float)x + 0.5f) * srcW / dstW - 0.5f : 0.0f;
               const int sx0 = std::clamp((int)std::floor(sx), 0, srcW - 1);
               const int sx1 = std::clamp(sx0 + 1, 0, srcW - 1);
               const float fx = std::clamp(sx - sx0, 0.0f, 1.0f);

               for (int c = 0; c < 3; c++)
               {
                  const float p00 = rgba[ry0 * srcStride + sx0 * 4 + c];
                  const float p10 = rgba[ry0 * srcStride + sx1 * 4 + c];
                  const float p01 = rgba[ry1 * srcStride + sx0 * 4 + c];
                  const float p11 = rgba[ry1 * srcStride + sx1 * 4 + c];
                  const float top = p00 + (p10 - p00) * fx;
                  const float bot = p01 + (p11 - p01) * fx;
                  const float value = (top + (bot - top) * fy) / 255.0f;
                  chw[c * planeSize + (size_t)y * dstW + x] = (value - kMean[c]) / kStd[c];
               }
            }
         }
      }
   } // namespace

   void SetProviderHook(ProviderHook hook)
   {
      gProviderHook = hook;
   }

   bool SubjectMask(const std::string& modelPath,
                    const std::vector<unsigned char>& rgbaPixels, int width, int height,
                    Platform::MattingMode /*mode*/, std::vector<unsigned char>& outMask,
                    std::string& outError)
   {
      outMask.clear();

      if (width <= 0 || height <= 0 || rgbaPixels.size() < (size_t)width * height * 4)
      {
         outError = "bad image";
         return false;
      }

      OrtMattingSession& ort = EnsureOrtSession(modelPath);
      if (!ort.session)
      {
         outError = ort.error.empty() ? "background removal model unavailable" : ort.error;
         return false;
      }

      try
      {
         std::vector<float> input((size_t)3 * ort.inputW * ort.inputH);
         // rgbaPixels arrives bottom-up (GL order), same as the macOS path.
         ResizeAndNormalize(rgbaPixels.data(), width, height, /*srcBottomUp=*/true,
                            input.data(), ort.inputW, ort.inputH);

         Ort::MemoryInfo memInfo = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
         const int64_t inputShape[4] = { 1, 3, ort.inputH, ort.inputW };
         Ort::Value inputTensor = Ort::Value::CreateTensor<float>(
            memInfo, input.data(), input.size(), inputShape, 4);

         const char* inputNames[] = { ort.inputName.c_str() };
         const char* outputNames[] = { ort.outputName.c_str() };
         auto outputs = ort.session->Run(Ort::RunOptions{ nullptr }, inputNames, &inputTensor, 1,
                                         outputNames, 1);

         const float* pred = outputs[0].GetTensorData<float>();
         const size_t predCount = outputs[0].GetTensorTypeAndShapeInfo().GetElementCount();
         const size_t maskPlane = (size_t)ort.inputW * ort.inputH;
         if (predCount < maskPlane)
         {
            outError = "background removal model returned an unexpected output shape";
            return false;
         }

         // Reference U^2-Net postprocessing: min-max normalize the saliency
         // map to [0,1] before turning it into a mask image.
         float lo = pred[0], hi = pred[0];
         for (size_t i = 0; i < maskPlane; i++)
         {
            lo = std::min(lo, pred[i]);
            hi = std::max(hi, pred[i]);
         }
         const float range = (hi - lo) > 1e-6f ? (hi - lo) : 1.0f;

         std::vector<unsigned char> modelMask(maskPlane);
         for (size_t i = 0; i < maskPlane; i++)
         {
            const float v = (pred[i] - lo) / range;
            modelMask[i] = (unsigned char)std::clamp(v * 255.0f, 0.0f, 255.0f);
         }

         // Rescale (nearest) to the requested size and flip to GL order, same
         // as the macOS/Vision path.
         outMask.assign((size_t)width * height, 0);
         for (int y = 0; y < height; y++)
         {
            const int sy = std::min(ort.inputH - 1, y * ort.inputH / height);
            unsigned char* dstRow = &outMask[(size_t)(height - 1 - y) * width];
            const unsigned char* srcRow = &modelMask[(size_t)sy * ort.inputW];
            for (int x = 0; x < width; x++)
               dstRow[x] = srcRow[std::min(ort.inputW - 1, x * ort.inputW / width)];
         }

         outError.clear();
         return true;
      }
      catch (const Ort::Exception& e)
      {
         outMask.clear();
         outError = std::string("background removal failed: ") + e.what();
         return false;
      }
      catch (const std::exception& e)
      {
         outMask.clear();
         outError = std::string("background removal failed: ") + e.what();
         return false;
      }
   }

   std::string MattingBackend()
   {
      switch (gMattingBackendKind.load(std::memory_order_acquire))
      {
         case 1: return "DirectML GPU (DX12)";
         case 2:
#if defined(_WIN32)
            return "CPU (DirectML unavailable)";
#else
            return "ONNX Runtime (CPU)";
#endif
         case 3: return "unavailable";
         default: return "not yet determined";
      }
   }

   const std::vector<std::string>& MattingModeNames()
   {
      static const std::vector<std::string> kNamesGpu = { "Salient subject (GPU)" };
      static const std::vector<std::string> kNamesCpu = { "Salient subject" };
      int k = gMattingBackendKind.load(std::memory_order_acquire);
      return (k == 1) ? kNamesGpu : kNamesCpu;
   }
} // namespace OrtMatting
