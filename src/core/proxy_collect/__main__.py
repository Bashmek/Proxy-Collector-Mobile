"""CLI entry point for Proxy-Collect."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .checker import check_many
from .collector import collect_all
from .parser import extract_proxy_links, parse_proxy_link
from .sources import DEFAULT_SOURCES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect and verify working Telegram MTProto proxies.",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="URL",
        help="Add a custom source URL (can be repeated)",
    )
    parser.add_argument(
        "--sources-file",
        type=Path,
        help="Text file with one source URL per line",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Local file with proxy links instead of downloading sources",
    )
    parser.add_argument(
        "--check",
        metavar="LINK",
        help="Check a single proxy link and exit",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=40,
        help="Number of parallel checks (default: 40)",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=3.0,
        help="TCP connect timeout in seconds (default: 3)",
    )
    parser.add_argument(
        "--response-timeout",
        type=float,
        default=5.0,
        help="Protocol response timeout in seconds (default: 5)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Check only the first N unique proxies (0 = all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("working_proxies.txt"),
        help="Output file for working proxies (default: working_proxies.txt)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Optional JSON report path",
    )
    parser.add_argument(
        "--fetch-timeout",
        type=float,
        default=20.0,
        help="Timeout for downloading source lists in seconds (default: 20)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Print only working proxy links",
    )
    return parser


def load_sources(args: argparse.Namespace) -> list[dict[str, str]]:
    sources = list(DEFAULT_SOURCES)

    if args.sources:
        for url in args.sources:
            sources.append({"name": url, "urls": [url]})

    if args.sources_file:
        lines = args.sources_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            url = line.strip()
            if url and not url.startswith("#"):
                sources.append({"name": url, "urls": [url]})

    return sources


def print_progress(done: int, total: int, result) -> None:
    status = "OK" if result.ok else "FAIL"
    latency = f"{result.rtt_ms:.0f} ms" if result.rtt_ms is not None else "-"
    print(
        f"[{done}/{total}] {status:4} {latency:>8}  {result.proxy.server}:{result.proxy.port}",
        flush=True,
    )


def save_results(
    working,
    all_results,
    output_path: Path,
    json_path: Path | None,
) -> None:
    output_path.write_text(
        "\n".join(item.proxy.tg_link() for item in working) + ("\n" if working else ""),
        encoding="utf-8",
    )

    if json_path:
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "total_checked": len(all_results),
            "working_count": len(working),
            "proxies": [
                {
                    "link": item.proxy.tg_link(),
                    "tme_link": item.proxy.tme_link(),
                    "server": item.proxy.server,
                    "port": item.proxy.port,
                    "secret": item.proxy.secret,
                    "rtt_ms": item.rtt_ms,
                    "mode": item.mode,
                    "dc": item.dc,
                }
                for item in working
            ],
        }
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.check:
        proxy = parse_proxy_link(args.check)
        if proxy is None:
            print("Invalid proxy link.", file=sys.stderr)
            return 2

        from .checker import check_one

        result = check_one(
            proxy,
            connect_timeout=args.connect_timeout,
            response_timeout=args.response_timeout,
        )
        if result.ok:
            print(f"OK  {result.rtt_ms:.0f} ms  DC {result.dc}  {result.mode}")
            print(result.proxy.tg_link())
            return 0

        print(f"FAIL  {result.error}", file=sys.stderr)
        return 1

    if args.input:
        text = args.input.read_text(encoding="utf-8")
        proxies = extract_proxy_links(text)
        source_results = []
        if not args.quiet:
            print(f"Loaded {len(proxies)} unique proxies from {args.input}")
    else:
        if not args.quiet:
            print("Collecting proxies from sources...")
        proxies, source_results = collect_all(
            load_sources(args),
            timeout=args.fetch_timeout,
        )

        if not args.quiet:
            for source in source_results:
                if source.error:
                    print(f"  ! {source.name}: {source.error}")
                else:
                    print(f"  + {source.name}: {len(source.proxies)} proxies")
            print(f"Total unique proxies: {len(proxies)}")

    if args.limit > 0:
        proxies = proxies[: args.limit]

    if not proxies:
        print("No proxies to check.", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"\nChecking {len(proxies)} proxies...\n")

    results = check_many(
        proxies,
        concurrency=args.concurrency,
        connect_timeout=args.connect_timeout,
        response_timeout=args.response_timeout,
        on_progress=None if args.quiet else print_progress,
    )

    working = [item for item in results if item.ok]
    save_results(working, results, args.output, args.json)

    if args.quiet:
        for item in working:
            print(item.proxy.tg_link())
    else:
        print(f"\nWorking: {len(working)} / {len(results)}")
        print(f"Saved to {args.output}")
        if args.json:
            print(f"JSON report: {args.json}")

        if working:
            print("\nTop working proxies:")
            for item in working[:10]:
                print(
                    f"  {item.rtt_ms:.0f} ms  {item.proxy.server}:{item.proxy.port}  "
                    f"{item.proxy.tg_link()}"
                )

    return 0 if working else 1


if __name__ == "__main__":
    raise SystemExit(main())
