"""
Anthropic LLM Provider

Anthropic Claude LLM provider implementation.
Provides high-quality text enhancement and chat capabilities.
"""

import os
import asyncio
from typing import Dict, Any, List
import logging

from .base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicLLMProvider(LLMProvider):
    """Anthropic Claude LLM Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Anthropic provider with configuration
        
        Args:
            config: Provider configuration containing:
                - api_key_env: Environment variable name for API key (deprecated - uses asset manager)
                - default_model: Default model to use
                - max_tokens: Maximum tokens in response
                - temperature: Temperature for text generation
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Asset management integration for credentials
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Get API key through asset manager or fallback to config
        credentials = self.asset_manager.get_credentials("anthropic")
        self.api_key = credentials.get("anthropic_api_key") or os.getenv(config.get("api_key_env", "ANTHROPIC_API_KEY"))
        
        if not self.api_key and config.get("api_key_env"):
            logger.warning("Using legacy api_key_env config. Consider using ANTHROPIC_API_KEY environment variable.")
            
        self.default_model = config.get("default_model", "claude-3-haiku-20240307")
        self.max_tokens = config.get("max_tokens", 150)
        self.temperature = config.get("temperature", 0.3)
        
    @classmethod
    def _get_default_extension(cls) -> str:
        """Anthropic is API-based, no persistent files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """Anthropic directory for temp files"""
        return "anthropic"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """Anthropic needs API key"""
        return ["ANTHROPIC_API_KEY"]
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Anthropic uses runtime cache for API responses"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """Anthropic is API-based, no model downloads"""
        return {}
    
    async def is_available(self) -> bool:
        """Check if Anthropic API is available"""
        try:
            import anthropic
            return self.api_key is not None
        except ImportError:
            logger.warning("Anthropic library not available")
            return False
    
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """Enhance text using Anthropic Claude"""
        model = kwargs.get("model", self.default_model)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        prompts = {
            "improve_speech_recognition": "Fix speech recognition errors in the following text while preserving its meaning:",
            "grammar_correction": "Fix grammar and punctuation in the following text:",
            "translation": "Translate the following text to {target_language}:",
            "improve": "Improve the following text for clarity and readability:",
            "summarize": "Summarize the following text concisely:",
            "expand": "Expand and elaborate on the following text:"
        }
        
        system_prompt = prompts.get(task, prompts["improve"])
        if task == "translation":
            target_language = kwargs.get("target_language", "English")
            system_prompt = system_prompt.format(target_language=target_language)
        
        try:
            from anthropic import AsyncAnthropic  # type: ignore
            client = AsyncAnthropic(api_key=self.api_key)
            
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Anthropic enhancement failed: {e}")
            return text  # Return original text on error
    
    async def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """Generate chat completion using Anthropic Claude"""
        model = kwargs.get("model", self.default_model)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        try:
            from anthropic import AsyncAnthropic  # type: ignore
            client = AsyncAnthropic(api_key=self.api_key)
            
            # Convert messages format for Anthropic (extract system message if present)
            system_message = ""
            user_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    user_messages.append(msg)
            
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message if system_message else "You are a helpful assistant.",
                messages=user_messages
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Anthropic chat completion failed: {e}")
            return "Sorry, I couldn't process that request."
    
    def get_available_models(self) -> List[str]:
        """Return list of available Anthropic models"""
        return [
            "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229", "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307"
        ]
    
    def get_supported_tasks(self) -> List[str]:
        """Return list of supported enhancement tasks"""
        return [
            "improve_speech_recognition", "grammar_correction", "translation",
            "improve", "summarize", "expand"
        ]
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for Anthropic-specific parameters"""
        return {
            "model": {
                "type": "string",
                "options": self.get_available_models(),
                "default": self.default_model,
                "description": "Anthropic model to use"
            },
            "max_tokens": {
                "type": "integer",
                "min": 1,
                "max": 4096,
                "default": self.max_tokens,
                "description": "Maximum tokens in response"
            },
            "temperature": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": self.temperature,
                "description": "Temperature for text generation"
            },
            "target_language": {
                "type": "string",
                "default": "English",
                "description": "Target language for translation task"
            }
        }
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "anthropic"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return Anthropic provider capabilities"""
        return {
            "models": self.get_available_models(),
            "tasks": self.get_supported_tasks(),
            "streaming": True,  # Anthropic supports streaming
            "multimodal": True,  # Claude 3 supports images
            "function_calling": True,  # Tool use support
            "high_quality": True,  # Very high quality
            "multilingual": True,  # Supports many languages
            "cloud_based": True,  # Requires internet connection
            "safety_focused": True,  # Strong safety measures
            "large_context": True  # Large context windows
        } 