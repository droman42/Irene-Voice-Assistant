#!/usr/bin/env python3
"""
Conversation Plugin Demo

Demonstrates the ConversationPlugin functionality including:
- Starting conversations via voice commands
- Multi-turn conversations with state management
- Different conversation modes (chat vs reference)
- API endpoints for conversation management
- Session persistence and cleanup

This replaces the functionality from legacy plugin_boltalka_vsegpt.py
with modern v13 architecture using UniversalLLMPlugin as backend.
"""

import asyncio
import json
import logging
from pathlib import Path
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.engine import AsyncVACore
from core.context import Context
from core.commands import CommandResult
from config.models import CoreConfig as Config
from plugins.builtin.conversation_plugin import ConversationPlugin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConversationDemoRunner:
    """Demo runner for ConversationPlugin"""
    
    def __init__(self):
        self.core = None
        self.conversation_plugin = None
    
    def _ensure_plugin(self) -> ConversationPlugin:
        """Ensure plugin is initialized and return it"""
        if not self.conversation_plugin:
            raise RuntimeError("ConversationPlugin not initialized")
        return self.conversation_plugin
    
    async def setup_core(self) -> None:
        """Set up AsyncVACore with ConversationPlugin"""
        logger.info("🚀 Setting up AsyncVACore with ConversationPlugin...")
        
        # Create minimal config
        config = Config()
        
        # Initialize core
        self.core = AsyncVACore(config)
        await self.core.start()
        
        # Load conversation plugin
        self.conversation_plugin = ConversationPlugin()
        await self.conversation_plugin.initialize(self.core)
        
        # Register with plugin manager (simulate registration)
        self.core.plugin_manager._plugins["conversation"] = self.conversation_plugin
        
        logger.info("✅ Core and ConversationPlugin initialized")
    
    async def demo_voice_commands(self) -> None:
        """Demonstrate voice command interface"""
        logger.info("\n" + "="*60)
        logger.info("🎤 VOICE COMMAND DEMO")
        logger.info("="*60)
        
        # Create context for commands
        context = Context()
        
        # Demo commands
        commands = [
            "поболтаем как дела?",
            "хорошо, а у тебя?", 
            "новый диалог",
            "расскажи про погоду",
            "справка что такое Python?",
            "сохрани диалог",
            "пока"
        ]
        
        for i, command in enumerate(commands, 1):
            logger.info(f"\n--- Command {i}: '{command}' ---")
            
            try:
                # Check if plugin can handle
                if self.conversation_plugin:
                    can_handle = await self.conversation_plugin.can_handle(command, context)
                    logger.info(f"Can handle: {can_handle}")
                    
                    if can_handle:
                        # Handle command
                        result = await self.conversation_plugin.handle_command(command, context)
                    
                    if result.success:
                        logger.info(f"✅ Response: {result.response}")
                        if result.metadata:
                            logger.info(f"📊 Metadata: {result.metadata}")
                    else:
                        logger.error(f"❌ Error: {result.error}")
                else:
                    logger.info("⏭️ Command not handled by ConversationPlugin")
                
                # Simulate delay between commands
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Error processing command: {e}")
    
    async def demo_session_management(self) -> None:
        """Demonstrate session management features"""
        logger.info("\n" + "="*60)
        logger.info("📚 SESSION MANAGEMENT DEMO")
        logger.info("="*60)
        
        plugin = self._ensure_plugin()
        
        # Show initial state
        logger.info(f"Initial sessions: {len(plugin.sessions)}")
        logger.info(f"Active session: {plugin.active_context_session}")
        
        # Create multiple sessions programmatically
        from plugins.builtin.conversation_plugin import ConversationSession
        
        session1 = ConversationSession("demo_1", "chat", "Ты дружелюбный помощник")
        session1.add_message("user", "Привет!")
        session1.add_message("assistant", "Привет! Как дела?")
        
        session2 = ConversationSession("demo_2", "reference", "Ты справочный помощник")
        session2.add_message("user", "Что такое ИИ?")
        session2.add_message("assistant", "Искусственный интеллект...")
        
        plugin.sessions["demo_1"] = session1
        plugin.sessions["demo_2"] = session2
        
        logger.info(f"Created sessions: {list(plugin.sessions.keys())}")
        
        # Show session details
        for session_id, session in plugin.sessions.items():
            logger.info(f"\n📄 Session {session_id}:")
            logger.info(f"  Type: {session.conversation_type}")
            logger.info(f"  Messages: {len(session.messages)}")
            logger.info(f"  Last activity: {session.last_activity}")
            
            # Show conversation history
            for msg in session.messages:
                role_icon = "🤖" if msg["role"] == "assistant" else "👤" if msg["role"] == "user" else "⚙️"
                logger.info(f"  {role_icon} {msg['role']}: {msg['content'][:50]}...")
        
        # Test session cleanup
        logger.info(f"\n🧹 Testing session cleanup...")
        await plugin._cleanup_old_sessions()
        logger.info(f"Sessions after cleanup: {len(plugin.sessions)}")
        
        # Test saving
        logger.info(f"\n💾 Testing session saving...")
        for session in plugin.sessions.values():
            filepath = session.save_to_file(Path("models"))
            if filepath:
                logger.info(f"✅ Saved session to: {filepath}")
            else:
                logger.info(f"❌ Failed to save session")
    
    async def demo_api_endpoints(self) -> None:
        """Demonstrate REST API endpoints"""
        logger.info("\n" + "="*60)
        logger.info("🌐 API ENDPOINTS DEMO")
        logger.info("="*60)
        
        # Get router
        plugin = self._ensure_plugin()
        router = plugin.get_router()
        logger.info(f"✅ ConversationPlugin router created with {len(router.routes)} routes")
        
        # List available endpoints
        logger.info("\n📋 Available API endpoints:")
        for route in router.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                methods = ', '.join(route.methods) if route.methods else 'N/A'
                logger.info(f"  {methods} {route.path}")
        
        # Note: We can't easily test the actual FastAPI endpoints here without
        # setting up a full web server, but we can show they're available
        logger.info("\n💡 API Usage examples:")
        logger.info("  POST /start - Start new conversation")
        logger.info("  POST /{session_id}/message - Send message") 
        logger.info("  GET /{session_id}/history - Get conversation history")
        logger.info("  DELETE /{session_id} - End conversation")
        logger.info("  GET /sessions - List all sessions")
    
    async def demo_configuration(self) -> None:
        """Demonstrate configuration options"""
        logger.info("\n" + "="*60)
        logger.info("⚙️ CONFIGURATION DEMO")
        logger.info("="*60)
        
        plugin = self._ensure_plugin()
        
        logger.info("📋 Current configuration:")
        for key, value in plugin.config.items():
            logger.info(f"  {key}: {value}")
        
        # Show configuration integration
        logger.info(f"\n🔧 Configuration integration:")
        logger.info(f"  Chat model: {plugin.config['chat_model']}")
        logger.info(f"  Reference model: {plugin.config['reference_model']}")
        logger.info(f"  Session timeout: {plugin.config['session_timeout']} seconds")
        logger.info(f"  Max sessions: {plugin.config['max_sessions']}")
        
        # Show TOML configuration example
        toml_config = """
[plugins.conversation]
chat_system_prompt = "Ты - Ирина, голосовой помощник, помогающий человеку. Давай ответы кратко и по существу."
reference_system_prompt = "Ты помощник для получения точных фактов. Отвечай максимально кратко и точно на русском языке."
chat_model = "openai/gpt-4o-mini"
reference_model = "perplexity/latest-large-online" 
session_timeout = 1800
max_sessions = 50
"""
        
        logger.info(f"\n📄 Example TOML configuration:")
        logger.info(toml_config)
    
    async def demo_architecture_comparison(self) -> None:
        """Show architecture comparison with legacy plugin"""
        logger.info("\n" + "="*60)
        logger.info("🏗️ ARCHITECTURE COMPARISON")
        logger.info("="*60)
        
        logger.info("🔴 LEGACY plugin_boltalka_vsegpt.py:")
        logger.info("  ❌ Direct OpenAI API calls")
        logger.info("  ❌ Hardcoded VseGPT integration")
        logger.info("  ❌ Mixed TTS and chat logic")
        logger.info("  ❌ Global state in VACore")
        logger.info("  ❌ Synchronous architecture")
        logger.info("  ❌ No web API")
        logger.info("  ❌ Limited error handling")
        
        logger.info("\n🟢 NEW ConversationPlugin:")
        logger.info("  ✅ Uses UniversalLLMPlugin backend")
        logger.info("  ✅ Multiple LLM provider support") 
        logger.info("  ✅ Clean separation of concerns")
        logger.info("  ✅ Proper session management")
        logger.info("  ✅ Full async/await architecture")
        logger.info("  ✅ Complete REST API")
        logger.info("  ✅ Robust error handling")
        logger.info("  ✅ Configuration-driven")
        logger.info("  ✅ Type-safe with proper interfaces")
        
        logger.info("\n📊 Migration status:")
        logger.info("  ✅ Conversational logic - MIGRATED")
        logger.info("  ✅ Voice commands - ENHANCED")  
        logger.info("  ✅ Session management - IMPROVED")
        logger.info("  ✅ LLM integration - ABSTRACTED")
        logger.info("  ✅ Web API - ADDED")
        logger.info("  ❌ VseGPT TTS - Use UniversalTTSPlugin instead")
    
    async def run_complete_demo(self) -> None:
        """Run the complete demonstration"""
        logger.info("🎯 ConversationPlugin Complete Demo")
        logger.info("=" * 80)
        
        try:
            # Setup
            await self.setup_core()
            
            # Run all demos
            await self.demo_voice_commands()
            await self.demo_session_management()
            await self.demo_api_endpoints()
            await self.demo_configuration()
            await self.demo_architecture_comparison()
            
            logger.info("\n" + "="*80)
            logger.info("🎉 ConversationPlugin demo completed successfully!")
            logger.info("="*80)
            
            # Note about LLM dependency
            logger.info("\n💡 Note: For full functionality, ensure:")
            logger.info("  1. UniversalLLMPlugin is loaded and configured")
            logger.info("  2. LLM providers (OpenAI, VseGPT, etc.) have API keys")
            logger.info("  3. Network connectivity for LLM API calls")
            
        except Exception as e:
            logger.error(f"❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Cleanup
            if self.core:
                await self.core.stop()


async def main():
    """Main demo entry point"""
    demo = ConversationDemoRunner()
    await demo.run_complete_demo()


if __name__ == "__main__":
    asyncio.run(main()) 