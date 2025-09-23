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
    sample_rate: Optional[int] = Field(
        default=16000,
        description="Audio sample rate in Hz (optional, defaults to 16000Hz)",
        example=16000,
        ge=8000,
        le=192000
    )
    channels: Optional[int] = Field(
        default=1,
        description="Number of audio channels (optional, defaults to 1=mono)",
        example=1,
        ge=1,
        le=8
    )
    format: Optional[str] = Field(
        default="pcm16",
        description="Audio format specification (optional, defaults to pcm16)",
        example="pcm16"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "audio_chunk",
                    "data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqF...",
                    "language": "ru",
                    "provider": "whisper",
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm16",
                    "timestamp": 1704067200.123
                },
                {
                    "type": "audio_chunk",
                    "data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqF...",
                    "language": "en",
                    "sample_rate": 44100,
                    "channels": 2,
                    "format": "pcm16",
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


class BinaryAudioSessionMessage(BaseAPIMessage):
    """
    WebSocket session configuration for binary audio streaming
    
    Initial JSON message sent to configure binary audio streaming session.
    After this message, all subsequent frames are raw binary PCM audio data.
    """
    type: Literal["session_config"] = Field(
        default="session_config",
        description="Message type identifier"
    )
    sample_rate: int = Field(
        default=16000,
        description="Audio sample rate in Hz (16000 recommended for ASR)",
        example=16000,
        ge=8000,
        le=48000
    )
    channels: int = Field(
        default=1,
        description="Number of audio channels (1=mono, 2=stereo)",
        example=1,
        ge=1,
        le=2
    )
    format: str = Field(
        default="pcm_s16le",
        description="Audio format specification (pcm_s16le = 16-bit signed little-endian PCM)",
        example="pcm_s16le"
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
                    "type": "session_config",
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm_s16le",
                    "language": "ru",
                    "provider": "whisper",
                    "timestamp": 1704067200.123
                },
                {
                    "type": "session_config",
                    "sample_rate": 16000,
                    "channels": 1,
                    "format": "pcm_s16le",
                    "language": "en",
                    "timestamp": 1704067200.456
                }
            ]
        }


class BinaryAudioStreamMessage(BaseAPIMessage):
    """
    Documentation schema for binary audio data frames
    
    Note: This schema is for AsyncAPI documentation only. In actual implementation,
    audio data is sent as raw binary WebSocket frames (not JSON) after the initial
    session configuration message.
    
    Binary Format Specification:
    - Raw PCM audio data as configured in session_config
    - Default: 16-bit signed little-endian, mono, 16kHz
    - Frame size: Variable (typically 160-1600 samples = 10-100ms audio)
    - No headers or metadata - pure audio samples
    """
    type: Literal["binary_audio"] = Field(
        default="binary_audio",
        description="Message type identifier (documentation only)"
    )
    description: str = Field(
        default="Raw PCM audio data as binary WebSocket frame",
        description="Binary audio data stream (not JSON - sent as WebSocket binary frames)"
    )
    format_specification: str = Field(
        default="16-bit signed little-endian PCM samples, no headers",
        description="Technical format of the binary data"
    )
    
    class Config:
        json_schema_extra = {
            "description": "This schema documents binary audio frames. Actual data is sent as WebSocket binary frames.",
            "x-binary-format": {
                "type": "binary",
                "format": "pcm_s16le",
                "sample_rate": 16000,
                "channels": 1,
                "frame_size": "variable",
                "notes": "Raw audio samples without headers or metadata"
            },
            "examples": [
                {
                    "type": "binary_audio", 
                    "description": "Raw PCM audio data as binary WebSocket frame",
                    "format_specification": "16-bit signed little-endian PCM samples, no headers",
                    "timestamp": 1704067200.123
                }
            ]
        }


