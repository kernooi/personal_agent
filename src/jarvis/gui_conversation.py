"""Scrollable, selectable message bubbles. Display state has no tool authority."""

import tkinter as tk
from tkinter import font as tkfont

from jarvis.gui_chrome import style_native_titlebar
from jarvis.gui_scrollbar import ChatScrollbar
from jarvis.gui_theme import ACCENT, BG, BORDER, INK, MUTED, PANEL, SELECT, USER, USER_BORDER
from jarvis.gui_widgets import RoundedPanel


class MessageBubble:
    def __init__(self, parent, role, text, *, background, wheel, changed):
        self.role, self.message = role, text
        self.preview = text[:8000]
        self.truncated_preview = len(text) > len(self.preview)
        if self.truncated_preview:
            self.preview += "\n\n[Message continues — use Read full message]"
        self.changed = changed
        self.row = tk.Frame(parent, bg=background)
        self.row.pack(fill="x", padx=12, pady=(8, 12))
        side = "right" if role == "user" else "left"
        group = tk.Frame(self.row, bg=background)
        group.pack(side=side)
        name = tk.Label(
            group,
            text="You" if role == "user" else "JARVIS",
            bg=background,
            fg=MUTED,
            font=("Segoe UI", 9),
        )
        name.pack(anchor="e" if role == "user" else "w", padx=8, pady=(0, 5))
        fill = USER if role == "user" else PANEL
        self.panel = RoundedPanel(
            group,
            background=background,
            fill=fill,
            border=USER_BORDER if role == "user" else BORDER,
            height=64,
        )
        self.panel.pack()
        self.font = tkfont.Font(parent, family="Segoe UI", size=12)
        self.natural_width = max(
            (self.font.measure(line) for line in self.preview.splitlines()), default=80
        )
        self.text = tk.Text(
            self.panel.body,
            bg=fill,
            fg=INK,
            font=self.font,
            wrap="word",
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            height=1,
            width=1,
            cursor="xterm",
            selectbackground=SELECT,
            selectforeground=INK,
            exportselection=False,
            takefocus=True,
        )
        self.text.insert("1.0", self.preview)
        self.text.configure(state="disabled")
        self.text.pack(fill="both", expand=True)
        self.text.bind("<Configure>", lambda _: self.fit())
        self.text.bind("<Control-a>", self.select_all)
        self.more = tk.Button(
            group,
            text="Read full message…",
            command=self.read_full,
            bg=background,
            fg=ACCENT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        menu = tk.Menu(
            self.text,
            tearoff=False,
            bg=PANEL,
            fg=INK,
            activebackground=SELECT,
            activeforeground=INK,
        )
        menu.add_command(label="Copy message", command=self.copy)
        self.text.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        for widget in (self.row, group, name, self.panel, self.panel.body, self.text, self.more):
            widget.bind("<MouseWheel>", wheel)
        self.resize(560)

    def select_all(self, event=None):
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def copy(self):
        self.text.clipboard_clear()
        self.text.clipboard_append(self.message)

    def resize(self, maximum):
        width = max(120, min(maximum, self.natural_width + 38))
        if int(self.panel.cget("width")) != width:
            self.panel.configure(width=width)

    def fit(self):
        count = self.text.count("1.0", "end-1c", "displaylines")
        lines = (count[0] if count else 0) + 1
        height = max(58, min(lines, 300) * self.font.metrics("linespace") + 34)
        if (lines > 300 or self.truncated_preview) and not self.more.winfo_manager():
            self.more.pack(anchor="e", pady=(4, 0))
        elif lines <= 300 and not self.truncated_preview:
            self.more.pack_forget()
        if int(self.panel.cget("height")) != height:
            self.panel.configure(height=height)
            self.changed()

    def read_full(self):
        dialog = tk.Toplevel(self.row)
        dialog.title("JARVIS · Full message")
        dialog.geometry("760x560")
        dialog.configure(bg=BG)
        dialog.bind(
            "<Map>", lambda e: style_native_titlebar(dialog) if e.widget is dialog else None
        )
        text = tk.Text(
            dialog,
            bg=BG,
            fg=INK,
            font=self.font,
            wrap="word",
            padx=18,
            pady=18,
            bd=0,
            highlightthickness=0,
        )
        bar = ChatScrollbar(dialog, command=text.yview, background=BG)
        text.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        text.insert("1.0", self.message)
        text.configure(state="disabled")

    def destroy(self):
        self.row.destroy()


class ConversationView(tk.Frame):
    def __init__(self, parent, *, background):
        super().__init__(parent, bg=background)
        self.background = background
        self.messages = []
        self.characters = 0
        self.follow_tail = True
        self.pending_layout = None
        self.scroll_callback = None
        self.scroll_target = None
        self.scroll_timer = None
        self.canvas = tk.Canvas(
            self,
            bg=background,
            bd=0,
            highlightthickness=0,
            yscrollincrement=1,
            yscrollcommand=self.scrolled,
        )
        self.canvas.pack(fill="both", expand=True)
        self.content = tk.Frame(self.canvas, bg=background)
        self.window = self.canvas.create_window(0, 0, anchor="nw", window=self.content)
        self.latest = tk.Button(
            self,
            text="↓ Latest",
            command=self.scroll_to_end,
            bg=PANEL,
            fg=INK,
            activebackground=SELECT,
            activeforeground=INK,
            relief="flat",
            bd=0,
            padx=14,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.canvas.bind("<Configure>", self.resize)
        self.content.bind("<Configure>", lambda _: self.request_layout())
        self.canvas.bind("<MouseWheel>", self.wheel)
        self.content.bind("<MouseWheel>", self.wheel)
        self.latest.bind("<MouseWheel>", self.wheel)
        self.show_welcome()

    def show_welcome(self):
        self.welcome = tk.Frame(self.content, bg=self.background)
        self.welcome.pack(fill="x")
        self.welcome.pack_propagate(False)
        center = tk.Frame(self.welcome, bg=self.background)
        center.place(relx=0.5, rely=0.40, anchor="center")
        tk.Label(
            center,
            text="Hello, how can I help?",
            bg=self.background,
            fg=INK,
            font=("Segoe UI", 25, "bold"),
        ).pack(pady=(0, 12))
        tk.Label(
            center,
            text="Ask a question, find information, or control your apps.",
            bg=self.background,
            fg=MUTED,
            font=("Segoe UI", 11),
        ).pack()
        self.welcome.configure(height=max(1, self.canvas.winfo_height()))

    def resize(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)
        if not self.messages:
            self.welcome.configure(height=max(1, event.height))
        maximum = max(160, min(620, int(event.width * 0.78) - 24))
        for bubble in self.messages:
            bubble.resize(maximum)
        self.layout()

    def layout(self, event=None):
        if self.pending_layout is not None:
            self.after_cancel(self.pending_layout)
        self.pending_layout = None
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight())
        self.canvas.itemconfigure(
            self.window, height=0 if self.messages else self.canvas.winfo_height()
        )
        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), height))
        if height <= self.canvas.winfo_height():
            self.cancel_scroll()
            self.canvas.yview_moveto(0.0)
        elif self.follow_tail:
            self.cancel_scroll()
            self.canvas.yview_moveto(1.0)

    def request_layout(self):
        if self.pending_layout is None:
            self.pending_layout = self.after_idle(self.layout)

    def destroy(self):
        self.cancel_scroll()
        if self.pending_layout is not None:
            self.after_cancel(self.pending_layout)
        super().destroy()

    def set_scrollbar(self, callback):
        self.scroll_callback = callback

    def scrolled(self, first, last):
        if self.scroll_callback:
            self.scroll_callback(first, last)
        if self.messages and float(last) < 0.97:
            self.latest.place(relx=0.5, rely=1, y=-12, anchor="s")
        else:
            self.latest.place_forget()

    def yview(self, *args):
        if args:
            self.cancel_scroll()
            self.follow_tail = args == ("moveto", 1.0)
            if args[0] == "scroll" and args[2] == "units":
                self.canvas.yview_scroll(int(args[1]) * 24, "units")
            else:
                self.canvas.yview(*args)
        return self.canvas.yview()

    def scroll_to_end(self):
        self.cancel_scroll()
        self.follow_tail = True
        self.canvas.yview_moveto(1.0)

    def wheel(self, event):
        # Tk widget bindings do not bubble up to parents. All chat surfaces route
        # here, including blank frame space, message text and floating controls.
        if event.delta:
            self.follow_tail = False
            height, maximum = self.scroll_extent()
            current = self.canvas.yview()[0] * height
            target = current if self.scroll_target is None else self.scroll_target
            self.scroll_target = max(0.0, min(maximum, target - event.delta * 0.6))
            if self.scroll_timer is None:
                self.animate_scroll()
        return "break"

    def scroll_extent(self):
        region = self.tk.splitlist(self.canvas.cget("scrollregion"))
        height = max(1.0, float(region[3]) if region else self.canvas.winfo_height())
        return height, max(0.0, height - self.canvas.winfo_height())

    def animate_scroll(self):
        self.scroll_timer = None
        height, maximum = self.scroll_extent()
        self.scroll_target = max(0.0, min(maximum, self.scroll_target))
        current = self.canvas.yview()[0] * height
        distance = self.scroll_target - current
        next_position = self.scroll_target if abs(distance) <= 1 else current + distance * 0.4
        self.canvas.yview_moveto(next_position / height)
        if abs(distance) > 1:
            self.scroll_timer = self.after(16, self.animate_scroll)
        elif self.scroll_target == maximum:
            self.follow_tail = True

    def cancel_scroll(self):
        if self.scroll_timer is not None:
            self.after_cancel(self.scroll_timer)
            self.scroll_timer = None
        self.scroll_target = None

    def append_message(self, role, text):
        text = text.strip()
        if not text:
            return
        text = text[-150000:]
        if not self.messages:
            self.welcome.destroy()
        if role == "user":
            self.cancel_scroll()
            self.follow_tail = True
        bubble = MessageBubble(
            self.content,
            role,
            text,
            background=self.background,
            wheel=self.wheel,
            changed=self.request_layout,
        )
        self.messages.append(bubble)
        self.characters += len(text)
        while len(self.messages) > 256 or self.characters > 150000:
            previous = self.messages.pop(0)
            self.characters -= len(previous.message)
            previous.destroy()
        bubble.resize(max(160, min(620, int(self.canvas.winfo_width() * 0.78) - 24)))
        self.request_layout()

    def clear(self):
        for bubble in self.messages:
            bubble.destroy()
        if not self.messages:
            self.welcome.destroy()
        self.messages = []
        self.characters = 0
        self.follow_tail = True
        self.show_welcome()
        self.request_layout()
