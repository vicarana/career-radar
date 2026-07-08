#!/usr/bin/env python3
"""Generate simple PWA icons (pure stdlib, no PIL). Sky dot on navy."""
import struct, zlib, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "docs")
BG = (15, 23, 42)       # navy
FG = (56, 189, 248)     # sky


def png(size, path):
    cx = cy = size / 2
    r = size * 0.30
    r2 = r * r
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0
        for x in range(size):
            d = (x - cx) ** 2 + (y - cy) ** 2
            raw += bytes(FG if d <= r2 else BG)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", ihdr))
        f.write(chunk(b"IDAT", comp))
        f.write(chunk(b"IEND", b""))
    print("wrote", path)


png(192, os.path.join(OUT, "icon-192.png"))
png(512, os.path.join(OUT, "icon-512.png"))
