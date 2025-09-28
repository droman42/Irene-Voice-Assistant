"""
Train Schedule Demo - Using the TrainScheduleIntentHandler

This demo shows how to use the new TrainScheduleIntentHandler
to get train schedules from Yandex.Schedules API.

Requirements:
- API key from https://yandex.ru/dev/rasp/raspapi/
- Station IDs for departure and destination
- requests library installed
"""

import asyncio
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Import intent system components
from irene.intents.models import Intent, UnifiedConversationContext
from irene.core.session_manager import SessionManager
from irene.intents.handlers.train_schedule import TrainScheduleIntentHandler
from irene.intents.registry import IntentRegistry
from irene.intents.orchestrator import IntentOrchestrator


class TrainScheduleDemo:
    """Demonstration of train schedule functionality"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the demo with configuration.
        
        Args:
            config: Configuration dictionary with API key and station settings
        """
        # Default configuration (Moscow to Sergiev Posad)
        self.default_config = {
            "api_key": "",  # Set your API key here
            "from_station": "s9600681",  # Leningradsky Railway Station (Moscow)
            "to_station": "s2000002",   # Sergiev Posad
            "max_results": 3
        }
        
        # Merge with provided config
        self.config = {**self.default_config, **(config or {})}
        
        # Initialize intent system
        self.registry = IntentRegistry()
        self.orchestrator = IntentOrchestrator(self.registry)
        
        # Create and register train schedule handler
        self.train_handler = TrainScheduleIntentHandler(self.config)
        self._register_handlers()
    
    def _register_handlers(self):
        """Register intent handlers with the registry"""
        # Register train schedule handler for various patterns
        patterns = [
            "transport.*",              # All transport-related intents
            "train_schedule",           # Direct train schedule requests
            "электричка",              # Russian term for electric train
            "поезд"                    # Russian term for train
        ]
        
        for pattern in patterns:
            self.registry.register_handler(pattern, self.train_handler)
    
    async def test_train_schedule_intent(self):
        """Test the train schedule intent handler"""
        print("=== Train Schedule Intent Demo ===\n")
        
        # Check if handler is available
        is_available = await self.train_handler.is_available()
        print(f"Handler available: {is_available}")
        
        if not is_available:
            print("❌ Train schedule handler is not available.")
            print("   Please check:")
            print("   1. API key is configured")
            print("   2. requests library is installed")
            return
        
        # Create test intents
        test_cases = [
            {
                "name": "transport.train_schedule",
                "text": "когда ближайшая электричка",
                "entities": {}
            },
            {
                "name": "transport.get_trains", 
                "text": "электричка расписание",
                "entities": {}
            },
            {
                "name": "general.query",
                "text": "ближайший поезд",
                "entities": {}
            },
            {
                "name": "transport.train_schedule",
                "text": "электрички на сегодня",
                "entities": {
                    "from_station": "s9600681",
                    "to_station": "s2000002"
                }
            }
        ]
        
        # Create conversation context
        context = UnifiedConversationContext(session_id=SessionManager.generate_session_id("demo"))
        
        # Test each intent
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test Case {i}: {test_case['text']} ---")
            
            # Create intent
            intent = Intent(
                name=test_case["name"],
                entities=test_case["entities"],
                confidence=0.9,
                raw_text=test_case["text"]
            )
            
            # Check if handler can handle this intent
            can_handle = await self.train_handler.can_handle(intent)
            print(f"Can handle: {can_handle}")
            
            if can_handle:
                try:
                    # Execute intent
                    result = await self.orchestrator.execute_intent(intent, context)
                    
                    print(f"Success: {result.success}")
                    print(f"Response: {result.text}")
                    print(f"Should speak: {result.should_speak}")
                    
                    if result.metadata:
                        print(f"Metadata: {result.metadata}")
                    
                    if not result.success and result.error:
                        print(f"Error: {result.error}")
                        
                except Exception as e:
                    print(f"❌ Error executing intent: {e}")
            else:
                print("Handler cannot process this intent")
    
    async def test_handler_capabilities(self):
        """Test handler capabilities and information"""
        print("\n=== Handler Capabilities ===")
        
        capabilities = self.train_handler.get_capabilities()
        print(f"Name: {capabilities['name']}")
        print(f"Domains: {capabilities['domains']}")
        print(f"Actions: {capabilities['actions']}")
        print(f"Available: {capabilities['available']}")
        print(f"Features: {capabilities['features']}")
        print(f"Requirements: {capabilities['requirements']}")
        
        info = self.train_handler.get_info()
        print(f"\nHandler Info:")
        print(f"Class: {info['class']}")
        print(f"Module: {info['module']}")
        print(f"Description: {info['description']}")
    
    async def run_demo(self):
        """Run the complete demonstration"""
        try:
            await self.test_handler_capabilities()
            await self.test_train_schedule_intent()
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            raise


async def main():
    """Main demo function"""
    print("Train Schedule Intent Handler Demo")
    print("=" * 50)
    
    # Configuration (set your API key here)
    config = {
        "api_key": "",  # Get from https://yandex.ru/dev/rasp/raspapi/
        "from_station": "s9600681",  # Moscow Leningradsky
        "to_station": "s2000002",   # Sergiev Posad
        "max_results": 3
    }
    
    if not config["api_key"]:
        print("⚠️  No API key configured!")
        print("   To test with real data:")
        print("   1. Get API key from https://yandex.ru/dev/rasp/raspapi/")
        print("   2. Set the 'api_key' in the config above")
        print("\n   Continuing with demo (will show error handling)...")
    
    # Create and run demo
    demo = TrainScheduleDemo(config)
    await demo.run_demo()
    
    print("\n" + "=" * 50)
    print("Demo completed!")


if __name__ == "__main__":
    asyncio.run(main()) 