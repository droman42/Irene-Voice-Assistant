# Session and Context Unification Implementation Plan

**Status:** 🔧 **PLANNED**  
**Priority:** High  
**Components:** Intent System, Context Management, Session Management, Entity Resolution

## Overview

This document outlines the implementation plan to unify session and context management across the Irene Voice Assistant system, addressing architectural inconsistencies and enabling proper room-based context injection for device control.

## Problems Identified

### 1. **Fragmented Session Management**
- Multiple session ID generation strategies across components
- Inconsistent session identifiers (hardcoded vs generated vs user-provided)
- No unified session lifecycle management
- **CRITICAL:** Must preserve room-scoped session boundaries for fire-and-forget actions

### 2. **Dual Context Architecture**
- `ConversationContext` (system-wide state) and `ConversationSession` (LLM chat history) serve different but related purposes at the same architectural layer
- Synchronization complexity between parallel context tracking systems
- Donation-routing compatibility problems due to method signature mismatches
- **CRITICAL:** Active action tracking relies on room-scoped contexts for disambiguation

### 3. **Incomplete Room Context Integration**
- Room context injection system works correctly within the system
- Missing integration point: External sources (like ESP32) don't populate room context
- Session ID generation doesn't reflect room identity consistently

### 4. **Hardcoded Localization**
- Device type mappings hardcoded in `DeviceEntityResolver`
- Room keyword mappings hardcoded in `LocationEntityResolver` 
- No external localization files for room/device mappings

### 5. **Fire-and-Forget System Dependencies (CRITICAL)**
- **Multi-room active action tracking:** Kitchen timer + living room music = separate contexts
- **Contextual command resolution (TODO16):** "stop" command targets room-scoped actions
- **Room-based disambiguation:** Commands resolve within physical location boundaries
- **Cross-room action independence:** Actions in different rooms must not interfere

> ⚠️ **ARCHITECTURE CONSTRAINT:** Any unification must preserve room-scoped session boundaries to maintain existing fire-and-forget and contextual command resolution functionality.
>
> 🏠 **SYSTEM DESIGN:** Single-user, multi-room personal assistant system. Room sessions represent physical locations, not different users.

## Implementation Plan

### **Phase 1: Context Architecture Unification** ✅ **COMPLETED**

#### **1.1 Design Unified Context Class (Room-Scoped)** ✅ **COMPLETED**

**File:** `irene/intents/models.py` (modify existing)

```python
@dataclass
class UnifiedConversationContext:
    """Unified conversation context replacing both ConversationContext and ConversationSession
    
    CRITICAL: Maintains room/client-scoped session boundaries for fire-and-forget action tracking
    and contextual command resolution (TODO16 compatibility).
    
    DESIGN: Single-user, multi-room system where sessions represent physical locations.
    """
    
    # Core identification (room-scoped sessions preserved)
    session_id: str                   # Room-based: "kitchen_session", "living_room_session"
    client_id: Optional[str] = None   # Room ID: "kitchen", "living_room"
    room_name: Optional[str] = None   # Human-readable: "Кухня", "Гостиная"
    
    # System-level context (from old ConversationContext)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    client_metadata: Dict[str, Any] = field(default_factory=dict)
    available_devices: List[Dict[str, Any]] = field(default_factory=list)
    language: str = "ru"
    
    # CRITICAL: Fire-and-forget action tracking (room-scoped)
    active_actions: Dict[str, Any] = field(default_factory=dict)      # Domain -> action info
    recent_actions: List[Dict[str, Any]] = field(default_factory=list) # Completed actions
    failed_actions: List[Dict[str, Any]] = field(default_factory=list) # Failed actions
    action_error_count: Dict[str, int] = field(default_factory=dict)   # Error tracking
    
    # Handler-specific contexts (replaces ConversationSession approach)
    handler_contexts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Unified timestamps
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    # Combined methods from both old classes
    def get_room_name(self) -> Optional[str]: ...
    def get_device_capabilities(self) -> List[Dict[str, Any]]: ...
    def get_device_by_name(self, device_name: str) -> Optional[Dict[str, Any]]: ...
    
    # Handler-specific context management
    def get_handler_context(self, handler_name: str) -> Dict[str, Any]:
        """Get handler-specific context (e.g., LLM conversation history)"""
        if handler_name not in self.handler_contexts:
            self.handler_contexts[handler_name] = {
                "messages": [],
                "conversation_type": "chat", 
                "model_preference": "",
                "created_at": time.time()
            }
        return self.handler_contexts[handler_name]
    
    def clear_handler_context(self, handler_name: str, keep_system: bool = True):
        """Clear handler-specific context (e.g., LLM history)"""
        context = self.get_handler_context(handler_name)
        if keep_system and context.get("messages") and context["messages"][0].get("role") == "system":
            system_msg = context["messages"][0]
            context["messages"] = [system_msg]
        else:
            context["messages"] = []
    
    # CRITICAL: Fire-and-forget action management (preserved from ConversationContext)
    def add_active_action(self, domain: str, action_info: Dict[str, Any]):
        """Add active action with automatic room context injection"""
        self.active_actions[domain] = {
            **action_info,
            'room_id': self.client_id,
            'room_name': self.room_name,
            'session_id': self.session_id,
            'started_at': time.time()
        }
    
    def complete_action(self, domain: str, success: bool = True, error: Optional[str] = None): ...
    def has_active_action(self, domain: str) -> bool: ...
    def get_active_action_domains(self) -> List[str]: ...
    def remove_completed_action(self, domain: str, success: bool = True, error: Optional[str] = None): ...
    
    # Additional fire-and-forget management methods
    def cancel_action(self, domain: str, reason: str = "User requested cancellation") -> bool:
        """Cancel an active action and mark it as cancelled"""
        if domain in self.active_actions:
            self.active_actions[domain].update({
                'status': 'cancelled',
                'cancelled_at': time.time(),
                'cancellation_reason': reason
            })
            return True
        return False
    
    def update_action_status(self, domain: str, status: str, error: Optional[str] = None) -> bool:
        """Update the status of a running action"""
        if domain in self.active_actions:
            self.active_actions[domain]['status'] = status
            if error:
                self.active_actions[domain]['error'] = error
            self.active_actions[domain]['last_updated'] = time.time()
            return True
        return False
    
    def get_cancellable_actions(self) -> List[str]:
        """Get list of domains with actions that can be cancelled"""
        return [domain for domain, action_info in self.active_actions.items()
                if action_info.get('status') == 'running']
```

