"""Synthetic platform; no real OS, inference, file or networking calls."""

from copy import deepcopy

from jarvis.application_data import Application, app_id
from jarvis.domain import AdmissionRejected


class FakeApplicationPlatform:
    def __init__(self):
        self.apps = []
        self.windows = []
        self.calls = []
        self.foreground = 0
        self.input_tick = 1
        self.before_effect = lambda: None
        self.after_effect = lambda: None
        self.apply = True
        self.crash = False
        self.pid = 100

    def add_app(self, name):
        launch = "fixture:" + name
        app = Application(
            app_id=app_id(launch),
            name=name,
            launch_id=launch,
            kind="exe",
            executable="fixture:" + name + ".exe",
        )
        self.apps.append(app)
        return app

    def add_window(self, app):
        self.pid += 1
        row = dict(
            app_id=app.app_id,
            hwnd=self.pid,
            pid=self.pid,
            created=self.pid * 100,
            os_session=1,
            owner_sid="fixture",
            exe_sha256="a" * 64,
            package="",
            class_name="Fixture",
            frame_host=None,
            content_hwnd=0,
            enabled=True,
            owned_dialog=False,
            minimized=False,
            close_safe=None,
            protected=False,
        )
        self.windows.append(row)
        return row

    def call(self, operation, payload=None, gate=None):
        from jarvis.application_tools import identity

        payload = payload or {}
        if operation == "catalog":
            return {
                "apps": [a.model_dump() for a in self.apps],
                "unsupported_count": getattr(self, "unsupported_count", 0),
            }
        if operation == "activity":
            return {"foreground": self.foreground, "last_input": self.input_tick}
        if operation == "validate_app":
            return {"exe_sha256": "a" * 64}
        if operation == "inventory":
            return deepcopy(self.windows)
        if operation == "absence":
            return {"present": any(r["hwnd"] == payload["hwnd"] for r in self.windows)}
        expected = payload.get("window")

        def selected():
            target = next(
                (r for r in self.windows if expected and r["hwnd"] == expected["hwnd"]), None
            )
            if target is None or identity(target) != identity(expected):
                raise AdmissionRejected("Window changed")
            return target

        if operation == "inspect":
            return deepcopy(selected())
        self.before_effect()
        gate()
        if not payload.get("allow_concurrent_input", False) and payload["activity"] != self.call(
            "activity"
        ):
            raise AdmissionRejected("User takeover")
        target = selected() if expected else None
        if target and (target["owned_dialog"] or not target["enabled"]):
            raise AdmissionRejected("Dialog or disabled window")
        if operation == "close" and (
            target["close_safe"] is False
            or (target["protected"] and target["close_safe"] is not True)
            or not payload["close_reviewed"]
        ):
            raise AdmissionRejected("Unsafe close")
        self.calls.append(operation)
        if self.apply:
            if operation == "open" and not target:
                target = self.add_window(Application.model_validate(payload["app"]))
            elif operation == "focus":
                target["minimized"] = False
                self.foreground = target["hwnd"]
            elif operation == "minimize":
                target["minimized"] = True
                if self.foreground == target["hwnd"]:
                    self.foreground = 0
            elif operation == "close":
                self.windows.remove(target)
        self.after_effect()
        if self.crash:
            raise RuntimeError("Injected loss after delivery")
        return {}
