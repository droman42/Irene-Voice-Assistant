"""
Random Intent Handler - Coin flips, dice rolls, and random numbers

Replaces the RandomPlugin with modern intent-based architecture.
Provides random number generation, coin flips, and dice rolls.
"""

import random
import asyncio
import logging
from typing import List, Dict, Any, Optional

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class RandomIntentHandler(IntentHandler):
    """
    Handles random generation intents - coin flips, dice rolls, and random numbers.
    
    Features:
    - Coin flip (heads/tails)
    - Dice roll (1-6 or custom)
    - Random number generation
    - Random choice from options
    - Russian and English language support
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        
        # Phase 5: Configuration injection via Pydantic RandomHandlerConfig
        if config:
            self.config = config
            self.default_max_number = config.get("default_max_number", 100)
            self.max_range_size = config.get("max_range_size", 1000000)
            self.default_dice_sides = config.get("default_dice_sides", 6)
            logger.info(f"RandomIntentHandler initialized with config: default_max={self.default_max_number}, max_range={self.max_range_size}, dice_sides={self.default_dice_sides}")
        else:
            # Fallback defaults (should not be used in production with proper config)
            self.config = {
                "default_max_number": 100,
                "max_range_size": 1000000,
                "default_dice_sides": 6
            }
            self.default_max_number = 100
            self.max_range_size = 1000000
            self.default_dice_sides = 6
            logger.warning("RandomIntentHandler initialized without configuration - using fallback defaults")

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Random handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Random handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Random handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process random intents"""
        if not self.has_donation():
            raise RuntimeError(f"RandomIntentHandler: Missing JSON donation file - random_handler.json is required")
        
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
        
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute random generation intent"""
        # Use donation-driven routing exclusively
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_coin_flip(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle coin flip request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Add small delay to simulate async operation
        await asyncio.sleep(0.05)
        
        result = self.flip_coin(language)
        
        self.logger.info(f"Coin flip result: {result['result_text']}")
        
        return IntentResult(
            text=result["result_text"],
            should_speak=True,
            metadata={"result": result["result"], "language": language},
            success=True
        )
        
    async def _handle_dice_roll(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle dice roll request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Extract parameters from intent
        sides = intent.entities.get("sides", 6)
        count = intent.entities.get("count", 1)
        
        # Validate parameters
        try:
            sides = int(sides) if sides else 6
            count = int(count) if count else 1
        except (ValueError, TypeError):
            sides, count = 6, 1
        
        # Add small delay to simulate async operation
        await asyncio.sleep(0.05)
        
        try:
            result = self.roll_dice(sides, count, language)
            
            self.logger.info(f"Dice roll result: {result['result_text']}")
            
            return IntentResult(
                text=result["result_text"],
                should_speak=True,
                metadata={
                    "rolls": result["rolls"],
                    "total": result["total"],
                    "sides": sides,
                    "count": count,
                    "language": language
                },
                success=True
            )
            
        except ValueError as e:
            error_msg = self._get_template("invalid_dice_params", language) if language == "ru" else self._get_template("invalid_dice_params", language, error=str(e))
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
        
    async def _handle_random_number(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle random number generation request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Extract parameters from intent (Phase 5: Use configured defaults)
        min_val = intent.entities.get("min", 1)
        max_val = intent.entities.get("max", self.default_max_number)
        
        # Validate parameters
        try:
            min_val = int(min_val) if min_val else 1
            max_val = int(max_val) if max_val else 100
        except (ValueError, TypeError):
            min_val, max_val = 1, 100
        
        # Add small delay to simulate async operation
        await asyncio.sleep(0.05)
        
        try:
            result = self.generate_random_number(min_val, max_val, language)
            
            self.logger.info(f"Random number generated: {result['number']}")
            
            return IntentResult(
                text=result["result_text"],
                should_speak=True,
                metadata={
                    "number": result["number"],
                    "min_val": min_val,
                    "max_val": max_val,
                    "language": language
                },
                success=True
            )
            
        except ValueError as e:
            error_msg = self._get_template("invalid_number_range", language) if language == "ru" else self._get_template("invalid_number_range", language, error=str(e))
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
        
    async def _handle_random_choice(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle random choice from options"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Extract options from intent
        options = intent.entities.get("options", [])
        if isinstance(options, str):
            # Split by common delimiters
            options = [opt.strip() for opt in options.replace(',', ' ').replace('или', ' ').replace('or', ' ').split()]
        
        if not options:
            error_msg = self._get_template("no_options", language)
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
        
        # Add small delay to simulate async operation
        await asyncio.sleep(0.05)
        
        try:
            result = self.random_choice(options, language)
            
            self.logger.info(f"Random choice made: {result['choice']}")
            
            return IntentResult(
                text=result["result_text"],
                should_speak=True,
                metadata={
                    "choice": result["choice"],
                    "options": options,
                    "language": language
                },
                success=True
            )
            
        except ValueError as e:
            error_msg = self._get_template("choice_error", language) if language == "ru" else self._get_template("choice_error", language, error=str(e))
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
    

    
    # Random functionality methods (core logic)
    def flip_coin(self, language: str = "ru") -> Dict[str, Any]:
        """Flip a coin and return result"""
        result_index = random.randint(0, 1)
        
        coin_results = self._get_template_data("coin_results", language)
        result_text = coin_results[result_index]
        
        return {
            "result": "heads" if result_index == 0 else "tails",
            "result_text": result_text,
            "language": language
        }
    
    def roll_dice(self, sides: int = None, count: int = 1, language: str = "ru") -> Dict[str, Any]:
        """Roll dice and return results (Phase 5: Use configured defaults)"""
        # Use configured default dice sides if not specified
        if sides is None:
            sides = self.default_dice_sides
            
        if sides < 2 or sides > 100:
            raise ValueError("Dice sides must be between 2 and 100")
        if count < 1 or count > 10:
            raise ValueError("Dice count must be between 1 and 10")
        
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        
        # Format result text
        if count == 1 and sides == 6 and rolls[0] <= 6:
            dice_results = self._get_template_data("dice_results", language)
            result_text = dice_results[rolls[0] - 1]
        else:
            rolls_str = ', '.join(map(str, rolls))
            if count > 1:
                result_text = self._get_template("dice_with_total", language, rolls=rolls_str, total=total)
            else:
                result_text = self._get_template("dice_multiple", language, rolls=rolls_str)
        
        return {
            "rolls": rolls,
            "total": total,
            "sides": sides,
            "count": count,
            "result_text": result_text,
            "language": language
        }
    
    def generate_random_number(self, min_val: int = 1, max_val: int = 100, language: str = "ru") -> Dict[str, Any]:
        """Generate a random number in specified range"""
        if min_val >= max_val:
            raise ValueError("min_val must be less than max_val")
        if abs(max_val - min_val) > self.max_range_size:
            raise ValueError(f"Range too large (max {self.max_range_size:,})")
        
        number = random.randint(min_val, max_val)
        
        result_text = self._get_template("random_number", language, number=number)
        
        return {
            "number": number,
            "min_val": min_val,
            "max_val": max_val,
            "result_text": result_text,
            "language": language
        }
    
    def random_choice(self, options: List[str], language: str = "ru") -> Dict[str, Any]:
        """Choose randomly from a list of options"""
        if not options:
            raise ValueError("Options list cannot be empty")
        if len(options) > 50:
            raise ValueError("Too many options (max 50)")
        
        choice = random.choice(options)
        
        result_text = self._get_template("random_choice", language, choice=choice)
        
        return {
            "choice": choice,
            "options": options,
            "result_text": result_text,
            "language": language
        }
    

        
    def _get_template_data(self, template_name: str, language: str = "ru") -> List[str]:
        """Get template data from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"RandomIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - random templates must be externalized."
            )
        
        # Get template directly from asset loader (template_name is the key from YAML)
        template_data = self.asset_loader.get_template("random", template_name, language)
        if template_data is None:
            raise RuntimeError(
                f"RandomIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/random/{language}/results.yaml. "
                f"This is a fatal error - all random templates must be externalized."
            )
        
        # Ensure it's a list and not empty
        if not isinstance(template_data, list) or not template_data:
            raise RuntimeError(
                f"RandomIntentHandler: Template '{template_name}' in "
                f"assets/templates/random/{language}/results.yaml is not a valid list or is empty. "
                f"At least one {template_name} must be defined for language '{language}'."
            )
        
        return template_data
    
    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"RandomIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - random templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("random", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"RandomIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/random/{language}/results.yaml. "
                f"This is a fatal error - all random templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"RandomIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/random/{language}/results.yaml for correct placeholders."
            )
    

