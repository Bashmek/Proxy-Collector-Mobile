# Proxy Collector - Модульная архитектура для Desktop и Mobile

## Структура проекта

```
/workspace
├── src/                          # Исходный код (модульная архитектура)
│   ├── __init__.py
│   ├── core/                     # Ядро бизнес-логики
│   │   └── proxy_collect/        # Оригинальный модуль сбора прокси
│   ├── models/                   # Модели данных
│   │   └── __init__.py           # ProxyLink, CheckResult, AppSettings
│   ├── services/                 # Сервисный слой
│   │   └── __init__.py           # Storage, Clipboard, Notification
│   └── utils/                    # Утилиты
│       └── __init__.py           # Helper функции
├── ui/                           # UI слои
│   ├── desktop/                  # Desktop GUI (Tkinter)
│   │   └── app.py
│   └── mobile/                   # Mobile GUI (Kivy)
│       └── main.py (symlink)
├── tests/                        # Unit тесты
│   └── test_models.py
├── main.py                       # Точка входа для Mobile (Android)
├── app.py                        # Точка входа для Desktop
├── buildozer.spec                # Конфигурация для сборки APK
└── requirements.txt              # Зависимости Python
```

## Ключевые изменения

### 1. Модульная архитектура
- **src/core/** - Бизнес-логика (сбор, проверка, парсинг прокси)
- **src/models/** - Модели данных с поддержкой сериализации
- **src/services/** - Абстракции для платформенно-зависимых операций
- **src/utils/** - Вспомогательные функции

### 2. Разделение UI
- **Desktop** - Tkinter интерфейс (`ui/desktop/app.py`)
- **Mobile** - Kivy интерфейс (`main.py`)

### 3. Сервисный слой
Абстрактные классы для:
- `StorageService` - Работа с файлами/БД
- `ClipboardService` - Буфер обмена
- `NotificationService` - Уведомления

Реализации:
- `DesktopClipboardService` - через Tkinter
- `MobileClipboardService` - через Kivy
- `DesktopNotificationService` - через plyer
- `MobileNotificationService` - через plyer (Android)

### 4. Модели данных
- `ProxyLink` - Модель прокси с методами сериализации
- `CheckResult` - Результат проверки
- `AppSettings` - Настройки приложения

## Запуск

### Desktop версия
```bash
python ui/desktop/app.py
```

### Mobile версия (эмуляция на ПК)
```bash
python main.py
```

### Сборка APK для Android
```bash
# Установка buildozer
pip install buildozer

# Инициализация (если нужно)
buildozer init

# Сборка APK
buildozer android debug

# Сборка релизного APK
buildozer android release
```

## Тестирование
```bash
python -m pytest tests/
# или
python -m unittest discover tests/
```

## Зависимости

### Основные
- kivy>=2.2.0 - Mobile UI framework
- plyer - Кроссплатформенные API (clipboard, notifications)
- requests - HTTP запросы
- certifi - SSL сертификаты

### Для Desktop
- tkinter - Встроен в Python

### Для Android сборки
- buildozer
- python-for-android
- Android SDK & NDK

## Преимущества новой архитектуры

1. **Разделение ответственности** - Логика отделена от UI
2. **Тестируемость** - Unit тесты для моделей и утилит
3. **Кроссплатформенность** - Общая бизнес-логика для Desktop и Mobile
4. **Расширяемость** - Легко добавить новые сервисы или UI
5. **Поддержка мобильных функций** - Уведомления, буфер обмена, разрешения

## Дальнейшие улучшения

- [ ] Добавить SQLite хранение для истории прокси
- [ ] Реализовать фоновую проверку на Android
- [ ] Добавить виджет для быстрого доступа
- [ ] Интеграция с Telegram Deep Linking
- [ ] Поддержка темизации (светлая/тёмная)
- [ ] Локализация (мультиязычность)
