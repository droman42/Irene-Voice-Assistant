"""
Configuration Schemas - Component-specific configuration schemas

Phase 1 Implementation: Centralized schemas for component configurations
that can be imported and used throughout the system for validation and
type hints.

This module provides:
- Component configuration schemas
- Provider configuration schemas  
- Validation utilities
- Schema versioning support
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


# ============================================================
# PROVIDER CONFIGURATION SCHEMAS
# ============================================================

class BaseProviderSchema(BaseModel):
    """Base schema for all providers"""
    enabled: bool = Field(default=True, description="Enable this provider")


class TTSProviderSchema(BaseProviderSchema):
    """Base schema for TTS providers"""
    pass


class AudioProviderSchema(BaseProviderSchema):
    """Base schema for Audio providers"""
    pass


class ASRProviderSchema(BaseProviderSchema):
    """Base schema for ASR providers"""
    pass


class LLMProviderSchema(BaseProviderSchema):
    """Base schema for LLM providers"""
    pass


class VoiceTriggerProviderSchema(BaseProviderSchema):
    """Base schema for Voice Trigger providers"""
    pass


class NLUProviderSchema(BaseProviderSchema):
    """Base schema for NLU providers"""
    pass


# ============================================================
# TTS PROVIDER SCHEMAS
# ============================================================

class ConsoleProviderSchema(TTSProviderSchema):
    """Console provider configuration schema (used across multiple components)"""
    color_output: bool = Field(default=True, description="Enable colored output")
    timing_simulation: bool = Field(default=False, description="Simulate timing delays")
    prefix: str = Field(default="", description="Output prefix")


class ElevenLabsProviderSchema(TTSProviderSchema):
    """ElevenLabs provider configuration schema"""
    api_key: str = Field(description="ElevenLabs API key (use ${ELEVENLABS_API_KEY})")
    voice_id: str = Field(default="21m00Tcm4TlvDq8ikWAM", description="Voice ID")
    model: str = Field(default="eleven_monolingual_v1", description="Model name")
    stability: float = Field(default=0.5, ge=0.0, le=1.0, description="Voice stability")
    similarity_boost: float = Field(default=0.5, ge=0.0, le=1.0, description="Similarity boost")


class SileroV3ProviderSchema(TTSProviderSchema):
    """Silero v3 TTS provider configuration schema"""
    default_speaker: str = Field(default="xenia", description="Default speaker voice")
    sample_rate: int = Field(default=24000, description="Audio sample rate")
    torch_device: str = Field(default="cpu", description="PyTorch device: cpu, cuda")
    put_accent: bool = Field(default=True, description="Enable accent marks in speech")
    put_yo: bool = Field(default=True, description="Use ё character in speech")
    threads: int = Field(default=4, description="Number of processing threads")
    speaker_by_assname: Dict[str, str] = Field(
        default_factory=dict,
        description="Speaker mapping by assistant name (e.g., {'ирина': 'xenia'})"
    )
    preload_models: bool = Field(default=False, description="Preload AI models during provider initialization")


class SileroV4ProviderSchema(TTSProviderSchema):
    """Silero v4 TTS provider configuration schema"""
    default_speaker: str = Field(default="xenia", description="Default speaker voice: xenia, aidar, baya, kseniya, eugene, random")
    sample_rate: int = Field(default=48000, description="Audio sample rate")
    torch_device: str = Field(default="cpu", description="PyTorch device: cpu, cuda")
    preload_models: bool = Field(default=False, description="Preload AI models during provider initialization")


# ============================================================
# AUDIO PROVIDER SCHEMAS
# ============================================================

class SoundDeviceProviderSchema(AudioProviderSchema):
    """SoundDevice provider configuration schema"""
    device_id: int = Field(default=-1, description="Device ID (-1 for default)")
    sample_rate: int = Field(default=44100, description="Sample rate")


class AudioPlayerProviderSchema(AudioProviderSchema):
    """AudioPlayer provider configuration schema"""
    volume: float = Field(default=0.8, ge=0.0, le=1.0, description="Volume level")
    fade_in: bool = Field(default=False, description="Enable fade-in")
    fade_out: bool = Field(default=True, description="Enable fade-out")


# ============================================================
# ASR PROVIDER SCHEMAS
# ============================================================

class WhisperProviderSchema(ASRProviderSchema):
    """Whisper provider configuration schema"""
    model_size: str = Field(default="base", description="Model size (tiny, base, small, medium, large)")
    device: str = Field(default="cpu", description="Device to run on (cpu, cuda)")
    default_language: Optional[str] = Field(default=None, description="Default language (None for auto-detect)")
    preload_models: bool = Field(default=False, description="Preload AI models during provider initialization")


class VoskASRProviderSchema(ASRProviderSchema):
    """Vosk ASR provider configuration schema"""
    default_language: str = Field(default="ru", description="Default language: ru, en")
    sample_rate: int = Field(default=16000, description="Audio sample rate")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Confidence threshold")
    preload_models: bool = Field(default=False, description="Preload AI models during provider initialization")


class VoskTTSProviderSchema(TTSProviderSchema):
    """Vosk TTS provider configuration schema"""
    default_language: str = Field(default="ru", description="Default language: ru, en, de, fr")
    sample_rate: int = Field(default=22050, description="Audio sample rate")
    voice_speed: float = Field(default=1.0, ge=0.1, le=3.0, description="Voice speed multiplier")
    preload_models: bool = Field(default=False, description="Preload AI models during provider initialization")


class GoogleCloudProviderSchema(ASRProviderSchema):
    """Google Cloud provider configuration schema"""
    credentials_path: str = Field(description="Path to credentials (use ${GOOGLE_APPLICATION_CREDENTIALS})")
    project_id: str = Field(description="Google Cloud project ID")
    default_language: str = Field(default="en-US", description="Default language")
    sample_rate_hertz: int = Field(default=16000, description="Sample rate in Hz")
    encoding: str = Field(default="LINEAR16", description="Audio encoding")


# ============================================================
# LLM PROVIDER SCHEMAS
# ============================================================

class OpenAIProviderSchema(LLMProviderSchema):
    """OpenAI provider configuration schema"""
    api_key: str = Field(description="OpenAI API key (use ${OPENAI_API_KEY})")
    default_model: str = Field(default="gpt-4", description="Default model name")
    max_tokens: int = Field(default=150, ge=1, description="Maximum tokens")
    temperature: float = Field(default=0.3, ge=0.0, le=2.0, description="Temperature")


class AnthropicProviderSchema(LLMProviderSchema):
    """Anthropic provider configuration schema"""
    api_key: str = Field(description="Anthropic API key (use ${ANTHROPIC_API_KEY})")
    default_model: str = Field(default="claude-3-haiku-20240307", description="Default model name")
    max_tokens: int = Field(default=150, ge=1, description="Maximum tokens")
    temperature: float = Field(default=0.3, ge=0.0, le=1.0, description="Temperature")


# ============================================================
# VOICE TRIGGER PROVIDER SCHEMAS
# ============================================================

class OpenWakeWordProviderSchema(VoiceTriggerProviderSchema):
    """OpenWakeWord provider configuration schema"""
    inference_framework: str = Field(default="onnx", description="Inference framework")
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Voice activity detection threshold")
    preload_models: bool = Field(default=False, description="Preload AI models during provider initialization")


class PorcupineProviderSchema(VoiceTriggerProviderSchema):
    """Porcupine provider configuration schema"""
    access_key: str = Field(description="Picovoice access key (use ${PICOVOICE_ACCESS_KEY})")
    keywords: List[str] = Field(default_factory=lambda: ["jarvis"], description="Keywords to detect")


# ============================================================
# NLU PROVIDER SCHEMAS
# ============================================================

class HybridKeywordMatcherProviderSchema(NLUProviderSchema):
    """Hybrid Keyword Matcher provider configuration schema (Phase 1: Updated for complete feature set)"""
    provider_class: str = Field(default="HybridKeywordMatcherProvider", description="Provider class name")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence for intent acceptance (normalized for Phase 1 consistency)")
    fuzzy_enabled: bool = Field(default=True, description="Enable fuzzy matching capabilities")
    fuzzy_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Minimum fuzzy matching score threshold")
    pattern_confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Base confidence for pattern matches")
    case_sensitive: bool = Field(default=False, description="Enable case-sensitive pattern matching")
    normalize_unicode: bool = Field(default=True, description="Enable improved Unicode normalization (Phase 1 enhancement)")
    cache_fuzzy_results: bool = Field(default=True, description="Enable caching of fuzzy matching results")
    max_fuzzy_keywords_per_intent: int = Field(default=50, ge=1, le=1000, description="Maximum fuzzy keywords per intent")
    min_pattern_length: int = Field(default=2, ge=1, le=100, description="Minimum pattern length for processing")


class SpaCyNLUProviderSchema(NLUProviderSchema):
    """SpaCy NLU provider configuration schema (Phase 1: Updated for multi-model support)"""
    provider_class: str = Field(default="SpaCyNLUProvider", description="Provider class name")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence for intent acceptance")
    entity_types: List[str] = Field(
        default=["PERSON", "ORG", "GPE", "DATE", "TIME", "MONEY", "QUANTITY"],
        description="spaCy entity types to extract"
    )
    language_preferences: Dict[str, List[str]] = Field(
        default={
            "ru": ["ru_core_news_md", "ru_core_news_sm"],
            "en": ["en_core_web_md", "en_core_web_sm"]
        },
        description="Language-specific model preferences (Phase 1: Multi-model support)"
    )


# ============================================================
# COMPONENT CONFIGURATION SCHEMAS
# ============================================================

class ComponentProviderConfigSchema(BaseModel):
    """Base schema for component provider configurations"""
    enabled: bool = Field(default=True, description="Enable component")
    default_provider: str = Field(description="Default provider name")
    fallback_providers: List[str] = Field(default_factory=list, description="Fallback providers")
    providers: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Provider configurations")


class TTSComponentSchema(ComponentProviderConfigSchema):
    """TTS component configuration schema"""
    default_provider: str = Field(default="console", description="Default TTS provider")
    fallback_providers: List[str] = Field(default_factory=lambda: ["console"], description="Fallback TTS providers")


class AudioComponentSchema(ComponentProviderConfigSchema):
    """Audio component configuration schema"""
    default_provider: str = Field(default="console", description="Default audio provider")
    fallback_providers: List[str] = Field(default_factory=lambda: ["console"], description="Fallback audio providers")
    concurrent_playback: bool = Field(default=False, description="Allow concurrent audio playback")


class ASRComponentSchema(ComponentProviderConfigSchema):
    """ASR component configuration schema"""
    default_provider: str = Field(default="whisper", description="Default ASR provider")
    fallback_providers: List[str] = Field(default_factory=lambda: ["whisper"], description="Fallback ASR providers")


class LLMComponentSchema(ComponentProviderConfigSchema):
    """LLM component configuration schema"""
    default_provider: str = Field(default="openai", description="Default LLM provider")
    fallback_providers: List[str] = Field(default_factory=lambda: ["console"], description="Fallback LLM providers")


class VoiceTriggerComponentSchema(ComponentProviderConfigSchema):
    """Voice trigger component configuration schema"""
    default_provider: str = Field(default="openwakeword", description="Default voice trigger provider")
    wake_words: List[str] = Field(default_factory=lambda: ["irene", "jarvis"], description="Wake words to detect")
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Detection confidence threshold")
    buffer_seconds: float = Field(default=1.0, gt=0.0, description="Audio buffer duration in seconds")
    timeout_seconds: float = Field(default=5.0, gt=0.0, description="Detection timeout in seconds")


class NLUComponentSchema(ComponentProviderConfigSchema):
    """NLU component configuration schema"""
    default_provider: str = Field(default="hybrid_keyword_matcher", description="Default NLU provider")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Global confidence threshold")
    fallback_intent: str = Field(default="conversation.general", description="Fallback intent name")
    provider_cascade_order: List[str] = Field(
        default_factory=lambda: ["hybrid_keyword_matcher", "spacy_nlu"],
        description="Provider cascade order (fast to slow)"
    )
    max_cascade_attempts: int = Field(default=4, ge=1, description="Maximum cascade attempts")
    cascade_timeout_ms: int = Field(default=200, gt=0, description="Cascade timeout in milliseconds")
    cache_recognition_results: bool = Field(default=False, description="Cache recognition results")
    cache_ttl_seconds: int = Field(default=300, gt=0, description="Cache TTL in seconds")


class TextProcessorComponentSchema(BaseModel):
    """Text processor component configuration schema"""
    enabled: bool = Field(default=True, description="Enable text processor component")
    stages: List[str] = Field(
        default_factory=lambda: ["asr_output", "tts_input", "command_input", "general"],
        description="Processing stages"
    )
    normalizers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Text normalizer configurations"
    )


class IntentSystemComponentSchema(BaseModel):
    """Intent system component configuration schema"""
    enabled: bool = Field(default=True, description="Enable intent system component")
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for intent recognition"
    )
    fallback_intent: str = Field(
        default="conversation.general",
        description="Fallback intent when recognition fails"
    )
    handlers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Intent handler configuration"
    )


# ============================================================
# AUDIO DEVICE SCHEMAS
# ============================================================

class AudioDeviceInfo(BaseModel):
    """Audio input device information schema"""
    id: int = Field(description="Device ID for selection")
    name: str = Field(description="Human-readable device name")
    channels: int = Field(description="Maximum input channels supported")
    sample_rate: int = Field(description="Default sample rate in Hz")
    is_default: bool = Field(description="Whether this is the system default input device")


class AudioDevicesResponse(BaseModel):
    """Response schema for available audio devices endpoint"""
    success: bool = Field(default=True, description="Operation success status")
    devices: List[AudioDeviceInfo] = Field(description="List of available audio input devices")
    total_count: int = Field(description="Total number of devices found")
    message: Optional[str] = Field(default=None, description="Optional status message")


# ============================================================
# SCHEMA VALIDATION UTILITIES
# ============================================================

class SchemaValidator:
    """Utility class for validating configurations against schemas"""
    
    # Provider schema registry
    PROVIDER_SCHEMAS = {
        "tts": {
            "console": ConsoleProviderSchema,
            "elevenlabs": ElevenLabsProviderSchema,
            "silero_v3": SileroV3ProviderSchema,
            "silero_v4": SileroV4ProviderSchema,
            "vosk": VoskTTSProviderSchema,
        },
        "audio": {
            "console": ConsoleProviderSchema,
            "sounddevice": SoundDeviceProviderSchema,
            "audioplayer": AudioPlayerProviderSchema,
        },
        "asr": {
            "whisper": WhisperProviderSchema,
            "vosk": VoskASRProviderSchema,
            "google_cloud": GoogleCloudProviderSchema,
        },
        "llm": {
            "openai": OpenAIProviderSchema,
            "anthropic": AnthropicProviderSchema,
            "console": ConsoleProviderSchema,
        },
        "voice_trigger": {
            "openwakeword": OpenWakeWordProviderSchema,
            "porcupine": PorcupineProviderSchema,
        },
        "nlu": {
            "hybrid_keyword_matcher": HybridKeywordMatcherProviderSchema,
            "spacy_nlu": SpaCyNLUProviderSchema,
        }
    }
    
    # Component schema registry
    COMPONENT_SCHEMAS = {
        "tts": TTSComponentSchema,
        "audio": AudioComponentSchema,
        "asr": ASRComponentSchema,
        "llm": LLMComponentSchema,
        "voice_trigger": VoiceTriggerComponentSchema,
        "nlu": NLUComponentSchema,
        "text_processor": TextProcessorComponentSchema,
        "intent_system": IntentSystemComponentSchema,
    }
    
    @classmethod
    def validate_provider_config(cls, component_type: str, provider_name: str, config: Dict[str, Any]) -> bool:
        """Validate provider configuration against schema"""
        if component_type not in cls.PROVIDER_SCHEMAS:
            return False
        
        if provider_name not in cls.PROVIDER_SCHEMAS[component_type]:
            return False
        
        schema_class = cls.PROVIDER_SCHEMAS[component_type][provider_name]
        try:
            schema_class.model_validate(config)
            return True
        except Exception:
            return False
    
    @classmethod
    def validate_component_config(cls, component_type: str, config: Dict[str, Any]) -> bool:
        """Validate component configuration against schema"""
        if component_type not in cls.COMPONENT_SCHEMAS:
            return False
        
        schema_class = cls.COMPONENT_SCHEMAS[component_type]
        try:
            schema_class.model_validate(config)
            return True
        except Exception:
            return False
    
    @classmethod
    def get_provider_schema(cls, component_type: str, provider_name: str) -> Optional[type]:
        """Get provider schema class"""
        if component_type not in cls.PROVIDER_SCHEMAS:
            return None
        return cls.PROVIDER_SCHEMAS[component_type].get(provider_name)
    
    @classmethod
    def get_component_schema(cls, component_type: str) -> Optional[type]:
        """Get component schema class"""
        return cls.COMPONENT_SCHEMAS.get(component_type)
    
    @classmethod
    def list_supported_providers(cls, component_type: str) -> List[str]:
        """List supported providers for a component type"""
        if component_type not in cls.PROVIDER_SCHEMAS:
            return []
        return list(cls.PROVIDER_SCHEMAS[component_type].keys())
    
    @classmethod
    def list_supported_components(cls) -> List[str]:
        """List supported component types"""
        return list(cls.COMPONENT_SCHEMAS.keys())


# ============================================================
# SCHEMA VERSION SUPPORT
# ============================================================

class SchemaVersion(BaseModel):
    """Schema version information"""
    major: int = Field(default=14, description="Major version")
    minor: int = Field(default=0, description="Minor version")
    patch: int = Field(default=0, description="Patch version")
    
    @property
    def version_string(self) -> str:
        """Get version as string"""
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def is_compatible_with(self, other: 'SchemaVersion') -> bool:
        """Check if this version is compatible with another"""
        # Same major version is compatible
        return self.major == other.major


# Current schema version
CURRENT_SCHEMA_VERSION = SchemaVersion(major=14, minor=0, patch=0)


def get_schema_version() -> SchemaVersion:
    """Get current schema version"""
    return CURRENT_SCHEMA_VERSION


def validate_schema_compatibility(config_version: str) -> bool:
    """Validate if config version is compatible with current schema"""
    try:
        parts = config_version.split(".")
        config_schema_version = SchemaVersion(
            major=int(parts[0]),
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2]) if len(parts) > 2 else 0
        )
        return CURRENT_SCHEMA_VERSION.is_compatible_with(config_schema_version)
    except (ValueError, IndexError):
        return False