#### **1.2 Migration Strategy (Preserving Fire-and-Forget)** ✅ **COMPLETED**

**Direct Replacement Approach:**
1. Create `UnifiedConversationContext` alongside existing classes
2. **CRITICAL:** Preserve all fire-and-forget action tracking methods during migration
3. Update components one by one to use unified context directly (no adapters needed)
4. **CRITICAL:** Ensure contextual command resolution (TODO16) continues working
5. Remove old classes after all components migrated

**Migration Order (Risk-Minimized):**
1. `ContextManager` - Update to create/manage unified contexts (preserve room-scoped sessions)
2. **Fire-and-forget validation** - Verify active action tracking works with unified context
3. **Contextual command testing** - Verify TODO16 disambiguation continues working
4. **MemoryManager** - Update to handle UnifiedConversationContext
5. `NLUComponent` - Update context-aware processing to use unified context
6. Intent handlers - Update method signatures and context access
7. Remove old `ConversationSession` class from `ConversationIntentHandler`

**Handler Context Migration Strategy:**
- **ConversationSession replacement:** Instead of separate session objects, handlers access `context.get_handler_context("handler_name")`
- **LLM message access:** `session.messages` becomes `context.get_handler_context("conversation")["messages"]`
- **Conversation type:** `session.conversation_type` becomes `context.get_handler_context("conversation")["conversation_type"]`
- **Development refactoring approach:** Direct replacement of classes and method signatures - no backward compatibility layers needed

**Critical Validation Points:**
- Multiple room sessions can have independent active actions
- "Stop" commands resolve within room boundaries
- Cross-room actions do not interfere with each other
- Fire-and-forget task lifecycle management preserved
- **Memory usage estimation works with unified context**

#### **1.3 MemoryManager Compatibility** ✅ **COMPLETED**

**Problem:** MemoryManager expects `get_memory_usage_estimate()` method on context objects but current dual context architecture causes AttributeError: `'Context' object has no attribute 'get_memory_usage_estimate'`.

**Root Cause:** MemoryManager receives basic `Context` objects from `irene/core/context.py` but expects `ConversationContext` objects from `irene/intents/models.py` which have the memory estimation method.

**Solution:**
1. Add `get_memory_usage_estimate()` method to `UnifiedConversationContext`
2. Update MemoryManager to handle unified context type
3. Verify memory analysis works with unified context structure

**Implementation:**
- **File:** `irene/intents/models.py` - Add memory estimation method to UnifiedConversationContext
- **File:** `irene/core/memory_manager.py` - Verify compatibility with unified context (may need minor updates)
- **File:** `irene/components/monitoring_component.py` - Test integration works correctly

**Memory Estimation Method for UnifiedConversationContext:**
```python
def get_memory_usage_estimate(self) -> Dict[str, Any]:
    """Estimate memory usage of unified context data"""
    import sys
    
    try:
        # Calculate approximate memory usage for all context data
        conversation_size = sum(sys.getsizeof(str(item)) for item in self.conversation_history)
        handler_contexts_size = sum(sys.getsizeof(str(ctx)) for ctx in self.handler_contexts.values())
        active_actions_size = sum(sys.getsizeof(str(action)) for action in self.active_actions.values())
        recent_actions_size = sum(sys.getsizeof(str(action)) for action in self.recent_actions)
        failed_actions_size = sum(sys.getsizeof(str(action)) for action in self.failed_actions)
        metadata_size = sys.getsizeof(str(self.client_metadata))
        devices_size = sum(sys.getsizeof(str(device)) for device in self.available_devices)
        
        total_bytes = (
            conversation_size + handler_contexts_size + active_actions_size +
            recent_actions_size + failed_actions_size + metadata_size + devices_size
        )
        
        return {
            "total_bytes": total_bytes,
            "total_mb": total_bytes / (1024 * 1024),
            "breakdown": {
                "conversation_history": {
                    "entries": len(self.conversation_history),
                    "bytes": conversation_size
                },
                "handler_contexts": {
                    "handlers": len(self.handler_contexts),
                    "bytes": handler_contexts_size
                },
                "active_actions": {
                    "entries": len(self.active_actions),
                    "bytes": active_actions_size
                },
                "recent_actions": {
                    "entries": len(self.recent_actions),
                    "bytes": recent_actions_size
                },
                "failed_actions": {
                    "entries": len(self.failed_actions),
                    "bytes": failed_actions_size
                },
                "client_metadata": {
                    "bytes": metadata_size
                },
                "available_devices": {
                    "entries": len(self.available_devices),
                    "bytes": devices_size
                }
            }
        }
    except Exception as e:
        return {
            "total_bytes": 0,
            "total_mb": 0.0,
            "error": str(e),
            "breakdown": {}
        }
```

**Validation:**
- Memory usage estimation works with unified context
- No AttributeError exceptions in MemoryManager logs
- Memory analysis includes all context data (conversation history, handler contexts, action tracking)
- MemoryManager monitoring endpoints return correct data
- Memory cleanup and alerts work with unified context structure

### **Phase 2: Fix Donation-Routing Compatibility**

#### **2.1 Fix Method Signatures**

**Problem:** Methods expecting 3 parameters incompatible with donation routing (2 parameters)

