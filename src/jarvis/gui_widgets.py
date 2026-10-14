"""Small code-drawn chat controls; no network or execution authority."""

import tkinter as tk

from jarvis.gui_art import artwork_image


class RoundedPanel(tk.Canvas):
    def __init__(self, parent, *, background, fill, border, height=130):
        super().__init__(parent, bg=background, height=height, bd=0, highlightthickness=0)
        self.fill, self.border = fill, border
        self.body = tk.Frame(self, bg=fill)
        self.shape = self.create_polygon(0, 0, 0, 0, fill=fill, outline=border, smooth=True)
        self.content = self.create_window(18, 16, anchor="nw", window=self.body)
        self.bind("<Configure>", self.layout)

    def layout(self, event=None):
        width, height = self.winfo_width(), self.winfo_height()
        self.itemconfigure(self.shape, outline=self.border)
        r = min(22, width / 2, height / 2)
        self.coords(
            self.shape,
            r,
            1,
            width - r,
            1,
            width - 1,
            1,
            width - 1,
            r,
            width - 1,
            height - r,
            width - 1,
            height - 1,
            width - r,
            height - 1,
            r,
            height - 1,
            1,
            height - 1,
            1,
            height - r,
            1,
            r,
            1,
            1,
        )
        self.itemconfigure(self.content, width=max(1, width - 36), height=max(1, height - 32))


class SendButton(tk.Canvas):
    def __init__(self, parent, command, *, background):
        super().__init__(
            parent,
            width=40,
            height=40,
            bg=background,
            highlightthickness=0,
            bd=0,
            takefocus=True,
            cursor="hand2",
        )
        self.command = command
        self.hover = False
        self.images = {}
        self.bind("<Button-1>", lambda _: self.invoke())
        self.bind("<Return>", lambda _: self.invoke())
        self.bind("<space>", lambda _: self.invoke())
        self.bind("<Enter>", lambda _: self.highlight(True))
        self.bind("<Leave>", lambda _: self.highlight(False))
        self.bind("<FocusIn>", lambda _: self.draw())
        self.bind("<FocusOut>", lambda _: self.draw())
        self.draw()

    def configure(self, cnf=None, **kwargs):
        result = super().configure(cnf, **kwargs)
        if kwargs or cnf:
            self.draw()
        return result

    config = configure

    def draw(self):
        self.delete("all")
        disabled = self.cget("state") == "disabled"
        focused = self.focus_get() == self
        key = disabled, self.hover, focused
        if key not in self.images:
            self.images[key] = artwork_image(
                self, "send", 40, disabled=disabled, hover=self.hover, focused=focused
            )
        self.create_image(20, 20, image=self.images[key])

    def highlight(self, value):
        self.hover = value
        self.draw()

    def invoke(self):
        if self.cget("state") != "disabled":
            self.command()
        return "break"
