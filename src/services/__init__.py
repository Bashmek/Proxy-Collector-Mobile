# Services module - platform-agnostic services

from abc import ABC, abstractmethod
from typing import Optional, Callable, List
import json
import os


class StorageService(ABC):
    """Сервис для работы с хранилищем (файлы, БД)"""
    
    @abstractmethod
    def save_proxies(self, proxies: List[dict], filepath: str) -> bool:
        """Сохранить прокси в файл"""
        pass
    
    @abstractmethod
    def load_proxies(self, filepath: str) -> List[dict]:
        """Загрузить прокси из файла"""
        pass
    
    @abstractmethod
    def save_settings(self, settings: dict, filepath: str = "settings.json") -> bool:
        """Сохранить настройки"""
        pass
    
    @abstractmethod
    def load_settings(self, filepath: str = "settings.json") -> dict:
        """Загрузить настройки"""
        pass


class FileStorageService(StorageService):
    """Реализация хранения в файлах"""
    
    def save_proxies(self, proxies: List[dict], filepath: str) -> bool:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for proxy in proxies:
                    if 'raw' in proxy and proxy['raw']:
                        f.write(proxy['raw'] + '\n')
            return True
        except Exception:
            return False
    
    def load_proxies(self, filepath: str) -> List[dict]:
        proxies = []
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            proxies.append({'raw': line})
        except Exception:
            pass
        return proxies
    
    def save_settings(self, settings: dict, filepath: str = "settings.json") -> bool:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            return True
        except Exception:
            return False
    
    def load_settings(self, filepath: str = "settings.json") -> dict:
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}


class ClipboardService(ABC):
    """Сервис для работы с буфером обмена"""
    
    @abstractmethod
    def copy_text(self, text: str) -> bool:
        """Скопировать текст в буфер обмена"""
        pass
    
    @abstractmethod
    def paste_text(self) -> Optional[str]:
        """Вставить текст из буфера обмена"""
        pass


class DesktopClipboardService(ClipboardService):
    """Реализация для Desktop (Tkinter)"""
    
    def copy_text(self, text: str) -> bool:
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            return True
        except Exception:
            return False
    
    def paste_text(self) -> Optional[str]:
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            return text
        except Exception:
            return None


class MobileClipboardService(ClipboardService):
    """Реализация для Mobile (Kivy)"""
    
    def copy_text(self, text: str) -> bool:
        try:
            from kivy.core.clipboard import Clipboard
            Clipboard.copy(text)
            return True
        except Exception:
            return False
    
    def paste_text(self) -> Optional[str]:
        try:
            from kivy.core.clipboard import Clipboard
            return Clipboard.paste()
        except Exception:
            return None


class NotificationService(ABC):
    """Сервис уведомлений"""
    
    @abstractmethod
    def show_notification(self, title: str, message: str) -> bool:
        """Показать уведомление"""
        pass


class DesktopNotificationService(NotificationService):
    """Уведомления для Desktop"""
    
    def show_notification(self, title: str, message: str) -> bool:
        try:
            # Попытка использовать plyer для кроссплатформенных уведомлений
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
            return True
        except Exception:
            # Fallback: print
            print(f"[{title}] {message}")
            return True


class MobileNotificationService(NotificationService):
    """Уведомления для Mobile"""
    
    def show_notification(self, title: str, message: str) -> bool:
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
            return True
        except Exception:
            # Fallback: print
            print(f"[{title}] {message}")
            return True