**Target Methods in `ConversationIntentHandler`:**
- `_handle_start_conversation(intent, context, session)` → `_handle_start_conversation(intent, context)`
- `_handle_end_conversation(intent, context, session)` → `_handle_end_conversation(intent, context)`  
- `_handle_clear_conversation(intent, context, session)` → `_handle_clear_conversation(intent, context)`
- `_handle_reference_query(intent, session)` → `_handle_reference_query(intent, context)`

**Solution:**
```python
# Before (incompatible)
async def _handle_start_conversation(self, intent: Intent, context: ConversationContext, session: ConversationSession):
    session.clear_history(keep_system=True)
    # ...

# After (donation-compatible)
async def _handle_start_conversation(self, intent: Intent, context: UnifiedConversationContext):
    # Access handler-specific context instead of separate session object
    context.clear_handler_context("conversation", keep_system=True)
    # ...
```

#### **2.2 Remove Session Management Code**

**From `ConversationIntentHandler`:**
- Remove `self.sessions: Dict[str, ConversationSession]` 
- Remove `_get_or_create_session()` method
- Remove session parameter passing in `execute()` method
- Update all handler methods to use unified context directly (no compatibility layer needed)

### **Phase 3: Localization System Implementation**

#### **3.1 Create Device Type Localization Files**

**File:** `assets/localization/devices/en.yaml` (new)
```yaml
device_types:
  light:
    keywords: [light, lamp, bulb, lighting, illumination]
    aliases: [lights, lamps, bulbs]
  speaker:
    keywords: [speaker, audio, sound, music player]
    aliases: [speakers, audio system]
  tv:
    keywords: [tv, television, screen, display]
    aliases: [television, telly, monitor]
  switch:
    keywords: [switch, outlet, plug, socket]
    aliases: [switches, outlets, plugs]
  sensor:
    keywords: [sensor, detector, monitor]
    aliases: [sensors, detectors]
  camera:
    keywords: [camera, cam, webcam]
    aliases: [cameras, cams]
```

**File:** `assets/localization/devices/ru.yaml` (new)
```yaml
device_types:
  light:
    keywords: [свет, лампа, лампочка, светильник, освещение, подсветка]
    aliases: [светы, лампы, лампочки]
  speaker:
    keywords: [колонка, динамик, аудио, звук, музыка]
    aliases: [колонки, динамики]
  tv:
    keywords: [телевизор, тв, экран, дисплей, монитор]
    aliases: [телевизоры, мониторы]
  switch:
    keywords: [выключатель, переключатель, розетка, штепсель]
    aliases: [выключатели, розетки]
  sensor:
    keywords: [датчик, сенсор, детектор, измеритель]
    aliases: [датчики, сенсоры]
  camera:
    keywords: [камера, видеокамера, веб-камера, вебкамера]
    aliases: [камеры, вебкамеры]
```

#### **3.2 Create Room Localization Files**

**File:** `assets/localization/rooms/en.yaml` (new)
```yaml
room_keywords:
  here_indicators:
    - "here"
    - "this room"
    - "current room"
    - "in here"
  
  room_aliases:
    kitchen:
      - "kitchen"
      - "cook area"
      - "cooking space"
    living_room:
      - "living room"
      - "lounge"
      - "main room"
      - "family room"
    bedroom:
      - "bedroom"
      - "bed room"
      - "sleeping room"
    bathroom:
      - "bathroom"
      - "bath"
      - "restroom"
```

**File:** `assets/localization/rooms/ru.yaml` (new)
```yaml
room_keywords:
  here_indicators:
    - "здесь"
    - "тут"
    - "в этой комнате"
    - "в комнате"
    - "сюда"
  
  room_aliases:
    kitchen:
      - "кухня"
      - "кухне"
      - "на кухне"
    living_room:
      - "гостиная"
      - "зал"
      - "гостиной"
      - "в зале"
    bedroom:
      - "спальня"
      - "спальне"
      - "в спальне"
    bathroom:
      - "ванная"
      - "туалет"
      - "в ванной"
```

#### **3.3 Update Entity Resolvers**

**File:** `irene/core/entity_resolver.py` (modify)

```python
class DeviceEntityResolver:
    def __init__(self, asset_loader: IntentAssetLoader):
        self.asset_loader = asset_loader
        self.logger = logging.getLogger(f"{__name__}.DeviceEntityResolver")
    
    def _load_device_types(self, language: str = "en") -> Dict[str, List[str]]:
        """Load device type keywords from localization files"""
        device_localization = self.asset_loader.localizations.get("devices", {})
        device_data = device_localization.get(language, {})
        
        if not device_data and language != "en":
            # Fallback to English
            device_data = device_localization.get("en", {})
        
        device_types = device_data.get("device_types", {})
        
        # Convert to expected format
        result = {}
        for device_type, config in device_types.items():
            keywords = config.get("keywords", [])
            aliases = config.get("aliases", [])
            result[device_type] = keywords + aliases
        
        return result
```

```python
class LocationEntityResolver:
    def __init__(self, asset_loader: IntentAssetLoader):
        self.asset_loader = asset_loader
        self.logger = logging.getLogger(f"{__name__}.LocationEntityResolver")
    
    def _load_location_keywords(self, language: str = "en") -> Dict[str, List[str]]:
        """Load location keywords from localization files"""
        room_localization = self.asset_loader.localizations.get("rooms", {})
        room_data = room_localization.get(language, {})
        
        if not room_data and language != "en":
            # Fallback to English
            room_data = room_localization.get("en", {})
        
        return room_data.get("room_keywords", {})
```

#### **3.4 Add Room Aliases API Endpoint**

**File:** `irene/components/nlu_component.py` (modify existing `get_router()` method)

**Purpose:** Provide ESP32 and external clients with valid room identifiers for session management.

