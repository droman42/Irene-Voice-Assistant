"""
Configuration Models - Pydantic models for type-safe configuration

Phase 1 Implementation: Complete architectural redesign with clean separation of concerns.
- System capabilities (hardware & services)
- Input sources (data entry points)  
- Components (processing pipeline)
- Component-specific configurations
- Asset management (environment-driven)
- Workflows (processing pipelines)

Requires: pydantic>=2.0.0, pydantic-settings>=2.0.0
"""

import os
import re
from typing import Optional, Any, Dict, List, Type, Union
from pathlib import Path
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ============================================================
# SYSTEM CAPABILITIES CONFIGURATION
# ============================================================

class SystemConfig(BaseModel):
    """System-level capability and service configuration"""
    # Hardware capabilities
    microphone_enabled: bool = Field(default=False, description="Enable microphone hardware capability")
    audio_playback_enabled: bool = Field(default=False, description="Enable audio playback hardware capability")
    
    # Service capabilities  
    web_api_enabled: bool = Field(default=True, description="Enable web API service")
    web_port: int = Field(default=8000, ge=1, le=65535, description="Web API server port")
    
    @field_validator('web_port')
    @classmethod
    def validate_ports(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('Port must be between 1 and 65535')
        return v


# ============================================================
# INPUT SOURCES CONFIGURATION
# ============================================================

class MicrophoneInputConfig(BaseModel):
    """Microphone input configuration with Phase 5 audio enhancements"""
    enabled: bool = Field(default=True, description="Enable microphone input")
    device_id: Optional[int] = Field(default=None, description="Audio device ID (None = default)")
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    chunk_size: int = Field(default=1024, description="Audio buffer chunk size")
    buffer_queue_size: int = Field(default=50, description="Audio buffer queue size for handling processing delays")
    
    # Phase 5: Global audio configuration enhancements
    auto_resample: bool = Field(default=True, description="Enable/disable resampling globally")
    resample_quality: str = Field(default="medium", description="Global resampling quality (fast/medium/high/best)")
    
    @field_validator('sample_rate')
    @classmethod
    def validate_sample_rate(cls, v):
        # Phase 5: Expanded sample rate range
        if v < 8000 or v > 192000:
            raise ValueError("Sample rate must be between 8000 and 192000 Hz")
        return v
    
    @field_validator('channels')
    @classmethod
    def validate_channels(cls, v):
        if v < 1 or v > 8:
            raise ValueError("Channels must be between 1 and 8")
        return v
    
    @field_validator('resample_quality')
    @classmethod
    def validate_resample_quality(cls, v):
        if v not in ['fast', 'medium', 'high', 'best']:
            raise ValueError("Resample quality must be one of: fast, medium, high, best")
        return v
    
    @field_validator('chunk_size')
    @classmethod
    def validate_chunk_size(cls, v):
        if v <= 0 or v > 8192:
            raise ValueError("chunk_size must be between 1 and 8192")
        return v
    
    @field_validator('buffer_queue_size')
    @classmethod
    def validate_buffer_queue_size(cls, v):
        if v <= 0 or v > 200:
            raise ValueError("buffer_queue_size must be between 1 and 200")
        return v


class WebInputConfig(BaseModel):
    """Web input configuration"""
    enabled: bool = Field(default=True, description="Enable web input")
    websocket_enabled: bool = Field(default=True, description="Enable WebSocket input")
    rest_api_enabled: bool = Field(default=True, description="Enable REST API input")


class CLIInputConfig(BaseModel):
    """CLI input configuration"""
    enabled: bool = Field(default=True, description="Enable CLI input")
    prompt_prefix: str = Field(default="irene> ", description="CLI prompt prefix")
    history_enabled: bool = Field(default=True, description="Enable command history")


class InputConfig(BaseModel):
    """Input source configuration"""
    microphone: bool = Field(default=False, description="Enable microphone input source")
    web: bool = Field(default=True, description="Enable web interface input")
    cli: bool = Field(default=True, description="Enable command line input")
    default_input: str = Field(default="cli", description="Default input source")
    
    # Input-specific configurations
    microphone_config: MicrophoneInputConfig = Field(default_factory=MicrophoneInputConfig, description="Microphone input configuration")
    web_config: WebInputConfig = Field(default_factory=WebInputConfig, description="Web input configuration")
    cli_config: CLIInputConfig = Field(default_factory=CLIInputConfig, description="CLI input configuration")
    
    @field_validator('default_input')
    @classmethod
    def validate_default_input(cls, v):
        valid_inputs = ["microphone", "web", "cli"]
        if v not in valid_inputs:
            raise ValueError(f"default_input must be one of: {valid_inputs}")
        return v


# ============================================================
# COMPONENT CONFIGURATION
# ============================================================

class ComponentConfig(BaseModel):
    """Processing component configuration (actual components only)"""
    # Actual components from irene/components/
    tts: bool = Field(default=False, description="Enable text-to-speech component")
    asr: bool = Field(default=False, description="Enable automatic speech recognition component")
    audio: bool = Field(default=False, description="Enable audio playback component")
    llm: bool = Field(default=False, description="Enable large language model component")
    voice_trigger: bool = Field(default=False, description="Enable wake word detection component")
    nlu: bool = Field(default=False, description="Enable natural language understanding component")
    text_processor: bool = Field(default=False, description="Enable text processing pipeline component")
    intent_system: bool = Field(default=True, description="Enable intent handling component (essential)")
    vad: bool = Field(default=False, description="Enable voice activity detection for audio processing")
    monitoring: bool = Field(default=True, description="Enable monitoring and metrics component (Phase 3 infrastructure)")


# ============================================================
# COMPONENT-SPECIFIC CONFIGURATIONS
# ============================================================

class TTSConfig(BaseModel):
    """TTS component configuration"""
    enabled: bool = Field(default=False, description="Enable TTS component")
    default_provider: Optional[str] = Field(default=None, description="Default TTS provider")
    fallback_providers: List[str] = Field(default_factory=list, description="Fallback providers in order")
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific configurations"
    )


