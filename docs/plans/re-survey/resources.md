# re-survey resources: algorithms, performance, 3D, compositing

Status: reference list, written 2026-10-12. Companion to `README.md` in this folder.
Purpose: where to learn how competitors' algorithms work **without opening their binaries**.
Every entry is a paper, book, talk, public doc or permissively licensed code.

Licence legend (clean room, see AGENTS.md rule 1):

| Tag | Meaning |
|---|---|
| **PUB** | Paper, book, article, talk or public doc. Read freely, write our own code from the idea. |
| **MIT/BSD/Apache/Boost/PD** | Code may be read and reused with the licence notice. |
| **GPL/AGPL** | Never read the source. Docs and observed behaviour only. |
| **EULA** | Proprietary: public docs only, measure by black box. |

Titles are given so each item can be found even if a URL moves. URLs are listed where known.

---

## 0. How competitors map to topics

| Competitor / product | Read first (section) |
|---|---|
| FabFilter Pro-Q (EQ) | 1.1, 1.8, 2 |
| FabFilter Pro-C / Pro-MB / Pro-DS / Pro-G | 1.2, 1.1 (crossovers) |
| FabFilter Pro-L (limiter) | 1.2, 1.3 (true peak), 1.9 |
| FabFilter Saturn (distortion) | 1.3, 2 |
| FabFilter Timeless (delay) / Volcano (filter) / Twin / One / Simplon | 1.4, 1.5, 1.1 |
| Valhalla (reverbs, delays, shimmer) | 1.4, 1.6 |
| u-he Diva (analog modelling) | 1.5, 1.1, 2 |
| Serum 2 / Vital (wavetable) | 1.5 (wavetable), 1.3 (aliasing) |
| Ableton Live / Logic / Bitwig (engine, hosting) | 3.1, 3.2, 3.5 |
| Bitwig / Live modulation systems | official APIs, see README section 6 |
| TouchDesigner (TOPs, SOPs, GLSL) | 4, 5, 6, 3.3 |
| Blender geometry nodes (GPL: manual only) | 4, 5 |
| Resolume / VDMX / Millumin (compositing, output) | 6, 3.3 |

---

## 1. Audio DSP algorithms

### 1.1 Filters and EQ

| Resource | What it gives you | Tag |
|---|---|---|
| Vadim Zavalishin, *The Art of VA Filter Design* (Native Instruments, free PDF) | Zero-delay-feedback filters, TPT, nonlinear ladder, how Diva-class filters are built | PUB |
| Robert Bristow-Johnson, *Audio EQ Cookbook* (w3.org/TR/audio-eq-cookbook) | Biquad formulas for every EQ shape | PUB |
| Andrew Simper (Cytomic), *Linear Trapezoidal Integrated SVF* (cytomic.com technical papers) | The modern SVF used in many plugins, stable under fast modulation | PUB |
| Martin Vicanek, *Matched Second Order Digital Filters* (2016, vicanek.de) | EQ bells that do not cramp at Nyquist: the "analog-matched" EQ trick | PUB |
| S. Orfanidis, *Digital Parametric Equalizer Design with Prescribed Nyquist-Frequency Gain* (JAES 1997) | Same problem, earlier solution | PUB |
| Julius O. Smith III, *Introduction to Digital Filters* and *Spectral Audio Signal Processing* (ccrma.stanford.edu/~jos) | Whole-field reference: allpass, minimum phase, FIR design | PUB |
| Huovilainen, *Non-linear digital implementation of the Moog ladder filter* (DAFx 2004) | The standard nonlinear ladder model | PUB |
| Stilson and Smith, *Analyzing the Moog VCF with considerations for digital implementation* (ICMC 1996) | Ladder analysis | PUB |
| D'Angelo and Välimäki, *An improved virtual analog model of the Moog ladder filter* (ICASSP 2013) | Improved ladder | PUB |
| Linkwitz-Riley crossovers (Linkwitz Lab, linkwitzlab.com) | Band splitting for multiband (Pro-MB, Nova class) | PUB |
| Natural-phase / linear-phase EQ: Smith (above) for min-phase via cepstrum; Oppenheim and Schafer, *Discrete-Time Signal Processing* | How "linear phase" and "natural phase" modes are built | PUB |

### 1.2 Dynamics: compressors, limiters, gates