class BinaryWebSocketProtocol(BaseAPIMessage):
    """
    Complete protocol documentation for binary WebSocket streaming
    
    This schema documents the full protocol flow for binary audio streaming:
    1. Client sends BinaryAudioSessionMessage (JSON) for configuration
    2. Server responds with session_ready confirmation (JSON)
    3. Client streams BinaryAudioStreamMessage frames (raw binary)
    4. Server responds with TranscriptionResultMessage (JSON)
    
    This wrapper schema allows AsyncAPI to properly document the mixed
    JSON/binary protocol while maintaining tool compatibility.
    """
    type: Literal["binary_websocket_protocol"] = Field(
        default="binary_websocket_protocol",
        description="Protocol documentation identifier"
    )
    session_config: BinaryAudioSessionMessage = Field(
        description="Initial session configuration sent as JSON message"
    )
    audio_streams: List[BinaryAudioStreamMessage] = Field(
        description="Subsequent binary audio frames (sent as WebSocket binary frames, not JSON)",
        default_factory=list
    )
    
    class Config:
        json_schema_extra = {
            "description": "Complete binary WebSocket streaming protocol documentation",
            "protocol_flow": [
                "1. Client → Server: BinaryAudioSessionMessage (JSON)",
                "2. Server → Client: session_ready confirmation (JSON)", 
                "3. Client → Server: Raw PCM binary frames (BinaryAudioStreamMessage format)",
                "4. Server → Client: TranscriptionResultMessage (JSON) or error (JSON)"
            ],
            "notes": [
                "Only the session_config is sent as JSON",
                "All audio_streams are sent as WebSocket binary frames",
                "This schema is for documentation - actual implementation uses mixed message types"
            ],
            "examples": [
                {
                    "type": "binary_websocket_protocol",
                    "session_config": {
                        "type": "session_config",
                        "sample_rate": 16000,
                        "channels": 1,
                        "format": "pcm_s16le",
                        "language": "en",
                        "provider": "whisper",
                        "timestamp": 1704067200.123
                    },
                    "audio_streams": [
                        {
                            "type": "binary_audio",
                            "description": "Raw PCM audio data as binary WebSocket frame",
                            "format_specification": "16-bit signed little-endian PCM samples, no headers",
                            "timestamp": 1704067200.200
                        }
                    ],
                    "timestamp": 1704067200.123
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

# ============================================================
# DONATION MANAGEMENT SCHEMAS
# ============================================================

class DonationMetadata(BaseModel):
    """Metadata about a donation file"""
    handler_name: str = Field(description="Handler name (filename without .json)")
    domain: str = Field(description="Handler domain from donation")
    description: str = Field(description="Donation description")
    methods_count: int = Field(description="Number of method donations")
    global_parameters_count: int = Field(description="Number of global parameters")
    file_size: int = Field(description="File size in bytes")
    last_modified: float = Field(description="Unix timestamp of last modification")


class ValidationError(BaseModel):
    """Validation error details"""
    type: str = Field(description="Error type (schema, method_existence, etc.)")
    message: str = Field(description="Human-readable error message")
    path: Optional[str] = Field(default=None, description="JSON path where error occurred")
    line: Optional[int] = Field(default=None, description="Line number if applicable")


class ValidationWarning(BaseModel):
    """Validation warning details"""
    type: str = Field(description="Warning type")
    message: str = Field(description="Human-readable warning message")
    path: Optional[str] = Field(default=None, description="JSON path where warning occurred")


# ============================================================
# LEGACY DONATION SCHEMAS REMOVED (Phase 3 Cleanup)
# ============================================================
# Old single-file donation request/response models removed:
# - DonationUpdateRequest
# - DonationValidationRequest 
# - DonationListResponse
# - DonationContentResponse
# - DonationUpdateResponse
# - DonationValidationResponse
#
# Replaced by language-aware v2 endpoints below


class DonationSchemaResponse(BaseAPIResponse):
    """Response for donation JSON schema"""
    json_schema: Dict[str, Any] = Field(description="JSON schema for donation structure")
    schema_version: str = Field(description="Schema version")
    supported_versions: List[str] = Field(description="Supported schema versions")


# ============================================================
# LANGUAGE-AWARE DONATION SCHEMAS (Phase 3)
# ============================================================

class HandlerLanguageInfo(BaseModel):
    """Information about a handler's language support"""
    handler_name: str = Field(description="Handler name")
    languages: List[str] = Field(description="Available languages")
    total_languages: int = Field(description="Language count")
    supported_languages: List[str] = Field(description="From system config")
    default_language: str = Field(description="System default language")


class DonationHandlerListResponse(BaseAPIResponse):
    """Response for listing handlers with language info"""
    handlers: List[HandlerLanguageInfo] = Field(description="List of handlers with language info")
    total_handlers: int = Field(description="Total number of handlers")


class CrossLanguageValidation(BaseModel):
    """Cross-language validation results"""
    parameter_consistency: bool = Field(description="Whether parameters are consistent across languages")
    missing_methods: List[str] = Field(description="Methods missing in some language files")
    extra_methods: List[str] = Field(description="Extra methods in some language files")


class LanguageDonationMetadata(BaseModel):
    """Metadata for a language-specific donation file"""
    file_path: str = Field(description="e.g., 'conversation_handler/en.json'")
    language: str = Field(description="Language code")
    file_size: int = Field(description="File size in bytes")
    last_modified: float = Field(description="Last modification timestamp")


class LanguageDonationContentResponse(BaseAPIResponse):
    """Response for language-specific donation content retrieval"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Current language")
    donation_data: Dict[str, Any] = Field(description="Complete donation JSON content")
    metadata: LanguageDonationMetadata = Field(description="File metadata")
    available_languages: List[str] = Field(description="Other available languages")
    cross_language_validation: CrossLanguageValidation = Field(description="Cross-language checks")


class LanguageDonationUpdateRequest(BaseAPIRequest):
    """Request to update a language-specific donation file"""
    donation_data: Dict[str, Any] = Field(description="Complete donation JSON data")
    validate_before_save: bool = Field(default=True, description="Whether to validate before saving")
    trigger_reload: bool = Field(default=True, description="Whether to trigger reload after save")


class LanguageDonationUpdateResponse(BaseAPIResponse):
    """Response for language-specific donation update operation"""
    handler_name: str = Field(description="Updated handler name")
    language: str = Field(description="Updated language")
    validation_passed: bool = Field(description="Whether validation passed")
    reload_triggered: bool = Field(description="Whether unified donation reload was triggered")
    backup_created: bool = Field(description="Whether backup was created")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")


class LanguageDonationValidationRequest(BaseAPIRequest):
    """Request to validate language-specific donation data without saving"""
    donation_data: Dict[str, Any] = Field(description="Donation data to validate")


class LanguageDonationValidationResponse(BaseAPIResponse):
    """Response for language-specific donation validation operation"""
    handler_name: str = Field(description="Handler name being validated")
    language: str = Field(description="Language being validated")
    is_valid: bool = Field(description="Whether donation is valid")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")
    validation_types: List[str] = Field(description="Types of validation performed")


class CreateLanguageRequest(BaseAPIRequest):
    """Request to create a new language file for a handler"""
    copy_from: Optional[str] = Field(default=None, description="Language to copy from")
    use_template: bool = Field(default=False, description="Use empty template instead of copying")


class CreateLanguageResponse(BaseAPIResponse):
    """Response for language creation operation"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Created language")
    created: bool = Field(description="Whether language file was created")
    copied_from: Optional[str] = Field(default=None, description="Language copied from")


class DeleteLanguageResponse(BaseAPIResponse):
    """Response for language deletion operation"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Deleted language")
    deleted: bool = Field(description="Whether language file was deleted")


class ReloadDonationResponse(BaseAPIResponse):
    """Response for unified donation reload operation"""
    handler_name: str = Field(description="Handler name")
    reloaded: bool = Field(description="Whether unified donation was reloaded")
    merged_languages: List[str] = Field(description="Languages that were merged")


# ============================================================
# CROSS-LANGUAGE VALIDATION SCHEMAS (Phase 4)
# ============================================================

class ValidationReportSchema(BaseModel):
    """Schema for parameter consistency validation report"""
    handler_name: str = Field(description="Handler name that was validated")
    languages_checked: List[str] = Field(description="Languages that were included in validation")
    parameter_consistency: bool = Field(description="Whether parameters are consistent across languages")
    missing_parameters: List[str] = Field(description="Parameters missing in some languages (format: 'language: method.parameter')")
    extra_parameters: List[str] = Field(description="Extra parameters in some languages")
    type_mismatches: List[str] = Field(description="Parameter type mismatches across languages")
    warnings: List[str] = Field(description="Validation warnings")
    timestamp: float = Field(description="Validation timestamp")


class CompletenessReportSchema(BaseModel):
    """Schema for method completeness validation report"""
    handler_name: str = Field(description="Handler name that was validated")
    languages_checked: List[str] = Field(description="Languages that were included in validation")
    method_completeness: bool = Field(description="Whether all methods exist in all languages")
    missing_methods: List[str] = Field(description="Methods missing in some languages (format: 'language: method_key')")
    extra_methods: List[str] = Field(description="Extra methods in some languages")
    all_methods: List[str] = Field(description="All unique method keys across languages")
    method_counts_by_language: Dict[str, int] = Field(description="Method count per language")
    warnings: List[str] = Field(description="Validation warnings")
    timestamp: float = Field(description="Validation timestamp")


class MissingPhraseInfo(BaseModel):
    """Information about missing phrases for translation"""
    method_key: str = Field(description="Method key (method_name#intent_suffix)")
    source_phrases: List[str] = Field(description="Phrases available in source language")
    target_phrases: List[str] = Field(description="Phrases available in target language")
    missing_count: int = Field(description="Number of missing phrases")
    coverage_ratio: float = Field(description="Ratio of target to source phrases", ge=0.0, le=1.0)


class TranslationSuggestionsSchema(BaseModel):
    """Schema for translation suggestions response"""
    handler_name: str = Field(description="Handler name")
    source_language: str = Field(description="Source language for suggestions")
    target_language: str = Field(description="Target language for suggestions")
    missing_phrases: List[MissingPhraseInfo] = Field(description="Information about missing phrases")
    missing_methods: List[str] = Field(description="Method keys completely missing in target language")
    confidence_scores: Dict[str, float] = Field(description="Confidence scores for suggestions")
    timestamp: float = Field(description="Suggestion generation timestamp")


class CrossLanguageValidationRequest(BaseAPIRequest):
    """Request for cross-language validation"""
    validation_type: str = Field(
        description="Type of validation to perform",
        example="parameters"
    )


class CrossLanguageValidationResponse(BaseAPIResponse):
    """Response for cross-language validation"""
    validation_type: str = Field(description="Type of validation performed")
    parameter_report: Optional[ValidationReportSchema] = Field(
        default=None,
        description="Parameter consistency report"
    )
    completeness_report: Optional[CompletenessReportSchema] = Field(
        default=None,
        description="Method completeness report"
    )


class SyncParametersRequest(BaseAPIRequest):
    """Request to sync parameter structures across languages"""
    source_language: str = Field(description="Source language to sync from")
    target_languages: List[str] = Field(description="Target languages to sync to")


class SyncParametersResponse(BaseAPIResponse):
    """Response for parameter synchronization operation"""
    handler_name: str = Field(description="Handler that was synced")
    source_language: str = Field(description="Source language used")
    sync_results: Dict[str, bool] = Field(description="Sync success status per target language")
    updated_languages: List[str] = Field(description="Languages that were actually updated")
    skipped_languages: List[str] = Field(description="Languages that were skipped")


class SuggestTranslationsRequest(BaseAPIRequest):
    """Request for translation suggestions"""
    source_language: str = Field(description="Source language for suggestions")
    target_language: str = Field(description="Target language for suggestions")


class SuggestTranslationsResponse(BaseAPIResponse):
    """Response for translation suggestions"""
    suggestions: TranslationSuggestionsSchema = Field(description="Translation suggestions")


# ============================================================
# TEMPLATE MANAGEMENT SCHEMAS (Phase 6)
# ============================================================

class TemplateMetadata(BaseModel):
    """Metadata for a language-specific template file"""
    file_path: str = Field(description="e.g., 'conversation_handler/en.yaml'")
    language: str = Field(description="Language code")
    file_size: int = Field(description="File size in bytes")
    last_modified: float = Field(description="Last modification timestamp")
    template_count: int = Field(description="Number of templates in the file")


class TemplateContentResponse(BaseAPIResponse):
    """Response for language-specific template content retrieval"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Current language")
    template_data: Dict[str, Any] = Field(description="Complete template YAML content")
    metadata: TemplateMetadata = Field(description="File metadata")
    available_languages: List[str] = Field(description="Other available languages")
    schema_info: Dict[str, Any] = Field(description="Expected keys and their types")


class TemplateUpdateRequest(BaseAPIRequest):
    """Request to update a language-specific template file"""
    template_data: Dict[str, Any] = Field(description="Complete template YAML data")
    validate_before_save: bool = Field(default=True, description="Whether to validate before saving")
    trigger_reload: bool = Field(default=True, description="Whether to trigger reload after save")


class TemplateUpdateResponse(BaseAPIResponse):
    """Response for language-specific template update operation"""
    handler_name: str = Field(description="Updated handler name")
    language: str = Field(description="Updated language")
    validation_passed: bool = Field(description="Whether validation passed")
    reload_triggered: bool = Field(description="Whether template reload was triggered")
    backup_created: bool = Field(description="Whether backup was created")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")


class TemplateValidationRequest(BaseAPIRequest):
    """Request to validate language-specific template data without saving"""
    template_data: Dict[str, Any] = Field(description="Template data to validate")


class TemplateValidationResponse(BaseAPIResponse):
    """Response for language-specific template validation operation"""
    handler_name: str = Field(description="Handler name being validated")
    language: str = Field(description="Language being validated")
    is_valid: bool = Field(description="Whether template is valid")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")
    validation_types: List[str] = Field(description="Types of validation performed")


class CreateTemplateLanguageRequest(BaseAPIRequest):
    """Request to create a new language file for template"""
    copy_from: Optional[str] = Field(default=None, description="Language to copy from")
    use_template: bool = Field(default=False, description="Use empty template instead of copying")


class CreateTemplateLanguageResponse(BaseAPIResponse):
    """Response for template language creation operation"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Created language")
    created: bool = Field(description="Whether language file was created")
    copied_from: Optional[str] = Field(default=None, description="Language copied from")


class DeleteTemplateLanguageResponse(BaseAPIResponse):
    """Response for template language deletion operation"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Deleted language")
    deleted: bool = Field(description="Whether language file was deleted")
    backup_created: bool = Field(description="Whether backup was created before deletion")