```python
# Add to existing NLUComponent.get_router() method
@router.get("/room_aliases", response_model=RoomAliasesResponse)
async def get_room_aliases(language: str = "en"):
    """Get valid room aliases/IDs from localization files
    
    Returns list of room identifiers that can be used for:
    - ESP32 room_id parameter in config messages
    - Session ID generation (room_id + "_session")
    - Room-scoped context management
    """
    try:
        # Access localization data through asset loader
        if not hasattr(self, 'asset_loader') or not self.asset_loader:
            raise HTTPException(503, "Asset loader not available")
        
        room_localization = self.asset_loader.localizations.get("rooms", {})
        room_data = room_localization.get(language, {})
        
        # Fallback to English if requested language not available
        if not room_data and language != "en":
            room_data = room_localization.get("en", {})
            language = "en"  # Update language to reflect fallback
        
        # Extract room aliases (keys from room_aliases section)
        room_aliases_data = room_data.get("room_keywords", {}).get("room_aliases", {})
        room_ids = list(room_aliases_data.keys()) if room_aliases_data else []
        
        return RoomAliasesResponse(
            success=True,
            room_aliases=room_ids,
            language=language,
            fallback_language="en",
            total_count=len(room_ids)
        )
        
    except Exception as e:
        logger.error(f"Failed to get room aliases: {e}")
        raise HTTPException(500, f"Failed to retrieve room aliases: {str(e)}")
```

**File:** `irene/api/schemas.py` (add new response model)

```python
class RoomAliasesResponse(BaseModel):
    """Response model for room aliases endpoint"""
    success: bool
    room_aliases: List[str]  # List of valid room IDs: ["kitchen", "living_room", ...]
    language: str           # Language used for response
    fallback_language: str  # Fallback language if requested not available
    total_count: int        # Number of room aliases returned
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "room_aliases": ["kitchen", "living_room", "bedroom", "bathroom"],
                "language": "en",
                "fallback_language": "en",
                "total_count": 4
            }
        }
```

**API Usage:**
```bash
# Get room aliases in English (default)
GET /nlu/room_aliases

# Get room aliases in Russian
GET /nlu/room_aliases?language=ru

# Response format
{
  "success": true,
  "room_aliases": ["kitchen", "living_room", "bedroom", "bathroom"],
  "language": "en",
  "fallback_language": "en",
  "total_count": 4
}
```

**Integration Benefits:**
- **ESP32 Integration:** ESP32 can query valid room IDs before sending config messages
- **Session Management:** Provides valid room identifiers for `SessionManager.generate_session_id()`
- **Validation:** External clients can validate room IDs before use
- **Multi-language Support:** Supports localized room identifiers
- **Consistent API:** Follows existing NLU component endpoint patterns

### **Phase 4: Session ID Unification**

#### **4.1 Create Unified Session ID Generator**

**File:** `irene/core/session_manager.py` (new)
```python
class SessionManager:
    """Unified session ID generation and management across all components"""
    
    @staticmethod
    def generate_session_id(source: str, room_id: Optional[str] = None, 
                           client_id: Optional[str] = None) -> str:
        """Generate consistent session ID across all components
        
        Single-user system: Room sessions represent physical locations.
        """
        if room_id:
            return f"{room_id}_session"  # "kitchen_session"
        elif client_id:
            return f"{client_id}_session"  # "browser_abc123_session"
        else:
            return f"{source}_{uuid.uuid4().hex[:8]}_session"  # "web_a1b2c3d4_session"
        
    def validate_session_id(self, session_id: str) -> bool:
        """Validate session ID format and structure"""
        return "_session" in session_id
        
    def extract_room_from_session(self, session_id: str) -> Optional[str]:
        """Extract room identifier from session ID if present"""
        if session_id.endswith("_session"):
            room_part = session_id[:-8]  # Remove "_session"
            # Check if it looks like a room ID (not a UUID)
            if not any(c.isdigit() for c in room_part[-8:]):
                return room_part
        return None
```

**Session ID Format Strategy (Room-Scoped):**
- Room-based: `{room_id}_session` (e.g., "kitchen_session") - **PRIMARY for IoT**
- Client-based: `{client_id}_session` (e.g., "browser_abc123_session") - For web clients
- Generated: `{source}_{uuid8}_session` (e.g., "web_a1b2c3d4_session") - Fallback

> 🎯 **Key Principle:** Session IDs remain room/client-scoped to preserve fire-and-forget action boundaries and contextual command resolution within physical locations.

#### **4.2 Update All Components**

**Target Components:**
- `ASRComponent` - Replace WebSocket session generation
- `TTSComponent` - Replace `f"tts_session_{uuid.hex[:8]}"`
- `WorkflowManager` - Replace hardcoded `"audio_session"`, `"default"`
- `WebAPIRouter` - Replace hardcoded session IDs

**Implementation:**
- Import and use `SessionManager.generate_session_id()` in all components
- Replace hardcoded session ID generation across all components
- Update all components to use unified session management

### **Phase 5: Enhanced Context Integration**

#### **5.1 Enhance RequestContext → ConversationContext Flow**

**File:** `irene/intents/context.py` (modify)

```python
async def get_context_with_request_info(self, session_id: str, request_context: 'RequestContext' = None) -> UnifiedConversationContext:
    """Enhanced context creation with proper room context injection
    
    CRITICAL: Preserves room-scoped session boundaries for fire-and-forget actions
    and contextual command resolution.
    """
    
    # Extract room information from multiple sources
    room_id = None
    room_name = None
    
    if request_context:
        # Priority 1: Explicit room information
        room_id = getattr(request_context, 'client_id', None)
        room_name = getattr(request_context, 'room_name', None)
        
        # Priority 2: Extract from session ID if room-based
        if not room_id:
            room_id = SessionManager().extract_room_from_session(session_id)
            
        # Priority 3: Extract from device context
        if not room_name and request_context.device_context:
            room_name = request_context.device_context.get('room_name')
    
    # Create unified context with room information
    context = UnifiedConversationContext(
        session_id=session_id,
        client_id=room_id,
        room_name=room_name,
        # ... other fields
    )
    
    # Populate with device context if available
    if request_context and request_context.device_context:
        context.available_devices = request_context.device_context.get("available_devices", [])
        context.client_metadata["device_capabilities"] = request_context.device_context.get("device_capabilities", {})
```

