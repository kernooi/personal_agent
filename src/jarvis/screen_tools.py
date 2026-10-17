"""Scoped read/advice capability on the existing task journal and execution broker."""

import hashlib
import re
import threading
from dataclasses import replace
from uuid import uuid4

from jarvis.domain import (
    AdmissionRejected,
    Denied,
    Evidence,
    PreparedAction,
    Scope,
    State,
    TaskResult,
)
from jarvis.models import ProviderError
from jarvis.policy import POLICY_VERSION
from jarvis.screen_data import Observation
from jarvis.tools import digest

SCREEN_ERRORS = {
    "CAPTURE_REGION_EXCLUDED_OR_UNKNOWN": (
        "Screen capture was blocked by an excluded, protected or inaccessible window. "
        "Close or move that window, then ask again."
    ),
    "CAPTURE_EXCLUDED": (
        "This screen or window is excluded from capture by your screen privacy settings."
    ),
    "VISIBLE_CREDENTIAL_FIELD": "Screen capture was blocked because a password field is visible.",
    "PROTECTED_CAPTURE": "Windows protects this content from screen capture.",
    "WINDOW_COVERED": (
        "The selected window is covered. Make it visible or ask to scan the whole screen."
    ),
    "CAPTURE_TIMEOUT": "Windows screen capture timed out. No image answer was produced.",
    "CAPTURE_PIXEL_LIMIT_RESIZE_WINDOW": (
        "This screen exceeds the configured image size limit. Use a smaller screen or window."
    ),
    "CAPTURE_INDICATOR_UNAVAILABLE": (
        "The screen capture indicator could not start. Close other JARVIS sessions and "
        "restart chat."
    ),
    "CAPTURE_TARGET_CHANGED": (
        "The screen layout or selected window changed during capture. Ask again when it is stable."
    ),
    "CAPTURE_CANCELLED": "Screen reading was stopped.",
    "SCREEN_CANCELLED": "Screen reading was stopped.",
    "VISION_CANCELLED_OR_INCOMPLETE": (
        "The local vision runtime failed to finish its answer. No partial reading was accepted."
    ),
    "VISION_CANCELLED": "Screen reading was stopped.",
    "CANCELLED": "Screen reading was stopped.",
    "TIMEOUT": (
        "The local vision model timed out. The screen was not answered; try again when "
        "the GPU is less busy."
    ),
    "RUNTIME_UNAVAILABLE": "The local vision runtime is unavailable. Check that Ollama is running.",
    "MODEL_OR_ENDPOINT_MISSING": "The configured local vision model is missing from Ollama.",
    "VISION_MODEL_HAS_NO_IMAGE_SUPPORT": (
        "The configured model does not support images. Check the vision model in screen.toml."
    ),
    "LOCAL_MODE_UNVERIFIED": "The local vision runtime has no verified local-only setup evidence.",
    "INCOMPATIBLE_MODEL_OR_OPTIONS": (
        "Ollama rejected the image or vision settings. Check the vision context in "
        "/screen-status; full-screen reads need the larger vision context."
    ),
    "VISION_MODEL_IDENTITY_CHANGED": (
        "The vision model identity changed during the request. No image answer was accepted."
    ),
    "VISION_OUTPUT_INVALID": (
        "The vision model returned an unreadable or invalid observation. If this is a "
        "word game, enlarge the board and ask again; no guess was accepted."
    ),
    "VISION_OUTPUT_LIMIT": (
        "The vision model ran out of reply space before finishing the observation. "
        "No partial reading or guess was accepted."
    ),
    "INVALID_RESPONSE": (
        "The local vision runtime returned an invalid response. No guess was accepted."
    ),
    "SCREEN_READ_FAILED": (
        "The screen read failed. /screen-status shows the failing stage and safe error category."
    ),
}


