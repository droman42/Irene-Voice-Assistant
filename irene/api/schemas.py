"""
Centralized API Schemas for Irene Voice Assistant

This module contains all Pydantic schemas for API endpoints across components,
including both HTTP REST APIs and WebSocket message formats.

Organization:
- Base classes for common patterns
- Component-specific message schemas  
- Request/Response models for HTTP APIs
- WebSocket message formats for real-time communication

Follows AsyncAPI and OpenAPI standards for documentation generation.
"""

import time
from typing import Literal, Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field


# ============================================================
# BASE API SCHEMAS
# ============================================================

class BaseAPIMessage(BaseModel):
    """Base class for all API messages"""
    type: str = Field(description="Message type identifier")
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp when message was created"
    )

    class Config:
        json_encoders = {
            float: lambda v: round(v, 3)  # Round timestamps to milliseconds
        }


class BaseAPIRequest(BaseModel):
    """Base class for API request models"""
    pass


class BaseAPIResponse(BaseModel):
    """Base class for API response models"""
    success: bool = Field(description="Whether the operation was successful")
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp when response was generated"
    )

    class Config:
        json_encoders = {
            float: lambda v: round(v, 3)
        }


class ErrorResponse(BaseAPIResponse):
    """Standard error response format"""
    success: Literal[False] = Field(default=False)
    error: str = Field(description="Error message describing what went wrong")
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code"
    )
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": False,
                    "error": "Provider not available",
                    "error_code": "PROVIDER_UNAVAILABLE",
                    "timestamp": 1704067200.123
                }
            ]
        }


# ============================================================
# ASR (AUTOMATIC SPEECH RECOGNITION) SCHEMAS
# ============================================================

class AudioChunkMessage(BaseAPIMessage):
    """
    WebSocket message containing audio data for real-time transcription
    
    Sent by clients to ASR WebSocket endpoints for streaming speech recognition.
    """
    type: Literal["audio_chunk"] = Field(
        default="audio_chunk",
        description="Message type identifier"
    )
    data: str = Field(
        description="Base64-encoded audio data (PCM, 16kHz, 16-bit, mono recommended)",
        example="UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqF..."
    )
    language: Optional[str] = Field(
        default="ru",
        description="Language code for transcription (ISO 639-1 format)",
        example="ru"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Specific ASR provider to use (optional, uses default if not specified)",
        example="whisper"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "audio_chunk",
                    "data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqF...",
                    "language": "ru",
                    "provider": "whisper",
                    "timestamp": 1704067200.123
                },
                {
                    "type": "audio_chunk",
                    "data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqF...",
                    "language": "en",
                    "timestamp": 1704067200.456
                }
            ]
        }


class TranscriptionResultMessage(BaseAPIMessage):
    """
    WebSocket message containing transcription results
    
    Sent by ASR WebSocket endpoints to clients with speech recognition results.
    """
    type: Literal["transcription_result"] = Field(
        default="transcription_result",
        description="Message type identifier"
    )
    text: str = Field(
        description="Transcribed text from the audio chunk",
        example="привет как дела"
    )
    provider: str = Field(
        description="ASR provider that performed the transcription",
        example="whisper"
    )
    language: str = Field(
        description="Language code used for transcription",
        example="ru"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score for the transcription (0.0-1.0, if available)",
        ge=0.0,
        le=1.0,
        example=0.95
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "transcription_result",
                    "text": "привет как дела",
                    "provider": "whisper",
                    "language": "ru",
                    "timestamp": 1704067200.123,
                    "confidence": 0.95
                },
                {
                    "type": "transcription_result",
                    "text": "hello how are you",
                    "provider": "whisper",
                    "language": "en",
                    "timestamp": 1704067201.456
                }
            ]
        }


class TranscriptionErrorMessage(BaseAPIMessage):
    """
    WebSocket message containing transcription error information
    
    Sent by ASR WebSocket endpoints when speech recognition fails.
    """
    type: Literal["error"] = Field(
        default="error",
        description="Message type identifier"
    )
    error: str = Field(
        description="Error message describing what went wrong",
        example="Audio format not supported"
    )
    provider: Optional[str] = Field(
        default=None,
        description="ASR provider that encountered the error (if known)",
        example="whisper"
    )
    recoverable: bool = Field(
        default=True,
        description="Whether the client can retry the request",
        example=True
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "error",
                    "error": "Audio format not supported",
                    "timestamp": 1704067200.123,
                    "provider": "whisper",
                    "recoverable": True
                },
                {
                    "type": "error",
                    "error": "Provider temporarily unavailable",
                    "timestamp": 1704067201.456,
                    "recoverable": True
                }
            ]
        }