#### **5.2 Update NLU Context Enhancement**

**File:** `irene/components/nlu_component.py` (modify)

```python
async def _enhance_with_context(self, intent: Intent, context: UnifiedConversationContext, 
                               resolved_entities: Dict[str, Any]) -> Intent:
    """Enhanced context injection using unified context"""
    
    enhanced_entities = resolved_entities.copy()
    
    # 1. Room Context Injection (simplified with unified context)
    if context.client_id:
        enhanced_entities["client_id"] = context.client_id
        enhanced_entities["room_id"] = context.client_id  # Explicit room ID
        
    if context.room_name:
        enhanced_entities["room_name"] = context.room_name
        self.logger.debug(f"Added room context: {context.room_name}")
    
    # 2. Device Entity Resolution (enhanced with localized mappings)
    enhanced_entities = await self._resolve_device_entities(enhanced_entities, context)
    
    # ... rest of enhancement logic
```

#### **5.3 Add Room Alias Support to API Endpoints**

**File:** `irene/api/schemas.py` (modify existing `CommandRequest`)

**Purpose:** Enable room-scoped command execution through `/execute/command` and `/trace/command` endpoints.

```python
class CommandRequest(BaseAPIRequest):
    """Request to execute a command with optional room context"""
    command: str = Field(description="Command text to execute")
    room_alias: Optional[str] = Field(
        default=None,
        description="Optional room identifier for room-scoped execution (e.g., 'kitchen', 'living_room')"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional command metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "command": "turn off the lights",
                "room_alias": "kitchen",
                "metadata": {"source": "mobile_app"}
            }
        }
```

**File:** `irene/runners/webapi_router.py` (modify existing endpoints)

**Add Room Alias Validation Function:**
```python
async def _validate_and_resolve_room_alias(
    room_alias: str, 
    asset_loader: Optional[IntentAssetLoader]
) -> tuple[bool, str]:
    """Validate room alias against localization files and return session_id
    
    Args:
        room_alias: Room identifier to validate (e.g., 'kitchen')
        asset_loader: Asset loader for accessing room localization data
        
    Returns:
        Tuple of (is_valid, session_id_or_error_message)
    """
    if not asset_loader:
        return False, f"Room alias '{room_alias}' cannot be validated - asset loader unavailable"
    
    try:
        # Get room aliases from localization files
        room_localization = asset_loader.localizations.get("rooms", {})
        room_data = room_localization.get("en", {})  # Default to English
        
        # Fallback to Russian if English not available
        if not room_data:
            room_data = room_localization.get("ru", {})
        
        room_aliases = room_data.get("room_keywords", {}).get("room_aliases", {})
        
        if room_alias not in room_aliases:
            available_aliases = list(room_aliases.keys())
            return False, f"Invalid room alias '{room_alias}'. Valid aliases: {available_aliases}"
        
        # Generate session_id using SessionManager from Phase 4
        from ..core.session_manager import SessionManager
        session_id = SessionManager.generate_session_id("api", room_id=room_alias)
        
        return True, session_id
        
    except Exception as e:
        return False, f"Room alias validation failed: {str(e)}"
```

**Update `/execute/command` Endpoint:**
```python
@router.post("/execute/command", response_model=CommandResponse, tags=["General"])
async def execute_command(request: CommandRequest):
    """Execute a voice assistant command via REST API with optional room context"""
    try:
        if not core:
            raise HTTPException(status_code=503, detail="Assistant not initialized")
        
        # NEW: Room alias validation and session_id generation
        if request.room_alias:
            is_valid, session_id_or_error = await _validate_and_resolve_room_alias(
                request.room_alias, asset_loader
            )
            if not is_valid:
                raise HTTPException(status_code=400, detail=session_id_or_error)
            
            session_id = session_id_or_error
            client_id = request.room_alias
            logger.debug(f"Using room-scoped session: {session_id} for room '{request.room_alias}'")
        else:
            # Existing behavior - use metadata or fallback
            session_id = request.metadata.get("session_id", "default_session") if request.metadata else "default_session"
            client_id = None
        
        # Enhanced client context with room information
        client_context = {
            "source": "api",
            "room_alias": request.room_alias,
            "client_id": client_id
        }
        if request.metadata:
            client_context.update(request.metadata)
        
        # Execute command with enhanced context
        result = await core.workflow_manager.process_text_input(
            text=request.command,
            session_id=session_id,
            wants_audio=False,
            client_context=client_context
        )
        
        return CommandResponse(
            success=True,
            response=result.text or "Command executed successfully",
            session_id=session_id,
            room_alias=request.room_alias,  # NEW: Include room alias in response
            metadata={
                "intent_name": result.intent_name,
                "confidence": result.confidence,
                "execution_time": result.metadata.get("execution_time") if result.metadata else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Command execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Command execution failed: {str(e)}")
```

