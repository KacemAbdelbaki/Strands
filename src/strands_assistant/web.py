"""An HTTP client for web_fetch that can only reach the public internet.

The SDK's web_fetch has no guard against private addresses, so without this the model (or a prompt
injected into a page) could make the Researcher read Ollama, the web UI, a router admin page or a
cloud metadata endpoint. Every request is checked, including each redirect hop: the host is resolved
and the request is refused if any of its addresses is not a public one.

Known limit: the check resolves the name, then httpx resolves it again to connect, so a DNS server
that answers differently the second time (DNS rebinding) can slip through. Closing that needs a
connector that dials the checked address itself, or an egress proxy.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable

import httpx

Resolver = Callable[[str, int], Awaitable[list[str]]]


async def _resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])  # drop an IPv6 zone id such as "%eth0"
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped  # "::ffff:127.0.0.1" is 127.0.0.1
    return ip.is_global and not ip.is_multicast


class PublicOnlyTransport(httpx.AsyncBaseTransport):
    """Refuses any request whose host is, or resolves to, a non-public address."""

    def __init__(self, inner: httpx.AsyncBaseTransport | None = None, resolve: Resolver = _resolve) -> None:
        # No keep-alive: agents run each call on a fresh event loop, and a pooled connection from
        # an earlier loop can't be reused on a later one
        self._inner = inner or httpx.AsyncHTTPTransport(limits=httpx.Limits(max_keepalive_connections=0))
        self._resolve = resolve

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        if url.scheme not in ("http", "https"):
            raise httpx.ConnectError(f"Refusing to fetch {url}: only http and https are allowed", request=request)
        host = url.host
        port = url.port or (443 if url.scheme == "https" else 80)
        try:
            addresses = [str(ipaddress.ip_address(host))]
        except ValueError:
            try:
                addresses = await self._resolve(host, port)
            except OSError as error:
                raise httpx.ConnectError(f"Could not resolve {host}: {error}", request=request) from error
        if not addresses or not all(_is_public(address) for address in addresses):
            raise httpx.ConnectError(
                f"Refusing to fetch {url}: {host} is a private or local address", request=request
            )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def make_public_web_client() -> httpx.AsyncClient:
    """The client the Researcher's web_fetch uses."""
    return httpx.AsyncClient(transport=PublicOnlyTransport(), follow_redirects=True, timeout=15)