# ASR HTTP API Schemas
class ASRTranscribeRequest(BaseAPIRequest):
    """HTTP request for file-based transcription"""
    # Note: File upload handled by FastAPI UploadFile
    provider: Optional[str] = Field(
        default=None,
        description="Specific ASR provider to use"
    )
    language: str = Field(
        default="ru",
        description="Language code for transcription"
    )
    enhance: bool = Field(
        default=False,
        description="Whether to enhance audio quality before transcription"
    )


class ASRTranscribeResponse(BaseAPIResponse):
    """HTTP response for file-based transcription"""
    text: str = Field(description="Transcribed text")
    provider: str = Field(description="ASR provider used")
    language: str = Field(description="Language used for transcription")
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score if available"
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds"
    )


class ASRProvidersResponse(BaseAPIResponse):
    """Response containing available ASR providers"""
    providers: Dict[str, Dict[str, Any]] = Field(
        description="Available providers and their capabilities"
    )
    default: str = Field(description="Default provider name")


# ============================================================
# TTS (TEXT-TO-SPEECH) SCHEMAS
# ============================================================

class TTSRequest(BaseAPIRequest):
    """HTTP request for text-to-speech synthesis"""
    text: str = Field(description="Text to synthesize")
    provider: Optional[str] = Field(
        default=None,
        description="Specific TTS provider to use"
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker voice to use"
    )
    language: Optional[str] = Field(
        default=None,
        description="Language code for synthesis"
    )


class TTSResponse(BaseAPIResponse):
    """HTTP response for text-to-speech synthesis"""
    provider: str = Field(description="TTS provider used")
    text: str = Field(description="Original text")
    audio_content: Optional[str] = Field(
        default=None,
        description="Base64 encoded audio data"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if synthesis failed"
    )


class TTSProvidersResponse(BaseAPIResponse):
    """Response containing available TTS providers"""
    providers: Dict[str, Any] = Field(
        description="Available providers and their capabilities"
    )
    default: str = Field(description="Default provider name")


# ============================================================
# NLU (NATURAL LANGUAGE UNDERSTANDING) SCHEMAS
# ============================================================

class NLURequest(BaseAPIRequest):
    """HTTP request for intent recognition"""
    text: str = Field(description="Text to analyze for intent")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Context information for intent recognition"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Specific NLU provider to use"
    )


class IntentResponse(BaseAPIResponse):
    """HTTP response containing recognized intent"""
    name: str = Field(description="Intent name")
    entities: Dict[str, Any] = Field(description="Extracted entities")
    confidence: float = Field(description="Recognition confidence score")
    provider: str = Field(description="NLU provider used")
    domain: Optional[str] = Field(
        default=None,
        description="Intent domain"
    )
    action: Optional[str] = Field(
        default=None,
        description="Intent action"
    )


class NLUConfigureRequest(BaseAPIRequest):
    """HTTP request for configuring NLU settings"""
    provider: str = Field(description="Provider name to configure")
    set_as_default: bool = Field(
        default=False,
        description="Whether to set this provider as default"
    )
    confidence_threshold: Optional[float] = Field(
        default=None,
        description="Confidence threshold for intent recognition",
        ge=0.0,
        le=1.0
    )


class NLUConfigResponse(BaseAPIResponse):
    """HTTP response for NLU configuration"""
    confidence_threshold: float = Field(description="Current confidence threshold")
    fallback_intent: str = Field(description="Fallback intent name")
    default_provider: Optional[str] = Field(description="Default NLU provider")
    available_providers: List[str] = Field(description="List of available providers")


class NLUProvidersResponse(BaseAPIResponse):
    """Response containing available NLU providers"""
    providers: Dict[str, Dict[str, Any]] = Field(
        description="Available providers and their capabilities"
    )
    default: Optional[str] = Field(description="Default provider name")


# ============================================================
# SYSTEM/HEALTH SCHEMAS
# ============================================================

class HealthResponse(BaseAPIResponse):
    """System health check response"""
    status: Literal["healthy", "unhealthy"] = Field(description="System status")
    version: str = Field(description="System version")
    uptime: Optional[float] = Field(
        default=None,
        description="System uptime in seconds"
    )


