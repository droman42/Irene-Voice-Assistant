# Руководство по реализации цепочек обработки в Irene
## Как связать несколько плагинов в единый поток

---

## 🎯 **Задача**

Реализовать поток: **WebSocket stream → ASR → LLM → Custom Processing → TTS**

---

## 🔧 **Подходы к реализации**

### **Подход 1: Оркестрирующий плагин (Рекомендуемый)**

Создайте специальный плагин для управления всей цепочкой:

```python
# irene/plugins/builtin/voice_chain_plugin.py

from ..base import BaseCommandPlugin
from ...core.interfaces.webapi import WebAPIPlugin
from ...core.commands import CommandResult

class VoiceChainPlugin(BaseCommandPlugin, WebAPIPlugin):
    """Плагин для цепочки голосовой обработки"""
    
    def __init__(self):
        super().__init__()
        self._asr_plugin = None
        self._llm_plugin = None
        self._tts_plugin = None
    
    async def initialize(self, core) -> None:
        await super().initialize(core)
        
        # Получаем ссылки на универсальные плагины
        self._asr_plugin = await core.plugin_manager.get_plugin("universal_asr")
        self._llm_plugin = await core.plugin_manager.get_plugin("universal_llm")
        self._tts_plugin = await core.plugin_manager.get_plugin("universal_tts")
    
    async def process_voice_chain(self, audio_data, options=None):
        """Основная цепочка обработки"""
        
        # Шаг 1: ASR (Speech Recognition)
        transcribed_text = await self._process_asr(audio_data)
        
        # Шаг 2: LLM (Text Improvement)
        improved_text = await self._process_llm(transcribed_text)
        
        # Шаг 3: Custom Processing
        processed_data = await self._process_custom(improved_text)
        
        # Шаг 4: TTS (Text-to-Speech)
        audio_output = await self._process_tts(processed_data)
        
        return {
            "original_audio": audio_data,
            "transcribed_text": transcribed_text,
            "improved_text": improved_text,
            "processed_data": processed_data,
            "final_audio": audio_output
        }
    
    async def _process_asr(self, audio_data):
        """Обработка через ASR плагин"""
        if not self._asr_plugin:
            raise RuntimeError("ASR plugin не доступен")
        
        # Вызываем метод ASR плагина
        return await self._asr_plugin.transcribe_audio(
            audio_data, 
            provider="vosk"
        )
    
    async def _process_llm(self, text):
        """Обработка через LLM плагин"""
        if not self._llm_plugin:
            return text  # Fallback: возвращаем исходный текст
        
        prompt = f"Улучши следующий текст, исправь ошибки: {text}"
        
        return await self._llm_plugin.generate_response(
            prompt,
            provider="openai",
            model="gpt-3.5-turbo"
        )
    
    async def _process_custom(self, text):
        """Custom обработка данных"""
        # Пример custom логики
        enhanced_text = text.strip().capitalize()
        
        # Добавляем метаданные
        return {
            "text": enhanced_text,
            "word_count": len(enhanced_text.split()),
            "processed_at": datetime.now().isoformat()
        }
    
    async def _process_tts(self, data):
        """Обработка через TTS плагин"""
        if not self._tts_plugin:
            return None
        
        text = data["text"] if isinstance(data, dict) else str(data)
        
        return await self._tts_plugin.synthesize_speech(
            text,
            provider="silero_v4"
        )
    
    # WebAPI интеграция
    def get_web_endpoints(self):
        return [
            {
                "path": "/voice/process",
                "methods": ["POST"],
                "handler": self._web_process_chain
            },
            {
                "path": "/voice/stream",
                "methods": ["WebSocket"],
                "handler": self._web_stream_chain
            }
        ]
    
    async def _web_process_chain(self, request):
        """REST endpoint для обработки"""
        audio_data = request.get("audio_data")
        options = request.get("options", {})
        
        try:
            result = await self.process_voice_chain(audio_data, options)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _web_stream_chain(self, websocket, data):
        """WebSocket для streaming обработки"""
        try:
            audio_chunk = data.get("audio_chunk")
            
            # Обрабатываем chunk
            result = await self.process_voice_chain(audio_chunk)
            
            # Отправляем результат
            await websocket.send_json({
                "type": "processed_chunk",
                "result": result
            })
            
        except Exception as e:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
```

### **Подход 2: Command-based цепочки**

Создайте команды, которые вызывают последовательности:

```python
# irene/plugins/builtin/chain_commands_plugin.py

class ChainCommandsPlugin(BaseCommandPlugin):
    """Плагин команд для цепочек обработки"""
    
    async def execute_command(self, command: str, context=None) -> CommandResult:
        
        if command.startswith("voice chain"):
            return await self._execute_voice_chain(command, context)
        elif command.startswith("text chain"):
            return await self._execute_text_chain(command, context)
            
        return CommandResult(success=False, response="Неизвестная команда цепочки")
    
    async def _execute_voice_chain(self, command, context):
        """Выполнить голосовую цепочку"""
        
        # Получаем audio data из контекста или WebSocket
        audio_data = context.get("audio_data") if context else None
        
        if not audio_data:
            return CommandResult(
                success=False, 
                response="Нет аудио данных для обработки"
            )
        
        try:
            # Цепочка: ASR → LLM → TTS
            steps = []
            
            # Шаг 1: ASR
            asr_plugin = await self.core.plugin_manager.get_plugin("universal_asr")
            if asr_plugin:
                text = await asr_plugin.transcribe_audio(audio_data)
                steps.append(f"ASR: '{text}'")
            else:
                return CommandResult(success=False, response="ASR недоступен")
            
            # Шаг 2: LLM
            llm_plugin = await self.core.plugin_manager.get_plugin("universal_llm") 
            if llm_plugin:
                improved = await llm_plugin.generate_response(
                    f"Улучши текст: {text}"
                )
                steps.append(f"LLM: '{improved}'")
            else:
                improved = text  # Fallback
            
            # Шаг 3: TTS
            tts_plugin = await self.core.plugin_manager.get_plugin("universal_tts")
            if tts_plugin:
                audio_output = await tts_plugin.synthesize_speech(improved)
                steps.append(f"TTS: {audio_output}")
            
            return CommandResult(
                success=True,
                response=f"Цепочка выполнена: {' → '.join(steps)}",
                metadata={"final_audio": audio_output}
            )
            
        except Exception as e:
            return CommandResult(
                success=False,
                response=f"Ошибка в цепочке: {e}"
            )
```

### **Подход 3: Пошаговые вызовы**

Простое последовательное выполнение:

```python
async def simple_voice_processing_flow(core, audio_input):
    """Простая последовательная обработка"""
    
    # Получаем плагины
    asr = await core.plugin_manager.get_plugin("universal_asr")
    llm = await core.plugin_manager.get_plugin("universal_llm")
    tts = await core.plugin_manager.get_plugin("universal_tts")
    
    # Шаг 1: Распознавание речи
    if asr:
        text = await asr.transcribe_audio(audio_input, provider="vosk")
        print(f"Распознано: {text}")
    else:
        raise RuntimeError("ASR плагин недоступен")
    
    # Шаг 2: Улучшение через LLM
    if llm:
        prompt = f"Исправь ошибки и улучши: {text}"
        improved_text = await llm.generate_response(
            prompt, 
            provider="openai",
            max_tokens=100
        )
        print(f"Улучшено: {improved_text}")
    else:
        improved_text = text
        print("LLM недоступен, используем исходный текст")
    
    # Шаг 3: Custom обработка
    processed_text = improved_text.strip().capitalize()
    if not processed_text.endswith('.'):
        processed_text += '.'
    print(f"Обработано: {processed_text}")
    
    # Шаг 4: Синтез речи
    if tts:
        audio_output = await tts.synthesize_speech(
            processed_text,
            provider="silero_v4"
        )
        print(f"Аудио создано: {audio_output}")
        return audio_output
    else:
        print("TTS недоступен")
        return processed_text

# Использование:
# result = await simple_voice_processing_flow(core, "audio_data")
```

### **Подход 4: WebSocket Streaming**

Для real-time обработки потока:

```python
class StreamingVoiceProcessor:
    """Обработчик потокового аудио"""
    
    def __init__(self, core):
        self.core = core
        self.buffer = []
        self.processing_queue = asyncio.Queue()
    
    async def start_streaming(self, websocket):
        """Запуск потоковой обработки"""
        
        # Создаем задачи обработки
        processor_task = asyncio.create_task(self._process_stream())
        
        try:
            async for message in websocket.iter_text():
                data = json.loads(message)
                
                if data["type"] == "audio_chunk":
                    # Добавляем chunk в очередь
                    await self.processing_queue.put(data["chunk"])
                
                elif data["type"] == "end_stream":
                    # Завершаем обработку
                    await self.processing_queue.put(None)
                    break
        
        finally:
            processor_task.cancel()
    
    async def _process_stream(self):
        """Основной цикл обработки потока"""
        
        asr = await self.core.plugin_manager.get_plugin("universal_asr")
        llm = await self.core.plugin_manager.get_plugin("universal_llm")
        tts = await self.core.plugin_manager.get_plugin("universal_tts")
        
        accumulated_audio = []
        
        while True:
            chunk = await self.processing_queue.get()
            
            if chunk is None:  # Конец потока
                break
            
            accumulated_audio.append(chunk)
            
            # Обрабатываем накопленное аудио
            if len(accumulated_audio) >= 5:  # Каждые 5 chunks
                
                try:
                    # Объединяем chunks
                    combined_audio = self._combine_audio_chunks(accumulated_audio)
                    
                    # ASR
                    text = await asr.transcribe_audio(combined_audio) if asr else ""
                    
                    # LLM (если есть достаточно текста)
                    if len(text.split()) >= 3:
                        improved = await llm.generate_response(
                            f"Улучши: {text}"
                        ) if llm else text
                        
                        # TTS
                        audio_result = await tts.synthesize_speech(
                            improved
                        ) if tts else None
                        
                        # Отправляем результат через WebSocket
                        await self._send_result({
                            "original_text": text,
                            "improved_text": improved,
                            "audio_output": audio_result
                        })
                    
                    # Очищаем буфер
                    accumulated_audio = []
                
                except Exception as e:
                    logger.error(f"Ошибка обработки потока: {e}")
    
    def _combine_audio_chunks(self, chunks):
        """Объединение аудио chunks"""
        # Реализация зависит от формата аудио
        return b"".join(chunks)
    
    async def _send_result(self, result):
        """Отправка результата через WebSocket"""
        # Отправка результата клиенту
        pass
```

---

## 🔄 **Интеграция с WebSocket**

### WebSocket обработчик

```python
# В WebAPIRunner или отдельном обработчике

@app.websocket("/voice/stream")
async def voice_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Создаем обработчик цепочки
    chain_plugin = await core.plugin_manager.get_plugin("voice_chain") 
    
    try:
        while True:
            # Получаем данные от клиента
            data = await websocket.receive_json()
            
            if data["type"] == "audio_chunk":
                # Обрабатываем через цепочку
                result = await chain_plugin.process_voice_chain(
                    data["audio_data"]
                )
                
                # Отправляем результат
                await websocket.send_json({
                    "type": "processing_result",
                    "result": result
                })
            
            elif data["type"] == "end_stream":
                break
    
    except WebSocketDisconnect:
        logger.info("WebSocket отключен")
    except Exception as e:
        logger.error(f"Ошибка WebSocket: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
```

### Клиентская часть (JavaScript)

```javascript
// Клиентский код для WebSocket
const ws = new WebSocket('ws://localhost:5003/voice/stream');

// Отправка аудио chunks
function sendAudioChunk(audioData) {
    ws.send(JSON.stringify({
        type: 'audio_chunk',
        audio_data: audioData
    }));
}

// Получение результатов
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'processing_result') {
        console.log('Результат обработки:', data.result);
        
        // Воспроизводим полученное аудио
        if (data.result.final_audio) {
            playAudio(data.result.final_audio);
        }
    }
};
```

---

## ⚙️ **Конфигурация цепочек**

### В config.toml

```toml
[plugins.voice_chain]
# Настройки цепочки обработки

# ASR настройки
asr_provider = "vosk"
asr_model = "vosk-model-ru-0.22"
asr_sample_rate = 16000

# LLM настройки  
llm_provider = "openai"
llm_model = "gpt-3.5-turbo"
llm_max_tokens = 150
llm_improvement_prompt = "Исправь ошибки и улучши читаемость следующего текста:"

# TTS настройки
tts_provider = "silero_v4"
tts_voice = "ru_v4_natasha"
tts_sample_rate = 48000

# Опции цепочки
enable_fallbacks = true
stream_processing = true
save_intermediate_results = false
timeout_seconds = 30
```

### Программная конфигурация

