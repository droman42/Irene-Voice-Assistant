# Client Registry System

**Complete guide to client identification, registration, and context-aware processing in Irene Voice Assistant**

---

## Overview

The Client Registry system provides unified client identification and capabilities management for all Irene Voice Assistant endpoints, including ESP32 nodes, web clients, mobile apps, and other system interfaces. It enables context-aware processing by maintaining room/device mappings and client capabilities.

### Key Features

- **Unified Registration API**: Single system for all client types (ESP32, web, mobile, etc.)
- **Room/Device Context**: Maps clients to physical locations and available devices
- **Capability Discovery**: Tracks what each client can do (voice input, audio output, etc.)
- **Persistent Storage**: Maintains client information across system restarts
- **Russian-First**: Supports Russian room names and device names as primary language
- **Context Propagation**: Flows client information through the entire processing pipeline

---

## Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ESP32 Node    │    │   Web Client    │    │  Mobile App     │
│   (Kitchen)     │    │   (Browser)     │    │   (Phone)       │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │            Client Registry                      │
         │  ┌─────────────────┐  ┌─────────────────┐       │
         │  │ ClientRegistry  │  │ ClientRegistration│      │
         │  │                 │  │                  │      │
         │  │ - register()    │  │ - client_id      │      │
         │  │ - get_client()  │  │ - room_name      │      │
         │  │ - get_rooms()   │  │ - devices[]      │      │
         │  │ - cleanup()     │  │ - capabilities   │      │
         │  └─────────────────┘  └─────────────────┘       │
         └─────────────────────────────────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │         Context-Aware Processing                │
         │  ┌─────────────────┐  ┌─────────────────┐       │
         │  │ RequestContext  │  │ConversationContext│     │
         │  │                 │  │                  │      │
         │  │ - client_id     │  │ - room_name      │      │
         │  │ - room_name     │  │ - devices[]      │      │
         │  │ - device_context│  │ - language       │      │
         │  └─────────────────┘  └─────────────────┘       │
         └─────────────────────────────────────────────────┘
```

### Data Models

#### ClientDevice
Represents a device available in a client's context:
```python
@dataclass
class ClientDevice:
    id: str                      # "light1", "sensor1", "speaker1"
    name: str                    # "Кухонный свет", "Датчик температуры"
    type: str                    # "light", "sensor", "speaker", "tv"
    capabilities: Dict[str, Any] # {"dimmable": True, "color": False}
    location: Optional[str]      # "Кухня"
    metadata: Dict[str, Any]     # Additional device info
```

#### ClientRegistration
Complete client registration with identity and capabilities:
```python
@dataclass
class ClientRegistration:
    client_id: str              # "kitchen_esp32", "web_living_room"
    room_name: str              # "Кухня", "Гостиная"
    language: str = "ru"        # Primary language
    client_type: str            # "esp32", "web", "mobile", "desktop"
    
    # Device capabilities
    available_devices: List[ClientDevice]
    
    # Client capabilities  
    capabilities: Dict[str, bool]  # {"voice_input": True, "audio_output": True}
    
    # Registration metadata
    registered_at: float
    last_seen: float
    source_address: Optional[str]  # IP address for ESP32 nodes
    user_agent: Optional[str]      # Browser info for web clients
```

---

## Usage Guide

### Basic Registration

#### ESP32 Node Registration
```python
from irene.core.client_registry import get_client_registry

registry = get_client_registry()

# Define available devices in the room
devices = [
    {
        "id": "light1",
        "name": "Кухонный свет",
        "type": "light",
        "capabilities": {"dimmable": True, "color": False}
    },
    {
        "id": "speaker1", 
        "name": "Умная колонка",
        "type": "speaker",
        "capabilities": {"volume_control": True, "bluetooth": True}
    },
    {
        "id": "sensor1",
        "name": "Датчик температуры",
        "type": "sensor", 
        "capabilities": {"temperature": True, "humidity": True}
    }
]

# Register ESP32 node
success = await registry.register_esp32_node(
    client_id="kitchen_esp32",
    room_name="Кухня", 
    devices=devices,
    source_address="192.168.1.100",
    language="ru"
)
```

#### Web Client Registration
```python
# Register web browser client
success = await registry.register_web_client(
    client_id="web_living_room",
    room_name="Гостиная",
    user_agent="Mozilla/5.0 (Chrome/96.0.4664.110)",
    language="ru"
)
```

### Client Discovery

#### Get Client Information
```python
# Get specific client
client = registry.get_client("kitchen_esp32")
if client:
    print(f"Room: {client.room_name}")
    print(f"Devices: {len(client.available_devices)}")
    print(f"Capabilities: {client.capabilities}")

