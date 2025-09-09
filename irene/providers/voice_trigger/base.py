"""
Voice Trigger Provider Base Classes

Defines the interface for voice trigger/wake word detection providers.
"""

import logging
from abc import abstractmethod
from typing import Dict, Any, List, Optional

from ..base import ProviderBase
from ...intents.models import AudioData, WakeWordResult

logger = logging.getLogger(__name__)


class VoiceTriggerProvider(ProviderBase):
    """
    Base class for voice trigger/wake word detection providers.
    
    Implements the common interface for wake word detection engines
    like OpenWakeWord, Picovoice Porcupine, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.wake_words = config.get('wake_words', ['irene', 'jarvis'])
        self.threshold = config.get('threshold', 0.8)
        self.sample_rate = config.get('sample_rate', 16000)
        self.channels = config.get('channels', 1)
        
    @abstractmethod
    async def detect_wake_word(self, audio_data: AudioData) -> WakeWordResult:
        """
        Detect wake word in audio data.
        
        Args:
            audio_data: Audio data to analyze
            
        Returns:
            WakeWordResult with detection status and metadata
        """
        pass
    
    @abstractmethod
    def get_supported_wake_words(self) -> List[str]:
        """
        Get list of wake words supported by this provider.
        
        Returns:
            List of supported wake words
        """
        pass
    
    @abstractmethod
    def get_parameter_schema(self) -> Dict[str, Any]:
        """
        Get parameter schema for this provider.
        
        Returns:
            Dictionary describing configurable parameters
        """
        pass
    
    @abstractmethod
    def get_supported_sample_rates(self) -> List[int]:
        """
        Get list of supported sample rates (Phase 3).
        
        Returns:
            List of supported sample rates in Hz
        """
        pass
    
    @abstractmethod
    def get_default_sample_rate(self) -> int:
        """
        Get default/optimal sample rate for this provider (Phase 3).
        
        Returns:
            Default sample rate in Hz
        """
        pass
    
    @abstractmethod
    def supports_resampling(self) -> bool:
        """
        Check if this provider supports automatic resampling (Phase 3).
        
        Returns:
            True if provider can handle resampling internally
        """
        pass
    
    @abstractmethod
    def get_default_channels(self) -> int:
        """
        Get default number of audio channels for this provider (Phase 3).
        
        Returns:
            Default number of channels (1 for mono, 2 for stereo)
        """
        pass
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get provider capabilities and metadata.
        
        Returns:
            Dictionary with provider capabilities
        """
        return {
            "wake_words": self.get_supported_wake_words(),
            "sample_rates": [16000, 22050, 44100],
            "channels": [1],
            "formats": ["pcm16"],
            "real_time": True,
            "configurable_threshold": True,
            "multiple_wake_words": len(self.get_supported_wake_words()) > 1
        }
    
    async def set_wake_words(self, wake_words: List[str]) -> bool:
        """
        Set active wake words.
        
        Args:
            wake_words: List of wake words to activate
            
        Returns:
            True if successfully set
        """
        supported = self.get_supported_wake_words()
        valid_words = [word for word in wake_words if word in supported]
        
        if not valid_words:
            self.logger.warning(f"No valid wake words from {wake_words}. Supported: {supported}")
            return False
        
        self.wake_words = valid_words
        self.logger.info(f"Active wake words set to: {valid_words}")
        return True
    
    async def set_threshold(self, threshold: float) -> bool:
        """
        Set detection threshold.
        
        Args:
            threshold: Detection threshold (0.0 - 1.0)
            
        Returns:
            True if successfully set
        """
        if not 0.0 <= threshold <= 1.0:
            self.logger.warning(f"Invalid threshold {threshold}, must be between 0.0 and 1.0")
            return False
        
        self.threshold = threshold
        self.logger.info(f"Detection threshold set to: {threshold}")
        return True
    
    def validate_config(self) -> bool:
        """Validate voice trigger provider configuration."""
        if not isinstance(self.wake_words, list) or not self.wake_words:
            self.logger.error("wake_words must be a non-empty list")
            return False
        
        if not 0.0 <= self.threshold <= 1.0:
            self.logger.error(f"threshold must be between 0.0 and 1.0, got {self.threshold}")
            return False
        
        if self.sample_rate not in [8000, 16000, 22050, 44100, 48000]:
            self.logger.error(f"Unsupported sample rate: {self.sample_rate}")
            return False
        
        return True 