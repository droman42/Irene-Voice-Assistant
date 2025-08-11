## 9. Named Client Support for Contextual Command Processing

**Status:** ✅ **COMPLETED**  
**Priority:** Medium  
**Components:** Workflow system, RequestContext, Voice trigger, Intent system

**✅ IMPLEMENTATION COMPLETED**: Full named client support with contextual command processing implemented via Client Registry System. All requirements achieved and documented in CLIENT_REGISTRY.md.

### Problem

The current system lacks support for named clients (device identification) that would allow the same command to behave differently based on the source device. This is essential for multi-device deployments where business logic needs to interpret commands contextually based on the originating client.

### Current Architecture Limitations

**Generic Request Context:**
```python
class RequestContext:
    def __init__(self,
                 source: str = "unknown",        # Generic source name
                 session_id: str = "default",    # Session ID
                 # No client/device identification
```

**Missing Components:**
- No client identifier propagation from VoiceTrigger
- No business logic interpretation of client identifiers
- No contextual command routing based on source device
- No standardized client naming scheme

### Proposed Solution: Named Client Architecture

**Phase 1: Client Identification Infrastructure**
- Extend `RequestContext` with client identifier support
- Add client ID propagation from voice trigger to intent execution
- Create client registry and metadata management
- Implement client-aware intent routing

**Phase 2: VoiceTrigger Integration**
```python
# VoiceTrigger passes client identifier
class WakeWordResult:
    def __init__(self, 
                 detected: bool,
                 confidence: float,
                 word: str,
                 client_id: Optional[str] = None):  # NEW: Client identifier
```

**Phase 3: Intent Context Awareness**
```python
# Enhanced RequestContext
class RequestContext:
    def __init__(self,
                 source: str = "unknown",
                 session_id: str = "default", 
                 client_id: Optional[str] = None,     # NEW: Named client
                 client_metadata: Optional[Dict] = None,  # NEW: Client data
                 wants_audio: bool = False,
                 skip_wake_word: bool = False,
                 metadata: Optional[Dict[str, Any]] = None):
```

**Phase 4: Business Logic Integration**
```python
# Intent handlers become client-aware
class IntentHandler(ABC):
    async def execute(self, intent: Intent, context: ConversationContext) -> IntentResult:
        # Access client information for contextual processing
        client_id = context.request_context.client_id
        client_metadata = context.request_context.client_metadata
        
        # Same command, different behavior based on client
        if intent.action == "close_curtains":
            return await self._handle_curtains_for_client(client_id)
```

### Technical Implementation

**Client Registry System**
```python
class ClientRegistry:
    """Registry for managing named clients and their metadata"""
    
    def register_client(self, client_id: str, metadata: Dict[str, Any]):
        """Register a named client with metadata"""
        
    def get_client_metadata(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a named client"""
        
    def update_client_status(self, client_id: str, status: Dict[str, Any]):
        """Update client status information"""
```

**Workflow Integration**
- Voice trigger components pass client identifiers
- Workflows propagate client context through pipeline
- Intent orchestrator provides client-aware routing
- Intent handlers receive client information for business logic

### Use Cases Enabled

**Multi-Device Scenarios:**
- Same voice command behaves differently in different rooms
- Device-specific capabilities and configurations
- Contextual responses based on client location
- Client-specific user preferences and settings

**Example: Contextual Commands**
```python
# Command: "Turn on the lights"
# kitchen_device -> Controls kitchen lights
# bedroom_device -> Controls bedroom lights  
# living_room_device -> Controls living room lights
```

### ✅ **ACHIEVED BENEFITS**

- ✅ **Contextual Intelligence**: Same commands work differently based on source via client_id and room_name
- ✅ **Multi-Device Support**: Complete ESP32, web client, and mobile app registration system
- ✅ **Business Logic Flexibility**: Intent handlers access full client context via ConversationContext
- ✅ **Future Extensibility**: Robust foundation implemented for smart home, IoT, and enterprise scenarios
- ✅ **Backwards Compatibility**: Optional client ID maintains full backward compatibility

### Configuration Example

```toml
[clients]
# Client registry configuration
kitchen = { type = "room", location = "kitchen", capabilities = ["lighting", "music"] }
bedroom = { type = "room", location = "bedroom", capabilities = ["lighting", "climate"] }
office = { type = "workspace", location = "office", capabilities = ["lighting", "presentation"] }

[voice_trigger]
# Client ID can be configured per voice trigger instance
client_id = "kitchen"  # This device represents the kitchen

[intents.handlers]
# Intent handlers can access client information
contextual_routing = true
```

### Impact

- **Workflow Changes**: RequestContext and workflow pipeline modifications
- **Intent System**: Enhanced context propagation and handler capabilities
- **Voice Trigger**: Client ID integration in wake word detection
- **Configuration**: Client registry and mapping configuration
- **Backward Compatibility**: Existing implementations continue to work with null client_id

### ✅ **IMPLEMENTATION COMPLETED THROUGH:**

**Client Registry System Implementation**  
- ✅ **Complete Client Registration**: ESP32, web, mobile, and desktop client support
- ✅ **Room-Based Device Context**: Clients register with room names and device lists
- ✅ **Context-Aware Processing**: Full client information flows through intent processing pipeline
- ✅ **Device Discovery**: Fuzzy device name matching and capability-based discovery
- ✅ **Persistent Storage**: Client registry survives system restarts with JSON storage
- ✅ **Business Logic Integration**: Intent handlers access room context and device capabilities

**RequestContext and Workflow Integration**  
- ✅ **Enhanced RequestContext**: Supports client_id, room_name, device_context, and language
- ✅ **Pipeline Integration**: Client context flows from request → workflows → intents → handlers
- ✅ **Conversation Context**: Client information integrated into ConversationContext model
- ✅ **Contextual Methods**: `get_room_name()`, `get_device_capabilities()`, `get_device_by_name()`

**Implementation Reference:** See `docs/CLIENT_REGISTRY.md` - Complete Client Registration and Context System

### Related Files (✅ All Implemented)
- ✅ `irene/workflows/base.py` (RequestContext with client identification)
- ✅ `irene/intents/models.py` (ConversationContext with client metadata)
- ✅ `irene/intents/context.py` (ContextManager with client information integration)
- ✅ `irene/intents/orchestrator.py` (client-aware routing and context propagation)
- ✅ `irene/intents/handlers/base.py` (intent handler base class with context access)
- ✅ `irene/core/client_registry.py` (complete client registration system)
- ✅ `docs/CLIENT_REGISTRY.md` (comprehensive documentation and examples)

**Result**: ✅ **FULLY COMPLETED** - Complete named client support with contextual command processing

**Key Achievement**: Same voice command "включи свет" now works contextually:
- Kitchen ESP32 → Controls kitchen lights
- Bedroom ESP32 → Controls bedroom lights  
- Web client in living room → Controls living room devices

Intent handlers receive full client context for intelligent, location-aware processing.
