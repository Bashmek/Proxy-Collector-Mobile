# Desktop GUI module - Tkinter interface

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from datetime import datetime

from src.core.proxy_collect.collector import collect_all
from src.core.proxy_collect.checker import check_many
from src.core.proxy_collect.sources import DEFAULT_SOURCES
from src.core.proxy_collect.parser import extract_proxy_links


class DesktopApp:
    """Desktop приложение для сбора прокси"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Proxy Collector - Desktop")
        self.root.geometry("900x700")
        
        self.results = []
        self.working_proxies = []
        self.is_running = False
        self.stop_event = threading.Event()
        
        self.create_ui()
    
    def create_ui(self):
        """Создание интерфейса"""
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Заголовок
        title_label = ttk.Label(
            main_frame, 
            text="Proxy Collector", 
            font=('Helvetica', 20, 'bold')
        )
        title_label.grid(row=0, column=0, pady=10)
        
        # Кнопки управления
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=0, pady=10)
        
        self.start_btn = ttk.Button(
            btn_frame, 
            text="▶ Запустить", 
            command=self.start_collection
        )
        self.start_btn.grid(row=0, column=0, padx=5)
        
        self.stop_btn = ttk.Button(
            btn_frame, 
            text="⏹ Стоп", 
            command=self.stop_collection, 
            state='disabled'
        )
        self.stop_btn.grid(row=0, column=1, padx=5)
        
        self.copy_btn = ttk.Button(
            btn_frame, 
            text="📋 Копировать все", 
            command=self.copy_to_clipboard
        )
        self.copy_btn.grid(row=0, column=2, padx=5)
        
        self.save_btn = ttk.Button(
            btn_frame, 
            text="💾 Сохранить", 
            command=self.save_to_file
        )
        self.save_btn.grid(row=0, column=3, padx=5)
        
        # Прогресс-бар
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            main_frame, 
            variable=self.progress_var, 
            maximum=100
        )
        self.progress_bar.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_label = ttk.Label(main_frame, text="")
        self.progress_label.grid(row=3, column=0, sticky=(tk.W, tk.E))
        
        # Настройки
        settings_frame = ttk.LabelFrame(main_frame, text="Настройки", padding="10")
        settings_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Label(settings_frame, text="Параллельных потоков:").grid(row=0, column=0, padx=5)
        self.concurrency_var = tk.StringVar(value="40")
        concurrency_entry = ttk.Entry(settings_frame, textvariable=self.concurrency_var, width=10)
        concurrency_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(settings_frame, text="Таймаут подключения (сек):").grid(row=0, column=2, padx=5)
        self.timeout_var = tk.StringVar(value="3.0")
        timeout_entry = ttk.Entry(settings_frame, textvariable=self.timeout_var, width=10)
        timeout_entry.grid(row=0, column=3, padx=5)
        
        # Список источников
        sources_frame = ttk.LabelFrame(main_frame, text="Источники", padding="10")
        sources_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=10)
        
        self.source_vars = {}
        for i, source in enumerate(DEFAULT_SOURCES):
            var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(sources_frame, text=source['name'], variable=var)
            chk.grid(row=i//2, column=i%2, sticky=tk.W)
            self.source_vars[source['name']] = var
        
        # Результаты
        results_frame = ttk.LabelFrame(main_frame, text="Рабочие прокси", padding="10")
        results_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        
        # Treeview для результатов
        columns = ('server', 'port', 'rtt', 'dc', 'mode')
        self.tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=15)
        
        self.tree.heading('server', text='Сервер')
        self.tree.heading('port', text='Порт')
        self.tree.heading('rtt', text='RTT (ms)')
        self.tree.heading('dc', text='DC')
        self.tree.heading('mode', text='Режим')
        
        self.tree.column('server', width=200)
        self.tree.column('port', width=60)
        self.tree.column('rtt', width=80)
        self.tree.column('dc', width=60)
        self.tree.column('mode', width=100)
        
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        results_frame.rowconfigure(0, weight=1)
        results_frame.columnconfigure(0, weight=1)
        
        # Лог
        self.log_var = tk.StringVar(value="Готов к работе")
        log_label = ttk.Label(main_frame, textvariable=self.log_var, foreground='green')
        log_label.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Контекстное меню
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Копировать ссылку", command=self.copy_selected_link)
        self.tree.bind("<Button-3>", self.show_menu)
    
    def show_menu(self, event):
        """Показать контекстное меню"""
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
    
    def log_message(self, message):
        """Логирование сообщения"""
        self.log_var.set(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        self.root.update_idletasks()
    
    def update_progress(self, value, max_value):
        """Обновление прогресс-бара"""
        progress = (value / max_value) * 100 if max_value > 0 else 0
        self.progress_var.set(progress)
        self.progress_label.config(text=f"{value}/{max_value}")
        self.root.update_idletasks()
    
    def add_result(self, result):
        """Добавление результата в таблицу"""
        if result.ok:
            self.tree.insert('', tk.END, values=(
                result.proxy.server,
                result.proxy.port,
                f"{result.rtt_ms:.0f}" if result.rtt_ms else "N/A",
                result.dc if result.dc else "N/A",
                result.mode or "N/A"
            ))
    
    def start_collection(self):
        """Запуск сбора прокси"""
        if self.is_running:
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        
        # Очистка результатов
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self.working_proxies = []
        
        # Запуск в потоке
        threading.Thread(target=self.run_collection, daemon=True).start()
    
    def stop_collection(self):
        """Остановка сбора"""
        self.stop_event.set()
        self.log_message("Остановка...")
    
    def run_collection(self):
        """Основная логика сбора"""
        try:
            self.log_message("Сбор источников...")
            
            # Фильтрация источников
            sources = [s for s in DEFAULT_SOURCES if self.source_vars.get(s['name'], tk.BooleanVar(value=True)).get()]
            
            proxies, source_results = collect_all(sources, timeout=20.0)
            
            if not proxies:
                self.log_message("Прокси не найдены")
                return
            
            self.log_message(f"Проверка {len(proxies)} прокси...")
            
            def on_progress(done, total, result):
                self.update_progress(done, total)
                if result.ok:
                    self.add_result(result)
            
            concurrency = int(self.concurrency_var.get() or 40)
            timeout = float(self.timeout_var.get() or 3.0)
            
            results = check_many(
                proxies,
                concurrency=concurrency,
                connect_timeout=timeout,
                response_timeout=timeout * 2,
                on_progress=on_progress,
                stop_event=self.stop_event
            )
            
            self.results = results
            self.working_proxies = [r for r in results if r.ok]
            
            if self.stop_event.is_set():
                self.log_message(f"Остановлено. Рабочих: {len(self.working_proxies)}")
            else:
                self.log_message(f"Готово! Найдено {len(self.working_proxies)} рабочих прокси")
        
        except Exception as e:
            self.log_message(f"Ошибка: {str(e)}")
        finally:
            self.is_running = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
    
    def copy_to_clipboard(self):
        """Копирование всех рабочих прокси"""
        if not self.working_proxies:
            messagebox.showwarning("Внимание", "Нет прокси для копирования")
            return
        
        links = '\n'.join(r.proxy.tg_link() for r in self.working_proxies)
        self.root.clipboard_clear()
        self.root.clipboard_append(links)
        self.log_message(f"Скопировано {len(self.working_proxies)} прокси")
    
    def copy_selected_link(self):
        """Копирование выбранной ссылки"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        server = item['values'][0]
        port = item['values'][1]
        
        # Найти соответствующий прокси
        for r in self.working_proxies:
            if r.proxy.server == server and r.proxy.port == port:
                link = r.proxy.tg_link()
                self.root.clipboard_clear()
                self.root.clipboard_append(link)
                self.log_message(f"Скопировано: {link[:50]}...")
                break
    
    def save_to_file(self):
        """Сохранение в файл"""
        if not self.working_proxies:
            messagebox.showwarning("Внимание", "Нет прокси для сохранения")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                for r in self.working_proxies:
                    f.write(r.proxy.tg_link() + '\n')
            self.log_message(f"Сохранено {len(self.working_proxies)} прокси в {filepath}")


def run_desktop_app():
    """Запуск Desktop приложения"""
    root = tk.Tk()
    app = DesktopApp(root)
    root.mainloop()


if __name__ == '__main__':
    run_desktop_app()
