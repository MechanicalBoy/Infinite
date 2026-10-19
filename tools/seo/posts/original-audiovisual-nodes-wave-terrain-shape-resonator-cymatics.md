---
title: Unique nodes in Infinite: Wave Terrain, Shape Resonator, and Cymatics
description: Explore Infinite original nodes: convert images to sound with Wave Terrain, ring 3D geometry with Shape Resonator, and simulate Chladni cymatics.
date: 2026-10-19
category: creative
tags: [wave terrain, shape resonator, cymatics, sound design, creative coding]
image: assets/nodes/Wave Terrain.png
image_alt: wave terrain synthesis node interface in infinite daw
keywords: wave terrain synthesis, shape resonator, 3d mesh to audio, audio displacement, cymatics simulation, desmos synth, equation oscillator
status: published
---

most creative software falls into one of two camps: digital audio workstations that treat visuals as an afterthought, or visual patchers (like touchdesigner or blender) that treat audio as a simple control voltage or fft spectrum.

infinite was designed from day one on a unified execution graph. sound, 2d textures, and 3d geometry live in the same memory space, enabling node architectures that simply do not exist in conventional daws.

here is an in-depth breakdown of seven standout original nodes in infinite that bridge sound, mathematics, and geometry.

---

## 1. wave terrain: converting images and textures into sound

wave terrain synthesis treats any 2d image—whether a drawn sketch, a webcam feed, a reaction-diffusion pattern, or procedural noise—as a continuous 3d topographic terrain surface $z = T(u, v)$.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Wave%20Terrain.png" alt="wave terrain synthesis node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">wave terrain node: scanning continuous 2d image topography at audio rates</figcaption>
</figure>

### how it works
1. **orbital trajectories**: an audio-rate oscillator traces a closed parametric path $(u(t), v(t))$ across the image (such as an ellipse, lissajous curve, lemniscate, or spiral).
2. **topographic sampling**: as the orbital point scans across pixels, the surface height $z$ becomes the instantaneous audio amplitude.
3. **10-level fourier mip pyramid**: raw pixel sampling produces harsh digital aliasing. infinite solves this by computing a real discrete fourier transform (rdft) mip pyramid across 10 octaves, ensuring completely alias-free polyphonic synthesis across all 8 octaves.

---

## 2. shape resonator: converting 3d geometry into physical sound

what does a 3d torus sound like when struck? what does an icosphere sound like compared to a long cylindrical tube?

the **shape resonator** node answers this by computing the acoustic standing waves and vibration modes of any input 3d geometry mesh.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Shape%20Resonator.png" alt="shape resonator node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">shape resonator node: physical modal acoustic resonance of 3d geometry</figcaption>
</figure>

### how it works
1. **laplace-beltrami modal solver**: on a dedicated worker thread, infinite solves the surface-laplacian eigenvalues $\lambda_i$ of the mesh.
2. **dispersion law**: mode frequencies follow the dispersion of a physical membrane or thin plate:
   $$f_i = \text{tune} \times \sqrt{\frac{\lambda_i}{\lambda_0}}$$
3. **strike and pickup positioning**: where you hit the 3d shape in space weights which modes resonate, while the pickup position determines which harmonics reach your speakers. hitting a nodal line silences that harmonic, exactly like a physical acoustic gong or vibraphone bar.
4. **lock-free triple buffer**: the modal solve runs asynchronously, handing finished two-pole coupled-form phasor coefficients to the 48khz audio thread with zero glitches.

---

## 3. audio displacement: cymatics and mesh deformation

the **audio displacement** node takes any 3d mesh and deforms its vertex topology in real time directly from incoming audio waveforms.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Audio%20Displacement.png" alt="audio displacement node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">audio displacement node: 5 real-time deformation modes including chladni cymatics</figcaption>
</figure>

