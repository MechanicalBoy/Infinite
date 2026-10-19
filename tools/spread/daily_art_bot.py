#!/usr/bin/env python3
"""infinite autonomous generative video & social distribution bot.

what: automatically synthesizes complete audio-reactive generative videos
      (2d javascript sketches and glsl shaders + modular audio dsp),
      validates them with the infinite c++20 engine, and exports stage-ready
      video loops (.mp4), high-res stills (.png), and clean lowercase copy.
"""

import argparse
import datetime
import glob
import json
import os
import random
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def escape_code(s):
    return s.replace('\\', '\\\\').replace('\n', '\\n')


def build_clifford_patch(js):
    esc = escape_code(js)
    return f"""infinite-patch 1
node 1 Notes Random Note Generator
  id notes
end
node 2 Synths Wavetable
  id synth
end
node 3 Utility Audio Out
  id speaker
end
node 4 Source Sketch
  id sk
  f width 720
  f height 720
  s code {esc}
end
node 5 Utility Output
  id out
end
note synth 0 notes
aud speaker 0 synth
cable out 0 sk
"""


def build_lorenz_patch(js):
    esc = escape_code(js)
    return f"""infinite-patch 1
node 1 Notes Arpeggiator
  id arp
end
node 2 Synths FM
  id synth
end
node 3 Utility Audio Out
  id speaker
end
node 4 Source Sketch
  id sk
  f width 720
  f height 720
  s code {esc}
end
node 5 Utility Output
  id out
end
note synth 0 arp
aud speaker 0 synth
cable out 0 sk
"""


def build_tunnel_patch(glsl):
    return f"""infinite-patch 1
node 1 Notes Random Note Generator
  id notes
end
node 2 Synths Wavetable
  id synth
end
node 3 Utility Audio Out
  id speaker
end
node 4 Source FieldPixel
  id visuals
  f width 720
  f height 720
  s code {glsl}
end
node 5 Utility Output
  id out
end
note synth 0 notes
aud speaker 0 synth
cable out 0 visuals
"""


RECIPES = [
    {
        "id": "clifford_attractor",
        "title": "clifford strange attractor with dynamic velocity trails",
        "category": "2d javascript sketch",
        "description": "8,000 algorithmic points computed via non-linear trigonometric recurrence and rendered into an infinite canvas.",
        "tags": ["#creativecoding", "#generativeart", "#javascript", "#visualsynthesizer", "#opensource"],
        "js_code": """
param("points", 8000, 1000, 20000);
param("drift", 0.25, 0, 1);
param("size", 1.8, 0.5, 4);

function draw(t) {
  background(0.02, 0.02, 0.05);
  const a = -1.4 + 0.3 * sin(t * drift);
  const b = 1.6 + 0.25 * cos(t * drift * 0.8);
  const c = 1.0 + 0.2 * sin(t * drift * 0.6);
  const d = 0.7;
  let x = 0.1, y = 0.1;
  const k = min(width, height) * 0.22;
  noStroke();
  for (let i = 0; i < points; i++) {
    const nx = sin(a * y) + c * cos(a * x);
    const ny = sin(b * x) + d * cos(b * y);
    x = nx; y = ny;
    if (i > 15) {
      fill(hsl(0.5 + 0.35 * (i / points), 0.8, 0.65, 0.4));
      circle(width / 2 + x * k, height / 2 + y * k, size);
    }
  }
}
""".strip(),
        "patch_builder": build_clifford_patch
    },
    {
        "id": "lorenz_flow",
        "title": "lorenz chaotic attractor vector flow",
        "category": "2d javascript sketch",
        "description": "continuous differential system showing sensitivity to initial conditions modulated by audio transport.",
        "tags": ["#mathart", "#generative", "#chaos", "#audiovisual", "#creativecode"],
        "js_code": """
param("steps", 3000, 500, 8000);
param("speed", 0.8, 0.1, 2);

function draw(t) {
  background(0.03, 0.02, 0.06);
  const sigma = 10, rho = 28, beta = 8/3;
  let x = 0.1, y = 0.1, z = 0.1;
  const dt = 0.008;
  const cx = width / 2, cy = height / 2;
  noStroke();
  for (let i = 0; i < steps; i++) {
    const dx = sigma * (y - x) * dt;
    const dy = (x * (rho - z) - y) * dt;
    const dz = (x * y - beta * z) * dt;
    x += dx; y += dy; z += dz;
    const px = cx + x * 9.0;
    const py = cy + (y * 0.7 - (z - 25)) * 8.5;
    fill(hsl(0.75 + 0.25 * sin(t * speed + i * 0.001), 0.85, 0.6, 0.5));
    circle(px, py, 1.6);
  }
}
""".strip(),
        "patch_builder": build_lorenz_patch
    },
    {
        "id": "glsl_raymarch_tunnel",
        "title": "audio-reactive raymarched tunnel",
        "category": "glsl field shader",
        "description": "infinite volumetric signed distance field with dynamic audio-reactive modulation and chromatic dispersion.",
        "tags": ["#glsl", "#shaders", "#raymarching", "#vj", "#touchdesigner"],
        "glsl_code": "p = (uv - 0.5) * aspect; r = length(p); a = atan2(p.y, p.x); col = vec3(0.5 + 0.5 * sin(r * 14.0 - t * 3.0 + a * 4.0)) * vec3(0.9, 0.45, 0.85);",
        "patch_builder": build_tunnel_patch
    }
]


