// re-survey au_oop: what does running an Audio Unit out of process (macOS's AU hosting service) cost a host?
// Instantiates one AU in process or out of process (kAudioComponentInstantiation_LoadOutOfProcess), renders N blocks
// of a -12 dBFS sine through its render block and prints JSON: instantiate time, per-block wall time (median, p99,
// max), this process's CPU, reported latency, output peak. Built and run by au_oop.py (swiftc ships with the Command
// Line Tools). Only Apple's public AudioToolbox API is used; the plugin binary is never read.
// Usage: au_oop <type> <subtype> <manufacturer> <in|out> <blockFrames> <blocks>
import AudioToolbox
import AVFoundation
import Foundation

func fourCC(_ s: String) -> FourCharCode {
    var r: FourCharCode = 0
    for u in s.utf8.prefix(4) { r = (r << 8) | FourCharCode(u) }
    return r
}

func cpuSeconds() -> Double {
    var u = rusage()
    getrusage(RUSAGE_SELF, &u)
    return Double(u.ru_utime.tv_sec + u.ru_stime.tv_sec) + Double(u.ru_utime.tv_usec + u.ru_stime.tv_usec) / 1e6
}

let a = CommandLine.arguments
guard a.count == 7, let frames = Int(a[5]), let blocks = Int(a[6]), a[4] == "in" || a[4] == "out" else {
    FileHandle.standardError.write("usage: au_oop <type> <subtype> <manufacturer> <in|out> <blockFrames> <blocks>\n".data(using: .utf8)!)
    exit(2)
}
let desc = AudioComponentDescription(componentType: fourCC(a[1]), componentSubType: fourCC(a[2]),
                                     componentManufacturer: fourCC(a[3]), componentFlags: 0, componentFlagsMask: 0)
let oop = a[4] == "out"
let sr = 48000.0

var unit: AUAudioUnit?
var err: Error?
let t0 = Date()
let sem = DispatchSemaphore(value: 0)
AUAudioUnit.instantiate(with: desc, options: oop ? [.loadOutOfProcess] : []) { u, e in
    unit = u
    err = e
    sem.signal()
}
sem.wait()
let instS = Date().timeIntervalSince(t0)
guard let au = unit else {
    print("{\"ok\":false,\"error\":\"\(err.map { "\($0)" } ?? "no unit")\"}")
    exit(1)
}

let fmt = AVAudioFormat(standardFormatWithSampleRate: sr, channels: 2)!
do {
    if au.outputBusses.count > 0 { try au.outputBusses[0].setFormat(fmt) }
    if au.inputBusses.count > 0 {
        try au.inputBusses[0].setFormat(fmt)
        au.inputBusses[0].isEnabled = true
    }
    au.maximumFramesToRender = AUAudioFrameCount(frames)
    try au.allocateRenderResources()
} catch {
    print("{\"ok\":false,\"error\":\"allocate: \(error)\"}")
    exit(1)
}

let inBuf = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: AVAudioFrameCount(frames))!
let outBuf = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: AVAudioFrameCount(frames))!
var phase = 0.0
let step = 2.0 * Double.pi * 1000.0 / sr
let amp = Float(pow(10.0, -12.0 / 20.0))
let pull: AURenderPullInputBlock = { _, _, count, _, abl in
    // An AU may hand over buffers with no memory (it wants ours) or its own.
    let l = UnsafeMutableAudioBufferListPointer(abl)
    let own = UnsafeMutableAudioBufferListPointer(inBuf.mutableAudioBufferList)
    for (k, b) in l.enumerated() where b.mData == nil {
        l[k].mData = own[min(k, own.count - 1)].mData
        l[k].mDataByteSize = UInt32(Int(count) * MemoryLayout<Float>.size)
    }
    for i in 0 ..< Int(count) {
        let v = amp * Float(sin(phase + Double(i) * step))
        for b in l { b.mData?.assumingMemoryBound(to: Float.self)[i] = v }
    }
    return noErr
}

let render = au.renderBlock
var times = [Double]()
times.reserveCapacity(blocks)
var peak: Float = 0
var failures = 0
var firstErr: OSStatus = 0
var ts = AudioTimeStamp()
ts.mFlags = .sampleTimeValid
let c0 = cpuSeconds()
let w0 = Date()
for _ in 0 ..< blocks {
    outBuf.frameLength = AVAudioFrameCount(frames)
    let abl = outBuf.mutableAudioBufferList
    var flags = AudioUnitRenderActionFlags()
    let s = DispatchTime.now().uptimeNanoseconds
    let st = render(&flags, &ts, AUAudioFrameCount(frames), 0, abl, au.inputBusses.count > 0 ? pull : nil)
    times.append(Double(DispatchTime.now().uptimeNanoseconds - s) / 1e6)
    if st != noErr { failures += 1; if firstErr == 0 { firstErr = st } }
    for b in UnsafeMutableAudioBufferListPointer(abl) {
        if let p = b.mData?.assumingMemoryBound(to: Float.self) {
            for i in 0 ..< frames { peak = max(peak, abs(p[i])) }
        }
    }
    phase += Double(frames) * step
    ts.mSampleTime += Double(frames)
}
let wall = Date().timeIntervalSince(w0)
let cpu = cpuSeconds() - c0
au.deallocateRenderResources()
let sorted = times.sorted()
func pct(_ p: Double) -> Double { sorted[min(sorted.count - 1, Int(Double(sorted.count) * p))] }
let audioS = Double(frames * blocks) / sr
let out: [String: Any] = [
    "ok": failures == 0, "mode": oop ? "out" : "in", "frames": frames, "blocks": blocks, "instantiate_s": instS,
    "block_ms_median": pct(0.5), "block_ms_p99": pct(0.99), "block_ms_max": sorted.last ?? 0,
    "deadline_ms": Double(frames) / sr * 1000.0, "render_wall_s": wall, "audio_s": audioS,
    "cpu_self_s": cpu, "latency_s": au.latency, "peak": Double(peak), "render_errors": failures, "overruns": times.filter { $0 > Double(frames) / sr * 1000.0 }.count, "first_error": Int(firstErr),
    "in_process_flag": oop ? false : true,
]
let data = try! JSONSerialization.data(withJSONObject: out, options: [.sortedKeys])
print(String(data: data, encoding: .utf8)!)