| Resource | What it gives you | Tag |
|---|---|---|
| Giannoulis, Massberg, Reiss, *Digital Dynamic Range Compressor Design: A Tutorial and Analysis* (JAES 2012) | Detector, gain computer, smooth knee, attack/release topologies | PUB |
| Reiss and McPherson, *Audio Effects: Theory, Implementation and Application* (CRC) | Textbook for every classic effect | PUB |
| Zölzer (ed.), *DAFX: Digital Audio Effects* (Wiley) | The standard effects textbook | PUB |
| Will Pirkle, *Designing Audio Effect Plugins in C++* (Routledge) | Working code patterns for dynamics, delays, reverbs, synths | PUB |
| ITU-R BS.1770 and EBU R128 | Loudness meter and true-peak spec (Pro-L style metering) | PUB |
| Look-ahead limiter literature: Giannoulis (above), plus Reiss *Dynamic range compression* chapters | Look-ahead, release curves, auto-release | PUB |
| FabFilter Learning (YouTube, "FabFilter Learning" series with Dan Worrall) | Maker's own explanations of limiting, saturation, oversampling, EQ phase | PUB |

### 1.3 Distortion, saturation, oversampling, aliasing

| Resource | What it gives you | Tag |
|---|---|---|
| Parker, Esqueda, Bergner, *Reducing the aliasing of nonlinear waveshaping using continuous-time convolution* (DAFx 2016) | Antiderivative anti-aliasing: alias suppression without full oversampling | PUB |
| Esqueda, Välimäki, Bilbao, *Aliasing reduction in clipped signals* (IEEE TSP 2016) | Clipper aliasing | PUB |
| Dan Worrall, FabFilter Learning videos on aliasing and oversampling | Practical aliasing intuition | PUB |
| Eichas and Zölzer, *Black-box modeling of distortion circuits with block-oriented models* (DAFx 2016) | Fit Wiener/Hammerstein models to measured distortion | PUB |
| Yeh, *Digital Implementation of Musical Distortion Circuits by Analysis and Simulation* (Stanford PhD 2009) | Circuit-level (diode clipper, tube stage) simulation | PUB |
| Pakarinen and Yeh, *A Review of Digital Techniques for Modeling Vacuum-Tube Guitar Amplifiers* (CMJ 2009) | Tube and transformer models | PUB |
| Half-band and polyphase oversampling filters: Smith (1.1), Lavry, *Sampling Theory for Digital Audio* | Oversampler design, latency and quality tradeoffs | PUB |

### 1.4 Reverb, delay, modulation effects

| Resource | What it gives you | Tag |
|---|---|---|
| Jon Dattorro, *Effect Design Part 1: Reverberator and Other Filters* (JAES 1997) | The plate-style reverb many plugins descend from | PUB |
| Välimäki et al., *Fifty Years of Artificial Reverberation* (IEEE TASLP 2012) | Survey: Schroeder, FDN, waveguide, convolution | PUB |
| Jot and Chaigne, *Digital delay networks for designing artificial reverberators* (AES 1991) | Feedback delay networks (FDN) | PUB |
| Julian Parker et al. on FDN and spring reverb modelling (DAFx papers) | Spring and plate modelling | PUB |
| Sean Costello, ValhallaDSP blog (valhalladsp.com/blog) | The maker explaining his own reverb design choices: modulation, decorrelation, diffusion, shimmer | PUB |
| Signalsmith Audio, *Let's Write a Reverb* and *Four Ways to Write a Pitch Shifter* (signalsmith-audio.co.uk/writing) | Clear, runnable explanations; Signalsmith DSP library is MIT | PUB / MIT |
| Freeverb (Jezar, public domain) | Classic Schroeder-Moorer reverb | PD |
| Dattorro-style, Griesinger and Gardner papers: Gardner, *Reverberation algorithms* (in Kahrs and Brandenburg, *Applications of DSP to Audio and Acoustics*) | Allpass-network design | PUB |
| Flanger/chorus/phaser: Dattorro, Smith (*Physical Audio Signal Processing*), DAFX | LFO shape, delay interpolation, feedback | PUB |
| Fractional delay interpolation: Laakso et al., *Splitting the Unit Delay* (IEEE SPM 1996) | Delay-line interpolation for tape and chorus modulation | PUB |

### 1.5 Synthesis (virtual analog, wavetable, FM)