class ComponentInfo(BaseModel):
    """Information about a system component"""
    name: str = Field(description="Component name")
    status: str = Field(description="Component status")
    version: Optional[str] = Field(default=None, description="Component version")
    capabilities: List[str] = Field(
        default_factory=list,
        description="Component capabilities"
    )


class SystemStatusResponse(BaseAPIResponse):
    """Comprehensive system status response"""
    system: str = Field(description="Overall system status")
    version: str = Field(description="System version")
    mode: str = Field(description="Operating mode")
    uptime: float = Field(description="System uptime in seconds")
    components: Dict[str, ComponentInfo] = Field(
        description="Individual component status"
    )


# ============================================================
# COMMAND EXECUTION SCHEMAS
# ============================================================

class CommandRequest(BaseAPIRequest):
    """Request to execute a command"""
    command: str = Field(description="Command text to execute")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional command metadata"
    )


class CommandResponse(BaseAPIResponse):
    """Response from command execution"""
    response: str = Field(description="Command execution result")
    error: Optional[str] = Field(
        default=None,
        description="Error message if command failed"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional response metadata"
    )


# ============================================================
# LLM (LARGE LANGUAGE MODEL) SCHEMAS
# ============================================================

class ChatMessage(BaseModel):
    """Individual message in a chat conversation"""
    role: Literal["user", "assistant", "system"] = Field(
        description="Role of the message sender",
        example="user"
    )
    content: str = Field(
        description="Content of the message",
        example="Hello, how can you help me today?"
    )


class LLMEnhanceRequest(BaseAPIRequest):
    """HTTP request for text enhancement using LLM"""
    text: str = Field(
        description="Text to enhance or improve",
        example="The weather is very good today"
    )
    task: str = Field(
        default="improve",
        description="Enhancement task type",
        example="improve"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Specific LLM provider to use",
        example="openai"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional provider-specific parameters"
    )


class LLMEnhanceResponse(BaseAPIResponse):
    """HTTP response for text enhancement"""
    original_text: str = Field(description="Original input text")
    enhanced_text: str = Field(description="Enhanced/improved text")
    task: str = Field(description="Enhancement task that was performed")
    provider: str = Field(description="LLM provider used")


class LLMChatRequest(BaseAPIRequest):
    """HTTP request for chat completion"""
    messages: List[ChatMessage] = Field(
        description="List of chat messages in conversation",
        example=[
            {"role": "user", "content": "What is artificial intelligence?"}
        ]
    )
    provider: Optional[str] = Field(
        default=None,
        description="Specific LLM provider to use",
        example="openai"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional provider-specific parameters like temperature, max_tokens"
    )


class LLMChatResponse(BaseAPIResponse):
    """HTTP response for chat completion"""
    response: str = Field(description="Generated response from the LLM")
    provider: str = Field(description="LLM provider used")
    usage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Token usage statistics if available"
    )


class LLMConfigureRequest(BaseAPIRequest):
    """HTTP request for configuring LLM settings"""
    provider: str = Field(description="Provider name to configure")
    set_as_default: bool = Field(
        default=False,
        description="Whether to set this provider as default"
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific configuration parameters"
    )


class LLMProvidersResponse(BaseAPIResponse):
    """Response containing available LLM providers"""
    providers: Dict[str, Dict[str, Any]] = Field(
        description="Available providers and their capabilities"
    )
    default: str = Field(description="Default provider name")


# ============================================================
# INTENT SYSTEM SCHEMAS  
# ============================================================

class IntentHandlerInfo(BaseModel):
    """Information about an intent handler"""
    class_name: str = Field(description="Handler class name", alias="class")
    domains: List[str] = Field(description="Supported domains")
    actions: List[str] = Field(description="Supported actions")
    available: bool = Field(description="Whether handler is available")
    capabilities: Dict[str, Any] = Field(description="Handler capabilities")
    has_donation: bool = Field(description="Whether handler has donation")
    supports_donation_routing: bool = Field(description="Whether handler supports donation routing")
    donation: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Donation information if available"
    )


class IntentSystemStatusResponse(BaseAPIResponse):
    """Response for intent system status"""
    status: str = Field(description="System status")
    handlers_count: int = Field(description="Number of loaded handlers")
    handlers: List[str] = Field(description="List of handler names")
    donations_count: int = Field(description="Number of loaded donations")
    donations: List[str] = Field(description="List of donation names")
    registry_patterns: List[str] = Field(description="Registered intent patterns")
    donation_routing_enabled: bool = Field(description="Whether donation routing is enabled")
    parameter_extraction_integrated: bool = Field(description="Whether parameter extraction is integrated")
    configuration: Optional[Dict[str, Any]] = Field(description="Current configuration")


