"""
Timer Intent Handler - Timer operations for Intent System

Handles timer creation, management, and cancellation.
Adapted from timer_plugin.py for the new intent architecture.
"""

import asyncio
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class TimerIntentHandler(IntentHandler):
    """
    Handles timer-related intents with natural language parsing.
    
    Features:
    - Natural language time parsing
    - Multiple concurrent timers
    - Timer management and cancellation
    - Context-aware timer storage
    - Async timer execution
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.active_timers: Dict[str, Dict[str, Any]] = {}
        self.timer_counter = 0
        
        # Phase 5: Configuration injection via Pydantic TimerHandlerConfig
        if config:
            self.config = config
            self.min_seconds = config.get("min_seconds", 1)
            self.max_seconds = config.get("max_seconds", 86400)
            self.unit_multipliers = config.get("unit_multipliers", {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400})
            logger.info(f"TimerIntentHandler initialized with config: min_seconds={self.min_seconds}, max_seconds={self.max_seconds}")
        else:
            # Fallback defaults (should not be used in production with proper config)
            self.config = {
                "min_seconds": 1,
                "max_seconds": 86400,
                "unit_multipliers": {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}
            }
            self.min_seconds = 1
            self.max_seconds = 86400
            self.unit_multipliers = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}
            logger.warning("TimerIntentHandler initialized without configuration - using fallback defaults")

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Timer handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Timer handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Timer handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process timer intents"""
        if not self.has_donation():
            raise RuntimeError(f"TimerIntentHandler: Missing JSON donation file - timer.json is required")
        
        # Use JSON donation patterns exclusively
        donation = self.get_donation()
        
        # Check domain patterns (fallback)
        if intent.domain == "timer":
            return True
        
        # Check intent name patterns
        if hasattr(donation, 'intent_name_patterns') and intent.name in donation.intent_name_patterns:
            return True
        
        # Check action patterns
        if hasattr(donation, 'action_patterns') and intent.action in donation.action_patterns:
            return True
        
        return False
    
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Execute timer intent"""
        try:
            if intent.action == "set" or intent.name == "timer.set":
                return await self._handle_set_timer(intent, context)
            elif intent.action == "cancel" or intent.name == "timer.cancel":
                return await self._handle_cancel_timer(intent, context)
            elif intent.action == "list" or intent.name == "timer.list":
                return await self._handle_list_timers(intent, context)
            elif intent.action == "status" or intent.name == "timer.status":
                return await self._handle_timer_status(intent, context)
            else:
                # Default: try to set timer from natural language
                return await self._handle_set_timer(intent, context)
                
        except Exception as e:
            logger.error(f"Timer intent execution failed: {e}")
            # Determine language for error response
            language = self._get_language(intent, context)
            error_text = self._get_template("general_error", language)
            
            return IntentResult(
                text=error_text,
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def is_available(self) -> bool:
        """Timer functionality is always available"""
        return True
    
    def _get_language(self, intent: Intent, context: ConversationContext) -> str:
        """Determine language from intent or context"""
        # Check intent entities first
        if hasattr(intent, 'entities') and "language" in intent.entities:
            return intent.entities["language"]
        
        # Check if text contains Russian characters
        if hasattr(intent, 'raw_text') and any(char in intent.raw_text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"):
            return "ru"
        elif hasattr(intent, 'text') and any(char in intent.text for char in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"):
            return "ru"
        
        # Default to Russian
        return "ru"
        
    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"TimerIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - timer templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("timer", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"TimerIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/timer/{language}/status_messages.yaml. "
                f"This is a fatal error - all timer templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"TimerIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/timer/{language}/status_messages.yaml for correct placeholders."
            )
    
    async def _handle_set_timer(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle timer creation intent with fire-and-forget action execution"""
        # Extract timer parameters from intent entities or text
        duration = intent.entities.get('duration')
        unit = intent.entities.get('unit', 'seconds')
        message = intent.entities.get('message', self._get_template("timer_completed_default", "ru"))
        
        # If no duration in entities, try to parse from text
        if not duration:
            duration, unit, message = self._parse_timer_from_text(intent.raw_text)
        
        if not duration:
            language = self._get_language(intent, context)
            error_text = self._get_template("timer_duration_parse_error", language)
            return IntentResult(
                text=error_text,
                should_speak=True,
                success=False
            )
        
        try:
            # Convert to seconds
            duration_seconds = self._convert_to_seconds(int(duration), unit)
            
            # Generate timer ID for action tracking
            self.timer_counter += 1
            timer_id = f"timer_{self.timer_counter}"
            
            # Use fire-and-forget action execution for timer creation
            action_metadata = await self.execute_fire_and_forget_action(
                self._create_timer_action,
                action_name=timer_id,
                domain="timers",
                duration_seconds=duration_seconds,
                message=message,
                session_id=context.session_id,
                timer_id=timer_id
            )
            
            # Format response using template
            language = self._get_language(intent, context)
            time_str = self._format_duration(duration_seconds)
            response = self._get_template("timer_set_success", language, time_str=time_str, message=message)
            
            return self.create_action_result(
                response_text=response,
                action_name=timer_id,
                domain="timers",
                should_speak=True,
                action_metadata=action_metadata
            )
            
        except ValueError as e:
            language = self._get_language(intent, context)
            error_text = self._get_template("timer_set_error", language, error=str(e))
            return IntentResult(
                text=error_text,
                should_speak=True,
                success=False
            )
    
    async def _handle_cancel_timer(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle timer cancellation intent with stop command disambiguation"""
        # Check for stop commands first
        stop_info = self.parse_stop_command(intent)
        if stop_info and stop_info.get("is_stop_command"):
            return await self._handle_stop_command(stop_info, context)
        
        timer_id = intent.entities.get('timer_id')
        
        # If no specific timer ID, cancel all timers for this session
        if not timer_id:
            session_timers = [tid for tid, timer in self.active_timers.items() 
                            if timer['session_id'] == context.session_id]
            
            if not session_timers:
                language = self._get_language(intent, context)
                error_text = self._get_template("timer_no_active", language)
                return IntentResult(
                    text=error_text,
                    should_speak=True
                )
            
            # Use fire-and-forget action for cancelling multiple timers
            action_metadata = await self.execute_fire_and_forget_action(
                self._cancel_multiple_timers_action,
                action_name="cancel_all_timers",
                domain="timers",
                session_timers=session_timers,
                session_id=context.session_id
            )
            
            language = self._get_language(intent, context)
            response_text = self._get_template("timer_cancel_all_success", language, count=len(session_timers))
            return self.create_action_result(
                response_text=response_text,
                action_name="cancel_all_timers",
                domain="timers",
                should_speak=True,
                action_metadata=action_metadata
            )
        
        # Cancel specific timer with fire-and-forget action
        if timer_id not in self.active_timers:
            language = self._get_language(intent, context)
            error_text = self._get_template("timer_cancel_not_found", language, timer_id=timer_id)
            return IntentResult(
                text=error_text,
                should_speak=True,
                success=False
            )
        
        action_metadata = await self.execute_fire_and_forget_action(
            self._cancel_single_timer_action,
            action_name=f"cancel_{timer_id}",
            domain="timers",
            timer_id=timer_id
        )
        
        language = self._get_language(intent, context)
        response_text = self._get_template("timer_cancel_success", language, timer_id=timer_id)
        return self.create_action_result(
            response_text=response_text,
            action_name=f"cancel_{timer_id}",
            domain="timers",
            should_speak=True,
            action_metadata=action_metadata
        )
    
    async def _handle_stop_command(self, stop_info: dict, context: ConversationContext) -> IntentResult:
        """Handle stop commands for timer actions with disambiguation"""
        target_domains = stop_info.get("target_domains", [])
        
        # Check if stop command targets timers domain
        if not target_domains or "timer" in target_domains or "timers" in target_domains:
            session_timers = [tid for tid, timer in self.active_timers.items() 
                            if timer['session_id'] == context.session_id]
            
            if not session_timers:
                # Use language from context (detected by NLU)
                language = context.language or "ru"
                response_text = self._get_template("stop_no_timers", language)
                return IntentResult(
                    text=response_text,
                    should_speak=True,
                    success=True
                )
            
            # Cancel all active timers for this session
            action_metadata = await self.execute_fire_and_forget_action(
                self._cancel_multiple_timers_action,
                action_name="stop_all_timers",
                domain="timers",
                session_timers=session_timers,
                session_id=context.session_id
            )
            
            language = context.language or "ru"
            response_text = self._get_template("stop_all_timers", language, count=len(session_timers))
            return self.create_action_result(
                response_text=response_text,
                action_name="stop_all_timers",
                domain="timers",
                should_speak=True,
                action_metadata=action_metadata
            )
        
        # Not targeting timers domain
        language = context.language or "ru"
        response_text = self._get_template("stop_not_timer_domain", language)
        return IntentResult(
            text=response_text,
            should_speak=False,
            success=True
        )
    
    async def _handle_list_timers(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle list timers intent"""
        session_timers = [(tid, timer) for tid, timer in self.active_timers.items() 
                        if timer['session_id'] == context.session_id]
        
        if not session_timers:
            language = self._get_language(intent, context)
            response_text = self._get_template("timer_list_empty", language)
            return IntentResult(
                text=response_text,
                should_speak=True
            )
        
        timer_list = []
        for timer_id, timer in session_timers:
            remaining = timer['end_time'] - datetime.now().timestamp()
            if remaining > 0:
                time_str = self._format_duration(int(remaining))
                timer_list.append(f"Таймер {timer_id}: {time_str} ({timer['message']})")
        
        if not timer_list:
            language = self._get_language(intent, context)
            response_text = self._get_template("timer_list_expired", language)
            return IntentResult(
                text=response_text,
                should_speak=True
            )
        
        language = self._get_language(intent, context)
        timer_list_str = "\n".join(timer_list)
        response = self._get_template("timer_list_active", language, count=len(timer_list), timer_list=timer_list_str)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"active_timer_count": len(timer_list)}
        )
    
    async def _handle_timer_status(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle timer status inquiry intent"""
        session_timers = [(tid, timer) for tid, timer in self.active_timers.items() 
                        if timer['session_id'] == context.session_id]
        
        if not session_timers:
            language = self._get_language(intent, context)
            response_text = self._get_template("timer_no_active", language)
            return IntentResult(
                text=response_text,
                should_speak=True
            )
        
        # Get status of the most recent timer
        latest_timer = max(session_timers, key=lambda x: x[1]['start_time'])
        timer_id, timer = latest_timer
        
        language = self._get_language(intent, context)
        remaining = timer['end_time'] - datetime.now().timestamp()
        if remaining <= 0:
            response = self._get_template("timer_status_expired", language, timer_id=timer_id)
        else:
            time_str = self._format_duration(int(remaining))
            response = self._get_template("timer_status_remaining", language, timer_id=timer_id, time_str=time_str)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={
                "timer_id": timer_id,
                "remaining_seconds": max(0, int(remaining))
            }
        )
    
    def _parse_timer_from_text(self, text: str) -> tuple[Optional[int], str, str]:
        """Parse timer parameters from natural language text"""
        text_lower = text.lower()
        
        # TODO: These parsing patterns are now migrated to timer.json duration parameter extraction_patterns
        # Common patterns for timer duration
        patterns = [
            r"(\d+)\s*(секунд|сек)",
            r"(\d+)\s*(минут|мин)",
            r"(\d+)\s*(час|часа|часов)",
            r"на\s+(\d+)\s*(секунд|сек|минут|мин|час|часа|часов)",
            r"через\s+(\d+)\s*(секунд|сек|минут|мин|час|часа|часов)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                duration = int(match.group(1))
                unit_text = match.group(2)
                
                # Map Russian units to standard units
                if unit_text in ['секунд', 'сек']:
                    unit = 'seconds'
                elif unit_text in ['минут', 'мин']:
                    unit = 'minutes'
                elif unit_text in ['час', 'часа', 'часов']:
                    unit = 'hours'
                else:
                    unit = 'seconds'
                
                # Try to extract message
                message = self._extract_timer_message(text)
                
                return duration, unit, message
        
        return None, 'seconds', self._get_template("timer_completed_default", "ru")
    
    def _extract_timer_message(self, text: str) -> str:
        """Extract custom message from timer text"""
        # TODO: These message patterns are now migrated to timer.json message parameter extraction_patterns
        # Look for message patterns
        message_patterns = [
            r"сообщение[:\s]+(.*)",
            r"напомни[:\s]+(.*)",
            r"скажи[:\s]+(.*)",
        ]
        
        for pattern in message_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1).strip()
        
        # Use template default value
        return self._get_template("timer_completed_default", "ru")
    
    def _convert_to_seconds(self, duration: int, unit: str) -> int:
        """Convert duration to seconds using injected configuration"""
        # Phase 5: Use injected unit multipliers from configuration
        multiplier = self.unit_multipliers.get(unit, 1)
        total_seconds = duration * multiplier
        
        # Use configured limits
        if total_seconds < self.min_seconds:
            raise ValueError(f"Время таймера слишком мало (минимум {self.min_seconds} секунд)")
        if total_seconds > self.max_seconds:
            max_hours = self.max_seconds // 3600
            raise ValueError(f"Время таймера слишком велико (максимум {max_hours} часов)")
        
        return total_seconds
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds} сек"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            if remaining_seconds == 0:
                return f"{minutes} мин"
            else:
                return f"{minutes} мин {remaining_seconds} сек"
        else:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            if remaining_minutes == 0:
                return f"{hours} ч"
            else:
                return f"{hours} ч {remaining_minutes} мин"
    
    async def _create_timer_action(self, duration_seconds: int, message: str, session_id: str, timer_id: str) -> str:
        """Fire-and-forget timer creation action"""
        start_time = datetime.now().timestamp()
        end_time = start_time + duration_seconds
        
        timer_info = {
            "id": timer_id,
            "duration": duration_seconds,
            "message": message,
            "session_id": session_id,
            "start_time": start_time,
            "end_time": end_time,
            "task": None
        }
        
        # Create async task for timer completion with fire-and-forget notification
        async def timer_callback():
            try:
                await asyncio.sleep(duration_seconds)
                # Fire-and-forget completion notification
                await self.execute_fire_and_forget_action(
                    self._timer_completion_notification,
                    action_name=f"{timer_id}_completion",
                    domain="timers",
                    timer_id=timer_id,
                    message=message,
                    session_id=session_id
                )
                await self._timer_completed(timer_id)
            except asyncio.CancelledError:
                logger.debug(f"Timer {timer_id} was cancelled")
                # Remove from active actions in context
                # TODO: Integrate with context manager to remove cancelled action
        
        timer_info["task"] = asyncio.create_task(timer_callback())
        self.active_timers[timer_id] = timer_info
        
        logger.info(f"Created timer {timer_id} for {duration_seconds} seconds")
        return timer_id
    
    async def _create_timer(self, duration_seconds: int, message: str, session_id: str) -> str:
        """Legacy create timer method - kept for backward compatibility"""
        self.timer_counter += 1
        timer_id = f"timer_{self.timer_counter}"
        return await self._create_timer_action(duration_seconds, message, session_id, timer_id)
    
    async def _cancel_timer(self, timer_id: str) -> bool:
        """Cancel a specific timer"""
        if timer_id not in self.active_timers:
            return False
        
        timer = self.active_timers[timer_id]
        if timer["task"]:
            timer["task"].cancel()
        
        del self.active_timers[timer_id]
        logger.info(f"Cancelled timer {timer_id}")
        return True
    
    async def _timer_completion_notification(self, timer_id: str, message: str, session_id: str) -> bool:
        """Fire-and-forget timer completion notification"""
        # TODO: Integrate with TTS/output system to actually speak the completion
        # For now, we log and could send through notification channels
        logger.info(f"🔔 Timer {timer_id} completed: {message}")
        
        # In a real implementation, this would:
        # 1. Send TTS notification: "Timer completed: {message}"
        # 2. Play completion sound
        # 3. Send push notification if supported
        # 4. Update UI if web interface is connected
        
        # Simulate notification delivery
        await asyncio.sleep(0.1)  # Simulate notification processing time
        return True
    
    async def _timer_completed(self, timer_id: str):
        """Handle timer completion cleanup"""
        if timer_id not in self.active_timers:
            return
        
        timer = self.active_timers[timer_id]
        message = timer["message"]
        
        logger.info(f"Timer {timer_id} completed and cleaned up: {message}")
        
        # Clean up completed timer
        del self.active_timers[timer_id]
    

    
    async def _cancel_single_timer_action(self, timer_id: str) -> bool:
        """Fire-and-forget single timer cancellation action"""
        if timer_id not in self.active_timers:
            logger.warning(f"Timer {timer_id} not found for cancellation")
            return False
        
        timer = self.active_timers[timer_id]
        if timer["task"]:
            timer["task"].cancel()
        
        del self.active_timers[timer_id]
        logger.info(f"🛑 Timer {timer_id} cancelled via fire-and-forget action")
        return True
    
    async def _cancel_multiple_timers_action(self, session_timers: list, session_id: str) -> int:
        """Fire-and-forget multiple timer cancellation action"""
        cancelled_count = 0
        for timer_id in session_timers:
            if await self._cancel_single_timer_action(timer_id):
                cancelled_count += 1
        
        logger.info(f"🛑 Cancelled {cancelled_count} timers for session {session_id} via fire-and-forget action")
        return cancelled_count

    async def cleanup(self) -> None:
        """Clean up all active timers"""
        for timer_id in list(self.active_timers.keys()):
            await self._cancel_timer(timer_id)
        logger.info("All timers cleaned up") 