class AudioConfig(BaseModel):
    """Audio component configuration"""
    enabled: bool = Field(default=False, description="Enable Audio component")
    default_provider: Optional[str] = Field(default=None, description="Default audio provider")
    fallback_providers: List[str] = Field(default_factory=list, description="Fallback providers in order")
    concurrent_playback: bool = Field(default=False, description="Allow concurrent audio playback")
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific configurations"
    )


class ASRConfig(BaseModel):
    """ASR component configuration with Phase 5 audio enhancements"""
    enabled: bool = Field(default=False, description="Enable ASR component")
    default_provider: Optional[str] = Field(default=None, description="Default ASR provider")
    fallback_providers: List[str] = Field(default_factory=list, description="Fallback providers in order")
    
    # Phase 5: Audio configuration enhancements
    sample_rate: Optional[int] = Field(default=16000, description="AUTHORITATIVE: Audio sample rate in Hz (overrides provider preferences)")
    channels: int = Field(default=1, description="AUTHORITATIVE: Number of audio channels")
    allow_resampling: bool = Field(default=True, description="Enable resampling for this component")
    resample_quality: str = Field(default="high", description="Component-specific quality setting (fast/medium/high/best)")
    
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific configurations"
    )
    
    @field_validator('sample_rate')
    @classmethod
    def validate_sample_rate(cls, v):
        if v is not None and (v < 8000 or v > 192000):
            raise ValueError("Sample rate must be between 8000 and 192000 Hz")
        return v
    
    @field_validator('channels')
    @classmethod
    def validate_channels(cls, v):
        if v < 1 or v > 8:
            raise ValueError("Channels must be between 1 and 8")
        return v
    
    @field_validator('resample_quality')
    @classmethod
    def validate_resample_quality(cls, v):
        if v not in ['fast', 'medium', 'high', 'best']:
            raise ValueError("Resample quality must be one of: fast, medium, high, best")
        return v


class LLMConfig(BaseModel):
    """LLM component configuration"""
    enabled: bool = Field(default=False, description="Enable LLM component")
    default_provider: Optional[str] = Field(default=None, description="Default LLM provider")
    fallback_providers: List[str] = Field(default_factory=list, description="Fallback providers in order")
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific configurations"
    )


class VoiceTriggerConfig(BaseModel):
    """Voice trigger / wake word component configuration with Phase 5 audio enhancements"""
    enabled: bool = Field(default=False, description="Enable voice trigger component")
    default_provider: Optional[str] = Field(default=None, description="Default voice trigger provider")
    wake_words: List[str] = Field(
        default_factory=list,
        description="Wake words to detect"
    )
    confidence_threshold: float = Field(default=0.8, description="Detection confidence threshold")
    buffer_seconds: float = Field(default=1.0, description="Audio buffer duration in seconds")
    timeout_seconds: float = Field(default=5.0, description="Detection timeout in seconds")
    
    # Phase 5: Audio configuration enhancements
    sample_rate: Optional[int] = Field(default=16000, description="AUTHORITATIVE: Audio sample rate in Hz (overrides provider preferences)")
    channels: int = Field(default=1, description="AUTHORITATIVE: Number of audio channels")
    allow_resampling: bool = Field(default=True, description="Enable resampling for voice triggers")
    resample_quality: str = Field(default="fast", description="Optimized for low-latency real-time processing (fast/medium/high/best)")
    strict_validation: bool = Field(default=True, description="Fatal error on provider conflicts")
    
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific configurations"
    )
    
    @field_validator('sample_rate')
    @classmethod
    def validate_sample_rate(cls, v):
        if v is not None and (v < 8000 or v > 192000):
            raise ValueError("Sample rate must be between 8000 and 192000 Hz")
        return v
    
    @field_validator('channels')
    @classmethod
    def validate_channels(cls, v):
        if v < 1 or v > 8:
            raise ValueError("Channels must be between 1 and 8")
        return v
    
    @field_validator('resample_quality')
    @classmethod
    def validate_resample_quality(cls, v):
        if v not in ['fast', 'medium', 'high', 'best']:
            raise ValueError("Resample quality must be one of: fast, medium, high, best")
        return v


class NLUConfig(BaseModel):
    """NLU component configuration"""
    enabled: bool = Field(default=False, description="Enable NLU component")
    default_provider: Optional[str] = Field(default=None, description="Default NLU provider")
    confidence_threshold: float = Field(default=0.7, description="Global confidence threshold")
    fallback_intent: str = Field(default="conversation.general", description="Fallback intent name")
    
    # Cascading configuration
    provider_cascade_order: List[str] = Field(
        default_factory=list,
        description="Provider cascade order (fast to slow)"
    )
    max_cascade_attempts: int = Field(default=4, description="Maximum cascade attempts")
    cascade_timeout_ms: int = Field(default=200, description="Cascade timeout in milliseconds")
    
    # Performance configuration
    cache_recognition_results: bool = Field(default=False, description="Cache recognition results")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")
    
    # Language detection settings
    auto_detect_language: bool = Field(default=True, description="Enable automatic language detection")
    language_detection_confidence_threshold: float = Field(default=0.8, description="Language detection confidence threshold")
    persist_language_preference: bool = Field(default=True, description="Persist language preference across conversation")
    supported_languages: List[str] = Field(default_factory=lambda: ["ru", "en"], description="Supported languages")
    default_language: str = Field(default="ru", description="Default language when detection fails")
    
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="NLU provider instance configurations"
    )