# Find device by name
device = client.get_device_by_name("свет")  # Fuzzy matching works
if device:
    print(f"Found device: {device.name} ({device.type})")
```

#### Room-Based Discovery
```python
# Get all clients in a room
kitchen_clients = registry.get_clients_by_room("Кухня")
print(f"Kitchen has {len(kitchen_clients)} clients")

# Get all rooms
all_rooms = registry.get_all_rooms()
print(f"Registered rooms: {all_rooms}")

# Find devices by type across all clients
lights = registry.get_devices_by_type("light")
for client_id, light_device in lights:
    print(f"Light '{light_device.name}' in client '{client_id}'")
```

### Context-Aware Processing

#### Request Context Integration
```python
from irene.workflows.base import RequestContext
from irene.intents.context import ContextManager

# Create request with client information
request = RequestContext(
    source="esp32",
    session_id="user_session_123",
    client_id="kitchen_esp32",
    room_name="Кухня",
    device_context={
        "available_devices": [
            {"id": "light1", "name": "Кухонный свет", "type": "light"}
        ]
    },
    language="ru"
)

# Get conversation context with client info
context_manager = ContextManager()
conv_context = await context_manager.get_context_with_request_info(
    request.session_id, request
)

# Now conv_context has:
# - conv_context.client_id = "kitchen_esp32"
# - conv_context.get_room_name() = "Кухня"
# - conv_context.get_device_capabilities() = [device list]
# - conv_context.language = "ru"
```

---

## ESP32 Integration

### Firmware Registration Process

The ESP32 firmware should register with the server on startup and periodically update its presence:

#### 1. Initial Registration
```cpp
// ESP32 firmware pseudocode
void register_with_server() {
    // Prepare device list
    JsonDocument devices;
    devices[0]["id"] = "light1";
    devices[0]["name"] = "Кухонный свет";
    devices[0]["type"] = "light";
    devices[0]["capabilities"]["dimmable"] = true;
    
    devices[1]["id"] = "speaker1"; 
    devices[1]["name"] = "Колонка";
    devices[1]["type"] = "speaker";
    devices[1]["capabilities"]["volume_control"] = true;
    
    // Prepare registration message
    JsonDocument registration;
    registration["type"] = "esp32_registration";
    registration["client_id"] = CONFIG_NODE_ID;        // "kitchen_esp32"
    registration["room_name"] = CONFIG_ROOM_NAME;      // "Кухня"
    registration["language"] = "ru";
    registration["devices"] = devices;
    registration["source_address"] = get_local_ip();
    registration["firmware_version"] = APP_VERSION;
    
    // Send via WebSocket to server
    websocket_send(registration);
}
```

#### 2. Periodic Heartbeat
```cpp
void send_heartbeat() {
    JsonDocument heartbeat;
    heartbeat["type"] = "client_heartbeat";
    heartbeat["client_id"] = CONFIG_NODE_ID;
    heartbeat["timestamp"] = get_unix_timestamp();
    
    websocket_send(heartbeat);
}

// Call every 5 minutes
void heartbeat_task(void* params) {
    while (true) {
        send_heartbeat();
        vTaskDelay(pdMS_TO_TICKS(300000)); // 5 minutes
    }
}
```

#### 3. Device Status Updates
```cpp
void report_device_status_change(const char* device_id, const char* new_status) {
    JsonDocument status_update;
    status_update["type"] = "device_status_update";
    status_update["client_id"] = CONFIG_NODE_ID;
    status_update["device_id"] = device_id;
    status_update["status"] = new_status;
    status_update["timestamp"] = get_unix_timestamp();
    
    websocket_send(status_update);
}
```

### Server-Side ESP32 Handler

The server should handle ESP32 registration messages:

```python
# In WebSocket message handler
async def handle_esp32_registration(websocket, message: dict):
    """Handle ESP32 node registration"""
    try:
        client_id = message.get("client_id")
        room_name = message.get("room_name")
        devices = message.get("devices", [])
        source_address = message.get("source_address")
        language = message.get("language", "ru")
        
        registry = get_client_registry()
        success = await registry.register_esp32_node(
            client_id=client_id,
            room_name=room_name,
            devices=devices,
            source_address=source_address,
            language=language
        )
        
        response = {
            "type": "registration_response",
            "success": success,
            "client_id": client_id,
            "server_time": time.time()
        }
        
        await websocket.send_text(json.dumps(response))
        
    except Exception as e:
        error_response = {
            "type": "registration_error",
            "error": str(e)
        }
        await websocket.send_text(json.dumps(error_response))
