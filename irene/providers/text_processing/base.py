"""
Text Processing Provider Base Classes

Abstract base class for all text processing implementations.
Following ABC inheritance pattern for type safety and runtime validation.
"""

from abc import abstractmethod
from typing import Dict, Any, List

from ..base import ProviderBase
from ...intents.models import UnifiedConversationContext


class TextProcessingProvider(ProviderBase):
    """
    Abstract base class for text processing implementations.
    
    All text processing providers must implement stage-specific text processing
    following the Component-Provider pattern.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with provider-specific configuration
        
        Args:
            config: Provider-specific configuration dictionary
        """
        # Call ProviderBase.__init__ to get status tracking, logging, etc.
        super().__init__(config)
    
    @abstractmethod
    async def process_pipeline(self, text: str, stage: str) -> str:
        """Process text for a specific pipeline stage
        
        Args:
            text: Input text to process
            stage: Processing stage ('asr_output', 'general', 'tts_input')
            
        Returns:
            Processed text string
        """
        pass
    
    @abstractmethod
    def get_supported_stages(self) -> List[str]:
        """Return list of processing stages this provider supports
        
        Returns:
            List of stage names ('asr_output', 'general', 'tts_input', etc.)
        """
        pass
    
    async def improve_text(self, text: str, context: UnifiedConversationContext, stage: str = "general") -> str:
        """Legacy method for text improvement (optional override)
        
        Default implementation delegates to process_pipeline for backwards compatibility.
        
        Args:
            text: Input text to improve
            context: Conversation context (may be unused by some providers)
            stage: Processing stage
            
        Returns:
            Improved text string
        """
        return await self.process_pipeline(text, stage)
    
    def get_processing_capabilities(self) -> Dict[str, Any]:
        """Return processing capabilities (optional override)
        
        Returns:
            Dictionary with capability information
        """
        return {
            "supported_stages": self.get_supported_stages(),
            "context_aware": False,  # Override if context is used
            "real_time": True,  # Override if not real-time capable
            "batch_processing": False,  # Override if batch processing supported
        } 