class TemplateHandlerListResponse(BaseAPIResponse):
    """Response for listing handlers with template language info"""
    handlers: List[HandlerLanguageInfo] = Field(description="List of handlers with language info")
    total_handlers: int = Field(description="Total number of handlers")


# ============================================================
# PROMPT MANAGEMENT SCHEMAS (Phase 7)
# ============================================================

class PromptDefinition(BaseModel):
    """Prompt definition with metadata"""
    description: str = Field(description="Description of the prompt")
    usage_context: str = Field(description="Context where this prompt is used")
    variables: List[Dict[str, str]] = Field(default=[], description="List of variable definitions")
    prompt_type: str = Field(default="system", description="Type of prompt: system, template, user")
    content: str = Field(description="The actual prompt content")


class PromptMetadata(BaseModel):
    """Metadata for a language-specific prompt file"""
    file_path: str = Field(description="e.g., 'conversation_handler/en.yaml'")
    language: str = Field(description="Language code")
    file_size: int = Field(description="File size in bytes")
    last_modified: float = Field(description="Last modification timestamp")
    prompt_count: int = Field(description="Number of prompts in the file")


class PromptContentResponse(BaseAPIResponse):
    """Response for language-specific prompt content retrieval"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Current language")
    prompt_data: Dict[str, PromptDefinition] = Field(description="Complete prompt YAML content")
    metadata: PromptMetadata = Field(description="File metadata")
    available_languages: List[str] = Field(description="Other available languages")
    schema_info: Dict[str, Any] = Field(description="Required fields and prompt types")


class PromptUpdateRequest(BaseAPIRequest):
    """Request to update a language-specific prompt file"""
    prompt_data: Dict[str, PromptDefinition] = Field(description="Complete prompt YAML data")
    validate_before_save: bool = Field(default=True, description="Whether to validate before saving")
    trigger_reload: bool = Field(default=True, description="Whether to trigger reload after save")


class PromptUpdateResponse(BaseAPIResponse):
    """Response for language-specific prompt update operation"""
    handler_name: str = Field(description="Updated handler name")
    language: str = Field(description="Updated language")
    validation_passed: bool = Field(description="Whether validation passed")
    reload_triggered: bool = Field(description="Whether prompt reload was triggered")
    backup_created: bool = Field(description="Whether backup was created")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")


class PromptValidationRequest(BaseAPIRequest):
    """Request to validate language-specific prompt data without saving"""
    prompt_data: Dict[str, PromptDefinition] = Field(description="Prompt data to validate")


class PromptValidationResponse(BaseAPIResponse):
    """Response for language-specific prompt validation operation"""
    handler_name: str = Field(description="Handler name being validated")
    language: str = Field(description="Language being validated")
    is_valid: bool = Field(description="Whether prompt is valid")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")
    validation_types: List[str] = Field(description="Types of validation performed")


class CreatePromptLanguageRequest(BaseAPIRequest):
    """Request to create a new language file for prompt"""
    copy_from: Optional[str] = Field(default=None, description="Language to copy from")
    use_template: bool = Field(default=False, description="Use empty template instead of copying")


class CreatePromptLanguageResponse(BaseAPIResponse):
    """Response for prompt language creation operation"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Created language")
    created: bool = Field(description="Whether language file was created")
    copied_from: Optional[str] = Field(default=None, description="Language copied from")