class TextProcessorConfig(BaseModel):
    """Text processing pipeline component configuration"""
    enabled: bool = Field(default=False, description="Enable text processing pipeline component")
    stages: List[str] = Field(
        default_factory=lambda: ["asr_output", "tts_input", "command_input", "general"],
        description="Processing stages"
    )
    normalizers: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "numbers": {
                "enabled": True,
                "stages": ["asr_output", "general", "tts_input"]
            },
            "prepare": {
                "enabled": True,
                "stages": ["tts_input", "general"],
                "latin_to_cyrillic": True,
                "symbol_replacement": True
            },
            "runorm": {
                "enabled": True,
                "stages": ["tts_input"],
                "model_size": "small",
                "device": "cpu"
            }
        },
        description="Text normalizer configurations"
    )
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Provider-specific configurations"
    )


# ============================================================
# INTENT HANDLER CONFIGURATIONS (Phase 1)
# ============================================================

class VADConfig(BaseModel):
    """Voice Activity Detection configuration"""
    enabled: bool = Field(default=True, description="Enable VAD processing")
    
    # Core VAD parameters (Phase 4 specification)
    energy_threshold: float = Field(default=0.01, description="RMS energy threshold for voice detection", ge=0.0, le=1.0)
    sensitivity: float = Field(default=0.5, description="Detection sensitivity multiplier", ge=0.1, le=2.0)
    voice_duration_ms: int = Field(default=100, description="Minimum voice duration in milliseconds", ge=10, le=1000)
    silence_duration_ms: int = Field(default=200, description="Minimum silence duration to end voice segment in milliseconds", ge=50, le=2000)
    max_segment_duration_s: int = Field(default=10, description="Maximum voice segment duration in seconds", ge=1, le=60)
    
    # Frame-based configuration (internal implementation)
    voice_frames_required: int = Field(default=2, description="Consecutive voice frames to confirm voice onset", ge=1)
    silence_frames_required: int = Field(default=5, description="Consecutive silence frames to confirm voice end", ge=1)
    
    # Advanced features
    use_zero_crossing_rate: bool = Field(default=True, description="Enable Zero Crossing Rate analysis")
    adaptive_threshold: bool = Field(default=False, description="Enable adaptive threshold adjustment")
    noise_percentile: int = Field(default=15, description="Percentile for noise floor estimation", ge=1, le=50)
    voice_multiplier: float = Field(default=3.0, description="Multiplier above noise floor for voice threshold", ge=1.0, le=10.0)
    
    # Performance configuration
    processing_timeout_ms: int = Field(default=50, description="Maximum processing time per frame in milliseconds", ge=1)
    buffer_size_frames: int = Field(default=100, description="Maximum frames to buffer in voice segments", ge=10)
    
    # Audio normalization for ASR
    normalize_for_asr: bool = Field(default=True, description="Enable audio normalization before sending to ASR to prevent clipping")
    asr_target_rms: float = Field(default=0.15, description="Target RMS level for ASR audio normalization", ge=0.01, le=0.3)
    enable_fallback_to_original: bool = Field(default=True, description="Try original audio if normalized version fails recognition")
    
    # Backward compatibility alias for threshold
    @property
    def threshold(self) -> float:
        """Alias for energy_threshold for backward compatibility"""
        return self.energy_threshold
    
    @field_validator('energy_threshold')
    @classmethod
    def validate_energy_threshold(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("VAD energy threshold must be between 0.0 and 1.0")
        return v
    
    @field_validator('sensitivity')
    @classmethod
    def validate_sensitivity(cls, v):
        if not 0.1 <= v <= 2.0:
            raise ValueError("VAD sensitivity must be between 0.1 and 2.0")
        return v


# ============================================================
# MONITORING COMPONENT CONFIGURATION
# ============================================================

class MonitoringConfig(BaseModel):
    """Monitoring component configuration (Phase 5 unified metrics system)"""
    enabled: bool = Field(default=True, description="Enable unified monitoring system")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    dashboard_enabled: bool = Field(default=True, description="Enable analytics dashboard")
    notifications_enabled: bool = Field(default=True, description="Enable notification system")
    debug_tools_enabled: bool = Field(default=True, description="Enable debug tools")
    memory_management_enabled: bool = Field(default=True, description="Enable memory management")
    
    # Notification system configuration
    notifications_default_channel: str = Field(default="log", description="Default notification channel")
    notifications_tts_enabled: bool = Field(default=True, description="Enable TTS notifications")
    notifications_web_enabled: bool = Field(default=True, description="Enable web notifications")
    
    # Metrics collection configuration
    metrics_monitoring_interval: int = Field(default=300, ge=30, description="Metrics collection interval in seconds")
    metrics_retention_hours: int = Field(default=24, ge=1, description="Metrics retention period in hours")
    
    # Memory management configuration
    memory_cleanup_interval: int = Field(default=1800, ge=300, description="Memory cleanup interval in seconds")
    memory_aggressive_cleanup: bool = Field(default=False, description="Enable aggressive memory cleanup")
    
    # Debug tools configuration
    debug_auto_inspect_failures: bool = Field(default=True, description="Automatically inspect failed actions")
    debug_max_history: int = Field(default=1000, ge=100, description="Maximum debug history entries")
    
    # Analytics dashboard configuration
    analytics_dashboard_enabled: bool = Field(default=True, description="Enable analytics dashboard web interface")
    analytics_refresh_interval: int = Field(default=30, ge=5, description="Dashboard refresh interval in seconds")
    
    # NOTE: Monitoring endpoints are accessible via unified web API at system.web_port
    # All functionality available through /monitoring/* endpoints (WebAPIPlugin integration)


class ConversationHandlerConfig(BaseModel):
    """Configuration for conversation intent handler"""
    session_timeout: int = Field(default=1800, ge=60, description="Session timeout in seconds")
    max_sessions: int = Field(default=50, ge=1, le=1000, description="Maximum concurrent sessions")
    max_context_length: int = Field(default=10, ge=1, le=100, description="Maximum conversation context length")
    default_conversation_confidence: float = Field(default=0.6, ge=0.0, le=1.0, description="Default confidence threshold")


class TrainScheduleHandlerConfig(BaseModel):
    """Configuration for train schedule intent handler"""
    api_key: str = Field(default="", description="Yandex Schedules API key")
    from_station: str = Field(default="s9600681", description="Default departure station ID")
    to_station: str = Field(default="s2000002", description="Default destination station ID")
    max_results: int = Field(default=3, ge=1, le=20, description="Maximum schedule results")
    request_timeout: int = Field(default=10, ge=1, le=60, description="API request timeout in seconds")


class TimerHandlerConfig(BaseModel):
    """Configuration for timer intent handler"""
    min_seconds: int = Field(default=1, ge=1, description="Minimum timer duration in seconds")
    max_seconds: int = Field(default=86400, ge=1, description="Maximum timer duration in seconds")
    unit_multipliers: Dict[str, int] = Field(
        default={'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400},
        description="Time unit multipliers"
    )


class RandomHandlerConfig(BaseModel):
    """Configuration for random number intent handler"""
    default_max_number: int = Field(default=100, ge=1, description="Default maximum for random numbers")
    max_range_size: int = Field(default=1000000, ge=1, description="Maximum allowed range size")
    default_dice_sides: int = Field(default=6, ge=2, le=100, description="Default number of dice sides")


class DateTimeHandlerConfig(BaseModel):
    """Configuration for datetime intent handler"""
    timezone: Optional[str] = Field(default=None, description="Default timezone (None = system timezone)")
    date_format: str = Field(default="%Y-%m-%d", description="Default date format")
    time_format: str = Field(default="%H:%M:%S", description="Default time format")


class GreetingsHandlerConfig(BaseModel):
    """Configuration for greetings intent handler"""
    personalized: bool = Field(default=True, description="Use personalized greetings")
    context_aware: bool = Field(default=True, description="Consider time of day for greetings")


class SystemHandlerConfig(BaseModel):
    """Configuration for system intent handler"""
    allow_shutdown: bool = Field(default=False, description="Allow system shutdown commands")
    allow_restart: bool = Field(default=False, description="Allow system restart commands")
    info_detail_level: str = Field(default="basic", description="Level of system info to provide (basic/detailed)")


class IntentHandlerListConfig(BaseModel):
    """Intent handler enable/disable configuration"""
    enabled: List[str] = Field(
        default_factory=lambda: ["conversation", "greetings", "timer", "datetime", "system"],
        description="List of enabled intent handlers"
    )
    disabled: List[str] = Field(
        default_factory=list,
        description="List of explicitly disabled intent handlers (takes precedence)"
    )
    auto_discover: bool = Field(default=True, description="Automatically discover available handlers")
    discovery_paths: List[str] = Field(
        default_factory=lambda: ["irene.intents.handlers"],
        description="Entry-point paths for handler discovery"
    )
    
    # Asset validation configuration (moved from manager)
    asset_validation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "strict_mode": True,
            "validate_method_existence": True,
            "validate_spacy_patterns": False,
            "validate_json_schema": True
        },
        description="Asset validation configuration"
    )
    
    @field_validator('enabled')
    @classmethod
    def validate_enabled_handlers(cls, v):
        """Validate enabled handlers list"""
        if not v:
            raise ValueError("At least one intent handler must be enabled")
        
        # Check for invalid handler names (basic validation)
        invalid_chars = set()
        for handler in v:
            if not isinstance(handler, str):
                raise ValueError(f"Handler name must be string, got {type(handler)}: {handler}")
            if not handler.strip():
                raise ValueError("Handler name cannot be empty or whitespace")
            # Check for potentially problematic characters
            if any(char in handler for char in ['/', '\\', '..']):
                invalid_chars.add(handler)
        
        if invalid_chars:
            raise ValueError(f"Invalid characters in handler names: {invalid_chars}")
        
        return v
    
    @field_validator('disabled')
    @classmethod
    def validate_disabled_handlers(cls, v):
        """Validate disabled handlers list"""
        # Check for invalid handler names
        for handler in v:
            if not isinstance(handler, str):
                raise ValueError(f"Disabled handler name must be string, got {type(handler)}: {handler}")
            if not handler.strip():
                raise ValueError("Disabled handler name cannot be empty or whitespace")
        
        return v
    
    @model_validator(mode='after')
    def validate_enabled_disabled_consistency(self):
        """Validate consistency between enabled and disabled lists"""
        # Check for overlaps
        enabled_set = set(self.enabled)
        disabled_set = set(self.disabled)
        
        overlap = enabled_set & disabled_set
        if overlap:
            raise ValueError(f"Handlers cannot be both enabled and disabled: {overlap}")
        
        # Warn about redundant disabled entries
        if disabled_set and not overlap:
            redundant = disabled_set - enabled_set
            if redundant:
                # Note: This is a warning, not an error, so we'll log it during validation
                pass
        
        return self