**Update `/trace/command` Endpoint:**
```python
@router.post("/trace/command", response_model=TraceCommandResponse, tags=["Tracing"])
async def trace_command_execution(request: CommandRequest):
    """Execute command with full execution trace and optional room context"""
    try:
        if not core:
            raise HTTPException(status_code=503, detail="Assistant not initialized")
        
        # NEW: Room alias validation and session_id generation (same as execute)
        if request.room_alias:
            is_valid, session_id_or_error = await _validate_and_resolve_room_alias(
                request.room_alias, asset_loader
            )
            if not is_valid:
                raise HTTPException(status_code=400, detail=session_id_or_error)
            
            session_id = session_id_or_error
            client_id = request.room_alias
        else:
            session_id = request.metadata.get("session_id", "trace_session") if request.metadata else "trace_session"
            client_id = None
        
        # Create trace context for detailed execution tracking
        trace_context = TraceContext(
            enabled=True, 
            request_id=str(uuid.uuid4()),
            max_stages=50,
            max_data_size_mb=5
        )
        
        # Enhanced client context with room information and tracing
        client_context = {
            "source": "trace_api", 
            "trace_enabled": True,
            "room_alias": request.room_alias,
            "client_id": client_id
        }
        if request.metadata:
            client_context.update(request.metadata)
        
        # Execute with tracing and room context
        result = await core.workflow_manager.process_text_input(
            text=request.command,
            session_id=session_id,
            wants_audio=False,
            client_context=client_context,
            trace_context=trace_context
        )
        
        return TraceCommandResponse(
            success=True,
            final_result=result,
            execution_trace=trace_context.to_dict(),
            session_id=session_id,
            room_alias=request.room_alias,  # NEW: Include room alias in trace response
            metadata={
                "trace_id": trace_context.request_id,
                "total_stages": len(trace_context.stages),
                "execution_time": trace_context.total_duration
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trace execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Trace execution failed: {str(e)}")
```

**Update `/execute/audio` Endpoint:**
```python
@router.post("/execute/audio", response_model=CommandResponse, tags=["General"])
async def execute_audio(audio_file: UploadFile = File(...), room_alias: Optional[str] = None):
    """Execute audio processing via REST API with optional room context"""
    try:
        if not core:
            raise HTTPException(status_code=503, detail="Assistant not initialized")
        
        # NEW: Room alias validation and session_id generation
        if room_alias:
            is_valid, session_id_or_error = await _validate_and_resolve_room_alias(
                room_alias, asset_loader
            )
            if not is_valid:
                raise HTTPException(status_code=400, detail=session_id_or_error)
            
            session_id = session_id_or_error
            client_id = room_alias
            logger.debug(f"Using room-scoped session: {session_id} for audio in room '{room_alias}'")
        else:
            # Existing behavior - hardcoded session
            session_id = "audio_session"
            client_id = None
        
        # Validate file size (limit to 10MB for safety)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_size = 0
        audio_data = b""
        
        # Read audio data with size check
        while True:
            chunk = await audio_file.read(8192)  # Read in 8KB chunks
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, 
                    detail=f"Audio file too large (max {MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"
                )
            audio_data += chunk
        
        logger.info(f"Audio processing: {audio_file.filename}, size: {file_size} bytes, room: {room_alias or 'none'}")
        
        # Enhanced client context with room information
        client_context = {
            "source": "audio_api",
            "filename": audio_file.filename,
            "skip_wake_word": True,  # Skip wake word for uploaded files
            "file_size_bytes": file_size,
            "room_alias": room_alias,
            "client_id": client_id
        }
        
        # Process audio through workflow manager with enhanced context
        result = await core.workflow_manager.process_audio_input(
            audio_data=audio_data,
            session_id=session_id,
            wants_audio=False,  # Don't generate TTS for API endpoint
            client_context=client_context
        )
        
        return CommandResponse(
            success=result.success,
            response=result.text or f"Audio file '{audio_file.filename}' processed successfully",
            session_id=session_id,
            room_alias=room_alias,  # NEW: Include room alias in response
            metadata={
                "processed_via": "audio_api", 
                "filename": audio_file.filename, 
                "file_size_bytes": file_size,
                "room_context": bool(room_alias)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Audio processing failed: {str(e)}")
```

**Update `/trace/audio` Endpoint:**
```python
@router.post("/trace/audio", response_model=TraceCommandResponse, tags=["Tracing"])
async def trace_audio_execution(audio_file: UploadFile = File(...), room_alias: Optional[str] = None):
    """Execute audio processing with full execution trace and optional room context"""
    try:
        if not core:
            raise HTTPException(status_code=503, detail="Assistant not initialized")
        
        # NEW: Room alias validation and session_id generation (same as execute/audio)
        if room_alias:
            is_valid, session_id_or_error = await _validate_and_resolve_room_alias(
                room_alias, asset_loader
            )
            if not is_valid:
                raise HTTPException(status_code=400, detail=session_id_or_error)
            
            session_id = session_id_or_error
            client_id = room_alias
        else:
            session_id = "trace_audio_session"
            client_id = None
        
        # Validate file size (limit to 10MB for safety)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        file_size = 0
        audio_data = b""
        
        # Read audio data with size check
        while True:
            chunk = await audio_file.read(8192)  # Read in 8KB chunks
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413, 
                    detail=f"Audio file too large (max {MAX_FILE_SIZE / 1024 / 1024:.1f}MB)"
                )
            audio_data += chunk
        
        # Create trace context with production limits for audio
        trace_context = TraceContext(
            enabled=True, 
            request_id=str(uuid.uuid4()),
            max_stages=75,  # More stages for audio processing
            max_data_size_mb=15  # Higher limit for audio traces (includes audio data)
        )
        
        logger.info(f"Trace audio processing: {audio_file.filename}, size: {file_size} bytes, room: {room_alias or 'none'}")
        
        # Enhanced client context with room information and tracing
        client_context = {
            "source": "trace_audio_api",
            "filename": audio_file.filename,
            "skip_wake_word": True,  # Skip wake word for uploaded files
            "file_size_bytes": file_size,
            "trace_enabled": True,
            "room_alias": room_alias,
            "client_id": client_id
        }
        
        # Process audio through workflow manager with tracing and room context
        result = await core.workflow_manager.process_audio_input(
            audio_data=audio_data,
            session_id=session_id,
            wants_audio=False,  # Don't generate TTS for trace endpoint
            client_context=client_context,
            trace_context=trace_context
        )
        
        return TraceCommandResponse(
            success=result.success,
            final_result=result,
            execution_trace=trace_context.to_dict(),
            session_id=session_id,
            room_alias=room_alias,  # NEW: Include room alias in trace response
            metadata={
                "trace_id": trace_context.request_id,
                "total_stages": len(trace_context.stages),
                "execution_time": trace_context.total_duration,
                "filename": audio_file.filename,
                "file_size_bytes": file_size,
                "room_context": bool(room_alias)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trace audio execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Audio trace execution failed: {str(e)}")
```