class DeletePromptLanguageResponse(BaseAPIResponse):
    """Response for prompt language deletion operation"""
    handler_name: str = Field(description="Handler name")
    language: str = Field(description="Deleted language")
    deleted: bool = Field(description="Whether language file was deleted")
    backup_created: bool = Field(description="Whether backup was created before deletion")


class PromptHandlerListResponse(BaseAPIResponse):
    """Response for listing handlers with prompt language info"""
    handlers: List[HandlerLanguageInfo] = Field(description="List of handlers with language info")
    total_handlers: int = Field(description="Total number of handlers")


# ============================================================
# LOCALIZATION MANAGEMENT SCHEMAS (Phase 8)
# ============================================================

class LocalizationMetadata(BaseModel):
    """Metadata for a language-specific localization file"""
    file_path: str = Field(description="Relative file path from assets root")
    language: str = Field(description="Language code")
    file_size: int = Field(description="File size in bytes")
    last_modified: float = Field(description="Last modification timestamp")
    entry_count: int = Field(description="Number of localization entries in the file")


class LocalizationContentResponse(BaseAPIResponse):
    """Response for language-specific localization content retrieval"""
    domain: str = Field(description="Domain name")
    language: str = Field(description="Current language")
    localization_data: Dict[str, Any] = Field(description="Complete localization YAML content")
    metadata: LocalizationMetadata = Field(description="File metadata")
    available_languages: List[str] = Field(description="Other available languages")
    schema_info: Dict[str, Any] = Field(description="Expected keys and their types")


