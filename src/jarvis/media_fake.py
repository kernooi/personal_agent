"""Stateful test-only browser. Never launches an application or performs networking."""

from uuid import uuid4

from jarvis.domain import AdmissionRejected
from jarvis.media_data import MediaItem, MediaObservation


class FakeBrowserProvider:
    real = False
    spotify_ready = True

    def __init__(self, clock):
        self.clock = clock
        self.states = {}
        self.calls = []
        self.results = {}
        self.before_execute = lambda: None
        self.after_execute = lambda: None
        self.override_observation = None
        self.restriction = None
        self.closed = False
        self.execution_count = 0
        self.catalog = [
            ("dQw4w9WgXcQ", "Never Gonna Give You Up", "Rick Astley"),
            ("aaaaaaaaaaa", "Synthetic other result", "Test channel"),
        ]

    def call(self, request, cancel):
        self.calls.append(request.command)
        args = request.arguments
        if cancel():
            raise AdmissionRejected("Stopped before fake browser effect")
        observed = self.states.get(args.service) or MediaObservation(
            session_ref=args.session_ref,
            service=args.service,
            generation=0,
            observed_at=float(self.clock.now()),
            state="ready",
        )
        if request.command == "execute":
            self.before_execute()
            if cancel() or args.generation != observed.generation:
                raise AdmissionRejected("Stale browser generation or stop")
            self.execution_count += 1
            update = {"generation": observed.generation + 1, "observed_at": float(self.clock.now())}
            if args.operation == "search":
                results = [
                    MediaItem(
                        reference="media_" + uuid4().hex, item_id=id, title=title, creator=creator
                    )
                    for id, title, creator in self.catalog[:5]
                ]
                self.results = {r.reference: r for r in results}
                update.update(state="results", results=results, item_id="", title="")
            elif args.operation == "open":
                if args.reference not in self.results:
                    raise AdmissionRejected("Stale result reference")
                result = self.results[args.reference]
                update.update(
                    state="opened", item_id=result.item_id, title=result.title, results=[]
                )
            elif args.operation in {"play", "pause", "resume"}:
                update["state"] = self.restriction or (
                    "paused" if args.operation == "pause" else "playing"
                )
                if args.backend == "windows":
                    update.update(
                        item_id="synthetic-track",
                        title="Synthetic track",
                        device_ref="device_" + "1" * 32,
                    )
            elif args.operation in {"next", "previous"}:
                update.update(
                    item_id="synthetic-changed-track",
                    title="Synthetic changed track",
                    state="playing",
                    device_ref="device_" + "1" * 32,
                )
            elif args.operation == "login":
                update["state"] = "login_required"
            observed = observed.model_copy(update=update)
            self.states[args.service] = observed
            self.after_execute()
        if request.command == "observe" and self.override_observation:
            return self.override_observation(observed)
        return observed

    def close(self):
        self.closed = True
