"""Owned disposable network/extraction worker. Never a shell or model tool."""

import json
import os
import sys
import threading

from jarvis.models import reject_constant, unique_object
from jarvis.web_data import SearchRequest, WebConfig, WebError
from jarvis.web_extract import extract
from jarvis.web_transport import fetch_page, search_api


def main():
    timer = None
    receipt = None
    try:
        raw = sys.stdin.buffer.readline(8193)
        if len(raw) > 8192:
            raise WebError("WORKER_REQUEST_LIMIT")
        request = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        config = WebConfig.model_validate(request["config"])
        if not config.enabled:
            raise WebError("WEB_DISABLED")
        from jarvis.web_limits import limit_worker_memory

        limit_worker_memory()
        timer = threading.Timer(config.timeout_seconds, lambda: os._exit(124))
        timer.daemon = True
        timer.start()
        if set(request) == {"search", "config"}:
            body, receipt = search_api(
                SearchRequest.model_validate_json(json.dumps(request["search"])), config
            )
            result = {
                "search_response": json.loads(
                    body, object_pairs_hook=unique_object, parse_constant=reject_constant
                ),
                "receipt": receipt,
            }
        elif set(request) == {"url", "config"}:
            body, receipt = fetch_page(request["url"], config)
            result = {"document": extract(body, receipt, config), "receipt": receipt}
        else:
            raise WebError("INVALID_WORKER_REQUEST")
    except WebError as exc:
        result = {"error": exc.code}
        count = exc.downloaded_bytes
        # A completed fetch remains measured even when text extraction fails.
        # Unknown/incomplete network operations still provide no refund receipt.
        if count is None and receipt is not None:
            count = receipt.get("downloaded_bytes")
        if count is not None:
            result["downloaded_bytes"] = count
    except Exception:
        result = {"error": "NETWORK_OR_EXTRACTION_FAILURE"}
    finally:
        if timer:
            timer.cancel()
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