class LocalizationUpdateRequest(BaseAPIRequest):
    """Request to update a language-specific localization file"""
    localization_data: Dict[str, Any] = Field(description="Localization data to save")
    validate_before_save: bool = Field(default=True, description="Whether to validate before saving")
    trigger_reload: bool = Field(default=True, description="Whether to trigger localization reload")


class LocalizationUpdateResponse(BaseAPIResponse):
    """Response for language-specific localization update operation"""
    domain: str = Field(description="Domain name being updated")
    language: str = Field(description="Language being updated")
    validation_passed: bool = Field(description="Whether validation passed")
    reload_triggered: bool = Field(description="Whether localization reload was triggered")
    backup_created: bool = Field(description="Whether backup was created")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")


class LocalizationValidationRequest(BaseAPIRequest):
    """Request to validate localization data without saving"""
    localization_data: Dict[str, Any] = Field(description="Localization data to validate")


class LocalizationValidationResponse(BaseAPIResponse):
    """Response for language-specific localization validation operation"""
    domain: str = Field(description="Domain name being validated")
    language: str = Field(description="Language being validated")
    is_valid: bool = Field(description="Whether localization is valid")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")
    validation_types: List[str] = Field(description="Types of validation performed")


class CreateLocalizationLanguageRequest(BaseAPIRequest):
    """Request to create a new language file for localization"""
    copy_from: Optional[str] = Field(default=None, description="Language to copy from")
    use_template: bool = Field(default=False, description="Use empty template instead of copying")


