"""Fetch MTProto proxy links from remote sources."""

from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .parser import ProxyLink, extract_proxy_links
from .sources import DEFAULT_SOURCES

DEFAULT_FETCH_TIMEOUT = 20.0
MAX_FETCH_RETRIES = 2


@dataclass(slots=True)
class SourceResult:
    name: str
    url: str
    proxies: list[ProxyLink]
    error: str | None = None


def format_fetch_error(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}: {exc.reason}"
    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            return "timeout"
        return str(reason)
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "timeout"
    return f"{type(exc).__name__}: {exc}"


def fetch_text(
    url: str,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
    retries: int = MAX_FETCH_RETRIES,
) -> str:
    context = ssl.create_default_context()
    last_error: BaseException | None = None

    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Proxy-Collect/1.0",
                    "Accept": "text/plain,*/*",
                },
            )
            with urllib.request.urlopen(
                request,
                timeout=timeout,
                context=context,
            ) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(0.75 * (attempt + 1))

    assert last_error is not None
    raise last_error


def collect_from_source(
    urls: list[str],
    name: str,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
) -> SourceResult:
    errors: list[str] = []

    for url in urls:
        try:
            text = fetch_text(url, timeout=timeout)
            proxies = extract_proxy_links(text)
            return SourceResult(name=name, url=url, proxies=proxies)
        except Exception as exc:
            errors.append(f"{url}: {format_fetch_error(exc)}")

    return SourceResult(
        name=name,
        url=urls[0] if urls else "",
        proxies=[],
        error=" | ".join(errors) if errors else "No URLs configured",
    )


def collect_all(
    sources: list[dict[str, object]] | None = None,
    timeout: float = DEFAULT_FETCH_TIMEOUT,
) -> tuple[list[ProxyLink], list[SourceResult]]:
    sources = sources or DEFAULT_SOURCES
    results: list[SourceResult] = []
    seen: set[str] = set()
    merged: list[ProxyLink] = []

    for source in sources:
        name = str(source.get("name", "source"))
        urls = source.get("urls")
        if urls is None and "url" in source:
            urls = [source["url"]]
        if not urls:
            continue

        try:
            result = collect_from_source(list(urls), name, timeout)
        except Exception as exc:
            result = SourceResult(
                name=name,
                url=str(urls[0]),
                proxies=[],
                error=format_fetch_error(exc),
            )

        results.append(result)

        for proxy in result.proxies:
            if proxy.key in seen:
                continue
            seen.add(proxy.key)
            merged.append(proxy)

    return merged, results
