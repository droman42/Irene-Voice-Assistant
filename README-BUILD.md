# Система Сборки Irene Voice Assistant

Этот документ описывает новую систему сборки Irene Voice Assistant, основанную на динамических метаданных entry-points, которая заменила статические зависимости и обеспечивает полную автоматизацию сборки.

## 📋 Содержание

- [Обзор системы сборки](#обзор-системы-сборки)
- [Анализатор сборки](#анализатор-сборки)
- [Docker сборка](#docker-сборка)
- [Установка Linux сервиса](#установка-linux-сервиса)
- [Валидатор зависимостей](#валидатор-зависимостей)
- [Внешние пакеты](#внешние-пакеты)

## 🏗️ Обзор системы сборки

### Архитектурная революция

Новая система сборки Irene полностью исключает жестко закодированные зависимости в пользу динамического анализа метаданных entry-points.

**ДО (статическая система):**
```python
# Жестко закодированные зависимости
PROVIDER_SYSTEM_DEPENDENCIES = {
    "sounddevice": ["libportaudio2", "libsndfile1"],
    "whisper": ["ffmpeg"],
    # ... 77 статических записей
}
```

**ПОСЛЕ (динамическая система):**
```python
# Динамические запросы метаданных
provider_class = dynamic_loader.get_provider_class(namespace, provider_name)
python_deps = provider_class.get_python_dependencies()
platform_deps = provider_class.get_platform_dependencies()
```

### Ключевые возможности

- **🔍 Динамическое обнаружение**: Автоматическое обнаружение всех entry-points из pyproject.toml
- **🖥️ Мультиплатформенность**: Нативная поддержка Ubuntu, Alpine, CentOS, macOS
- **📦 Минимальные сборки**: Точный анализ зависимостей для каждой конфигурации
- **🔌 Внешние пакеты**: Готовность к интеграции сторонних расширений
- **✅ Валидация**: Комплексная проверка метаданных и зависимостей

## 🔍 Анализатор сборки

Анализатор сборки (`irene/tools/build_analyzer.py`) - это основной инструмент для анализа требований времени выполнения на основе TOML конфигураций.

### Основное использование

```bash
# Анализ конкретной конфигурации
uv run python -m irene.tools.build_analyzer --config configs/minimal.toml

# Анализ для конкретной платформы
uv run python -m irene.tools.build_analyzer \
    --config configs/voice.toml \
    --platform alpine

# Генерация Docker команд
uv run python -m irene.tools.build_analyzer \
    --config configs/full.toml \
    --platform ubuntu \
    --docker

# JSON вывод для автоматизации
uv run python -m irene.tools.build_analyzer \
    --config configs/voice.toml \
    --platform alpine \
    --json
```

### Поддерживаемые платформы

| Платформа | Менеджер пакетов | Использование |
|-----------|------------------|---------------|
| `ubuntu` | apt | Ubuntu/Debian системы |
| `alpine` | apk | Alpine Linux (ARM/контейнеры) |
| `centos` | yum/dnf | CentOS/RHEL системы |
| `macos` | brew | macOS системы |

### Пример вывода

```bash
$ uv run python -m irene.tools.build_analyzer --config configs/voice.toml --platform alpine

🔍 Анализ сборки для профиля: voice
📦 Python модули: 22
  - irene.providers.audio.sounddevice
  - irene.providers.tts.elevenlabs
  - irene.providers.asr.whisper
  # ... дополнительные модули

🖥️ Системные пакеты (alpine): 6
  - portaudio-dev
  - libsndfile-dev
  - ffmpeg
  - espeak
  - espeak-data

🐍 Python зависимости: 18
  - sounddevice>=0.4.0
  - elevenlabs>=1.0.3
  - openai-whisper>=20230314
  # ... дополнительные зависимости

✅ Валидация: УСПЕШНА
```

### Доступные профили конфигурации

```bash
# Просмотр всех доступных профилей
uv run python -m irene.tools.build_analyzer --list-profiles

# Результат:
# minimal.toml    - Минимальная конфигурация (текстовая обработка)
# voice.toml      - Голосовой помощник
# api-only.toml   - Только API сервер
# full.toml       - Полная конфигурация
# embedded-armv7.toml - ARM встроенные системы
```

## 🐳 Docker сборка

Новая система Docker сборки использует динамический анализ для создания оптимизированных образов для разных платформ.

### ARM (ARMv7) сборка

```bash
# Сборка для ARM устройств (Alpine Linux)
docker build -f Dockerfile.armv7 \
    --build-arg CONFIG_PROFILE=voice \
    --platform linux/arm/v7 \
    -t irene-voice-assistant:armv7 .

# Запуск ARM контейнера
docker run -it \
    --device /dev/snd \
    -v /path/to/models:/app/models \
    irene-voice-assistant:armv7
```

### x86_64 сборка

```bash
# Сборка для x86_64 (Ubuntu)
docker build -f Dockerfile.x86_64 \
    --build-arg CONFIG_PROFILE=full \
    --platform linux/amd64 \
    -t irene-voice-assistant:x86_64 .

# Запуск x86_64 контейнера
docker run -it \
    --device /dev/snd \
    -p 8000:8000 \
    -v /path/to/models:/app/models \
    irene-voice-assistant:x86_64
```

### Переменные сборки

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `CONFIG_PROFILE` | Профиль конфигурации | `voice` |
| `PYTHON_VERSION` | Версия Python | `3.11` |
| `UV_VERSION` | Версия UV | `latest` |

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  irene-voice:
    build:
      context: .
      dockerfile: Dockerfile.x86_64
      args:
        CONFIG_PROFILE: voice
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./configs:/app/configs
    devices:
      - /dev/snd
    environment:
      - IRENE_CONFIG_PATH=/app/configs/voice.toml
      - IRENE_MODELS_ROOT=/app/models
```

### Мультиплатформенная сборка

```bash
# Настройка buildx для мультиплатформенности
docker buildx create --name irene-builder --use
docker buildx inspect --bootstrap

# Сборка для обеих платформ
docker buildx build \
    --platform linux/amd64,linux/arm/v7 \
    --build-arg CONFIG_PROFILE=voice \
    -t irene-voice-assistant:latest \
    --push .
```

## 🛠️ Установка Linux сервиса

### Системные требования

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3 python3-pip curl

# CentOS/RHEL
sudo yum update
sudo yum install -y python3 python3-pip curl

# Установка UV
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### Автоматическая установка

```bash
# Загрузка и выполнение скрипта установки
curl -sSL https://raw.githubusercontent.com/user/irene-voice-assistant/main/install-irene.sh | bash

# Или локальная установка
chmod +x install-irene.sh
./install-irene.sh
```

### Ручная установка

```bash
# 1. Клонирование репозитория
git clone https://github.com/user/irene-voice-assistant.git
cd irene-voice-assistant

# 2. Анализ зависимостей для вашей системы
uv run python -m irene.tools.build_analyzer \
    --config configs/voice.toml \
    --platform ubuntu \
    --system-install

# 3. Установка системных зависимостей
sudo apt-get update
sudo apt-get install -y libportaudio2 libsndfile1 espeak espeak-data

# 4. Установка Python зависимостей
uv sync
uv run pip install -e .

# 5. Создание конфигурации
cp configs/voice.toml ~/.config/irene/config.toml
# Отредактируйте конфигурацию под ваши нужды

# 6. Создание systemd сервиса
sudo tee /etc/systemd/system/irene-voice.service > /dev/null <<EOF
[Unit]
Description=Irene Voice Assistant
After=network.target sound.target

[Service]
Type=simple
User=irene
Group=audio
WorkingDirectory=/opt/irene-voice-assistant
Environment=PATH=/opt/irene-voice-assistant/.venv/bin
ExecStart=/opt/irene-voice-assistant/.venv/bin/python -m irene.runners.webapi_runner
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 7. Запуск сервиса
sudo systemctl daemon-reload
sudo systemctl enable irene-voice
sudo systemctl start irene-voice
```

### Управление сервисом

```bash
# Проверка статуса
sudo systemctl status irene-voice

# Просмотр логов
sudo journalctl -u irene-voice -f

# Перезапуск сервиса
sudo systemctl restart irene-voice

# Остановка сервиса
sudo systemctl stop irene-voice

# Отключение автозапуска
sudo systemctl disable irene-voice
```

### Конфигурация сервиса

```toml
# ~/.config/irene/config.toml
[providers.audio]
enabled = ["sounddevice"]

[providers.tts]
enabled = ["pyttsx"]

[providers.asr]
enabled = ["vosk"]

[components]
enabled = ["audio", "tts", "asr", "intent_system"]

[workflows]
enabled = ["voice_assistant"]

[webapi]
host = "0.0.0.0"
port = 8000
```

## ✅ Валидатор зависимостей

Валидатор зависимостей (`irene/tools/dependency_validator.py`) - это инструмент для проверки корректности метаданных entry-points и их зависимостей.

### Основные возможности

- **🔍 Анализ импорта**: Динамическая загрузка и проверка классов entry-points
- **📦 Проверка зависимостей**: Сопоставление с pyproject.toml
- **🖥️ Валидация пакетов**: Проверка системных пакетов для платформ
- **⚡ Тестирование производительности**: Измерение времени выполнения методов метаданных
- **🔄 Кроссплатформенность**: Валидация для нескольких платформ одновременно

### Основное использование

#### Валидация одного entry-point

```bash
# Проверка конкретного провайдера для платформы
uv run python -m irene.tools.dependency_validator \
    --file irene/providers/audio/sounddevice.py \
    --class SoundDeviceAudioProvider \
    --platform ubuntu

# Результат:
# 🔍 Результат валидации: ✅ ВАЛИДНО
# 📁 Entry-point: irene/providers/audio/sounddevice.py:SoundDeviceAudioProvider
# 🖥️ Платформа: ubuntu
# ⏱️ Производительность: 0.1ms
```

#### Комплексная валидация

```bash
# Валидация всех entry-points для одной платформы
uv run python -m irene.tools.dependency_validator \
    --validate-all \
    --platform alpine

# Кроссплатформенная валидация для CI/CD
uv run python -m irene.tools.dependency_validator \
    --validate-all \
    --platforms ubuntu,alpine,centos,macos

# JSON вывод для автоматизации
uv run python -m irene.tools.dependency_validator \
    --validate-all \
    --platform ubuntu \
    --json
```

### Пример вывода валидации

```bash
$ uv run python -m irene.tools.dependency_validator --validate-all --platform ubuntu

🔍 Отчет о валидации зависимостей
==================================================
📊 Сводка: 47/53 валидаций прошли успешно
❌ Ошибки: 14
⚠️ Предупреждения: 143

🖥️ Сводка по платформам:
  ❌ ubuntu: 47/53 прошли, 14 ошибок, 143 предупреждения

❌ Неудачные валидации:
  irene.workflows.voice_assistant@ubuntu:
    ERROR: Не удалось импортировать модуль 'irene.workflows.voice_assistant'
  irene.runners.cli@ubuntu:
    ERROR: Отсутствует обязательный метод: get_python_dependencies
    ERROR: Отсутствует обязательный метод: get_platform_dependencies
    ERROR: Отсутствует обязательный метод: get_platform_support
```

### JSON формат для автоматизации

```json
{
  "summary": {
    "total_entry_points": 53,
    "successful_validations": 47,
    "failed_validations": 6,
    "total_errors": 14,
    "total_warnings": 143
  },
  "platform_summary": {
    "ubuntu": {
      "total": 53,
      "passed": 47,
      "failed": 6,
      "errors": 14,
      "warnings": 143
    }
  },
  "validation_results": {
    "irene.providers.audio.sounddevice@ubuntu": {
      "entry_point": "irene/providers/audio/sounddevice.py:SoundDeviceAudioProvider",
      "platform": "ubuntu",
      "is_valid": true,
      "errors": [],
      "warnings": [],
      "performance_ms": 0.1,
      "import_successful": true,
      "metadata_methods_exist": true,
      "python_deps_valid": true,
      "system_packages_valid": true,
      "platform_consistency_valid": true
    }
  }
}
```

### Интеграция с CI/CD

#### GitHub Actions

```yaml
# .github/workflows/validate-dependencies.yml
name: Валидация зависимостей
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Установка UV
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
        
      - name: Валидация зависимостей
        run: |
          source ~/.cargo/env
          uv run python -m irene.tools.dependency_validator \
            --validate-all \
            --platforms ubuntu,alpine \
            --json > validation-report.json
            
      - name: Загрузка отчета
        uses: actions/upload-artifact@v3
        with:
          name: validation-report
          path: validation-report.json
```

#### Pre-commit hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
echo "Проверка валидации зависимостей..."

# Получить измененные файлы Python
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' | grep -E '(providers|components|workflows|inputs|outputs|plugins)/')

if [ -n "$CHANGED_FILES" ]; then
    echo "Найдены измененные entry-point файлы, запуск валидации..."
    
    if ! uv run python -m irene.tools.dependency_validator --validate-all --platform ubuntu; then
        echo "❌ Валидация зависимостей не прошла!"
        exit 1
    fi
    
    echo "✅ Валидация зависимостей прошла успешно!"
fi
```

### Типы проверок

#### 1. Анализ импорта
- Динамическая загрузка модулей entry-points
- Проверка существования классов
- Валидация наследования от базовых классов

#### 2. Проверка методов метаданных
- `get_python_dependencies()` возвращает `List[str]`
- `get_platform_dependencies()` возвращает `Dict[str, List[str]]`
- `get_platform_support()` возвращает `List[str]`

#### 3. Валидация Python зависимостей
- Сопоставление с `pyproject.toml` optional-dependencies
- Проверка корректности спецификаций версий
- Выявление отсутствующих зависимостей

#### 4. Проверка системных пакетов
- Валидация против известных репозиториев пакетов
- Проверка соответствия соглашениям именования
- Платформенная совместимость

#### 5. Тестирование производительности
- Измерение времени выполнения методов метаданных
- Пороговое значение < 100ms
- Выявление медленных реализаций

## 🔌 Внешние пакеты

Новая система сборки полностью готова для интеграции внешних пакетов.

### Создание совместимого пакета

#### 1. Реализация интерфейса метаданных

```python
# your_package/providers/my_provider.py
from irene.core.metadata import EntryPointMetadata
from irene.providers.base import ProviderBase

class MyCustomProvider(ProviderBase, EntryPointMetadata):
    """Пользовательский провайдер."""
    
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Python зависимости."""
        return ["requests>=2.28.0", "numpy>=1.21.0"]
    
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Системные зависимости по платформам."""
        return {
            "ubuntu": ["libssl-dev", "libcurl4-openssl-dev"],
            "alpine": ["openssl-dev", "curl-dev"],
            "centos": ["openssl-devel", "libcurl-devel"],
            "macos": []  # Homebrew управляет зависимостями
        }
    
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Поддерживаемые платформы."""
        return ["linux", "macos", "windows"]
    
    # Методы конфигурации активов
    @classmethod
    def _get_default_extension(cls) -> str:
        return ".json"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        return ["MY_API_KEY", "MY_SECRET_TOKEN"]
```

#### 2. Регистрация entry-points

```toml
# pyproject.toml вашего пакета
[project.entry-points."irene.providers.custom"]
my_provider = "your_package.providers.my_provider:MyCustomProvider"
```

#### 3. Валидация вашего пакета

```bash
# Проверка вашего провайдера
uv run python -m irene.tools.dependency_validator \
    --file your_package/providers/my_provider.py \
    --class MyCustomProvider \
    --platform ubuntu

# Валидация всех entry-points вашего пакета
uv run python -m irene.tools.dependency_validator \
    --validate-all \
    --platforms ubuntu,alpine,macos
```

### Использование внешнего пакета

```toml
# configs/custom.toml
[providers.custom]
enabled = ["my_provider"]

[components]
enabled = ["audio", "tts", "my_custom_component"]
```

```bash
# Анализ конфигурации с внешним пакетом
uv run python -m irene.tools.build_analyzer \
    --config configs/custom.toml \
    --platform ubuntu
```

### Лучшие практики для внешних пакетов

#### Метаданные
- ✅ Реализуйте все методы интерфейса `EntryPointMetadata`
- ✅ Используйте конкретные версии зависимостей (`>=`, `==`)
- ✅ Предоставьте платформенные зависимости для всех поддерживаемых платформ
- ✅ Тестируйте производительность методов метаданных

#### Зависимости
- ✅ Минимизируйте количество зависимостей
- ✅ Используйте optional-dependencies для группировки
- ✅ Избегайте конфликтов версий с основным пакетом
- ✅ Документируйте системные требования

#### Тестирование
- ✅ Используйте валидатор зависимостей в CI/CD
- ✅ Тестируйте на всех поддерживаемых платформах
- ✅ Проверяйте совместимость с разными версиями Irene
- ✅ Валидируйте Docker сборки

## 🚀 Заключение

Новая система сборки Irene Voice Assistant предоставляет:

- **🔧 Полную автоматизацию**: Никаких ручных обновлений зависимостей
- **🖥️ Мультиплатформенность**: Нативная поддержка всех основных платформ
- **📦 Оптимизацию**: Минимальные зависимости для каждой конфигурации
- **🔌 Расширяемость**: Готовность к интеграции внешних пакетов
- **✅ Надежность**: Комплексная валидация и тестирование

Система трансформировала проект из монолитной структуры с жестко закодированными зависимостями в модульную, масштабируемую платформу с конфигурационно-управляемыми сборками.

**Добро пожаловать в будущее сборки Irene! 🌟** 