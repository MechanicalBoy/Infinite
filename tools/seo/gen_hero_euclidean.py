#!/usr/bin/env python3
"""Generate the technical hero diagram for the Euclidean rhythm sequencer post.
Outputs a crisp 1200x675 brand-compliant image to website/assets/blog_euclidean_rhythm_sequencer.png.
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 675
img = Image.new("RGBA", (W, H), (13, 16, 32, 255)) # Midnight deep #0D1020
draw = ImageDraw.Draw(img)

# Fonts
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FONT_DIR = os.path.join(REPO_ROOT, "art", "brand", "fonts")
GEIST_SEMIBOLD = os.path.join(FONT_DIR, "Geist-SemiBold.ttf")
GEIST_MONO = os.path.join(FONT_DIR, "GeistMono-Medium.ttf")

try:
    f_title = ImageFont.truetype(GEIST_SEMIBOLD, 28)
    f_sub = ImageFont.truetype(GEIST_SEMIBOLD, 14)
    f_badge = ImageFont.truetype(GEIST_MONO, 11)
    f_body = ImageFont.truetype(GEIST_SEMIBOLD, 12)
    f_mono = ImageFont.truetype(GEIST_MONO, 12)
    f_mono_sm = ImageFont.truetype(GEIST_MONO, 11)
    f_formula = ImageFont.truetype(GEIST_MONO, 13)
except Exception:
    f_title = f_sub = f_badge = f_body = f_mono = f_mono_sm = f_formula = ImageFont.load_default()

# 1. Subtle background dot grid
dot_color = (35, 42, 74, 180) # #232A4A
for gx in range(24, W - 24, 28):
    for gy in range(24, H - 24, 28):
        draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=dot_color)

# 2. Outer decorative frame
draw.rounded_rectangle([20, 20, W - 20, H - 20], radius=16, outline=(42, 48, 82, 255), width=1)

# 3. Header section
# Top pill badge: INFINITE // ALGORITHMIC AUDIO
pill_box = [45, 42, 330, 68]
draw.rounded_rectangle(pill_box, radius=6, fill=(32, 38, 63, 255), outline=(52, 59, 94, 255), width=1)
draw.text((58, 48), "INFINITE  //  ALGORITHMIC AUDIO ARCHITECTURE", font=f_badge, fill=(167, 177, 255, 255)) # Signal #A7B1FF

# Right pill: TRACK B: CREATIVE CODING
draw.rounded_rectangle([W - 250, 42, W - 45, 68], radius=6, fill=(32, 38, 63, 255), outline=(52, 59, 94, 255), width=1)
draw.text((W - 238, 48), "TRACK B: CREATIVE CODING", font=f_badge, fill=(238, 241, 250, 255)) # Ink #EEF1FA

# Main title and subtitle
draw.text((45, 84), "Euclidean Rhythm Sequencer Algorithm", font=f_title, fill=(238, 241, 250, 255))
draw.text((45, 122), "Integer Bresenham distribution, modular clock division, and synchronous geometry deformation", font=f_sub, fill=(163, 170, 203, 255)) # Ink-2 #A3AACB

# Horizontal rule below header
draw.line([(45, 148), (W - 45, 148)], fill=(42, 48, 82, 255), width=1)

# 4. Left Pane: Concentric Euclidean Polar Clocks
cx, cy = 305, 395

# Radial division spokes (16 steps outer)
for s in range(16):
    angle = -math.pi / 2.0 + (2.0 * math.pi * s / 16.0)
    rx = cx + 205 * math.cos(angle)
    ry = cy + 205 * math.sin(angle)
    draw.line([(cx, cy), (rx, ry)], fill=(32, 38, 63, 140), width=1)

# Ring configurations: (pulses, steps, radius, color_active, label)
# E(7, 16): Samba / Aksak
# E(5, 12): Bembe / West African Bell
# E(3, 8): Tresillo / Habanera
rings = [
    (7, 16, 185, (255, 107, 53, 255), (255, 158, 121, 255), "E(7, 16) SAMBA"),
    (5, 12, 130, (167, 177, 255, 255), (167, 177, 255, 255), "E(5, 12) BEMBE"),
    (3, 8, 75, (217, 67, 14, 255), (255, 107, 53, 255), "E(3, 8) TRESILLO")
]

# Draw circular guide rings
for _, _, r, _, _, _ in rings:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(42, 48, 82, 220), width=1)

# Function to compute Euclidean pattern using Bresenham integer division
def get_euclid_pattern(k, n):
    pattern = []
    for s in range(n):
        on = math.floor((s + 1) * k / n + 0.0001) - math.floor(s * k / n + 0.0001)
        pattern.append(on >= 1)
    return pattern

# Draw polygons connecting active hits
poly_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
poly_draw = ImageDraw.Draw(poly_layer)

for k, n, r, col_active, col_edge, label in rings:
    pat = get_euclid_pattern(k, n)
    active_pts = []
    for s in range(n):
        angle = -math.pi / 2.0 + (2.0 * math.pi * s / float(n))
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        if pat[s]:
            active_pts.append((px, py))
    
    # Inscribed polygon with subtle fill
    if len(active_pts) >= 3:
        fill_col = (col_active[0], col_active[1], col_active[2], 26)
        poly_draw.polygon(active_pts, fill=fill_col, outline=(col_edge[0], col_edge[1], col_edge[2], 180))

# Composite polygon layer
img = Image.alpha_composite(img, poly_layer)
draw = ImageDraw.Draw(img)

# Draw step nodes / pips on top of polygons
for k, n, r, col_active, col_edge, label in rings:
    pat = get_euclid_pattern(k, n)
    for s in range(n):
        angle = -math.pi / 2.0 + (2.0 * math.pi * s / float(n))
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        is_hit = pat[s]
        
        if is_hit:
            # Active hit: glowing double pip
            glow_r = 7
            draw.ellipse([px - glow_r, py - glow_r, px + glow_r, py + glow_r], fill=(col_active[0], col_active[1], col_active[2], 80))
            draw.ellipse([px - 4, py - 4, px + 4, py + 4], fill=col_active, outline=(238, 241, 250, 255), width=1)
        else:
            # Rest: small hollow pip
            draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(21, 25, 48, 255), outline=(52, 59, 94, 255), width=1)

# Ring labels
draw.text((cx - 40, cy - 185 - 18), "E(7, 16) SAMBA", font=f_badge, fill=(255, 158, 121, 255))
draw.text((cx - 38, cy - 130 - 18), "E(5, 12) BEMBE", font=f_badge, fill=(167, 177, 255, 255))
draw.text((cx - 44, cy - 75 - 18), "E(3, 8) TRESILLO", font=f_badge, fill=(255, 107, 53, 255))

# Centre crosshair
draw.line([(cx - 8, cy), (cx + 8, cy)], fill=(167, 177, 255, 255), width=1)
draw.line([(cx, cy - 8), (cx, cy + 8)], fill=(167, 177, 255, 255), width=1)

# Phase rotation arrow indicator
draw.arc([cx - 215, cy - 215, cx + 215, cy + 215], start=-100, end=-30, fill=(255, 107, 53, 200), width=2)
# Arrow head at -30 deg
a_tip = -30 * math.pi / 180.0
at_x = cx + 215 * math.cos(a_tip)
at_y = cy + 215 * math.sin(a_tip)
draw.polygon([(at_x, at_y), (at_x - 8, at_y - 3), (at_x - 3, at_y + 8)], fill=(255, 107, 53, 255))
draw.text((cx + 140, cy - 195), "PHASE ROTATE", font=f_badge, fill=(255, 107, 53, 255))

# 5. Right Pane: Technical Cards (x=550 to x=1155)
rx1, ry1, rx2, ry2 = 560, 168, W - 45, H - 42
draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, fill=(21, 25, 48, 255), outline=(42, 48, 82, 255), width=1)

# Card Section 1: Integer Formula
draw.text((rx1 + 20, ry1 + 16), "INTEGER DISTRIBUTION FORMULA", font=f_badge, fill=(255, 107, 53, 255))

fbox = [rx1 + 20, ry1 + 36, rx2 - 20, ry1 + 86]
draw.rounded_rectangle(fbox, radius=6, fill=(13, 16, 32, 255), outline=(35, 42, 74, 255), width=1)
draw.text((rx1 + 32, ry1 + 45), "on(s) = floor((s + 1) * k / n) - floor(s * k / n)", font=f_formula, fill=(238, 241, 250, 255))
draw.text((rx1 + 32, ry1 + 67), "where s in [0..n-1], k = active pulses, n = total step division", font=f_mono_sm, fill=(163, 170, 203, 255))

# Card Section 2: Field Notes Kernel
draw.text((rx1 + 20, ry1 + 102), "FIELD NOTES DSP KERNEL", font=f_badge, fill=(167, 177, 255, 255))

cbox = [rx1 + 20, ry1 + 122, rx2 - 20, ry1 + 276]
draw.rounded_rectangle(cbox, radius=6, fill=(13, 16, 32, 255), outline=(35, 42, 74, 255), width=1)

code_lines = [
    ("// Sample-accurate Euclidean trigger evaluation in Field Notes", (98, 107, 144, 255)),
    ("param float hits = 5 [1, 16]", (167, 177, 255, 255)),
    ("param float steps = 16 [1, 32]", (167, 177, 255, 255)),
    ("param float rotate = 0 [0, 15]", (167, 177, 255, 255)),
    ("if (tick(1/16) > 0.5) {", (238, 241, 250, 255)),
    ("   s = (step + rotate) % steps", (163, 170, 203, 255)),
    ("   on = floor((s + 1) * hits / steps + 0.001) - floor(s * hits / steps + 0.001)", (255, 107, 53, 255)),
    ("   if (on > 0.5) note(deg(0), 0.85, 1/16)", (167, 177, 255, 255)),
    ("   step = (step + 1) % steps", (163, 170, 203, 255)),
    ("}", (238, 241, 250, 255)),
]

line_y = ry1 + 130
for text, col in code_lines:
    draw.text((rx1 + 32, line_y), text, font=f_mono_sm, fill=col)
    line_y += 14

# Card Section 3: Audio-Visual Signal Flow
draw.text((rx1 + 20, ry1 + 292), "AUDIO-VISUAL SIGNAL GRAPH", font=f_badge, fill=(238, 241, 250, 255))

gbox = [rx1 + 20, ry1 + 312, rx2 - 20, ry2 - 18]
draw.rounded_rectangle(gbox, radius=6, fill=(13, 16, 32, 255), outline=(35, 42, 74, 255), width=1)

# Node boxes inside graph
def draw_node(bx, by, bw, bh, title, sub, stroke_col):
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=6, fill=(32, 38, 63, 255), outline=stroke_col, width=1)
    draw.text((bx + 10, by + 7), title, font=f_body, fill=(238, 241, 250, 255))
    draw.text((bx + 10, by + 23), sub, font=f_mono_sm, fill=(163, 170, 203, 255))

# Row 1: Audio Chain
draw_node(rx1 + 35, ry1 + 326, 120, 42, "Field Notes", "E(5, 16) KERNEL", (74, 84, 214, 255))
draw_node(rx1 + 215, ry1 + 326, 130, 42, "Drum Sampler", "808 TRANSIENTS", (255, 107, 53, 255))
draw_node(rx1 + 400, ry1 + 326, 110, 42, "Audio Out", "STEREO MASTER", (52, 59, 94, 255))

# Wire 1: Field Notes -> Drum Sampler
draw.line([(rx1 + 155, ry1 + 347), (rx1 + 215, ry1 + 347)], fill=(255, 107, 53, 255), width=2)
draw.ellipse([rx1 + 153, ry1 + 345, rx1 + 157, ry1 + 349], fill=(255, 107, 53, 255))
draw.ellipse([rx1 + 213, ry1 + 345, rx1 + 217, ry1 + 349], fill=(255, 107, 53, 255))

# Wire 2: Drum Sampler -> Audio Out
draw.line([(rx1 + 345, ry1 + 347), (rx1 + 400, ry1 + 347)], fill=(167, 177, 255, 255), width=2)
draw.ellipse([rx1 + 343, ry1 + 345, rx1 + 347, ry1 + 349], fill=(167, 177, 255, 255))
draw.ellipse([rx1 + 398, ry1 + 345, rx1 + 402, ry1 + 349], fill=(167, 177, 255, 255))

# Row 2: Visual 3D Chain
draw_node(rx1 + 215, ry1 + 386, 130, 42, "Instance on Points", "VERTEX DISPLACE", (167, 177, 255, 255))
draw_node(rx1 + 400, ry1 + 386, 110, 42, "Render 3D", "PULSE LATTICE", (74, 84, 214, 255))

# Wire 3: Field Notes branch down to Instance on Points
draw.line([(rx1 + 95, ry1 + 368), (rx1 + 95, ry1 + 407), (rx1 + 215, ry1 + 407)], fill=(167, 177, 255, 200), width=2)
draw.ellipse([rx1 + 93, ry1 + 366, rx1 + 97, ry1 + 370], fill=(167, 177, 255, 255))
draw.ellipse([rx1 + 213, ry1 + 405, rx1 + 217, ry1 + 409], fill=(167, 177, 255, 255))

# Wire 4: Instance on Points -> Render 3D
draw.line([(rx1 + 345, ry1 + 407), (rx1 + 400, ry1 + 407)], fill=(74, 84, 214, 255), width=2)
draw.ellipse([rx1 + 343, ry1 + 405, rx1 + 347, ry1 + 409], fill=(74, 84, 214, 255))
draw.ellipse([rx1 + 398, ry1 + 405, rx1 + 402, ry1 + 409], fill=(74, 84, 214, 255))

# Save image
out_path = os.path.join(REPO_ROOT, "website", "assets", "blog_euclidean_rhythm_sequencer.png")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
img.convert("RGB").save(out_path, "PNG", optimize=True)
print(f"Generated {out_path} ({W}x{H})")
