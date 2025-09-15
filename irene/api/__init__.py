"""
Irene API Module

Centralized API definitions, schemas, and utilities for all
API endpoints (REST, WebSocket, etc.) across Irene components.
"""

from .schemas import *

__all__ = [
    # Base schemas
    "BaseAPIMessage",
    "BaseAPIRequest", 
    "BaseAPIResponse",
    "ErrorResponse",
    # ASR schemas
    "AudioChunkMessage",
    "TranscriptionResultMessage",
    "TranscriptionErrorMessage",
    "ASRTranscribeRequest",
    "ASRTranscribeResponse", 
    "ASRProvidersResponse",
    # TTS schemas
    "TTSRequest",
    "TTSResponse",
    "TTSProvidersResponse",
    # NLU schemas
    "NLURequest",
    "IntentResponse",
    # System schemas
    "HealthResponse",
    "ComponentInfo",
    "SystemStatusResponse",
    "CommandRequest",
    "CommandResponse"
]
