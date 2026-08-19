# Mobile Android version of Proxy Collector using Kivy
# Refactored to use modular architecture

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.accordion import Accordion, AccordionItem
from kivy.metrics import dp, sp
from kivy.clock import Clock
from kivy.core.window import Window
import threading
import time
from datetime import datetime

# Import from modular architecture
from src.core.proxy_collect.checker import check_many
from src.core.proxy_collect.collector import collect_all
from src.core.proxy_collect.sources import DEFAULT_SOURCES
from src.core.proxy_collect.parser import extract_proxy_links
from src.services import MobileClipboardService, MobileNotificationService

# Для Android
try:
    from android.permissions import request_permissions, Permission
except ImportError:
    pass


class ProxyCollectorMobileApp(App):
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.15, 1)  # Тёмный фон
        
        # Запрашиваем разрешения для Android
        try:
            request_permissions([Permission.INTERNET, Permission.ACCESS_NETWORK_STATE])
        except:
            pass
        
        self.results = []
        self.working_proxies = []
        self.is_running = False
        self.stop_event = threading.Event()
        
        # Сервисы
        self.clipboard = MobileClipboardService()
        self.notification = MobileNotificationService()
        
        return self.create_main_screen()
    
    def create_main_screen(self):
        """Создаёт главный экран."""
        root = BoxLayout(orientation='vertical')
        
        # Заголовок
        header = Label(
            text='Proxy Collector',
            font_size=sp(24),
            bold=True,
            color=(0.16, 0.66, 0.93, 1),  # Telegram blue
            size_hint=(1, 0.1)
        )
        root.add_widget(header)
        
        # Кнопки управления
        btn_layout = BoxLayout(size_hint=(1, 0.08), spacing=dp(5), padding=dp(5))
        
        self.start_btn = Button(
            text='▶ Запустить',
            background_color=(0.3, 0.7, 0.3, 1),
            on_press=self.start_collection
        )
        self.stop_btn = Button(
            text='⏹ Стоп',
            background_color=(0.9, 0.3, 0.3, 1),
            on_press=self.stop_collection,
            disabled=True
        )
        self.copy_btn = Button(
            text='📋 Копировать',
            background_color=(0.3, 0.6, 0.9, 1),
            on_press=self.copy_to_clipboard
        )
        
        btn_layout.add_widget(self.start_btn)
        btn_layout.add_widget(self.stop_btn)
        btn_layout.add_widget(self.copy_btn)
        root.add_widget(btn_layout)
        
        # Прогресс-бар
        self.progress_bar = ProgressBar(max=100, value=0, size_hint=(1, 0.03))
        self.progress_label = Label(text='', size_hint=(1, 0.04))
        root.add_widget(self.progress_bar)
        root.add_widget(self.progress_label)
        
        # Аккордеон с настройками
        accordion = Accordion(size_hint=(1, 0.2), padding=dp(5))
        
        # Настройки
        settings_item = AccordionItem(title='⚙️ Настройки')
        settings_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        
        settings_layout.add_widget(Label(text='Параллельных потоков:', size_hint=(1, 0.3)))
        self.concurrency_input = TextInput(
            text='40',
            multiline=False,
            size_hint=(1, 0.7)
        )
        settings_layout.add_widget(self.concurrency_input)
        
        settings_item.add_widget(settings_layout)
        accordion.add_widget(settings_item)
        
        # Источники
        sources_item = AccordionItem(title='🌐 Источники')
        sources_scroll = ScrollView(size_hint=(1, 1))
        sources_layout = BoxLayout(orientation='vertical', size_hint_y=None)
        sources_layout.bind(minimum_height=sources_layout.setter('height'))
        
        self.source_checks = {}
        for source in DEFAULT_SOURCES:
            # Упрощённо - просто чекбоксы
            btn = Button(
                text=source['name'],
                size_hint=(1, None),
                height=dp(40)
            )
            btn.bind(on_press=lambda instance, name=source['name']: self.toggle_source(name))
            sources_layout.add_widget(btn)
            self.source_checks[source['name']] = True
        
        sources_scroll.add_widget(sources_layout)
        sources_item.add_widget(sources_scroll)
        accordion.add_widget(sources_item)
        
        root.add_widget(accordion)
        
        # Список результатов
        results_label = Label(
            text='Рабочие прокси:',
            size_hint=(1, 0.05),
            bold=True
        )
        root.add_widget(results_label)
        
        self.results_scroll = ScrollView(size_hint=(1, 1))
        self.results_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(2)
        )
        self.results_layout.bind(minimum_height=self.results_layout.setter('height'))
        self.results_scroll.add_widget(self.results_layout)
        root.add_widget(self.results_scroll)
        
        # Лог
        self.log_label = Label(
            text='Готов к работе',
            size_hint=(1, 0.06),
            color=(0.4, 0.9, 0.4, 1)
        )
        root.add_widget(self.log_label)
        
        return root
    
    def toggle_source(self, name):
        self.source_checks[name] = not self.source_checks[name]
    
    def log_message(self, message):
        Clock.schedule_once(lambda dt: setattr(self.log_label, 'text', message))
    
    def update_progress(self, value, max_value, text):
        Clock.schedule_once(lambda dt: setattr(self.progress_bar, 'value', (value/max_value)*100))
        Clock.schedule_once(lambda dt: setattr(self.progress_label, 'text', text))
    
    def add_result(self, result):
        """Добавляет результат в список."""
        if result.ok:
            btn = Button(
                text=f"✅ {result.proxy.server}:{result.proxy.port} - {result.rtt_ms:.0f}ms",
                size_hint=(1, None),
                height=dp(50),
                background_color=(0.2, 0.6, 0.2, 1)
            )
            btn.bind(on_press=lambda instance, link=result.proxy.tg_link(): self.copy_single_link(link))
            Clock.schedule_once(lambda dt: self.results_layout.add_widget(btn))
    
    def copy_single_link(self, link):
        """Копирует одну ссылку."""
        if self.clipboard.copy_text(link):
            self.log_message(f'📋 Скопировано: {link[:50]}...')
    
    def start_collection(self, instance):
        if self.is_running:
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.start_btn.disabled = True
        self.stop_btn.disabled = False
        
        # Очищаем результаты
        self.results_layout.clear_widgets()
        self.results = []
        self.working_proxies = []
        
        # Запускаем в потоке
        threading.Thread(target=self.run_collection, daemon=True).start()
    
    def stop_collection(self, instance):
        self.stop_event.set()
        self.log_message('⚠️ Остановка...')
    
    def run_collection(self):
        """Основная логика сбора."""
        try:
            self.log_message('🔄 Сбор источников...')
            
            # Собираем прокси
            sources = [s for s in DEFAULT_SOURCES if self.source_checks.get(s['name'], True)]
            proxies, source_results = collect_all(sources, timeout=20.0)
            
            if not proxies:
                self.log_message('❌ Прокси не найдены')
                return
            
            self.log_message(f'📊 Проверка {len(proxies)} прокси...')
            
            checked = 0
            
            def on_progress(done, total, result):
                nonlocal checked
                checked = done
                self.update_progress(done, total, f'{done}/{total}')
                if result.ok:
                    self.add_result(result)
            
            results = check_many(
                proxies,
                concurrency=int(self.concurrency_input.text or 40),
                on_progress=on_progress,
                stop_event=self.stop_event
            )
            
            self.results = results
            self.working_proxies = [r for r in results if r.ok]
            
            if self.stop_event.is_set():
                self.log_message(f'🛑 Остановлено. Рабочих: {len(self.working_proxies)}')
            else:
                self.log_message(f'✅ Готово! Найдено {len(self.working_proxies)} рабочих прокси')
                # Показываем уведомление
                self.notification.show_notification(
                    'Proxy Collector',
                    f'Найдено {len(self.working_proxies)} рабочих прокси'
                )
        
        except Exception as e:
            self.log_message(f'❌ Ошибка: {str(e)}')
        finally:
            self.is_running = False
            Clock.schedule_once(lambda dt: setattr(self.start_btn, 'disabled', False))
            Clock.schedule_once(lambda dt: setattr(self.stop_btn, 'disabled', True))
    
    def copy_to_clipboard(self, instance):
        """Копирует все рабочие прокси."""
        if not self.working_proxies:
            self.log_message('⚠️ Нет прокси для копирования')
            return
        
        links = '\n'.join(r.proxy.tg_link() for r in self.working_proxies)
        if self.clipboard.copy_text(links):
            self.log_message(f'📋 Скопировано {len(self.working_proxies)} прокси')
        else:
            self.log_message('❌ Ошибка копирования')


if __name__ == '__main__':
    ProxyCollectorMobileApp().run()