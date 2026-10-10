"""Replaceable provider protocol and supervised public-only network worker."""

import base64
import json
import os
import queue
import subprocess
import sys
import threading
import time
from typing import Protocol

from jarvis.public_data import SOURCE, PublicDataError


class CurrencyProvider(Protocol):
    def fetch(self, base, quote, config, cancel, deadline): ...
    def supported_currencies(self, config, cancel, deadline): ...


class FrankfurterProvider:
    _active = threading.BoundedSemaphore(1)

    def __init__(self):
        self.last_receipt = None

    def fetch(self, base, quote, config, cancel, deadline):
        return self._request({"base": base, "quote": quote}, config, cancel, deadline)

    def supported_currencies(self, config, cancel, deadline):
        return self._request({"metadata": True}, config, cancel, deadline)

    def _request(self, request, config, cancel, deadline):
        if cancel():
            raise PublicDataError("CANCELLED")
        if config.mode != "enabled":
            raise PublicDataError("NETWORK_DISABLED")
        if deadline <= time.time():
            raise PublicDataError("TIMEOUT")
        if not self._active.acquire(blocking=False):
            raise PublicDataError("CONCURRENCY_LIMIT")
        try:
            return self._fetch(request, config, cancel, deadline)
        finally:
            self._active.release()

    def _fetch(self, request, config, cancel, deadline):
        until = min(
            time.monotonic() + config.timeout_seconds,
            time.monotonic() + max(0, deadline - time.time()),
        )
        process = subprocess.Popen(
            [sys.executable, "-m", "jarvis.public_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        outputs = queue.Queue(maxsize=1)

        def read():
            outputs.put(process.stdout.readline(65537))

        reader = threading.Thread(target=read, daemon=True)
        try:
            reader.start()
            # Only pair and reviewed policy reach the worker. No amount or prompt.
            process.stdin.write(
                json.dumps({**request, "config": config.model_dump()}).encode() + b"\n"
            )
            process.stdin.flush()
            while True:
                if cancel():
                    raise PublicDataError("CANCELLED")
                if time.monotonic() >= until:
                    raise PublicDataError("TIMEOUT")
                try:
                    raw = outputs.get(timeout=0.02)
                    break
                except queue.Empty:
                    continue
            if not raw or len(raw) > 65536:
                if process.poll() == 124:
                    raise PublicDataError("TIMEOUT")
                raise PublicDataError("INVALID_WORKER_RESPONSE")
            result = json.loads(raw)
            if "error" in result:
                raise PublicDataError(result["error"])
            if set(result) != {"body", "receipt"}:
                raise PublicDataError("INVALID_WORKER_RESPONSE")
            body = base64.b64decode(result["body"], validate=True)
            if len(body) > config.max_response_bytes:
                raise PublicDataError("OVERSIZED_PAYLOAD")
            self.last_receipt = result["receipt"]
            return body
        finally:
            if process.poll() is None:
                process.terminate()  # The owned fetch worker only, never Notepad or Ollama.
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()  # Escalation is confined to this owned fetch worker.
                process.wait(timeout=1)
            for stream in (process.stdin, process.stdout):
                stream.close()
            reader.join(timeout=1)


class FixtureProvider:
    """Explicit synthetic provider, never an automatic fallback."""

    def __init__(self, raw, currencies=("MYR", "JPY", "USD", "SGD", "EUR", "GBP", "AUD")):
        self.raw = raw
        self.calls = []
        self.last_receipt = {"synthetic": True}
        self.currencies = currencies
        self.metadata_calls = 0

    def supported_currencies(self, config, cancel, deadline):
        if config.mode != "fixture":
            raise PublicDataError("FIXTURE_MODE_REQUIRED")
        if cancel():
            raise PublicDataError("CANCELLED")
        self.metadata_calls += 1
        return json.dumps(
            {
                "key": "ECB",
                "name": "European Central Bank",
                "rate_type": "reference rate",
                "pivot_currency": "EUR",
                "data_url": SOURCE,
                "currencies": list(self.currencies),
                "unknown_currencies": [],
            }
        ).encode()

    def fetch(self, base, quote, config, cancel, deadline):
        if config.mode != "fixture":
            raise PublicDataError("FIXTURE_MODE_REQUIRED")
        if cancel():
            raise PublicDataError("CANCELLED")
        self.calls.append((base, quote))
        return self.raw(base, quote) if callable(self.raw) else self.raw
