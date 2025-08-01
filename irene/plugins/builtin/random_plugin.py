"""
Random Plugin - Coin flips and dice rolls

Replaces legacy plugin_random.py with modern async architecture.
Provides random number generation, coin flips, and dice rolls.
"""

import random
import asyncio
from typing import List

from ...core.context import Context
from ...core.commands import CommandResult
from ..base import BaseCommandPlugin


class RandomPlugin(BaseCommandPlugin):
    """
    Random plugin providing coin flips, dice rolls, and random numbers.
    
    Features:
    - Coin flip (heads/tails)
    - Dice roll (1-6)
    - Random number generation
    - Russian language support
    """
    
    @property
    def name(self) -> str:
        return "random"
        
    @property
    def version(self) -> str:
        return "1.0.0"
        
    @property
    def description(self) -> str:
        return "Random numbers, coin flips, and dice rolls"
        
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
        if is_russian:
            result = random.choice(self.coin_results_ru)
        else:
            result = random.choice(self.coin_results_en)
            
        self.logger.info(f"Coin flip result: {result}")
        
        return CommandResult.success_result(
            response=result,
            should_continue_listening=True
        )
        
    async def _handle_dice_roll(self, is_russian: bool = True) -> CommandResult:
        """Handle dice roll request"""
        if is_russian:
            result = random.choice(self.dice_results_ru)
        else:
            result = random.choice(self.dice_results_en)
            
        self.logger.info(f"Dice roll result: {result}")
        
        return CommandResult.success_result(
            response=result,
            should_continue_listening=True
        )
        
    async def _handle_random_number(self, is_russian: bool = True) -> CommandResult:
        """Handle random number request"""
        # Generate random number between 1 and 100
        number = random.randint(1, 100)
        
        if is_russian:
            result = f"Случайное число: {number}"
        else:
            result = f"Random number: {number}"
            
        self.logger.info(f"Random number generated: {number}")
        
        return CommandResult.success_result(
            response=result,
            should_continue_listening=True
        ) 