"""
Random Intent Handler - Coin flips, dice rolls, and random numbers

Replaces the RandomPlugin with modern intent-based architecture.
Provides random number generation, coin flips, and dice rolls.
"""

import random
import asyncio
import logging
from typing import List, Dict, Any

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
    
    def __init__(self):
        super().__init__()
        
        # Coin flip results in Russian
        self.coin_results_ru = [
            "Выпал орёл",
            "Выпала решка",
        ]
        
        # Dice roll results in Russian
        self.dice_results_ru = [
            "Выпала единица",
            "Выпало два",
            "Выпало три",
            "Выпало четыре",
            "Выпало пять",
            "Выпало шесть",
        ]
        
        # Coin flip results in English
        self.coin_results_en = [
            "Heads!",
            "Tails!",
        ]
        
        # Dice roll results in English
        self.dice_results_en = [
            "You rolled a one",
            "You rolled a two",
            "You rolled a three",
            "You rolled a four",
            "You rolled a five",
            "You rolled a six",
        ]

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Random handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Random handler has no system dependencies - pure Python logic"""
        return {
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Random handler supports all platforms"""
        return ["linux", "windows", "macos"]
        
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
        # Determine language from context or intent
        language = self._get_language(intent, context)
        
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
        # Determine language from context or intent
        language = self._get_language(intent, context)
        
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
            error_msg = "Некорректные параметры кубика" if language == "ru" else f"Invalid dice parameters: {str(e)}"
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
        
    async def _handle_random_number(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle random number generation request"""
        # Determine language from context or intent
        language = self._get_language(intent, context)
        
        # Extract parameters from intent
        min_val = intent.entities.get("min", 1)
        max_val = intent.entities.get("max", 100)
        
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
            error_msg = "Некорректный диапазон чисел" if language == "ru" else f"Invalid number range: {str(e)}"
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
        
    async def _handle_random_choice(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle random choice from options"""
        # Determine language from context or intent
        language = self._get_language(intent, context)
        
        # Extract options from intent
        options = intent.entities.get("options", [])
        if isinstance(options, str):
            # Split by common delimiters
            options = [opt.strip() for opt in options.replace(',', ' ').replace('или', ' ').replace('or', ' ').split()]
        
        if not options:
            error_msg = "Не указаны варианты для выбора" if language == "ru" else "No options provided for choice"
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
            error_msg = "Ошибка при выборе варианта" if language == "ru" else f"Error making choice: {str(e)}"
            return IntentResult(
                text=error_msg,
                should_speak=True,
                success=False
            )
    

    
    # Random functionality methods (core logic)
    def flip_coin(self, language: str = "ru") -> Dict[str, Any]:
        """Flip a coin and return result"""
        result_index = random.randint(0, 1)
        
        if language.lower() == "ru":
            result_text = self.coin_results_ru[result_index]
        else:
            result_text = self.coin_results_en[result_index]
        
        return {
            "result": "heads" if result_index == 0 else "tails",
            "result_text": result_text,
            "language": language
        }
    
    def roll_dice(self, sides: int = 6, count: int = 1, language: str = "ru") -> Dict[str, Any]:
        """Roll dice and return results"""
        if sides < 2 or sides > 100:
            raise ValueError("Dice sides must be between 2 and 100")
        if count < 1 or count > 10:
            raise ValueError("Dice count must be between 1 and 10")
        
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        
        # Format result text
        if language.lower() == "ru":
            if count == 1 and sides == 6 and rolls[0] <= 6:
                result_text = self.dice_results_ru[rolls[0] - 1]
            else:
                result_text = f"Выпало: {', '.join(map(str, rolls))}"
                if count > 1:
                    result_text += f" (сумма: {total})"
        else:
            if count == 1 and sides == 6 and rolls[0] <= 6:
                result_text = self.dice_results_en[rolls[0] - 1]
            else:
                result_text = f"Rolled: {', '.join(map(str, rolls))}"
                if count > 1:
                    result_text += f" (total: {total})"
        
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
        if abs(max_val - min_val) > 1000000:
            raise ValueError("Range too large (max 1,000,000)")
        
        number = random.randint(min_val, max_val)
        
        if language.lower() == "ru":
            result_text = f"Случайное число: {number}"
        else:
            result_text = f"Random number: {number}"
        
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
        
        if language.lower() == "ru":
            result_text = f"Выбрано: {choice}"
        else:
            result_text = f"Chosen: {choice}"
        
        return {
            "choice": choice,
            "options": options,
            "result_text": result_text,
            "language": language
        }
    

        
    def _get_language(self, intent: Intent, context: ConversationContext) -> str:
        """Determine language from intent or context"""
        # Check intent entities first
        if "language" in intent.entities:
            return intent.entities["language"]
        
        # Check if text contains Russian characters
        if any(char in intent.text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"):
            return "ru"
        
        # Default to Russian
        return "ru"