| Resource | What it gives you | Tag |
|---|---|---|
| Välimäki and Huovilainen, *Oscillator and filter algorithms for virtual analog synthesis* (CMJ 2006) and *Antialiasing oscillators in subtractive synthesis* (IEEE SPM 2007) | Overview of anti-aliased oscillator methods | PUB |
| Stilson and Smith, *Alias-free digital synthesis of classic analog waveforms* (ICMC 1996) | BLIT oscillators | PUB |
| Välimäki, Nam, Smith, Abel, *Alias-suppressed oscillators based on differentiated polynomial waveforms* (IEEE TASLP 2010) | PolyBLEP/DPW family | PUB |
| Esqueda et al., *Rounding corners with BLAMP* (DAFx 2016) | Correct anti-aliasing for slope discontinuities | PUB |
| Robert Bristow-Johnson, *Wavetable Synthesis 101* | Wavetable lookup, mip-mapping, interpolation | PUB |
| Serum / Serum 2 manual, Vital docs (docs only) | What each warp mode claims to do; measure to confirm | EULA / GPL (docs only) |
| u-he Diva manual and Urs Heckmann's public forum posts (u-he.com) | Model descriptions in the maker's own words | EULA (docs only) |
| John Chowning, *The Synthesis of Complex Audio Spectra by Means of Frequency Modulation* (JAES 1973) | FM | PUB |
| Zavalishin (1.1) | Oscillator sync, nonlinear VA structures | PUB |
| Airwindows (github.com/airwindows, MIT) | Large collection of small, readable effect algorithms | MIT |
| Faust libraries (faustlibraries, mixed licences: check each file) | Filters, oscillators, reverbs in compact form | check per file |
| STK, Synthesis ToolKit (CCRMA, permissive licence) | Physical models, basic building blocks | permissive |

### 1.6 Pitch, time and spectral

| Resource | What it gives you | Tag |
|---|---|---|
| Laroche and Dolson, *Improved phase vocoder time-scale modification of audio* (IEEE TSAP 1999) | Phase vocoder with phase locking | PUB |
| Röbel, *A new approach to transient processing in the phase vocoder* (DAFx 2003) | Transient preservation | PUB |
| Zölzer DAFX chapters on time and pitch | Overview | PUB |
| Signalsmith (1.4) | Modern stretching and pitch articles | PUB / MIT |
| Smith, *Spectral Audio Signal Processing* (CCRMA) | STFT, windows, overlap-add | PUB |

### 1.7 Convolution

| Resource | What it gives you | Tag |
|---|---|---|
| Gardner, *Efficient Convolution without Input/Output Delay* (JAES 1995) | Non-uniform partitioned convolution | PUB |
| Wefers, *Partitioned convolution algorithms for real-time auralization* (2015) | Modern survey | PUB |

### 1.8 Spectrum, metering, analysis (for the measurement side)

| Resource | What it gives you | Tag |
|---|---|---|
| Farina, *Simultaneous Measurement of Impulse Response and Distortion with a Swept-Sine Technique* (AES 2000) | Exponential sine sweep: IR plus harmonic distortion separated | PUB |
| Novak et al., *Nonlinear System Identification Using Exponential Swept-Sine Signal* (IEEE TIM 2010) | Hammerstein models from sweeps | PUB |
| Harris, *On the use of windows for harmonic analysis with the DFT* (Proc. IEEE 1978) | Windows for measurement | PUB |
| Plugin Doctor (DDMF, EULA binary used as a measuring tool) | Black-box response, THD and dynamics curves of any plugin | EULA (tool use only) |
| pyfar (python acoustics toolbox, MIT), scipy.signal, librosa (ISC) | Analysis scripts | MIT / ISC |

### 1.9 Where DSP engineers write it all down

| Resource | Notes |
|---|---|
| DAFx proceedings (dafx.de) | Free PDFs, every year since 1998: the best single source for plugin-class algorithms |
| JAES (AES E-Library) | Mostly paywalled; many authors post preprints |
| ICASSP / IEEE TASLP / IEEE SPL | Abstract level free, many on arXiv |
| ADC, Audio Developer Conference (YouTube, JUCE channel) | Engineers from Ableton, Bitwig, FabFilter peers, u-he peers, Native Instruments describe real designs |
| KVR DSP forum, Music-DSP archive (musicdsp.org) | Folklore; licence of snippets unclear: read ideas, never copy code |
| Julius Smith's CCRMA book pages | Cited above |

---

## 2. System identification: our own model from measurements

This is the legal replacement for reading a competitor's internals.

