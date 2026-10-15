#pragma once

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>

// Reader for HAP movies (Hap1, Hap5, HapY) in a QuickTime / MP4 container.
//
// HAP frames are already GPU texture data (DXT1, DXT5, or YCoCg in DXT5)
// wrapped in an optional snappy layer, so playback is a file read, a snappy
// expand and a glCompressedTexSubImage2D: no colour conversion on the CPU and
// a fraction of the bandwidth of raw RGBA. This file is GL-free so the
// decoder is testable without a context, and is the same code on macOS,
// Windows and Linux.
//
// Not supported (Probe returns false, so the caller uses its normal decoder):
// HapM (multiple textures per frame), HapA, and files with no video track.
namespace Hap
{
   enum class Format
   {
      None,
      Dxt1,    // Hap1, opaque
      Dxt5,    // Hap5, with alpha
      YCoCg5,  // HapY (HAP Q), YCoCg stored in DXT5, converted on the GPU
   };

   // Pure snappy raw-block decompressor. Returns false on corrupt input or
   // when the stream does not expand to exactly `expectedSize` bytes.
   bool SnappyDecompress(const uint8_t* in, size_t inSize, uint8_t* out, size_t expectedSize);

   // Decodes one HAP frame payload (the bytes of one QuickTime sample) into
   // texture block data. `out` is resized to the texture's byte size.
   bool DecodeFrame(const uint8_t* data, size_t size, Format& fmt, std::vector<uint8_t>& out,
                    std::string& error);

   // Bytes of block-compressed texture data for a w x h image.
   size_t TextureBytes(Format fmt, int w, int h);

   class Reader
   {
   public:
      Reader() = default;
      ~Reader() = default;
      Reader(const Reader&) = delete;
      Reader& operator=(const Reader&) = delete;

      // True when `path` is a QuickTime/MP4 file whose first video track is a
      // supported HAP codec. Cheap: reads the moov atom only.
      static bool Probe(const std::string& path);

      bool Open(const std::string& path, std::string& error);
      void Close();
      bool IsOpen() const { return mFile.is_open(); }

      int Width() const { return mWidth; }
      int Height() const { return mHeight; }
      double Duration() const { return mDuration; }
      double Fps() const { return mFps; }
      int FrameCount() const { return (int)mSamples.size(); }
      Format TextureFormat() const { return mFormat; }

      // Index of the frame shown at `seconds` (clamped to the clip).
      int FrameIndexAt(double seconds) const;
      double FrameTime(int index) const;

      // Reads and decodes frame `index` into texture block data.
      bool ReadFrame(int index, std::vector<uint8_t>& out, std::string& error);

   private:
      struct Sample
      {
         uint64_t offset = 0;
         uint32_t size = 0;
         double time = 0.0; // presentation start, seconds
      };

      std::ifstream mFile;
      int mWidth = 0;
      int mHeight = 0;
      double mDuration = 0.0;
      double mFps = 0.0;
      Format mFormat = Format::None;
      std::vector<Sample> mSamples;
      std::vector<uint8_t> mRaw;
   };
}
