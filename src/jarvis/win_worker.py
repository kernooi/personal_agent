"""One bounded native operation with parent-owned JSON pipes; no pickle or shell."""

import json
import subprocess
import sys
import time

from jarvis.domain import Denied
from jarvis.models import reject_constant, unique_object
from jarvis.win_native import Native, clean, file_hash, window_identity


def read():
    raw = sys.stdin.buffer.readline(65537)
    if not raw or len(raw) > 65536:
        raise Denied("Worker envelope limit")
    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)


def send(request, stage, data):
    print(
        json.dumps(
            {"version": 1, "request_id": request["request_id"], "stage": stage, "data": data}
        ),
        flush=True,
    )


def selected(native, registration, expected):
    records = native.windows(registration)
    matches = [record for record in records if record["hwnd"] == expected["hwnd"]]
    if len(matches) != 1:
        raise Denied("Selected window missing or changed")
    actual = native.metadata(matches[0])
    actual_identity = window_identity(actual)
    if any(
        actual_identity[key] != value for key, value in expected.items() if key in actual_identity
    ):
        raise Denied("Selected window identity changed")
    return actual


def run(request):
    if (
        set(request)
        != {"version", "request_id", "deadline", "operation", "registration", "payload"}
        or request["version"] != 1
    ):
        raise Denied("Invalid worker protocol")
    if time.time() >= request["deadline"]:
        raise Denied("Worker deadline expired")
    from jarvis.notepad import Registration

    registration = Registration.model_validate(request["registration"], strict=True)
    registration.revalidate()
    config = registration.model_dump()
    native = Native()
    operation = request["operation"]
    payload = request["payload"]
    if operation == "activity":
        send(request, "result", native.activity())
        return
    if operation == "inventory":
        send(request, "result", native.windows(config))
        return
    if operation == "inspect":
        send(request, "result", selected(native, config, payload["window"]))
        return
    if operation not in {"open", "focus", "close"}:
        raise Denied("Unreviewed worker operation")
    current = None
    if operation != "open":
        current = selected(native, config, payload["window"])
        if operation == "close" and (
            not clean(current) or current["tab_ids"] != payload["window"]["tab_ids"]
        ):
            raise Denied("Whole-window close scope changed; handle manually")
    if native.activity() != payload["activity"]:
        raise Denied("User takeover or unexpected focus; operation paused")
    baseline = native.windows(config) if operation == "open" else []
    send(request, "ready", {})
    permit = read()
    if (
        permit != {"version": 1, "request_id": request["request_id"], "commit": True}
        or time.time() >= request["deadline"]
    ):
        raise Denied("Invalid or late commit")
    # Fresh observations after the parent grant/cancellation gate and any COM wait.
    registration.revalidate()
    if operation != "open":
        actual = selected(native, config, payload["window"])
        if operation == "close" and (
            not clean(actual) or actual["tab_ids"] != payload["window"]["tab_ids"]
        ):
            send(request, "rejected", {"reason": "Window scope changed before effect"})
            return
    if time.time() >= request["deadline"] or native.activity() != payload["activity"]:
        send(request, "rejected", {"reason": "User takeover before effect"})
        return
    if operation == "open":
        if file_hash(config["launcher"]) != config["launcher_sha256"]:
            raise Denied("Launcher changed")
        process = subprocess.Popen([config["launcher"]], shell=False, close_fds=True)
        # The launcher PID is deliberately not treated as window identity/readiness.
        process.poll()
    elif operation == "focus":
        native.user.SetForegroundWindow(payload["window"]["hwnd"])
    else:
        if not native.user.PostMessageW(payload["window"]["hwnd"], 0x0010, 0, 0):
            raise Denied("Close delivery uncertain")
    send(request, "result", {"baseline": baseline})


def main():
    # comtypes initializes COM with MTA on this worker's only automation thread.
    sys.coinit_flags = 0
    request = read()
    try:
        run(request)
    except Exception:
        # No exception dumps, titles, paths or private content in worker output.
        send(request, "error", {"reason": "Native operation unavailable or target changed"})


if __name__ == "__main__":
    main()
