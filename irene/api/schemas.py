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
