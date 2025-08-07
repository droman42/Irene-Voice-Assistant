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
- ✅ **Современная I/O система** - AsyncIterator для ввода, Response-объекты для вывода
- ✅ **Голосовой ввод** - VOSK распознавание речи с полной интеграцией микрофона
- ✅ **Web API сервер** - FastAPI с WebSocket, REST endpoints и веб-интерфейсом

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

# 4. С мультиязычной поддержкой (lingua-franca)
uv add irene-voice-assistant[text-multilingual]

# 5. С инструментами обучения wake word (TensorFlow)
uv add irene-voice-assistant[wake-word-training]

# 6. Полная установка (все опции)
uv add irene-voice-assistant[all]
```

### **Проверка зависимостей:**
```bash
# Проверить, какие компоненты доступны
uv run python -m irene.runners.cli --check-deps

# Показать доступные профили развертывания
uv run python -m irene.runners.cli --list-profiles

# Протестировать основной функционал (работает сейчас!)
uv run python -m irene.runners.cli --test-greeting

# Протестировать новую I/O систему
uv run python -m irene.examples.io_demo

# Протестировать голосовой ввод (требует VOSK модель)
uv run python -m irene.examples.microphone_demo

# Протестировать полный голосовой ассистент
uv run python -m irene.examples.voice_assistant_demo

# Протестировать Web API (FastAPI + WebSocket)
uv run python -m irene.examples.web_api_demo
```

### **Быстрые команды:**
```bash
# Простой CLI режим (всегда работает)
uv run python -m irene.runners.cli

# Тест приветствия (совместимость с legacy)
uv run python -m irene.runners.cli --test-greeting

# Выполнить одну команду и выйти
uv run python -m irene.runners.cli --command "время"

# Headless режим (без аудио)
uv run python -m irene.runners.cli --headless

# Voice режим (если зависимости доступны)
uv run python -m irene.runners.cli --voice
```

## 🔧 **Конфигурация системы**

### **Новая система конфигурации v13.0:**
- ✅ **Entry-points discovery**: Динамическое обнаружение провайдеров
- ✅ **Configuration-driven filtering**: Загрузка только включенных провайдеров  
- ✅ **Модульная архитектура**: Включение/отключение целых подсистем
- ✅ **19 провайдеров** в 5 категориях (TTS, ASR, LLM, Audio, Voice Trigger)

### **Быстрая настройка:**
```bash
# Скопировать пример конфигурации
cp config-example.toml config.toml

# Настроить переменные окружения (API ключи)
cp docs/env-example.txt .env
# Отредактируйте .env с вашими API ключами

# Запустить с конфигурацией
uv run python -m irene.runners.webapi --config config.toml
```

**📖 Документация**: Полное описание в [`config-example.md`](config-example.md)

**🎛️ Пример фильтрации провайдеров:**
```toml
[plugins.universal_tts.providers.console]
enabled = true    # ← Будет загружен

[plugins.universal_tts.providers.elevenlabs] 
enabled = true    # ← Будет загружен

[plugins.universal_tts.providers.pyttsx]
enabled = false   # ← Будет пропущен
```

### **🎯 Основные команды уже работают:**
```bash
# Протестируйте основной функционал v13:
uv run python -m irene.runners.cli

# Доступные команды:
> привет              # Случайные приветствия (рус/eng)
> время               # Текущее время с естественной речью  
> дата                # Сегодняшняя дата с днем недели
> подбрось монетку    # Орел или решка
> брось кубик         # Случайное число 1-6
> таймер 10 секунд    # Асинхронный таймер
> help                # Список всех команд

# 🎤 Голосовые команды (с установленным VOSK):
uv run python -m irene.runners.vosk_runner

# Произнесите вслух любую из команд выше!
# Система распознает речь и выполнит команду

# 📝 Текстовые утилиты (новое! Phase I):
# Тестирование обработки текста с числами
echo "У меня 123 рубля и 25% скидка" | uv run python -c "
from irene.utils.text_processing import all_num_to_text
import sys
text = sys.stdin.read().strip()
print('Результат:', all_num_to_text(text))
"