class CreateLocalizationLanguageResponse(BaseAPIResponse):
    """Response for localization language creation operation"""
    domain: str = Field(description="Domain name")
    language: str = Field(description="Created language")
    created: bool = Field(description="Whether language file was created")
    copied_from: Optional[str] = Field(default=None, description="Language copied from")


class DeleteLocalizationLanguageResponse(BaseAPIResponse):
    """Response for localization language deletion operation"""
    domain: str = Field(description="Domain name")
    language: str = Field(description="Deleted language")
    deleted: bool = Field(description="Whether language file was deleted")
    backup_created: bool = Field(description="Whether backup was created before deletion")


class DomainLanguageInfo(BaseModel):
    """Information about a domain and its available languages"""
    domain: str = Field(description="Domain name")
    languages: List[str] = Field(description="Available language codes")
    total_languages: int = Field(description="Total number of languages available")
    supported_languages: List[str] = Field(description="Configured supported languages")
    default_language: str = Field(description="System default language")


class LocalizationDomainListResponse(BaseAPIResponse):
    """Response for listing domains with localization language info"""
    domains: List[DomainLanguageInfo] = Field(description="List of domains with language info")
    total_domains: int = Field(description="Total number of domains")


# ============================================================
# INTENT SYSTEM SCHEMAS (EXISTING)
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


# ============================================================
# CONFIGURATION MANAGEMENT SCHEMAS
# ============================================================

class ConfigUpdateResponse(BaseAPIResponse):
    """Response for configuration section updates"""
    message: str = Field(description="Update status message")
    reload_triggered: bool = Field(description="Whether hot-reload was triggered")
    backup_created: Optional[str] = Field(default=None, description="Path to backup file if created")


class ConfigValidationResponse(BaseAPIResponse):
    """Response for configuration validation"""
    valid: bool = Field(description="Whether the configuration is valid")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Validated configuration data")
    validation_errors: Optional[List[Dict[str, Any]]] = Field(default=None, description="Validation error details")


class ConfigStatusResponse(BaseAPIResponse):
    """Response for configuration system status"""
    config_path: Optional[str] = Field(description="Path to active configuration file")
    config_exists: bool = Field(description="Whether configuration file exists")
    hot_reload_active: bool = Field(description="Whether hot-reload monitoring is active")
    component_initialized: bool = Field(description="Whether ConfigurationComponent is initialized")
    last_modified: Optional[float] = Field(default=None, description="Configuration file last modified timestamp")
    file_size: Optional[int] = Field(default=None, description="Configuration file size in bytes")


# ============================================================
# RAW TOML CONFIGURATION SCHEMAS (Phase 4)
# ============================================================

class RawTomlRequest(BaseAPIRequest):
    """Request to save raw TOML content"""
    toml_content: str = Field(description="Raw TOML content to save")
    validate_before_save: bool = Field(default=True, description="Whether to validate before saving")


class RawTomlResponse(BaseAPIResponse):
    """Response containing raw TOML content"""
    toml_content: str = Field(description="Raw TOML configuration content with comments preserved")
    config_path: str = Field(description="Path to configuration file")
    file_size: int = Field(description="File size in bytes")
    last_modified: float = Field(description="File last modified timestamp")