| Resource | What it gives you | Tag |
|---|---|---|
| Farina and Novak (1.8) | Measurement signals and Hammerstein identification | PUB |
| Eichas and Zölzer (1.3) | Block-oriented model fitting | PUB |
| Wright, Damskägg, Välimäki, *Real-Time Black-Box Modelling with Recurrent Neural Networks* (DAFx 2019) | Neural model of a nonlinear device from input/output pairs | PUB |
| Nercessian, *Neural Parametric Equalizer Matching Using Differentiable Biquads* (DAFx 2020) | Fit EQ curves by gradient descent | PUB |
| Engel et al., *DDSP: Differentiable Digital Signal Processing* (ICLR 2020; Magenta code Apache) | Differentiable filters, reverbs, oscillators | PUB / Apache |
| Lee et al., *Differentiable Artificial Reverberation* (IEEE TASLP 2022) | Fit FDN reverb parameters to a measured reverb | PUB |
| Neural Amp Modeler (MIT) | Capture workflow pattern for a nonlinear device | MIT |
| Kuznetsov et al., *Differentiable IIR filters for machine learning applications* (DAFx 2020) | Fitting recursive filters | PUB |

Workflow: measure response (sweeps, steps, noise) → pick a structure from sections 1.x → fit parameters → compare error against the measured plugin → ship our own code. Nothing in this path touches the plugin's code.

---

## 3. Performance and efficiency

### 3.1 Real-time audio engineering

| Resource | What it gives you | Tag |
|---|---|---|
| Ross Bencina, *Real-time audio programming 101: time waits for nothing* (rossbencina.com) | The rules: no locks, no allocation, no syscalls on the audio thread | PUB |
| Timur Doumler, *C++ in the Audio Industry* and *Using locks in real-time audio processing, safely* (CppCon / ADC) | Practical rules and measurements | PUB |
| Fabian Renn-Giles and Dave Rowland, *Real-time 101* (ADC 2019) | Real-time safe design | PUB |
| Apple, *Audio Workgroups* (WWDC 2020) and Core Audio docs | Thread scheduling on Apple silicon | PUB |
| Jeff Preshing, preshing.com | Lock-free programming, memory ordering | PUB |
| moodycamel concurrent queue (BSD / Boost) | Lock-free queues | BSD |
| ADC talks from DAW makers (search "ADC Bitwig", "ADC Ableton", "ADC multithreading plugin host") | How real hosts schedule graphs across cores, handle PDC, sandbox plugins | PUB |

### 3.2 CPU performance (applies to audio, canvas and UI)

| Resource | What it gives you | Tag |
|---|---|---|
| Agner Fog, *Optimizing software in C++* and instruction tables (agner.org/optimize) | Micro-architecture, SIMD, branch costs | PUB |
| Denis Bakhvalov, *Performance Analysis and Tuning on Modern CPUs* (free PDF) | Top-down method, profiling, cache and branch analysis | PUB |
| Ulrich Drepper, *What Every Programmer Should Know About Memory* | Cache, TLB, prefetch | PUB |
| Mike Acton, *Data-Oriented Design and C++* (CppCon 2014); Richard Fabian, *Data-Oriented Design* (free online) | Layout for throughput | PUB |
| Casey Muratori, *Performance-Aware Programming* (computerenhance.com) | Course-length treatment of CPU cost model | PUB |
| Daniel Lemire's blog (lemire.me) | SIMD parsing, benchmarks, practical tricks | PUB |
| Brendan Gregg, *Systems Performance* and flame graphs (brendangregg.com) | Profiling method | PUB |
| xsimd (BSD), Highway (Apache), Eigen (MPL2) | SIMD wrappers; check licence before linking | per licence |
| Apple, *Optimizing for Apple silicon*, Instruments docs, `xctrace` | Native profiling on macOS | PUB |
| Denormals: Intel and ARM docs on FTZ/DAZ | Avoid CPU spikes in feedback paths | PUB |
| Tracy profiler (BSD-3) | Frame/thread profiler for dev builds only (never in shipped builds) | BSD |

### 3.3 GPU and graphics performance

