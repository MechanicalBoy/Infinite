// re-survey latency_probe: play a click train into a loopback device (BlackHole) and record the same device.
// An app that monitors that device's input straight to its output (at -6 dB) puts each click back a round
// trip later, so every click arrives twice in the recording: once direct, once through the app. The gap is
// the app's real round-trip latency; latency_probe.py measures it. Only Apple's public CoreAudio/AVFoundation
// API is used. Usage: latency_probe <device substring> <seconds> <period s> <out.wav> [echo samples for self-test]
import AudioToolbox
import AVFoundation
import CoreAudio
import Foundation

func deviceID(_ want: String) -> AudioDeviceID? {
    var addr = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices, mScope: kAudioObjectPropertyScopeGlobal,
                                          mElement: kAudioObjectPropertyElementMain)
    var size: UInt32 = 0
    AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size)
    var ids = [AudioDeviceID](repeating: 0, count: Int(size) / MemoryLayout<AudioDeviceID>.size)
    AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &addr, 0, nil, &size, &ids)
    for id in ids {
        var name: CFString = "" as CFString
        var n = UInt32(MemoryLayout<CFString>.size)
        var a = AudioObjectPropertyAddress(mSelector: kAudioObjectPropertyName, mScope: kAudioObjectPropertyScopeGlobal,
                                           mElement: kAudioObjectPropertyElementMain)
        if AudioObjectGetPropertyData(id, &a, 0, nil, &n, &name) == noErr,
           (name as String).lowercased().contains(want.lowercased()) { return id }
    }
    return nil
}

let a = CommandLine.arguments
guard a.count >= 5, let secs = Double(a[2]), let period = Double(a[3]) else {
    FileHandle.standardError.write("usage: latency_probe <device> <seconds> <period> <out.wav> [echo]\n".data(using: .utf8)!)
    exit(2)
}
let fakeEcho = a.count > 5 ? Int(a[5]) ?? 0 : 0
guard var dev = deviceID(a[1]) else {
    print("{\"ok\":false,\"error\":\"no device matching \(a[1])\"}")
    exit(1)
}
func fail(_ what: String, _ st: OSStatus) -> Never {
    print("{\"ok\":false,\"error\":\"\(what): \(st)\"}")
    exit(1)
}

// One full-duplex HAL unit on the loopback device: output bus 0 plays the clicks, input bus 1 is read in the
// same callback, so both sides share one sample clock.
var desc = AudioComponentDescription(componentType: kAudioUnitType_Output, componentSubType: kAudioUnitSubType_HALOutput,
                                     componentManufacturer: kAudioUnitManufacturer_Apple, componentFlags: 0, componentFlagsMask: 0)
guard let comp = AudioComponentFindNext(nil, &desc) else { fail("no HAL unit", -1) }
var unitOpt: AudioUnit?
var st = AudioComponentInstanceNew(comp, &unitOpt)
guard st == noErr, let unit = unitOpt else { fail("instance", st) }
var one: UInt32 = 1
st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_EnableIO, kAudioUnitScope_Input, 1, &one, 4)
if st != noErr { fail("enable input", st) }
st = AudioUnitSetProperty(unit, kAudioOutputUnitProperty_CurrentDevice, kAudioUnitScope_Global, 0, &dev,
                          UInt32(MemoryLayout<AudioDeviceID>.size))
if st != noErr { fail("set device", st) }
var got = AudioDeviceID(0)
var gsz = UInt32(MemoryLayout<AudioDeviceID>.size)
AudioUnitGetProperty(unit, kAudioOutputUnitProperty_CurrentDevice, kAudioUnitScope_Global, 0, &got, &gsz)
if got != dev { fail("the unit did not take the loopback device", -2) }  // never play to the speakers

var srAddr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyNominalSampleRate, mScope: kAudioObjectPropertyScopeGlobal,
                                        mElement: kAudioObjectPropertyElementMain)
var sr = 48000.0
var srsz = UInt32(MemoryLayout<Double>.size)
AudioObjectGetPropertyData(dev, &srAddr, 0, nil, &srsz, &sr)
var asbd = AudioStreamBasicDescription(mSampleRate: sr, mFormatID: kAudioFormatLinearPCM,
                                       mFormatFlags: kAudioFormatFlagsNativeFloatPacked | kAudioFormatFlagIsNonInterleaved,
                                       mBytesPerPacket: 4, mFramesPerPacket: 1, mBytesPerFrame: 4, mChannelsPerFrame: 2,
                                       mBitsPerChannel: 32, mReserved: 0)
