# Utils module - helper functions

import re
from typing import Optional


def format_proxy_link(server: str, port: int, secret: str) -> str:
    """Создать tg:// ссылку для прокси"""
    return f"tg://proxy?server={server}&port={port}&secret={secret}"


def format_tme_link(server: str, port: int, secret: str) -> str:
    """Создать https://t.me/proxy ссылку"""
    return f"https://t.me/proxy?server={server}&port={port}&secret={secret}"


def parse_proxy_url(url: str) -> Optional[dict]:
    """Распарсить URL прокси и вернуть компоненты"""
    url = url.strip()
    
    # Паттерн для tg://proxy и https://t.me/proxy
    pattern = r"(?:tg://proxy|https?://t\.me/proxy)\?server=([^&\s]+)&port=(\d+)&secret=([^\s\"'<>]+)"
    match = re.search(pattern, url, re.IGNORECASE)
    
    if not match:
        return None
    
    try:
        server = match.group(1)
        port = int(match.group(2))
        secret = match.group(3)
        
        if port <= 0 or port > 65535:
            return None
        
        return {
            'server': server,
            'port': port,
            'secret': secret
        }
    except (ValueError, IndexError):
        return None


def format_rtt(rtt_ms: Optional[float]) -> str:
    """Форматировать RTT в читаемый вид"""
    if rtt_ms is None:
        return "N/A"
    if rtt_ms < 100:
        return f"{rtt_ms:.0f}ms"
    elif rtt_ms < 1000:
        return f"{rtt_ms:.1f}ms"
    else:
        return f"{rtt_ms/1000:.2f}s"


def format_dc(dc: Optional[int]) -> str:
    """Форматировать DC индекс"""
    if dc is None:
        return "N/A"
    return f"DC {dc}"


def is_valid_proxy(secret: str) -> bool:
    """Проверить валидность секрета прокси"""
    if not secret:
        return False
    # Секрет должен быть в формате hex или base64
    if len(secret) < 8:
        return False
    return True


def get_proxy_type(secret: str) -> str:
    """Определить тип прокси по секрету"""
    if secret.startswith('ee'):
        return 'MTProto Proxy'
    elif secret.startswith('dd'):
        return 'MTProto Proxy (UDP)'
    else:
        return 'MTProto Proxy (Unknown)'
