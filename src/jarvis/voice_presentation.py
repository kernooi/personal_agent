"""Trusted GUI metadata to the existing companion; never a model-callable tool."""

import json
import threading

from jarvis.models import reject_constant, unique_object
from jarvis.screen_capture import CaptureIndicator
from jarvis.voice_data import VoiceState

PREFIX = "\x1eVOICE "


def parse_control(line):
    if not line.startswith(PREFIX) or len(line) > 256:
        raise ValueError("Invalid voice presentation frame")
    data = json.loads(
        line[len(PREFIX) :], object_pairs_hook=unique_object, parse_constant=reject_constant
    )
    if (
        not isinstance(data, dict)
        or set(data) != {"sequence", "state"}
        or type(data["sequence"]) is not int
        or not 0 < data["sequence"] < 2**53
        or not isinstance(data["state"], str)
    ):
        raise ValueError("Invalid voice presentation frame")
    VoiceState(data["state"])
    return data


class VoicePresentation:
    def __init__(self, broker):
        screen = getattr(broker, "screen", None)
        self.indicator = screen.indicator if screen else CaptureIndicator()
        self.broker = broker
        self.sequence = 0
        self.task = "voice-presentation"

    def __call__(self, line):
        try:
            data = parse_control(line)
            if data["sequence"] <= self.sequence:
                return
            self.sequence = data["sequence"]
            stop = getattr(self.broker.desktop, "stop", threading.Event())
            if stop.is_set():
                return
            state = data["state"]
            if state in {
                "WAKE_ACKNOWLEDGING",
                "LISTENING",
                "TRANSCRIBING",
                "PROCESSING",
                "SPEAKING",
            }:
                self.indicator.start()
            if self.indicator.alive:
                self.indicator.update("voice", self.task, voice_state=state)
        except (OSError, ValueError):
            pass  # Presentation failure cannot submit, approve or replay a request.

    def close(self):
        self.indicator.close()
