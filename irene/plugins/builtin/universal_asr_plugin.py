"""
Universal ASR Plugin

Speech Recognition Coordinator managing multiple ASR providers.
Provides unified web API (/asr/*), voice commands, and multi-source audio processing.
"""

from typing import Dict, Any, List, Optional, AsyncIterator
from pathlib import Path
import json
import time
import base64
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect  # type: ignore
from ...core.interfaces.asr import ASRPlugin
from ...core.interfaces.webapi import WebAPIPlugin
from ...core.interfaces.command import CommandPlugin
from ...core.context import Context
from ...core.commands import CommandResult

# Import all ASR providers using ABC pattern
from ...providers.asr import (
    ASRProvider,
    VoskASRProvider,
    WhisperASRProvider,
    GoogleCloudASRProvider
)

logger = logging.getLogger(__name__)


class UniversalASRPlugin(ASRPlugin, WebAPIPlugin, CommandPlugin):
    """
    Universal ASR Plugin - Speech Recognition Coordinator
    
    Manages multiple ASR providers and provides:
    - Unified web API (/asr/*)
    - Voice commands for ASR control
    - Multi-source audio processing (microphone, web, files)
    - Provider switching and fallbacks
    """
    
    def __init__(self):
        super().__init__()
        self.providers: Dict[str, ASRProvider] = {}  # Proper ABC type hint
        self.default_provider = "vosk"
        self.default_language = "ru"
        self.core = None  # Store core reference for LLM integration
        
        # Provider class mapping
        self._provider_classes = {
            "vosk": VoskASRProvider,
            "whisper": WhisperASRProvider,
            "google_cloud": GoogleCloudASRProvider,
        }
        
    @property
    def name(self) -> str:
        return "universal_asr"
    
    @property 
    def version(self) -> str:
        return "1.0.0"
        
    async def initialize(self, core) -> None:
        """Initialize ASR providers from configuration"""
        try:
            self.core = core  # Store core reference
            config = getattr(core.config.plugins, "universal_asr", {})
            
            # Initialize enabled providers with ABC error handling
            providers_config = config.get("providers", {})
            
            for provider_name, provider_class in self._provider_classes.items():
                provider_config = providers_config.get(provider_name, {})
                if provider_config.get("enabled", False):
                    try:
                        provider = provider_class(provider_config)
                        if await provider.is_available():
                            self.providers[provider_name] = provider
                            logger.info(f"Loaded ASR provider: {provider_name}")
                        else:
                            logger.warning(f"ASR provider {provider_name} not available (dependencies missing)")
                    except TypeError as e:
                        logger.error(f"ASR provider {provider_name} missing required abstract methods: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to load ASR provider {provider_name}: {e}")
            
            # Set defaults from config
            self.default_provider = config.get("default_provider", "vosk")
            self.default_language = config.get("default_language", "ru")
            
            # Ensure we have at least one provider
            if not self.providers:
                logger.warning("No ASR providers available")
            else:
                logger.info(f"Universal ASR Plugin initialized with {len(self.providers)} providers")
                
        except Exception as e:
            logger.error(f"Failed to initialize Universal ASR Plugin: {e}")
    
    # Primary ASR interface - used by input sources
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        """
        Core ASR functionality - transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes
            provider: ASR provider to use (default: self.default_provider)
            language: Language code (default: self.default_language)
            **kwargs: Provider-specific parameters
            
        Returns:
            Transcribed text
        """
        provider_name = kwargs.get("provider", self.default_provider)
        language = kwargs.get("language", self.default_language)
        
        if provider_name not in self.providers:
            raise HTTPException(404, f"ASR provider '{provider_name}' not available")
        
        provider = self.providers[provider_name]
        return await provider.transcribe_audio(audio_data, language=language, **kwargs)
    
    # CommandPlugin interface - voice control
    def get_triggers(self) -> List[str]:
        """Get command triggers for ASR control"""
        return [
            "распознай", "транскрибируй", "переключись на", "покажи распознавание",
            "язык", "качество", "микрофон", "запись"
        ]
    
    async def can_handle(self, command: str, context: Context) -> bool:
        """Check if this command is ASR-related"""
        triggers = self.get_triggers()
        command_lower = command.lower()
        return any(trigger in command_lower for trigger in triggers)
    
    async def handle_command(self, command: str, context: Context) -> CommandResult:
        """Handle ASR voice commands"""
        if "покажи распознавание" in command or "покажи провайдеры" in command:
            info = self._get_providers_info()
            return CommandResult(success=True, response=info)
        elif "переключись на" in command:
            # "переключись на whisper"
            new_provider = self._parse_provider_name(command)
            if new_provider in self.providers:
                self.default_provider = new_provider
                return CommandResult(success=True, response=f"Переключился на {new_provider}")
            else:
                return CommandResult(success=False, error=f"Провайдер {new_provider} недоступен")
        elif "язык" in command:
            # Handle language switching commands
            # TODO: Implement language switching logic
            return CommandResult(success=False, error="Переключение языка пока не реализовано")
            
        return CommandResult(success=False, error="Неизвестная команда распознавания")
    
    def _get_providers_info(self) -> str:
        """Get formatted information about available providers"""
        if not self.providers:
            return "Нет доступных провайдеров ASR"
        
        info_lines = [f"Доступные провайдеры ASR ({len(self.providers)}):"]
        for name, provider in self.providers.items():
            status = "✓ (по умолчанию)" if name == self.default_provider else "✓"
            languages = ", ".join(provider.get_supported_languages()[:3])  # Show first 3
            info_lines.append(f"  {status} {name}: {languages}...")
        
        return "\n".join(info_lines)
    
    def _parse_provider_name(self, command: str) -> str:
        """Extract provider name from voice command"""
        command_lower = command.lower()
        for provider_name in self.providers.keys():
            if provider_name in command_lower:
                return provider_name
        
        # Handle common aliases
        aliases = {
            "воск": "vosk",
            "виспер": "whisper", 
            "гугл": "google_cloud",
            "облако": "google_cloud"
        }
        
        for alias, provider_name in aliases.items():
            if alias in command_lower and provider_name in self.providers:
                return provider_name
        
        return ""
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> APIRouter:
        router = APIRouter()
        
        @router.post("/transcribe")
        async def transcribe_audio_file(
            audio: UploadFile = File(...),
            provider: Optional[str] = None,
            language: str = "ru",
            enhance: bool = False
        ):
            """Transcribe uploaded audio file - NEW CAPABILITY!"""
            provider_name = provider or self.default_provider
            
            if provider_name not in self.providers:
                raise HTTPException(404, f"Provider '{provider_name}' not available")
            
            # Read and transcribe audio
            audio_data = await audio.read()
            text = await self.transcribe_audio(
                audio_data, provider=provider_name, language=language
            )
            
            # Optional LLM enhancement
            enhanced_text = None
            if enhance and text.strip():
                # Get LLM plugin and enhance text
                if hasattr(self, 'core') and self.core:
                    llm_plugin = self.core.plugin_manager.get_plugin("universal_llm")
                    if llm_plugin:
                        try:
                            enhanced_text = await llm_plugin.enhance_text(
                                text, task="improve_speech_recognition"
                            )
                        except Exception as e:
                            logger.warning(f"LLM enhancement failed: {e}")
                
                if enhanced_text:
                    return {
                        "original_text": text,
                        "enhanced_text": enhanced_text,
                        "provider": provider_name,
                        "language": language,
                        "enhanced": True
                    }
            
            return {
                "text": text,
                "provider": provider_name,
                "language": language,
                "enhanced": False
            }
        
        @router.websocket("/stream")
        async def stream_transcription(websocket: WebSocket):
            """WebSocket endpoint for real-time ASR - NEW CAPABILITY!"""
            await websocket.accept()
            
            try:
                while True:
                    # Receive audio chunk
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message["type"] == "audio_chunk":
                        # Decode and process audio
                        audio_data = base64.b64decode(message["data"])
                        language = message.get("language", self.default_language)
                        provider_name = message.get("provider", self.default_provider)
                        
                        # Transcribe chunk
                        try:
                            text = await self.transcribe_audio(
                                audio_data, 
                                provider=provider_name,
                                language=language
                            )
                            
                            if text.strip():
                                # Send result back
                                response = {
                                    "type": "transcription_result",
                                    "text": text,
                                    "provider": provider_name,
                                    "language": language,
                                    "timestamp": time.time()
                                }
                                await websocket.send_text(json.dumps(response))
                        except Exception as e:
                            error_response = {
                                "type": "error",
                                "error": str(e),
                                "timestamp": time.time()
                            }
                            await websocket.send_text(json.dumps(error_response))
                            
            except WebSocketDisconnect:
                logger.info("ASR WebSocket client disconnected")
            except Exception as e:
                logger.error(f"ASR WebSocket error: {e}")
        
        @router.get("/providers")
        async def list_asr_providers():
            """Discovery endpoint for all ASR provider capabilities"""
            result = {}
            for name, provider in self.providers.items():
                try:
                    result[name] = {
                        "available": await provider.is_available(),
                        "parameters": provider.get_parameter_schema(),
                        "languages": provider.get_supported_languages(),
                        "formats": provider.get_supported_formats(),
                        "capabilities": provider.get_capabilities()
                    }
                except Exception as e:
                    result[name] = {
                        "available": False,
                        "error": str(e)
                    }
            return {"providers": result, "default": self.default_provider}
        
        @router.post("/configure")
        async def configure_asr(provider: str, set_as_default: bool = False):
            """Configure ASR settings"""
            if provider in self.providers:
                if set_as_default:
                    self.default_provider = provider
                return {"success": True, "default_provider": self.default_provider}
            else:
                raise HTTPException(404, f"Provider '{provider}' not available")
        
        return router 