"""
System Intent Handler - Essential system commands for Intent System

Provides system control and information commands.
Adapted from core_commands.py for the new intent architecture.
"""

import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Type, TYPE_CHECKING
from ...__version__ import __version__

from .base import IntentHandler
from ..models import Intent, IntentResult, UnifiedConversationContext

if TYPE_CHECKING:
    from pydantic import BaseModel

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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.start_time = time.time()
        
        # Configuration injection via Pydantic SystemHandlerConfig
        if config:
            self.config = config
            self.allow_shutdown = config.get("allow_shutdown", False)
            self.allow_restart = config.get("allow_restart", False)
            self.info_detail_level = config.get("info_detail_level", "basic")
            logger.info(f"SystemIntentHandler initialized with config: allow_shutdown={self.allow_shutdown}, allow_restart={self.allow_restart}, info_detail_level={self.info_detail_level}")
        else:
            # Fallback defaults (should not be used in production with proper config)
            self.config = {
                "allow_shutdown": False,
                "allow_restart": False,
                "info_detail_level": "basic"
            }
            self.allow_shutdown = False
            self.allow_restart = False
            self.info_detail_level = "basic"
            logger.warning("SystemIntentHandler initialized without configuration - using fallback defaults")

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
    
    # Configuration metadata methods
    @classmethod
    def get_config_schema(cls) -> Type["BaseModel"]:
        """Return configuration schema for system handler"""
        from ...config.models import SystemHandlerConfig
        return SystemHandlerConfig
    
    @classmethod
    def get_config_defaults(cls) -> Dict[str, Any]:
        """Return default configuration values matching TOML"""
        return {
            "allow_shutdown": False,     # matches config-master.toml line 445
            "allow_restart": False,      # matches config-master.toml line 446
            "info_detail_level": "basic" # matches config-master.toml line 447
        }
        
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
    
    async def execute(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Execute system intent"""
        try:
            # Use language from context (detected by NLU)
            language = context.language or "ru"
            
            if intent.action == "help" or intent.name == "system.help":
                return await self._handle_help_request(intent, context)
            elif intent.action == "status" or intent.name == "system.status":
                return await self._handle_status_request(intent, context)
            elif intent.action == "version" or intent.name == "system.version":
                return await self._handle_version_request(intent, context)
            elif intent.action == "info" or intent.name == "system.info":
                return await self._handle_info_request(intent, context)
            elif intent.action == "language_switch" or intent.name == "system.language_switch":
                return await self._handle_language_switch(intent, context)
            else:
                # Default: provide general system information
                return await self._handle_general_info(intent, context)
                
        except Exception as e:
            logger.error(f"System intent execution failed: {e}")
            language = context.language or "ru"
            return IntentResult(
                text="Извините, произошла ошибка при выполнении системной команды." if language == "ru" else "Sorry, there was an error executing the system command.",
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
                f"not found in assets/templates/system/{language}/system_messages.yaml. "
                f"This is a fatal error - all system templates must be externalized."
            )
        
        # Format template with provided arguments
        try:
            return template_content.format(**format_args)
        except KeyError as e:
            raise RuntimeError(
                f"SystemIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                f"Check assets/templates/system/{language}/system_messages.yaml for correct placeholders."
            )
    
    async def _handle_help_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle help/assistance request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
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
    
    async def _handle_status_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle system status request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
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
        version = __version__
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
    
    async def _handle_version_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle version information request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        version = __version__
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
    
    async def _handle_info_request(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle general information request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        session_stats = self._get_session_stats(context)
        version = __version__
        
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
    
    async def _handle_general_info(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle general system information request"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        version = __version__
        info_text = self._get_template("general", language, version=version)
        
        return IntentResult(
            text=info_text,
            should_speak=True,
            metadata={
                "type": "general_info",
                "language": language
            }
        )
    
    async def _handle_language_switch(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """
        Handle language switching requests.
        
        Phase 3: Language switching support implementation.
        """
        target_language = intent.entities.get('language', 'ru')
        
        # Validate language
        if target_language not in ['ru', 'en']:
            return IntentResult(
                text="Поддерживаются только русский и английский языки." if context.language == 'ru' 
                     else "Only Russian and English languages are supported.",
                should_speak=True
            )
        
        # Update context and preferences using context manager
        try:
            # Get context manager from core to update language preference
            from ...core.engine import get_core
            core = get_core()
            if core and hasattr(core, 'context_manager'):
                await core.context_manager.update_language_preference(context.session_id, target_language)
            else:
                # Fallback: update context directly
                context.language = target_language
                context.user_preferences['language'] = target_language
        except Exception as e:
            logger.warning(f"Could not access context manager for language update: {e}")
            # Fallback: update context directly
            context.language = target_language
            context.user_preferences['language'] = target_language
        
        response = "Язык изменён на русский." if target_language == 'ru' else "Language changed to English."
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={'language_changed': target_language},
            success=True
        )
    
    def _get_session_stats(self, context: UnifiedConversationContext) -> Dict[str, Any]:
        """Get session statistics"""
        return {
            "session_id": context.session_id,
            "created_at": context.created_at,
            "last_updated": context.last_updated,
            "message_count": len(context.history),
            "session_duration": time.time() - context.created_at
        }
    
 