| Resource | What it gives you | Tag |
|---|---|---|
| Fabian Giesen, *A trip through the Graphics Pipeline 2011* (fgiesen.wordpress.com) | How GPUs actually work: rasterizer, caches, scheduling | PUB |
| *GPU Gems 1 to 3* (NVIDIA, free online) | Classic GPU algorithms | PUB |
| *Advances in Real-Time Rendering* (advances.realtimerendering.com) | Every SIGGRAPH course, from real engines | PUB |
| Haar and Aaltonen, *GPU-Driven Rendering Pipelines* (SIGGRAPH 2015) | Culling and draw submission on the GPU | PUB |
| Karis, Stubbe, Wihlidal, *A Deep Dive into Nanite Virtualized Geometry* (SIGGRAPH 2021) | Cluster LOD and software rasterization | PUB |
| Arseny Kapoulkine, zeux.io blog; meshoptimizer (MIT, github.com/zeux/meshoptimizer) | Vertex cache, overdraw, meshlets, simplification | MIT |
| Apple, *Metal Best Practices Guide*, WWDC Metal sessions, TBDR docs | Tile-based GPU behaviour on Apple silicon | PUB |
| Dougall Johnson, Apple GPU architecture notes (dougallj.github.io/applegpu) | Public hardware-level notes on Apple GPU | PUB |
| Khronos OpenGL wiki: *Performance*, *Buffer Object Streaming*; *Approaching Zero Driver Overhead* (GDC 2014) | Driver overhead, streaming, persistent mapping | PUB |
| Dear ImGui docs and FAQ (MIT) | Immediate-mode UI cost model | MIT |
| Derivative, TouchDesigner wiki: *Optimization* and cook-chain pages | How a competitor documents its own cook, GPU memory and CPU rules | EULA (docs only) |

### 3.4 Measuring competitors' performance from outside

| Tool | What it measures |
|---|---|
| `powermetrics`, `sample`, `vmmap`, `top`/`ps` | CPU, power, memory, threads of a running app, read-only |
| Instruments / `xctrace` (attach, time profiler) | Where an app spends time, by symbol names the vendor ships; no disassembly |
| DAWBench (dawbench.com) and own project sets | Standardised multi-track and plugin-count load tests |
| Infinite's own plugin host + `tools/re-survey` bounce kit | Per-plugin CPU per block, latency, oversampling cost |
| Audio device loopback + known test signal | Real latency of a host chain |
| Frame-time capture (screen record, Instruments Metal System Trace) | Competitor canvas and video frame pacing |

### 3.5 Hosting, sandboxing and graph scheduling

| Resource | What it gives you | Tag |
|---|---|---|
| VST3 SDK docs (Steinberg, now MIT) | Host/plugin contract, processing, latency | MIT |
| Apple AUv3 / AudioUnit docs | Host rules on macOS | PUB |
| CLAP spec (MIT) | Clean modern plugin ABI and threading rules | MIT |
| Public ADC talks on plugin sandboxing and multi-core graph scheduling | Patterns used by real hosts | PUB |
| `pluginval` (run as a black-box tool only) | Plugin stress testing | GPL (tool use only: never read source) |

---

## 4. 3D, geometry and meshes

### 4.1 Books and reference sites

| Resource | What it gives you | Tag |
|---|---|---|
| *Real-Time Rendering*, 4th ed. (Akenine-Möller, Haines, Hoffman; realtimerendering.com) | The standard reference | PUB |
| *Physically Based Rendering*, 4th ed. (Pharr, Jakob, Humphreys; pbr-book.org free; code BSD-2) | Shapes, BVH, sampling, materials | PUB / BSD |
| Botsch et al., *Polygon Mesh Processing* (pmp-book.org) | Smoothing, simplification, remeshing, parameterisation | PUB |
| Christer Ericson, *Real-Time Collision Detection* | Intersections, BVH, spatial hashing | PUB |
| David Eberly, Geometric Tools (geometrictools.com, Boost licence) | Robust geometry algorithms with code | Boost |
| Inigo Quilez articles (iquilezles.org) | SDFs, smooth min/max, noise, procedural shapes; verify per-article licence | PUB |
| Jamie Wong, *Ray Marching and SDFs* (jamie-wong.com) | Gentle SDF introduction | PUB |

### 4.2 Core mesh algorithms (what 3D nodes do)