```

### Configuration Integration

#### Node Configuration Template
ESP32 nodes should be configured with room and device information:

```yaml
# ESP32/firmware/nodes/kitchen/node_config.yaml
node:
  id: "kitchen_esp32"
  room_name: "Кухня"
  language: "ru"
  
network:
  wifi_ssid: "YourWiFi"
  server_host: "irene.local"
  server_port: 8765
  
devices:
  - id: "light1"
    name: "Кухонный свет"
    type: "light"
    gpio_pin: 5
    capabilities:
      dimmable: true
      color: false
      
  - id: "speaker1"
    name: "Колонка"
    type: "speaker"
    i2s_port: 0
    capabilities:
      volume_control: true
      bluetooth: false
      
  - id: "sensor1"
    name: "Датчик температуры"
    type: "sensor"
    gpio_pin: 18
    capabilities:
      temperature: true
      humidity: true
```

---

## Web Client Integration

### Browser Registration

Web clients can register using WebSocket messages:

```javascript
// Web client registration
const websocket = new WebSocket('ws://irene.local:8080/ws');

websocket.onopen = function() {
    // Register client
    const registration = {
        type: 'register_client',
        client_id: 'web_' + Math.random().toString(36).substr(2, 9),
        room_name: document.getElementById('room-select').value, // User selected
        language: 'ru',
        user_agent: navigator.userAgent,
        device_capabilities: {
            microphone: navigator.mediaDevices ? true : false,
            speaker: true,
            camera: navigator.mediaDevices ? true : false
        }
    };
    
    websocket.send(JSON.stringify(registration));
};

websocket.onmessage = function(event) {
    const response = JSON.parse(event.data);
    
    if (response.type === 'registration_success') {
        console.log('Registered as:', response.client_id);
        console.log('Room:', response.room_name);
        
        // Store client ID for future messages
        window.irene_client_id = response.client_id;
    }
};
```

### Sending Commands with Context

```javascript
function sendCommand(text) {
    const command = {
        type: 'voice_command',
        client_id: window.irene_client_id,
        text: text,
        timestamp: Date.now()
    };
    
    websocket.send(JSON.stringify(command));
}

// Example: "включи свет на кухне"
sendCommand("включи свет на кухне");
```

---

## Management and Monitoring

### Registry Statistics

```python
# Get registry statistics
stats = registry.get_registry_stats()
print(f"Total clients: {stats['total_clients']}")
print(f"Total rooms: {stats['total_rooms']}")
print(f"Total devices: {stats['total_devices']}")
print(f"Clients by type: {stats['clients_by_type']}")
print(f"Devices by type: {stats['devices_by_type']}")
```

### Cleanup Operations

```python
# Clean up expired clients (haven't been seen for > 1 hour)
expired_count = await registry.cleanup_expired_clients()
print(f"Cleaned up {expired_count} expired clients")

# Manually unregister a client
success = await registry.unregister_client("old_client_id")
```

### Persistent Storage

The registry automatically saves/loads client information:

```json
{
  "kitchen_esp32": {
    "client_id": "kitchen_esp32",
    "room_name": "Кухня", 
    "language": "ru",
    "client_type": "esp32",
    "available_devices": [
      {
        "id": "light1",
        "name": "Кухонный свет",
        "type": "light",
        "capabilities": {"dimmable": true}
      }
    ],
    "capabilities": {
      "voice_input": true,
      "audio_output": true,
      "local_processing": true
    },
    "registered_at": 1640995200.0,
    "last_seen": 1640995800.0,
    "source_address": "192.168.1.100"
  }
}
```

---

## Configuration

### Registry Configuration

```toml
# In your config.toml
[client_registry]
registration_timeout = 3600  # 1 hour
persistent_storage = true
storage_path = "cache/client_registry.json"
```

### Global Registry Initialization

```python
# Initialize with custom config
from irene.core.client_registry import initialize_client_registry

config = {
    "registration_timeout": 7200,  # 2 hours
    "persistent_storage": True,
    "storage_path": "data/clients.json"
}

