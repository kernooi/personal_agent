"""Bounded lossless preprocessing of this adapter's own in-memory RGB PNGs.

Wordle is an explicit M5 example: identify a complete, regular 5x6 grid before
using palette evidence. This never locates controls or produces input actions.
"""

import hashlib
import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from uuid import uuid4

from jarvis.domain import Denied


def recovery_thumbnail(frame, max_pixels, cancel):
    """Bounded in-memory derivative of the same frame, never a second capture."""
    if frame.width * frame.height <= max_pixels:
        return frame.png, (frame.width, frame.height)
    import math

    from jarvis.screen_worker import png_bgra

    width, height, rgb = decode_rgb(frame.png, frame.width * frame.height)
    scale = math.sqrt(max_pixels / (width * height))
    out_w, out_h = max(1, int(width * scale)), max(1, int(height * scale))
    bgra = bytearray(out_w * out_h * 4)
    for y in range(out_h):
        if cancel():
            raise Denied("VISION_CANCELLED")
        sy = min(height - 1, int((y + 0.5) * height / out_h))
        for x in range(out_w):
            sx = min(width - 1, int((x + 0.5) * width / out_w))
            source, dest = (sy * width + sx) * 3, (y * out_w + x) * 4
            bgra[dest : dest + 4] = bytes((rgb[source + 2], rgb[source + 1], rgb[source], 255))
    return png_bgra(bgra, out_w, out_h), (out_w, out_h)


PALETTE = {
    (83, 141, 78): "correct",
    (106, 170, 100): "correct",
    (181, 159, 59): "present_elsewhere",
    (201, 180, 88): "present_elsewhere",
    (58, 58, 60): "absent",
    (120, 124, 126): "absent",
    (245, 121, 58): "correct",
    (133, 192, 249): "present_elsewhere",
}


def decode_rgb(png, max_pixels):
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise Denied("PNG_FORMAT_UNSUPPORTED")
    position, compressed, dimensions = 8, bytearray(), None
    while position + 12 <= len(png):
        length = struct.unpack_from(">I", png, position)[0]
        kind = png[position + 4 : position + 8]
        if length > len(png) - position - 12:
            raise Denied("PNG_FORMAT_INVALID")
        data = png[position + 8 : position + 8 + length]
        checksum = struct.unpack_from(">I", png, position + 8 + length)[0]
        if zlib.crc32(kind + data) != checksum:
            raise Denied("PNG_FORMAT_INVALID")
        if kind == b"IHDR":
            if length != 13:
                raise Denied("PNG_FORMAT_INVALID")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if not width or not height or width * height > max_pixels:
                raise Denied("PNG_PIXEL_LIMIT")
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise Denied("PNG_FORMAT_UNSUPPORTED")
            dimensions = width, height
        elif kind == b"IDAT":
            compressed.extend(data)
        elif kind == b"IEND":
            break
        position += length + 12
    if dimensions is None:
        raise Denied("PNG_FORMAT_INVALID")
    width, height = dimensions
    expected = (width * 3 + 1) * height
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, expected + 1)
    if len(raw) != expected or not decoder.eof:
        raise Denied("PNG_DECODE_LIMIT")
    stride = width * 3 + 1
    if any(raw[y * stride] != 0 for y in range(height)):
        raise Denied("PNG_FILTER_UNSUPPORTED")
    return width, height, b"".join(raw[y * stride + 1 : (y + 1) * stride] for y in range(height))


@dataclass(frozen=True)
class BoardRegion:
    bounds: tuple[int, int, int, int]
    feedback: tuple[tuple[str, ...], ...]


