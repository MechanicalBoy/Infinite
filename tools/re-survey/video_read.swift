// re-survey video_read: what is inside a movie file, read with Apple's public AVFoundation API.
// Built by render_bench.py (swiftc -O). No third-party decoder: macOS's own.
//
//   video_read info  <movie>                    -> one JSON line: codec, size, fps, duration, frames, bitrates, audio
//   video_read luma  <movie>                    -> one line per frame: "<pts seconds> <mean luma 0..1>"
//   video_read frames <movie> <out.raw> <i,j,..> -> BGRA 8-bit frames i, j, ... (decode order) appended to out.raw
//   video_read audio <movie> <out.f32>          -> interleaved float32 PCM; prints {"sr":..,"channels":..,"frames":..}
// Exit: 0 ok, 1 unreadable movie / no such track, 2 usage.

import AVFoundation
import CoreMedia
import Foundation

func fail(_ msg: String, _ code: Int32 = 1) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(code)
}

func fourcc(_ v: FourCharCode) -> String {
    let b = [UInt8((v >> 24) & 255), UInt8((v >> 16) & 255), UInt8((v >> 8) & 255), UInt8(v & 255)]
    return String(bytes: b, encoding: .ascii) ?? "?"
}

func loadTrack(_ asset: AVURLAsset, _ type: AVMediaType) -> AVAssetTrack? {
    let sem = DispatchSemaphore(value: 0)
    var out: AVAssetTrack?
    Task {
        out = try? await asset.loadTracks(withMediaType: type).first
        sem.signal()
    }
    sem.wait()
    return out
}

func videoReader(_ asset: AVURLAsset, _ track: AVAssetTrack) -> (AVAssetReader, AVAssetReaderTrackOutput) {
    guard let r = try? AVAssetReader(asset: asset) else { fail("video_read: cannot open reader") }
    let o = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
    o.alwaysCopiesSampleData = false
    r.add(o)
    if !r.startReading() { fail("video_read: startReading failed: \(r.error?.localizedDescription ?? "?")") }
    return (r, o)
}

let args = CommandLine.arguments
if args.count < 3 { fail("usage: video_read info|luma|frames|audio <movie> ...", 2) }
let asset = AVURLAsset(url: URL(fileURLWithPath: args[2]))

switch args[1] {
case "info":
    var d: [String: Any] = ["path": args[2]]
    if let v = loadTrack(asset, .video) {
        let fmt = v.formatDescriptions.first.map { $0 as! CMFormatDescription }
        d["codec"] = fmt.map { fourcc(CMFormatDescriptionGetMediaSubType($0)) } ?? "?"
        d["width"] = Int(v.naturalSize.width)
        d["height"] = Int(v.naturalSize.height)
        d["fps"] = Double(v.nominalFrameRate)
        d["video_kbps"] = Double(v.estimatedDataRate) / 1000.0
        d["video_s"] = CMTimeGetSeconds(v.timeRange.duration)
        var n = 0
        let (r, o) = videoReader(asset, v)
        while o.copyNextSampleBuffer() != nil { n += 1 }
        if r.status == .failed { fail("video_read: decode failed: \(r.error?.localizedDescription ?? "?")") }
        d["frames"] = n
    }
    if let a = loadTrack(asset, .audio) {
        let fmt = a.formatDescriptions.first.map { $0 as! CMFormatDescription }
        if let f = fmt, let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(f)?.pointee {
            d["audio_codec"] = fourcc(asbd.mFormatID)
            d["audio_sr"] = asbd.mSampleRate
            d["audio_channels"] = Int(asbd.mChannelsPerFrame)
        }
        d["audio_kbps"] = Double(a.estimatedDataRate) / 1000.0
        d["audio_s"] = CMTimeGetSeconds(a.timeRange.duration)
    }
    let data = try! JSONSerialization.data(withJSONObject: d, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)

case "luma":
    guard let v = loadTrack(asset, .video) else { fail("video_read: no video track") }
    let (r, o) = videoReader(asset, v)
    var lines = ""
    while let sb = o.copyNextSampleBuffer() {
        guard let pb = CMSampleBufferGetImageBuffer(sb) else { continue }
        let pts = CMTimeGetSeconds(CMSampleBufferGetPresentationTimeStamp(sb))
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), rb = CVPixelBufferGetBytesPerRow(pb)
        let p = CVPixelBufferGetBaseAddress(pb)!.assumingMemoryBound(to: UInt8.self)
        var sum = 0.0
        let step = max(1, min(w, h) / 64)  // a 64-ish grid per frame is plenty for a flash detector
        var cnt = 0
        var y = 0
        while y < h {
            var x = 0
            while x < w {
                let q = p + y * rb + x * 4
                sum += 0.0722 * Double(q[0]) + 0.7152 * Double(q[1]) + 0.2126 * Double(q[2])
                cnt += 1
                x += step
            }
            y += step
        }
        CVPixelBufferUnlockBaseAddress(pb, .readOnly)
        lines += String(format: "%.6f %.5f\n", pts, sum / Double(max(cnt, 1)) / 255.0)
    }
    if r.status == .failed { fail("video_read: decode failed: \(r.error?.localizedDescription ?? "?")") }
    print(lines, terminator: "")

