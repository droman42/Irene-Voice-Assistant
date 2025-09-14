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
    """
    Official OpenAI LLM Provider
    
    Enhanced in TODO #4 Phase 1 with intelligent asset defaults.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize OpenAI provider with configuration
        
        Args:
            config: Provider configuration containing:
                - api_key_env: Environment variable name for API key (deprecated - uses asset manager)
                - base_url: OpenAI API base URL
                - default_model: Default model to use
                - max_tokens: Maximum tokens in response
                - temperature: Temperature for text generation
        """
        super().__init__(config)  # Proper ABC inheritance
        
        # Asset management integration for credentials
        from ...core.assets import get_asset_manager
        self.asset_manager = get_asset_manager()
        
        # Get API key through asset manager or fallback to config
        credentials = self.asset_manager.get_credentials("openai")
        self.api_key = credentials.get("openai_api_key") or os.getenv(config.get("api_key_env", "OPENAI_API_KEY"))
        
        if not self.api_key and config.get("api_key_env"):
            logger.warning("Using legacy api_key_env config. Consider using OPENAI_API_KEY environment variable.")
            
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.default_model = config.get("default_model", "gpt-4o-mini")
        self.max_tokens = config.get("max_tokens", 150)
        self.temperature = config.get("temperature", 0.3)
    
    @classmethod
    def _get_default_extension(cls) -> str:
        """OpenAI is API-based, no persistent files"""
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """OpenAI uses runtime cache only"""
        return "openai"
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """OpenAI requires API key credential"""
        return ["OPENAI_API_KEY"]
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """Uses runtime cache for request/response data only"""
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """OpenAI is API-based, no model downloads"""
        return {}
    
    async def is_available(self) -> bool:
        """Check if OpenAI API is available and validate configured model"""
        try:
            from openai import AsyncOpenAI
            if not self.api_key:
                logger.error("OpenAI API key not configured")
                return False
                
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # Get available models for this API key
            try:
                models_response = await client.models.list()
                available_models = {model.id for model in models_response.data}
                
                if self.default_model not in available_models:
                    logger.error(
                        "Configured model '%s' not available for this API key. "
                        "Available models: %s", 
                        self.default_model, 
                        sorted(list(available_models))[:10]
                    )
                    return False
                    
                logger.info(
                    "OpenAI provider validated: model '%s' available", 
                    self.default_model
                )
                return True
                
            except Exception as e:
                logger.warning(
                    "Could not validate OpenAI model availability: %s. "
                    "Proceeding with basic API key check.", e
                )
                return True  # Fallback to basic availability
                
        except ImportError:
            logger.error("OpenAI library not available. Install with: pip install openai>=1.0.0")
            return False
        except Exception as e:
            logger.error("OpenAI availability check failed: %s", e)
            return False
    
    async def enhance_text(self, text: str, task: str = "improve", **kwargs) -> str:
        """Enhance text using OpenAI GPT models with smart API routing"""
        model = kwargs.get("model") or self.default_model  # Handle None model parameter
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
            from openai import AsyncOpenAI  # type: ignore
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # Smart routing: use appropriate API for the model
            if model in self._get_chat_compatible_models():
                logger.debug("Using Chat Completions API for model: %s", model)
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
                
            elif model in self._get_responses_compatible_models():
                logger.debug("Using Responses API for model: %s", model)
                # Combine system prompt and user text for Responses API
                full_input = f"{system_prompt}\n\n{text}"
                response = await client.responses.create(
                    model=model,
                    input=full_input,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
                # Use convenience property or fallback to response structure
                return getattr(response, "output_text", response.output[0].content[0].text).strip()
                
            else:
                # Unknown model - try Chat Completions first, then log
                logger.warning("Unknown model '%s', attempting Chat Completions API", model)
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
            logger.error(
                "OpenAI enhancement failed for model '%s' at %s: %s", 
                model, self.base_url, e
            )
            return text  # Return original text on error
    
    async def chat_completion(self, messages: List[Dict], **kwargs) -> str:
        """Generate chat completion using OpenAI with smart API routing"""
        model = kwargs.get("model") or self.default_model  # Handle None model parameter
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)
        
        try:
            from openai import AsyncOpenAI  # type: ignore
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            
            # Smart routing: use appropriate API for the model
            if model in self._get_chat_compatible_models():
                logger.debug("Using Chat Completions API for model: %s", model)
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content.strip()
                
            elif model in self._get_responses_compatible_models():
                logger.debug("Using Responses API for model: %s", model)
                # Flatten chat messages into a single input string (simple adapter)
                user_text = "\n".join(
                    f"{m['role']}: {m['content']}" if isinstance(m.get("content"), str)
                    else f"{m['role']}: {m['content']}" for m in messages
                )
                response = await client.responses.create(
                    model=model,
                    input=user_text,
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                )
                # Use convenience property or fallback to response structure
                return getattr(response, "output_text", response.output[0].content[0].text).strip()
                
            else:
                # Unknown model - try Chat Completions first, then log
                logger.warning("Unknown model '%s', attempting Chat Completions API", model)
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(
                "OpenAI chat completion failed for model '%s' at %s: %s", 
                model, self.base_url, e
            )
            return "Sorry, I couldn't process that request."
    
    def get_available_models(self) -> List[str]:
        """Return list of known OpenAI models"""
        # Only include models that are currently available and stable
        return [
            "gpt-4o",           # Latest GPT-4 Omni
            "gpt-4o-mini",      # Smaller GPT-4 Omni
            "gpt-4-turbo",      # GPT-4 Turbo
            "gpt-4",            # Standard GPT-4
            "gpt-3.5-turbo"     # GPT-3.5 (if available)
        ]
    
    def _get_chat_compatible_models(self) -> set:
        """Return models that work with Chat Completions API"""
        return {
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", 
            "gpt-4", "gpt-3.5-turbo"
        }
    
    def _get_responses_compatible_models(self) -> set:
        """Return models that work with Responses API"""
        return {
            "o3", "o3-mini", "o4-mini", 
            "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano"
        }
    
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
    
    # Build dependency methods (TODO #5 Phase 1)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """OpenAI requires specific openai library"""
        return ["openai>=1.0.0"]
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """OpenAI is cloud-based, no system dependencies"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """OpenAI supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
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