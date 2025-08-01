# Голосовой ассистент Ирина v13.0 🚀

**Современный асинхронный голосовой ассистент для Python 3.11+**

Ирина - русский голосовой ассистент для работы оффлайн с полностью переработанной архитектурой. Версия 13.0 представляет собой **кардинальную модернизацию** с переходом на async/await и модульную архитектуру.

[Статья на Хабре](https://habr.com/ru/post/595855/) | [Вторая статья на Хабре](https://habr.com/ru/post/660715/) | [Третья статья на Хабре](https://habr.com/ru/articles/725066/) | [Группа в Телеграм](https://t.me/irene_va)

## 🆕 **Что нового в версии 13.0**

### **Кардинальные изменения архитектуры:**
- ✅ **Полностью асинхронная архитектура** - никаких блокирующих операций
- ✅ **Модульная система компонентов** - микрофон, TTS и веб-API теперь опциональны
- ✅ **Современный Python 3.11+** - использование последних возможностей языка
- ✅ **Чистая структура проекта** - организованная иерархия модулей
- ✅ **Интерфейсы плагинов** - четкие контракты вместо прямых мутаций
- ✅ **Гибкие режимы развертывания** - от headless-сервера до полного голосового ассистента

### **Зачем нужна была модернизация:**
- **Производительность**: синхронная архитектура v12 блокировала выполнение при TTS/аудио операциях
- **Масштабируемость**: невозможность обработки нескольких запросов одновременно  
- **Гибкость развертывания**: жесткая привязка к аудио-зависимостям мешала серверным установкам
- **Качество кода**: устаревшие паттерны Python 3.5 затрудняли разработку и поддержку

## 🚀 **Быстрый старт**

### **Системные требования:**
- **Python 3.11+** (обязательно!)
- **uv** для управления зависимостями (рекомендуется)

### **Установка с uv (рекомендуется):**

```bash
# Установка uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Клонирование проекта
git clone https://github.com/janvarev/Irene-Voice-Assistant.git
cd Irene-Voice-Assistant

# Выбор профиля установки:

# 1. Полный голосовой ассистент (все компоненты)
uv add irene-voice-assistant[voice]

# 2. API-сервер (без аудио)
uv add irene-voice-assistant[api]

# 3. Headless режим (только текст)
uv add irene-voice-assistant[headless]
```

### **Проверка зависимостей:**
```bash
# Проверить, какие компоненты доступны
python -m irene.runners.cli --check-deps
```

### **Запуск:**
```bash
# Простой CLI режим (всегда работает)
python -m irene.runners.cli

# Автоматический режим (выберет лучший доступный профиль)
python -m irene.runners.cli --auto

# Принудительно headless режим
python -m irene.runners.cli --headless

# Полный голосовой режим (если зависимости доступны)
python -m irene.runners.cli --voice
```

## 🏗️ **Режимы развертывания**

### **1. Headless режим** 💻
```bash
python -m irene.runners.cli --headless
```
- **Зависимости:** Только базовые Python пакеты
- **Ввод:** Командная строка
- **Вывод:** Текст в консоль
- **Использование:** Серверы, автоматизация, тестирование

### **2. API сервер** 🌐  
```bash
python -m irene.runners.cli --api
```
- **Зависимости:** FastAPI, uvicorn
- **Ввод:** CLI + REST API + WebSocket
- **Вывод:** Текст + JSON API
- **Использование:** Веб-интеграции, мобильные приложения

### **3. Полный голосовой ассистент** 🎤
```bash
python -m irene.runners.cli --voice
```
- **Зависимости:** VOSK, sounddevice, pyttsx3, FastAPI
- **Ввод:** Микрофон + CLI + Web API
- **Вывод:** TTS + текст + Web API
- **Использование:** Настольные установки, умный дом

### **4. Автоматический режим** 🤖
```bash
python -m irene.runners.cli --auto
```
- Автоматически выбирает лучший доступный режим на основе установленных зависимостей
- Graceful fallback: voice → api → headless

## 📂 **Новая архитектура проекта**

```
irene/                           # Основной пакет v13
├── core/                        # Ядро системы
│   ├── engine.py                # AsyncVACore - основной движок
│   ├── context.py               # Управление контекстом
│   ├── timers.py                # Асинхронные таймеры
│   ├── commands.py              # Обработка команд
│   └── interfaces/              # Интерфейсы компонентов
│       ├── plugin.py            # Базовые интерфейсы плагинов
│       ├── tts.py               # TTS интерфейс
│       ├── audio.py             # Аудио интерфейс
│       └── input.py             # Интерфейсы ввода
├── plugins/                     # Система плагинов
│   ├── manager.py               # Асинхронный менеджер плагинов
│   ├── registry.py              # Обнаружение и загрузка плагинов
│   └── builtin/                 # Встроенные плагины
├── inputs/                      # Источники ввода
│   ├── cli.py                   # Ввод из командной строки
│   ├── microphone.py            # Микрофонный ввод (опционально)
│   └── web.py                   # Веб-ввод (опционально)
├── outputs/                     # Цели вывода
│   ├── text.py                  # Текстовый вывод
│   ├── tts.py                   # TTS вывод (опционально)
│   └── web.py                   # Веб-вывод (опционально)
├── runners/                     # Точки входа
│   └── cli.py                   # CLI раннер
├── config/                      # Управление конфигурацией
│   └── models.py                # Pydantic модели конфигурации
└── utils/                       # Утилиты
    └── logging.py               # Настройка логирования
```

## ⚡ **Ключевые преимущества v13**

### **Производительность:**
- **Истинная асинхронность**: никаких блокирующих операций
- **Конкурентная обработка**: обработка нескольких команд одновременно
- **Быстрый запуск**: ленивая загрузка компонентов
- **Эффективное использование ресурсов**: лучшее управление CPU/памятью

### **Гибкость развертывания:**
- **Headless серверы**: работа без аудио-зависимостей
- **API-only режим**: текстовая обработка без TTS/микрофона
- **Контейнеризация**: минимальные Docker образы для разных сценариев
- **Облачное развертывание**: масштабируемые серверные инстансы

### **Качество кода:**
- **Типобезопасность**: полная совместимость с mypy
- **Чистая архитектура**: правильное разделение ответственности
- **Тестируемость**: внедрение зависимостей и интерфейсы
- **Поддерживаемость**: четкие границы модулей

## 🔌 **Разработка плагинов v13**

### **Новый интерфейс плагинов:**
```python
from irene.core.interfaces.plugin import CommandPlugin
from irene.core.context import Context
from irene.core.commands import CommandResult

class MyCommandPlugin(CommandPlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    @property 
    def version(self) -> str:
        return "1.0.0"
    
    def get_triggers(self) -> list[str]:
        return ["привет", "hello"]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        return any(trigger in command.lower() for trigger in self.get_triggers())
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        return CommandResult(
            success=True,
            response="Привет! Как дела?",
            should_continue_listening=False
        )
```

### **Асинхронные TTS плагины:**
```python
from irene.core.interfaces.tts import TTSPlugin
from pathlib import Path

class MyTTSPlugin(TTSPlugin):
    async def speak(self, text: str, **kwargs) -> None:
        # Асинхронная озвучка
        await self._speak_async(text)
    
    async def to_file(self, text: str, output_path: Path, **kwargs) -> None:
        # Асинхронное сохранение в файл
        await self._save_to_file_async(text, output_path)
```

## ⚠️ **Миграция с v12**

### **Критические изменения:**
- **Python 3.11+** обязателен (было 3.5+)
- **Полностью новый API плагинов** (async/await)
- **Новая структура конфигурации** (TOML вместо JSON)
- **Новые точки входа** (вместо runva_*.py)

### **Помощь в миграции:**
```bash
# Инструменты миграции (в разработке)
python tools/migrate_config.py --from options/core.json --to config.toml
python tools/migrate_plugin.py --plugin plugins/plugin_my.py
```

## 📊 **Конфигурация v13**

Конфигурация теперь использует **TOML** формат с **Pydantic** валидацией:

```toml
# config.toml
[core]
name = "ирина"
version = "13.0.0"
language = "ru"

[components]
microphone = true
tts = true
audio_output = true
web_api = true

[components.microphone]
device = null  # auto-detect
model_path = "model/"

[components.tts]
engine = "pyttsx3"
voice = null  # auto-detect
rate = 150

[components.web_api]
host = "0.0.0.0"
port = 8000
enable_websockets = true

[logging]
level = "INFO"
console = true
file = false
```

## 🧪 **Примеры и демонстрации**

```bash
# Демонстрация асинхронных возможностей
python -m irene.examples.async_demo

# Демонстрация компонентной системы
python -m irene.examples.component_demo

# Демонстрация управления зависимостями
python -m irene.examples.dependency_demo

# Демонстрация плагинной системы
python -m irene.examples.plugin_demo
```

## 🔧 **Отладка и разработка**

### **Проверка статуса компонентов:**
```bash
python -c "
from irene.utils.loader import get_component_status
import json
print(json.dumps(get_component_status(), indent=2))
"
```

### **Запуск с отладкой:**
```bash
# Детальное логирование
python -m irene.runners.cli --log-level DEBUG

# Проверка плагинов
python -m irene.runners.cli --validate-plugins

# Профилирование производительности  
python -m irene.runners.cli --profile
```

## 🐛 **Известные ограничения v13.0**

- **Плагины v12 несовместимы** - требуется миграция
- **Не все TTS движки портированы** - в процессе
- **Веб-интерфейс в разработке** - базовый функционал готов
- **Документация обновляется** - некоторые разделы устарели

## 🤝 **Contributing в эпоху v13**

Мы приветствуем участие в развитии v13! Приоритетные направления:

### **Высокий приоритет:**
- Портирование плагинов v12 на новый API
- Улучшение TTS интеграций
- Расширение веб-API функционала
- Создание миграционных инструментов

### **Средний приоритет:**
- Новые плагины для v13 API
- Улучшение документации
- Примеры использования и туториалы
- Тестирование и исправление багов

### **Как начать:**
1. Изучите новую архитектуру в `irene/examples/`
2. Смотрите встроенные плагины в `irene/plugins/builtin/`
3. Читайте интерфейсы в `irene/core/interfaces/`
4. Создавайте PR с улучшениями!

## 💝 **Поддержка проекта**

Переход на v13 - это **масштабная модернизация**, требующая значительных усилий по поддержке. Если проект полезен:

- 💰 **[Поддержать через Boosty](https://boosty.to/irene-voice)** - помогает продолжать развитие
- 🔧 **Портировать плагины** - сообщество выиграет от ваших усилий  
- 📢 **Рассказать об Ирине** - помочь другим перейти на v13
- 🙏 **Сказать спасибо** в [issues/12](https://github.com/janvarev/Irene-Voice-Assistant/issues/12)

## 🎯 **Roadmap v13**

### **Ближайшие планы:**
- [ ] Завершение портирования основных плагинов
- [ ] Инструменты автоматической миграции v12→v13  
- [ ] Расширенный веб-интерфейс с WebSocket
- [ ] Docker образы для разных профилей развертывания

### **Долгосрочные цели:**
- [ ] Поддержка кластерных развертываний
- [ ] Интеграция с современными AI сервисами
- [ ] Мобильные клиенты
- [ ] Расширенная многоязычность

---

**Ирина v13 - это не просто обновление, это революция в архитектуре голосовых ассистентов! 🚀✨**