let asz = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
st = AudioUnitSetProperty(unit, kAudioUnitProperty_StreamFormat, kAudioUnitScope_Input, 0, &asbd, asz)
if st != noErr { fail("output format", st) }
st = AudioUnitSetProperty(unit, kAudioUnitProperty_StreamFormat, kAudioUnitScope_Output, 1, &asbd, asz)
if st != noErr { fail("input format", st) }

final class State {
    var total = 0, step = 0, echo = 0, pos = 0
    var rec: [Float] = []
    var inL = [Float](repeating: 0, count: 8192), inR = [Float](repeating: 0, count: 8192)
    var unit: AudioUnit?
}
let S = State()
S.total = Int(secs * sr)
S.step = Int(period * sr)
S.echo = fakeEcho
S.rec = [Float](repeating: 0, count: S.total)
S.unit = unit

func click(_ i: Int) -> Float {
    let first = Int(0.5 * sr)
    if i < first { return 0 }
    let k = (i - first) % S.step
    if k == 0 { return 0.5 }
    if S.echo > 0 && k == S.echo { return 0.25 }
    return 0
}

var cb = AURenderCallbackStruct(inputProc: { _, flags, ts, _, frames, io in
    let n = Int(frames)
    var abl = AudioBufferList.allocate(maximumBuffers: 2)
    defer { free(abl.unsafeMutablePointer) }
    S.inL.withUnsafeMutableBufferPointer { l in
        S.inR.withUnsafeMutableBufferPointer { r in
            abl[0] = AudioBuffer(mNumberChannels: 1, mDataByteSize: UInt32(n * 4), mData: l.baseAddress)
            abl[1] = AudioBuffer(mNumberChannels: 1, mDataByteSize: UInt32(n * 4), mData: r.baseAddress)
            _ = AudioUnitRender(S.unit!, flags, ts, 1, frames, abl.unsafeMutablePointer)
        }
    }
    let out = UnsafeMutableAudioBufferListPointer(io!)
    for i in 0 ..< n {
        let p = S.pos + i
        let v: Float = p < S.total ? click(p) : 0
        for b in out { b.mData!.assumingMemoryBound(to: Float.self)[i] = v }
        if p < S.total { S.rec[p] = S.inL[i] }
    }
    S.pos += n
    return noErr
}, inputProcRefCon: nil)
st = AudioUnitSetProperty(unit, kAudioUnitProperty_SetRenderCallback, kAudioUnitScope_Input, 0, &cb,
                          UInt32(MemoryLayout<AURenderCallbackStruct>.size))
if st != noErr { fail("callback", st) }
st = AudioUnitInitialize(unit)
if st != noErr { fail("initialize", st) }
st = AudioOutputUnitStart(unit)
if st != noErr { fail("start", st) }
while S.pos < S.total { Thread.sleep(forTimeInterval: 0.05) }
AudioOutputUnitStop(unit)
AudioUnitUninitialize(unit)

let fmt = AVAudioFormat(standardFormatWithSampleRate: sr, channels: 1)!
let buf = AVAudioPCMBuffer(pcmFormat: fmt, frameCapacity: AVAudioFrameCount(S.total))!
buf.frameLength = AVAudioFrameCount(S.total)
S.rec.withUnsafeBufferPointer { buf.floatChannelData![0].update(from: $0.baseAddress!, count: S.total) }
do {
    // 24-bit integer WAV: what Python's wave module (and plugin_probe.read_wav) reads.
    let settings: [String: Any] = [AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: sr, AVNumberOfChannelsKey: 1,
                                   AVLinearPCMBitDepthKey: 24, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false]
    let f = try AVAudioFile(forWriting: URL(fileURLWithPath: a[4]), settings: settings, commonFormat: .pcmFormatFloat32,
                            interleaved: false)
    try f.write(from: buf)
} catch {
    print("{\"ok\":false,\"error\":\"write: \(error)\"}")
    exit(1)
}
print("{\"ok\":true,\"sample_rate\":\(sr),\"frames\":\(S.total),\"period_s\":\(period)}")