class RawTomlSaveResponse(BaseAPIResponse):
    """Response for raw TOML save operation"""
    message: str = Field(description="Save operation result message")
    backup_created: Optional[str] = Field(default=None, description="Path to backup file if created")
    config_cached: bool = Field(description="Whether configuration was successfully cached")


class RawTomlValidationRequest(BaseAPIRequest):
    """Request to validate raw TOML content"""
    toml_content: str = Field(description="Raw TOML content to validate")


class RawTomlValidationResponse(BaseAPIResponse):
    """Response for raw TOML validation"""
    valid: bool = Field(description="Whether TOML content is valid")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Parsed configuration data if valid")
    errors: Optional[List[Dict[str, Any]]] = Field(default=None, description="Validation errors if invalid")


class SectionToTomlRequest(BaseAPIRequest):
    """Request to apply section changes to raw TOML"""
    section_data: Dict[str, Any] = Field(description="Section configuration data")


class SectionToTomlResponse(BaseAPIResponse):
    """Response for section-to-TOML operation"""
    toml_content: str = Field(description="Updated TOML content with section applied")
    section_name: str = Field(description="Section that was updated")
    comments_preserved: bool = Field(description="Whether comments were preserved")


# ============================================================
# NLU ANALYSIS SCHEMAS (Phase 2)
# ============================================================

class AnalyzeDonationRequest(BaseAPIRequest):
    """Request for real-time donation analysis"""
    handler_name: str = Field(description="Handler name to analyze")
    language: str = Field(description="Language of the donation", example="en")
    donation_data: Dict[str, Any] = Field(description="Complete donation data to analyze")


class NLUAnalysisResult(BaseAPIResponse):
    """Response for NLU analysis operations"""
    conflicts: List[Dict[str, Any]] = Field(description="Detected conflicts")
    scope_issues: List[Dict[str, Any]] = Field(description="Scope creep issues")
    performance_metrics: Dict[str, Any] = Field(description="Detailed analysis performance metrics from analyzers")
    language_coverage: Dict[str, float] = Field(description="Language coverage analysis")
    analysis_time_ms: float = Field(description="Time taken for analysis")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "timestamp": 1704067200.123,
                    "conflicts": [
                        {
                            "intent_a": "timer.set",
                            "intent_b": "datetime.current_time",
                            "language": "en",
                            "severity": "warning",
                            "score": 0.75,
                            "conflict_type": "phrase_overlap",
                            "signals": {
                                "shared_phrases": ["set time", "time setting"],
                                "overlap_percentage": 0.4
                            },
                            "suggestions": [
                                "Make 'timer.set' phrases more specific: 'set timer for X'",
                                "Consider removing generic 'set time' from timer domain"
                            ]
                        }
                    ],
                    "scope_issues": [],
                    "performance_metrics": {
                        "hybrid": {
                            "keyword_analysis": {
                                "collision_count": 2,
                                "efficiency_score": 0.95
                            },
                            "pattern_analysis": {
                                "complexity_score": 0.8,
                                "optimization_suggestions": []
                            }
                        },
                        "spacy": {
                            "similarity_analysis": {
                                "semantic_conflicts": [],
                                "confidence_scores": [0.92, 0.87]
                            },
                            "entity_analysis": {
                                "entity_coverage": 0.85
                            }
                        }
                    },
                    "language_coverage": {
                        "en": 0.85
                    },
                    "analysis_time_ms": 8.5
                }
            ]
        }


class AnalyzeChangesRequest(BaseAPIRequest):
    """Request for analyzing impact of multiple changes"""
    changes: Dict[str, Dict[str, Any]] = Field(description="Dictionary of changes to analyze")
    language: Optional[str] = Field(default=None, description="Optional language filter")


class ChangeImpactAnalysisResponse(BaseAPIResponse):
    """Response for change impact analysis"""
    changes: Dict[str, Any] = Field(description="Summary of proposed changes")
    affected_intents: List[str] = Field(description="Intents affected by changes")
    new_conflicts: List[Dict[str, Any]] = Field(description="New conflicts introduced")
    resolved_conflicts: List[Dict[str, Any]] = Field(description="Conflicts resolved by changes")
    impact_score: float = Field(description="Overall impact score (0.0-1.0)", ge=0.0, le=1.0)
    recommendations: List[str] = Field(description="Recommendations based on impact")
    analysis_time_ms: float = Field(description="Time taken for impact analysis")


class ValidateRequest(BaseAPIRequest):
    """Request for pre-save validation"""
    handler_name: str = Field(description="Handler name to validate")
    language: str = Field(description="Language of the donation", example="en")
    donation_data: Dict[str, Any] = Field(description="Complete donation data to validate")


