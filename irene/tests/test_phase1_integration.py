"""
Phase 1 Integration Tests - Context-Aware Foundation

Comprehensive tests for client identification, room/device context,
and Russian language support in the context-aware foundation.
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List

from irene.intents.models import ConversationContext
from irene.intents.context import ContextManager
from irene.workflows.base import RequestContext
from irene.core.client_registry import ClientRegistry, ClientRegistration, ClientDevice
from irene.core.entity_resolver import ContextualEntityResolver, DeviceEntityResolver


class TestPhase1ClientIdentification:
    """Test client identification and registration functionality"""
    
    @pytest.fixture
    def client_registry(self):
        """Create a test client registry"""
        return ClientRegistry({"persistent_storage": False})
    
    @pytest.fixture
    def context_manager(self):
        """Create a test context manager"""
        return ContextManager(session_timeout=3600, max_history_turns=10)
    
    @pytest.mark.asyncio
    async def test_esp32_client_registration(self, client_registry):
        """Test ESP32 node registration with devices"""
        devices = [
            {
                "id": "light1",
                "name": "Кухонный свет",
                "type": "light",
                "capabilities": {"dimmable": True, "color": False}
            },
            {
                "id": "sensor1", 
                "name": "Датчик температуры",
                "type": "sensor",
                "capabilities": {"temperature": True, "humidity": True}
            }
        ]
        
        success = await client_registry.register_esp32_node(
            client_id="kitchen_esp32",
            room_name="Кухня",
            devices=devices,
            source_address="192.168.1.100",
            language="ru"
        )
        
        assert success
        
        # Verify registration
        client = client_registry.get_client("kitchen_esp32")
        assert client is not None
        assert client.client_id == "kitchen_esp32"
        assert client.room_name == "Кухня"
        assert client.language == "ru"
        assert client.client_type == "esp32"
        assert len(client.available_devices) == 2
        assert client.capabilities["voice_input"] is True
        assert client.source_address == "192.168.1.100"
        
        print("✅ ESP32 client registration test passed!")
    
    @pytest.mark.asyncio
    async def test_web_client_registration(self, client_registry):
        """Test web client registration"""
        success = await client_registry.register_web_client(
            client_id="web_living_room",
            room_name="Гостиная",
            user_agent="Mozilla/5.0 (Chrome)",
            language="ru"
        )
        
        assert success
        
        # Verify registration
        client = client_registry.get_client("web_living_room")
        assert client is not None
        assert client.client_id == "web_living_room"
        assert client.room_name == "Гостиная"
        assert client.language == "ru"
        assert client.client_type == "web"
        assert client.capabilities["visual_output"] is True
        assert client.user_agent == "Mozilla/5.0 (Chrome)"
        
        print("✅ Web client registration test passed!")
    
    @pytest.mark.asyncio
    async def test_client_lookup_by_room(self, client_registry):
        """Test finding clients by room name"""
        # Register multiple clients in same room
        await client_registry.register_esp32_node("kitchen_esp32", "Кухня", [])
        await client_registry.register_web_client("kitchen_web", "Кухня")
        await client_registry.register_web_client("living_room_web", "Гостиная")
        
        # Test room lookup
        kitchen_clients = client_registry.get_clients_by_room("Кухня")
        assert len(kitchen_clients) == 2
        assert all(client.room_name == "Кухня" for client in kitchen_clients)
        
        living_room_clients = client_registry.get_clients_by_room("Гостиная")
        assert len(living_room_clients) == 1
        assert living_room_clients[0].room_name == "Гостиная"
        
        # Test all rooms
        all_rooms = client_registry.get_all_rooms()
        assert "Кухня" in all_rooms
        assert "Гостиная" in all_rooms
        
        print("✅ Client room lookup test passed!")


class TestPhase1ContextFlow:
    """Test context information flow from request to conversation"""
    
    @pytest.fixture
    def context_manager(self):
        """Create a test context manager"""
        return ContextManager(session_timeout=3600, max_history_turns=10)
    
    @pytest.mark.asyncio
    async def test_request_context_to_conversation_context_flow(self, context_manager):
        """Test that client information flows from RequestContext to ConversationContext"""
        # Create request context with client information
        request_context = RequestContext(
            source="esp32",
            session_id="test_session",
            client_id="kitchen_esp32",
            room_name="Кухня",
            device_context={
                "available_devices": [
                    {"id": "light1", "name": "Кухонный свет", "type": "light"},
                    {"id": "speaker1", "name": "Колонка", "type": "speaker"}
                ]
            },
            language="ru"
        )
        
        # Get conversation context with request information
        conv_context = await context_manager.get_context_with_request_info(
            "test_session", request_context
        )
        
        # Verify client information was transferred
        assert conv_context.client_id == "kitchen_esp32"
        assert conv_context.language == "ru"
        assert conv_context.request_source == "esp32"
        
        # Verify room name resolution
        room_name = conv_context.get_room_name()
        assert room_name == "Кухня"
        
        # Verify device capabilities
        devices = conv_context.get_device_capabilities()
        assert len(devices) == 2
        assert any(device["name"] == "Кухонный свет" for device in devices)
        assert any(device["name"] == "Колонка" for device in devices)
        
        print("✅ Request-to-conversation context flow test passed!")
    
    @pytest.mark.asyncio
    async def test_device_name_resolution(self, context_manager):
        """Test device name resolution with fuzzy matching"""
        request_context = RequestContext(
            client_id="test_client",
            room_name="Кухня",
            device_context={
                "available_devices": [
                    {"id": "light1", "name": "Кухонный свет", "type": "light"},
                    {"id": "light2", "name": "Kitchen Light", "type": "light"},
                    {"id": "tv1", "name": "Телевизор Samsung", "type": "tv"}
                ]
            },
            language="ru"
        )
        
        conv_context = await context_manager.get_context_with_request_info(
            "test_session", request_context
        )
        
        # Test exact match (Russian)
        device = conv_context.get_device_by_name("Кухонный свет")
        assert device is not None
        assert device["name"] == "Кухонный свет"
        
        # Test exact match (English)
        device = conv_context.get_device_by_name("Kitchen Light")
        assert device is not None
        assert device["name"] == "Kitchen Light"
        
        # Test fuzzy match
        device = conv_context.get_device_by_name("кухонный")  # Lower case, partial
        assert device is not None
        assert "Кухонный" in device["name"]
        
        # Test non-existent device
        device = conv_context.get_device_by_name("несуществующее устройство")
        assert device is None
        
        print("✅ Device name resolution test passed!")


class TestPhase1EntityResolution:
    """Test context-aware entity resolution"""
    
    @pytest.fixture
    def entity_resolver(self):
        """Create entity resolver"""
        return ContextualEntityResolver()
    
    @pytest.fixture
    def sample_context_with_devices(self):
        """Create context with Russian device names"""
        context = ConversationContext(
            session_id="test_session",
            client_id="kitchen_esp32",
            language="ru"
        )
        
        context.set_client_context("kitchen_esp32", {
            "room_name": "Кухня",
            "available_devices": [
                {"id": "light1", "name": "Кухонный свет", "type": "light"},
                {"id": "speaker1", "name": "Умная колонка", "type": "speaker"},
                {"id": "sensor1", "name": "Датчик температуры", "type": "sensor"}
            ]
        })
        
        return context
    
    @pytest.mark.asyncio
    async def test_russian_device_entity_resolution(self, entity_resolver, sample_context_with_devices):
        """Test device entity resolution with Russian terms"""
        from irene.intents.models import Intent
        
        # Test with Russian device reference
        intent = Intent(
            name="device.control",
            entities={"device": "свет", "action": "включи"},
            confidence=0.9,
            raw_text="включи свет"
        )
        
        resolved_entities = await entity_resolver.resolve_entities(intent, sample_context_with_devices)
        
        # Check device resolution
        assert "device_resolved" in resolved_entities
        device_resolved = resolved_entities["device_resolved"]
        assert device_resolved["name"] == "Кухонный свет"
        assert device_resolved["type"] == "light"
        
        print("✅ Russian device entity resolution test passed!")
    
    @pytest.mark.asyncio 
    async def test_russian_temporal_entity_resolution(self, entity_resolver):
        """Test temporal entity resolution with Russian time expressions"""
        from irene.intents.models import Intent
        
        context = ConversationContext(session_id="test", language="ru")
        
        # Test Russian duration
        intent = Intent(
            name="timer.set",
            entities={"duration": "5 минут"},
            confidence=0.9,
            raw_text="поставь таймер на 5 минут"
        )
        
        resolved_entities = await entity_resolver.resolve_entities(intent, context)
        
        # Check duration resolution
        assert "duration_resolved" in resolved_entities
        duration_resolved = resolved_entities["duration_resolved"]
        assert duration_resolved["value"] == 5
        assert duration_resolved["unit"] == "minutes"
        
        print("✅ Russian temporal entity resolution test passed!")
    
    @pytest.mark.asyncio
    async def test_russian_location_entity_resolution(self, entity_resolver, sample_context_with_devices):
        """Test location entity resolution with Russian location terms"""
        from irene.intents.models import Intent
        
        # Test "здесь" (here) resolution
        intent = Intent(
            name="device.status",
            entities={"location": "здесь"},
            confidence=0.9,
            raw_text="какие устройства здесь"
        )
        
        resolved_entities = await entity_resolver.resolve_entities(intent, sample_context_with_devices)
        
        # Check location resolution to current room
        assert "location_resolved" in resolved_entities
        location_resolved = resolved_entities["location_resolved"]
        assert location_resolved == "Кухня"
        
        print("✅ Russian location entity resolution test passed!")


class TestPhase1RussianLanguageSupport:
    """Test Russian language support and configuration"""
    
    def test_russian_language_defaults(self):
        """Test Russian-first language configuration in modules"""
        # Test text processing defaults by importing and checking
        from irene.providers.text_processing.general_text_processor import GeneralTextProcessor
        from irene.providers.text_processing.number_text_processor import NumberTextProcessor
        from irene.providers.nlu.spacy_provider import SpaCyNLUProvider
        
        # Test that modules default to Russian when no config provided
        general_processor = GeneralTextProcessor({})
        assert general_processor.language == "ru"
        
        number_processor = NumberTextProcessor({})
        assert number_processor.language == "ru"
        
        # Test spaCy provider Russian model default
        spacy_provider = SpaCyNLUProvider({})
        assert spacy_provider.model_name == "ru_core_news_sm"
        
        print("✅ Russian language defaults test passed!")
    
    def test_russian_language_preference_in_context(self):
        """Test Russian language preference in context objects"""
        # Test ConversationContext defaults to Russian
        context = ConversationContext(session_id="test")
        assert context.language == "ru"
        
        # Test RequestContext defaults to Russian
        from irene.workflows.base import RequestContext
        request_context = RequestContext()
        assert request_context.language == "ru"
        
        print("✅ Russian language preference in context test passed!")
    
    def test_conversation_context_russian_defaults(self):
        """Test that ConversationContext defaults to Russian"""
        context = ConversationContext(session_id="test")
        assert context.language == "ru"
        
        # Test context creation with explicit language
        context_en = ConversationContext(session_id="test", language="en")
        assert context_en.language == "en"
        
        print("✅ ConversationContext Russian defaults test passed!")


class TestPhase1EndToEndIntegration:
    """End-to-end integration tests for complete Phase 1 functionality"""
    
    @pytest.mark.asyncio
    async def test_complete_context_aware_flow(self):
        """Test complete flow from client registration to context-aware processing"""
        # 1. Set up client registry and register ESP32 node
        registry = ClientRegistry({"persistent_storage": False})
        
        devices = [
            {"id": "light1", "name": "Кухонный свет", "type": "light"},
            {"id": "speaker1", "name": "Колонка Yandex", "type": "speaker"}
        ]
        
        await registry.register_esp32_node(
            client_id="kitchen_esp32",
            room_name="Кухня", 
            devices=devices,
            language="ru"
        )
        
        # 2. Create request context with client information
        request_context = RequestContext(
            source="esp32",
            session_id="integration_test",
            client_id="kitchen_esp32",
            room_name="Кухня",
            device_context={"available_devices": devices},
            language="ru"
        )
        
        # 3. Get conversation context with client info
        context_manager = ContextManager()
        conv_context = await context_manager.get_context_with_request_info(
            "integration_test", request_context
        )
        
        # 4. Test entity resolution
        from irene.intents.models import Intent
        resolver = ContextualEntityResolver()
        
        intent = Intent(
            name="device.control",
            entities={"device": "свет", "action": "включи"},
            confidence=0.9,
            raw_text="включи свет на кухне"
        )
        
        resolved_entities = await resolver.resolve_entities(intent, conv_context)
        
        # 5. Verify complete flow
        assert conv_context.client_id == "kitchen_esp32"
        assert conv_context.language == "ru"
        assert conv_context.get_room_name() == "Кухня"
        assert len(conv_context.get_device_capabilities()) == 2
        
        # Device resolution should work
        assert "device_resolved" in resolved_entities
        device = resolved_entities["device_resolved"]
        assert device["name"] == "Кухонный свет"
        assert device["type"] == "light"
        
        # Client context should include device information
        assert conv_context.client_id in registry.clients
        client_reg = registry.get_client(conv_context.client_id)
        assert client_reg.room_name == "Кухня"
        assert len(client_reg.available_devices) == 2
        
        print("✅ Complete context-aware flow integration test passed!")
        print(f"   Client: {conv_context.client_id}")
        print(f"   Room: {conv_context.get_room_name()}")
        print(f"   Devices: {len(conv_context.get_device_capabilities())}")
        print(f"   Resolved device: {device['name']}")


async def run_phase1_tests():
    """Run all Phase 1 integration tests"""
    print("🧪 Running Phase 1 Context-Aware Foundation Integration Tests...\n")
    
    # Test client identification
    print("📝 Testing Client Identification...")
    test_client = TestPhase1ClientIdentification()
    registry = ClientRegistry({"persistent_storage": False})
    
    await test_client.test_esp32_client_registration(registry)
    await test_client.test_web_client_registration(registry)
    await test_client.test_client_lookup_by_room(registry)
    
    print("\n🔗 Testing Context Flow...")
    test_flow = TestPhase1ContextFlow()
    context_manager = ContextManager()
    
    await test_flow.test_request_context_to_conversation_context_flow(context_manager)
    await test_flow.test_device_name_resolution(context_manager)
    
    print("\n🎯 Testing Entity Resolution...")
    test_entities = TestPhase1EntityResolution()
    resolver = ContextualEntityResolver()
    
    # Create sample context
    sample_context = ConversationContext(session_id="test", client_id="kitchen", language="ru")
    sample_context.set_client_context("kitchen", {
        "room_name": "Кухня",
        "available_devices": [
            {"id": "light1", "name": "Кухонный свет", "type": "light"},
            {"id": "speaker1", "name": "Умная колонка", "type": "speaker"}
        ]
    })
    
    await test_entities.test_russian_device_entity_resolution(resolver, sample_context)
    await test_entities.test_russian_temporal_entity_resolution(resolver)
    await test_entities.test_russian_location_entity_resolution(resolver, sample_context)
    
    print("\n🇷🇺 Testing Russian Language Support...")
    test_russian = TestPhase1RussianLanguageSupport()
    
    test_russian.test_russian_language_defaults()
    test_russian.test_russian_language_preference_in_context()
    test_russian.test_conversation_context_russian_defaults()
    
    print("\n🚀 Testing End-to-End Integration...")
    test_e2e = TestPhase1EndToEndIntegration()
    await test_e2e.test_complete_context_aware_flow()
    
    print("\n🎉 All Phase 1 Context-Aware Foundation Tests Passed!")
    print("✅ Client identification and registration working")
    print("✅ Context metadata flow working")  
    print("✅ Russian-first language support working")
    print("✅ Device and entity resolution working")
    print("✅ End-to-end context-aware processing working")
    print("\n📈 Phase 1 implementation is complete and functional!")


if __name__ == "__main__":
    asyncio.run(run_phase1_tests())
