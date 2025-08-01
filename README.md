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
- ✅ **Современные раннеры** - замена всех legacy `runva_*.py` файлов
- ✅ **Основные плагины** - приветствие, дата/время, таймер, генератор случайных чисел, TTS

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

# Показать доступные профили развертывания
python -m irene.runners.cli --list-profiles

# Протестировать основной функционал (работает сейчас!)
python -m irene.runners.cli --test-greeting
```

### **Быстрые команды:**
```bash
# Простой CLI режим (всегда работает)
python -m irene.runners.cli

# Тест приветствия (совместимость с legacy)
python -m irene.runners.cli --test-greeting

# Выполнить одну команду и выйти
python -m irene.runners.cli --command "время"

# Headless режим (без аудио)
python -m irene.runners.cli --headless

# Voice режим (если зависимости доступны)
python -m irene.runners.cli --voice
```

### **🎯 Основные команды уже работают:**
```bash
# Протестируйте основной функционал v13:
python -m irene.runners.cli

# Доступные команды:
> привет              # Случайные приветствия (рус/eng)
> время               # Текущее время с естественной речью  
> дата                # Сегодняшняя дата с днем недели
> подбрось монетку    # Орел или решка
> брось кубик         # Случайное число 1-6
> таймер 10 секунд    # Асинхронный таймер
> help                # Список всех команд
```

## 🏗️ **Современные раннеры v13**

### **1. CLI Раннер** 💻
```bash
# Интерактивный режим
python -m irene.runners.cli

# Одна команда и выход (как legacy runva_cmdline.py)
python -m irene.runners.cli --command "привет"

# Тихий режим
python -m irene.runners.cli --quiet

# С отладкой
python -m irene.runners.cli --debug --log-level DEBUG
```
- **Заменяет:** `runva_cmdline.py`
- **Возможности:** Интерактивный и одноразовый режимы
- **Ввод:** Командная строка
- **Вывод:** Текст в консоль

### **2. VOSK Раннер** 🎤
```bash
# Запуск с моделью по умолчанию
python -m irene.runners.vosk_runner

# Кастомная модель и устройство
python -m irene.runners.vosk_runner --model models/vosk-small --device 2

# Список аудио устройств
python -m irene.runners.vosk_runner --list-devices

# Сохранение аудио
python -m irene.runners.vosk_runner --save-audio recording.wav
```
- **Заменяет:** `runva_vosk.py`
- **Возможности:** Офлайн распознавание речи с VOSK
- **Ввод:** Микрофон + VOSK
- **Вывод:** TTS + текст

### **3. Web API Раннер** 🌐
```bash
# Запуск на localhost:5003
python -m irene.runners.webapi_runner

# Кастомный хост и порт
python -m irene.runners.webapi_runner --host 0.0.0.0 --port 8080

# С SSL
python -m irene.runners.webapi_runner --ssl-cert cert.pem --ssl-key key.pem

# Режим разработки
python -m irene.runners.webapi_runner --reload --debug
```
- **Заменяет:** `runva_webapi.py`
- **Возможности:** FastAPI + WebSocket + автодокументация
- **API docs:** `http://localhost:5003/docs`
- **WebSocket:** `ws://localhost:5003/ws`

### **4. Settings Manager** ⚙️
```bash
# Веб-интерфейс настроек
python -m irene.runners.settings_runner

# Кастомный порт
python -m irene.runners.settings_runner --port 7860

# Без автооткрытия браузера
python -m irene.runners.settings_runner --no-browser
```
- **Заменяет:** `runva_settings_manager.py`
- **Возможности:** Современный Gradio интерфейс
- **URL:** `http://localhost:7860`

### **5. Миграция с legacy** 🔄
```bash
# Анализ legacy файлов
python tools/migrate_runners.py

# Детальная информация
python tools/migrate_runners.py --details

# Создание скрипта миграции
python tools/migrate_runners.py --create-script migrate.sh
```
- **Возможности:** Анализ и миграция с `runva_*.py`
- **Поддержка:** Автогенерация команд миграции

## 📂 **Обновленная архитектура проекта**