**Update Response Models:**
```python
# In irene/api/schemas.py - Update existing response models
class CommandResponse(BaseAPIResponse):
    """Response from command execution"""
    response: str = Field(description="Command execution result")
    session_id: str = Field(description="Session ID used for execution")
    room_alias: Optional[str] = Field(default=None, description="Room alias used for execution")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional response metadata")

class TraceCommandResponse(BaseAPIResponse):
    """Response for trace command execution with complete pipeline visibility"""
    final_result: IntentResult = Field(description="Final command execution result")
    execution_trace: ExecutionTrace = Field(description="Complete pipeline execution trace")
    session_id: str = Field(description="Session ID used for execution")
    room_alias: Optional[str] = Field(default=None, description="Room alias used for execution")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional trace metadata")
```

**API Usage Examples:**
```bash
# Room-scoped command execution
POST /execute/command
{
  "command": "turn off the lights",
  "room_alias": "kitchen"
}
# Response includes room context and uses "kitchen_session"

# Room-scoped audio execution
POST /execute/audio?room_alias=kitchen
# Form data: audio_file=@recording.wav
# Processes audio with kitchen room context

# Room-scoped trace execution
POST /trace/command
{
  "command": "start timer 5 minutes",
  "room_alias": "living_room"
}
# Full execution trace with room context injection

# Room-scoped audio trace execution
POST /trace/audio?room_alias=living_room
# Form data: audio_file=@voice_command.wav
# Full audio processing trace with room context

# Traditional usage (unchanged)
POST /execute/command
{
  "command": "what time is it",
  "metadata": {"session_id": "my_session"}
}
# Backward compatible - no room context

# Traditional audio usage (unchanged)
POST /execute/audio
# Form data: audio_file=@recording.wav
# Uses default "audio_session" - no room context
```

**Integration Benefits:**
- **ESP32 Ready:** ESP32 can use same room aliases for both text and audio API calls
- **Session Consistency:** Uses SessionManager from Phase 4 for consistent session IDs across all endpoints
- **Room Context:** Automatic room context injection for device commands in both text and audio processing
- **Validation:** Prevents invalid room aliases with clear error messages on all endpoints
- **API Compatible:** Existing API usage continues to work unchanged for all endpoints
- **Complete Coverage:** Room alias support for all execution endpoints: `/execute/command`, `/execute/audio`, `/trace/command`, `/trace/audio`
- **Trace Support:** Full execution tracing with room context visibility for both text and audio processing
- **Audio Processing:** Room-scoped audio file processing enables location-aware voice commands

### **Phase 6: Code Cleanup and Removal**

#### **6.1 Remove Old Classes**

**After migration is complete and tested:**

1. **Remove `ConversationSession` class:**
   - Delete from `irene/intents/handlers/conversation.py`
   - Remove all references and imports

2. **Remove old `ConversationContext` class:**
   - Replace with `UnifiedConversationContext` in `irene/intents/models.py`
   - Update all imports across the codebase

3. **Remove session management methods:**
   - Delete `_get_or_create_session()` from `ConversationIntentHandler`
   - Remove `self.sessions` dictionary management
   - Clean up session parameter passing

4. **Replace hardcoded session IDs with SessionManager:**
   - Replace `"audio_session"` in `webapi_router.py` with `SessionManager.generate_session_id("api")`
   - Replace `"trace_session"` in `webapi_router.py` with `SessionManager.generate_session_id("trace")`
   - Replace `"trace_audio_session"` in `webapi_router.py` with `SessionManager.generate_session_id("trace_audio")`
   - Replace `"cli_session"` in `runners/cli.py` with `SessionManager.generate_session_id("cli")`
   - Replace `"vosk_session"` in `runners/vosk_runner.py` with `SessionManager.generate_session_id("vosk")`
   - Update demo and example files to use SessionManager

5. **Clean up imports and references:**
   - Remove `ConversationSession` imports from `examples/conversation_demo.py`
   - Update all `from ..models import ConversationContext` to import `UnifiedConversationContext`
   - Remove unused imports after class removal
   - Update type hints and annotations

#### **6.2 Remove Hardcoded Mappings**

**From `irene/core/entity_resolver.py`:**
```python
# Remove these hardcoded dictionaries:
device_types = {
    "light": ["light", "lamp", "свет", "лампа", ...],  # DELETE
    "speaker": ["speaker", "колонка", ...],            # DELETE
    # ... all hardcoded mappings
}

here_keywords = ["here", "this room", "здесь", ...]   # DELETE
```

**Replace with:**
```python
# Load from localization files instead
self.device_types = self._load_device_type_mappings()
self.location_keywords = self._load_location_keywords()
```

#### **6.3 Update Test Files**

**Files requiring updates after context unification:**

1. **Update integration tests:**
   - `tests/test_phase1_integration.py` - Update `ConversationContext` imports and usage
   - `tests/test_phase4_integration.py` - Update context handling patterns
   - `tests/test_tts_audio_separation.py` - Update session ID handling
   - `tests/test_cascading_nlu.py` - Update context passing

2. **Update example files:**
   - `examples/conversation_demo.py` - Remove `ConversationSession` usage
   - `examples/component_demo.py` - Update hardcoded session IDs
   - `examples/config_demo.py` - Update session management examples

