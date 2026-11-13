#!/usr/bin/env python3
"""Garuda Nebula — entry for make.fun's "Make the coolest art" bounty.

Reads the artwork held in this repository (art.png, an indexed PNG),
gives it a deterministic finishing pass — a warm golden lift, richer
saturation, a gentle vignette and a scatter of new stars in the nebula
sky — and writes the finished piece to /output/entry.png as an indexed
PNG on the artwork's own palette.

Deterministic: no network, no randomness; every run writes the same bytes.
If the finishing pass ever fails, the held artwork is copied unchanged.
"""
import os
import struct
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "art.png")
OUT_DIR = "/output"
OUT = os.path.join(OUT_DIR, "entry.png")


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_indexed_png(data):
    """Decode a non-interlaced 8-bit indexed PNG. Returns (w, h, palette, indices)."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    palette = None
    idat = bytearray()
    width = height = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, depth, color = struct.unpack(">IIBB", chunk[:10])
            assert depth == 8 and color == 3
        elif ctype == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif ctype == b"IDAT":
            idat.extend(chunk)
        pos += 12 + length
    raw = zlib.decompress(bytes(idat))
    rows = []
    prev = bytearray(width)
    ppos = 0
    for _y in range(height):
        ftype = raw[ppos]
        ppos += 1
        line = bytearray(raw[ppos:ppos + width])
        ppos += width
        if ftype == 1:
            for i in range(1, width):
                line[i] = (line[i] + line[i - 1]) & 0xFF
        elif ftype == 2:
            for i in range(width):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(width):
                left = line[i - 1] if i else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(width):
                a = line[i - 1] if i else 0
                b = prev[i]
                c = prev[i - 1] if i else 0
                line[i] = (line[i] + _paeth(a, b, c)) & 0xFF
        rows.append(bytes(line))
        prev = line
    return width, height, palette, rows


def finish(width, height, palette, rows):
    """The finishing pass: returns the finished image's palette indices."""
    pal = palette
    # Nearest-palette lookup on a 5-bit-per-channel grid, filled lazily.
    nearest = {}

    def to_index(r, g, b):
        key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
        idx = nearest.get(key)
        if idx is None:
            cr, cg, cb = (r >> 3) << 3, (g >> 3) << 3, (b >> 3) << 3
            best, idx = 1 << 62, 0
            for i, (pr, pg, pb) in enumerate(pal):
                d = (pr - cr) ** 2 + (pg - cg) ** 2 + (pb - cb) ** 2
                if d < best:
                    best, idx = d, i
            nearest[key] = idx
        return idx

    cx, cy = width / 2.0, height / 2.0
    out_rows = []
    for y in range(height):
        src = rows[y]
        dy = (y - cy) / cy
        out = bytearray(width)
        for x in range(width):
            r, g, b = pal[src[x]]
            # Gentle vignette: corners fall to 88% light.
            dx = (x - cx) / cx
            vig = 1.0 - 0.12 * (dx * dx + dy * dy) / 2.0
            # Saturation: push each channel away from the pixel's grey.
            grey = (r + g + b) / 3.0
            r = grey + (r - grey) * 1.08
            g = grey + (g - grey) * 1.08
            b = grey + (b - grey) * 1.08
            # Warm golden lift in the highlights (the Garuda's glow).
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
            if lum > 0.62:
                lift = (lum - 0.62) * 0.35
                r += 255.0 * lift
                g += 190.0 * lift
            # New stars: a deterministic scatter over the dark nebula sky.
            if b > r + 18 and lum < 0.30:
                h = ((x * 73856093) ^ (y * 19349663)) & 0xFFFF
                if h % 613 == 0:
                    r, g, b = 235.0, 240.0, 255.0
            out[x] = to_index(
                max(0, min(255, round(r * vig))),
                max(0, min(255, round(g * vig))),
                max(0, min(255, round(b * vig))),
            )
        out_rows.append(bytes(out))
    return out_rows


def encode_indexed_png(width, height, palette, rows):
    def chunk(ctype, payload):
        c = struct.pack(">I", len(payload)) + ctype + payload
        return c + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    plte = b"".join(bytes(rgb) for rgb in palette)
    raw = bytearray()
    for line in rows:
        raw.append(0)
        raw.extend(line)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"PLTE", plte)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def render(data):
    width, height, palette, rows = decode_indexed_png(data)
    finished = finish(width, height, palette, rows)
    return encode_indexed_png(width, height, palette, finished)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SRC, "rb") as f:
        data = f.read()
    try:
        data = render(data)
    except Exception:
        pass  # Fall back to the held artwork, unchanged.
    with open(OUT, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