case "frames":
    if args.count < 5 { fail("usage: video_read frames <movie> <out.raw> <i,j,...>", 2) }
    guard let v = loadTrack(asset, .video) else { fail("video_read: no video track") }
    let want = Set(args[4].split(separator: ",").compactMap { Int($0) })
    FileManager.default.createFile(atPath: args[3], contents: nil)
    guard let fh = FileHandle(forWritingAtPath: args[3]) else { fail("video_read: cannot write \(args[3])") }
    let (r, o) = videoReader(asset, v)
    var i = 0, w = 0, h = 0, got = 0
    while let sb = o.copyNextSampleBuffer() {
        defer { i += 1 }
        if !want.contains(i) { continue }
        guard let pb = CMSampleBufferGetImageBuffer(sb) else { continue }
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        w = CVPixelBufferGetWidth(pb)
        h = CVPixelBufferGetHeight(pb)
        let rb = CVPixelBufferGetBytesPerRow(pb)
        let p = CVPixelBufferGetBaseAddress(pb)!
        for y in 0..<h { fh.write(Data(bytes: p + y * rb, count: w * 4)) }
        CVPixelBufferUnlockBaseAddress(pb, .readOnly)
        got += 1
    }
    fh.closeFile()
    if r.status == .failed { fail("video_read: decode failed: \(r.error?.localizedDescription ?? "?")") }
    print("{\"width\":\(w),\"height\":\(h),\"frames\":\(got),\"total\":\(i)}")

case "audio":
    if args.count < 4 { fail("usage: video_read audio <movie> <out.f32>", 2) }
    guard let a = loadTrack(asset, .audio) else { fail("video_read: no audio track") }
    guard let r = try? AVAssetReader(asset: asset) else { fail("video_read: cannot open reader") }
    let o = AVAssetReaderTrackOutput(track: a, outputSettings: [
        AVFormatIDKey: kAudioFormatLinearPCM, AVLinearPCMBitDepthKey: 32, AVLinearPCMIsFloatKey: true,
        AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsNonInterleaved: false])
    r.add(o)
    if !r.startReading() { fail("video_read: startReading failed") }
    FileManager.default.createFile(atPath: args[3], contents: nil)
    guard let fh = FileHandle(forWritingAtPath: args[3]) else { fail("video_read: cannot write \(args[3])") }
    var sr = 0.0, ch = 0, frames = 0
    while let sb = o.copyNextSampleBuffer() {
        if let f = CMSampleBufferGetFormatDescription(sb), let asbd = CMAudioFormatDescriptionGetStreamBasicDescription(f)?.pointee {
            sr = asbd.mSampleRate
            ch = Int(asbd.mChannelsPerFrame)
        }
        guard let bb = CMSampleBufferGetDataBuffer(sb) else { continue }
        let len = CMBlockBufferGetDataLength(bb)
        var buf = Data(count: len)  // copy: the block buffer need not be contiguous
        buf.withUnsafeMutableBytes { _ = CMBlockBufferCopyDataBytes(bb, atOffset: 0, dataLength: len, destination: $0.baseAddress!) }
        fh.write(buf)
        frames += CMSampleBufferGetNumSamples(sb)
    }
    fh.closeFile()
    if r.status == .failed { fail("video_read: decode failed: \(r.error?.localizedDescription ?? "?")") }
    print("{\"sr\":\(sr),\"channels\":\(ch),\"frames\":\(frames)}")

default:
    fail("usage: video_read info|luma|frames|audio <movie> ...", 2)
}