```
irene/                           # Основной пакет v13
├── core/                        # Ядро системы
│   ├── engine.py                # AsyncVACore - основной движок
│   ├── context.py               # Управление контекстом
│   ├── timers.py                # Асинхронные таймеры
│   ├── commands.py              # Обработка команд
│   ├── components.py            # Система компонентов ✅
│   └── interfaces/              # Интерфейсы компонентов
│       ├── plugin.py            # Базовые интерфейсы плагинов
│       ├── tts.py               # TTS интерфейс
│       ├── audio.py             # Аудио интерфейс
│       ├── input.py             # Интерфейсы ввода
│       └── command.py           # Командные интерфейсы
├── plugins/                     # Система плагинов
│   ├── manager.py               # Асинхронный менеджер плагинов
│   ├── registry.py              # Обнаружение и загрузка плагинов
│   ├── base.py                  # Базовые классы плагинов
│   └── builtin/                 # Встроенные плагины ✅
│       ├── core_commands.py     # Основные команды
│       ├── timer_plugin.py      # Асинхронные таймеры
│       └── async_service_demo.py # Демо сервисов
├── inputs/                      # Источники ввода
│   ├── base.py                  # Базовые классы ввода
│   ├── cli.py                   # Ввод из командной строки ✅
│   ├── microphone.py            # Микрофонный ввод (опционально)
│   └── web.py                   # Веб-ввод (опционально)
├── outputs/                     # Цели вывода
│   ├── base.py                  # Базовые классы вывода
│   ├── text.py                  # Текстовый вывод ✅
│   ├── tts.py                   # TTS вывод (опционально)
│   └── web.py                   # Веб-вывод (опционально)
├── runners/                     # Современные точки входа ✅
│   ├── cli.py                   # CLI раннер ✅
│   ├── vosk_runner.py           # VOSK раннер ✅
│   ├── webapi_runner.py         # Web API раннер ✅
│   └── settings_runner.py       # Settings Manager ✅
├── config/                      # Управление конфигурацией
│   ├── manager.py               # Менеджер конфигурации ✅
│   └── models.py                # Pydantic модели конфигурации ✅
├── utils/                       # Утилиты
│   ├── logging.py               # Настройка логирования ✅
│   └── loader.py                # Загрузка компонентов ✅
└── examples/                    # Примеры и демонстрации ✅
    ├── async_demo.py            # Демо асинхронности
    ├── component_demo.py        # Демо компонентов
    ├── dependency_demo.py       # Демо зависимостей
    └── phase5_demo.py           # Демо phase 5
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

### **Современные раннеры:**
- **Полная замена legacy**: все `runva_*.py` заменены современными раннерами
- **Consistent CLI**: единообразные опции `--help`, `--check-deps`, `--debug`
- **Graceful fallback**: автоматическая деградация при отсутствии зависимостей
- **Legacy compatibility**: поддержка привычных команд и режимов

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
- **Современные раннеры** (вместо runva_*.py)

### **Таблица миграции раннеров:**

| Legacy файл | v13 раннер | Команда |
|-------------|------------|---------|
| `runva_cmdline.py` | CLI Runner | `python -m irene.runners.cli --command "привет"` |
| `runva_vosk.py` | VOSK Runner | `python -m irene.runners.vosk_runner` |
| `runva_webapi.py` | Web API Runner | `python -m irene.runners.webapi_runner` |
| `runva_settings_manager.py` | Settings Manager | `python -m irene.runners.settings_runner` |
| `runva_speechrecognition.py` | CLI Runner | `python -m irene.runners.cli` (cloud deprecated) |
| `runva_voskrem.py` | Web API Runner | `python -m irene.runners.webapi_runner` (WebSocket) |

### **Автоматическая помощь в миграции:**
```bash
# Анализ legacy файлов в проекте
python tools/migrate_runners.py

# Детальная информация и рекомендации
python tools/migrate_runners.py --details

# Создание исполняемого скрипта миграции
python tools/migrate_runners.py --create-script migrate.sh

# Инструменты конфигурации (в разработке)
python tools/migrate_config.py --from options/core.json --to config.toml
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

# Демонстрация phase 5 (I/O системы)
python -m irene.examples.phase5_demo
```

## 🔧 **Отладка и разработка**

### **Проверка статуса компонентов:**
```bash
# Быстрая проверка всех раннеров
python -m irene.runners.cli --check-deps

# Детальная информация о компонентах
python -c "
from irene.utils.loader import get_component_status
import json
print(json.dumps(get_component_status(), indent=2))
"

# Веб-интерфейс для мониторинга
python -m irene.runners.settings_runner
```

### **Запуск с отладкой:**
```bash
# Детальное логирование CLI
python -m irene.runners.cli --log-level DEBUG

# Отладка VOSK распознавания
python -m irene.runners.vosk_runner --debug

# Отладка Web API сервера
python -m irene.runners.webapi_runner --debug --reload

# Тестирование одной команды
python -m irene.runners.cli --command "время" --debug
```

### **Профилирование и тестирование:**
```bash
# Тест производительности
python -m irene.examples.async_demo --benchmark

