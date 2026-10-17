"""Deterministic screen fixtures. Never import or call native capture."""

import hashlib
from types import SimpleNamespace
from uuid import uuid4

from jarvis.domain import Denied
from jarvis.screen_data import Frame, Interpretation, Target
from jarvis.screen_worker import png_bgra


class FakeCapture:
    def __init__(self, clock):
        self.clock, self.calls, self.generation = clock, 0, 0
        self.target = Target(
            reference="screen_" + "a" * 32,
            kind="window",
            identity="b" * 64,
            application="Synthetic fixture",
            bounds=(-200, 50, -100, 150),
            dpi=144,
            native={"synthetic": True},
        )
        self.active = self.target
        self.error = None
        self.changed = False
        self.after_capture = lambda: None
        self.pixels = bytes([64, 128, 192, 255, 192, 64, 128, 255]) * 5000

    def inventory(self, cancel=lambda: False):
        return [self.target]

    def foreground(self, cancel=lambda: False):
        return self.active

    def validate(self, target, cancel=lambda: False):
        if cancel() or self.error or self.changed or target != self.target:
            raise Denied(self.error or "SYNTHETIC_TARGET_CHANGED")

    def capture(self, target, cancel, indicator_pid=0):
        self.validate(target, cancel)
        self.calls += 1
        self.generation += 1
        frame = Frame(
            artifact="image_" + uuid4().hex,
            target_identity=target.identity,
            generation=self.generation,
            captured_at=self.clock.now(),
            width=100,
            height=100,
            bounds=target.bounds,
            png=png_bgra(self.pixels, 100, 100),
            pixel_digest=hashlib.sha256(self.pixels).hexdigest(),
        )
        self.after_capture()
        return frame


class FakeVision:
    def __init__(self):
        self.calls, self.image_support = 0, True
        self.result = Interpretation(description="A synthetic test application is visible.")
        self.after_analyze = lambda: None
        self.metadata = {"identity": "synthetic-vision", "digest": "c" * 64}
        self.frames = []

    def inspect(self, cancel, deadline):
        if cancel() or not self.image_support:
            raise Denied("VISION_MODEL_HAS_NO_IMAGE_SUPPORT")
        return self.metadata

    def analyze(self, frame, question, context, cancel, deadline):
        self.calls += 1
        self.frames[:] = [frame.artifact]  # No fake image history either.
        self.after_analyze()
        return self.result, self.metadata


class FakeIndicator:
    def __init__(self):
        self.process, self.alive, self.pid = None, False, 0
        self.events = []

    def start(self):
        self.process, self.alive = SimpleNamespace(), True

    def close(self):
        self.process, self.alive = None, False

    def update(self, event, task, bounds, *, watching=False):
        self.events.append((event, task, bounds, watching))


class FakeScreenAnswer:
    """Explicit test double; production never substitutes this for local inference."""

    def __init__(self):
        self.calls = 0
        self.after_compose = lambda: None
        self.context = None

    def compose(self, observation, question, context, profile, task, deadline, cancel):
        self.calls += 1
        self.context = context
        self.after_compose()
        return observation.interpretation.description
