"""
ASR (Automatic Speech Recognition) Providers

This module contains ASR provider implementations following the ABC inheritance pattern.
All providers inherit from the abstract ASRProvider base class.
"""

from .base import ASRProvider
from .vosk import VoskASRProvider
from .whisper import WhisperASRProvider
from .google_cloud import GoogleCloudASRProvider

__all__ = [
    "ASRProvider",
    "VoskASRProvider", 
    "WhisperASRProvider",
    "GoogleCloudASRProvider"
] 