def screen_error(exc, stage):
    code = (
        exc.code
        if isinstance(exc, ProviderError)
        else str(exc)
        if isinstance(exc, Denied)
        else None
    )
    if code in SCREEN_ERRORS:
        return code
    return (
        "VISION_OUTPUT_INVALID"
        if stage == "vision"
        and isinstance(exc, ValueError)
        and not isinstance(exc, (ProviderError, Denied))
        else "SCREEN_READ_FAILED"
    )


def screen_question(text, has_context=False):
    text = text.casefold().strip()
    if re.search(r"\b(?:don't|do not|never)\s+(?:look|capture|watch|read|inspect|see)\b", text):
        return False
    if re.search(
        r"\b(?:what is|what's|how does|explain)\s+(?:a |the )?screen\s+"
        r"(?:capture|recording|resolution|refresh|sharing|saver)\b",
        text,
    ):
        return False
    if text.rstrip(".!?") in {"stop watching", "stop screen watching", "stop looking at my screen"}:
        return True
    explicit = re.search(
        r"\b(?:what(?:'s| is) on (?:my |the )?screen|what am i looking at|"
        r"(?:look at|check|scan|capture|inspect|read|describe|explain|watch) (?:my |the |this )?"
        r"(?:whole |entire |full )?"
        r"(?:screen|screenshot|window|desktop)|help.*wordle|"
        r"application am i using|what am i doing|watch my wordle|"
        r"keep an eye on this window|follow what i'm doing)\b",
        text,
    )
    deictic = re.search(
        r"\b(what(?:'s| is) (?:this|that)\b|what (?:[a-z]+ ){1,3}is (?:this|that)\b|"
        r"what(?:'s| is) wrong with this|(?:read|explain) this (?:error|chart)|"
        r"describe (?:the|this) picture|can you (?:read this|see the problem)|"
        r"what does this (?:error|button)|what should i click|help me with this game)\b",
        text,
    )
    followup = has_context and re.search(
        r"\b(check again|check it again|what changed|help me solve it|what should i do next|"
        r"entered another guess|look again|tell me more about (?:it|that))\b",
        text,
    )
    return bool(explicit or deictic or followup)


class ScreenRegistry:
    def __init__(self, underlying, screen):
        self.underlying, self.screen = underlying, screen

    def __getattr__(self, name):
        return getattr(self.underlying, name)

    def validate(self, action):
        if action.capability != "screen.observe":
            return self.underlying.validate(action)
        context = self.screen.pending.get(action.task_id)
        if (
            not context
            or action.app_id != "screen"
            or action.target_identity != context["target"].identity
            or action.window_ref != context["nonce"]
            or action.effects != ("screen_private_read",)
            or action.adapter_version != "screen-read-v1"
            or action.policy_version != POLICY_VERSION
            or digest(action) != action.digest
            or not self.screen.config.enabled
            or self.screen.revoked
        ):
            raise Denied("SCREEN_SCOPE_INVALID_OR_REVOKED")


