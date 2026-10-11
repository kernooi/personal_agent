"""Official Spotify API only. Credentials never leave this worker-layer module."""

import ctypes
import json
import os
import re
import time
from ctypes import wintypes
from uuid import uuid4

import httpcore
import httpx

from jarvis.media_data import MediaError, MediaItem, MediaObservation, PlaybackDevice
from jarvis.models import reject_constant, unique_object
from jarvis.web_transport import PublicBackend

SCOPES = frozenset(
    {"user-read-playback-state", "user-read-currently-playing", "user-modify-playback-state"}
)
CREDENTIAL_NAME = "Jarvis/M4/Spotify"


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def credential_api():
    if os.name != "nt":
        raise MediaError("WINDOWS_CREDENTIAL_STORE_REQUIRED")
    api = ctypes.WinDLL("Advapi32", use_last_error=True)
    api.CredReadW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(Credential)),
    ]
    api.CredReadW.restype = wintypes.BOOL
    api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    api.CredWriteW.restype = wintypes.BOOL
    api.CredFree.argtypes = [ctypes.c_void_p]
    return api


def read_token():
    api = credential_api()
    pointer = ctypes.POINTER(Credential)()
    if not api.CredReadW(CREDENTIAL_NAME, 1, 0, ctypes.byref(pointer)):
        raise MediaError("SPOTIFY_OAUTH_SETUP_REQUIRED")
    try:
        blob = pointer.contents
        if blob.CredentialBlobSize > 2400:
            raise MediaError("SPOTIFY_CREDENTIAL_INVALID")
        return json.loads(
            ctypes.string_at(blob.CredentialBlob, blob.CredentialBlobSize).decode(),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    finally:
        api.CredFree(pointer)


def store_token(token, scopes, expires_at):
    if not re.fullmatch(r"[A-Za-z0-9._~-]{20,2000}", token) or not SCOPES <= set(scopes):
        raise MediaError("SPOTIFY_TOKEN_OR_SCOPES_INVALID")
    if not time.time() < expires_at <= time.time() + 3600:
        raise MediaError("SPOTIFY_EXPIRY_INVALID")
    raw = json.dumps(
        {"access_token": token, "scopes": sorted(scopes), "expires_at": expires_at}
    ).encode()
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    record = Credential(
        Type=1,
        TargetName=CREDENTIAL_NAME,
        CredentialBlobSize=len(raw),
        CredentialBlob=buffer,
        Persist=2,
        UserName="JARVIS authorized Spotify access",
    )
    if not credential_api().CredWriteW(ctypes.byref(record), 0):
        raise MediaError("SPOTIFY_CREDENTIAL_WRITE_FAILED")


def credential_ready():
    try:
        data = read_token()
        return data["expires_at"] > time.time() and SCOPES <= set(data["scopes"])
    except (OSError, ValueError, KeyError, TypeError):
        return False


class SpotifyAPI:
    def __init__(self, token_reader=read_token, *, transport=None, clock=time.time):
        self.token_reader, self.transport, self.clock = token_reader, transport, clock
        self.results = []
        self.devices = {}
        self.device_refs = {}
        self.selected = None
        self.generation = 0
        self.session_ref = None
        self.admitted = False
        self.last_query = ""
        self.limit = 5

    def request(self, method, path, *, params=None, body=None, gate=lambda: None):
        allowed = (method, path) in {
            ("GET", "/search"),
            ("GET", "/me/player/devices"),
            ("GET", "/me/player"),
            ("PUT", "/me/player/play"),
            ("PUT", "/me/player/pause"),
        } or (method == "GET" and re.fullmatch(r"/tracks/[A-Za-z0-9]{22}", path))
        if not allowed:
            raise MediaError("SPOTIFY_ENDPOINT_DENIED")
        data = self.token_reader()
        if data.get("expires_at", 0) <= self.clock():
            raise MediaError("SPOTIFY_TOKEN_EXPIRED_REAUTHORIZE_MANUALLY")
        if not SCOPES <= set(data.get("scopes", [])):
            raise MediaError("SPOTIFY_REQUIRED_SCOPES_MISSING")
        token = data.get("access_token")
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._~-]{20,2000}", token):
            raise MediaError("SPOTIFY_CREDENTIAL_INVALID")
        transport = self.transport
        if transport is None:
            if httpx.__version__ != "0.28.1" or httpcore.__version__ != "1.0.9":
                raise MediaError("SPOTIFY_TRANSPORT_UNREVIEWED")
            transport = httpx.HTTPTransport(verify=True, trust_env=False, retries=0)
            transport._pool._network_backend = PublicBackend("api.spotify.com")
        gate()
        with httpx.Client(
            transport=transport, trust_env=False, follow_redirects=False, timeout=5
        ) as client:
            with client.stream(
                method,
                "https://api.spotify.com/v1" + path,
                params=params,
                json=body,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            ) as response:
                codes = {
                    401: "SPOTIFY_AUTHORIZATION_EXPIRED_OR_REVOKED",
                    403: "SPOTIFY_ACCOUNT_OR_SCOPE_RESTRICTED",
                    404: "SPOTIFY_TARGET_OR_DEVICE_UNAVAILABLE",
                    429: "SPOTIFY_RATE_LIMITED",
                }
                if response.status_code in codes:
                    raise MediaError(codes[response.status_code])
                if response.status_code == 204:
                    return None
                if response.status_code != 200:
                    raise MediaError("SPOTIFY_SERVICE_UNAVAILABLE")
                if (
                    response.headers.get("content-type", "").split(";")[0] != "application/json"
                    or response.headers.get("content-encoding", "identity") != "identity"
                ):
                    raise MediaError("SPOTIFY_INVALID_RESPONSE_TYPE")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 65536:
                        raise MediaError("SPOTIFY_RESPONSE_LIMIT")
                return json.loads(
                    raw, object_pairs_hook=unique_object, parse_constant=reject_constant
                )

    def track(self, item, reference=None):
        identity = item.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9]{22}", identity):
            raise MediaError("SPOTIFY_TRACK_IDENTITY_INVALID")
        return MediaItem(
            reference=reference or "media_" + uuid4().hex,
            item_id=identity,
            title=item["name"][:240],
            creator=", ".join(a["name"] for a in item.get("artists", [])[:4])[:160],
        )

    def observe(self, args, gate=lambda: None):
        data = self.request("GET", "/me/player", gate=gate)
        if not data:
            return MediaObservation(
                session_ref=args.session_ref,
                service="spotify",
                generation=self.generation,
                observed_at=float(self.clock()),
                state="ready",
            )
        track = data.get("item")
        device = data.get("device", {})
        item = self.track(track) if track and track.get("type") == "track" else None
        ref = self.device_refs.get(device.get("id"), "")
        return MediaObservation(
            session_ref=args.session_ref,
            service="spotify",
            generation=self.generation,
            observed_at=float(self.clock()),
            state="playing" if data.get("is_playing") is True else "paused",
            item_id=item.item_id if item else "",
            title=item.title if item else "",
            creator=item.creator if item else "",
            device_ref=ref,
            progress_ms=data.get("progress_ms"),
            authenticated=True,
        )

    def handle(self, request):
        self.admitted = False
        self.limit = request.result_limit
        args = request.arguments
        if args.backend != "api":
            raise MediaError("SPOTIFY_BACKEND_MISMATCH")
        if self.session_ref not in {None, args.session_ref}:
            raise MediaError("SPOTIFY_SESSION_CHANGED")
        self.session_ref = args.session_ref

        def gate():
            if self.clock() >= request.deadline:
                raise MediaError("SPOTIFY_DEADLINE")

        gate()
        if request.command != "execute":
            if args.operation == "search":
                data = self.request(
                    "GET",
                    "/search",
                    params={"q": self.last_query, "type": "track", "limit": self.limit},
                    gate=gate,
                )
                live = [self.track(item) for item in data["tracks"]["items"][: self.limit]]
                matched = [(i.item_id, i.title) for i in live] == [
                    (i.item_id, i.title) for i in self.results
                ]
                return self.last_observation.model_copy(
                    update={
                        "state": "results" if matched else "unknown",
                        "observed_at": float(self.clock()),
                    }
                )
            if args.operation == "open" and self.selected:
                item = self.track(
                    self.request("GET", "/tracks/" + self.selected.item_id, gate=gate)
                )
                return self.last_observation.model_copy(
                    update={
                        "item_id": item.item_id,
                        "title": item.title,
                        "observed_at": float(self.clock()),
                    }
                )
            if args.operation == "devices":
                data = self.request("GET", "/me/player/devices", gate=gate)
                live_ids = {item.get("id") for item in data["devices"] if item.get("id")}
                return self.last_observation.model_copy(
                    update={
                        "state": "ready" if live_ids == set(self.devices.values()) else "unknown",
                        "observed_at": float(self.clock()),
                    }
                )
            return self.observe(args, gate)
        if args.generation != self.generation:
            raise MediaError("SPOTIFY_STALE_GENERATION")
        if args.operation == "search":
            self.last_query = request.query
            data = self.request(
                "GET",
                "/search",
                params={"q": request.query, "type": "track", "limit": self.limit},
                gate=gate,
            )
            self.results = [self.track(item) for item in data["tracks"]["items"][: self.limit]]
            observed = MediaObservation(
                session_ref=args.session_ref,
                service="spotify",
                generation=self.generation + 1,
                observed_at=float(self.clock()),
                state="results",
                results=self.results,
            )
        elif args.operation == "devices":
            data = self.request("GET", "/me/player/devices", gate=gate)
            devices = []
            self.devices = {}
            for item in data["devices"][:10]:
                identity = item.get("id")
                if not identity:
                    continue
                ref = self.device_refs.setdefault(identity, "device_" + uuid4().hex)
                self.devices[ref] = identity
                devices.append(
                    PlaybackDevice(
                        reference=ref,
                        name=item["name"][:100],
                        active=item["is_active"],
                        restricted=item["is_restricted"],
                    )
                )
            observed = MediaObservation(
                session_ref=args.session_ref,
                service="spotify",
                generation=self.generation + 1,
                observed_at=float(self.clock()),
                state="ready",
                devices=devices,
            )
        elif args.operation == "open":
            selected = next((r for r in self.results if r.reference == args.reference), None)
            if not selected:
                raise MediaError("SPOTIFY_STALE_TRACK_REFERENCE")
            verified = self.track(
                self.request("GET", "/tracks/" + selected.item_id, gate=gate), selected.reference
            )
            if verified.item_id != selected.item_id or verified.title != selected.title:
                raise MediaError("SPOTIFY_WRONG_TRACK")
            self.selected = verified
            observed = MediaObservation(
                session_ref=args.session_ref,
                service="spotify",
                generation=self.generation + 1,
                observed_at=float(self.clock()),
                state="opened",
                item_id=verified.item_id,
                title=verified.title,
            )
        elif args.operation in {"play", "pause", "resume"}:
            if (
                not self.selected
                or self.selected.reference != args.reference
                or args.device_ref not in self.devices
            ):
                raise MediaError("SPOTIFY_SELECT_TRACK_AND_DEVICE")
            device_data = self.request("GET", "/me/player/devices", gate=gate)
            target_id = self.devices[args.device_ref]
            if not any(
                d.get("id") == target_id and not d.get("is_restricted", True)
                for d in device_data["devices"]
            ):
                raise MediaError("SPOTIFY_TARGET_DEVICE_UNAVAILABLE")
            before = self.observe(args, gate)
            if args.operation in {"pause", "resume"} and (
                before.item_id != self.selected.item_id or before.device_ref != args.device_ref
            ):
                raise MediaError("SPOTIFY_USER_TAKEOVER")
            gate()
            self.admitted = True
            self.request(
                "PUT",
                "/me/player/pause" if args.operation == "pause" else "/me/player/play",
                params={"device_id": target_id},
                body={"uris": ["spotify:track:" + self.selected.item_id]}
                if args.operation == "play"
                else None,
                gate=gate,
            )
            observed = self.observe(args, gate)
            observed = observed.model_copy(update={"generation": self.generation + 1})
        elif args.operation == "current":
            observed = self.observe(args, gate)
            observed = observed.model_copy(update={"generation": self.generation + 1})
        else:
            raise MediaError("SPOTIFY_MANUAL_OAUTH_SETUP_REQUIRED")
        self.generation = observed.generation
        self.last_observation = observed
        return observed