class IntentHandlersResponse(BaseAPIResponse):
    """Response for intent handlers listing"""
    handlers: Dict[str, IntentHandlerInfo] = Field(description="Available handlers information")


class IntentActionCancelRequest(BaseAPIRequest):
    """Request to cancel an active action"""
    domain: str = Field(description="Domain of the action to cancel")
    reason: str = Field(
        default="User requested cancellation",
        description="Reason for cancellation"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for targeted cancellation"
    )


class IntentActionResponse(BaseAPIResponse):
    """Response for action operations"""
    message: str = Field(description="Operation result message")
    domain: Optional[str] = Field(description="Action domain")
    reason: Optional[str] = Field(description="Action reason")
    note: Optional[str] = Field(description="Additional notes")


class IntentActiveActionsResponse(BaseAPIResponse):
    """Response for active actions listing"""
    message: str = Field(description="Response message")
    active_actions: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of active actions"
    )
    note: Optional[str] = Field(description="Additional notes")


class IntentRegistryResponse(BaseAPIResponse):
    """Response for intent registry patterns"""
    patterns: Dict[str, Dict[str, Any]] = Field(description="Registry patterns information")


class IntentReloadResponse(BaseAPIResponse):
    """Response for handler reload operation"""
    status: str = Field(description="Reload status")
    handlers_count: int = Field(description="Number of handlers loaded")
    handlers: List[str] = Field(description="List of loaded handler names")
    error: Optional[str] = Field(
        default=None,
        description="Error message if reload failed"
    )


# ============================================================
# AUDIO PLAYBACK SCHEMAS
# ============================================================

class AudioPlayRequest(BaseAPIRequest):
    """Request for file-based audio playback (moved from component)"""
    # Note: File upload handled by FastAPI UploadFile
    provider: Optional[str] = Field(
        default=None,
        description="Specific audio provider to use"
    )
    volume: Optional[float] = Field(
        default=None,
        description="Playback volume (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    device: Optional[str] = Field(
        default=None,
        description="Audio output device ID"
    )


class AudioPlayResponse(BaseAPIResponse):
    """Response for audio playback operations"""
    provider: str = Field(description="Audio provider used")
    file: Optional[str] = Field(description="Original filename")
    size: int = Field(description="Audio data size in bytes")


class AudioStreamRequest(BaseAPIRequest):
    """Request for stream-based audio playback"""
    # Note: Audio data handled separately as bytes
    format: str = Field(
        default="wav",
        description="Audio format",
        example="wav"
    )
    provider: Optional[str] = Field(
        default=None,
        description="Specific audio provider to use"
    )
    volume: Optional[float] = Field(
        default=None,
        description="Playback volume (0.0-1.0)",
        ge=0.0,
        le=1.0
    )


class AudioStreamResponse(BaseAPIResponse):
    """Response for audio stream playback"""
    provider: str = Field(description="Audio provider used")
    format: str = Field(description="Audio format processed")
    size: int = Field(description="Audio data size in bytes")


class AudioStopResponse(BaseAPIResponse):
    """Response for audio stop operation"""
    message: str = Field(description="Stop operation message")


class AudioDeviceInfo(BaseModel):
    """Information about an audio output device"""
    id: str = Field(description="Device ID")
    name: str = Field(description="Device name")
    default: bool = Field(description="Whether this is the default device")


class AudioDevicesResponse(BaseAPIResponse):
    """Response for audio devices listing"""
    provider: str = Field(description="Provider that reported devices")
    devices: List[Dict[str, Any]] = Field(description="Available audio output devices")


class AudioConfigureRequest(BaseAPIRequest):
    """Request for configuring audio settings"""
    provider: Optional[str] = Field(
        default=None,
        description="Provider to configure"
    )
    set_as_default: bool = Field(
        default=False,
        description="Whether to set this provider as default"
    )
    volume: Optional[float] = Field(
        default=None,
        description="Volume to set (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    device: Optional[str] = Field(
        default=None,
        description="Device ID to set as output"
    )


class AudioConfigureResponse(BaseAPIResponse):
    """Response for audio configuration"""
    provider: str = Field(description="Configured provider")
    default_provider: str = Field(description="Current default provider")
    volume: Optional[float] = Field(description="Set volume")
    device: Optional[str] = Field(description="Set device")