class IntentSystemConfig(BaseModel):
    """Intent system component configuration"""
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
    handlers: IntentHandlerListConfig = Field(
        default_factory=IntentHandlerListConfig,
        description="Intent handler configuration"
    )
    
    # Handler-specific configurations
    conversation: ConversationHandlerConfig = Field(
        default_factory=ConversationHandlerConfig,
        description="Conversation handler configuration"
    )
    train_schedule: TrainScheduleHandlerConfig = Field(
        default_factory=TrainScheduleHandlerConfig,
        description="Train schedule handler configuration"
    )
    timer: TimerHandlerConfig = Field(
        default_factory=TimerHandlerConfig,
        description="Timer handler configuration"
    )
    random_handler: RandomHandlerConfig = Field(
        default_factory=RandomHandlerConfig,
        description="Random handler configuration"
    )
    datetime: DateTimeHandlerConfig = Field(
        default_factory=DateTimeHandlerConfig,
        description="DateTime handler configuration"
    )
    greetings: GreetingsHandlerConfig = Field(
        default_factory=GreetingsHandlerConfig,
        description="Greetings handler configuration"
    )
    system: SystemHandlerConfig = Field(
        default_factory=SystemHandlerConfig,
        description="System handler configuration"
    )
    
    @model_validator(mode='after')
    def validate_handler_configurations(self):
        """Validate handler-specific configurations for enabled handlers"""
        if not self.enabled:
            return self
        
        # Get enabled handlers list (considering disabled takes precedence)
        enabled_handlers = [h for h in self.handlers.enabled if h not in self.handlers.disabled]
        
        # Validate we have at least one enabled handler
        if not enabled_handlers:
            raise ValueError("At least one intent handler must remain enabled after applying disabled list")
        
        # Validate that each enabled handler has proper configuration
        handler_config_mapping = {
            "conversation": self.conversation,
            "train_schedule": self.train_schedule,
            "timer": self.timer,
            "random_handler": self.random_handler,
            "datetime": self.datetime,
            "greetings": self.greetings,
            "system": self.system
        }
        
        # Check for enabled handlers without configurations
        missing_configs = []
        for handler_name in enabled_handlers:
            if handler_name not in handler_config_mapping:
                missing_configs.append(handler_name)
        
        if missing_configs:
            raise ValueError(f"Enabled handlers missing configuration classes: {missing_configs}. "
                           f"Please add configuration classes for these handlers in IntentSystemConfig.")
        
        # Check for orphaned configurations (configurations for disabled handlers)
        final_disabled = set(self.handlers.disabled)
        final_enabled = set(enabled_handlers)
        orphaned_configs = []
        
        for handler_name in handler_config_mapping.keys():
            if handler_name in final_disabled and handler_name not in final_enabled:
                orphaned_configs.append(handler_name)
        
        # Log warning about orphaned configs (not an error)
        if orphaned_configs:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Configuration exists for disabled handlers: {orphaned_configs}. "
                         f"These configurations will be ignored.")
        
        # Validate fallback intent format
        if not self.fallback_intent or '.' not in self.fallback_intent:
            raise ValueError("fallback_intent must be in format 'handler.action' (e.g., 'conversation.general')")
        
        fallback_handler = self.fallback_intent.split('.')[0]
        if fallback_handler not in enabled_handlers:
            raise ValueError(f"Fallback intent handler '{fallback_handler}' is not enabled. "
                           f"Enabled handlers: {enabled_handlers}")
        
        for handler_name in enabled_handlers:
            if handler_name in handler_config_mapping:
                handler_config = handler_config_mapping[handler_name]
                
                # Validate configuration is present and valid
                if handler_config is None:
                    raise ValueError(f"Handler '{handler_name}' is enabled but has no configuration")
                
                # Additional validation for specific handlers
                if handler_name == "conversation":
                    if handler_config.session_timeout <= 0:
                        raise ValueError("Conversation handler session_timeout must be positive")
                    if handler_config.max_sessions <= 0:
                        raise ValueError("Conversation handler max_sessions must be positive")
                
                elif handler_name == "timer":
                    if handler_config.min_seconds >= handler_config.max_seconds:
                        raise ValueError("Timer handler min_seconds must be less than max_seconds")
                    if not handler_config.unit_multipliers:
                        raise ValueError("Timer handler unit_multipliers cannot be empty")
                
                elif handler_name == "random_handler":
                    if handler_config.default_max_number <= 0:
                        raise ValueError("Random handler default_max_number must be positive")
                    if handler_config.max_range_size <= 0:
                        raise ValueError("Random handler max_range_size must be positive")
                
                elif handler_name == "train_schedule":
                    if handler_config.max_results <= 0:
                        raise ValueError("Train schedule handler max_results must be positive")
                    if handler_config.request_timeout <= 0:
                        raise ValueError("Train schedule handler request_timeout must be positive")
        
        return self


