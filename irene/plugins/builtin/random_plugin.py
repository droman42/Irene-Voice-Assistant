"""
Random Plugin - Coin flips and dice rolls

Replaces legacy plugin_random.py with modern async architecture.
Provides random number generation, coin flips, and dice rolls.
"""

import random
import asyncio
from typing import List, Optional, Dict, Any

from ...core.context import Context
from ...core.commands import CommandResult
from ...core.interfaces.webapi import WebAPIPlugin
from ..base import BaseCommandPlugin


class RandomPlugin(BaseCommandPlugin, WebAPIPlugin):
    """
    Random plugin providing coin flips, dice rolls, and random numbers.
    
    Features:
    - Coin flip (heads/tails)
    - Dice roll (1-6)
    - Random number generation
    - Russian language support
    - Web API endpoints for random operations
    """
    
    @property
    def name(self) -> str:
        return "random"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Random numbers, coin flips, and dice rolls with web API"
        
    @property
    def dependencies(self) -> list[str]:
        """No dependencies for random"""
        return []
        
    @property
    def optional_dependencies(self) -> list[str]:
        """No optional dependencies for random"""
        return []
        
    # Additional metadata for PluginRegistry discovery
    @property
    def enabled_by_default(self) -> bool:
        """Random should be enabled by default"""
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
        # Coin flip triggers
        self.add_trigger("подбрось монету")
        self.add_trigger("подбрось монетку")
        self.add_trigger("брось монету")
        self.add_trigger("брось монетку")
        self.add_trigger("монетка")
        self.add_trigger("flip coin")
        self.add_trigger("coin flip")
        
        # Dice roll triggers
        self.add_trigger("подбрось кубик")
        self.add_trigger("брось кубик")
        self.add_trigger("подбрось кость")
        self.add_trigger("брось кость")
        self.add_trigger("кубик")
        self.add_trigger("roll dice")
        self.add_trigger("dice roll")
        
        # Random number triggers
        self.add_trigger("случайное число")
        self.add_trigger("random number")
        
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
        
    # BaseCommandPlugin interface - existing voice functionality
    async def _handle_command_impl(self, command: str, context: Context) -> CommandResult:
        """Handle random commands"""
        command_lower = command.lower().strip()
        
        # Add small delay to simulate async operation
        await asyncio.sleep(0.05)
        
        # Determine if this is Russian or English command
        is_russian = any(word in command_lower for word in ["подбрось", "брось", "монет", "кубик", "кость", "случайное"])
        
        if self._is_coin_command(command_lower):
            return await self._handle_coin_flip(is_russian)
        elif self._is_dice_command(command_lower):
            return await self._handle_dice_roll(is_russian)
        elif any(trigger in command_lower for trigger in ["случайное число", "random number"]):
            return await self._handle_random_number(is_russian)
        else:
            return CommandResult.error_result("Неизвестная команда генерации случайных чисел")
    
    # Random functionality methods (used by both voice and API)
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
    
    # WebAPIPlugin interface - unified API
    def get_router(self) -> Optional[Any]:
        """Get FastAPI router with random endpoints"""
        if not self.is_api_available():
            return None
            
        try:
            from fastapi import APIRouter, HTTPException  # type: ignore
            from pydantic import BaseModel  # type: ignore
            
            router = APIRouter()
            
            # Request/Response models
            class RandomNumberRequest(BaseModel):
                min_val: int = 1
                max_val: int = 100
                language: str = "ru"
                
            class DiceRequest(BaseModel):
                sides: int = 6
                count: int = 1
                language: str = "ru"
                
            class ChoiceRequest(BaseModel):
                options: List[str]
                language: str = "ru"
                
            class CoinResponse(BaseModel):
                result: str
                result_text: str
                language: str
                
            class DiceResponse(BaseModel):
                rolls: List[int]
                total: int
                sides: int
                count: int
                result_text: str
                language: str
                
            class NumberResponse(BaseModel):
                number: int
                min_val: int
                max_val: int
                result_text: str
                language: str
                
            class ChoiceResponse(BaseModel):
                choice: str
                options: List[str]
                result_text: str
                language: str
            
            @router.post("/coin", response_model=CoinResponse)
            async def flip_coin(language: str = "ru"):
                """Flip a coin"""
                try:
                    result = self.flip_coin(language)
                    return CoinResponse(**result)
                except Exception as e:
                    raise HTTPException(500, f"Error flipping coin: {str(e)}")
            
            @router.post("/dice", response_model=DiceResponse)
            async def roll_dice(request: DiceRequest):
                """Roll dice"""
                try:
                    result = self.roll_dice(request.sides, request.count, request.language)
                    return DiceResponse(**result)
                except ValueError as e:
                    raise HTTPException(400, str(e))
                except Exception as e:
                    raise HTTPException(500, f"Error rolling dice: {str(e)}")
            
            @router.post("/number", response_model=NumberResponse)
            async def random_number(request: RandomNumberRequest):
                """Generate a random number"""
                try:
                    result = self.generate_random_number(request.min_val, request.max_val, request.language)
                    return NumberResponse(**result)
                except ValueError as e:
                    raise HTTPException(400, str(e))
                except Exception as e:
                    raise HTTPException(500, f"Error generating number: {str(e)}")
            
            @router.post("/choice", response_model=ChoiceResponse)
            async def random_choice(request: ChoiceRequest):
                """Choose randomly from options"""
                try:
                    result = self.random_choice(request.options, request.language)
                    return ChoiceResponse(**result)
                except ValueError as e:
                    raise HTTPException(400, str(e))
                except Exception as e:
                    raise HTTPException(500, f"Error making choice: {str(e)}")
            
            return router
            
        except ImportError:
            self.logger.warning("FastAPI not available for random web API")
            return None
    
    def get_api_prefix(self) -> str:
        """Get URL prefix for random API endpoints"""
        return "/random"
    
    def get_api_tags(self) -> list[str]:
        """Get OpenAPI tags for random endpoints"""
        return ["Random", "Games"]

    # Internal helper methods
    def _is_coin_command(self, command: str) -> bool:
        """Check if command is for coin flip"""
        coin_keywords = ["монет", "coin", "flip coin", "coin flip"]
        return any(keyword in command for keyword in coin_keywords)
        
    def _is_dice_command(self, command: str) -> bool:
        """Check if command is for dice roll"""
        dice_keywords = ["кубик", "кость", "dice", "roll dice", "dice roll"]
        return any(keyword in command for keyword in dice_keywords)
        
    async def _handle_coin_flip(self, is_russian: bool = True) -> CommandResult:
        """Handle coin flip request"""
        language = "ru" if is_russian else "en"
        result = self.flip_coin(language)
        
        self.logger.info(f"Coin flip result: {result['result_text']}")
        
        return CommandResult.success_result(
            response=result["result_text"],
            should_continue_listening=True
        )
        
    async def _handle_dice_roll(self, is_russian: bool = True) -> CommandResult:
        """Handle dice roll request"""
        language = "ru" if is_russian else "en"
        result = self.roll_dice(language=language)
        
        self.logger.info(f"Dice roll result: {result['result_text']}")
        
        return CommandResult.success_result(
            response=result["result_text"],
            should_continue_listening=True
        )
        
    async def _handle_random_number(self, is_russian: bool = True) -> CommandResult:
        """Handle random number request"""
        language = "ru" if is_russian else "en"
        result = self.generate_random_number(language=language)
        
        self.logger.info(f"Random number generated: {result['number']}")
        
        return CommandResult.success_result(
            response=result["result_text"],
            should_continue_listening=True
        ) 