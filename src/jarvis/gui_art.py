"""Antialiased code-drawn marks, encoded as RGBA PNG without dependencies."""

import base64
import math
import struct
import tkinter as tk
import zlib
from functools import lru_cache


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _line_distance(x, y, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def _logo(u, v):
    # A rounded slate tile, two orbital arcs and a luminous four-point core.
    qx, qy = abs(u - 0.5) - 0.24, abs(v - 0.5) - 0.24
    edge = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - 0.20
    if edge > 0:
        return None
    tint = (u + 1 - v) / 2
    color = (29 + 13 * tint, 46 + 21 * tint, 71 + 29 * tint)
    if edge > -0.014:
        color = (56, 77, 106)
    radius = math.hypot(u - 0.5, v - 0.5)
    if 0.26 < radius < 0.31 and abs(v - 0.5) > 0.065:
        color = (137 + 34 * v, 223 - 36 * v, 232 + 16 * v)
    if abs(u - 0.5) / 0.15 + abs(v - 0.5) / 0.20 <= 1:
        color = (189 + 42 * (1 - v), 219 + 28 * (1 - v), 250)
    return color


def _send(u, v, disabled, hover, focused):
    radius = math.hypot(u - 0.5, v - 0.5)
    if radius > 0.47:
        return None
    color = (58, 74, 96) if disabled else (188, 207, 255) if hover else (159, 183, 241)
    if focused and radius > 0.435:
        color = (227, 237, 255)
    arrow = min(
        _line_distance(u, v, 0.5, 0.67, 0.5, 0.34),
        _line_distance(u, v, 0.35, 0.48, 0.5, 0.33),
        _line_distance(u, v, 0.5, 0.33, 0.65, 0.48),
    )
    if arrow < 0.027:
        color = (132, 150, 177) if disabled else (29, 44, 66)
    return color


@lru_cache(maxsize=32)
def artwork_png(kind, size, disabled=False, hover=False, focused=False):
    """Average 6×6 subpixels in premultiplied alpha for clean transparent edges."""
    if kind not in {"logo", "send"} or not 8 <= size <= 128:
        raise ValueError("Unsupported GUI artwork")
    raw = bytearray()
    samples = 6
    for y in range(size):
        raw.append(0)  # PNG filter: none.
        for x in range(size):
            red = green = blue = hits = 0
            for sy in range(samples):
                v = (y + (sy + 0.5) / samples) / size
                for sx in range(samples):
                    u = (x + (sx + 0.5) / samples) / size
                    pixel = _logo(u, v) if kind == "logo" else _send(u, v, disabled, hover, focused)
                    if pixel is not None:
                        red += pixel[0]
                        green += pixel[1]
                        blue += pixel[2]
                        hits += 1
            if hits:
                raw.extend(
                    (
                        round(red / hits),
                        round(green / hits),
                        round(blue / hits),
                        round(255 * hits / (samples * samples)),
                    )
                )
            else:
                raw.extend((0, 0, 0, 0))
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def artwork_image(master, kind, size, **state):
    return tk.PhotoImage(master=master, data=base64.b64encode(artwork_png(kind, size, **state)))