# Мультиязычная поддержка (с lingua-franca)
uv add irene-voice-assistant[text-multilingual]  # только при необходимости
```

## 🎯 **Wake Word Training (Обучение активации голоса)**

### **Интегрированная система обучения**
Обучайте собственные модели активации для улучшенного голосового взаимодействия:

```bash
# Установка с инструментами обучения (если работаете в проекте)
uv sync --extra wake-word-training

# Или как внешний пакет:
# uv add irene-voice-assistant[wake-word-training]

# Полный цикл создания wake word модели:
irene-record-samples --wake_word irene --speaker_name your_name --num_samples 50
irene-train-wake-word irene --epochs 55 --batch_size 16
irene-validate-model models/irene_medium_*.tflite

# Конвертация для разных платформ:
irene-convert-to-esp32 models/irene_medium_*.tflite     # → ESP32 firmware 
irene-convert-to-onnx models/irene_medium_*.tflite      # → OpenWakeWord (Python)
irene-convert-to-tflite models/irene_medium_*.tflite    # → microWakeWord (Python)
```

**Поддерживаемые платформы:**
- ✅ **ESP32 firmware** - C заголовки для встраиваемых устройств
- ✅ **Python OpenWakeWord** - ONNX модели для OpenWakeWord provider
- ✅ **Python microWakeWord** - TFLite модели для microWakeWord provider
- ✅ **Унифицированное обучение** - одна система для всех платформ

📖 **Документация**: `wake_word_training/README.md` и `wake_word_training/USAGE_EXAMPLE.md`

## 🏗️ **Современные раннеры v13**

### **1. CLI Раннер** 💻
```bash
# Интерактивный режим
uv run python -m irene.runners.cli

# Одна команда и выход (как legacy runva_cmdline.py)
uv run python -m irene.runners.cli --command "привет"

# Тихий режим
uv run python -m irene.runners.cli --quiet

# С отладкой
uv run python -m irene.runners.cli --debug --log-level DEBUG
```
- **Заменяет:** `runva_cmdline.py`
- **Возможности:** Интерактивный и одноразовый режимы
- **Ввод:** Командная строка (AsyncIterator)
- **Вывод:** Текст в консоль (Response-объекты)

### **2. VOSK Раннер** 🎤
```bash
# Запуск с моделью по умолчанию
uv run python -m irene.runners.vosk_runner

# Кастомная модель и устройство
uv run python -m irene.runners.vosk_runner --model models/vosk-small --device 2

# Список аудио устройств
uv run python -m irene.runners.vosk_runner --list-devices

# Сохранение аудио
uv run python -m irene.runners.vosk_runner --save-audio recording.wav
```
- **Заменяет:** `runva_vosk.py`
- **Возможности:** Офлайн распознавание речи с VOSK
- **Ввод:** Микрофон + VOSK
- **Вывод:** TTS + текст

### **3. Web API Раннер** 🌐
```bash
# Запуск на localhost:5003
uv run python -m irene.runners.webapi_runner

# Кастомный хост и порт
uv run python -m irene.runners.webapi_runner --host 0.0.0.0 --port 8080

# С SSL
uv run python -m irene.runners.webapi_runner --ssl-cert cert.pem --ssl-key key.pem

# Режим разработки
uv run python -m irene.runners.webapi_runner --reload --debug

# С микрофоном и TTS в веб-режиме
uv run python -m irene.runners.webapi_runner --enable-microphone --enable-tts
```
- **Заменяет:** `runva_webapi.py`
- **Возможности:** FastAPI + WebSocket + веб-интерфейс + автодокументация
- **Веб-интерфейс:** `http://localhost:5003`
- **API docs:** `http://localhost:5003/docs`
- **WebSocket:** `ws://localhost:5003/ws`
- **REST API:** `/status`, `/command`, `/history`, `/components`, `/health`
- **Интеграция:** Полная связь с AsyncVACore через WebInput/WebOutput

