"""Presentation-only orb animation. No model, capture, input or task execution."""

import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanionConfig(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    enabled: bool = True
    size: int = Field(default=80, ge=48, le=128)
    position: Literal["bottom-right", "bottom-left", "top-right", "top-left"] = "bottom-right"
    intensity: float = Field(default=0.7, ge=0, le=1)
    reduced_motion: Literal["system", "always", "never"] = "system"
    show_during_watch: bool = True


@dataclass(frozen=True)
class Pose:
    state: str = "hidden"
    gaze_x: float = 0
    gaze_y: float = 0
    blink: float = 1
    scale: float = 1
    opacity: float = 0
    bob: float = 0
    tilt: float = 0


def ease(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def placement(work, size, dpi=96, position="bottom-right"):
    """Physical-pixel window enclosing an 80-DIP orb, above the taskbar."""
    scale = dpi / 96
    edge = round(size * 1.32 * scale)
    margin = round(24 * scale)
    left, top, right, bottom = work
    x = right - edge - margin if position.endswith("right") else left + margin
    y = bottom - edge - margin if position.startswith("bottom") else top + margin
    return max(left, min(x, right - edge)), max(top, min(y, bottom - edge)), edge


def eyes(pose, diameter):
    """Exactly two pupil-free capsules, expressed in orb-local coordinates."""
    x = pose.gaze_x * 0.065 * diameter
    y = pose.gaze_y * 0.045 * diameter
    width, height = diameter * 0.103, diameter * 0.192 * pose.blink
    return tuple(
        (diameter * center + x, diameter * 0.405 + y, width, max(diameter * 0.015, height))
        for center in (0.405, 0.655)
    )


class Animation:
    """Bounded task-keyed UI events; terminal events cannot revive old tasks."""

    def __init__(self, config=None, *, seed=None, reduced=False):
        self.config = config or CompanionConfig()
        self.reduced = reduced or self.config.reduced_motion == "always"
        self.random = random.Random(seed)
        self.task = None
        self.sequence = -1
        self.retired = deque(maxlen=64)
        self.state = "hidden"
        self.entered = self.changed = 0.0
        self.terminal = None
        self.gaze = self.previous = (0.0, 0.0)
        self.gaze_started = self.next_gaze = 0.0
        self.next_blink = 4.0
        self.blink_started = None

    def event(self, state, task, sequence, now, *, watching=False):
        if sequence <= self.sequence or task in self.retired:
            return False
        if state not in {
            "capturing",
            "analyzing",
            "watching",
            "completed",
            "error",
            "cancelled",
            "listening",
            "transcribing",
            "thinking",
            "speaking",
        }:
            return False
        if task != self.task:
            if state not in {
                "capturing",
                "watching",
                "listening",
                "transcribing",
                "thinking",
                "speaking",
            }:
                return False
            if self.task:
                self.retired.append(self.task)
            self.task, self.entered = task, now
            self.terminal = None
            self.next_blink = now + self.random.uniform(3, 7)
            self.next_gaze = now
        elif state == self.state or (state == "capturing" and self.state == "analyzing"):
            self.sequence = sequence
            return False
        self.sequence = sequence
        if state == "completed" and watching:
            state = "watching"
        self.state, self.changed = state, now
        if state == "analyzing":
            self.next_gaze = now
        if state in {"completed", "error", "cancelled"}:
            self.terminal = now
            self.retired.append(task)
            self.previous, self.gaze, self.gaze_started = self.current_gaze(now), (0, 0), now
        return True

    def current_gaze(self, now):
        t = ease((now - self.gaze_started) / 0.27)
        return tuple(a + (b - a) * t for a, b in zip(self.previous, self.gaze, strict=True))

    def pose(self, now):
        if not self.config.enabled or self.state == "hidden":
            return Pose()
        if self.state == "watching" and not self.config.show_during_watch:
            return Pose()
        elapsed = max(0, now - self.entered)
        opacity, scale, blink = 1.0, 1.0, 1.0
        if self.terminal is not None:
            age = now - self.terminal
            if self.state == "cancelled":
                self.state = "hidden"
                return Pose()
            hold = 0.34 if self.state == "completed" else 0.28
            if age >= hold + 0.28:
                self.state = "hidden"
                return Pose()
            opacity = 1 - ease((age - hold) / 0.28)
            scale = 1 - 0.18 * ease((age - hold) / 0.28)
            if self.state == "completed" and age < hold and not self.reduced:
                scale += 0.025 * math.sin(age / hold * math.pi)
                blink = max(0.08, 1 - math.sin(min(1, age / 0.18) * math.pi))
        elif now >= self.next_gaze:
            self.previous = self.current_gaze(now)
            choices = (
                [(0.1, -0.8), (-0.2, -0.75), (0, -0.6)]
                if self.state in {"analyzing", "thinking"}
                else [(-0.55, -0.1), (-0.4, 0)]
                if self.state == "transcribing"
                else [(0, 0), (0, 0), (0.25, -0.15)]
                if self.state in {"watching", "listening", "speaking"}
                else [
                    (0, 0),
                    (-0.85, 0),
                    (0.85, 0),
                    (0, -0.8),
                    (-0.6, -0.6),
                    (0.6, -0.6),
                    (0, 0.55),
                    (0, 0),
                ]
            )
            self.gaze = self.random.choice(choices)
            self.gaze_started = now
            self.next_gaze = now + self.random.uniform(0.9, 2.5)
        if not self.reduced and self.terminal is None:
            if self.blink_started is None and now >= self.next_blink:
                self.blink_started = now
            if self.blink_started is not None:
                age = now - self.blink_started
                blink = max(0.08, 1 - math.sin(min(1, age / 0.15) * math.pi))
                if age >= 0.15:
                    self.blink_started = None
                    self.next_blink = now + (
                        0.22 if self.random.random() < 0.1 else self.random.uniform(3, 7)
                    )
        if not self.reduced and elapsed < 0.4 and self.terminal is None:
            t = min(1, elapsed / 0.4)
            # Small ease-out overshoot, settling to exactly 100 percent.
            scale = 0.65 + 0.35 * (1 + 1.7 * (t - 1) ** 3 + 0.7 * (t - 1) ** 2)
            opacity = ease(elapsed / 0.2)
        intensity = self.config.intensity
        gaze = self.current_gaze(now)
        if self.state == "error":
            gaze = (0, 0.55)
        if self.reduced:
            gaze = (0, -0.55) if self.state in {"analyzing", "thinking"} else (0, 0)
        bob = math.sin(elapsed * 1.8) * 1.6 * intensity if not self.reduced else 0
        if self.state == "speaking" and not self.reduced:
            bob = math.sin(elapsed * 4) * 1.2 * intensity
        tilt = gaze[0] * 7 * intensity if not self.reduced else 0
        return Pose(
            self.state,
            gaze[0] * intensity,
            gaze[1] * intensity,
            blink,
            scale if not self.reduced else 1,
            opacity,
            bob,
            tilt,
        )