class AudioProvidersResponse(BaseAPIResponse):
    """Response containing available audio providers"""
    providers: Dict[str, Dict[str, Any]] = Field(
        description="Available providers and their capabilities"
    )
    default: str = Field(description="Default provider name")
    fallbacks: List[str] = Field(description="Fallback provider names")


# ============================================================
# VOICE TRIGGER SCHEMAS
# ============================================================

class VoiceTriggerStatus(BaseAPIResponse):
    """Response for voice trigger status (moved from component)"""
    active: bool = Field(description="Whether voice trigger is active")
    wake_words: List[str] = Field(description="Current wake words")
    threshold: float = Field(
        description="Detection threshold",
        ge=0.0,
        le=1.0
    )
    provider: str = Field(description="Current provider name")
    providers_available: List[str] = Field(description="Available provider names")


class WakeWordConfig(BaseAPIRequest):
    """Request for configuring wake word settings (moved from component)"""
    wake_words: List[str] = Field(
        description="Wake words to configure",
        min_items=1
    )
    threshold: float = Field(
        default=0.8,
        description="Detection threshold",
        ge=0.0,
        le=1.0
    )


class VoiceTriggerConfigureResponse(BaseAPIResponse):
    """Response for voice trigger configuration"""
    config: WakeWordConfig = Field(description="Applied configuration")
    updated_words: bool = Field(description="Whether wake words were updated")
    updated_threshold: bool = Field(description="Whether threshold was updated")


class VoiceTriggerSwitchRequest(BaseAPIRequest):
    """Request to switch voice trigger provider"""
    provider_name: str = Field(description="Provider name to switch to")


class VoiceTriggerSwitchResponse(BaseAPIResponse):
    """Response for provider switch operation"""
    active_provider: str = Field(description="Now active provider")
    wake_words: List[str] = Field(description="Current wake words")
    threshold: float = Field(description="Current threshold")


class VoiceTriggerProvidersResponse(BaseAPIResponse):
    """Response containing available voice trigger providers"""
    providers: Dict[str, Dict[str, Any]] = Field(
        description="Available providers and their capabilities"
    )
    default: Optional[str] = Field(description="Default provider name")
    fallbacks: List[str] = Field(description="Fallback provider names")


# ============================================================
# TEXT PROCESSING SCHEMAS
# ============================================================

class TextProcessingRequest(BaseAPIRequest):
    """Request for text processing and normalization (moved from component)"""
    text: str = Field(description="Text to process")
    stage: str = Field(
        default="general",
        description="Processing stage",
        example="general"
    )
    normalizer: Optional[str] = Field(
        default=None,
        description="Specific normalizer to use (optional)",
        example="numbers"
    )


class TextProcessingResponse(BaseAPIResponse):
    """Response for text processing operations (moved from component)"""
    original_text: str = Field(description="Original input text")
    processed_text: str = Field(description="Processed/normalized text")
    stage: str = Field(description="Processing stage used")
    normalizers_applied: List[str] = Field(description="Names of normalizers that were applied")


class NumberConversionRequest(BaseAPIRequest):
    """Request for number-to-words conversion (moved from component)"""
    text: str = Field(description="Text containing numbers to convert")
    language: str = Field(
        default="ru",
        description="Language for number conversion",
        example="ru"
    )


class NumberConversionResponse(BaseAPIResponse):
    """Response for number-to-words conversion"""
    original_text: str = Field(description="Original input text")
    processed_text: str = Field(description="Text with numbers converted to words")
    language: str = Field(description="Language used for conversion")


class TextNormalizerInfo(BaseModel):
    """Information about a text normalizer"""
    stages: List[str] = Field(description="Available processing stages")
    applies_to: List[str] = Field(description="Stages this normalizer applies to")
    description: str = Field(description="Normalizer description")


class TextProcessingNormalizersResponse(BaseAPIResponse):
    """Response for text processing normalizers listing"""
    normalizers: Dict[str, TextNormalizerInfo] = Field(description="Available normalizers")
    pipeline_stages: List[str] = Field(description="Available pipeline stages")
    available_languages: List[str] = Field(description="Supported languages for number conversion")


class TextProcessingConfigResponse(BaseAPIResponse):
    """Response for text processing configuration"""
    normalizer_count: int = Field(description="Number of loaded normalizers")
    supported_stages: List[str] = Field(description="Supported processing stages")
    supported_languages: List[str] = Field(description="Supported languages")
    dependencies: List[str] = Field(description="Component dependencies")