# ============================================================
# ASSET MANAGEMENT CONFIGURATION (Environment-Driven)
# ============================================================

class AssetConfig(BaseModel):
    """Comprehensive asset management configuration"""
    assets_root: Path = Field(
        default_factory=lambda: Path(os.getenv("IRENE_ASSETS_ROOT", "~/.cache/irene")).expanduser(),
        description="Root directory for all assets (models, cache, credentials)"
    )
    
    # Directory management
    auto_create_dirs: bool = Field(default=True, description="Automatically create asset directories")
    cleanup_on_startup: bool = Field(default=False, description="Clean temporary files on startup")
    
    # Download configuration
    auto_download: bool = Field(default=True, description="Automatically download missing models")
    download_timeout_seconds: int = Field(default=300, description="Download timeout in seconds")
    max_download_retries: int = Field(default=3, description="Maximum download retry attempts")
    verify_downloads: bool = Field(default=True, description="Verify downloaded file integrity")
    
    # Cache configuration
    cache_enabled: bool = Field(default=True, description="Enable model and file caching")
    max_cache_size_mb: int = Field(default=2048, description="Maximum cache size in megabytes")
    cache_ttl_hours: int = Field(default=24, description="Cache time-to-live in hours")
    
    # Model management
    preload_essential_models: bool = Field(default=False, description="Preload essential models on startup")
    model_compression: bool = Field(default=True, description="Use compressed model formats when available")
    concurrent_downloads: int = Field(default=2, description="Maximum concurrent model downloads")
    
    # Subdirectories under assets root
    @property
    def models_root(self) -> Path:
        return self.assets_root / "models"
    
    @property
    def cache_root(self) -> Path:
        return self.assets_root / "cache"
    
    @property 
    def credentials_root(self) -> Path:
        return self.assets_root / "credentials"
    
    @property
    def temp_root(self) -> Path:
        return self.assets_root / "temp"
    
    @property
    def temp_audio_dir(self) -> Path:
        return self.temp_root / "audio"
    
    def model_post_init(self, __context):
        """Create directories after initialization if auto_create_dirs is True"""
        if self.auto_create_dirs:
            self._create_directories()
    
    def _create_directories(self) -> None:
        """Create all necessary directories"""
        directories = [
            self.assets_root,
            self.models_root,
            self.cache_root,
            self.credentials_root,
            self.temp_root,
            self.temp_audio_dir
        ]
        
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except Exception:
                # Silently continue if directory creation fails
                pass


