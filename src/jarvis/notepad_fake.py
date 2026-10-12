"""Deterministic M2 platform fixture. Never imports Windows or launches processes."""

from copy import deepcopy

from jarvis.domain import AdmissionRejected


class FakeNotepadTransport:
    def __init__(self):
        self.records = []
        self.focus = 0
        self.input_tick = 1
        self.calls = []
        self.before_effect = lambda: None
        self.after_effect = lambda: None
        self.apply = True
        self.dialog = False
        self.pid = 10
        self.crash = False

    def add(self, *, empty=True, tabs=1):
        self.pid += 1
        record = {
            "hwnd": self.pid * 10,
            "pid": self.pid,
            "created": self.pid * 100,
            "os_session": 1,
            "exe": "fixture:Notepad.exe",
            "exe_sha256": "a" * 64,
            "package": "fixture:microsoft-notepad",
            "class_name": "Notepad",
            "runtime_id": [42, self.pid],
            "tab_ids": [[self.pid, index] for index in range(tabs)],
            "empty": empty,
            "modified": False,
            "enabled": True,
            "owned_dialog": False,
            "minimized": False,
        }
        self.records.append(record)
        return record

    def call(self, operation, payload=None, gate=None):
        payload = payload or {}
        if operation == "activity":
            return {"foreground": self.focus, "last_input": self.input_tick}
        if operation == "inventory":
            return deepcopy(self.records)
        expected = payload.get("window")
        target = next(
            (
                row
                for row in self.records
                if expected
                and row["hwnd"] == expected["hwnd"]
                and row["created"] == expected["created"]
            ),
            None,
        )
        if operation == "inspect":
            from jarvis.notepad import identity

            if target is None or identity(target) != identity(expected):
                raise AdmissionRejected("Stale window")
            return deepcopy(target)
        self.before_effect()
        gate()
        if operation != "open":
            from jarvis.notepad import identity

            if target is None or identity(target) != identity(expected):
                raise AdmissionRejected("Stale window")
        if operation == "minimize" and (
            target.get("enabled") is not True or target.get("owned_dialog") is not False
        ):
            raise AdmissionRejected("Unavailable minimize target")
        if (
            not payload.get("allow_concurrent_input", False)
            and self.call("activity") != payload["activity"]
        ):
            raise AdmissionRejected("User takeover")
        if operation == "close" and (
            not target
            or target["empty"] is not True
            or target["modified"] is not False
            or len(target["tab_ids"]) != 1
            or target["tab_ids"] != expected["tab_ids"]
        ):
            raise AdmissionRejected("Unsafe window close")
        self.calls.append(operation)
        baseline = deepcopy(self.records)
        if self.apply:
            if operation == "open":
                self.add()
            elif operation == "focus":
                target["minimized"] = False
                self.focus = target["hwnd"]
            elif operation == "minimize":
                target["minimized"] = True
                if self.focus == target["hwnd"]:
                    self.focus = 0
            elif operation == "close":
                if self.dialog:
                    target["owned_dialog"] = True
                else:
                    self.records.remove(target)
        self.after_effect()
        if self.crash:
            raise RuntimeError("Injected worker loss after effect")
        return {"baseline": baseline}
