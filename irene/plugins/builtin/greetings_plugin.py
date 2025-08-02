"""
Greetings Plugin - Random greeting responses

Replaces legacy plugin_greetings.py with modern async architecture.
Provides random greeting responses and welcome messages.
"""

import random
from typing import List, Optional, Dict, Any

from ...core.context import Context
from ...core.commands import CommandResult
from ...core.interfaces.webapi import WebAPIPlugin
from ..base import BaseCommandPlugin


class GreetingsPlugin(BaseCommandPlugin, WebAPIPlugin):
    """
    Greetings plugin providing random welcome and greeting responses.
    
    Features:
    - Random greeting selection
    - Multiple greeting variations
    - Friendly welcome messages
    - Russian language support
    - Web API endpoints for greeting management
    """
    
    @property
    def name(self) -> str:
        return "greetings"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Greeting and farewell responses with bilingual support and web API"
        
    @property
    def dependencies(self) -> list[str]:
        """No dependencies for greetings"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """No optional dependencies for greetings"""
        return []
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """Greetings should be enabled by default"""
        return True
        
    @property  
    def category(self) -> str:
        """Plugin category"""
        return "command"
        
    @property
    def platforms(self) -> list[str]:
        """Supported platforms (empty = all platforms)"""
        return []
        
    def __init__(self):
        super().__init__()
        # Russian greeting triggers
        self.add_trigger("привет")
        self.add_trigger("доброе утро")
        self.add_trigger("добрый день")
        self.add_trigger("добрый вечер")
        self.add_trigger("здравствуй")
        self.add_trigger("здравствуйте")
        # English greeting triggers
        self.add_trigger("hello")
        self.add_trigger("hi")
        self.add_trigger("good morning")
        self.add_trigger("good afternoon")
        self.add_trigger("good evening")
        
        # Greeting responses in Russian
        self.russian_greetings = [
            "И тебе привет!",
            "Рада тебя видеть!",
            "Привет! Как дела?",
            "Добро пожаловать!",
            "Здравствуй! Что нового?",
            "Привет! Чем могу помочь?",
            "Рада нашей встрече!",
            "Привет! Готова к работе!",
            "Здравствуй! Как настроение?",
            "Привет! Что будем делать?"
        ]
        
        # Greeting responses in English
        self.english_greetings = [
            "Hello there!",
            "Hi! Nice to see you!",
            "Hello! How are you doing?",
            "Welcome!",
            "Hi! What's new?",
            "Hello! How can I help?",
            "Nice to meet you!",
            "Hi! Ready to work!",
            "Hello! How's your mood?",
            "Hi! What shall we do?"
        ]
        
        # Custom greetings storage
        self.custom_greetings = {
            "ru": [],
            "en": []
        }
        
    # BaseCommandPlugin interface - existing voice functionality
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle greeting commands"""
        command_lower = command.lower().strip()
        
        # Determine language and select appropriate greetings
        if any(trigger in command_lower for trigger in ["привет", "доброе", "добрый", "здравствуй"]):
            # Russian greeting
            greeting = self.get_random_greeting("ru")
        else:
            # English greeting
            greeting = self.get_random_greeting("en")
        
        # Log the greeting for debugging (like legacy plugin)
        self.logger.info(f"Selected greeting: {greeting}")
        
        return CommandResult.success_result(
            response=greeting,
            should_continue_listening=True  # Keep listening after greeting
        )
    
    # Greeting functionality methods (used by both voice and API)
    def get_random_greeting(self, language: str = "ru") -> str:
        """Get a random greeting in specified language"""
        if language.lower() == "ru":
            all_greetings = self.russian_greetings + self.custom_greetings["ru"]
        elif language.lower() == "en":
            all_greetings = self.english_greetings + self.custom_greetings["en"]
        else:
            # Default to Russian
            all_greetings = self.russian_greetings + self.custom_greetings["ru"]
        
        if not all_greetings:
            return "Hello!" if language.lower() == "en" else "Привет!"
            
        return random.choice(all_greetings)
    
    def add_custom_greeting(self, text: str, language: str = "ru") -> bool:
        """Add a custom greeting"""
        if language.lower() in ["ru", "en"]:
            if text.strip() and text not in self.custom_greetings[language.lower()]:
                self.custom_greetings[language.lower()].append(text.strip())
                return True
        return False
    
    def remove_custom_greeting(self, text: str, language: str = "ru") -> bool:
        """Remove a custom greeting"""
        if language.lower() in ["ru", "en"]:
            if text in self.custom_greetings[language.lower()]:
                self.custom_greetings[language.lower()].remove(text)
                return True
        return False
    
    def get_all_greetings(self, language: str = "ru") -> Dict[str, List[str]]:
        """Get all greetings (built-in and custom) for a language"""
        if language.lower() == "ru":
            return {
                "built_in": self.russian_greetings.copy(),
                "custom": self.custom_greetings["ru"].copy()
            }
        elif language.lower() == "en":
            return {
                "built_in": self.english_greetings.copy(),
                "custom": self.custom_greetings["en"].copy()
            }
        else:
            return {"built_in": [], "custom": []}
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return ["ru", "en"]
    
    def get_greeting_stats(self) -> Dict[str, Any]:
        """Get statistics about greetings"""
        return {
            "total_russian": len(self.russian_greetings) + len(self.custom_greetings["ru"]),
            "total_english": len(self.english_greetings) + len(self.custom_greetings["en"]),
            "built_in_russian": len(self.russian_greetings),
            "built_in_english": len(self.english_greetings),
            "custom_russian": len(self.custom_greetings["ru"]),
            "custom_english": len(self.custom_greetings["en"]),
            "supported_languages": self.get_supported_languages()
        }
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with greeting endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class GreetingRequest(BaseModel):
                text: str
                language: str = "ru"
                
            class GreetingResponse(BaseModel):
                greeting: str
                language: str
                
            class GreetingsListResponse(BaseModel):
                built_in: List[str]
                custom: List[str]
                language: str
                total_count: int
                
            class LanguagesResponse(BaseModel):
                supported_languages: List[str]
                
            class StatsResponse(BaseModel):
                total_russian: int
                total_english: int
                built_in_russian: int
                built_in_english: int
                custom_russian: int
                custom_english: int
                supported_languages: List[str]
                
            class ActionResponse(BaseModel):
                success: bool
                message: str
            
            @router.get("/random", response_model=GreetingResponse)
            async def get_random_greeting(language: str = "ru"):
                """Get a random greeting in specified language"""
                try:
                    greeting = self.get_random_greeting(language)
                    return GreetingResponse(
                        greeting=greeting,
                        language=language
                    )
                except Exception as e:
                    raise HTTPException(500, f"Error getting random greeting: {str(e)}")
            
            @router.post("/custom", response_model=ActionResponse)
            async def add_custom_greeting(request: GreetingRequest):
                """Add a custom greeting"""
                success = self.add_custom_greeting(request.text, request.language)
                
                if success:
                    return ActionResponse(
                        success=True,
                        message=f"Custom greeting added successfully in {request.language}"
                    )
                else:
                    return ActionResponse(
                        success=False,
                        message="Failed to add greeting (already exists or invalid language)"
                    )
            
            @router.delete("/custom", response_model=ActionResponse)
            async def remove_custom_greeting(request: GreetingRequest):
                """Remove a custom greeting"""
                success = self.remove_custom_greeting(request.text, request.language)
                
                if success:
                    return ActionResponse(
                        success=True,
                        message=f"Custom greeting removed successfully from {request.language}"
                    )
                else:
                    return ActionResponse(
                        success=False,
                        message="Greeting not found or invalid language"
                    )
            
            @router.get("/list", response_model=GreetingsListResponse)
            async def list_greetings(language: str = "ru"):
                """List all greetings for a language"""
                greetings = self.get_all_greetings(language)
                total_count = len(greetings["built_in"]) + len(greetings["custom"])
                
                return GreetingsListResponse(
                    built_in=greetings["built_in"],
                    custom=greetings["custom"],
                    language=language,
                    total_count=total_count
                )
            
            @router.get("/languages", response_model=LanguagesResponse)
            async def list_languages():
                """List supported languages"""
                return LanguagesResponse(
                    supported_languages=self.get_supported_languages()
                )
            
            @router.get("/stats", response_model=StatsResponse)
            async def get_greeting_stats():
                """Get greeting statistics"""
                stats = self.get_greeting_stats()
                return StatsResponse(**stats)
            
            return router
            
        except ImportError:
            self.logger.warning("FastAPI not available for greetings web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for greetings API endpoints"""
        return "/greetings"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for greetings endpoints"""
        return ["Greetings", "Social"] 