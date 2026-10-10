"""One fixed public lookup per disposable process; no prompts, amounts or OS effects."""

import base64
import json
import os
import sys
import threading

from jarvis.public_data import METADATA_URL, PublicConfig, PublicDataError
from jarvis.public_transport import fetch, fetch_url


def main():
    watchdog = None
    try:
        raw = sys.stdin.buffer.readline(4097)
        if len(raw) > 4096:
            raise PublicDataError("INVALID_REQUEST")
        request = json.loads(raw)
        metadata = set(request) == {"metadata", "config"} and request.get("metadata") is True
        if not metadata and set(request) != {"base", "quote", "config"}:
            raise PublicDataError("INVALID_REQUEST")
        config = PublicConfig.model_validate(request["config"], strict=True)
        if config.mode != "enabled":
            raise PublicDataError("NETWORK_DISABLED")
        # Also bound DNS if the supervising chat process crashes or disappears.
        watchdog = threading.Timer(config.timeout_seconds, lambda: os._exit(124))
        watchdog.daemon = True
        watchdog.start()
        body, receipt = (
            fetch_url(METADATA_URL, config)
            if metadata
            else fetch(request["base"], request["quote"], config)
        )
        result = {"body": base64.b64encode(body).decode(), "receipt": receipt}
    except PublicDataError as exc:
        result = {"error": exc.code}
    except Exception:
        result = {"error": "INVALID_REQUEST_OR_TRANSPORT_FAILURE"}
    finally:
        if watchdog:
            watchdog.cancel()
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
