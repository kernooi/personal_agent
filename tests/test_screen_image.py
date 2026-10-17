"""Pixel evidence is independent of an LLM's color claims."""

import hashlib

import pytest

from jarvis.domain import Denied
from jarvis.screen_data import Frame
from jarvis.screen_image import decode_rgb, find_wordle, wordle_image
from jarvis.screen_worker import png_bgra


def test_recovery_thumbnail_preserves_scope_aspect_colors_and_cancellation():
    from types import SimpleNamespace

    from jarvis.screen_image import recovery_thumbnail

    # Four distinct corners make accidental cropping/color-channel swaps observable.
    width, height = 400, 200
    colors = [(10, 20, 30, 255), (40, 50, 60, 255), (70, 80, 90, 255), (100, 110, 120, 255)]
    pixels = b"".join(
        bytes(colors[(y >= height // 2) * 2 + (x >= width // 2)])
        for y in range(height)
        for x in range(width)
    )
    frame = SimpleNamespace(width=width, height=height, png=png_bgra(pixels, width, height))
    png, dimensions = recovery_thumbnail(frame, 5000, lambda: False)
    w, h, rgb = decode_rgb(png, 5000)
    assert dimensions == (w, h) == (100, 50)
    for index, (x, y) in enumerate([(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]):
        start = (y * w + x) * 3
        assert rgb[start : start + 3] == bytes(reversed(colors[index][:3]))
    assert recovery_thumbnail(frame, width * height, lambda: False) == (frame.png, (width, height))
    with pytest.raises(Denied, match="VISION_CANCELLED"):
        recovery_thumbnail(frame, 5000, lambda: True)


def synthetic_grid(inner_outline=False, vertical_step=38, tile_height=30):
    width, height, size, step = 240, 300, 30, 38
    rgb = bytearray(bytes((23, 32, 43)) * width * height)
    colors = [(58, 58, 60), (58, 58, 60), (181, 159, 59), (58, 58, 60), (83, 141, 78)]
    for row in range(6):
        for col in range(5):
            x0, y0 = 20 + col * step, round(25 + row * vertical_step)
            for y in range(y0 - 1, y0 + tile_height + 1):
                for x in range(x0 - 1, x0 + size + 1):
                    color = colors[col] if row == 0 else (23, 32, 43)
                    if x in {x0 - 1, x0 + size} or y in {y0 - 1, y0 + tile_height}:
                        color = (119, 128, 138)
                    if row and inner_outline:
                        color = (23, 32, 43)
                        if (
                            x0 <= x < x0 + size
                            and y0 <= y < y0 + tile_height
                            and (
                                x < x0 + 2
                                or x >= x0 + size - 2
                                or y < y0 + 2
                                or y >= y0 + tile_height - 2
                            )
                        ):
                            color = (119, 128, 138)
                    rgb[(y * width + x) * 3 : (y * width + x) * 3 + 3] = bytes(color)
    bgra = bytearray()
    for index in range(0, len(rgb), 3):
        r, g, b = rgb[index : index + 3]
        bgra.extend((b, g, r, 255))
    png = png_bgra(bgra, width, height)
    return width, height, bytes(rgb), png


def test_lossless_decode_grid_crop_and_palette_evidence():
    width, height, rgb, png = synthetic_grid()
    assert decode_rgb(png, 100000) == (width, height, rgb)
    board = find_wordle(width, height, rgb)
    assert board is not None
    assert board.bounds == (20, 25, 202, 245)
    assert board.feedback == (("absent", "absent", "present_elsewhere", "absent", "correct"),)
    frame = Frame(
        artifact="image_" + "a" * 32,
        target_identity="b" * 64,
        generation=1,
        captured_at=1000.0,
        width=width,
        height=height,
        bounds=(0, 0, width, height),
        png=png,
        pixel_digest=hashlib.sha256(rgb).hexdigest(),
    )
    cropped, detected = wordle_image(frame, 1000000)
    assert cropped.bounds == board.bounds and detected == board
    assert (cropped.width, cropped.height) == (364, 440)
    assert cropped.captured_at == frame.captured_at


def test_no_board_from_unrelated_or_partial_image():
    assert find_wordle(100, 100, bytes([10, 20, 30]) * 10000) is None
    width, height, rgb, _ = synthetic_grid()
    assert find_wordle(width, 70, rgb[: width * 70 * 3]) is None


def test_empty_tiles_with_inside_two_pixel_outline_preserve_exact_feedback():
    width, height, rgb, _ = synthetic_grid(inner_outline=True)
    board = find_wordle(width, height, rgb)
    assert board is not None and board.bounds == (20, 25, 202, 245)
    assert board.feedback == (("absent", "absent", "present_elsewhere", "absent", "correct"),)


@pytest.mark.parametrize("vertical_step,tile_height", [(38.5, 30), (39, 31), (37.5, 29)])
def test_browser_vertical_rounding_and_rectangular_tiles_remain_independently_verified(
    vertical_step,
    tile_height,
):
    width, height, rgb, _ = synthetic_grid(
        inner_outline=True, vertical_step=vertical_step, tile_height=tile_height
    )
    board = find_wordle(width, height, rgb)
    assert board is not None
    assert board.feedback == (("absent", "absent", "present_elsewhere", "absent", "correct"),)


def test_large_geometry_disagreement_is_not_accepted_as_a_regular_grid():
    width, height, rgb, _ = synthetic_grid(vertical_step=42)
    assert find_wordle(width, height, rgb) is None


def test_image_decode_caps_and_corruption():
    _, _, _, png = synthetic_grid()
    with pytest.raises(Denied, match="PNG_PIXEL_LIMIT"):
        decode_rgb(png, 100)
    corrupt = png[:100] + b"BAD" + png[103:]
    with pytest.raises(Denied):
        decode_rgb(corrupt, 1000000)
