"""Pinned, bounded external-webhook delivery primitives."""

from dataclasses import dataclass
import hashlib
import hmac
import ipaddress
import json
import ssl
from urllib.parse import urlparse

import urllib3

MAX_URL = 2048


@dataclass(frozen=True)
class WebhookConfig:
    url: str
    secret: str
    allowed_hosts: set[str]
    version: int = 0


@dataclass(frozen=True)
class Destination:
    url: str
    address: str
    sni: str


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes = b""
    redirect: bool = False


@dataclass(frozen=True)
class Delivery:
    destination: Destination
    body: bytes
    headers: dict[str, str]

    def classify(self, response: Response) -> tuple[bool, bool]:
        if response.redirect:
            return False, False
        if 200 <= response.status < 300:
            return True, False
        return False, response.status in {408, 425, 429} or response.status >= 500


def _public(addresses: list[str]) -> str:
    if not addresses or any(not ipaddress.ip_address(item).is_global for item in addresses):
        raise ValueError("webhook destination must resolve only to public addresses")
    return addresses[0]


def validate_destination(url: str, allowed_hosts: set[str], resolve, reresolve) -> Destination:
    parsed = urlparse(url)
    if len(url) > MAX_URL or parsed.scheme != "https" or not parsed.hostname or parsed.port not in {None, 443}:
        raise ValueError("webhook URL must be HTTPS on port 443 within the size bound")
    host = parsed.hostname.lower()
    if host not in allowed_hosts:
        raise ValueError("webhook host is not allowlisted")
    first, second = _public(resolve(host)), _public(reresolve(host))
    if first != second:
        raise ValueError("webhook DNS destination rebound")
    return Destination(url, first, host)


def build_delivery(delivery_id: str, chat_id: str, message_id: str, text: str, secret: str, timestamp: int, url: str, allowed_hosts: set[str], resolve) -> Delivery:
    destination = validate_destination(url, allowed_hosts, resolve, resolve)
    body = json.dumps({"chat_id": chat_id, "delivery_id": delivery_id, "message_id": message_id, "text": text, "timestamp": timestamp}, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return Delivery(destination, body, {"Content-Type": "application/json", "X-Webhook-Signature": f"sha256={signature}", "X-Webhook-Timestamp": str(timestamp)})


def concrete_https_transport(delivery: Delivery, *, connect_address: str, tls_server_name: str, connect_timeout: int = 2, total_timeout: int = 10, max_response_bytes: int = 16384, allow_redirects: bool = False, ca_certs: str | None = None) -> Response:
    """Connect to a validated IP while verifying the original hostname's TLS identity."""
    try:
        ipaddress.ip_address(connect_address)
    except ValueError as error:
        raise ValueError("webhook connect address must be an IP address") from error
    if allow_redirects:
        raise ValueError("webhook redirects are disabled")
    target = urlparse(delivery.destination.url)
    options = {"cert_reqs": ssl.CERT_REQUIRED, "assert_hostname": tls_server_name, "server_hostname": tls_server_name}
    if ca_certs:
        options["ca_certs"] = ca_certs
    try:
        pool = urllib3.HTTPSConnectionPool(connect_address, port=target.port or 443, **options)
        response = pool.request("POST", target.path or "/", body=delivery.body, headers={**delivery.headers, "Host": tls_server_name}, timeout=urllib3.Timeout(connect=connect_timeout, total=total_timeout), retries=False, redirect=False, preload_content=False, assert_same_host=False)
        body = response.read(max_response_bytes + 1)
    except urllib3.exceptions.HTTPError as error:
        raise OSError("webhook TLS connection failed") from error
    finally:
        if "response" in locals():
            response.release_conn()
    if len(body) > max_response_bytes:
        raise ValueError("webhook response exceeds bound")
    return Response(response.status, body, bool(response.get_redirect_location()))


def verify_signature(body: bytes, headers: dict[str, str], secret: str, *, now: int, window: int = 300) -> bool:
    """Verify the exact canonical bytes only within the five-minute replay window."""
    try:
        timestamp = int(headers["X-Webhook-Timestamp"])
        supplied = headers["X-Webhook-Signature"].removeprefix("sha256=")
    except (KeyError, ValueError):
        return False
    expected = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return abs(now - timestamp) <= window and hmac.compare_digest(expected, supplied)
