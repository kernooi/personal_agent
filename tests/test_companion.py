"""Deterministic presentation tests; no Windows overlay, capture, model or GUI root."""

import math

import pytest

from jarvis.companion import Animation, CompanionConfig, Pose, eyes, placement
from jarvis.screen_data import ScreenConfig


def test_configuration_and_disabled_companion_keep_screen_permission_separate():
    config = ScreenConfig()
    assert not config.enabled and config.companion.enabled
    animation = Animation(CompanionConfig(enabled=False))
    animation.event("capturing", "task", 1, 0)
    assert animation.pose(1).opacity == 0
    for value in (47, 129):
        with pytest.raises(ValueError):
            CompanionConfig(size=value)


@pytest.mark.parametrize("size", [48, 64, 80, 128])
@pytest.mark.parametrize("direction", [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (0, 0)])
def test_exactly_two_small_pill_eyes_inside_circular_body(size, direction):
    shapes = eyes(Pose(gaze_x=direction[0], gaze_y=direction[1]), size)
    assert len(shapes) == 2
    for x, y, w, h in shapes:
        assert 0.08 * size <= w <= 0.11 * size
        assert 0.16 * size <= h <= 0.20 * size
        assert y < size / 2
        for dx in (-w / 2, w / 2):
            for dy in (-h / 2, h / 2):
                assert math.hypot(x + dx - size / 2, y + dy - size / 2) < size / 2


def test_gaze_smooth_interpolation():
    a = Animation(seed=1)
    a.previous, a.gaze, a.gaze_started = (0, 0), (1, -1), 1
    assert a.current_gaze(1) == (0, 0)
    assert a.current_gaze(1.135) == pytest.approx((0.5, -0.5))
    assert a.current_gaze(1.27) == (1, -1)


def test_entrance_exit_and_success_blink():
    a = Animation(seed=1)
    a.event("capturing", "one", 1, 0)
    assert a.pose(0).scale == pytest.approx(0.65)
    assert a.pose(0.15).opacity > 0
    assert a.pose(0.41).scale == 1
    a.event("completed", "one", 2, 1)
    assert a.pose(1.09).blink < 0.2
    assert 0 < a.pose(1.5).opacity < 1
    assert a.pose(1.7).opacity == 0


def test_blink_independent_of_gaze_and_double_blink_is_bounded():
    a = Animation(seed=2)
    a.event("capturing", "one", 1, 0)
    a.next_blink = 4
    a.pose(4)
    assert a.pose(4.075).blink < 0.15
    assert a.pose(4.16).blink == pytest.approx(1)
    assert a.next_blink >= 4.38


def test_cancellation_duplicate_and_late_events_do_not_revive_overlay():
    a = Animation(seed=1)
    assert a.event("capturing", "a", 1, 0)
    assert not a.event("capturing", "a", 1, 0.1)
    assert a.event("cancelled", "a", 2, 0.2)
    assert a.pose(0.2).opacity == 0
    assert not a.event("analyzing", "a", 3, 0.3)
    assert not a.event("capturing", "a", 4, 0.4)
    assert a.event("capturing", "b", 5, 0.5)
    assert a.event("analyzing", "b", 6, 0.51)
    assert a.pose(1).state == "analyzing"
    assert a.pose(1).opacity == 1


def test_watch_between_samples_is_not_capturing_and_stops():
    a = Animation(seed=2)
    a.event("watching", "watch", 1, 0)
    a.event("capturing", "watch", 2, 1, watching=True)
    a.event("analyzing", "watch", 3, 2, watching=True)
    a.event("completed", "watch", 4, 3, watching=True)
    assert a.pose(4).state == "watching" and a.pose(4).opacity == 1
    assert a.event("capturing", "watch", 5, 5, watching=True)
    a.event("cancelled", "watch", 6, 6)
    assert not a.event("capturing", "watch", 7, 7)
    assert a.pose(7).opacity == 0


def test_reduced_motion_and_watch_preference():
    a = Animation(CompanionConfig(reduced_motion="always"), seed=1)
    a.event("capturing", "task", 1, 0)
    assert a.pose(0.5).bob == a.pose(3).bob == 0
    assert a.pose(3).scale == a.pose(3).blink == 1
    a.event("analyzing", "task", 2, 4)
    assert a.pose(4).gaze_y < 0
    b = Animation(CompanionConfig(show_during_watch=False))
    b.event("watching", "w", 1, 0)
    assert b.pose(1).opacity == 0