### five real-time modes
- **normal waveform**: pushes vertices outward along their surface normals proportionally to the raw oscilloscope audio signal.
- **spectral bands**: deforms vertices along the u/x axis based on real-time fft frequency bins.
- **acoustic ripples**: generates concentric radial wave rings expanding outward from the center.
- **chladni cymatics**: simulates ernst chladni's 2d and 3d acoustic standing wave nodal patterns:
  $$w = \sin(n \pi x) \sin(m \pi y) \pm \sin(m \pi x) \sin(n \pi y)$$
- **directional axis**: displaces vertices along specific global or local Cartesian axes.

---

## 4. equation synth: desmos-style mathematical synthesis

for artists who think in mathematical formulas, **equation synth** provides an interactive cartesian graphing plane where any mathematical formula $y = f(x, a, b, c, d)$ becomes an anti-aliased polyphonic synthesizer.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Equation%20Synth.png" alt="equation synth node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">equation synth node: evaluating mathematical curves as anti-aliased wavetables</figcaption>
</figure>

whether exploring chebyshev polynomials, weierstrass fractal curves, or phase-modulated gaussian wave packets, equation synth graphs the function visually and compiles it into bandlimited wavetable mipmaps for pristine audio playback.

---

## 5. audio ribbon: 3d physical waveform extrusion

the **audio ribbon** node extrudes incoming audio waveforms into a physical 3d ribbon geometry traveling through space.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Audio%20Ribbon.png" alt="audio ribbon node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">audio ribbon node: extruded 3d waveform mesh with physical pbr materials</figcaption>
</figure>

unlike 2d flat oscilloscope lines, the audio ribbon is a true procedural polygonal mesh that can be lit with directional lights, cast shadows, and rendered with physically based metallic and emission materials.

---

## 6. audio color ramp: sound-driven color palettes

the **audio color ramp** node analyzes live frequency spectrums and dynamically drives gradient color ramps used across 2d visuals, 3d materials, and shader backgrounds.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Audio%20Color%20Ramp.png" alt="audio color ramp node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">audio color ramp node: modulating color stops and gradients from live audio</figcaption>
</figure>

### operating modes
- **intensity mode**: low frequencies cause deep color glow while high-frequency percussion triggers bright highlights.
- **expansion mode**: frequency band energies dynamically expand and contract the spatial boundaries of each color stop.
- **spectrum mode**: maps the continuous real-time fft spectrum directly onto the custom palette.

---

## 7. audio texture: audio-rate gpu textures

the **audio texture** node converts audio streams directly into a 2d gpu texture at 60 fps.

<figure style="margin:20px 0;text-align:center;">
  <img src="../assets/nodes/Audio%20Texture.png" alt="audio texture node in infinite" style="max-width:100%;border-radius:12px;border:1px solid rgba(255,255,255,0.1);">
  <figcaption style="font-size:12px;opacity:0.75;margin-top:6px;">audio texture node: streaming audio waveforms and spectrograms as gpu textures</figcaption>
</figure>

this texture can be cabled directly into materials, raymarchers, and field pixel shader nodes, allowing custom glsl kernels to sample audio buffers as standard `sampler2D` textures with zero cpu overhead.

---

## more standout nodes to explore

in addition to these seven audiovisual transformers, infinite includes over 300 modular nodes spanning physics, generative art, and signal processing:
- **reaction diffusion**: gray-scott chemical morphogenesis simulation creating organic spots, stripes, and cellular patterns.
- **klein bottle & mobius strip**: non-orientable 4d and 3d topological manifold surfaces.
- **fluid**: real-time 2d navier-stokes grid fluid dynamics with velocity advection and dye injection.
- **cloth**: verlet particle-spring physics simulation responding to audio wind and turbulence.
- **paulstretch**: extreme 64-bit spectral phase vocoder stretching audio by 10x to 1000x into lush ambient drones.
- **face, hand, & pose track**: on-device neural vision modulators turning physical movement into modulation cables.

all of these nodes run natively on macos, windows, and linux, and can be inspected in the [node reference manual](https://infinitedevices.org/assets/Infinite_Node_Reference_Manual.pdf) and [library gallery](https://infinitedevices.org/library.html).
