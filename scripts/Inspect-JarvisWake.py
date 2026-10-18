"""Build only an inactive wake recognizer/grammar. No recording or playback."""

import argparse
import json
import os
import threading
import time
from pathlib import Path

from jarvis.voice_data import load_config
from jarvis.voice_keyword import WakeSetupError, WindowsWakeDetector


def check_message_pump(detector):
    import ctypes as c
    from ctypes import wintypes as w

    from comtypes.automation import IDispatch
    from comtypes.client import PumpEvents

    from jarvis.voice_keyword import WakeMessagePump

    receiver = detector.connection.receiver.QueryInterface(IDispatch)
    pump = WakeMessagePump()
    timer_callback = c.WINFUNCTYPE(None, w.HWND, w.UINT, c.c_size_t, w.DWORD)
    user = pump.user
    user.SetTimer.argtypes = [w.HWND, c.c_size_t, w.UINT, timer_callback]
    user.SetTimer.restype = c.c_size_t
    user.KillTimer.argtypes = [w.HWND, c.c_size_t]
    user.KillTimer.restype = w.BOOL

    @timer_callback
    def callback(*args):
        receiver.Invoke(1, 1, 0)  # Synthetic metadata only; native recognizer stays inactive.

    detector.events.started = False
    timer = user.SetTimer(None, 0, 10, callback)
    if not timer:
        raise OSError("Owned diagnostic timer unavailable")
    try:
        PumpEvents(0.08)
        via_com_wait = detector.events.started
        until = time.monotonic() + 0.5
        while not detector.events.started and time.monotonic() < until:
            pump.pump()
            time.sleep(0.005)
        return {
            "com_wait_delivered": via_com_wait,
            "windows_pump_delivered": detector.events.started,
            "recognizer_inactive": detector.recognizer.State == 0,
        }
    finally:
        user.KillTimer(None, timer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-events", action="store_true")
    parser.add_argument("--check-dispatch", action="store_true")
    parser.add_argument("--check-message-pump", action="store_true")
    args = parser.parse_args()
    config = load_config(Path(os.environ["LOCALAPPDATA"]) / "Jarvis")
    detector = WindowsWakeDetector(config, threading.Event(), lambda *a, **k: None)
    outcome = {"status": "FAILED", "activation_requested": False}
    try:
        detector.open(activate=False)
        outcome.update(status="INACTIVE_SETUP_READY", stage="GRAMMAR")
        if args.check_message_pump:
            outcome["message_pump"] = check_message_pump(detector)
        if args.check_dispatch:
            from comtypes.automation import IDispatch

            # Exercise only the callback receiver with synthetic metadata. The
            # recognizer stays inactive; no speech is emulated or mic activated.
            receiver = detector.connection.receiver.QueryInterface(IDispatch)
            receiver.Invoke(1, 1, 0)  # StartStream event signature.
            outcome["synthetic_start_callback"] = detector.events.started
            outcome["recognizer_inactive"] = detector.recognizer.State == 0
        if args.compare_events:
            from comtypes.client import GetEvents

            try:
                connection = GetEvents(detector.context, detector.events)
            except Exception as exc:
                outcome["automatic_events"] = {
                    "status": "FAILED",
                    **WakeSetupError("EVENTS", exc).diagnostic.model_dump(),
                }
            else:
                connection.disconnect()
                outcome["automatic_events"] = {"status": "READY"}
    except WakeSetupError as exc:
        outcome.update(code=str(exc), **exc.diagnostic.model_dump())
    except ValueError as exc:
        outcome["code"] = str(exc) if str(exc).startswith("WAKE_") else "WAKE_SETUP_FAILED"
    except Exception:
        outcome["code"] = "WAKE_SETUP_FAILED"
    finally:
        try:
            detector.close()
        except WakeSetupError as exc:
            if outcome["status"] == "INACTIVE_SETUP_READY":
                outcome.update(status="FAILED", code=str(exc), **exc.diagnostic.model_dump())
        except Exception:
            if outcome["status"] == "INACTIVE_SETUP_READY":
                outcome.update(status="FAILED", code="WAKE_INPUT_DID_NOT_STOP")
    print(json.dumps(outcome), flush=True)
    return 0 if outcome["status"] == "INACTIVE_SETUP_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