def find_infinite():
    candidates = [
        "/Applications/Infinite.app/Contents/MacOS/Infinite",
        os.path.join(ROOT, "build", "Infinite.app", "Contents", "MacOS", "Infinite"),
        os.path.join(ROOT, "build-check", "Infinite.app", "Contents", "MacOS", "Infinite"),
        os.path.join(ROOT, "build", "Infinite"),
        shutil.which("Infinite") or "",
    ]
    for c in candidates:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


def render_item(recipe, out_dir, duration=5):
    os.makedirs(out_dir, exist_ok=True)
    item_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{recipe['id']}"
    target_dir = os.path.join(out_dir, item_id)
    os.makedirs(target_dir, exist_ok=True)

    code = recipe.get("js_code") or recipe.get("glsl_code")
    patch_text = recipe["patch_builder"](code)
    patch_path = os.path.join(target_dir, f"{recipe['id']}.inf")
    with open(patch_path, "w") as f:
        f.write(patch_text)

    infinite = find_infinite()
    if not infinite:
        sys.exit("infinite binary not found")

    # 1. validate
    val = subprocess.run([infinite, "--validate", patch_path], capture_output=True, text=True)
    if val.returncode != 0:
        sys.exit(f"validation failed: {val.stdout}")

    # 2. audio synthesis
    wav_path = os.path.join(target_dir, "audio.wav")
    summary_path = os.path.join(target_dir, "summary.json")
    subprocess.run([
        infinite, "--audio-summary", patch_path, summary_path,
        "--wav", wav_path, "--duration", str(duration)
    ], check=True, stdout=subprocess.DEVNULL)

    # 3. video render
    raw_video = os.path.join(target_dir, "video_raw.mp4")
    subprocess.run([
        infinite, "--render", patch_path, raw_video,
        "--duration", str(duration), "--fps", "30"
    ], check=True, stdout=subprocess.DEVNULL)

    # 4. still poster frame
    poster_path = os.path.join(target_dir, "poster.png")
    subprocess.run([
        infinite, "--frame", patch_path, "1.0", poster_path
    ], check=True, stdout=subprocess.DEVNULL)

    # 5. mux audio + video with ffmpeg
    final_video = os.path.join(target_dir, f"{recipe['id']}.mp4")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and os.path.exists(wav_path) and os.path.exists(raw_video):
        subprocess.run([
            ffmpeg, "-y", "-i", raw_video, "-i", wav_path,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
            final_video
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.remove(raw_video)
    else:
        final_video = raw_video

    # 6. generate clean social copy
    social_text = f"""{recipe['title']}

{recipe['description']}

rendered in real time using infinite (c++20 / opengl modular daw).
no external plugins, 100% free and open-source.

code and interactive canvas: https://infinitedevices.org
github: https://github.com/n1m21n/infinite

{' '.join(recipe['tags'])}
""".strip()

    with open(os.path.join(target_dir, "post.txt"), "w") as f:
        f.write(social_text)

    metadata = {
        "id": item_id,
        "title": recipe["title"],
        "category": recipe["category"],
        "date": datetime.datetime.now().isoformat(),
        "video": os.path.relpath(final_video, ROOT),
        "poster": os.path.relpath(poster_path, ROOT),
        "patch": os.path.relpath(patch_path, ROOT),
        "social_text": social_text,
    }

    with open(os.path.join(target_dir, "meta.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def main():
    parser = argparse.ArgumentParser(description="infinite daily art distribution bot")
    parser.add_argument("--recipe", choices=[r["id"] for r in RECIPES], help="pick a specific recipe")
    parser.add_argument("--out-dir", default=os.path.join(ROOT, "dist", "social_queue"), help="queue directory")
    parser.add_argument("--duration", type=int, default=5, help="duration in seconds")
    args = parser.parse_args()

    selected = None
    if args.recipe:
        selected = next(r for r in RECIPES if r["id"] == args.recipe)
    else:
        selected = random.choice(RECIPES)

    print(f"selected recipe: {selected['title']}")
    meta = render_item(selected, args.out_dir, args.duration)
    print("generation complete:")
    print(f"video:  {meta['video']}")
    print(f"poster: {meta['poster']}")
    print()
    print("social copy ready:")
    print("-----------------------------------------------------------------")
    print(meta["social_text"])
    print("-----------------------------------------------------------------")


if __name__ == "__main__":
    main()
