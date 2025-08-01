"""
Greetings Plugin - Random greeting responses

Replaces legacy plugin_greetings.py with modern async architecture.
Provides random greeting responses and welcome messages.
"""

import random
from typing import List

from ...core.context import Context
from ...core.commands import CommandResult
from ..base import BaseCommandPlugin


class GreetingsPlugin(BaseCommandPlugin):
    """
    Greetings plugin providing random welcome and greeting responses.
    
    Features:
    - Random greeting selection
    - Multiple greeting variations
    - Friendly welcome messages
    - Russian language support
    """
    
    @property
    def name(self) -> str:
        return "greetings"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Greeting and farewell responses with bilingual support"
        
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
        
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle greeting commands"""
        command_lower = command.lower().strip()
        
        # Determine language and select appropriate greetings
        if any(trigger in command_lower for trigger in ["привет", "доброе", "добрый", "здравствуй"]):
            # Russian greeting
            greeting = random.choice(self.russian_greetings)
        else:
            # English greeting
            greeting = random.choice(self.english_greetings)
        
        # Log the greeting for debugging (like legacy plugin)
        self.logger.info(f"Selected greeting: {greeting}")
        
        return CommandResult.success_result(
            response=greeting,
            should_continue_listening=True  # Keep listening after greeting
        ) 