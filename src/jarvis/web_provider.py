"""Replaceable SearXNG API adapter and separate supervised public page fetcher."""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from uuid import uuid4

from jarvis.models import reject_constant, unique_object
from jarvis.web_data import SearchResult, WebError, public_url, stamp
from jarvis.web_extract import clean, page_date

_ACTIVE = threading.BoundedSemaphore(1)


def supervised(request, config, cancel, deadline):
    if not config.enabled:
        raise WebError("WEB_DISABLED")
    if cancel() or time.time() >= deadline:
        raise WebError("CANCELLED_OR_EXPIRED")
    if not _ACTIVE.acquire(blocking=False):
        raise WebError("CONCURRENCY_LIMIT")
    process = None
    try:
        until = time.monotonic() + min(config.timeout_seconds, max(0, deadline - time.time()))
        process = subprocess.Popen(
            [sys.executable, "-m", "jarvis.web_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        output = queue.Queue(maxsize=1)
        limit = config.max_response_bytes * 6 + 65536
        reader = threading.Thread(
            target=lambda: output.put(process.stdout.readline(limit + 1)), daemon=True
        )
        reader.start()
        process.stdin.write(json.dumps({**request, "config": config.model_dump()}).encode() + b"\n")
        process.stdin.flush()
        while True:
            if cancel():
                raise WebError("CANCELLED")
            if time.monotonic() >= until:
                raise WebError("TIMEOUT")
            try:
                raw = output.get(timeout=0.02)
                break
            except queue.Empty:
                continue
        if not raw or len(raw) > limit:
            raise WebError("INVALID_WORKER_RESPONSE")
        result = json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant)
        if "error" in result:
            count = result.get("downloaded_bytes")
            if count is not None and (
                type(count) is not int or not 0 <= count <= config.max_response_bytes
            ):
                raise WebError("INVALID_WORKER_RESPONSE")
            raise WebError(result["error"], downloaded_bytes=count)
        if cancel() or time.time() >= deadline:
            raise WebError("CANCELLED_OR_EXPIRED")
        return result
    finally:
        if process is not None:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
            process.stdin.close()
            process.stdout.close()
        _ACTIVE.release()


def normalize_search(payload, request, now, provider="searxng"):
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("results"), list)
        or len(payload["results"]) > 256
    ):
        raise WebError("INVALID_SEARCH_RESPONSE")
    results, seen = [], set()
    for rank, item in enumerate(payload["results"], 1):
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("title"), str)
            or not isinstance(item.get("url"), str)
        ):
            raise WebError("INVALID_SEARCH_RESULT")
        try:
            url = public_url(item["url"].split("#", 1)[0])
        except ValueError:
            continue
        domain = urlsplit(url).hostname
        if request.domains and not any(
            domain == d or domain.endswith("." + d) for d in request.domains
        ):
            continue  # Engine site: support is not assumed; enforce the filter locally.
        if url in seen:
            continue
        seen.add(url)
        results.append(
            SearchResult(
                result_id="result_" + uuid4().hex,
                provider=provider,
                title=clean(item["title"], 200),
                url=url,
                domain=domain,
                snippet=clean(item.get("content", ""), 500)
                if isinstance(item.get("content", ""), str)
                else "",
                published_at=page_date(item.get("publishedDate")),
                retrieved_at=stamp(now),
                rank=rank,
            )
        )
        if len(results) == request.result_limit:
            break
    return tuple(results)


class SearXNGProvider:
    name = "searxng"

    def __init__(self, worker=supervised):
        self.worker = worker
        self.last_receipt = None

    def search(self, request, config, cancel, deadline):
        if config.provider != self.name:
            raise WebError("SEARCH_PROVIDER_NOT_CONFIGURED")
        value = self.worker({"search": request.model_dump()}, config, cancel, deadline)
        if set(value) != {"search_response", "receipt"}:
            raise WebError("INVALID_WORKER_RESPONSE")
        self.last_receipt = value["receipt"]
        return normalize_search(value["search_response"], request, time.time(), self.name)


class PublicPageFetcher:
    def __init__(self, worker=supervised):
        self.worker = worker

    def fetch(self, url, config, cancel, deadline):
        public_url(url)
        value = self.worker({"url": url}, config, cancel, deadline)
        if set(value) != {"document", "receipt"}:
            raise WebError("INVALID_WORKER_RESPONSE")
        return value["document"], value["receipt"]