```python
# Создание цепочки с custom настройками
chain_config = {
    "steps": [
        {
            "name": "asr",
            "plugin": "universal_asr",
            "config": {"provider": "vosk", "model": "ru-0.22"}
        },
        {
            "name": "llm_enhance",
            "plugin": "universal_llm", 
            "config": {
                "provider": "openai",
                "prompt": "Улучши текст:",
                "max_tokens": 100
            }
        },
        {
            "name": "custom_process",
            "function": "process_text_metadata"
        },
        {
            "name": "tts",
            "plugin": "universal_tts",
            "config": {"provider": "silero_v4"}
        }
    ],
    "options": {
        "parallel_where_possible": False,
        "error_handling": "continue_on_error",
        "timeout_per_step": 10
    }
}
```

---

## 📊 **Мониторинг и отладка**

### Логирование цепочек

```python
import logging
import time

logger = logging.getLogger("voice_chain")

class ChainLogger:
    """Логирование выполнения цепочек"""
    
    def __init__(self, chain_id):
        self.chain_id = chain_id
        self.start_time = time.time()
        self.steps = []
    
    async def log_step(self, step_name, duration_ms, success, result=None, error=None):
        """Логирование шага"""
        step_info = {
            "step": step_name,
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": time.time()
        }
        
        if error:
            step_info["error"] = str(error)
            logger.error(f"Chain {self.chain_id} step {step_name} failed: {error}")
        else:
            logger.info(f"Chain {self.chain_id} step {step_name} completed in {duration_ms:.1f}ms")
        
        self.steps.append(step_info)
    
    def get_summary(self):
        """Получить сводку выполнения"""
        total_time = (time.time() - self.start_time) * 1000
        successful_steps = sum(1 for s in self.steps if s["success"])
        
        return {
            "chain_id": self.chain_id,
            "total_duration_ms": total_time,
            "steps_total": len(self.steps),
            "steps_successful": successful_steps,
            "success_rate": successful_steps / len(self.steps) if self.steps else 0,
            "steps": self.steps
        }
```

### Метрики производительности

```python
class ChainMetrics:
    """Сбор метрик производительности цепочек"""
    
    def __init__(self):
        self.execution_times = []
        self.step_times = {}
        self.error_counts = {}
    
    def record_execution(self, duration_ms, success, steps_data):
        """Записать выполнение цепочки"""
        self.execution_times.append({
            "duration_ms": duration_ms,
            "success": success,
            "timestamp": time.time()
        })
        
        # Записываем времена по шагам
        for step in steps_data:
            step_name = step["step"]
            if step_name not in self.step_times:
                self.step_times[step_name] = []
            
            self.step_times[step_name].append(step["duration_ms"])
            
            if not step["success"]:
                self.error_counts[step_name] = self.error_counts.get(step_name, 0) + 1
    
    def get_statistics(self):
        """Получить статистику"""
        if not self.execution_times:
            return {"message": "Нет данных для анализа"}
        
        total_executions = len(self.execution_times)
        successful = sum(1 for e in self.execution_times if e["success"])
        avg_duration = sum(e["duration_ms"] for e in self.execution_times) / total_executions
        
        step_stats = {}
        for step_name, times in self.step_times.items():
            step_stats[step_name] = {
                "avg_duration_ms": sum(times) / len(times),
                "min_duration_ms": min(times),
                "max_duration_ms": max(times),
                "error_count": self.error_counts.get(step_name, 0)
            }
        
        return {
            "total_executions": total_executions,
            "success_rate": successful / total_executions,
            "avg_duration_ms": avg_duration,
            "step_statistics": step_stats
        }
```

---

## 🎯 **Лучшие практики**

### 1. **Обработка ошибок**
- Используйте graceful degradation
- Предусмотрите fallback варианты
- Логируйте все ошибки с контекстом

### 2. **Производительность**
- Кэшируйте ссылки на плагины
- Используйте connection pooling для внешних API
- Обрабатывайте данные потоково где возможно

### 3. **Мониторинг**
- Собирайте метрики времени выполнения
- Отслеживайте успешность каждого шага
- Используйте structured logging

### 4. **Тестирование**
- Тестируйте каждый шаг изолированно
- Создавайте mock-данные для тестов
- Проверяйте обработку ошибок

### 5. **Конфигурация**
- Делайте цепочки конфигурируемыми
- Поддерживайте множественные профили
- Используйте валидацию конфигурации

---

Этот подход обеспечивает гибкость, масштабируемость и надежность при создании сложных цепочек обработки в архитектуре Irene. 