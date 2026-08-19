"""Validate MTProto proxies with a real protocol handshake."""
from __future__ import annotations
import time
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from .mtproto_check import check_proxy
from .parser import ProxyLink

@dataclass(slots=True)
class CheckResult:
    proxy: ProxyLink
    ok: bool
    rtt_ms: float | None = None
    mode: str | None = None
    dc: int | None = None
    error: str | None = None

def check_one(
    proxy: ProxyLink,
    connect_timeout: float = 3.0,
    response_timeout: float = 5.0,
) -> CheckResult:
    started = time.perf_counter()
    try:
        result = check_proxy(
            proxy.tg_link(),
            connect_timeout=connect_timeout,
            response_timeout=response_timeout,
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return CheckResult(proxy=proxy, ok=False, rtt_ms=elapsed, error=str(exc))

    if result.ok:
        return CheckResult(proxy=proxy, ok=True, rtt_ms=result.rtt_ms, mode=result.mode, dc=result.dc)
    
    return CheckResult(
        proxy=proxy, ok=False, 
        rtt_ms=result.rtt_ms or (time.perf_counter() - started) * 1000,
        error=result.error or "Proxy unavailable",
    )

def check_many(
    proxies: list[ProxyLink],
    *,
    concurrency: int = 40,
    connect_timeout: float = 3.0,
    response_timeout: float = 5.0,
    on_progress: Callable[[int, int, CheckResult], None] | None = None,
    stop_event: threading.Event | None = None,
) -> list[CheckResult]:
    if not proxies:
        return []
    
    results: list[CheckResult] = []
    total = len(proxies)
    done = 0
    
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {
            pool.submit(check_one, proxy, connect_timeout, response_timeout): proxy
            for proxy in proxies
        }
        
        for future in as_completed(futures):
            # Честная остановка: если нажали "Стоп", отменяем оставшиеся
            if stop_event and stop_event.is_set():
                for f in futures:
                    f.cancel()
                break
                
            result = future.result()
            results.append(result)
            done += 1
            
            if on_progress:
                on_progress(done, total, result)

    results.sort(
        key=lambda item: (
            0 if item.ok else 1,
            item.rtt_ms if item.rtt_ms is not None else float("inf"),
        )
    )
    return results