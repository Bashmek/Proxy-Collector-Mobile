# Models module - data structures

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ProxyLink:
    """Модель прокси-сервера"""
    server: str
    port: int
    secret: str
    raw: str = ""
    
    def __post_init__(self):
        if not self.raw:
            object.__setattr__(self, 'raw', self.tg_link())
    
    @property
    def key(self) -> str:
        return f"{self.server.lower()}:{self.port}:{self.secret.lower()}"
    
    def tg_link(self) -> str:
        return f"tg://proxy?server={self.server}&port={self.port}&secret={self.secret}"
    
    def tme_link(self) -> str:
        return f"https://t.me/proxy?server={self.server}&port={self.port}&secret={self.secret}"
    
    def to_dict(self) -> dict:
        return {
            'server': self.server,
            'port': self.port,
            'secret': self.secret,
            'raw': self.raw
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProxyLink':
        return cls(
            server=data['server'],
            port=data['port'],
            secret=data['secret'],
            raw=data.get('raw', '')
        )


@dataclass(slots=True)
class CheckResult:
    """Результат проверки прокси"""
    proxy: ProxyLink
    ok: bool
    rtt_ms: Optional[float] = None
    mode: Optional[str] = None
    dc: Optional[int] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'proxy': self.proxy.to_dict(),
            'ok': self.ok,
            'rtt_ms': self.rtt_ms,
            'mode': self.mode,
            'dc': self.dc,
            'error': self.error
        }


@dataclass(slots=True)
class SourceResult:
    """Результат получения прокси из источника"""
    name: str
    url: str
    proxies: list[ProxyLink] = field(default_factory=list)
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'url': self.url,
            'proxies': [p.to_dict() for p in self.proxies],
            'error': self.error
        }


@dataclass(slots=True)
class AppSettings:
    """Настройки приложения"""
    concurrency: int = 40
    connect_timeout: float = 3.0
    response_timeout: float = 5.0
    fetch_timeout: float = 20.0
    max_retries: int = 2
    auto_save: bool = True
    save_path: str = "proxies.txt"
    dark_mode: bool = False
    language: str = "ru"
    
    def to_dict(self) -> dict:
        return {
            'concurrency': self.concurrency,
            'connect_timeout': self.connect_timeout,
            'response_timeout': self.response_timeout,
            'fetch_timeout': self.fetch_timeout,
            'max_retries': self.max_retries,
            'auto_save': self.auto_save,
            'save_path': self.save_path,
            'dark_mode': self.dark_mode,
            'language': self.language
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AppSettings':
        return cls(**data)
