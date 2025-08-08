"""
VseGPT LLM Provider

VseGPT LLM provider implementation - OpenAI-compatible API with different endpoint.
Provides an alternative to OpenAI with similar functionality but different pricing/access.
"""

import os
import asyncio
from typing import Dict, Any, List
import logging

from .base import LLMProvider

logger = logging.getLogger(__name__)


class VseGPTLLMProvider(LLMProvider):
    """VseGPT LLM Provider - OpenAI-compatible API with different endpoint"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize VseGPT provider with configuration
        
        Args:
            config: Provider configuration containing:
                - api_key_env: Environment variable name for API key (deprecated - uses asset manager)
                - base_url: VseGPT API base URL
                - default_model: Default model to use
                - max_tokens: Maximum tokens in response
                - temperature: Temperature for text generation
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Asset management integration for credentials
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Get API key through asset manager or fallback to config
        credentials = self.asset_manager.get_credentials("vsegpt")
        self.api_key = credentials.get("vsegpt_api_key") or os.getenv(config.get("api_key_env", "VSEGPT_API_KEY"))
        
        if not self.api_key and config.get("api_key_env"):
            logger.warning("Using legacy api_key_env config. Consider using VSEGPT_API_KEY environment variable.")
            
        self.base_url = config.get("base_url", "https://api.vsegpt.ru/v1")
        self.default_model = config.get("default_model", "openai/gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 150)
        self.temperature = config.get("temperature", 0.3)
        
    async def is_available(self) -> bool:
        """Check if VseGPT API is available"""
        if not self.api_key:
            logger.warning("VseGPT API key not found")
            return False
            
        try:
            import openai  # VseGPT uses OpenAI-compatible client
            return True
        except ImportError:
            logger.warning("OpenAI library not available (required for VseGPT)")
            return False
    
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """Enhance text using VseGPT models"""
        model = kwargs.get("model", self.default_model)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        # Same prompts as OpenAI but optimized for Russian content
        prompts = {
            "improve_speech_recognition": "Ты помощник, который исправляет ошибки распознавания речи. Исправь следующий текст, сохраняя его смысл:",
            "grammar_correction": "Исправь грамматику и пунктуацию в следующем тексте:",
            "translation": "Переведи следующий текст на {target_language}:",
            "improve": "Улучши следующий текст для ясности и читаемости:",
            "summarize": "Кратко изложи следующий текст:",
            "expand": "Расширь и детализируй следующий текст:"
        }
        
        system_prompt = prompts.get(task, prompts["improve"])
        if task == "translation":
            target_language = kwargs.get("target_language", "русский")
            system_prompt = system_prompt.format(target_language=target_language)
        
        try:
            from openai import AsyncOpenAI  # type: ignore
            # VseGPT API call (OpenAI-compatible)
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"VseGPT enhancement failed: {e}")
            return text  # Return original text on error
    
    async def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """Generate chat completion using VseGPT"""
        model = kwargs.get("model", self.default_model)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        try:
            from openai import AsyncOpenAI  # type: ignore
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"VseGPT chat completion failed: {e}")
            return "Извините, не удалось обработать этот запрос."
    
    def get_available_models(self) -> List[str]:
        """Return list of available VseGPT models"""
        return [
            "openai/gpt-4o-mini", "openai/gpt-4o", "openai/gpt-4-turbo",
            "openai/gpt-3.5-turbo", "anthropic/claude-3-haiku",
            "anthropic/claude-3-sonnet", "google/gemini-pro",
            "mistralai/mistral-7b-instruct"
        ]
    
    def get_supported_tasks(self) -> List[str]:
        """Return list of supported enhancement tasks"""
        return [
            "improve_speech_recognition", "grammar_correction", "translation",
            "improve", "summarize", "expand"
        ]
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for VseGPT-specific parameters"""
        return {
            "model": {
                "type": "string",
                "options": self.get_available_models(),
                "default": self.default_model,
                "description": "VseGPT model to use"
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
                "max": 2.0,
                "default": self.temperature,
                "description": "Temperature for text generation"
            },
            "target_language": {
                "type": "string",
                "default": "русский",
                "description": "Target language for translation task"
            }
        }
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "vsegpt"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return VseGPT provider capabilities"""
        return {
            "models": self.get_available_models(),
            "tasks": self.get_supported_tasks(),
            "streaming": True,  # VseGPT supports streaming
            "multimodal": False,  # Limited multimodal support
            "function_calling": True,  # Function calling support
            "high_quality": True,  # Good quality models
            "multilingual": True,  # Supports many languages
            "cloud_based": True,  # Requires internet connection
            "russian_optimized": True,  # Optimized for Russian content
            "cost_effective": True  # Generally lower cost than OpenAI
        } 