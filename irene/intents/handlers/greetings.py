"""
Greetings Intent Handler - Greeting and farewell responses

Provides random greeting responses and welcome messages.
Adapted from greetings_plugin.py for the new intent architecture.
"""

import random
import logging
from typing import List, Optional, Dict

from .base import IntentHandler
from ..models import Intent, IntentResult, UnifiedConversationContext

logger = logging.getLogger(__name__)


class GreetingsIntentHandler(IntentHandler):
    """
    Handles greeting and farewell intents.
    
    Features:
    - Welcome messages
    - Farewell responses 
    - Random greeting variations
    - Context-aware responses
    """
    
    def __init__(self):
        super().__init__()
        
        # TODO #15: Phase 3 - Greeting templates now externalized to assets/templates/greetings/
        # All greeting arrays are loaded from template files with fatal error handling
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Greetings handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Greetings handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Greetings handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process greeting intents"""
        if not self.has_donation():
            raise RuntimeError(f"GreetingsIntentHandler: Missing JSON donation file - greetings.json is required")
        
        # Use JSON donation patterns exclusively
        donation = self.get_donation()
        
        # Check domain patterns
        if hasattr(donation, 'domain_patterns') and intent.domain in donation.domain_patterns:
            return True
        
        # Check intent name patterns
        if hasattr(donation, 'intent_name_patterns') and intent.name in donation.intent_name_patterns:
            return True
        
        # Check action patterns
        if hasattr(donation, 'action_patterns') and intent.action in donation.action_patterns:
            return True
        
        return False
    
    async def execute(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Execute greeting intent"""
        try:
            # Use language from context (detected by NLU)
            language = context.language or "ru"  # Fallback to Russian if not set
            
            if intent.action == "goodbye" or intent.name == "greeting.goodbye":
                return await self._handle_farewell(intent, context)
            elif intent.action == "welcome" or intent.name == "greeting.welcome":
                return await self._handle_welcome(intent, context)
            else:
                # Default: handle hello greeting
                return await self._handle_greeting(intent, context)
                
        except Exception as e:
            logger.error(f"Greeting intent execution failed: {e}")
            return IntentResult(
                text="Привет! Как дела?",  # Fallback greeting
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def is_available(self) -> bool:
        """Greetings are always available"""
        return True
    
    def _get_template_data(self, template_name: str, language: str = "ru") -> List[str]:
        """Get template data from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"GreetingsIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - greeting templates must be externalized."
            )
        
        # Get template directly from asset loader (template_name is the key from YAML)
        template_data = self.asset_loader.get_template("greetings", template_name, language)
        if template_data is None:
            raise RuntimeError(
                f"GreetingsIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/greetings/{language}/greetings.yaml. "
                f"This is a fatal error - all greeting templates must be externalized."
            )
        
        # Ensure it's a list and not empty
        if not isinstance(template_data, list) or not template_data:
            raise RuntimeError(
                f"GreetingsIntentHandler: Template '{template_name}' in "
                f"assets/templates/greetings/{language}/greetings.yaml is not a valid list or is empty. "
                f"At least one {template_name} must be defined for language '{language}'."
            )
        
        return template_data
    
    def _get_time_based_greeting_template(self, time_period: str, language: str = "ru") -> str:
        """Get time-based greeting from templates - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"GreetingsIntentHandler: Asset loader not initialized. "
                f"Cannot access time-based greeting for language '{language}'. "
                f"This is a fatal configuration error - greeting templates must be externalized."
            )
        
        # Get time-based greetings template directly
        time_greetings = self.asset_loader.get_template("greetings", "time_based_greetings", language)
        if time_greetings is None:
            raise RuntimeError(
                f"GreetingsIntentHandler: Required time-based greetings for language '{language}' "
                f"not found in assets/templates/greetings/{language}/greetings.yaml. "
                f"This is a fatal error - all time-based greeting templates must be externalized."
            )
        
        # Ensure it's a dict and has the time period
        greeting = time_greetings.get(time_period) if isinstance(time_greetings, dict) else None
        if not greeting:
            raise RuntimeError(
                f"GreetingsIntentHandler: Missing time-based greeting '{time_period}' in "
                f"assets/templates/greetings/{language}/greetings.yaml. "
                f"All time periods (morning, afternoon, evening, night) must be defined."
            )
        
        return greeting
    
    async def _handle_greeting(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle hello greeting intent"""
        # Use language from context (already detected by NLU)
        language = context.language or "ru"
        
        greetings = self._get_template_data("greetings", language)
        greeting = random.choice(greetings)
        
        # Add time-based greeting if possible
        time_greeting = self._get_time_based_greeting(language)
        if time_greeting:
            greeting = f"{time_greeting} {greeting}"
        
        return IntentResult(
            text=greeting,
            should_speak=True,
            metadata={
                "greeting_type": "hello",
                "language": language,
                "random_selection": True
            }
        )
    
    async def _handle_farewell(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle goodbye farewell intent"""
        # Use language from context (already detected by NLU)
        language = context.language or "ru"
        
        farewells = self._get_template_data("farewells", language)
        farewell = random.choice(farewells)
        
        return IntentResult(
            text=farewell,
            should_speak=True,
            metadata={
                "greeting_type": "farewell",
                "language": language,
                "conversation_ending": True
            }
        )
    
    async def _handle_welcome(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle welcome message intent"""
        # Use language from context (already detected by NLU)
        language = context.language or "ru"
        
        welcome_messages = self._get_template_data("welcome_messages", language)
        welcome = random.choice(welcome_messages)
        
        return IntentResult(
            text=welcome,
            should_speak=True,
            metadata={
                "greeting_type": "welcome",
                "language": language,
                "first_interaction": True
            }
        )
    
    def _get_time_based_greeting(self, language: str) -> Optional[str]:
        """Get time-based greeting prefix from templates"""
        try:
            import datetime
            current_hour = datetime.datetime.now().hour
            
            # Determine time period
            if 5 <= current_hour < 12:
                time_period = "morning"
            elif 12 <= current_hour < 18:
                time_period = "afternoon"
            elif 18 <= current_hour < 22:
                time_period = "evening"
            else:
                time_period = "night"
            
            # Get time-based greeting from templates
            return self._get_time_based_greeting_template(time_period, language)
                    
        except Exception:
            return None
    
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Greetings handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
    
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Greetings handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Configuration metadata: No configuration needed
    # This handler uses asset loader for template data only
    # No get_config_schema() method = no configuration required
 