# ============================================================
# WORKFLOW CONFIGURATION
# ============================================================

# ============================================================
# WORKFLOW-SPECIFIC CONFIGURATIONS  
# ============================================================

class UnifiedVoiceAssistantWorkflowConfig(BaseModel):
    """Configuration for unified voice assistant workflow pipeline stages"""
    voice_trigger_enabled: bool = Field(default=True, description="Enable voice trigger stage")
    asr_enabled: bool = Field(default=True, description="Enable ASR stage")
    text_processing_enabled: bool = Field(default=True, description="Enable text processing stage")
    nlu_enabled: bool = Field(default=True, description="Enable NLU stage")
    intent_execution_enabled: bool = Field(default=True, description="Enable intent execution stage")
    llm_enabled: bool = Field(default=True, description="Enable LLM processing stage")
    tts_enabled: bool = Field(default=True, description="Enable TTS output stage")
    audio_enabled: bool = Field(default=True, description="Enable audio playback stage")
    monitoring_enabled: bool = Field(default=True, description="Enable monitoring and metrics stage")
    
    # VAD processing configuration
    enable_vad_processing: bool = Field(default=True, description="Enable Voice Activity Detection processing for audio pipeline")


class WorkflowConfig(BaseModel):
    """Workflow processing pipeline configuration"""
    enabled: List[str] = Field(
        default_factory=lambda: ["unified_voice_assistant"],
        description="List of enabled workflows"
    )
    default: str = Field(
        default="unified_voice_assistant",
        description="Default workflow to execute"
    )
    
    # Workflow-specific configurations
    unified_voice_assistant: UnifiedVoiceAssistantWorkflowConfig = Field(
        default_factory=UnifiedVoiceAssistantWorkflowConfig,
        description="Unified voice assistant workflow configuration"
    )
    
    @field_validator('default')
    @classmethod
    def validate_default_workflow(cls, v, info):
        # Note: We can't access 'enabled' during field validation due to model construction order
        # This validation will be handled in the model_validator
        return v


# ============================================================
# ENVIRONMENT VARIABLE UTILITIES
# ============================================================