# Анализ миграции legacy файлов
python tools/migrate_runners.py --details
```

## 🎯 **Статус v13.0 (Текущий)**

### **✅ Завершено:**
- ✅ **Асинхронная архитектура** - полностью переработана
- ✅ **Система компонентов** - опциональные аудио/TTS/WebAPI
- ✅ **Современные раннеры** - замена всех legacy `runva_*.py`
- ✅ **Интерфейсы плагинов** - чистые async контракты
- ✅ **Основные плагины** - приветствие, дата/время, таймер, random, TTS (console/pyttsx)
- ✅ **Конфигурация TOML** - с Pydantic валидацией
- ✅ **Инструменты миграции** - автоматический анализ и помощь

### **🔄 В разработке (следующие фазы):**
- 🔄 **Реальные I/O компоненты** - полная интеграция микрофона, TTS output, WebAPI
- 🔄 **Расширенные плагины** - audio playback, weather, media controls (21+ плагинов)
- 🔄 **Расширенная Web API** - полнофункциональный FastAPI сервер с WebSocket
- 🔄 **Инструменты конфигурации** - миграция JSON → TOML

### **📋 Известные ограничения:**
- **Расширенные плагины v12 несовместимы** - требуется миграция на async API (21+ плагинов)
- **Реальные аудио компоненты частично интегрированы** - микрофон/WebAPI требуют доработки
- **Некоторая документация устарела** - обновление в процессе

### **🎉 Что уже работает и готово к использованию:**
- ✅ **CLI режим** - полнофункциональная командная строка
- ✅ **Основные команды** - приветствие, время, дата, случайные числа, таймеры
- ✅ **TTS вывод** - консольный и pyttsx3 (при наличии зависимостей)
- ✅ **Async архитектура** - неблокирующая обработка команд
- ✅ **Современные раннеры** - замена всех legacy точек входа

## 🤝 **Contributing в эпоху v13**

Мы приветствуем участие в развитии v13! Приоритетные направления:

### **Высокий приоритет:**
- 🔥 **Интеграция I/O компонентов** - реальные CLIInput, MicrophoneInput, TextOutput
- 🔥 **Web API реализация** - полная FastAPI интеграция с WebSocket
- 🔥 **Портирование расширенных плагинов** - audio playback, weather, media (21+ плагинов)
- 🔥 **Создание миграционных инструментов** - помощь сообществу в переходе

### **Средний приоритет:**
- ⚡ **Новые плагины для v13** - использование современного API
- ⚡ **Улучшение документации** - примеры, туториалы
- ⚡ **Тестирование и исправление багов** - повышение стабильности
- ⚡ **Docker образы** - контейнеризация для разных профилей

### **Как начать:**
1. **Изучите новую архитектуру** в `irene/examples/`
2. **Смотрите современные раннеры** в `irene/runners/`
3. **Анализируйте интерфейсы** в `irene/core/interfaces/`
4. **Тестируйте миграцию** с `tools/migrate_runners.py`
5. **Создавайте PR** с улучшениями!

## 💝 **Поддержка проекта**

Переход на v13 - это **масштабная модернизация**, требующая значительных усилий по поддержке. Если проект полезен:

- 💰 **[Поддержать через Boosty](https://boosty.to/irene-voice)** - помогает продолжать развитие
- 🔧 **Портировать плагины** - сообщество выиграет от ваших усилий  
- 📢 **Рассказать об Ирине** - помочь другим перейти на v13
- 🙏 **Сказать спасибо** в [issues/12](https://github.com/janvarev/Irene-Voice-Assistant/issues/12)

## 🎯 **Roadmap v13**

### **Ближайшие планы (Phases 6-7):**
- [x] **Портирование основных плагинов** - datetime, timer, random, TTS engines ✅ **ЗАВЕРШЕНО**
- [ ] **Реальная интеграция I/O компонентов** - CLIInput, MicrophoneInput, TextOutput, WebInput
- [ ] **Полнофункциональный Web API сервер** - FastAPI + WebSocket + документация
- [ ] **Расширенные плагины** - audio playback, weather, media controls

### **Среднесрочные цели:**
- [ ] **Расширенный веб-интерфейс** - улучшенный Settings Manager
- [ ] **Docker образы для разных профилей** - headless, api, voice
- [ ] **Миграция всех 27+ плагинов** - полная совместимость функций v12
- [ ] **Comprehensive testing suite** - автотесты для всех компонентов

### **Долгосрочные цели:**
- [ ] **Поддержка кластерных развертываний** - распределенная архитектура
- [ ] **Интеграция с современными AI сервисами** - GPT, Claude, local LLM
- [ ] **Мобильные клиенты** - React Native / Flutter приложения
- [ ] **Расширенная многоязычность** - поддержка английского и других языков

---

**Основной функционал v13 уже работает! Протестируйте команды: `привет`, `время`, `дата`, `таймер 10 секунд`. Современные раннеры готовы к использованию.**

---

## 🎉 **Статус: Основные плагины работают!**

V13 теперь имеет **функциональное ядро** с работающими командами. Вы можете:
- ✅ **Запустить CLI** и протестировать основные команды  
- ✅ **Использовать современные раннеры** вместо legacy файлов
- ✅ **Настроить TTS** (console или pyttsx3 при наличии зависимостей)
- ✅ **Разрабатывать новые плагины** на основе v13 API

**Переход на v13 уже оправдан для базового использования!**