registry = initialize_client_registry(config)
```

---

## Integration Examples

### Room-Based Device Control

```python
async def handle_device_command(intent, context):
    """Handle device control with room context"""
    
    # Get the room from context
    room_name = context.get_room_name()  # "Кухня"
    device_name = intent.entities.get("device", "")  # "свет"
    action = intent.entities.get("action", "")  # "включи"
    
    # Find clients in this room
    registry = get_client_registry()
    room_clients = registry.get_clients_by_room(room_name)
    
    # Search for the device across all clients in room
    target_device = None
    target_client = None
    
    for client in room_clients:
        device = client.get_device_by_name(device_name)
        if device:
            target_device = device
            target_client = client
            break
    
    if target_device:
        # Execute the action
        await execute_device_action(
            client_id=target_client.client_id,
            device_id=target_device.id,
            action=action
        )
        return f"Выполнено: {action} {target_device.name}"
    else:
        return f"Устройство '{device_name}' не найдено в комнате '{room_name}'"
```

### Multi-Room Announcements

```python
async def make_announcement(message: str, target_rooms: List[str] = None):
    """Send announcement to specific rooms or all rooms"""
    
    registry = get_client_registry()
    
    if target_rooms:
        # Send to specific rooms
        for room_name in target_rooms:
            clients = registry.get_clients_by_room(room_name)
            for client in clients:
                if client.capabilities.get("audio_output"):
                    await send_audio_message(client.client_id, message)
    else:
        # Send to all rooms with audio capability
        for client in registry.clients.values():
            if client.capabilities.get("audio_output"):
                await send_audio_message(client.client_id, message)
```

---

## Best Practices

### Security Considerations

1. **Client ID Validation**: Use secure, unique client IDs
2. **Source Verification**: Validate ESP32 nodes using mutual TLS
3. **Rate Limiting**: Prevent registration spam
4. **Input Sanitization**: Validate all device names and room names

### Performance Optimization

1. **Batch Operations**: Group multiple device updates
2. **Caching**: Cache frequently accessed room/device mappings
3. **Cleanup Scheduling**: Run expired client cleanup periodically
4. **Storage Optimization**: Use efficient JSON serialization

### Error Handling

1. **Registration Failures**: Retry with exponential backoff
2. **Network Issues**: Handle disconnections gracefully  
3. **Storage Errors**: Fallback to in-memory operation
4. **Invalid Data**: Validate all inputs and provide meaningful errors

---

## Migration from Existing Systems

### From Static Configuration

If you currently use static device configurations:

```python
# Old way (static config)
DEVICES = {
    "kitchen": ["light1", "speaker1"],
    "living_room": ["tv1", "light2"]
}

# New way (dynamic registration)
registry = get_client_registry()
kitchen_clients = registry.get_clients_by_room("Кухня")
devices = []
for client in kitchen_clients:
    devices.extend(client.available_devices)
```

### From Manual Context Management

```python
# Old way (manual context)
def get_room_devices(session_id):
    # Hardcoded logic...
    return []

# New way (automatic context)
async def process_command(request_context):
    context_manager = ContextManager()
    conv_context = await context_manager.get_context_with_request_info(
        request_context.session_id, request_context
    )
    
    # Context automatically populated with client information
    devices = conv_context.get_device_capabilities()
    room = conv_context.get_room_name()
```

---

## Troubleshooting

### Common Issues

#### Client Not Registering
- Check network connectivity
- Verify WebSocket URL and port
- Check for firewall blocking
- Validate JSON message format

#### Device Not Found
- Verify device name spelling (supports fuzzy matching)
- Check if client is registered in correct room
- Ensure device is included in client's device list

#### Context Not Propagating  
- Verify RequestContext includes client_id
- Check if ContextManager is using get_context_with_request_info()
- Ensure workflows pass RequestContext properly

### Debug Commands

```python
# Check if client is registered
registry = get_client_registry()
client = registry.get_client("kitchen_esp32")
if not client:
    print("Client not found!")
else:
    print(f"Client found: {client.room_name}, {len(client.available_devices)} devices")

# List all registrations
for client_id, client in registry.clients.items():
    print(f"{client_id}: {client.room_name} ({client.client_type})")

# Check device discovery
devices = registry.get_devices_by_type("light")
print(f"Found {len(devices)} lights across all clients")
```

---

## API Reference

See the complete API documentation in `irene/core/client_registry.py` for detailed method signatures and parameters.

### Key Methods

- `register_esp32_node()` - Register ESP32 with devices
- `register_web_client()` - Register web browser client  
- `get_client()` - Get client by ID
- `get_clients_by_room()` - Find clients in room
- `get_all_rooms()` - List all rooms
- `get_devices_by_type()` - Find devices by type
- `cleanup_expired_clients()` - Remove old registrations

---

*This system is a crucial foundation for context-aware voice processing and enables Irene to understand "включи свет на кухне" by knowing which client made the request and what devices are available in that room.*