3. **Update configuration schemas:**
   - Review `ConversationHandlerConfig` for session-related fields
   - Update session timeout configurations to work with unified context
   - Remove session management configuration options that are no longer needed

#### **6.4 Update Documentation**

1. **Update architecture documentation** to reflect unified context
2. **Update API documentation** for new context structure and room alias support
3. **Update developer guides** for new session management and SessionManager usage
4. **Add localization documentation** for room/device mappings
5. **Update migration guides** for developers upgrading existing handlers
6. **Document SessionManager API** for consistent session ID generation

## Testing Strategy

### **Phase Testing Requirements**

1. **Session ID Consistency (Room-Scoped):**
   - Verify same session ID used across all components for single room session
   - Test room-based session ID generation and extraction
   - Validate session ID format and structure consistency
   - **CRITICAL:** Ensure different rooms have different session IDs

2. **Context Unification (Fire-and-Forget Safe):**
   - Test all intent handlers work with unified context
   - Verify donation-routing compatibility restored
   - Test unified context functionality matches old behavior
   - **CRITICAL:** Verify active action tracking preserved with unified context

3. **Room Context Flow:**
   - Test room information flows from request to intent execution
   - Verify device resolution uses room context correctly
   - Test localized device/room keyword matching
   - **CRITICAL:** Test room boundaries for device resolution

4. **Fire-and-Forget System Integrity:**
   - **Multi-room action independence:** Kitchen timer + living room music in separate contexts
   - **Contextual command resolution:** "stop" targets correct room's actions
   - **Cross-room isolation:** Commands in kitchen don't affect living room actions
   - **Action lifecycle preservation:** Start, track, complete, cancel actions work correctly

5. **TODO16 Compatibility:**
   - Test contextual command disambiguation within room scope
   - Verify domain priority resolution works with unified context
   - Test ambiguous command resolution (multiple active actions in same room)
   - Verify recent action fallback logic preserved

6. **Localization:**
   - Test device type resolution in multiple languages
   - Verify room keyword matching across language files
   - Test fallback behavior when localization files missing
   - **NEW:** Test room aliases API endpoint with multiple languages
   - **NEW:** Validate room aliases endpoint returns correct room IDs for session management

7. **Room Alias API Integration (Phase 5):**
   - **Room alias validation:** Test valid and invalid room aliases in all four endpoints: `/execute/command`, `/execute/audio`, `/trace/command`, `/trace/audio`
   - **Session ID generation:** Verify room aliases generate correct session IDs (e.g., "kitchen" → "kitchen_session") for both text and audio endpoints
   - **Error handling:** Test clear error messages for invalid room aliases with available alternatives on all endpoints
   - **API compatibility:** Ensure existing API usage without room_alias continues to work for all endpoints
   - **Room context injection:** Verify room aliases properly inject room context into both text and audio command execution
   - **Audio file processing:** Test room-scoped audio file processing with proper context injection
   - **Trace integration:** Test room alias support in both text and audio trace endpoints with full context visibility
   - **Multi-language support:** Test room alias validation across different localization languages for all endpoints
   - **Parameter handling:** Test room_alias as query parameter for audio endpoints vs JSON body for command endpoints

## Success Criteria

1. ✅ **Room-scoped Session IDs** used consistently across all components
2. ✅ **Unified Context** replaces dual context architecture while preserving functionality
3. ✅ **Donation-routing compatibility** restored for all intent handlers
4. ✅ **Room context flows** properly from input to intent execution
5. ✅ **Fire-and-forget system preserved:** Multi-room action tracking works correctly
6. ✅ **TODO16 compatibility:** Contextual command resolution works within room boundaries
7. ✅ **Cross-room isolation:** Actions in different rooms remain independent
8. ✅ **Localized mappings** replace all hardcoded device/location keywords
9. ✅ **Legacy code removed** after successful migration
10. ✅ **Full test coverage** including fire-and-forget and contextual resolution scenarios

### **Critical Success Validation Scenarios:**

**Scenario 1: Multi-Room Action Independence**
```
Kitchen: User starts timer → active_actions["timers"] in kitchen_session
Living Room: User starts music → active_actions["audio"] in living_room_session
Kitchen: User says "stop" → Targets kitchen timer, not living room music
```

**Scenario 2: Room-Scoped Device Resolution**
```
Kitchen: "Turn off the light" → Resolves to kitchen light using room context
Living Room: "Turn off the light" → Resolves to living room light using room context
```

**Scenario 3: Contextual Command Disambiguation**
```
Kitchen: Timer + Music both active → "stop" command uses domain priorities
Result: Targets higher priority domain within kitchen context only
```

## Migration Timeline

- **Phase 1:** 1-2 weeks (Context architecture unification)
- **Phase 2:** 1 week (Fix donation-routing compatibility) 
- **Phase 3:** 1 week (Localization system implementation)
- **Phase 4:** 1 week (Session ID unification)
- **Phase 5:** 1 week (Enhanced context integration)
- **Phase 6:** 1 week (Cleanup and testing)

**Total Estimated Time:** 6-8 weeks

**Phase Dependencies:** Context unification → Donation-routing fixes → Localization (parallel with Session ID) → Context integration → Cleanup. Each phase builds on previous foundations with direct replacement approach.

## Future Enhancements

After core unification is complete:

1. **Smart Home Intent Handlers** - Implement handlers that leverage the room context system
2. **ESP32 Protocol Integration** - Connect ESP32 room_id to unified session system (separate project)
3. **Cross-Room Coordination** - Optional features for "stop everything" commands across all rooms
4. **Context Persistence** - Save/restore unified context across system restarts
5. **Analytics Integration** - Room-based usage analytics and metrics
6. **Multi-User Support** - Future enhancement if needed (currently single-user system)

---

This plan provides a systematic approach to unifying the session and context architecture while preserving the sophisticated room-based context injection system that already exists in the codebase.