@pytest.mark.parametrize(
    "work,dpi",
    [((0, 0, 1920, 1040), 96), ((-2560, -100, 0, 1300), 144), ((1920, 0, 3840, 1000), 192)],
)
@pytest.mark.parametrize("corner", ["bottom-right", "bottom-left", "top-right", "top-left"])
def test_monitor_dpi_placement_stays_in_work_area(work, dpi, corner):
    x, y, edge = placement(work, 80, dpi, corner)
    assert work[0] <= x and x + edge <= work[2]
    assert work[1] <= y and y + edge <= work[3]
    assert edge == round(80 * 1.32 * dpi / 96)


def test_denied_screen_request_emits_no_capture_animation(tmp_path):
    from jarvis.bootstrap import ManualClock, build
    from jarvis.models import Profile
    from jarvis.screen_fake import FakeCapture, FakeIndicator, FakeVision
    from jarvis.screen_tools import attach

    clock = ManualClock()
    broker = build(
        tmp_path / "journal",
        Profile(
            profile_name="test", model_identity="fixture", reply='{"kind":"say","text":"Fixture."}'
        ),
        clock=clock,
    )
    indicator = FakeIndicator()
    screen = attach(
        broker, ScreenConfig(), capture=FakeCapture(clock), vision=FakeVision(), indicator=indicator
    )
    screen.submit("What am I looking at?")
    assert indicator.events == [] and not indicator.alive
    screen.close()
    broker.store.close()


def test_terminal_history_and_sequences_are_bounded():
    a = Animation(seed=0)
    for i in range(100):
        a.event("capturing", str(i), i * 2, i)
        a.event("completed", str(i), i * 2 + 1, i + 0.1)
    assert len(a.retired) <= 64
    # Even retired IDs falling out of the cache cannot replay an old sequence.
    assert not a.event("capturing", "0", 0, 101)


@pytest.mark.parametrize(
    "failure", [None, "pid", "class", "affinity", "owner", "session", "exe", "creation"]
)
def test_capture_exclusion_is_bound_to_owned_verified_interpreter_ui(monkeypatch, failure):
    import sys
    from types import SimpleNamespace

    from jarvis.screen_worker import CaptureNative

    def pid(hwnd, output):
        output._obj.value = 2

    def cls(hwnd, output, length):
        output.value = "OtherApp" if failure == "class" else "JarvisCompanionOrbV1"

    def affinity(hwnd, output):
        output._obj.value = 1 if failure == "affinity" else 0x11
        return True

    native = CaptureNative.__new__(CaptureNative)
    native.user = SimpleNamespace(
        GetWindowThreadProcessId=pid, GetClassNameW=cls, GetWindowDisplayAffinity=affinity
    )
    process = {"owner_sid": "owner", "os_session": 1, "exe": sys._base_executable, "created": 20}
    launcher = {**process, "created": 10}
    if failure == "owner":
        process["owner_sid"] = "other"
    if failure == "session":
        process["os_session"] = 2
    if failure == "exe":
        process["exe"] = "untrusted.exe"
    if failure == "creation":
        launcher["created"] = 30
    native.native = SimpleNamespace(
        owner_sid="owner", session=1, process=lambda p: process if p == 2 else launcher
    )
    monkeypatch.setattr(
        "jarvis.application_identity.process_parents", lambda: {2: 99 if failure == "pid" else 1}
    )
    assert native.excluded_indicator(5, 1) is (failure is None)


def test_capture_to_analysis_never_regresses_on_late_capture_event():
    a = Animation(seed=1)
    a.event("capturing", "one", 1, 0)
    a.event("analyzing", "one", 2, 0.01)
    assert not a.event("capturing", "one", 3, 0.02)
    assert a.pose(0.5).state == "analyzing"


def test_native_fallback_hides_only_orb_before_capture_and_cleanup_is_idempotent(monkeypatch):
    from types import SimpleNamespace

    from jarvis import companion_windows as native

    calls = []
    monkeypatch.setattr(
        native, "function", lambda dll, name, *args: lambda *v: calls.append((name, v))
    )
    orb = native.Overlay.__new__(native.Overlay)
    orb.closed, orb.excluded, orb.hwnd, orb.user = False, False, 123, object()
    orb.renderer = SimpleNamespace(close=lambda: calls.append(("renderer.close", ())))
    orb.show(Pose("capturing", opacity=1))
    assert calls == [("ShowWindow", (123, 0))]
    orb.close()
    orb.close()
    assert calls[1:] == [("DestroyWindow", (123,)), ("renderer.close", ())]
