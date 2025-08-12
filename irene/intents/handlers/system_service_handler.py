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
            "ubuntu": [],
            "alpine": [],
            "centos": [],
            "macos": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """System service handler supports all platforms"""
        return ["linux", "windows", "macos"]
        
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
        return await self.execute_with_donation_routing(intent, context)
        
    async def _handle_service_status(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Handle service status request"""
        # Simulate heartbeat update
        self._status_count += 1
        self._last_heartbeat = datetime.now()
        
        # Determine language
        language = self._get_language(intent, context)
        
        if language == "ru":
            status_text = f"""
🔧 Статус системы:
• Сервис: 🟢 Работает
• Пульсы: {self._status_count}
• Последний пульс: {self._last_heartbeat.strftime('%H:%M:%S')}
• Время работы: {self._get_uptime()}
            """.strip()
        else:
            status_text = f"""
🔧 System Status:
• Service: 🟢 Running
• Heartbeats: {self._status_count}
• Last heartbeat: {self._last_heartbeat.strftime('%H:%M:%S')}
• Uptime: {self._get_uptime()}
            """.strip()
        
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
        
        if language == "ru":
            stats_text = f"""
📊 Статистика сервиса:
• Всего пульсов: {self._status_count}
• Сервис работает: Да
• Фоновые задачи: 1
• Эффективность памяти: ✅ (async реализация)
• Не блокирует: ✅ (не блокирует основной поток)
• Использование ресурсов: Минимальное
            """.strip()
        else:
            stats_text = f"""
📊 Service Statistics:
• Total heartbeats: {self._status_count}
• Service running: Yes
• Background tasks: 1
• Memory efficient: ✅ (async implementation)
• Non-blocking: ✅ (doesn't block main thread)
• Resource usage: Minimal
            """.strip()
        
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
        
        if language == "ru":
            health_text = f"""
💚 Состояние системы:
• Общее состояние: {health_score}% здоровый
• Время работы: {self._get_uptime()}
• Последняя активность: {self._last_heartbeat.strftime('%H:%M:%S')}
• Проблемы: Не обнаружены
• Производительность: Оптимальная
            """.strip()
        else:
            health_text = f"""
💚 System Health:
• Overall health: {health_score}% healthy
• Uptime: {self._get_uptime()}
• Last activity: {self._last_heartbeat.strftime('%H:%M:%S')}
• Issues: None detected
• Performance: Optimal
            """.strip()
        
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
    

    
    def _get_uptime(self) -> str:
        """Get service uptime"""
        if not self._last_heartbeat:
            return "No heartbeats yet"
            
        # Calculate uptime based on start time
        uptime_seconds = (datetime.now() - self._start_time).total_seconds()
        
        if uptime_seconds < 60:
            return f"{int(uptime_seconds)} seconds"
        elif uptime_seconds < 3600:
            minutes = int(uptime_seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        else:
            hours = int(uptime_seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
            
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