class EnvironmentVariableResolver:
    """Enablement-aware utility class for resolving ${VAR} patterns in configuration"""
    
    @staticmethod
    def substitute_env_vars(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Replace ${VAR} patterns with environment variable values, respecting enablement hierarchy"""
        return EnvironmentVariableResolver._substitute_recursive(config_dict, [], config_dict)
    
    @staticmethod
    def _substitute_recursive(value: Any, path: List[str], root_config: Dict[str, Any]) -> Any:
        """Recursively substitute environment variables with enablement awareness"""
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            var_name = value[2:-1]
            
            # Skip validation for disabled sections
            if not EnvironmentVariableResolver._is_section_enabled(path, root_config):
                return value  # Return unresolved for disabled sections
            
            # Validate and resolve for enabled sections
            env_value = os.getenv(var_name)
            if env_value is None:
                config_path = ".".join(path) if path else "root"
                raise ValueError(f"Required environment variable {var_name} is not set (used in enabled section: {config_path})")
            return env_value
            
        elif isinstance(value, dict):
            result = {}
            for k, v in value.items():
                new_path = path + [k]
                # Always process dict entries, but enablement checking happens at the env var level
                result[k] = EnvironmentVariableResolver._substitute_recursive(v, new_path, root_config)
            return result
            
        elif isinstance(value, list):
            return [EnvironmentVariableResolver._substitute_recursive(item, path, root_config) for item in value]
        
        return value
    
    @staticmethod
    def _is_section_enabled(path: List[str], config_dict: Dict[str, Any]) -> bool:
        """Check if a configuration section should be processed based on enablement hierarchy"""
        if len(path) == 0:
            return True
            
        # Handle provider-level enablement: component.providers.provider_name
        if len(path) >= 3 and path[1] == "providers":
            component_name = path[0]  # e.g., "tts"
            provider_name = path[2]   # e.g., "elevenlabs"
            
            # Check component is enabled
            component_enabled = config_dict.get("components", {}).get(component_name, False)
            if not component_enabled:
                return False
                
            # Check provider is enabled
            provider_config = config_dict.get(component_name, {}).get("providers", {}).get(provider_name, {})
            return provider_config.get("enabled", False)
        
        # Handle intent handler enablement: intent_system.handlers.handler_name
        if len(path) >= 3 and path[0] == "intent_system" and path[1] == "handlers":
            handler_name = path[2]
            
            # Check if intent system is enabled
            intent_system_enabled = config_dict.get("components", {}).get("intent_system", False)
            if not intent_system_enabled:
                return False
                
            # Check if handler is in enabled list
            enabled_handlers = config_dict.get("intent_system", {}).get("handlers", {}).get("enabled", [])
            disabled_handlers = config_dict.get("intent_system", {}).get("handlers", {}).get("disabled", [])
            
            # Disabled list takes precedence
            if handler_name in disabled_handlers:
                return False
                
            return handler_name in enabled_handlers
        
        # Handle input source enablement: inputs.source_name
        if len(path) >= 2 and path[0] == "inputs":
            input_name = path[1]
            
            # Skip config subsections like microphone_config, web_config, cli_config
            if input_name.endswith("_config"):
                base_input = input_name.replace("_config", "")
                return config_dict.get("inputs", {}).get(base_input, False)
            
            # Direct input enablement check
            return config_dict.get("inputs", {}).get(input_name, False)
        
        # Handle component-level enablement: component_name.* 
        if len(path) >= 1:
            component_name = path[0]
            
            # Check against known components
            known_components = ["tts", "asr", "audio", "llm", "voice_trigger", "nlu", "text_processor", "intent_system"]
            if component_name in known_components:
                return config_dict.get("components", {}).get(component_name, False)
        
        # Handle workflow enablement
        if len(path) >= 2 and path[0] == "workflows":
            workflow_name = path[1]
            enabled_workflows = config_dict.get("workflows", {}).get("enabled", [])
            return workflow_name in enabled_workflows
        
        # Handle system-level sections (always enabled)
        if path[0] in ["system", "components", "assets"]:
            return True
            
        # Default to enabled for unknown sections (conservative approach)
        return True
    
    @staticmethod
    def find_env_var_patterns(config: Dict[str, Any]) -> List[str]:
        """Find all ${VAR} patterns in enabled configuration sections only"""
        patterns = []
        
        def _scan_value(value: Any, path: List[str]):
            # Only scan if section is enabled
            if not EnvironmentVariableResolver._is_section_enabled(path, config):
                return
                
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                var_name = value[2:-1]
                patterns.append(var_name)
            elif isinstance(value, dict):
                for k, v in value.items():
                    _scan_value(v, path + [k])
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    _scan_value(v, path + [str(i)])
        
        _scan_value(config, [])
        return patterns
    
    @staticmethod
    def validate_environment_variables(config: Dict[str, Any]) -> None:
        """Validate ${VAR} patterns have corresponding environment variables for enabled sections only"""
        patterns = EnvironmentVariableResolver.find_env_var_patterns(config)
        missing_vars = []
        
        for var_name in patterns:
            if os.getenv(var_name) is None:
                missing_vars.append(var_name)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables for enabled components: {missing_vars}")


# ============================================================
# COMPONENT LOADING SYSTEM
# ============================================================

class ComponentRegistry:
    """Registry for initialized components"""
    
    def __init__(self):
        self._components: Dict[str, Any] = {}
    
    def register(self, name: str, component: Any) -> None:
        """Register a component"""
        self._components[name] = component
    
    def get(self, name: str) -> Optional[Any]:
        """Get a component by name"""
        return self._components.get(name)
    
    def has(self, name: str) -> bool:
        """Check if component is registered"""
        return name in self._components
    
    def list_components(self) -> List[str]:
        """List all registered component names"""
        return list(self._components.keys())


class ComponentLoader:
    """Component loader using entry-point discovery"""
    
    def __init__(self):
        from ..utils.loader import dynamic_loader
        self.dynamic_loader = dynamic_loader
    
    def load_components(self, config: ComponentConfig) -> ComponentRegistry:
        """Load components based on configuration using entry-point discovery"""
        registry = ComponentRegistry()
        
        # Get available components via entry-points
        available_components = self.dynamic_loader.discover_providers("irene.components")
        
        # Load enabled components
        for component_name in available_components:
            if self._is_component_enabled(component_name, config):
                try:
                    component_class = available_components[component_name]
                    component_instance = component_class()
                    registry.register(component_name, component_instance)
                except Exception as e:
                    # Log error but continue with other components
                    import logging
                    logging.getLogger(__name__).error(f"Failed to load component '{component_name}': {e}")
        
        return registry
    
    def _is_component_enabled(self, component_name: str, config: ComponentConfig) -> bool:
        """Check if component is enabled in configuration"""
        return getattr(config, component_name, False)
    
    def get_available_components(self) -> Dict[str, Type]:
        """Get available components via entry-point discovery"""
        return self.dynamic_loader.discover_providers("irene.components")


# ============================================================
# CORE CONFIGURATION (NEW ARCHITECTURE)
# ============================================================

class CoreConfig(BaseSettings):
    """Main configuration for Irene Voice Assistant v14+ with clean architecture"""
    
    # Core settings
    name: str = Field(default="Irene", description="Assistant name")
    version: str = Field(default="14.0.0", description="Version")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    
    # New architecture sections
    system: SystemConfig = Field(default_factory=SystemConfig, description="System capabilities configuration")
    inputs: InputConfig = Field(default_factory=InputConfig, description="Input sources configuration")
    components: ComponentConfig = Field(default_factory=ComponentConfig, description="Component configuration")
    assets: AssetConfig = Field(default_factory=AssetConfig, description="Asset management configuration")
    workflows: WorkflowConfig = Field(default_factory=WorkflowConfig, description="Workflow configuration")
    
    # Component-specific configurations
    tts: TTSConfig = Field(default_factory=TTSConfig, description="TTS component configuration")
    audio: AudioConfig = Field(default_factory=AudioConfig, description="Audio component configuration")
    asr: ASRConfig = Field(default_factory=ASRConfig, description="ASR component configuration")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM component configuration")
    voice_trigger: VoiceTriggerConfig = Field(default_factory=VoiceTriggerConfig, description="Voice trigger component configuration")
    nlu: NLUConfig = Field(default_factory=NLUConfig, description="NLU component configuration")
    text_processor: TextProcessorConfig = Field(default_factory=TextProcessorConfig, description="Text processor component configuration")
    intent_system: IntentSystemConfig = Field(default_factory=IntentSystemConfig, description="Intent system component configuration")
    vad: VADConfig = Field(default_factory=VADConfig, description="Voice Activity Detection component configuration")
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig, description="Monitoring component configuration (Phase 5 unified metrics system)")
    
    # Language and locale
    language: str = Field(default="en-US", description="Primary language")
    timezone: Optional[str] = Field(default=None, description="Timezone (e.g., UTC, America/New_York)")
    
    # Runtime settings
    max_concurrent_commands: int = Field(default=10, ge=1, description="Maximum concurrent commands")
    command_timeout_seconds: float = Field(default=30.0, gt=0, description="Command timeout in seconds")
    context_timeout_minutes: int = Field(default=30, ge=1, description="Context timeout in minutes")
    
    model_config = {
        "env_prefix": "IRENE_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }
    
    @model_validator(mode='after')
    def validate_system_dependencies(self):
        """Validate cross-component dependencies"""
        # TTS requires Audio component
        if self.components.tts and not self.components.audio:
            raise ValueError("TTS component requires Audio component. Either disable TTS or enable Audio component.")
        
        # Microphone hardware requires microphone input
        if self.system.microphone_enabled and not self.inputs.microphone:
            raise ValueError("Microphone hardware enabled but input source disabled")
        
        # Component-specific config sync
        self.tts.enabled = self.components.tts
        self.audio.enabled = self.components.audio
        self.asr.enabled = self.components.asr
        self.llm.enabled = self.components.llm
        self.voice_trigger.enabled = self.components.voice_trigger
        self.nlu.enabled = self.components.nlu
        self.text_processor.enabled = self.components.text_processor
        self.intent_system.enabled = self.components.intent_system
        
        # Validate default workflow is in enabled list
        if self.workflows.default not in self.workflows.enabled:
            raise ValueError(f"Default workflow '{self.workflows.default}' must be in enabled workflows list")
        
        return self
    
    @model_validator(mode='after') 
    def validate_entry_point_consistency(self):
        """Validate component names match entry-points"""
        try:
            loader = ComponentLoader()
            available_components = loader.get_available_components()
            
            # Check that all enabled components have corresponding entry-points
            enabled_components = []
            for attr_name in ['tts', 'asr', 'audio', 'llm', 'voice_trigger', 'nlu', 'text_processor', 'intent_system']:
                if getattr(self.components, attr_name, False):
                    enabled_components.append(attr_name)
            
            missing_components = []
            for component_name in enabled_components:
                if component_name not in available_components:
                    missing_components.append(component_name)
            
            if missing_components:
                import logging
                logging.getLogger(__name__).warning(
                    f"Enabled components missing entry-points: {missing_components}. "
                    f"Available components: {list(available_components.keys())}"
                )
        except Exception as e:
            # Don't fail configuration loading due to entry-point validation issues
            import logging
            logging.getLogger(__name__).warning(f"Entry-point validation failed: {e}")
        
        return self

    def resolve_environment_variables(self) -> 'CoreConfig':
        """Resolve all ${VAR} patterns in configuration (enablement-aware)"""
        config_dict = self.model_dump()
        
        # Validate environment variables exist (only for enabled sections)
        EnvironmentVariableResolver.validate_environment_variables(config_dict)
        
        # Substitute environment variables (enablement-aware)
        resolved_dict = EnvironmentVariableResolver.substitute_env_vars(config_dict)
        
        # Return new instance with resolved values
        return CoreConfig.model_validate(resolved_dict)


# ============================================================
# DEPLOYMENT PROFILE PRESETS (Backwards Compatibility)
# ============================================================

def create_voice_profile() -> CoreConfig:
    """Create voice assistant profile configuration"""
    config = CoreConfig()
    # System capabilities
    config.system.microphone_enabled = True
    config.system.audio_playback_enabled = True
    config.system.web_api_enabled = True
    # Input sources
    config.inputs.microphone = True
    config.inputs.web = True
    config.inputs.cli = True
    config.inputs.default_input = "microphone"
    # Components
    config.components.tts = True
    config.components.asr = True
    config.components.audio = True
    config.components.voice_trigger = True
    config.components.nlu = True
    config.components.text_processor = True
    config.components.intent_system = True
    return config


def create_api_profile() -> CoreConfig:
    """Create API-only profile configuration"""
    config = CoreConfig()
    # System capabilities
    config.system.microphone_enabled = False
    config.system.audio_playback_enabled = False
    config.system.web_api_enabled = True
    # Input sources
    config.inputs.microphone = False
    config.inputs.web = True
    config.inputs.cli = False
    config.inputs.default_input = "web"
    # Components
    config.components.tts = False
    config.components.asr = False
    config.components.audio = False
    config.components.voice_trigger = False
    config.components.nlu = True
    config.components.text_processor = True
    config.components.intent_system = True
    return config


def create_headless_profile() -> CoreConfig:
    """Create headless profile configuration"""
    config = CoreConfig()
    # System capabilities
    config.system.microphone_enabled = False
    config.system.audio_playback_enabled = False
    config.system.web_api_enabled = False
    # Input sources
    config.inputs.microphone = False
    config.inputs.web = False
    config.inputs.cli = True
    config.inputs.default_input = "cli"
    # Components
    config.components.tts = False
    config.components.asr = False
    config.components.audio = False
    config.components.voice_trigger = False
    config.components.nlu = True
    config.components.text_processor = True
    config.components.intent_system = True
    return config


def create_default_config() -> CoreConfig:
    """Create a default configuration with sensible defaults"""
    return CoreConfig()


def create_config_from_profile(profile_name: str) -> CoreConfig:
    """Create configuration from a deployment profile"""
    profiles = {
        "voice": create_voice_profile,
        "api": create_api_profile, 
        "headless": create_headless_profile
    }
    
    if profile_name not in profiles:
        raise ValueError(f"Unknown profile: {profile_name}. Available: {list(profiles.keys())}")
        
    return profiles[profile_name]()