| Operation | Primary source | Tag |
|---|---|---|
| Subdivision (Catmull-Clark, Loop) | Catmull and Clark 1978; Loop 1987; Pixar OpenSubdiv docs (Apache) | PUB / Apache |
| Feature-adaptive GPU subdivision | Nießner et al., *Feature-adaptive GPU rendering of Catmull-Clark subdivision surfaces* (TOG 2012) | PUB |
| Simplification / decimation | Garland and Heckbert, *Surface Simplification Using Quadric Error Metrics* (SIGGRAPH 1997); meshoptimizer | PUB / MIT |
| Smoothing | Taubin, *Curve and Surface Smoothing Without Shrinkage* (1995); Botsch (above) | PUB |
| Isosurface (SDF/volume to mesh) | Lorensen and Cline, *Marching Cubes* (1987); Ju et al., *Dual Contouring of Hermite Data* (2002) | PUB |
| Mesh booleans | Zhou et al., *Mesh Arrangements for Solid Geometry* (SIGGRAPH 2016); Cherchi et al. (SIGGRAPH Asia 2020) | PUB |
| Delaunay / Voronoi | Bowyer 1981, Watson 1981; Shewchuk, *Triangle* papers | PUB |
| Poisson disk sampling | Bridson, *Fast Poisson Disk Sampling in Arbitrary Dimensions* (2007) | PUB |
| Normals, tangents | Lengyel, *Foundations of Game Engine Development* (tangent space); mikktspace spec (zlib) | PUB / zlib |
| UV parametrisation | Lévy et al., LSCM (2002); Botsch (above) | PUB |
| Skinning / deformers | Lewis et al., *Pose Space Deformation* (2000); Kavan et al., dual quaternion skinning (2007) | PUB |
| Instancing | Khronos OpenGL wiki: *Instancing*; Metal docs | PUB |
| Culling and LOD | Haar and Aaltonen; Nanite (3.3) | PUB |
| Curves and splines | Farin, *Curves and Surfaces for CAGD*; Catmull-Rom (Barry and Goldman 1988) | PUB |
| Lights, materials | Karis, *Real Shading in Unreal Engine 4* (SIGGRAPH 2013); Burley, *Physically Based Shading at Disney* (2012); glTF 2.0 spec (Khronos) | PUB |
| Shadows | Williams 1978; Donnelly and Lauritzen VSM (2006); Wyman et al. | PUB |

### 4.3 Competitor behaviour for 3D (docs only)

| Source | Use |
|---|---|
| TouchDesigner wiki (docs.derivative.ca): SOP, POP, Geometry COMP, Instancing | What nodes exist, how instancing works |
| Blender manual (docs.blender.org/manual) and Python API docs | Node semantics only. Blender is GPL: no source, no bundled scripts |
| SideFX Houdini docs | The most complete public catalogue of geometry node semantics |
| Cinema 4D, Notch, Resolume docs | Real-time visual-tool semantics |
| glTF 2.0, USD (OpenUSD docs), OBJ, PLY, STL specs | Import/export formats |

---

## 5. Procedural, simulation and generative

| Resource | What it gives you | Tag |
|---|---|---|
| Perlin, *An Image Synthesizer* (1985) and *Improving Noise* (2002) | Gradient noise | PUB |
| Gustavson, *Simplex noise demystified* (2005) | Simplex noise | PUB |
| Bridson, Houriham, Nordenstam, *Curl-noise for procedural fluid flow* (SIGGRAPH 2007) | Divergence-free particle fields | PUB |
| Reeves, *Particle Systems: a technique for modeling a class of fuzzy objects* (1983) | Particle systems | PUB |
| Reynolds, *Flocks, Herds, and Schools* (1987) | Boids | PUB |
| Müller et al., *Position Based Dynamics* (2007); *Ten Minute Physics* (matthias-research.github.io) | Cloth, soft bodies, particles on GPU | PUB |
| Stam, *Stable Fluids* (1999); *Real-Time Fluid Dynamics for Games* (2003) | Real-time fluid | PUB |
| Turk, *Generating textures on arbitrary surfaces using reaction-diffusion* (1991) | Reaction-diffusion | PUB |
| Prusinkiewicz and Lindenmayer, *The Algorithmic Beauty of Plants* (free PDF) | L-systems | PUB |
| The Book of Shaders (thebookofshaders.com) | Shader-based generative basics | PUB |

---

## 6. Compositing and image processing

### 6.1 Compositing theory