### **4. Settings Manager** ⚙️
```bash
# Веб-интерфейс настроек
uv run python -m irene.runners.settings_runner

# Кастомный порт
uv run python -m irene.runners.settings_runner --port 7860

# Без автооткрытия браузера
uv run python -m irene.runners.settings_runner --no-browser
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
│       ├── *_tts_plugin.py      # 5 TTS плагинов ✅
│       ├── *_audio_plugin.py    # 5 аудио плагинов ✅
│       └── async_service_demo.py # Демо сервисов
├── inputs/                      # Источники ввода ✅
│   ├── base.py                  # Базовые классы ввода
│   ├── cli.py                   # Ввод из командной строки ✅
│   ├── microphone.py            # Микрофонный ввод ✅
│   └── web.py                   # Веб-ввод (в разработке)
├── outputs/                     # Цели вывода ✅
│   ├── base.py                  # Базовые классы вывода
│   ├── text.py                  # Текстовый вывод ✅
│   ├── tts.py                   # TTS вывод ✅
│   └── web.py                   # Веб-вывод (в разработке)
├── runners/                     # Современные точки входа ✅
│   ├── cli.py                   # CLI раннер ✅
│   ├── vosk_runner.py           # VOSK раннер ✅
│   ├── webapi_runner.py         # Web API раннер ✅
│   └── settings_runner.py       # Settings Manager ✅
├── config/                      # Управление конфигурацией
│   ├── manager.py               # Менеджер конфигурации ✅
│   └── models.py                # Pydantic модели конфигурации ✅
├── utils/                       # Утилиты ✅
│   ├── logging.py               # Настройка логирования ✅
│   ├── loader.py                # Загрузка компонентов ✅
│   ├── text_processing.py       # Обработка текста и число-в-текст ✅
│   └── audio_helpers.py         # Аудио-утилиты и обработка ✅
└── examples/                    # Примеры и демонстрации ✅
    ├── async_demo.py            # Демо асинхронности
    ├── component_demo.py        # Демо компонентов
    ├── dependency_demo.py       # Демо зависимостей
    ├── phase5_demo.py           # Демо phase 5
    └── io_demo.py               # Демо I/O системы ✅
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

### **Современная I/O система:**
- **AsyncIterator ввод**: неблокирующие потоки команд из любых источников
- **Response-объекты вывод**: структурированные ответы с метаданными и типизацией
- **Цветной консольный вывод**: автоматическая поддержка colorama для лучшего UX
- **Грэйсфул деградация**: автоматические fallback при отсутствии зависимостей
- **Голосовой ввод**: VOSK распознавание речи с офлайн обработкой команд
- **Аудио устройства**: автоматическое обнаружение и конфигурация микрофонов

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

### **Современные Input/Output плагины:**
```python
from irene.inputs.base import InputSource
from irene.outputs.base import OutputTarget, Response
from typing import AsyncIterator

class MyInputSource(InputSource):
    async def listen(self) -> AsyncIterator[str]:
        while self._listening:
            command = await self._get_command_async()
            if command:
                yield command

class MyOutputTarget(OutputTarget):
    async def send(self, response: Response) -> None:
        # Отправка структурированного ответа
        await self._send_response_async(response.text, response.response_type)
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
| `runva_cmdline.py` | CLI Runner | `uv run python -m irene.runners.cli --command "привет"` |
| `runva_vosk.py` | VOSK Runner | `uv run python -m irene.runners.vosk_runner` |
| `runva_webapi.py` | Web API Runner | `uv run python -m irene.runners.webapi_runner` |
| `runva_settings_manager.py` | Settings Manager | `uv run python -m irene.runners.settings_runner` |
| `runva_speechrecognition.py` | CLI Runner | `uv run python -m irene.runners.cli` (cloud deprecated) |
| `runva_voskrem.py` | Web API Runner | `uv run python -m irene.runners.webapi_runner` (WebSocket) |

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

### **Optional Dependencies (pyproject.toml):**
```toml
[project.optional-dependencies]
# Аудио ввод компоненты
audio-input = ["vosk>=0.3.45", "sounddevice>=0.4.0", "soundfile>=0.12.0"]

# TTS движки
tts = ["pyttsx3>=2.90", "elevenlabs>=1.0.3"]

# Аудио вывод
audio-output = ["sounddevice>=0.4.0", "soundfile>=0.12.0", "audioplayer>=0.6.0"]

# Web API сервер
web-api = ["fastapi>=0.100.0", "uvicorn[standard]>=0.20.0", "websockets>=11.0.0"]

# Мультиязычная поддержка текста (новое!)
text-multilingual = ["lingua-franca>=0.4.0"]

# Профили установки
voice = ["irene-voice-assistant[audio-input,tts,audio-output,web-api,text-multilingual]"]
api = ["irene-voice-assistant[web-api]"]
headless = []  # минимальная установка, только текст
```

