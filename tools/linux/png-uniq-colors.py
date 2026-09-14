#!/usr/bin/env python3
"""Print the number of distinct RGB colours in a PNG.

Used by shots.sh as its "did anything actually render" gate on hosts without
ImageMagick (macOS). Deliberately dependency-free - no Pillow, no numpy - so it
runs on a stock macOS python3 and inside the Linux dev container alike.

Handles what stb_image_write emits: 8-bit, non-interlaced, RGB or RGBA.
"""

import struct
import sys
import zlib


def read_png(path):
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")

    pos = 8
    idat = bytearray()
    width = height = depth = colour_type = None

    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length  # length + type + data + crc

        if kind == b"IHDR":
            width, height, depth, colour_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", chunk)
            if interlace:
                raise ValueError("interlaced PNG not supported")
            if depth != 8:
                raise ValueError("only 8-bit PNGs supported")
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break

    channels = {0: 1, 2: 3, 4: 2, 6: 4}[colour_type]
    raw = zlib.decompress(bytes(idat))
    stride = width * channels

    # Undo the per-scanline filters (PNG spec 9.2). Straightforward rather than
    # clever: these images are read once, in a test gate.
    out = bytearray()
    prev = bytearray(stride)
    pos = 0
    for _ in range(height):
        filt = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if filt:
            for x in range(stride):
                a = line[x - channels] if x >= channels else 0
                b = prev[x]
                c = prev[x - channels] if x >= channels else 0
                if filt == 1:
                    line[x] = (line[x] + a) & 0xFF
                elif filt == 2:
                    line[x] = (line[x] + b) & 0xFF
                elif filt == 3:
                    line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
                elif filt == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    line[x] = (line[x] + pred) & 0xFF
                else:
                    raise ValueError("bad filter %d" % filt)
        out += line
        prev = line

    return width, height, channels, bytes(out)


def main():
    width, height, channels, px = read_png(sys.argv[1])
    # Sample rather than walk every pixel: the counts this feeds are compared
    # against a threshold three orders of magnitude apart (a blank editor lands
    # near 500, a real render in the thousands), so a 200k-pixel sample decides
    # it just as well and keeps the gate fast on a 3200x2000 Retina grab.
    total = width * height
    step = max(1, total // 200000)
    colours = set()
    for i in range(0, total, step):
        off = i * channels
        colours.add(px[off:off + 3])
    print(len(colours))


if __name__ == "__main__":
    main()
