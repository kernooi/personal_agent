"""Fixed HTTPS destination using the locked HTTPX/httpcore TLS stack."""

import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpcore
import httpx
from httpcore._backends.sync import SyncBackend

from jarvis.public_data import HOST, METADATA_URL, PublicConfig, PublicDataError, endpoint


def public_address(value):
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise PublicDataError("DESTINATION_DENIED") from exc
    if (
        not address.is_global
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or getattr(address, "is_site_local", False)
        or getattr(address, "sixtofour", None)
        or getattr(address, "teredo", None)
    ):
        raise PublicDataError("DESTINATION_DENIED")
    if getattr(address, "ipv4_mapped", None):
        public_address(str(address.ipv4_mapped))
    return address


def validate_url(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.netloc != HOST or parts.query or parts.fragment:
        raise PublicDataError("URL_DENIED")
    if url != METADATA_URL and not re.fullmatch(
        r"/v2/providers/ecb/rate/[a-z]{3}/[a-z]{3}", parts.path
    ):
        raise PublicDataError("URL_DENIED")


class PinnedBackend(SyncBackend):
    """Resolve once, connect to a checked numeric IP, inspect the actual socket peer.

    httpcore still supplies the original hostname for normal certificate/SNI checks.
    DNS cannot substitute another destination between validation and connection.
    """

    def __init__(self, resolver=socket.getaddrinfo, connector=None):
        self.resolver = resolver
        self.connector = connector or super().connect_tcp
        self.peer = None

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != HOST or port != 443 or local_address is not None:
            raise PublicDataError("DESTINATION_DENIED")
        addresses = self.resolver(host, port, type=socket.SOCK_STREAM)
        if not addresses or len(addresses) > 32:
            raise PublicDataError("DNS_FAILURE")
        checked = [str(public_address(row[4][0])) for row in addresses]
        chosen = checked[0]
        stream = self.connector(chosen, port, timeout=timeout, socket_options=socket_options)
        peer = stream.get_extra_info("server_addr")
        try:
            if not peer or str(public_address(peer[0])) != chosen or peer[1] != 443:
                raise PublicDataError("PEER_MISMATCH")
        except Exception:
            stream.close()
            raise
        self.peer = chosen
        return stream


def fetch(base, quote, config: PublicConfig):
    return fetch_url(endpoint(base, quote), config)


def fetch_url(url, config: PublicConfig):
    if config.mode != "enabled":
        raise PublicDataError("NETWORK_DISABLED")
    validate_url(url)
    # Fail closed if the explicitly reviewed backend integration changes.
    if httpcore.__version__ != "1.0.9" or httpx.__version__ != "0.28.1":
        raise PublicDataError("TRANSPORT_UNREVIEWED")
    backend = PinnedBackend()
    transport = httpx.HTTPTransport(verify=True, trust_env=False, retries=0)
    transport._pool._network_backend = backend
    try:
        with httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=min(5.0, config.timeout_seconds),
        ) as client:
            with client.stream(
                "GET", url, headers={"Accept": "application/json", "Accept-Encoding": "identity"}
            ) as response:
                if response.status_code == 429:
                    # No retry: Retry-After cannot outlive this bounded task.
                    raise PublicDataError("RATE_LIMITED")
                if 300 <= response.status_code < 400:
                    raise PublicDataError("REDIRECT_DENIED")
                if response.status_code in {404, 422}:
                    raise PublicDataError("UNSUPPORTED_PAIR")
                if response.status_code != 200:
                    raise PublicDataError("PROVIDER_UNAVAILABLE")
                if response.headers.get("content-type", "").split(";")[0] != "application/json":
                    raise PublicDataError("UNEXPECTED_CONTENT_TYPE")
                if response.headers.get("content-encoding", "identity") != "identity":
                    raise PublicDataError("ENCODING_DENIED")
                body = bytearray()
                for chunk in response.iter_raw():
                    body.extend(chunk)
                    if len(body) > config.max_response_bytes:
                        raise PublicDataError("OVERSIZED_PAYLOAD")
                return bytes(body), {
                    "connected_public_ip": backend.peer,
                    "tls_hostname": HOST,
                    "tls_verification": True,
                    "redirects": False,
                    "environment_proxies": False,
                }
    except PublicDataError:
        raise
    except httpx.TimeoutException as exc:
        raise PublicDataError("TIMEOUT") from exc
    except (httpx.HTTPError, OSError) as exc:
        raise PublicDataError("DNS_TLS_NETWORK_FAILURE") from exc