## 🧪 **Примеры и демонстрации**

```bash
# Демонстрация асинхронных возможностей
uv run python -m irene.examples.async_demo

# Демонстрация компонентной системы
uv run python -m irene.examples.component_demo

# Демонстрация управления зависимостями
uv run python -m irene.examples.dependency_demo

# Демонстрация I/O системы (новое!) ✅
uv run python -m irene.examples.io_demo

# Демонстрация голосового ввода (новое!) ✅
uv run python -m irene.examples.microphone_demo

# Демонстрация полного голосового ассистента (новое!) ✅
uv run python -m irene.examples.voice_assistant_demo

# Демонстрация аудио плейбек системы (новое!) ✅
uv run python -m irene.examples.audio_demo

# Демонстрация TTS движков (новое!) ✅
uv run python -m irene.examples.tts_demo

# Демонстрация утилит обработки текста (новое!) ✅
uv run python -m irene.examples.text_processing_demo

# Демонстрация всех мигрированных утилит (новое!) ✅
uv run python -m irene.examples.utilities_demo

# Демонстрация мультиязычной поддержки (новое!) ✅
uv run python -m irene.examples.multilingual_demo

# Демонстрация phase 5 (I/O системы - legacy)
uv run python -m irene.examples.phase5_demo
```

## 🔧 **Отладка и разработка**

### **Проверка статуса компонентов:**
```bash
# Быстрая проверка всех раннеров
uv run python -m irene.runners.cli --check-deps

# Детальная информация о компонентах
uv run python -c "
from irene.utils.loader import get_component_status
import json
print(json.dumps(get_component_status(), indent=2))
"

# Веб-интерфейс для мониторинга
uv run python -m irene.runners.settings_runner
```

### **Запуск с отладкой:**
```bash
# Детальное логирование CLI
uv run python -m irene.runners.cli --log-level DEBUG

# Отладка VOSK распознавания
uv run python -m irene.runners.vosk_runner --debug

# Отладка Web API сервера
uv run python -m irene.runners.webapi_runner --debug --reload

# Тестирование одной команды
uv run python -m irene.runners.cli --command "время" --debug
```

