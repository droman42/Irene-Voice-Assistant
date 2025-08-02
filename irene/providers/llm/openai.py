"""
OpenAI LLM Provider

Official OpenAI LLM provider implementation for GPT models.
Supports text enhancement, chat completion, and various language tasks.
"""

import os
import asyncio
from typing import Dict, Any, List
import logging

from .base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """Official OpenAI LLM Provider"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI provider with configuration
        
        Args:
            config: Provider configuration containing:
                - api_key_env: Environment variable name for API key
                - base_url: OpenAI API base URL
                - default_model: Default model to use
                - max_tokens: Maximum tokens in response
                - temperature: Temperature for text generation
        """
        super().__init__(config)  # Proper ABC inheritance
        self.api_key = os.getenv(config["api_key_env"])
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.default_model = config.get("default_model", "gpt-4")
        self.max_tokens = config.get("max_tokens", 150)
        self.temperature = config.get("temperature", 0.3)
        
    async def is_available(self) -> bool:
        """Check if OpenAI API is available"""
        try:
            import openai
            return self.api_key is not None
        except ImportError:
            logger.warning("OpenAI library not available")
            return False
    
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """Enhance text using OpenAI GPT models"""
        model = kwargs.get("model", self.default_model)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        prompts = {
            "improve_speech_recognition": "You are an assistant that fixes speech recognition errors. Fix the following text while preserving its meaning:",
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
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
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
            logger.error(f"OpenAI enhancement failed: {e}")
            return text  # Return original text on error
    
    async def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """Generate chat completion using OpenAI"""
        model = kwargs.get("model", self.default_model)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI chat completion failed: {e}")
            return "Sorry, I couldn't process that request."
    
    def get_available_models(self) -> List[str]:
        """Return list of available OpenAI models"""
        return [
            "gpt-4", "gpt-4-turbo", "gpt-4-turbo-preview",
            "gpt-3.5-turbo", "gpt-3.5-turbo-16k"
        ]
    
    def get_supported_tasks(self) -> List[str]:
        """Return list of supported enhancement tasks"""
        return [
            "improve_speech_recognition", "grammar_correction", "translation",
            "improve", "summarize", "expand"
        ]
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        """Return schema for OpenAI-specific parameters"""
        return {
            "model": {
                "type": "string",
                "options": self.get_available_models(),
                "default": self.default_model,
                "description": "OpenAI model to use"
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
                "default": "English",
                "description": "Target language for translation task"
            }
        }
    
    def get_provider_name(self) -> str:
        """Return provider identifier"""
        return "openai"
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Return OpenAI provider capabilities"""
        return {
            "models": self.get_available_models(),
            "tasks": self.get_supported_tasks(),
            "streaming": True,  # OpenAI supports streaming
            "multimodal": True,  # GPT-4 Vision support
            "function_calling": True,  # Function calling support
            "high_quality": True,  # Generally high quality
            "multilingual": True,  # Supports many languages
            "cloud_based": True  # Requires internet connection
        } 