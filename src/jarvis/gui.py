"""Minimal native desktop chat. UI state never authorizes an action."""

import queue
import threading
import time
import tkinter as tk

from jarvis.gui_chrome import brand_icon, style_native_titlebar
from jarvis.gui_conversation import ConversationView
from jarvis.gui_scrollbar import ChatScrollbar
from jarvis.gui_session import ChatSession
from jarvis.gui_theme import ACCENT, BG, BORDER, FOCUS, INK, MUTED, PANEL, SELECT, TITLE
from jarvis.gui_widgets import RoundedPanel, SendButton


class ChatWindow:
    def __init__(
        self,
        root,
        command_factory,
        repository,
        *,
        prepare=None,
        auto_start=False,
        voice_factory=None,
    ):
        self.root, self.command_factory, self.repository = root, command_factory, repository
        self.session = None
        self.prepare = prepare
        self.ready = False
        self.busy = False
        self.connected = False
        self.global_stopped = False
        self.closed = False
        self.started_at = 0
        self.logs = []
        self.timers = set()
        self.composer_focused = False
        self.status = tk.StringVar(value="Start a local chat when you're ready")
        root.title("JARVIS · Local assistant")
        root.geometry("940x760")
        root.minsize(620, 520)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.window_icons = [brand_icon(root, size) for size in (16, 32, 64)]
        root.iconphoto(True, *self.window_icons)
        root.bind("<Map>", self.style_titlebar, add="+")
        self.build()
        self.voice = voice_factory(self) if voice_factory else None
        if self.voice:
            self.update_composer()
        root.bind("<Escape>", lambda _: self.stop())
        self.schedule(40, self.poll)
        self.schedule(200, self.animate)
        if auto_start:
            self.schedule(100, self.auto_connect)

    def style_titlebar(self, event):
        if event.widget is self.root:
            style_native_titlebar(self.root)

    def schedule(self, delay, callback):
        def invoke():
            self.timers.discard(token)
            callback()

        token = self.root.after(delay, invoke)
        self.timers.add(token)

    def auto_connect(self):
        if not self.connected and not self.closed:
            self.toggle_session()

    def button(self, parent, text, command, *, accent=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT if accent else PANEL,
            fg=BG if accent else INK,
            activebackground="#becbff" if accent else "#34455e",
            activeforeground=BG if accent else INK,
            disabledforeground="#62718a",
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            cursor="hand2",
            takefocus=True,
        )

    def build(self):
        header = tk.Frame(self.root, bg=TITLE, padx=24, pady=14)
        header.pack(fill="x")
        self.brand_image = brand_icon(self.root)
        tk.Label(header, image=self.brand_image, bg=TITLE).pack(side="left", padx=(0, 10))
        brand = tk.Frame(header, bg=TITLE)
        brand.pack(side="left")
        name = tk.Frame(brand, bg=TITLE)
        name.pack(anchor="w")
        tk.Label(name, text="JARVIS", bg=TITLE, fg="#e8edf5", font=("Segoe UI", 16, "bold")).pack(
            side="left"
        )
        self.model = tk.Label(
            brand, text="Your personal assistant", bg=TITLE, fg="#a6b9d6", font=("Segoe UI", 9)
        )
        self.model.pack(anchor="w", pady=(3, 0))
        self.connect_button = self.button(header, "Start chat", self.toggle_session)
        self.connect_button.configure(
            bg="#243b60",
            fg="#e8edf5",
            activeforeground="#ffffff",
            activebackground="#304e7b",
            pady=8,
        )
        self.connect_button.pack(side="right")
        details = self.button(header, "Details", self.details)
        details.configure(
            bg=TITLE,
            fg="#c4d6f5",
            activeforeground="#ffffff",
            activebackground="#243b60",
            pady=8,
        )
        details.pack(side="right", padx=(0, 8))
        self.settings_button = self.button(header, "Settings", self.settings)
        self.settings_button.configure(
            bg=TITLE,
            fg="#c4d6f5",
            activeforeground="#ffffff",
            activebackground="#243b60",
            pady=8,
        )
        self.settings_button.pack(side="right", padx=(0, 8))
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        self.hint = tk.Label(
            self.root,
            text="Attended app & media controls · Ctrl+Alt+Shift+F10 stops effects",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.hint.pack(fill="x", padx=36, pady=(12, 0))

        # Reserve the composer first; the transcript must yield space on small windows.
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(side="bottom", fill="x")

        chat = tk.Frame(self.root, bg=BG)
        chat.pack(fill="both", expand=True, padx=(28, 20), pady=12)
        self.transcript = ConversationView(chat, background=BG)
        self.scrollbar = ChatScrollbar(
            chat,
            background=BG,
            command=self.scroll_transcript,
            wheel_command=self.transcript.wheel,
        )
        self.transcript.set_scrollbar(self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y", padx=(8, 0))
        self.transcript.pack(side="left", fill="both", expand=True)

        activity = tk.Frame(footer, bg=BG, padx=32)
        activity.pack(fill="x", pady=(0, 8))
        self.dots = tk.Canvas(activity, width=38, height=22, bg=BG, highlightthickness=0)
        self.dots.pack(side="left")
        self.dot_ids = [
            self.dots.create_oval(x, 8, x + 5, 13, fill=MUTED, outline="") for x in (2, 14, 26)
        ]
        tk.Label(activity, textvariable=self.status, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(
            side="left", padx=(6, 0)
        )
        self.stop_button = self.button(activity, "Stop", self.stop)
        self.stop_button.pack(side="right")
        self.stop_button.configure(state="disabled")

        self.composer = RoundedPanel(footer, background=BG, fill=PANEL, border=BORDER, height=132)
        self.composer.bind("<Button-1>", lambda _: self.input.focus_set())
        self.composer.body.bind("<Button-1>", lambda _: self.input.focus_set())
        self.composer.pack(fill="x", padx=32, pady=(0, 8))
        composer = self.composer.body
        toolbar = tk.Frame(composer, bg=PANEL)
        toolbar.pack(side="bottom", fill="x", pady=(8, 0))
        tk.Label(
            toolbar,
            text="Enter to send · Shift+Enter for a new line",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(side="left")
        self.send_button = SendButton(toolbar, self.send, background=PANEL)
        self.send_button.pack(side="right")
        self.input = tk.Text(
            composer,
            height=2,
            bg=PANEL,
            fg=INK,
            insertbackground=INK,
            insertwidth=2,
            insertontime=600,
            insertofftime=350,
            relief="flat",
            bd=0,
            font=("Segoe UI", 12),
            wrap="word",
            undo=True,
            highlightthickness=0,
            selectbackground=SELECT,
            selectforeground=INK,
        )
        self.input.bind("<Return>", self.enter)
        self.input.bind("<Shift-Return>", lambda _: None)
        self.input.bind("<KeyRelease>", lambda _: self.update_composer())
        self.input.bind("<FocusIn>", lambda _: self.focus_composer(True))
        self.input.bind("<FocusOut>", lambda _: self.focus_composer(False))
        self.input.bind("<Configure>", lambda _: self.update_composer())
        self.input.pack(fill="both", expand=True)
        self.placeholder = tk.Label(
            composer,
            text="Message JARVIS…",
            font=("Segoe UI", 12),
            bg=PANEL,
            fg=MUTED,
            cursor="xterm",
        )
        self.placeholder.bind("<Button-1>", lambda _: self.input.focus_set())
        self.placeholder.place(in_=self.input, x=0, y=0)
        self.send_button.configure(state="disabled")
        tk.Label(
            footer,
            text="Local assistant · Real app & media controls · Esc to stop",
            bg=BG,
            fg=MUTED,
            font=("Segoe UI", 9),
        ).pack(pady=(0, 16))

    def scroll_transcript(self, *args):
        if args == ("moveto", 1.0):
            self.transcript.scroll_to_end()
        else:
            self.transcript.yview(*args)

    def focus_composer(self, focused):
        self.composer_focused = focused
        self.composer.border = FOCUS if focused else BORDER
        self.composer.itemconfigure(self.composer.shape, width=2 if focused else 1)
        self.composer.layout()
        self.update_composer()

    def update_composer(self):
        text = self.input.get("1.0", "end-1c")
        if not text and not self.composer_focused:
            self.placeholder.place(in_=self.input, x=0, y=0)
        else:
            self.placeholder.place_forget()
        count = self.input.count("1.0", "end-1c", "displaylines")
        lines = max(2, min(6, (count[0] if count else 0) + 1))
        if int(self.input.cget("height")) != lines:
            self.input.configure(height=lines)
        height = (164 if getattr(self, "voice", None) else 132) + (lines - 2) * 22
        if int(self.composer.cget("height")) != height:
            self.composer.configure(height=height)

    def add_message(self, role, text):
        self.transcript.append_message(role, text)

    def toggle_session(self):
        if self.connected:
            if self.voice:
                self.voice.stop()
            self.status.set("Ending session…")
            self.ready = False
            self.send_button.configure(state="disabled")
            self.connect_button.configure(state="disabled")
            self.session.close()
            self.wait_for_exit(self.session)
            return
        self.logs = []
        self.session = ChatSession(self.command_factory, self.repository, prepare=self.prepare)
        self.connected, self.ready, self.busy = True, False, True
        self.global_stopped = False
        self.started_at = time.monotonic()
        self.status.set("Connecting…")
        self.connect_button.configure(text="End session")
        self.stop_button.configure(state="normal")
        session = self.session

        def start():
            try:
                session.start(real=True)
            except (OSError, ValueError) as exc:
                session._post({"kind": "diagnostic", "text": str(exc)})
                session._post({"kind": "closed", "text": ""})

        threading.Thread(target=start, daemon=True).start()

    def wait_for_exit(self, session):
        if self.closed:
            return
        startup_done = getattr(session, "startup_done", None)
        if (startup_done is not None and not startup_done.is_set()) or (
            session.process is not None and session.process.poll() is None
        ):
            self.schedule(100, lambda: self.wait_for_exit(session))
        else:
            self.finish()

    def finish(self):
        was_ready = self.ready
        self.connected = self.ready = self.busy = False
        self.send_button.configure(state="disabled")
        self.stop_button.configure(state="disabled")
        self.connect_button.configure(text="Start chat", state="normal")
        self.status.set("Session ended" if was_ready else "Session closed · see Details")

    def enter(self, event):
        if event.state & 0x0001:
            return None
        self.send()
        return "break"

    def send(self):
        return self.send_text(self.input.get("1.0", "end-1c").strip())

    def send_text(self, text, *, from_voice=False, display_text=None):
        if not self.ready or self.busy:
            return False
        if not text:
            return
        if text.casefold() in {"/stop", "stop", "/cancel"}:
            self.input.delete("1.0", "end")
            self.stop()
            return
        if text.casefold() in {"/quit", "quit", "/exit", "exit"}:
            self.input.delete("1.0", "end")
            self.toggle_session()
            return
        try:
            self.session.send(text)
        except ValueError as exc:
            self.status.set(str(exc))
            return
        if self.voice:
            self.voice.submitted(from_voice)
        self.add_message("user", "Voice: " + display_text if from_voice else text)
        self.input.delete("1.0", "end")
        self.update_composer()
        self.busy, self.ready = True, False
        self.started_at = time.monotonic()
        self.status.set("Thinking…")
        self.send_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        return True

    def stop(self):
        if self.voice:
            self.voice.stop()
        if self.session and self.connected and self.busy:
            startup_done = getattr(self.session, "startup_done", None)
            if (
                self.session.process is None
                and startup_done is not None
                and not startup_done.is_set()
            ):
                self.status.set("Cancelling startup…")
                self.session.close()
                self.wait_for_exit(self.session)
                return
            try:
                self.session.send("/stop")
                self.status.set("Stopping…")
            except ValueError as exc:
                self.status.set(str(exc))

    def poll(self):
        if self.closed:
            return
        if self.session:
            for _ in range(100):
                try:
                    event = self.session.events.get_nowait()
                except queue.Empty:
                    break
                kind, text = event["kind"], event["text"]
                if kind == "ready":
                    if self.global_stopped:
                        self.busy, self.ready = False, False
                        self.status.set("Stopped · end this session before starting another")
                        self.send_button.configure(state="disabled")
                        self.stop_button.configure(state="disabled")
                        continue
                    self.busy, self.ready = False, True
                    self.status.set("Ready · Real app & media controls")
                    self.send_button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.input.focus_set()
                    if self.voice:
                        self.voice.ready()
                elif kind == "progress":
                    self.status.set(text)
                elif kind == "reply":
                    self.add_message("assistant", text)
                    if self.voice:
                        self.voice.reply(text)
                elif kind == "diagnostic":
                    self.logs.append(text)
                    self.logs = self.logs[-300:]
                    if text.startswith("JARVIS |"):
                        model = next(
                            (p[6:] for p in text.split(" | ") if p.startswith("model=")), "local"
                        )
                        self.model.configure(text=f"Local · {model} · Attended Windows")
                    if text.startswith("A previous ") or "actions are paused" in text:
                        self.add_message("assistant", text)
                    if text.startswith("JARVIS: Stop acknowledged. New actions are blocked;"):
                        self.global_stopped = True
                        if self.voice:
                            self.voice.stop()
                        self.ready = self.busy = False
                        self.status.set("Stopped · end this session before starting another")
                        self.send_button.configure(state="disabled")
                        self.stop_button.configure(state="disabled")
                        self.add_message("assistant", text.removeprefix("JARVIS: "))
                elif kind == "closed":
                    if self.voice:
                        self.voice.stop()
                    if not self.ready and self.logs:
                        self.add_message("assistant", self.logs[-1])
                    self.session.close()
                    self.wait_for_exit(self.session)
        self.schedule(40, self.poll)

    def animate(self):
        if self.closed:
            return
        phase = int((time.monotonic() - self.started_at) * 4) % 3
        for index, dot in enumerate(self.dot_ids):
            active = self.busy and phase == index
            self.dots.itemconfigure(dot, fill=ACCENT if active else "#53627a")
        if self.busy and self.status.get().startswith("Thinking"):
            elapsed = int(time.monotonic() - self.started_at)
            self.status.set(f"Thinking…  {elapsed}s" if elapsed >= 3 else "Thinking…")
        self.schedule(200, self.animate)

    def details(self):
        window = tk.Toplevel(self.root)
        window.bind(
            "<Map>",
            lambda event: style_native_titlebar(window) if event.widget is window else None,
            add="+",
        )
        window.title("JARVIS · Session details")
        window.geometry("760x460")
        window.configure(bg=BG)
        text = tk.Text(
            window,
            wrap="word",
            bg=BG,
            fg=INK,
            font=("Consolas", 10),
            padx=20,
            pady=20,
            relief="flat",
        )
        text.pack(fill="both", expand=True)
        text.insert("end", "\n".join(self.logs) or "No session details yet. Start a chat first.")
        text.configure(state="disabled")

    def settings(self):
        if self.voice:
            self.voice.settings()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.voice:
            self.voice.close()
        self.voice_close_deadline = time.monotonic() + 3
        for timer in self.timers:
            self.root.after_cancel(timer)
        self.timers.clear()
        if self.session:
            self.session.close()
        self.root.withdraw()
        self.finish_close()

    def finish_close(self):
        voice = getattr(self.voice, "voice", None)
        if voice and voice.jobs.active and time.monotonic() < self.voice_close_deadline:
            self.schedule(50, self.finish_close)
            return
        startup_done = getattr(self.session, "startup_done", None)
        process = getattr(self.session, "process", None)
        if (startup_done is not None and not startup_done.is_set()) or (
            process is not None and process.poll() is None
        ):
            self.schedule(100, self.finish_close)
        else:
            self.root.destroy()


def main(command_factory, repository, *, prepare=None):
    from jarvis.gui_voice import VoicePanel

    root = tk.Tk()
    ChatWindow(
        root,
        command_factory,
        repository,
        prepare=prepare,
        auto_start=True,
        voice_factory=VoicePanel,
    )
    root.mainloop()