class ScreenAssistance:
    evidence_source = "screen-binding-validator-v1"
    evidence_kind = "scoped_visual_observation"

    def __init__(self, broker, config, capture, vision, indicator, answerer=None):
        self.broker, self.clock, self.config = broker, broker.clock, config
        self.capture, self.vision, self.indicator = capture, vision, indicator
        self.pending, self.replies = {}, {}
        self.cancel = lambda: False
        self.selected = None
        self.observation = None
        self.previous_observation = None
        self.inventory = {}
        self.revoked = False
        self.watching = None
        self.real = True
        self.notice = lambda text: None
        self.timings = {}
        self.stop_requested = threading.Event()
        self.failure_code = None
        self.failure_stage = None
        self.stage = "validation"
        from jarvis.screen_answer import LocalScreenAnswer

        self.answerer = answerer or LocalScreenAnswer(broker)
        self.answer_status = "not_started"
        self.dialogue = []  # Private bounded screen context, never ordinary chat history.

    def stopped(self):
        return self.broker.cancel_requested() or self.revoked or self.stop_requested.is_set()

    def clear(self):
        self.stop_watching()
        self.observation = self.previous_observation = self.selected = None
        self.inventory.clear()
        self.replies.clear()
        self.end_dialogue()

    def end_dialogue(self):
        self.dialogue.clear()

    def has_dialogue(self):
        if self.dialogue and not (
            0
            <= self.clock.now() - self.dialogue[-1]["captured_at"]
            <= self.config.freshness_seconds
        ):
            self.end_dialogue()
        return bool(self.dialogue)

    def companion_event(self, event, task="", target=None):
        update = getattr(self.indicator, "update", None)
        if update is None or not self.indicator.alive:
            return
        watch = self.watching
        update(
            event,
            watch["companion_id"] if watch else task,
            (target or self.selected).bounds if (target or self.selected) else (0, 0, 1, 1),
            watching=bool(watch),
        )

    def stop_watching(self):
        if self.watching:
            try:
                self.companion_event("cancelled")
            except (OSError, ValueError):
                pass
        self.watching = None
        self.indicator.close()

    def close(self):
        self.revoked = True
        self.clear()

    def control(self, text):
        parts = text.split()
        if text == "/screen-status":
            return (
                f"Screen assistance={'enabled' if self.config.enabled else 'disabled'}; "
                f"watching={'active' if self.watching else 'off'}; "
                f"local vision={self.config.vision_model or 'not configured'}. "
                f"Default capture={self.config.default_capture_scope}. "
                f"Vision context={self.config.context_tokens}. "
                f"Last failure={self.failure_stage or 'none'}/{self.failure_code or 'none'}. "
                f"Chat handoff={'on' if self.config.chat_answer_enabled else 'off'}/"
                f"{self.answer_status}. "
                "Only explicit requests capture; images stay in memory. "
                "/screen-windows lists scopes."
            )
        if text in {"/screen-stop", "/screen-revoke"}:
            self.clear()
            self.stop_requested.set()
            self.revoked = text == "/screen-revoke"
            return "Screen access stopped; transient observations cleared. No action was replayed."
        if not text.startswith("/screen-"):
            return None
        if not self.config.enabled:
            return "Screen capture is disabled. Select an enabled private --screen-config first."
        if text == "/screen-windows":
            targets = self.capture.inventory(self.broker.cancel_requested)
            self.inventory = {t.reference: t for t in targets}
            return (
                "\n".join(
                    f"{n + 1}. {t.application} ({t.kind}) · {t.reference}"
                    for n, t in enumerate(targets)
                )
                or "No eligible capture targets."
            )
        if (
            parts[0] in {"/screen-allow", "/screen-allow-display", "/screen-allow-desktop"}
            and len(parts) == 2
        ):
            target = self.inventory.get(parts[1])
            expected = {
                "/screen-allow": "window",
                "/screen-allow-display": "display",
                "/screen-allow-desktop": "desktop",
            }[parts[0]]
            if not target or target.kind != expected:
                raise Denied("List scopes with /screen-windows, then choose the matching scope.")
            self.capture.validate(target, self.broker.cancel_requested)
            self.clear()
            self.revoked = False
            self.stop_requested.clear()
            self.selected = target
            return (
                f"Screen questions may inspect this exact {target.kind}: {target.application}. "
                "No capture yet. /screen-revoke ends permission."
            )
        if text == "/screen-watch":
            if not self.config.watch_enabled or not self.selected:
                return "Watching needs watch_enabled=true and an explicitly allowed target."
            self.capture.validate(self.selected, self.stopped)
            self.indicator.start()
            self.watching = {
                "companion_id": str(uuid4()),
                "expires": self.clock.now() + self.config.watch_seconds,
                "next": self.clock.now() + 5,
                "samples": 0,
                "digest": None,
                "changes": 0,
            }
            self.companion_event("watching", target=self.selected)
            return (
                f"Watching {self.selected.application} for at most "
                f"{self.config.watch_seconds} seconds, "
                f"every {self.config.sample_seconds} seconds. Switch to it within five seconds. "
                "Switching elsewhere stops watching. "
                "Close the screen indicator or /screen-stop to stop."
            )
        return (
            "Screen controls: /screen-status, /screen-windows, /screen-allow <reference>, "
            "/screen-allow-display <reference>, /screen-watch, /screen-stop, /screen-revoke."
        )

    def poll(self):
        watch = self.watching
        if not watch:
            return
        now = self.clock.now()
        if (
            self.stopped()
            or not self.indicator.alive
            or now >= watch["expires"]
            or watch["samples"] >= self.config.max_samples
        ):
            self.stop_watching()
            self.notice("Screen watching ended; no further captures.")
            return
        if now < watch["next"] or self.broker.busy:
            return
        try:
            active = self.capture.foreground(self.stopped)
            if self.selected.kind != "window" or active.identity != self.selected.identity:
                raise Denied("WATCH_SCOPE_CHANGED")
            # Each sample is its own journaled broker read. Unchanged pixels skip inference.
            result = self.submit("Describe meaningful visible changes.", watch_sample=True)
            if result.state != State.SUCCEEDED:
                raise Denied("WATCH_SAMPLE_FAILED")
            if self.watching:
                watch["next"] = self.clock.now() + self.config.sample_seconds
        except (ValueError, OSError, RuntimeError):
            self.stop_watching()
            self.notice(
                "Screen watching stopped because its scope, permission "
                "or capture became unavailable."
            )

    def submit(self, text, request_key=None, *, watch_sample=False, conversation_context=()):
        broker = self.broker
        if text.strip().casefold().rstrip(".!?") in {
            "stop watching",
            "stop screen watching",
            "stop looking at my screen",
        }:
            return TaskResult("", State.ANSWERED, self.control("/screen-stop"), False, "say")
        key = request_key or str(uuid4())
        # Recover duplicate receipts without another screenshot or model call.
        previous = broker.store.db.execute(
            "SELECT task_id FROM tasks WHERE session=? AND request_key=?",
            (broker.grant.session, key),
        ).fetchone()
        if previous:
            stored = broker.store.db.execute(
                "SELECT request_fingerprint FROM tasks WHERE task_id=?", (previous[0],)
            ).fetchone()
            if (
                broker.store.get(previous[0]).scope.app_id != "screen"
                or stored[0] != hashlib.sha256(text.encode()).hexdigest()
            ):
                raise Denied("Request key reused for a different instruction")
            return replace(
                broker.store.result(previous[0]),
                simulated=False,
                display_message=self.replies.get(
                    previous[0], "This screen request already ended; no capture was repeated."
                ),
            )
        if not self.config.enabled or self.revoked or self.stop_requested.is_set():
            return TaskResult(
                "",
                State.WAITING_INPUT,
                "Screen capture is disabled or revoked. "
                "Enable it explicitly and choose an allowed scope.",
                False,
                "clarify",
            )
        if broker.busy:
            return TaskResult("", State.FAILED, "Another request is active.", False)
        if len(text.encode()) > 4096:
            raise Denied("Screen question exceeds its input limit")
        if re.search(r"(?i)\b(stop|stop watching)\b", text):
            return TaskResult("", State.ANSWERED, self.control("/screen-stop"), False, "say")
        if re.search(r"(?i)\b(watch|keep an eye|follow what)\b", text):
            if self.selected is not None:
                return TaskResult("", State.ANSWERED, self.control("/screen-watch"), False, "say")
            return TaskResult(
                "",
                State.WAITING_INPUT,
                "Select the exact window with /screen-windows and /screen-allow, "
                "then /screen-watch starts a bounded session.",
                False,
                "clarify",
            )
        full_screen = bool(
            re.search(
                r"(?i)\b((?:full|whole|entire) (?:screen|desktop)|(?:all|both) monitors)\b", text
            )
        )
        if (
            full_screen
            and self.config.default_capture_scope == "foreground_window"
            and (self.selected is None or self.selected.kind not in {"display", "desktop"})
        ):
            return TaskResult(
                "",
                State.WAITING_INPUT,
                "Display capture needs separate permission. Use /screen-windows then "
                "/screen-allow-display for one display. "
                "Window permission never expands automatically.",
                False,
                "clarify",
            )
        try:
            if self.selected is not None and not full_screen:
                target = self.selected
            elif self.config.default_capture_scope == "primary_display":
                targets = self.capture.inventory(self.stopped)
                displays = [t for t in targets if t.kind == "display"]
                primary = [
                    t
                    for t in displays
                    if t.bounds[0] <= 0 < t.bounds[2] and t.bounds[1] <= 0 < t.bounds[3]
                ]
                if len(primary) != 1:
                    raise Denied("PRIMARY_DISPLAY_UNAVAILABLE")
                target = primary[0]
                if re.search(
                    r"(?i)\b((?:all|both) monitors|(?:whole|entire|full) desktop)\b", text
                ):
                    desktops = [t for t in targets if t.kind == "desktop"]
                    if len(desktops) != 1:
                        raise Denied("DESKTOP_CAPTURE_UNAVAILABLE")
                    target = desktops[0]
            else:
                target = self.selected or self.capture.foreground(self.stopped)
        except (ValueError, OSError, RuntimeError):
            return TaskResult(
                "",
                State.WAITING_INPUT,
                "I cannot inspect the requested screen scope. "
                "Check display availability or choose a narrower visible window.",
                False,
                "clarify",
            )
        if (
            self.observation
            and not self.selected
            and target.identity != self.observation.target_identity
            and re.search(r"(?i)\b(again|changed|solve it|next|that|another guess)\b", text)
        ):
            return TaskResult(
                "",
                State.WAITING_INPUT,
                "The foreground window changed since the last observation. "
                "Select the intended window with /screen-windows and /screen-allow, "
                "or explicitly ask what is on the current screen.",
                False,
                "clarify",
            )
        nonce = "capture_" + uuid4().hex
        scope = Scope(broker.grant.session, "screen", "screen_private_read", nonce)
        deadline = self.clock.now() + min(
            180, self.config.inference_seconds + self.config.capture_seconds + 10
        )
        task, _ = broker.store.accept(
            key,
            scope,
            hashlib.sha256(text.encode()).hexdigest(),
            deadline,
            {"capability": "screen-read-v1"},
        )
        self.pending[task.task_id] = {
            "target": target,
            "nonce": nonce,
            "question": text,
            "watch_sample": watch_sample,
            "observation": None,
            "foreground": self.selected is None and target.kind == "window",
            "text_profile": broker.profile,
            "conversation_context": tuple(conversation_context)[-4:],
        }
        old_grant = broker.grant
        self.failure_code = self.failure_stage = None
        broker.busy = True
        broker.model_turns, broker.model_metrics = 0, []
        self.answer_status = "not_started"
        try:
            broker.store.transition(task.task_id, State.PLANNING)
            if self.stopped():
                broker.store.cancel(task.task_id)
                return broker.store.result(task.task_id)
            broker.grant = replace(
                old_grant,
                apps=old_grant.apps | {"screen"},
                effects=old_grant.effects | {"screen_private_read"},
                expires_at=deadline,
            )
            action = PreparedAction(
                task.task_id,
                task.revision,
                "screen.observe",
                "screen",
                target.identity,
                scope.session,
                (scope.effect,),
                "screen-read-v1",
                POLICY_VERSION,
                broker.grant.grant_id,
                broker.grant.version,
                deadline,
                "",
                nonce,
            )
            action = replace(action, digest=digest(action))
            broker.registry.validate(action)
            broker.store.transition(task.task_id, State.READY)
            result = broker.dispatch(action)
            try:
                self.companion_event(
                    "completed"
                    if result.state == State.SUCCEEDED
                    else "cancelled"
                    if result.state == State.CANCELLED or self.stopped()
                    else "error",
                    task.task_id,
                    target,
                )
            except (OSError, ValueError):
                # Presentation failure cannot rewrite an already verified result.
                self.indicator.close()
            if result.state == State.SUCCEEDED:
                return replace(
                    result, simulated=False, display_message=self.replies.get(task.task_id)
                )
            if self.failure_code:
                with broker.store.db:
                    broker.store.event(
                        task.task_id,
                        "screen_read_error",
                        payload={"stage": self.failure_stage, "code": self.failure_code},
                    )
            return replace(
                result,
                simulated=False,
                display_message="Screen reading was stopped."
                if result.state == State.CANCELLED
                else SCREEN_ERRORS.get(self.failure_code, SCREEN_ERRORS["SCREEN_READ_FAILED"]),
            )
        except (ValueError, OSError, RuntimeError):
            current = broker.store.get(task.task_id)
            if current.state in {State.PLANNING, State.READY}:
                broker.store.transition(
                    task.task_id, State.FAILED, "Screen request failed; private content omitted."
                )
            return replace(broker.store.result(task.task_id), simulated=False)
        finally:
            current_grant = broker.grant
            broker.grant = replace(
                old_grant, revoked=current_grant.revoked, version=current_grant.version
            )
            broker.busy = False
            self.pending.pop(task.task_id, None)
            self.replies = dict(list(self.replies.items())[-4:])
            if not self.watching:
                self.indicator.close()

    def execute(self, action, gate):
        self.stage = "validation"
        try:
            return self._execute(action, gate)
        except Exception as exc:
            self.failure_stage, self.failure_code = self.stage, screen_error(exc, self.stage)
            raise

    def _execute(self, action, gate):
        import time

        context = self.pending[action.task_id]
        target = context["target"]

        def check():
            gate()
            if context["watch_sample"] and (
                not self.watching or self.clock.now() >= self.watching["expires"]
            ):
                raise AdmissionRejected("WATCH_EXPIRED")
            if self.stopped() or (self.indicator.process is not None and not self.indicator.alive):
                raise AdmissionRejected("SCREEN_REVOKED_OR_STOPPED")
            if self.broker.profile != context["text_profile"]:
                raise AdmissionRejected("SCREEN_PROFILE_CHANGED")

        check()
        self.capture.validate(target, self.stopped)
        if (
            context["foreground"]
            and self.capture.foreground(self.stopped).identity != target.identity
        ):
            raise AdmissionRejected("FOREGROUND_CAPTURE_CHANGED")
        # Capability inspection before taking private pixels; absent vision never captures.
        self.stage = "model_check"
        self.vision.inspect(lambda: self.cancel() or self.stopped(), action.expires_at)
        check()
        self.indicator.start()
        self.notice("Screen access active: " + target.application + " · local analysis only.")
        check()
        start = time.perf_counter()
        self.stage = "capture"
        self.companion_event("capturing", action.task_id, target)
        check()
        frame = self.capture.capture(
            target,
            lambda: self.cancel() or self.stopped() or not self.indicator.alive,
            self.indicator.pid,
        )
        self.timings["capture_seconds"] = time.perf_counter() - start
        if (
            frame.target_identity != target.identity
            or frame.bounds != target.bounds
            or frame.width != target.bounds[2] - target.bounds[0]
            or frame.height != target.bounds[3] - target.bounds[1]
            or frame.width * frame.height > self.config.max_pixels
            or len(frame.png) > self.config.max_image_bytes
            or not 0 <= self.clock.now() - frame.captured_at <= self.config.freshness_seconds
        ):
            raise Denied("CAPTURE_BINDING_INVALID")
        check()
        if (
            context["foreground"]
            and self.capture.foreground(self.stopped).identity != target.identity
        ):
            raise AdmissionRejected("FOREGROUND_CAPTURE_CHANGED")
        watch = self.watching if context["watch_sample"] else None
        if watch:
            watch["samples"] += 1
            if watch["digest"] == frame.pixel_digest:
                context["unchanged"] = True
                self.replies[action.task_id] = "No pixel change in the sampled frame."
                return
            if watch["digest"] is not None:
                watch["changes"] += 1
            watch["digest"] = frame.pixel_digest
        start = time.perf_counter()
        self.stage = "vision"
        self.companion_event("analyzing", action.task_id, target)
        check()
        prior = (
            self.previous_observation
            if re.search(r"(?i)\b(changed|compare|difference)\b", context["question"])
            and self.previous_observation is not None
            else self.observation
        )
        interpreted, metadata = self.vision.analyze(
            frame,
            context["question"],
            {
                "application": target.application,
                "previous": {
                    "captured_at": prior.captured_at,
                    "description": prior.interpretation.description[:1000],
                    "objects": prior.interpretation.objects[:10],
                    "visible_text": prior.interpretation.visible_text[:5],
                }
                if prior
                and prior.target_identity == target.identity
                and 0 <= self.clock.now() - prior.captured_at <= self.config.freshness_seconds
                else None,
            },
            lambda: (
                self.cancel()
                or self.stopped()
                or not self.indicator.alive
                or bool(
                    context["watch_sample"]
                    and (not self.watching or self.clock.now() >= self.watching["expires"])
                )
            ),
            action.expires_at,
        )
        self.timings["vision_seconds"] = time.perf_counter() - start
        self.stage = "verification"
        check()
        self.capture.validate(target, self.stopped)
        observation = Observation(
            observation_id="observation_" + uuid4().hex,
            artifact=frame.artifact,
            target_identity=target.identity,
            application=target.application,
            capture_scope=target.kind,
            captured_at=frame.captured_at,
            generation=frame.generation,
            bounds=frame.bounds,
            image_dimensions=(frame.width, frame.height),
            analyzed_regions=metadata.get("analyzed_regions", [frame.bounds]),
            model=metadata["identity"],
            model_digest=metadata["digest"],
            interpretation=interpreted,
        )
        age = max(0, self.clock.now() - frame.captured_at)
        answer = (
            f"In the image captured {age:.0f} seconds ago: "
            if age > self.config.freshness_seconds
            else "From the captured image: "
        ) + interpreted.description
        if interpreted.wordle is not None:
            from jarvis.wordle import board_advice

            # Only deterministic logic recommends guesses; discard model-proposed guesses.
            answer = board_advice(interpreted.wordle, self.config.word_list)
            self.answer_status = "deterministic_solver"
        else:
            from jarvis.screen_vision import word_game_question

            if word_game_question(context["question"]):
                answer = (
                    "I cannot reliably read a Wordle board in this capture. "
                    "Make the board larger and visible on your main screen, then ask again. "
                    "No guess was accepted."
                )
                self.answer_status = "unreadable_board"
            elif self.config.chat_answer_enabled:
                self.stage = "answer"
                check()
                start = time.perf_counter()
                recent = [
                    {"question": turn["question"], "answer": turn["answer"]}
                    for turn in self.dialogue[-2:]
                    if turn["target_identity"] == target.identity
                    and 0 <= self.clock.now() - turn["captured_at"] <= self.config.freshness_seconds
                ]
                history = [
                    {"role": message.role, "text": message.text[:400]}
                    for message in context["conversation_context"]
                    if message.role in {"owner", "assistant"}
                ]
                try:
                    answer = self.answerer.compose(
                        observation,
                        context["question"],
                        {"conversation": history, "screen": recent},
                        context["text_profile"],
                        self.broker.store.get(action.task_id),
                        min(action.expires_at, self.clock.now() + self.config.chat_answer_seconds),
                        lambda: self.cancel() or self.stopped() or not self.indicator.alive,
                    )
                    check()
                    self.answer_status = "generated"
                    age = max(0, self.clock.now() - frame.captured_at)
                    if age > self.config.freshness_seconds:
                        answer = f"Based on the screen captured {age:.0f} seconds ago: " + answer
                except (ProviderError, ValueError) as exc:
                    check()  # A presentation fallback never bypasses stop/revocation/expiry.
                    code = exc.code if isinstance(exc, ProviderError) else "INVALID_ANSWER"
                    if code not in {
                        "TIMEOUT",
                        "CONTEXT_LIMIT",
                        "INVALID_RESPONSE",
                        "INVALID_DECISION",
                        "MODEL_TURN_BUDGET",
                        "RUNTIME_UNAVAILABLE",
                    }:
                        code = "INVALID_ANSWER"
                    self.answer_status = "fallback/" + code
                    with self.broker.store.db:
                        self.broker.store.event(
                            action.task_id, "screen_answer_fallback", payload={"code": code}
                        )
                    age = max(0, self.clock.now() - frame.captured_at)
                    answer = (
                        f"In the image captured {age:.0f} seconds ago: "
                        if age > self.config.freshness_seconds
                        else "From the captured image: "
                    ) + interpreted.description
                    answer += "\nI read the screen, but couldn't finish the explanation."
                finally:
                    self.timings["answer_seconds"] = time.perf_counter() - start
            else:
                self.answer_status = "disabled"
        # Keep every limitation visible without repeating an exact warning the
        # text model has already included in its natural reply.
        remaining = [
            text
            for text in interpreted.uncertainty
            if text.casefold().strip() not in answer.casefold()
        ]
        if remaining:
            answer += "\n" + " ".join(remaining)
        unreadable = [
            text
            for text in interpreted.unreadable_regions
            if text.casefold().strip() not in answer.casefold()
        ]
        if unreadable:
            answer += "\nSome content is unreadable: " + "; ".join(unreadable)
        if self.watching and re.search(r"(?i)what changed", context["question"]):
            answer += (
                f"\n{self.watching['changes']} sampled pixel changes; "
                "events between samples are unknown."
            )
        self.stage = "verification"
        check()
        self.capture.validate(target, self.stopped)
        context["observation"] = observation
        self.replies[action.task_id] = answer
        context["dialogue"] = {
            "question": context["question"][:600],
            "answer": answer[:1600],
            "target_identity": target.identity,
            "captured_at": frame.captured_at,
        }
        # Pixels go out of scope here. No image or visual text enters journal/history/web.

    def observe(self, action):
        try:
            return self._observe(action)
        except Exception as exc:
            self.failure_stage, self.failure_code = (
                "verification",
                screen_error(exc, "verification"),
            )
            raise

    def _observe(self, action):
        context = self.pending[action.task_id]
        observation = context["observation"]
        self.capture.validate(context["target"], self.stopped)
        if self.cancel() or not self.indicator.alive:
            raise Denied("SCREEN_CANCELLED")
        if observation:
            self.previous_observation = self.observation
            self.observation = observation
            self.dialogue = (self.dialogue + [context["dialogue"]])[-2:]
        elif not context.get("unchanged"):
            raise Denied("SCREEN_EVIDENCE_MISSING")
        return Evidence(
            action.target_identity,
            action.session,
            self.clock.now(),
            None,
            self.evidence_source,
            "tool_output",
            "private",
            self.evidence_kind,
            True,
            action.window_ref,
            action.target_identity,
        )

    def success_message(self, action):
        return (
            "Screen observation completed; private image and interpretation omitted from journal."
        )


def attach(broker, config, *, capture=None, vision=None, indicator=None, answerer=None):
    from jarvis.screen_capture import CaptureIndicator, WindowsCapture
    from jarvis.screen_vision import LocalVision

    screen = ScreenAssistance(
        broker,
        config,
        capture or WindowsCapture(config),
        vision or LocalVision(broker.clock, config, broker.profile),
        indicator or CaptureIndicator(config.companion),
        answerer,
    )
    broker.registry = ScreenRegistry(broker.registry, screen)
    broker.screen = screen
    return screen