def find_wordle(width, height, rgb):
    """Find aligned long flat runs, then independently verify every grid cell."""

    def pixel(x, y):
        return tuple(rgb[(y * width + x) * 3 : (y * width + x) * 3 + 3])

    lines = []
    # Sample every third row; avoid an unbounded per-pixel Python object graph.
    for y in range(0, height, 3):
        runs, x = [], 0
        while x < width:
            color = pixel(x, y)
            if color not in PALETTE:
                x += 1
                continue
            start = x
            while x < width and pixel(x, y) == color:
                x += 1
            if 20 <= x - start <= 160:
                runs.append((start, x, color))
        for start in range(max(0, len(runs) - 4)):
            row = runs[start : start + 5]
            lengths = [end - begin for begin, end, color in row]
            steps = [row[i + 1][0] - row[i][0] for i in range(4)]
            if (
                max(lengths) - min(lengths) <= 2
                and max(steps) - min(steps) <= 2
                and (lengths[0] < steps[0] <= lengths[0] * 1.5)
            ):
                lines.append((y, row, lengths[0], steps[0]))
    for y, row, size, step in lines:
        left = row[0][0]
        top = y
        first_color = row[0][2]
        while top > 0 and pixel(left, top - 1) == first_color:
            top -= 1
        # Browser layout can round vertical spacing differently from columns.
        # Try bounded pixel geometry variants, verifying all thirty cells each time.
        for tile_height in (size, size + 1, size - 1):
            for vertical_step in (step, step + 0.5, step - 0.5, step + 1, step - 1):
                board = read_grid(
                    width, height, pixel, left, top, size, tile_height, step, vertical_step
                )
                if board is not None:
                    return board

    return None


def read_grid(width, height, pixel, left, top, size, tile_height, step, vertical_step):
    right = left + step * 4 + size
    bottom = round(top + vertical_step * 5) + tile_height
    if right >= width or bottom >= height or top < 2 or left < 2:
        return None
    feedback, found_empty = [], False
    for row in range(6):
        states = []
        for column in range(5):
            x0, y0 = left + column * step, round(top + row * vertical_step)
            colors = [
                pixel(x0 + dx, y0 + dy)
                for dx, dy in (
                    (3, 3),
                    (size - 4, 3),
                    (3, tile_height - 4),
                    (size - 4, tile_height - 4),
                )
            ]
            common, count = Counter(colors).most_common(1)[0]
            state = PALETTE.get(common) if count == 4 else None
            if state:
                states.append(state)
                continue
            middle = pixel(x0 + size // 2, y0 + tile_height // 2)
            if count != 4 or common != middle:
                return None
            outlined = False
            for inset in range(-2, 3):
                xa, xb = x0 + inset, x0 + size - 1 - inset
                ya, yb = y0 + inset, y0 + tile_height - 1 - inset
                if xa < 0 or ya < 0 or xb >= width or yb >= height:
                    continue
                edges = [
                    pixel(xa, y0 + tile_height // 2),
                    pixel(xb, y0 + tile_height // 2),
                    pixel(x0 + size // 2, ya),
                    pixel(x0 + size // 2, yb),
                ]
                if len(set(edges)) == 1 and edges[0] != middle:
                    outlined = True
                    break
            if not outlined:
                return None
            states.append("empty")
        if states == ["empty"] * 5:
            found_empty = True
        elif "empty" in states or found_empty:
            return None
        else:
            feedback.append(tuple(states))
    return BoardRegion((left, top, right, bottom), tuple(feedback)) if feedback else None


def wordle_image(frame, max_pixels):
    """Crop only an independently detected board; preserve original pixel meaning."""
    from jarvis.screen_worker import png_bgra

    width, height, rgb = decode_rgb(frame.png, max_pixels)
    board = find_wordle(width, height, rgb)
    if board is None:
        return frame, None
    left, top, right, bottom = board.bounds
    crop_width, crop_height = right - left, bottom - top
    # 2x nearest-neighbor preserves glyph/color evidence without smoothing it away.
    scale = 2 if crop_width * crop_height * 4 <= max_pixels else 1
    output = bytearray()
    for y in range(top, bottom):
        row = bytearray()
        for x in range(left, right):
            r, g, b = rgb[(y * width + x) * 3 : (y * width + x) * 3 + 3]
            row.extend(bytes((b, g, r, 255)) * scale)
        output.extend(row * scale)
    png = png_bgra(output, crop_width * scale, crop_height * scale)
    return frame.model_copy(
        update={
            "artifact": "image_" + uuid4().hex,
            "png": png,
            "width": crop_width * scale,
            "height": crop_height * scale,
            "bounds": (
                frame.bounds[0] + left,
                frame.bounds[1] + top,
                frame.bounds[0] + right,
                frame.bounds[1] + bottom,
            ),
            "pixel_digest": hashlib.sha256(output).hexdigest(),
        }
    ), board