### **Профилирование и тестирование:**
```bash
# Тест производительности
uv run python -m irene.examples.async_demo --benchmark

# Анализ миграции legacy файлов
python tools/migrate_runners.py --details

# Тестирование I/O системы
uv run python -m irene.examples.io_demo

# Тестирование голосового ввода
uv run python -m irene.examples.microphone_demo

# Тестирование голосового ассистента
uv run python -m irene.examples.voice_assistant_demo

# Тестирование аудио плейбек системы
uv run python -m irene.examples.audio_demo

# Тестирование TTS движков
uv run python -m irene.examples.tts_demo

# Тестирование Web API и WebSocket
uv run python -m irene.examples.web_api_demo

# Тестирование утилит обработки текста (новое!)
uv run python -m irene.examples.text_processing_demo

# Тестирование всех мигрированных утилит (новое!)
uv run python -m irene.examples.utilities_demo

# Тестирование мультиязычной поддержки (новое!)
uv run python -m irene.examples.multilingual_demo
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
- ✅ **Essential I/O Implementation** - современная система ввода/вывода
- ✅ **Микрофонный ввод** - VOSK речевое распознавание с async обработкой
- ✅ **Web API сервер** - FastAPI с WebSocket, REST API и веб-интерфейсом

### **✅ Дополнительно завершено:**
- ✅ **Аудио плейбек система** - полная система воспроизведения звуков и аудио файлов (5 плагинов)
  - **SoundDevice** - высококачественный звук с выбором устройств (sounddevice + soundfile)
  - **AudioPlayer** - кроссплатформенное воспроизведение (audioplayer)
  - **Aplay** - Linux ALSA через команду aplay (без Python зависимостей)
  - **SimpleAudio** - легковесное WAV воспроизведение (simpleaudio)
  - **Console** - отладочный вывод с имитацией времени (всегда доступен)

### **✅ Дополнительно завершено:**
- ✅ **Продвинутые TTS движки** - нейронные TTS с высоким качеством (3 плагина):
  - **Silero v3** - нейронный TTS с PyTorch 1.10+, множественные спикеры (xenia, aidar, baya, kseniya, eugene)
  - **Silero v4** - улучшенный нейронный TTS с PyTorch 2.0+, оптимизирован для производительности
  - **VOSK TTS** - русский TTS с поддержкой GPU, множественные ID спикеров, ONNX runtime

### **✅ Phase I: Essential Utilities Migration завершен:**
- ✅ **Современные утилиты обработки текста** - полная миграция legacy `utils/` в v13:
  - **Русская число-в-текст конвертация** - с async поддержкой (`num_to_text_ru`, `decimal_to_text_ru`)
  - **Мультиязычная поддержка** - интеграция с lingua-franca (опциональная зависимость)
  - **Текстовая нормализация** - современная обработка чисел в тексте (`all_num_to_text`)
  - **Async версии всех утилит** - неблокирующие операции для v13 интеграции
- ✅ **Аудио-утилиты** - вспомогательные функции для аудио обработки:
  - **Валидация аудио файлов** - проверка поддерживаемых форматов
  - **Обнаружение аудио устройств** - автоматическое выявление микрофонов и динамиков
  - **Конвертация аудио** - изменение частоты дискретизации и форматов
  - **Буферизация аудио** - расчет оптимальных размеров буферов
- ✅ **Очистка репозитория** - удаление встроенных зависимостей:
  - **Удален embedded lingua_franca/** - 100+ файлов, теперь опциональная зависимость
  - **Добавлена опциональная группа** - `irene-voice-assistant[text-multilingual]`
  - **Graceful fallback** - работа без мультиязычной поддержки

### **🔄 В разработке (следующие фазы):**
- 🔄 **Расширенные плагины** - weather, media controls (13+ плагинов)
- 🔄 **Инструменты конфигурации** - миграция JSON → TOML

### **📋 Известные ограничения:**
- **Расширенные плагины v12 несовместимы** - требуется миграция на async API (13+ плагинов)
- **Некоторая документация устарела** - обновление в процессе

### **🎉 Что уже работает и готово к использованию:**
- ✅ **CLI режим** - полнофункциональная командная строка с современной I/O
- ✅ **Основные команды** - приветствие, время, дата, случайные числа, таймеры
- ✅ **TTS вывод** - консольный, pyttsx3, и продвинутые нейронные TTS (Silero v3/v4, VOSK)
- ✅ **Аудио плейбек** - 5 полных backend'ов (SoundDevice, AudioPlayer, Aplay, SimpleAudio, Console)
- ✅ **Async архитектура** - неблокирующая обработка команд
- ✅ **Современные раннеры** - замена всех legacy точек входа
- ✅ **I/O система** - CLIInput, TextOutput, TTSOutput полностью готовы
- ✅ **Голосовой ввод** - MicrophoneInput с VOSK распознаванием речи
- ✅ **Web API сервер** - FastAPI с WebSocket, REST API и веб-интерфейсом
- ✅ **Текстовые утилиты** - современная обработка текста и число-в-текст конвертация
- ✅ **Аудио утилиты** - набор функций для работы с аудио файлами и устройствами
- ✅ **Мультиязычная поддержка** - опциональная интеграция с lingua-franca
- ✅ **Чистый репозиторий** - удалены embedded зависимости, современная структура

## 🤝 **Contributing в эпоху v13**

Мы приветствуем участие в развитии v13! Приоритетные направления:

### **Высокий приоритет:**
- 🔥 **Портирование расширенных плагинов** - weather, media controls (13+ плагинов)
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
4. **Тестируйте I/O систему** с `uv run python -m irene.examples.io_demo`
5. **Тестируйте миграцию** с `tools/migrate_runners.py`
6. **Создавайте PR** с улучшениями!

## 💝 **Поддержка проекта**

Переход на v13 - это **масштабная модернизация**, требующая значительных усилий по поддержке. Если проект полезен:

- 💰 **[Поддержать через Boosty](https://boosty.to/irene-voice)** - помогает продолжать развитие
- 🔧 **Портировать плагины** - сообщество выиграет от ваших усилий  
- 📢 **Рассказать об Ирине** - помочь другим перейти на v13
- 🙏 **Сказать спасибо** в [issues/12](https://github.com/janvarev/Irene-Voice-Assistant/issues/12)

## 🎯 **Roadmap v13**

### **Ближайшие планы (Phases 6-7):**
- [x] **Портирование основных плагинов** - datetime, timer, random, TTS engines ✅ **ЗАВЕРШЕНО**
- [x] **Essential I/O Implementation** - CLIInput, TextOutput, TTSOutput ✅ **ЗАВЕРШЕНО**
- [x] **Микрофонный ввод** - VOSK речевое распознавание ✅ **ЗАВЕРШЕНО**
- [x] **Web API сервер** - FastAPI + WebSocket + веб-интерфейс ✅ **ЗАВЕРШЕНО**
- [x] **Аудио плейбек система** - воспроизведение звуков и аудио файлов (5 плагинов) ✅ **ЗАВЕРШЕНО**
- [x] **Продвинутые TTS движки** - Silero v3/v4, VOSK TTS (3 плагина) ✅ **ЗАВЕРШЕНО**
- [ ] **Расширенные плагины** - weather, media controls (13+ плагинов)

### **Среднесрочные цели:**
- [ ] **Расширенный веб-интерфейс** - улучшенный Settings Manager
- [ ] **Docker образы для разных профилей** - headless, api, voice
- [ ] **Миграция всех 27+ плагинов** - полная совместимость функций v12 (16+ остается)
- [ ] **Comprehensive testing suite** - автотесты для всех компонентов

### **Долгосрочные цели:**
- [ ] **Поддержка кластерных развертываний** - распределенная архитектура
- [ ] **Интеграция с современными AI сервисами** - GPT, Claude, local LLM
- [ ] **Мобильные клиенты** - React Native / Flutter приложения
- [ ] **Расширенная многоязычность** - поддержка английского и других языков

---

**Основной функционал v13 уже работает! Протестируйте команды: `привет`, `время`, `дата`, `таймер 10 секунд`. Современные раннеры и I/O система готовы к использованию.**

---

## 🎉 **Статус: Web API сервер готов!**

V13 теперь имеет **полноценный Web API сервер** с современным веб-интерфейсом. Вы можете:
- ✅ **Использовать веб-интерфейс** с интерактивным чатом и управлением
- ✅ **Подключаться через WebSocket** для режима реального времени
- ✅ **Использовать REST API** для интеграции с внешними приложениями
- ✅ **Использовать голосовые команды** с VOSK распознаванием речи
- ✅ **Запустить CLI** с современным AsyncIterator вводом и Response-объектами вывода
- ✅ **Использовать современные раннеры** вместо legacy файлов
- ✅ **Настроить TTS** (console или pyttsx3 при наличии зависимостей)
- ✅ **Разрабатывать новые плагины** на основе v13 API
- ✅ **Тестировать I/O систему** с помощью `uv run python -m irene.examples.io_demo`
- ✅ **Тестировать голосовой ввод** с помощью `uv run python -m irene.examples.microphone_demo`
- ✅ **Тестировать аудио плейбек** с помощью `uv run python -m irene.examples.audio_demo`
- ✅ **Тестировать TTS движки** с помощью `uv run python -m irene.examples.tts_demo`
- ✅ **Тестировать Web API** с помощью `uv run python -m irene.examples.web_api_demo`
- ✅ **Тестировать текстовые утилиты** с помощью `uv run python -m irene.examples.text_processing_demo`
- ✅ **Тестировать все утилиты** с помощью `uv run python -m irene.examples.utilities_demo`
- ✅ **Тестировать мультиязычность** с помощью `uv run python -m irene.examples.multilingual_demo`
