"""Opt-in synthetic M5 display fixture; modifies only its own widgets."""

import json
import queue
import sys
import threading
import tkinter as tk


def main():
    root = tk.Tk()
    root.title("JARVIS M5 synthetic screen fixture")
    root.attributes("-topmost", True)
    root.geometry("800x590+80+100")
    canvas = tk.Canvas(root, width=800, height=590, bg="#17202b", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    messages = queue.Queue(maxsize=4)
    photograph = None
    if len(sys.argv) == 2:
        from pathlib import Path

        path = Path(sys.argv[1])
        if path.is_file() and path.stat().st_size <= 4_000_000:
            photograph = tk.PhotoImage(file=str(path))

    def draw(kind):
        canvas.delete("all")
        canvas.create_text(
            36,
            30,
            anchor="nw",
            text="JARVIS M5 · synthetic test content",
            fill="#d9e6ff",
            font=("Segoe UI", 18, "bold"),
        )
        if kind == "error":
            canvas.create_text(
                36,
                110,
                anchor="nw",
                text=(
                    "Python 3.13 · synthetic terminal\n\n"
                    "Traceback (most recent call last):\n"
                    '  File "example.py", line 1, in <module>\n'
                    "    import pandas\n"
                    "ModuleNotFoundError: No module named 'pandas'"
                ),
                fill="#f4c5c5",
                font=("Consolas", 17),
            )
        elif kind in {"wordle", "wordle-next"}:
            canvas.create_text(
                36,
                80,
                anchor="nw",
                text="WORDLE · controlled board",
                fill="white",
                font=("Segoe UI", 16),
            )
            guesses = ["CRANE"] + (["SLATE"] if kind == "wordle-next" else [])
            colors = [
                ["absent", "absent", "present_elsewhere", "absent", "correct"],
                ["absent", "present_elsewhere", "present_elsewhere", "absent", "correct"],
            ]
            palette = {"absent": "#3a3a3c", "present_elsewhere": "#b59f3b", "correct": "#538d4e"}
            for row in range(6):
                for col in range(5):
                    x, y = 230 + col * 62, 128 + row * 62
                    fill = palette[colors[row][col]] if row < len(guesses) else "#17202b"
                    canvas.create_rectangle(
                        x, y, x + 54, y + 54, fill=fill, outline="#77808a", width=2
                    )
                    if row < len(guesses):
                        canvas.create_text(
                            x + 27,
                            y + 27,
                            text=guesses[row][col],
                            fill="white",
                            font=("Consolas", 26, "bold"),
                        )
        elif kind == "plant":
            if photograph:
                canvas.create_image(400, 320, image=photograph)
                canvas.create_text(
                    400,
                    565,
                    text="Public test photograph · source in report",
                    fill="#a8b8cc",
                    font=("Segoe UI", 11),
                )
                return
            canvas.create_rectangle(348, 395, 452, 485, fill="#bf7857", outline="")
            canvas.create_line(400, 400, 400, 160, fill="#58a76a", width=10)
            for y in (195, 260, 325):
                canvas.create_oval(300, y - 30, 400, y + 15, fill="#56aa6a", outline="")
                canvas.create_oval(400, y - 55, 505, y - 10, fill="#68bd7c", outline="")
            canvas.create_text(
                400,
                530,
                text="Synthetic illustration · not a photograph",
                fill="#a8b8cc",
                font=("Segoe UI", 13),
            )
        root.update_idletasks()

    def read():
        for line in sys.stdin:
            try:
                messages.put_nowait(line.strip())
            except queue.Full:
                return
        messages.put("quit")

    def poll():
        try:
            command = messages.get_nowait()
        except queue.Empty:
            root.after(25, poll)
            return
        if command == "quit":
            root.destroy()
            return
        if command == "focus":
            hwnd = user.GetAncestor(root.winfo_id(), 2)
            user.SetForegroundWindow.argtypes = [wintypes.HWND]
            user.GetForegroundWindow.restype = wintypes.HWND
            user.SetForegroundWindow(hwnd)
            print(
                json.dumps({"foreground": int(user.GetForegroundWindow() or 0) == int(hwnd)}),
                flush=True,
            )
            root.after(25, poll)
            return
        if command in {"error", "wordle", "wordle-next", "plant"}:
            draw(command)
            print(json.dumps({"shown": command}), flush=True)
        root.after(25, poll)

    draw("error")
    root.update()
    import ctypes
    from ctypes import wintypes

    user = ctypes.WinDLL("user32")
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    print(json.dumps({"hwnd": int(user.GetAncestor(root.winfo_id(), 2))}), flush=True)
    threading.Thread(target=read, daemon=True).start()
    root.after(25, poll)
    root.mainloop()


if __name__ == "__main__":
    main()
