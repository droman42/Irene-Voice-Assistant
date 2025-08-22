"""
System Intent Handler - Essential system commands for Intent System

Provides system control and information commands.
Adapted from core_commands.py for the new intent architecture.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from .base import IntentHandler
from ..models import Intent, IntentResult, ConversationContext

logger = logging.getLogger(__name__)


class SystemIntentHandler(IntentHandler):
    """
    Handles system control and status intents.
    
    Features:
    - System shutdown/restart
    - Status queries
    - Volume control
    - Time/date queries
    """
    
    def __init__(self):
        super().__init__()
        self.start_time = time.time()

    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """System handler needs no external dependencies - pure Python logic"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """System handler has no system dependencies - pure Python logic"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """System handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process system intents"""
        if not self.has_donation():
            raise RuntimeError(f"SystemIntentHandler: Missing JSON donation file - system.json is required")
        
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
        """Execute system intent"""
        try:
            # Determine language preference
            language = self._detect_language(intent.raw_text, context)
            
            if intent.action == "help" or intent.name == "system.help":
                return await self._handle_help_request(intent, context, language)
            elif intent.action == "status" or intent.name == "system.status":
                return await self._handle_status_request(intent, context, language)
            elif intent.action == "version" or intent.name == "system.version":
                return await self._handle_version_request(intent, context, language)
            elif intent.action == "info" or intent.name == "system.info":
                return await self._handle_info_request(intent, context, language)
            else:
                # Default: provide general system information
                return await self._handle_general_info(intent, context, language)
                
        except Exception as e:
            logger.error(f"System intent execution failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка при выполнении системной команды." if self._detect_language(intent.raw_text, context) == "ru" else "Sorry, there was an error executing the system command.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def is_available(self) -> bool:
        """System commands are always available"""
        return True
    
    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"SystemIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - system templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("system", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"SystemIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/system/{language}/{template_name}.md. "
                f"This is a fatal error - all system templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"SystemIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/system/{language}/{template_name}.md for correct placeholders."
            )
    
    def _detect_language(self, text: str, context: ConversationContext) -> str:
        """Detect language from text or context"""
        text_lower = text.lower()
        
        english_indicators = ["help", "status", "version", "info", "system"]
        russian_indicators = ["помощь", "справка", "статус", "версия", "система", "информация"]
        
        english_count = sum(1 for word in english_indicators if word in text_lower)
        russian_count = sum(1 for word in russian_indicators if word in text_lower)
        
        # Check context metadata for language preference
        if hasattr(context, 'metadata') and 'language' in context.metadata:
            return context.metadata['language']
        
        # Default to Russian if unclear
        return "en" if english_count > russian_count else "ru"
    
    async def _handle_help_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle help/assistance request"""
        help_text = self._get_template("help", language)
        
        return IntentResult(
            text=help_text,
            should_speak=True,
            metadata={
                "help_type": "general",
                "language": language,
                "capabilities_listed": True
            }
        )
    
    async def _handle_status_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle system status request"""
        uptime_seconds = time.time() - self.start_time
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        
        if language == "en":
            if uptime_hours > 0:
                uptime_str = f"{uptime_hours} hours and {uptime_minutes} minutes"
            else:
                uptime_str = f"{uptime_minutes} minutes"
        else:
            if uptime_hours > 0:
                uptime_str = f"{uptime_hours} часов и {uptime_minutes} минут"
            else:
                uptime_str = f"{uptime_minutes} минут"
        
        # TODO #15: Move hardcoded version to TOML configuration (not JSON donations)
        version = "13.0.0"  # Should come from config
        status_text = self._get_template("status", language, uptime_str=uptime_str, version=version)
        
        return IntentResult(
            text=status_text,
            should_speak=True,
            metadata={
                "status": "running",
                "uptime_seconds": uptime_seconds,
                "version": version,
                "language": language
            }
        )
    
    async def _handle_version_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle version information request"""
        version = "13.0.0"  # TODO: Should come from config
        version_text = self._get_template("version", language, version=version)
        
        return IntentResult(
            text=version_text,
            should_speak=True,
            metadata={
                "version": version,
                "architecture": "intent-based",
                "language": language
            }
        )
    
    async def _handle_info_request(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle general information request"""
        session_stats = self._get_session_stats(context)
        version = "13.0.0"  # TODO: Should come from config
        
        info_text = self._get_template(
            "info", 
            language,
            version=version,
            session_start_time=datetime.fromtimestamp(context.created_at).strftime('%H:%M'),
            message_count=len(context.history),
            session_id=context.session_id
        )
        
        return IntentResult(
            text=info_text,
            should_speak=True,
            metadata={
                "session_info": session_stats,
                "language": language
            }
        )
    
    async def _handle_general_info(self, intent: Intent, context: ConversationContext, language: str) -> IntentResult:
        """Handle general system information request"""
        version = "13.0.0"  # TODO: Should come from config
        info_text = self._get_template("general", language, version=version)
        
        return IntentResult(
            text=info_text,
            should_speak=True,
            metadata={
                "type": "general_info",
                "language": language
            }
        )
    
    def _get_session_stats(self, context: ConversationContext) -> Dict[str, Any]:
        """Get session statistics"""
        return {
            "session_id": context.session_id,
            "created_at": context.created_at,
            "last_updated": context.last_updated,
            "message_count": len(context.history),
            "session_duration": time.time() - context.created_at
        }
    
 