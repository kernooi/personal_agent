"""Quiet, rounded scrollbar for the chat transcript."""

import tkinter as tk


class ChatScrollbar(tk.Canvas):
    def __init__(self, parent, *, command, background, wheel_command=None):
        super().__init__(
            parent,
            width=16,
            bg=background,
            bd=0,
            highlightthickness=0,
            takefocus=True,
        )
        self.command = command
        self.wheel_command = wheel_command
        self.first, self.last = 0.0, 1.0
        self.hover = False
        self.drag_offset = None
        self.wheel_remainder = 0.0
        self.thumb_top = self.thumb_bottom = 0.0
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Enter>", lambda _: self.emphasize(True))
        self.bind("<Leave>", lambda _: self.emphasize(False))
        self.bind("<FocusIn>", lambda _: self.draw())
        self.bind("<FocusOut>", lambda _: self.draw())
        self.bind("<Button-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<MouseWheel>", self.wheel)
        self.bind("<Button-4>", lambda _: self.scroll(-1))
        self.bind("<Button-5>", lambda _: self.scroll(1))
        for key, amount, unit in (
            ("Up", -1, "units"),
            ("Down", 1, "units"),
            ("Prior", -1, "pages"),
            ("Next", 1, "pages"),
        ):
            self.bind(f"<{key}>", lambda _, a=amount, u=unit: self.scroll(a, u))
        self.bind("<Home>", lambda _: self.move(0.0))
        self.bind("<End>", lambda _: self.move(1.0))

    def set(self, first, last):
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self.draw()

    def geometry(self):
        height = max(0, self.winfo_height() - 8)
        visible = self.last - self.first
        length = min(height, max(32, height * visible))
        travel = height - length
        top = 4 + travel * self.first / max(1e-9, 1 - visible)
        return top, length, travel

    def draw(self):
        self.delete("all")
        if self.last - self.first >= 0.999999:
            return  # No bright track or disabled buttons when everything fits.
        top, length, _ = self.geometry()
        self.thumb_top, self.thumb_bottom = top, top + length
        emphasized = self.hover or self.drag_offset is not None
        focused = self.focus_get() == self
        color = "#a5baff" if focused else "#8293ae" if emphasized else "#4d5c75"
        width = 8 if emphasized or focused else 6
        center = self.winfo_width() / 2
        self.create_line(
            center,
            top + width / 2,
            center,
            top + length - width / 2,
            fill=color,
            width=width,
            capstyle="round",
            tags="thumb",
        )

    def emphasize(self, value):
        self.hover = value
        self.draw()

    def press(self, event):
        if self.last - self.first >= 0.999999:
            return "break"
        if self.thumb_top <= event.y <= self.thumb_bottom:
            self.drag_offset = event.y - self.thumb_top
            self.draw()
        else:
            self.scroll(-1 if event.y < self.thumb_top else 1, "pages")
        return "break"

    def drag(self, event):
        if self.drag_offset is not None:
            _, _, travel = self.geometry()
            fraction = (event.y - self.drag_offset - 4) / max(1, travel)
            # Text can refine wrapped/tagged line heights after moving. Let Tk
            # clamp the bottom endpoint rather than using its previous estimate.
            self.move(1.0 if fraction >= 1 else max(0.0, fraction) * (1 - self.last + self.first))
        return "break"

    def release(self, event):
        self.drag_offset = None
        self.hover = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self.draw()
        return "break"

    def move(self, fraction):
        self.command("moveto", fraction)
        return "break"

    def scroll(self, amount, unit="units"):
        self.command("scroll", amount, unit)
        return "break"

    def wheel(self, event):
        if self.wheel_command:
            return self.wheel_command(event)
        self.wheel_remainder -= event.delta / 120
        steps = int(self.wheel_remainder)
        if steps:
            self.wheel_remainder -= steps
            self.scroll(steps * 3)
        return "break"