# ============================================================
# MONITORING SCHEMAS
# ============================================================

class MonitoringStatusResponse(BaseAPIResponse):
    """Response for monitoring system status (moved from component)"""
    status: str = Field(description="Overall monitoring status")
    services: Dict[str, bool] = Field(description="Status of monitoring services")
    uptime: float = Field(description="System uptime in seconds")


class MetricsResponse(BaseAPIResponse):
    """Response for system metrics (moved from component)"""
    system_metrics: Dict[str, Any] = Field(description="System-level metrics")
    domain_metrics: Dict[str, Any] = Field(description="Domain-specific metrics")
    performance_summary: Dict[str, Any] = Field(description="Performance summary")


class MemoryStatusResponse(BaseAPIResponse):
    """Response for memory status (moved from component)"""
    memory_usage: Dict[str, Any] = Field(description="Current memory usage")
    cleanup_needed: Dict[str, bool] = Field(description="Areas requiring cleanup")
    recommendations: List[Dict[str, Any]] = Field(description="Memory optimization recommendations")


class NotificationResponse(BaseAPIResponse):
    """Response for notification operations (moved from component)"""
    message: str = Field(description="Notification result message")


class DebugResponse(BaseAPIResponse):
    """Response for debug operations (moved from component)"""
    debug_status: Dict[str, Any] = Field(description="Current debug status")
    inspection_history: List[Dict[str, Any]] = Field(description="Debug inspection history")


class DashboardResponse(BaseAPIResponse):
    """Response for analytics dashboard (moved from component)"""
    dashboard_data: Dict[str, Any] = Field(description="Dashboard visualization data")
    health_summary: Dict[str, Any] = Field(description="System health summary")


class AnalyticsReportResponse(BaseAPIResponse):
    """Response for comprehensive analytics report (moved from component)"""
    timestamp: float = Field(description="Report generation timestamp")
    report_type: str = Field(description="Type of analytics report")
    intents: Dict[str, Any] = Field(description="Intent analytics data")
    sessions: Dict[str, Any] = Field(description="Session analytics data")
    system: Dict[str, Any] = Field(description="System analytics data")


class PerformanceValidationResponse(BaseAPIResponse):
    """Response for performance validation (moved from component)"""
    performance_score: float = Field(
        description="Overall performance score",
        ge=0.0,
        le=1.0
    )
    meets_criteria: bool = Field(description="Whether performance meets criteria")
    validation_criteria: Dict[str, float] = Field(description="Performance validation criteria")
    performance_analysis: Dict[str, Any] = Field(description="Detailed performance analysis")
    recommendations: List[Dict[str, str]] = Field(description="Performance improvement recommendations")
    generated_at: str = Field(description="Validation generation timestamp")


class SessionSatisfactionRequest(BaseAPIRequest):
    """Request for rating session satisfaction"""
    satisfaction_score: float = Field(
        description="User satisfaction score",
        ge=0.0,
        le=1.0,
        example=0.8
    )


class SessionSatisfactionResponse(BaseAPIResponse):
    """Response for session satisfaction rating"""
    session_id: str = Field(description="Session identifier")
    satisfaction_score: float = Field(description="Recorded satisfaction score")
    message: str = Field(description="Operation result message")


class IntentAnalyticsResponse(BaseAPIResponse):
    """Response for intent analytics"""
    total_intents_processed: int = Field(description="Total number of intents processed")
    unique_intent_types: int = Field(description="Number of unique intent types")
    intent_breakdown: Dict[str, Any] = Field(description="Detailed intent breakdown")
    overall_success_rate: float = Field(description="Overall intent success rate")
    timestamp: float = Field(description="Analytics timestamp")


class SessionAnalyticsResponse(BaseAPIResponse):
    """Response for session analytics"""
    active_sessions: int = Field(description="Number of active sessions")
    total_sessions: int = Field(description="Total number of sessions")
    average_session_duration: float = Field(description="Average session duration")
    average_user_satisfaction: float = Field(description="Average user satisfaction score")
    uptime_seconds: float = Field(description="System uptime in seconds")
    timestamp: float = Field(description="Analytics timestamp")


class PerformanceAnalyticsResponse(BaseAPIResponse):
    """Response for performance analytics"""
    system: Dict[str, Any] = Field(description="System performance metrics")
    vad: Dict[str, Any] = Field(description="Voice Activity Detection metrics")
    components: Dict[str, Any] = Field(description="Component-specific metrics")
    timestamp: float = Field(description="Analytics timestamp")