| Resource | What it gives you | Tag |
|---|---|---|
| Porter and Duff, *Compositing Digital Images* (SIGGRAPH 1984) | The alpha compositing operators | PUB |
| Alvy Ray Smith, *Image Compositing Fundamentals* (Microsoft Tech Memo 4, 1995) | Premultiplied alpha, why it matters | PUB |
| W3C *Compositing and Blending Level 1* (w3.org/TR/compositing-1) | Exact formulas for all blend modes | PUB |
| Jim Blinn, *Jim Blinn's Corner* (Morgan Kaufmann) | Compositing and colour pitfalls | PUB |
| Smith and Blinn, *Blue Screen Matting* (SIGGRAPH 1996) | Keying | PUB |
| Nuke docs (Foundry public docs) | Reference semantics for merge, keyer, transform | EULA (docs only) |

### 6.2 Image effects (blur, bloom, DOF, AA)

| Resource | What it gives you | Tag |
|---|---|---|
| Kawase, *Frame Buffer Postprocessing Effects in DOUBLE-S.T.E.A.L* (GDC 2003) | Kawase blur | PUB |
| Bjørge, *Bandwidth-Efficient Rendering* (ARM, SIGGRAPH 2015) | Dual-filter blur: very cheap wide blur | PUB |
| Jimenez, *Next Generation Post Processing in Call of Duty: Advanced Warfare* (SIGGRAPH 2014) | Bloom, DOF, motion blur in production | PUB |
| Rastergrid, *Efficient Gaussian blur with linear sampling* | Cut the taps by half with bilinear | PUB |
| McGuire et al., *A Reconstruction Filter for Plausible Motion Blur* (2012) | Motion blur | PUB |
| Lottes, FXAA (NVIDIA); Jimenez et al., SMAA (2012); Karis, *High Quality Temporal Supersampling* (SIGGRAPH 2014) | Anti-aliasing | PUB |
| Farnebäck, *Two-frame motion estimation based on polynomial expansion* (2003); Horn and Schunck (1981) | Optical flow for retiming | PUB |

### 6.3 Colour and tone

| Resource | What it gives you | Tag |
|---|---|---|
| Björn Ottosson, *A perceptual color space for image processing* (Oklab, bottosson.github.io) | Oklab: blending and gradients that look right (public domain / MIT) | PD / MIT |
| OpenColorIO and ACES docs (BSD) | Colour management in film pipelines | BSD |
| Bruce Lindbloom (brucelindbloom.com) | Colour conversion maths | PUB |
| Hable, *Filmic Tonemapping Operators* (Uncharted 2, GDC 2010); Narkowicz ACES fit; Reinhard et al. (2002) | Tone mapping | PUB |
| Colour Science for Python (BSD) | Reference implementations to test against | BSD |

### 6.4 Video and output

| Resource | What it gives you | Tag |
|---|---|---|
| Apple, VideoToolbox and AVFoundation docs | Hardware decode/encode | PUB |
| Syphon (BSD) and Spout (BSD) docs and code | Texture sharing between apps | BSD |
| NDI SDK docs | Network video | EULA (SDK terms) |
| FFmpeg docs (docs only; code is LGPL/GPL) | Codec/filter semantics | LGPL/GPL (docs only) |
| Projection mapping: Szeliski, *Computer Vision: Algorithms and Applications* (free online) | Homography, warping, edge blending | PUB |

---

## 7. Licence traps (do not cross)

| Source | Rule |
|---|---|
| Vital, Surge, Bespoke, VCV Rack, Blender, OBS, VLC, SuperCollider, Kronos, Cmajor | GPL/AGPL: docs and observed behaviour only |
| FFmpeg, x264, pluginval, Natron | LGPL/GPL: docs and tool use only |
| Musicdsp.org, forum snippets | Licence unclear: take the idea, write our own |
| FabFilter, Valhalla, u-he, Serum, Ableton, Logic, Bitwig, TouchDesigner | EULA: public docs, black-box measurement |
| Papers | Ideas free; any accompanying code has its own licence: check it |
| Commercial books with code (Pirkle, Zölzer) | Ideas free; do not copy listings |

## 8. Reading order (suggested)

1. Section 2 and 1.8 first: they set up the measurement pipeline.
2. Per competitor: row in section 0 → sections listed → measure → fit → dossier.
3. Performance: 3.1 then 3.2 as the base, 3.3 for canvas/projector, 3.4 to measure rivals.
4. 3D: 4.1 then 4.2 as needed per node; 6.1 before any blend or alpha change.

Link check 2026-10-12: all domains named above answer (200), except valhalladsp.com and realtimerendering.com (403, bot block, open in a browser), iquilezles.org (404 from curl, search "Inigo Quilez articles") and rossbencina.com (timed out). Paper titles are exact enough to search.
