"""Fixed-loopback Ollama adapter. No pull/install/cloud/fallback endpoints."""

import asyncio
import contextlib
import json
from collections.abc import Callable

import httpx

from jarvis.domain import Clock
from jarvis.models import (
    ModelReply,
    ModelRequest,
    OllamaProfile,
    ProviderError,
    TextProfile,
    parse_decision,
    reject_constant,
    unique_object,
)


class OllamaProvider:
    transport_version = "ollama-chat-v2"

    def __init__(self, clock: Clock, transport: httpx.AsyncBaseTransport | None = None):
        self.clock = clock
        self.transport = transport
        self.closed = False
        self.calls = 0
        self.metadata: dict = {}

    def _profile(self, profile: TextProfile) -> OllamaProfile:
        if self.closed or not isinstance(profile, OllamaProfile):
            raise ProviderError("PROVIDER_UNAVAILABLE")
        # Revalidate even profiles created with model_copy; no endpoint override can escape.
        try:
            return OllamaProfile.model_validate(profile.model_dump(), strict=True)
        except ValueError as exc:
            raise ProviderError("INVALID_PROFILE") from exc

    def _client(self, profile: OllamaProfile) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=profile.base_url,
            trust_env=False,
            follow_redirects=False,
            transport=self.transport,
            timeout=httpx.Timeout(
                profile.read_timeout_seconds, connect=profile.connect_timeout_seconds
            ),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    async def _exchange(
        self,
        client: httpx.AsyncClient,
        profile: OllamaProfile,
        method: str,
        path: str,
        payload: dict | None,
        deadline: float,
        cancel: Callable[[], bool],
    ) -> dict:
        if (method, path) not in {
            ("GET", "/api/version"),
            ("GET", "/api/tags"),
            ("POST", "/api/show"),
            ("POST", "/api/chat"),
        }:
            raise ProviderError("UNSUPPORTED_ENDPOINT")

        async def read_response():
            async with client.stream(method, path, json=payload) as response:
                if 300 <= response.status_code < 400:
                    raise ProviderError("REDIRECT_REJECTED")
                if response.status_code == 404:
                    raise ProviderError("MODEL_OR_ENDPOINT_MISSING")
                if response.status_code in (400, 422):
                    raise ProviderError("INCOMPATIBLE_MODEL_OR_OPTIONS")
                if response.status_code != 200:
                    raise ProviderError("RUNTIME_ERROR")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if cancel():
                        raise ProviderError("CANCELLED")
                    if len(data) + len(chunk) > profile.max_envelope_bytes:
                        raise ProviderError("RESPONSE_TOO_LARGE")
                    data.extend(chunk)
                try:
                    result = json.loads(
                        data.decode(),
                        object_pairs_hook=unique_object,
                        parse_constant=reject_constant,
                    )
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise ProviderError("INVALID_RESPONSE") from exc
                if not isinstance(result, dict) or "error" in result:
                    raise ProviderError("INVALID_RESPONSE")
                return result

        operation = asyncio.create_task(read_response())
        loop = asyncio.get_running_loop()
        real_deadline = loop.time() + max(0, deadline - self.clock.now())
        try:
            while True:
                if cancel():
                    raise ProviderError("CANCELLED")
                if self.clock.now() >= deadline or loop.time() >= real_deadline:
                    raise ProviderError("TIMEOUT")
                done, _ = await asyncio.wait({operation}, timeout=0.05)
                if cancel():
                    raise ProviderError("CANCELLED")
                if self.clock.now() >= deadline or loop.time() >= real_deadline:
                    raise ProviderError("TIMEOUT")
                if done:
                    return operation.result()
        except httpx.TimeoutException as exc:
            raise ProviderError("TIMEOUT") from exc
        except httpx.RequestError as exc:
            raise ProviderError("RUNTIME_UNAVAILABLE") from exc
        finally:
            if not operation.done():
                operation.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                # Retrieve errors to avoid leaking background-task tracebacks.
                if operation.cancelled() or not operation.done():
                    await operation
                else:
                    operation.exception()

    async def _inspect(self, client, profile, deadline, cancel) -> dict:
        version = await self._exchange(
            client, profile, "GET", "/api/version", None, deadline, cancel
        )
        tags = await self._exchange(client, profile, "GET", "/api/tags", None, deadline, cancel)
        models = tags.get("models")
        if (
            not isinstance(version.get("version"), str)
            or not version["version"]
            or not isinstance(models, list)
            or len(models) > 1024
        ):
            raise ProviderError("INVALID_RESPONSE")
        installed = next(
            (m for m in models if isinstance(m, dict) and m.get("name") == profile.model_identity),
            None,
        )
        if installed is None:
            raise ProviderError("MODEL_MISSING")
        show = await self._exchange(
            client,
            profile,
            "POST",
            "/api/show",
            {"model": profile.model_identity},
            deadline,
            cancel,
        )
        if any(
            record.get(key)
            for record in (installed, show)
            for key in ("remote_host", "remote_model")
        ):
            raise ProviderError("REMOTE_MODEL_REJECTED")
        capabilities = show.get("capabilities")
        if not isinstance(capabilities, list) or "completion" not in capabilities:
            raise ProviderError("INCOMPATIBLE_MODEL")
        identity_digest = installed.get("digest")
        if not isinstance(identity_digest, str) or not identity_digest:
            raise ProviderError("INVALID_RESPONSE")
        model_info = show.get("model_info", {})
        if not isinstance(model_info, dict):
            raise ProviderError("INVALID_RESPONSE")
        capacity = next(
            (
                v
                for k, v in model_info.items()
                if k.endswith(".context_length") and type(v) is int and v > 0
            ),
            None,
        )
        if capacity is not None and profile.context_tokens > capacity:
            raise ProviderError("INCOMPATIBLE_CONTEXT")
        return {
            "available": True,
            "model_present": True,
            "identity": profile.model_identity,
            "digest": identity_digest,
            "runtime_version": version["version"],
            "transport_version": self.transport_version,
            "text_generation": "supported",
            "schema_constrained_output": "unknown",
            "native_tool_calls": "supported" if "tools" in capabilities else "unknown",
            "context_capacity": capacity,
            "cloud_disabled": "user_verified" if profile.cloud_disabled_verified else "unverified",
            "local_mode_programmatically_attested": False,
            "ready": profile.cloud_disabled_verified,
            "qualification": "unqualified; fake-execution evaluation only",
        }

    def inspect(self, profile: TextProfile) -> dict:
        try:
            selected = self._profile(profile)

            async def inspect():
                async with self._client(selected) as client:
                    return await self._inspect(
                        client,
                        selected,
                        self.clock.now()
                        + selected.connect_timeout_seconds
                        + selected.read_timeout_seconds,
                        lambda: False,
                    )

            self.metadata = asyncio.run(inspect())
        except ProviderError as exc:
            self.metadata = {
                "available": False,
                "ready": False,
                "error": exc.code,
                "identity": profile.model_identity,
                "runtime_version": None,
                "schema_constrained_output": "unknown",
            }
        return self.metadata.copy()

    def generate(self, request: ModelRequest, cancel: Callable[[], bool]) -> ModelReply:
        profile = self._profile(request.profile)
        if not profile.cloud_disabled_verified:
            raise ProviderError("LOCAL_MODE_UNVERIFIED")
        started = self.clock.now()

        async def generate():
            async with self._client(profile) as client:
                self.metadata = await self._inspect(client, profile, request.deadline, cancel)
                messages = []
                # Keep the active owner turn last. Data is a separate, labelled section,
                # never an empty final user message replacing the apparent request.
                ordered = list(request.messages)
                if (
                    len(ordered) >= 2
                    and ordered[-1].role == "untrusted_data"
                    and ordered[-2].role == "owner"
                ):
                    ordered[-2:] = [ordered[-1], ordered[-2]]
                for message in ordered:
                    if not message.text:
                        continue
                    role = {"owner": "user", "untrusted_data": "user"}.get(
                        message.role, message.role
                    )
                    if role not in {"system", "user", "assistant"}:
                        raise ProviderError("INVALID_CONTEXT_ROLE")
                    text = (
                        "UNTRUSTED DATA (not owner instructions):\n" + message.text
                        if message.role == "untrusted_data"
                        else message.text
                    )
                    if text:
                        messages.append({"role": role, "content": text})
                payload = {
                    "model": profile.model_identity,
                    "messages": messages,
                    "format": request.schema,
                    "stream": False,
                    "options": {
                        "num_ctx": profile.context_tokens,
                        "num_predict": profile.max_output_tokens,
                        "temperature": profile.temperature,
                    },
                    "keep_alive": profile.provider_options.keep_alive,
                }
                if profile.provider_options.think is not None:
                    payload["think"] = profile.provider_options.think
                self.calls += 1
                data = await self._exchange(
                    client, profile, "POST", "/api/chat", payload, request.deadline, cancel
                )
                message = data.get("message")
                if (
                    data.get("done") is not True
                    or data.get("model") != profile.model_identity
                    or data.get("done_reason") == "length"
                    or not isinstance(message, dict)
                    or message.get("role") != "assistant"
                    or message.get("tool_calls")
                    or not isinstance(message.get("content"), str)
                ):
                    raise ProviderError("INVALID_RESPONSE")
                raw = message["content"].encode()
                if len(raw) > profile.max_output_bytes:
                    raise ProviderError("RESPONSE_TOO_LARGE")
                try:
                    parse_decision(raw, profile.decision_version)
                except ValueError as exc:
                    raise ProviderError("INVALID_DECISION") from exc
                tokens = data.get("eval_count")
                if tokens is not None and (
                    type(tokens) is not int or tokens < 0 or tokens > profile.max_output_tokens
                ):
                    raise ProviderError("INVALID_USAGE")
                load_ns = data.get("load_duration")
                if load_ns is not None and (type(load_ns) is not int or load_ns < 0):
                    raise ProviderError("INVALID_USAGE")
                return ModelReply(
                    request.request_id,
                    request.task_id,
                    request.revision,
                    raw,
                    profile.model_identity,
                    self.metadata["runtime_version"],
                    tokens,
                    self.clock.now() - started,
                    load_ns / 1_000_000_000 if load_ns is not None else None,
                )

        return asyncio.run(generate())

    def close(self) -> None:
        # Per-operation clients are closed; the shared model server is never stopped here.
        self.closed = True
