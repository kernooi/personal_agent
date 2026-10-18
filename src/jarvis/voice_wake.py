"""Transient wake-address gate. No tool, approval, history or speaker authority."""

import re
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SpeechClip:
    pcm: bytes = field(repr=False)
    started_at: float
    ended_at: float


class SpeechBuffer:
    """Bounded mono int16 utterances, short pre-roll, frame-clock endpointing."""

    def __init__(self, rate, maximum_seconds, silence_seconds, minimum_rms):
        self.rate = rate
        self.maximum = int(rate * maximum_seconds)
        self.silence_seconds = silence_seconds
        self.minimum_rms = minimum_rms
        self.preroll = deque()
        self.preroll_frames = 0
        self.parts = []
        self.frames = 0
        self.active = False
        self.discarding = False
        self.last_sound = None
        self.started_at = None
        self.signal_frames = 0
        self.quiet_frames = 0

    def feed(self, pcm, frames, rms, ended_at):
        if frames <= 0 or len(pcm) != frames * 2:
            raise ValueError("INVALID_AUDIO")
        sound = rms >= self.minimum_rms
        if sound:
            self.quiet_frames = 0
            if not self.signal_frames:
                self.started_at = ended_at - frames / self.rate
            self.signal_frames += frames
            self.last_sound = ended_at
        elif not self.active:
            self.signal_frames = 0
        else:
            self.quiet_frames += frames
        if not self.active:
            self.preroll.append((pcm, frames))
            self.preroll_frames += frames
            # Keep at least the latest block, at most approximately 300 ms.
            while len(self.preroll) > 1 and self.preroll_frames > self.rate * 0.3:
                _, old_frames = self.preroll.popleft()
                self.preroll_frames -= old_frames
            if self.signal_frames < self.rate * 0.1:
                return None
            self.active = True
            self.parts = [part for part, _ in self.preroll]
            self.frames = self.preroll_frames
            self.preroll.clear()
            self.preroll_frames = 0
        elif not self.discarding:
            self.parts.append(pcm)
            self.frames += frames
        if self.frames > self.maximum:
            self.parts.clear()
            self.discarding = True
        # Endpoint on actual audio duration, not callback scheduling gaps. A busy
        # desktop must not turn delayed delivery into fictitious silence.
        if self.last_sound is None or self.quiet_frames < self.rate * self.silence_seconds:
            return None
        # Empty marks an overlong utterance, whose entire tail was discarded.
        result = SpeechClip(
            b"" if self.discarding else b"".join(self.parts), self.started_at, ended_at
        )
        self.parts.clear()
        self.frames = self.signal_frames = self.quiet_frames = 0
        self.active = self.discarding = False
        self.last_sound = self.started_at = None
        return result


class WakeGate:
    def __init__(self, followup_seconds=10, *, wake_call="Jarvis"):
        self.followup_seconds = followup_seconds
        phrase = r"\s+".join(re.escape(word) for word in wake_call.split())
        self.address = re.compile(
            r"^\s*(?:(?:hey|ok|okay)\s+)?" + phrase + r"\b[\s,.:!?-]*", re.IGNORECASE
        )
        self.until = 0
        self.after = 0

    def arm(self, now):
        self.after = now
        self.until = now + self.followup_seconds

    def accept(self, transcript, now, *, started_at=None):
        """Return (addressed request, armed). Unaddressed words never leave here."""
        match = self.address.match(transcript.text)
        if transcript.uncertain:
            self.until = 0
            return None, False
        if match:
            remainder = transcript.text[match.end() :].strip()
            if not remainder:
                self.arm(now)
                return None, True
            self.until = 0
            return transcript.model_copy(update={"text": remainder}), False
        began = now if started_at is None else started_at
        if self.after <= began < self.until:
            self.until = 0
            return transcript, False
        self.until = 0
        return None, False
