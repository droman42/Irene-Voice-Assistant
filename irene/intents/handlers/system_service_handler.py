"""
System Service Intent Handler - Service status and statistics

Replaces the AsyncServiceDemoPlugin with modern intent-based architecture.
Provides system service status and statistics information.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class SystemServiceIntentHandler(IntentHandler):
    """
    Handles system service intents - status checks and statistics.
    
    Features:
    - Service status information
    - Service statistics and metrics
    - System health information
    - Uptime tracking
    """
    
    def __init__(self):
        super().__init__()
        self._status_count = 0
        self._last_heartbeat = None
        self._start_time = datetime.now()

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """System service handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """System service handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """System service handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process system service intents"""
        if not self.has_donation():
            raise RuntimeError(f"SystemServiceIntentHandler: Missing JSON donation file - system_service_handler.json is required")
        
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
        """Execute system service intent"""
        # Use donation-driven routing exclusively
        try:
            return await self.execute_with_donation_routing(intent, context)
        except Exception as e:
            logger.error(f"System service intent execution failed: {e}")
            # Determine language for error response
            language = self._get_language(intent, context)
            error_text = self._get_template("general_error", language)
            
            return IntentResult(
                text=error_text,
                should_speak=True,
                success=False,
                error=str(e)
            )
        
    async def _handle_service_status(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle service status request"""
        # Simulate heartbeat update
        self._status_count += 1
        self._last_heartbeat = datetime.now()
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Format response using external template
        status_text = self._get_template(
            "service_status_info", 
            language,
            heartbeats=self._status_count,
            last_heartbeat=self._last_heartbeat.strftime('%H:%M:%S'),
            uptime=self._get_uptime(language)
        )
        
        self.logger.info(f"Service status requested - heartbeat #{self._status_count}")
        
        return IntentResult(
            text=status_text,
            should_speak=True,
            metadata={
                "status": "running",
                "heartbeats": self._status_count,
                "last_heartbeat": self._last_heartbeat.isoformat(),
                "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
                "language": language
            },
            success=True
        )
        
    async def _handle_service_stats(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle service statistics request"""
        # Simulate async data collection
        await asyncio.sleep(0.1)
        
        # Update heartbeat
        self._status_count += 1
        self._last_heartbeat = datetime.now()
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Format response using external template
        stats_text = self._get_template(
            "service_stats_info",
            language,
            total_heartbeats=self._status_count
        )
        
        self.logger.info(f"Service statistics requested - heartbeat #{self._status_count}")
        
        return IntentResult(
            text=stats_text,
            should_speak=True,
            metadata={
                "total_heartbeats": self._status_count,
                "service_running": True,
                "background_tasks": 1,
                "memory_efficient": True,
                "non_blocking": True,
                "resource_usage": "minimal",
                "language": language
            },
            success=True
        )
        
    async def _handle_service_health(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle service health check request"""
        # Simulate health check
        await asyncio.sleep(0.05)
        
        # Update heartbeat
        self._status_count += 1
        self._last_heartbeat = datetime.now()
        
        # Determine language
        language = self._get_language(intent, context)
        
        # Calculate health metrics
        uptime_seconds = (datetime.now() - self._start_time).total_seconds()
        health_score = min(100, int(95 + (self._status_count * 0.1)))  # Simulate improving health
        
        # Format response using external template
        health_text = self._get_template(
            "service_health_info",
            language,
            health_score=health_score,
            uptime=self._get_uptime(language),
            last_activity=self._last_heartbeat.strftime('%H:%M:%S')
        )
        
        self.logger.info(f"Service health check - score: {health_score}%")
        
        return IntentResult(
            text=health_text,
            should_speak=True,
            metadata={
                "health_score": health_score,
                "uptime_seconds": uptime_seconds,
                "last_activity": self._last_heartbeat.isoformat(),
                "issues_detected": 0,
                "performance": "optimal",
                "language": language
            },
            success=True
        )
    

    
    def _get_uptime(self, language: str = "ru") -> str:
        """Get service uptime using external templates with language support"""
        if not self._last_heartbeat:
            return self._get_template("uptime_no_heartbeats", language)
            
        # Calculate uptime based on start time
        uptime_seconds = (datetime.now() - self._start_time).total_seconds()
        
        if uptime_seconds < 60:
            return self._get_template("uptime_seconds", language, seconds=int(uptime_seconds))
        elif uptime_seconds < 3600:
            minutes = int(uptime_seconds // 60)
            # Handle pluralization based on language
            if language == "ru":
                plural_y = "ы" if minutes in [2, 3, 4] and minutes not in [12, 13, 14] else ""
                return self._get_template("uptime_minutes", language, minutes=minutes, plural_y=plural_y)
            else:
                plural_s = "s" if minutes != 1 else ""
                return self._get_template("uptime_minutes", language, minutes=minutes, plural_s=plural_s)
        else:
            hours = int(uptime_seconds // 3600)
            # Handle pluralization based on language
            if language == "ru":
                plural_ov = "ов" if hours > 4 or hours == 0 or hours in [11, 12, 13, 14] else ""
                return self._get_template("uptime_hours", language, hours=hours, plural_ov=plural_ov)
            else:
                plural_s = "s" if hours != 1 else ""
                return self._get_template("uptime_hours", language, hours=hours, plural_s=plural_s)
            
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
                f"SystemServiceIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - system service templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("system_service", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"SystemServiceIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/system_service/{language}/status_messages.yaml. "
                f"This is a fatal error - all system service templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"SystemServiceIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/system_service/{language}/status_messages.yaml for correct placeholders."
            )
