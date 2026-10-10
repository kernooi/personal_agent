"""Short SQLite transactions. No database transaction performs an external effect."""

import json
import sqlite3
from dataclasses import MISSING, asdict, fields
from pathlib import Path
from uuid import uuid4

from pydantic import TypeAdapter

from jarvis.domain import (
    TRANSITIONS,
    Approval,
    Clock,
    Denied,
    Evidence,
    ExecutionAttempt,
    PreparedAction,
    Scope,
    State,
    Task,
    TaskResult,
)
from jarvis.models import reject_constant, unique_object

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
 task_id TEXT PRIMARY KEY, request_key TEXT NOT NULL, session TEXT NOT NULL,
 request_fingerprint TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision >= 1),
 state TEXT NOT NULL, scope_json TEXT NOT NULL, deadline REAL NOT NULL,
 cancelled INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '',
 profile_json TEXT NOT NULL,
 created_at REAL NOT NULL, updated_at REAL NOT NULL, UNIQUE(session, request_key)
);
CREATE TABLE IF NOT EXISTS actions (
 action_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
 task_revision INTEGER NOT NULL, logical_step_key TEXT NOT NULL,
 capability TEXT NOT NULL, prepared_digest TEXT NOT NULL, prepared_json TEXT NOT NULL,
 state TEXT NOT NULL, authorization_ref TEXT NOT NULL,
 UNIQUE(task_id, task_revision, logical_step_key)
);
CREATE TABLE IF NOT EXISTS attempts (
 attempt_id TEXT PRIMARY KEY, action_id TEXT NOT NULL UNIQUE REFERENCES actions(action_id),
 attempt_number INTEGER NOT NULL CHECK(attempt_number = 1), status TEXT NOT NULL,
 admitted_at REAL NOT NULL, completed_at REAL, evidence_json TEXT
);
CREATE TABLE IF NOT EXISTS events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT REFERENCES tasks(task_id),
 action_id TEXT REFERENCES actions(action_id), kind TEXT NOT NULL, created_at REAL NOT NULL,
 redacted_payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consumed_approvals (
 approval_id TEXT PRIMARY KEY, action_id TEXT NOT NULL REFERENCES actions(action_id)
);
"""


def encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Store:
    def __init__(self, path: Path, clock: Clock):
        self.clock = clock
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1):
            self.db.close()
            raise ValueError("Unsupported journal schema; no automatic migration")
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA user_version=1")
        self.db.commit()

    def event(
        self, task_id: str, kind: str, action_id: str | None = None, payload: dict | None = None
    ) -> None:
        self.db.execute(
            "INSERT INTO events(task_id,action_id,kind,created_at,"
            "redacted_payload_json) VALUES(?,?,?,?,?)",
            (task_id, action_id, kind, self.clock.now(), encode(payload or {})),
        )

    def accept(
        self,
        key: str,
        scope: Scope,
        fingerprint: str,
        deadline: float,
        profile_snapshot: dict | None = None,
    ) -> tuple[Task, bool]:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT * FROM tasks WHERE session=? AND request_key=?", (scope.session, key)
            ).fetchone()
            if row:
                if (
                    row["request_fingerprint"] != fingerprint
                    or self.get(row["task_id"]).scope != scope
                ):
                    raise Denied("Request key reused for different instruction")
                self.event(row["task_id"], "duplicate_delivery")
                return self.get(row["task_id"]), False
            task_id = str(uuid4())
            now = self.clock.now()
            self.db.execute(
                "INSERT INTO tasks(task_id,request_key,session,request_fingerprint,"
                "revision,state,scope_json,deadline,profile_json,created_at,updated_at) "
                "VALUES(?,?,?,?,1,?,?,?,?,?,?)",
                (
                    task_id,
                    key,
                    scope.session,
                    fingerprint,
                    State.RECEIVED,
                    encode(asdict(scope)),
                    deadline,
                    encode(profile_snapshot or {}),
                    now,
                    now,
                ),
            )
            self.event(task_id, "request_accepted")
        return self.get(task_id), True

    def get(self, task_id: str) -> Task:
        row = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise Denied("Unknown task")
        payload = json.loads(
            row["scope_json"], object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        if (
            set(payload)
            not in ({"session", "app_id", "effect"}, {"session", "app_id", "effect", "window_ref"})
            or not all(
                isinstance(payload[x], str) and payload[x] for x in ("session", "app_id", "effect")
            )
            or payload["effect"]
            not in (
                {"web_public_read", "web_evidence"}
                if payload["app_id"] == "web"
                else {"public_read", "local_calculate", "read_evidence"}
                if payload["app_id"] == "currency"
                else {"open", "focus", "close"}
            )
            or not isinstance(payload.get("window_ref", ""), str)
            or row["revision"] < 1
        ):
            raise Denied("Corrupt task scope")
        if payload["app_id"] == "currency":
            from jarvis.public_data import CurrencyArguments, canonical

            arguments = CurrencyArguments.model_validate_json(payload.get("window_ref", ""))
            if canonical(arguments) != payload["window_ref"]:
                raise Denied("Corrupt currency argument binding")
        if payload["app_id"] == "web":
            from jarvis.web_data import WebArguments, canonical

            arguments = WebArguments.model_validate_json(payload.get("window_ref", ""))
            if canonical(arguments) != payload["window_ref"]:
                raise Denied("Corrupt research argument binding")
        return Task(
            task_id,
            row["revision"],
            State(row["state"]),
            Scope(**payload),
            row["deadline"],
            bool(row["cancelled"]),
        )

    def _transition(self, task_id: str, target: State, message: str = "") -> None:
        current = self.get(task_id)
        if target not in TRANSITIONS.get(current.state, set()):
            raise Denied(f"Invalid state transition {current.state} -> {target}")
        self.db.execute(
            "UPDATE tasks SET state=?,message=?,updated_at=? WHERE task_id=?",
            (target, message, self.clock.now(), task_id),
        )
        self.event(task_id, "state_changed", payload={"from": current.state, "to": target})

    def transition(self, task_id: str, target: State, message: str = "") -> None:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._transition(task_id, target, message)

    def revise(self, task_id: str) -> None:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            task = self.get(task_id)
            if task.state not in (State.PLANNING, State.READY):
                raise Denied("Task cannot be revised now")
            self.db.execute("UPDATE tasks SET revision=revision+1 WHERE task_id=?", (task_id,))
            self.event(task_id, "revision_changed")

    def cancel(self, task_id: str) -> None:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            task = self.get(task_id)
            if task.cancelled or task.state not in TRANSITIONS:
                return
            self.db.execute(
                "UPDATE tasks SET cancelled=1,revision=revision+1 WHERE task_id=?", (task_id,)
            )
            self.event(task_id, "cancel_acknowledged")
            if task.state not in (State.RUNNING, State.VERIFYING):
                self._transition(
                    task_id,
                    State.CANCELLED,
                    "SIMULATED: cancelled before execution; no effect admitted.",
                )

    def gate(self, action: PreparedAction) -> None:
        task = self.get(action.task_id)
        if task.cancelled or task.revision != action.revision or self.clock.now() >= task.deadline:
            raise Denied("Cancellation, revision, or deadline gate closed")

    def intent(self, action: PreparedAction, authorization_ref: str) -> str:
        action_id = str(uuid4())
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.gate(action)
            if self.get(action.task_id).state != State.READY:
                raise Denied("Task not ready")
            self.db.execute(
                "INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    action_id,
                    action.task_id,
                    action.revision,
                    "open-editor-v1"
                    if action.adapter_version == "fake-desktop-v1"
                    else "currency-read-v1"
                    if action.adapter_version == "currency-adapter-v1"
                    else "notepad-" + action.effects[0] + "-v1",
                    action.capability,
                    action.digest,
                    encode(asdict(action)),
                    "INTENT_RECORDED",
                    authorization_ref,
                ),
            )
            self.event(
                action.task_id,
                "intent_recorded",
                action_id,
                {"digest": action.digest, "policy": action.policy_version},
            )
        return action_id

    def admit(
        self, action_id: str, action: PreparedAction, approval: Approval | None
    ) -> ExecutionAttempt:
        attempt_id = str(uuid4())
        admitted_at = self.clock.now()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.gate(action)
            row = self.db.execute(
                "SELECT * FROM actions WHERE action_id=?", (action_id,)
            ).fetchone()
            if (
                row is None
                or row["state"] != "INTENT_RECORDED"
                or row["prepared_json"] != encode(asdict(action))
            ):
                raise Denied("Duplicate or changed dispatch")
            if approval:
                try:
                    self.db.execute(
                        "INSERT INTO consumed_approvals VALUES(?,?)",
                        (approval.approval_id, action_id),
                    )
                except sqlite3.IntegrityError as exc:
                    raise Denied("Approval already consumed") from exc
            self.db.execute(
                "INSERT INTO attempts VALUES(?,?,1,'ADMITTED',?,NULL,NULL)",
                (attempt_id, action_id, admitted_at),
            )
            self.db.execute(
                "UPDATE actions SET state='DISPATCHING' WHERE action_id=?", (action_id,)
            )
            self._transition(action.task_id, State.RUNNING)
            self.event(action.task_id, "dispatch_admitted", action_id)
        return ExecutionAttempt(attempt_id, action_id, 1, admitted_at)

    def complete(
        self, action_id: str, status: str, evidence: Evidence | None, state: State, message: str
    ) -> None:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute(
                "SELECT task_id,state FROM actions WHERE action_id=?", (action_id,)
            ).fetchone()
            if (
                row is None
                or row["state"] != "DISPATCHING"
                or status not in {"VERIFIED", "FAILED", "UNKNOWN"}
            ):
                raise Denied("Invalid action outcome transition")
            task_id = row["task_id"]
            self.db.execute("UPDATE actions SET state=? WHERE action_id=?", (status, action_id))
            self.db.execute(
                "UPDATE attempts SET status=?,completed_at=?,evidence_json=? WHERE action_id=?",
                (
                    status,
                    self.clock.now(),
                    encode(asdict(evidence)) if evidence else None,
                    action_id,
                ),
            )
            self._transition(task_id, state, message)
            self.event(task_id, "action_outcome", action_id, {"status": status})

    def result(self, task_id: str) -> TaskResult:
        task = self.get(task_id)
        row = self.db.execute("SELECT message FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if task.state == State.SUCCEEDED:
            outcome = self.db.execute(
                "SELECT a.prepared_json,p.evidence_json FROM actions a JOIN attempts p "
                "ON a.action_id=p.action_id WHERE a.task_id=? AND a.state='VERIFIED'",
                (task_id,),
            ).fetchone()
            if outcome is None:
                raise Denied("Success has no durable evidence")
            action = self.load_action(outcome["prepared_json"])
            evidence = self.load_record(outcome["evidence_json"], Evidence)
            if (
                (
                    evidence.postcondition
                    if action.adapter_version
                    in {
                        "notepad-windows-v1",
                        "notepad-fake-v1",
                        "currency-adapter-v1",
                        "web-adapter-v1",
                    }
                    else evidence.running
                )
                is not True
                or evidence.target_identity != action.target_identity
                or evidence.session != task.scope.session
            ):
                raise Denied("Stored success evidence is invalid")
            if action.adapter_version == "currency-adapter-v1":
                if (
                    evidence.source != "currency-record-validator-v1"
                    or evidence.kind != "validated_public_quote"
                    or evidence.authority != "tool_output"
                ):
                    raise Denied("Stored currency evidence authority is invalid")
            if action.adapter_version == "web-adapter-v1":
                from jarvis.web_data import Source
                from jarvis.web_decisions import ResearchAnswer, validate_answer

                if (
                    evidence.source != "web-excerpt-validator-v1"
                    or evidence.kind != "validated_public_research"
                    or evidence.authority != "tool_output"
                ):
                    raise Denied("Stored web evidence authority is invalid")
                record = json.loads(
                    evidence.observed_identity,
                    object_pairs_hook=unique_object,
                    parse_constant=reject_constant,
                )
                sources = tuple(
                    Source.model_validate_json(json.dumps(s)) for s in record["sources"]
                )
                from jarvis.web_data import WebArguments

                args = WebArguments.model_validate_json(action.window_ref)
                if not sources or any(s.query_hash != args.query_hash for s in sources):
                    raise Denied("Stored source relationship differs from owner task")
                if args.operation != "sources" and record["answer"] is None:
                    raise Denied("Stored research success has no grounded answer")
                if record["answer"] is not None:
                    validate_answer(ResearchAnswer.model_validate(record["answer"]), sources)
        return TaskResult(
            task_id,
            task.state,
            row["message"] or "SIMULATED: task in progress; completion is unverified.",
        )

    def close(self) -> None:
        self.db.close()

    def load_action(self, raw: str) -> PreparedAction:
        return self.load_record(raw, PreparedAction)

    def load_record(self, raw: str, record_type):
        payload = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        names = {f.name for f in fields(record_type)}
        required = {
            f.name
            for f in fields(record_type)
            if f.default is MISSING and f.default_factory is MISSING
        }
        if not isinstance(payload, dict) or not required <= set(payload) <= names:
            raise Denied("Invalid stored record fields")
        return TypeAdapter(record_type).validate_json(raw, strict=True)
