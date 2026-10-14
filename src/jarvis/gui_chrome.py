"""Branding for our own Tk windows, preserving native Windows chrome."""

import ctypes
import sys
from ctypes import wintypes

from jarvis.gui_art import artwork_image
from jarvis.gui_theme import BORDER, TITLE
from jarvis.gui_theme import INK as TITLE_INK


def brand_icon(master, size=40):
    """Use the orbital-core mark for both header and native window icons."""
    return artwork_image(master, "logo", size)


def style_native_titlebar(window):
    """Use documented per-window DWM colors; older hosts retain native chrome."""
    if sys.platform != "win32":
        return False
    try:
        user = ctypes.WinDLL("user32", use_last_error=True)
        dwm = ctypes.WinDLL("dwmapi")
        user.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user.GetAncestor.restype = wintypes.HWND
        dwm.DwmSetWindowAttribute.argtypes = (
            wintypes.HWND,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        )
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        handle = user.GetAncestor(window.winfo_id(), 2)
        if not handle:
            return False

        def color(value):
            r, g, b = (int(value[i : i + 2], 16) for i in (1, 3, 5))
            return r | g << 8 | b << 16

        results = []
        for attribute, value in (
            (20, 1),  # DWMWA_USE_IMMERSIVE_DARK_MODE
            (34, color(BORDER)),  # DWMWA_BORDER_COLOR
            (35, color(TITLE)),  # DWMWA_CAPTION_COLOR
            (36, color(TITLE_INK)),  # DWMWA_TEXT_COLOR
        ):
            setting = wintypes.DWORD(value)
            results.append(
                dwm.DwmSetWindowAttribute(
                    handle, attribute, ctypes.byref(setting), ctypes.sizeof(setting)
                )
            )
        return all(result == 0 for result in results)
    except (OSError, AttributeError):
        return False
