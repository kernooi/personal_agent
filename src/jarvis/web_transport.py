"""Public HTTPS only; pinned DNS/peer, normal TLS, manual bounded redirects."""

import ipaddress
import socket
import zlib
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx
from httpcore._backends.sync import SyncBackend

from jarvis.public_transport import public_address
from jarvis.web_data import WebError, public_url


class PublicBackend(SyncBackend):
    def __init__(self, host, resolver=socket.getaddrinfo, connector=None):
        self.host, self.resolver = host, resolver
        self.connector = connector or super().connect_tcp
        self.peer = None

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        if host != self.host or port != 443 or local_address is not None:
            raise WebError("DESTINATION_DENIED")
        rows = self.resolver(host, port, type=socket.SOCK_STREAM)
        if not rows or len(rows) > 32:
            raise WebError("DNS_FAILURE")
        ips = []
        for row in rows:
            address = public_address(row[4][0])
            if address.version == 6 and any(
                address in ipaddress.ip_network(prefix)
                for prefix in ("64:ff9b::/96", "64:ff9b:1::/48")
            ):
                raise WebError("TRANSLATED_DESTINATION_DENIED")
            ips.append(str(address))
        chosen = ips[0]
        stream = self.connector(chosen, port, timeout=timeout, socket_options=socket_options)
        peer = stream.get_extra_info("server_addr")
        try:
            if not peer or str(public_address(peer[0])) != chosen or peer[1] != port:
                raise WebError("PEER_MISMATCH")
        except Exception:
            stream.close()
            raise
        self.peer = chosen
        return stream


def fetch_page(url, config):
    downloaded = 0
    hops = []
    for index in range(config.redirects + 1):
        public_url(url)
        host = urlsplit(url).hostname.encode("idna").decode()
        if httpcore.__version__ != "1.0.9" or httpx.__version__ != "0.28.1":
            raise WebError("TRANSPORT_UNREVIEWED")
        backend = PublicBackend(host)
        transport = httpx.HTTPTransport(verify=True, trust_env=False, retries=0)
        transport._pool._network_backend = backend
        with httpx.Client(
            transport=transport,
            trust_env=False,
            follow_redirects=False,
            timeout=min(5.0, config.timeout_seconds),
        ) as client:
            with client.stream(
                "GET",
                url,
                headers={
                    "Accept": "text/html, text/plain, application/pdf",
                    "Accept-Encoding": "identity",
                    "User-Agent": "JarvisPublicResearch/1.0",
                },
            ) as response:
                hops.append({"url": url, "peer": backend.peer})
                if response.status_code in {301, 302, 303, 307, 308}:
                    if index == config.redirects:
                        raise WebError("REDIRECT_LIMIT")
                    url = public_url(urljoin(url, response.headers.get("location", "")))
                    continue
                if response.status_code in {401, 403}:
                    raise WebError("AUTHENTICATION_OR_SITE_BLOCK", downloaded_bytes=downloaded)
                if response.status_code == 429:
                    raise WebError("RATE_LIMITED", downloaded_bytes=downloaded)
                if response.status_code != 200:
                    raise WebError("SOURCE_UNAVAILABLE", downloaded_bytes=downloaded)
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if content_type not in {"text/html", "text/plain", "application/pdf"}:
                    raise WebError("CONTENT_TYPE_UNSUPPORTED")
                encoding = response.headers.get("content-encoding", "identity").strip().lower()
                if encoding not in {"identity", "gzip"}:
                    raise WebError("ENCODING_DENIED")
                body = bytearray()
                for chunk in response.iter_raw():
                    downloaded += len(chunk)
                    if downloaded > config.max_response_bytes:
                        raise WebError("OVERSIZED_PAYLOAD")
                    body.extend(chunk)
                decoded = bytes(body)
                if encoding == "gzip":
                    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    try:
                        decoded = decoder.decompress(decoded, config.max_response_bytes + 1)
                    except zlib.error:
                        raise WebError("INVALID_GZIP_PAYLOAD") from None
                    if len(decoded) > config.max_response_bytes or decoder.unconsumed_tail:
                        raise WebError("OVERSIZED_DECOMPRESSED_PAYLOAD")
                    if not decoder.eof or decoder.unused_data:
                        raise WebError("INVALID_GZIP_PAYLOAD")
                return decoded, {
                    "url": url,
                    "content_type": content_type,
                    "hops": hops,
                    "tls_verified": True,
                    "environment_proxies": False,
                    "downloaded_bytes": downloaded,
                    "decoded_bytes": len(decoded),
                    "content_encoding": encoding,
                }
    raise WebError("REDIRECT_LIMIT")


def search_api(request, config):
    if not config.enabled or not config.local_search_authorized:
        raise WebError("LOCAL_SEARCH_NOT_AUTHORIZED")
    # No model-supplied endpoint, path, headers, cookie jar, or redirects.
    domains = request.domains
    if len(domains) > 4 or any(
        not d or not all(c.isalnum() or c in ".-" for c in d) for d in domains
    ):
        raise WebError("DOMAIN_FILTER_INVALID")
    query = request.query
    if domains:
        query += " " + " OR ".join("site:" + d for d in domains)
    params = {"q": query, "format": "json", "categories": "general", "pageno": "1"}
    if request.recency:
        params["time_range"] = request.recency
    with httpx.Client(
        trust_env=False, follow_redirects=False, timeout=min(5.0, config.timeout_seconds)
    ) as client:
        with client.stream(
            "POST",
            config.search_endpoint,
            data=params,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        ) as response:
            if response.status_code == 403:
                raise WebError("SEARXNG_JSON_DISABLED_OR_FORBIDDEN")
            if response.status_code == 429:
                raise WebError("RATE_LIMITED")
            if response.status_code != 200:
                raise WebError("SEARCH_PROVIDER_UNAVAILABLE")
            if (
                response.headers.get("content-type", "").split(";")[0] != "application/json"
                or response.headers.get("content-encoding", "identity") != "identity"
            ):
                raise WebError("INVALID_SEARCH_CONTENT_TYPE")
            body = bytearray()
            for chunk in response.iter_raw():
                body.extend(chunk)
                if len(body) > config.max_response_bytes:
                    raise WebError("OVERSIZED_PAYLOAD")
            return bytes(body), {
                "endpoint": config.search_endpoint,
                "redirects": False,
                "environment_proxies": False,
                "downloaded_bytes": len(body),
            }
