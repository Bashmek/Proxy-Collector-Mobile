"""Parse and deduplicate MTProto proxy links."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

PROXY_LINK_RE = re.compile(
    r"(?:tg://proxy|https?://t\.me/proxy)\?"
    r"server=[^&\s]+&port=\d+&secret=[^\s\"'<>]+",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ProxyLink:
    server: str
    port: int
    secret: str
    raw: str

    @property
    def key(self) -> str:
        return f"{self.server.lower()}:{self.port}:{self.secret.lower()}"

    def tg_link(self) -> str:
        return (
            f"tg://proxy?server={self.server}&port={self.port}&secret={self.secret}"
        )

    def tme_link(self) -> str:
        return (
            f"https://t.me/proxy?server={self.server}&port={self.port}"
            f"&secret={self.secret}"
        )


def parse_proxy_link(link: str) -> ProxyLink | None:
    link = link.strip()
    if not link or link.startswith("#"):
        return None

    match = PROXY_LINK_RE.search(link)
    if not match:
        return None

    raw = match.group(0)
    parsed = urlparse(raw.replace("tg://", "https://", 1))
    params = parse_qs(parsed.query)

    try:
        server = params["server"][0]
        port = int(params["port"][0])
        secret = params["secret"][0]
    except (KeyError, IndexError, ValueError):
        return None

    if not server or port <= 0 or port > 65535 or not secret:
        return None

    return ProxyLink(server=server, port=port, secret=secret, raw=raw)


def extract_proxy_links(text: str) -> list[ProxyLink]:
    seen: set[str] = set()
    result: list[ProxyLink] = []

    for line in text.splitlines():
        proxy = parse_proxy_link(line)
        if proxy is None or proxy.key in seen:
            continue
        seen.add(proxy.key)
        result.append(proxy)

    return result