class NLUValidationResult(BaseAPIResponse):
    """Response for pre-save validation"""
    is_valid: bool = Field(description="Whether donation is valid for saving")
    has_blocking_conflicts: bool = Field(description="Whether there are blocking conflicts")
    has_warnings: bool = Field(description="Whether there are warning-level issues")
    conflicts: List[Dict[str, Any]] = Field(description="All detected conflicts")
    suggestions: List[str] = Field(description="General improvement suggestions")
    validation_time_ms: float = Field(description="Time taken for validation")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "timestamp": 1704067200.123,
                    "is_valid": False,
                    "has_blocking_conflicts": True,
                    "has_warnings": False,
                    "conflicts": [
                        {
                            "intent_a": "timer.set",
                            "intent_b": "timer.cancel",
                            "severity": "blocker",
                            "conflict_type": "keyword_collision"
                        }
                    ],
                    "suggestions": ["Resolve keyword collisions before saving"],
                    "validation_time_ms": 15.2
                }
            ]
        }


class ConflictReport(BaseModel):
    """Individual conflict report"""
    intent_a: str = Field(description="First intent in conflict")
    intent_b: str = Field(description="Second intent in conflict")
    language: str = Field(description="Language where conflict occurs")
    severity: Literal['blocker', 'warning', 'info'] = Field(description="Conflict severity")
    score: float = Field(description="Conflict strength score (0.0-1.0)", ge=0.0, le=1.0)
    conflict_type: str = Field(description="Type of conflict detected")
    signals: Dict[str, Any] = Field(description="Evidence and analysis details")
    suggestions: List[str] = Field(description="Suggested resolutions")


class BatchAnalysisResponse(BaseAPIResponse):
    """Response for full system batch analysis"""
    summary: Dict[str, int] = Field(description="Summary statistics")
    conflicts: List[ConflictReport] = Field(description="All detected conflicts")
    scope_issues: List[Dict[str, Any]] = Field(description="All scope issues")
    system_health: Dict[str, float] = Field(description="System health metrics")
    language_breakdown: Dict[str, Dict[str, int]] = Field(description="Per-language statistics")
    performance_metrics: Dict[str, float] = Field(description="System performance metrics")
    recommendations: List[str] = Field(description="System-wide recommendations")
    analysis_time_ms: float = Field(description="Total analysis time")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "timestamp": 1704067200.123,
                    "summary": {
                        "total_intents": 45,
                        "total_conflicts": 3,
                        "blockers": 1,
                        "warnings": 2,
                        "scope_issues": 1
                    },
                    "conflicts": [],
                    "scope_issues": [],
                    "system_health": {
                        "overall_score": 0.87,
                        "conflict_ratio": 0.067,
                        "coverage_ratio": 0.92
                    },
                    "language_breakdown": {
                        "ru": {"intents": 22, "conflicts": 2},
                        "en": {"intents": 23, "conflicts": 1}
                    },
                    "performance_metrics": {
                        "avg_analysis_time": 12.5,
                        "memory_usage_mb": 28.4
                    },
                    "recommendations": [
                        "Resolve blocking conflict in timer domain",
                        "Consider splitting broad patterns in conversation handler"
                    ],
                    "analysis_time_ms": 156.7
                }
            ]
        }


class SystemHealthResponse(BaseAPIResponse):
    """Response for NLU system health check"""
    status: Literal['healthy', 'degraded', 'critical'] = Field(description="Overall system status")
    health_score: float = Field(description="Overall health score (0.0-1.0)", ge=0.0, le=1.0)
    component_status: Dict[str, str] = Field(description="Status of individual components")
    conflict_summary: Dict[str, int] = Field(description="Conflict summary by severity")
    performance_summary: Dict[str, float] = Field(description="Performance metrics summary")
    recommendations: List[str] = Field(description="Health improvement recommendations")
    last_analysis: float = Field(description="Timestamp of last analysis")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "success": True,
                    "timestamp": 1704067200.123,
                    "status": "healthy",
                    "health_score": 0.87,
                    "component_status": {
                        "hybrid_analyzer": "operational",
                        "spacy_analyzer": "operational",
                        "conflict_detector": "operational"
                    },
                    "conflict_summary": {
                        "blockers": 0,
                        "warnings": 2,
                        "info": 5
                    },
                    "performance_summary": {
                        "avg_analysis_time": 12.5,
                        "memory_usage_mb": 28.4,
                        "success_rate": 0.98
                    },
                    "recommendations": [
                        "Monitor warning-level conflicts",
                        "Consider optimization for large datasets"
                    ],
                    "last_analysis": 1704067200.123
                }
            ]
        }
