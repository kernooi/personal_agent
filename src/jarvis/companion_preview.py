"""Same renderer and animation as production, without capture/model/backend startup."""

import math
import time

from jarvis.companion import Animation, CompanionConfig, Pose

STATES = (
    "hidden",
    "appearing",
    "idle",
    "left",
    "right",
    "up",
    "blinking",
    "capturing",
    "analyzing",
    "watching",
    "success",
    "error",
    "disappearing",
)


def sample(name):
    return {
        "hidden": Pose(),
        "appearing": Pose("capturing", scale=0.8, opacity=0.6),
        "idle": Pose("watching", opacity=1),
        "left": Pose("capturing", gaze_x=-0.85, tilt=-6, opacity=1),
        "right": Pose("capturing", gaze_x=0.85, tilt=6, opacity=1),
        "up": Pose("analyzing", gaze_y=-0.8, opacity=1),
        "blinking": Pose("capturing", blink=0.1, opacity=1),
        "capturing": Pose("capturing", gaze_x=-0.4, gaze_y=-0.3, opacity=1, tilt=-4),
        "analyzing": Pose("analyzing", gaze_y=-0.7, opacity=1),
        "watching": Pose("watching", opacity=1),
        "success": Pose("completed", blink=0.45, scale=1.02, opacity=1),
        "error": Pose("error", gaze_y=0.55, tilt=-3, opacity=1),
        "disappearing": Pose("completed", scale=0.88, opacity=0.5),
    }[name]


def export_sheet(path, config):
    from jarvis.companion_windows import Renderer, rgba_png

    if path.exists():
        raise ValueError("Preview export requires a new filename")
    renderer = Renderer(config.size)
    tile = renderer.edge + 40
    width, height = tile * 4, tile * math.ceil(len(STATES) / 4)
    output = bytearray(bytes((237, 237, 240, 255)) * width * height)
    try:
        for index, name in enumerate(STATES):
            renderer.render(sample(name))
            rgba = renderer.rgba()
            x0, y0 = index % 4 * tile + 20, index // 4 * tile + 20
            background = (237, 237, 240) if index % 2 == 0 else (18, 23, 31)
            for y in range(tile):
                for x in range(tile):
                    position = ((index // 4 * tile + y) * width + index % 4 * tile + x) * 4
                    output[position : position + 4] = bytes((*background, 255))
            for y in range(renderer.edge):
                for x in range(renderer.edge):
                    i = (y * renderer.edge + x) * 4
                    alpha = rgba[i + 3] / 255 * sample(name).opacity
                    color = [
                        round(rgba[i + c] * alpha + background[c] * (1 - alpha)) for c in range(3)
                    ]
                    i = ((y0 + y) * width + x0 + x) * 4
                    output[i : i + 4] = bytes((*color, 255))
        path.write_bytes(rgba_png(width, height, output))
    finally:
        renderer.close()


def run(args):
    import sys

    if sys.platform != "win32":
        raise ValueError("The native companion renderer requires Windows")
    config = CompanionConfig(
        size=args.size, reduced_motion="always" if args.reduced_motion else "system"
    )
    if args.export:
        export_sheet(args.export, config)
        print("Generated vector preview (no capture). Row-major states: " + ", ".join(STATES))
        return
    import tkinter as tk

    from jarvis.companion_windows import Overlay, system_reduced_motion

    root = tk.Tk()
    root.title("JARVIS orb preview · no screen/model access")
    root.configure(bg="#131923")
    overlay = Overlay(config)
    animation = Animation(config, seed=4, reduced=system_reduced_motion())
    selection = tk.StringVar(value="capturing")
    task = 0
    began = time.monotonic()
    cycling = args.cycle
    cycle_index, next_cycle = -1, began

    def select(name, *, automatic=False):
        nonlocal animation, task, cycling
        if not automatic:
            cycling = False
        task += 1
        now = time.monotonic()
        animation = Animation(config, seed=task, reduced=system_reduced_motion())
        animation.event("capturing", str(task), task * 2, now)
        if name != "appearing":
            animation.entered = now - 1
        if name in {"idle", "analyzing", "watching", "success", "error", "hidden", "disappearing"}:
            state = {
                "idle": "watching",
                "success": "completed",
                "hidden": "cancelled",
                "disappearing": "completed",
            }.get(name, name)
            animation.event(state, str(task), task * 2 + 1, now)
            if name == "disappearing":
                animation.terminal -= 0.34
        if name in {"left", "right", "up"}:
            animation.gaze = {"left": (-0.85, 0), "right": (0.85, 0), "up": (0, -0.8)}[name]
            animation.previous = animation.gaze
            animation.next_gaze = now + 20
        if name == "blinking":
            animation.next_blink = now

    tk.Label(
        root,
        text="Code-rendered black orb · preview only",
        bg="#131923",
        fg="white",
        font=("Segoe UI", 12),
        padx=24,
        pady=16,
    ).pack()
    menu = tk.OptionMenu(root, selection, *STATES, command=select)
    menu.configure(bg="#263143", fg="white", highlightthickness=0)
    menu.pack(padx=24, pady=10)
    tk.Label(
        root,
        text="Overlay is click-through. Close this preview to exit.",
        bg="#131923",
        fg="#a4b3cb",
        padx=24,
        pady=16,
    ).pack()

    def close():
        overlay.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    select("capturing", automatic=True)

    def tick():
        nonlocal cycle_index, next_cycle
        now = time.monotonic()
        if args.duration and now - began >= args.duration:
            close()
            return
        if cycling and now >= next_cycle:
            cycle_index = (cycle_index + 1) % len(STATES)
            selection.set(STATES[cycle_index])
            select(STATES[cycle_index], automatic=True)
            next_cycle = now + 2
        overlay.show(animation.pose(now))
        root.after(16, tick)

    root.after(16, tick)
    try:
        root.mainloop()
    finally:
        overlay.close()
