"""Modern Soft-Dark GUI for Proxy-Collect."""
import tkinter as tk
from tkinter import messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
import threading
import sys
import os
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# Импорт бэкенда
from proxy_collect.checker import check_many
from proxy_collect.collector import collect_all
from proxy_collect.sources import DEFAULT_SOURCES

# ==========================================
# ЗАГРУЗКА ИКОНКИ ИЗ ФАЙЛА
# ==========================================
def load_app_icon():
    """Загружает иконку приложения из файла icon.png."""
    try:
        from PIL import Image, ImageTk
        
        # Путь к иконке (рядом с app.py)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
        
        if not os.path.exists(icon_path):
            print(f"Warning: icon.png not found at {icon_path}")
            return None
        
        img = Image.open(icon_path)
        # Tkinter любит иконки 32x32 или 48x48 для окна
        img_small = img.resize((48, 48), Image.LANCZOS)
        return ImageTk.PhotoImage(img_small)
    except Exception as e:
        print(f"Warning: Could not load icon: {e}")
        return None


class ProxyCollectorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Proxy Collector • MTProto Checker")
        self.root.geometry("1050x800")
        self.root.minsize(900, 650)
        
        # Загружаем иконку из файла
        self.icon = load_app_icon()
        if self.icon:
            self.root.iconphoto(True, self.icon)
            
        # Состояние и потоки
        self.is_running = False
        self.stop_event = threading.Event()
        self.results = []
        self.working_proxies = []
        
        # Шрифты
        self.ui_font = ("Segoe UI", 10)
        self.mono_font = ("Consolas", 9)
        self.root.option_add("*Font", self.ui_font)
        
        self.create_widgets()
        
    def create_widgets(self):
        """Создаёт мягкий современный интерфейс."""
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # ==========================================
        # 1. ШАПКА С ЛОГО И КНОПКАМИ
        # ==========================================
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 20))
        
        # Лого слева — та же иконка, что и в окне
        if self.icon:
            logo_label = ttk.Label(header_frame, image=self.icon)
            logo_label.pack(side=LEFT, padx=(0, 15))
            
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=LEFT, fill=Y)
        ttk.Label(title_frame, text="Proxy Collector", font=("Segoe UI", 18, "bold"), foreground="#2AABEE").pack(anchor=W)
        ttk.Label(title_frame, text="Сбор и проверка MTProto прокси для Telegram", font=("Segoe UI", 9), foreground="gray").pack(anchor=W)

        # Кнопки справа
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=RIGHT)
        
        self.start_btn = ttk.Button(btn_frame, text="▶ Запустить", bootstyle=SUCCESS, width=12, command=self.start_collection)
        self.start_btn.pack(side=LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ Стоп", bootstyle=DANGER, width=12, command=self.stop_collection, state=DISABLED)
        self.stop_btn.pack(side=LEFT, padx=5)
        
        ttk.Separator(btn_frame, orient=VERTICAL).pack(side=LEFT, fill=Y, padx=10)
        
        self.copy_btn = ttk.Button(btn_frame, text="📋 Копировать", bootstyle=INFO, width=14, command=self.copy_to_clipboard)
        self.copy_btn.pack(side=LEFT, padx=5)
        
        self.save_btn = ttk.Button(btn_frame, text="💾 Сохранить", bootstyle=PRIMARY, width=14, command=self.save_results)
        self.save_btn.pack(side=LEFT, padx=5)

        # ==========================================
        # 2. НАСТРОЙКИ
        # ==========================================
        settings_container = ttk.Frame(main_frame)
        settings_container.pack(fill=X, pady=(0, 20))
        settings_container.columnconfigure(0, weight=1)
        settings_container.columnconfigure(1, weight=1)
        
        left_card = ttk.Frame(settings_container, padding=20, style="TFrame")
        left_card.grid(row=0, column=0, sticky=NSEW, padx=(0, 10))
        ttk.Label(left_card, text="⚙️ Параметры проверки", font=("Segoe UI", 11, "bold"), foreground="#2AABEE").grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 15))
        
        self._add_soft_setting(left_card, "Параллельных потоков:", "concurrency_var", 40, 1)
        self._add_soft_setting(left_card, "Таймаут подключения (с):", "connect_timeout_var", 3.0, 2, is_float=True)
        self._add_soft_setting(left_card, "Таймаут ответа (с):", "response_timeout_var", 5.0, 3, is_float=True)
        self._add_soft_setting(left_card, "Лимит прокси (0 = все):", "limit_var", 0, 4)
        
        right_card = ttk.Frame(settings_container, padding=20, style="TFrame")
        right_card.grid(row=0, column=1, sticky=NSEW, padx=(10, 0))
        ttk.Label(right_card, text="🌐 Источники прокси", font=("Segoe UI", 11, "bold"), foreground="#2AABEE").grid(row=0, column=0, sticky=W, pady=(0, 15))
        
        self.source_vars = []
        for i, source in enumerate(DEFAULT_SOURCES):
            var = tk.BooleanVar(value=True)
            self.source_vars.append(var)
            cb = ttk.Checkbutton(right_card, text=source['name'], variable=var)
            cb.grid(row=i+1, column=0, sticky=W, pady=2)
            
        ttk.Label(right_card, text="Свои URL (каждый с новой строки):", foreground="gray").grid(row=len(DEFAULT_SOURCES)+1, column=0, sticky=W, pady=(15, 5))
        
        self.custom_sources_text = scrolledtext.ScrolledText(
            right_card, height=3, font=self.mono_font, 
            bg="#2b2b2b", fg="#e0e0e0", insertbackground="white",
            relief="flat", highlightthickness=1, highlightbackground="#444444", highlightcolor="#2AABEE"
        )
        self.custom_sources_text.grid(row=len(DEFAULT_SOURCES)+2, column=0, sticky=EW, pady=2)

        # ==========================================
        # 3. СТАТУС И ПРОГРЕСС
        # ==========================================
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Готов к работе", font=("Segoe UI", 12, "bold"), foreground="#4CAF50")
        self.status_label.pack(side=LEFT)
        
        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(status_frame, textvariable=self.progress_var, font=("Segoe UI", 10))
        self.progress_label.pack(side=RIGHT)
        
        self.progress_bar = ttk.Progressbar(main_frame, mode='determinate', bootstyle=(INFO, STRIPED))
        self.progress_bar.pack(fill=X, pady=(0, 20))
        
        # ==========================================
        # 4. ТАБЛИЦА РЕЗУЛЬТАТОВ
        # ==========================================
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=BOTH, expand=True, pady=(0, 15))
        
        columns = ("status", "latency", "server", "port", "mode", "dc")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", bootstyle=INFO)
        
        headings = {"status": "Статус", "latency": "Пинг", "server": "Сервер", "port": "Порт", "mode": "Режим", "dc": "DC"}
        widths = {"status": 70, "latency": 80, "server": 250, "port": 70, "mode": 80, "dc": 50}
        
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=CENTER if col != "server" else W)
            
        vsb = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        self.tree.bind("<Button-3>", self.show_context_menu)
        
        # ==========================================
        # 5. ЛОГ
        # ==========================================
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=X)
        ttk.Label(log_frame, text="📜 Лог событий", font=("Segoe UI", 10, "bold"), foreground="gray").pack(anchor=W, pady=(0, 5))
        
        self.output_text = scrolledtext.ScrolledText(
            log_frame, height=6, font=self.mono_font, 
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            relief="flat", highlightthickness=1, highlightbackground="#333333", highlightcolor="#2AABEE",
            state=DISABLED
        )
        self.output_text.pack(fill=X)
        
        self.output_text.tag_config("info", foreground="#569cd6")
        self.output_text.tag_config("success", foreground="#6a9955")
        self.output_text.tag_config("error", foreground="#f44747")
        self.output_text.tag_config("warning", foreground="#ce9178")

    def _add_soft_setting(self, parent, label, var_name, default, row, is_float=False):
        ttk.Label(parent, text=label, foreground="#cccccc").grid(row=row, column=0, sticky=W, pady=8)
        var = tk.DoubleVar(value=default) if is_float else tk.IntVar(value=default)
        setattr(self, var_name, var)
        spin = ttk.Spinbox(parent, from_=0 if not is_float else 0.5, to=100 if not is_float else 10.0, 
                           textvariable=var, width=10, increment=0.5 if is_float else 1)
        spin.grid(row=row, column=1, sticky=W, padx=10)

    # ==========================================
    # ДЕЙСТВИЯ КНОПОК
    # ==========================================
    def copy_to_clipboard(self):
        if not self.working_proxies:
            messagebox.showwarning("Нет данных", "Нет рабочих прокси для копирования!")
            return
        links = "\n".join(r.proxy.tg_link() for r in self.working_proxies)
        self.root.clipboard_clear()
        self.root.clipboard_append(links)
        self.log_message(f"📋 Скопировано {len(self.working_proxies)} ссылок в буфер обмена", "success")

    def save_results(self):
        if not self.working_proxies:
            messagebox.showwarning("Нет данных", "Нет рабочих прокси для сохранения!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"working_proxies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                for result in self.working_proxies:
                    f.write(result.proxy.tg_link() + '\n')
            self.log_message(f"💾 Сохранено {len(self.working_proxies)} прокси в {os.path.basename(filename)}", "success")

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            menu = tk.Menu(self.root, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#2AABEE")
            menu.add_command(label="📋 Копировать ссылку", command=lambda: self.copy_row_link(item))
            menu.post(event.x_root, event.y_root)
    
    def copy_row_link(self, item_id):
        values = self.tree.item(item_id, 'values')
        if values:
            server, port = values[2], values[3]
            for result in self.results:
                if result.proxy.server == server and str(result.proxy.port) == port:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(result.proxy.tg_link())
                    self.log_message(f"📋 Скопировано: {result.proxy.tg_link()[:40]}...", "info")
                    break

    # ==========================================
    # ЛОГИКА СБОРА
    # ==========================================
    def log_message(self, message, tag="info"):
        self.output_text.config(state=NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.output_text.insert(END, f"[{timestamp}] ", "info")
        self.output_text.insert(END, f"{message}\n", tag)
        self.output_text.see(END)
        self.output_text.config(state=DISABLED)
    
    def start_collection(self):
        if self.is_running: return
        self.is_running = True
        self.stop_event.clear()
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        
        for item in self.tree.get_children(): self.tree.delete(item)
        self.results = []
        self.working_proxies = []
        self.progress_bar['value'] = 0
        
        threading.Thread(target=self.run_collection, daemon=True).start()
    
    def stop_collection(self):
        self.stop_event.set()
        self.log_message("⚠️ Отмена задач и остановка...", "warning")
        self.status_label.config(text="Остановка...", foreground="#ce9178")
        self.stop_btn.config(state=DISABLED)
    
    def run_collection(self):
        try:
            self.status_label.config(text="Сбор источников...", foreground="#569cd6")
            self.log_message("🔄 Начинаем сбор прокси...")
            
            sources = [DEFAULT_SOURCES[i] for i, var in enumerate(self.source_vars) if var.get()]
            custom_text = self.custom_sources_text.get("1.0", END).strip()
            if custom_text:
                for line in custom_text.split('\n'):
                    url = line.strip()
                    if url and not url.startswith('#'):
                        sources.append({"name": url, "urls": [url]})
            
            if not sources:
                self.status_label.config(text="Нет источников!", foreground="#f44747")
                self.log_message("❌ Выберите хотя бы один источник", "error")
                self.reset_ui()
                return
            
            proxies, source_results = collect_all(sources, timeout=20.0)
            for s in source_results:
                self.log_message(f"{'✅' if not s.error else '❌'} {s.name}: {len(s.proxies)} прокси" if not s.error else f"❌ {s.name}: {s.error}", "success" if not s.error else "error")
            
            if not proxies:
                self.reset_ui()
                return
            
            limit = self.limit_var.get()
            if limit > 0: proxies = proxies[:limit]
            total = len(proxies)
            
            self.log_message(f"📊 Всего к проверке: {total}", "info")
            self.status_label.config(text=f"Проверка {total} прокси...", foreground="#569cd6")
            
            checked = 0
            working_count = 0
            
            def on_progress(done, total_count, result):
                nonlocal checked, working_count
                checked = done
                if result.ok: working_count += 1
                self.root.after(0, lambda: self.update_ui_progress(done, total_count, working_count, result))
            
            results = check_many(
                proxies,
                concurrency=self.concurrency_var.get(),
                connect_timeout=self.connect_timeout_var.get(),
                response_timeout=self.response_timeout_var.get(),
                on_progress=on_progress,
                stop_event=self.stop_event
            )
            
            self.results = results
            self.working_proxies = [r for r in results if r.ok]
            
            if self.stop_event.is_set():
                self.log_message(f"🛑 Сбор остановлен. Успели проверить {len(results)} прокси, рабочих: {len(self.working_proxies)}", "warning")
                self.status_label.config(text=f"Остановлено. Рабочих: {len(self.working_proxies)}", foreground="#ce9178")
            else:
                final_msg = f"🎉 Готово! Найдено {len(self.working_proxies)} рабочих из {total}" if self.working_proxies else "😞 Рабочих прокси не найдено"
                self.log_message(final_msg, "success" if self.working_proxies else "error")
                self.status_label.config(text=final_msg, foreground="#6a9955" if self.working_proxies else "#f44747")
            
        except Exception as e:
            self.log_message(f" Критическая ошибка: {str(e)}", "error")
            self.status_label.config(text="Ошибка!", foreground="#f44747")
        finally:
            self.reset_ui()

    def update_ui_progress(self, done, total, working_count, result):
        self.progress_bar['value'] = (done / total) * 100
        self.progress_var.set(f"{done} / {total}")
        if result.ok:
            self.tree.insert("", 0, values=(
                "✅ OK", f"{result.rtt_ms:.0f} ms", result.proxy.server, result.proxy.port, result.mode or "-", str(result.dc) or "-"
            ))

    def reset_ui(self):
        self.is_running = False
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)


def main():
    root = ttk.Window(themename="superhero")
    
    app = ProxyCollectorApp(root)
    
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()