# Getting Started with ESP32 Firmware

This guide will help you build and deploy the Irene Voice Assistant firmware to your ESP32-S3 nodes.

## Prerequisites

### Hardware Requirements
- ESP32-S3-R8 development board with:
  - 16MB Flash + 8MB PSRAM
  - ES8311 audio codec
  - 1.46" round IPS display (412×412)
  - PCF85063 RTC
  - FT6236 touch controller

### Software Requirements
- ESP-IDF v5.3 or later
- Python 3.8+ (for tools)
- OpenSSL (for certificate generation)
- microwakeword package (for wake word training)

## Quick Start

### 1. Initialize the Certificate Authority

First, create the root CA and server certificates:

```bash
cd ESP32/firmware/tools
./generate_certs.sh init
```

This creates:
- `ca.crt` - Root Certificate Authority
- `server.crt` - Server certificate for nginx
- `server.key` - Server private key

### 2. Create Your First Node

Create a new node (e.g., "kitchen"):

```bash
./setup_node.py kitchen --wifi-ssid "YourWiFi" --wifi-password "YourPassword"
```

This creates a complete node structure with:
- Configuration files
- Client certificates 
- Build files
- Placeholder model files

### 3. Train Wake Word Model

For each node, you need to train a custom wake word model:

```bash
# Record samples (see ESP32/wakeword_training/README.md)
cd ../../wakeword_training
python scripts/record_samples.py --wake-word jarvis --samples 200

# Train model
microwakeword-train \
    --wake_word "jarvis" \
    --positive_dir data/positive \
    --negative_dir data/negative \
    --model_size medium \
    --batch_norm \
    --epochs 55 \
    --sample_rate 16000 \
    --output models/jarvis_medium.tflite

# Convert for firmware
xxd -i models/jarvis_medium.tflite > ../firmware/nodes/kitchen/main/models/jarvis_medium.tflite
```

### 4. Build and Flash

```bash
cd ESP32/firmware/nodes/kitchen
export IDF_PATH=/path/to/esp-idf
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## Directory Structure

```
ESP32/firmware/
├── common/                    # Shared firmware components
│   ├── include/              # Header files
│   │   ├── core/            # Core system (state machine, types)
│   │   ├── audio/           # Audio processing (I2S, VAD, wake word)
│   │   ├── network/         # Networking (WiFi, TLS, WebSocket)
│   │   ├── ui/              # User interface (LVGL, display)
│   │   ├── hardware/        # Hardware abstraction (codecs, sensors)
│   │   └── utils/           # Utilities (logging, buffers)
│   └── src/                 # Implementation files
├── nodes/                   # Node-specific configurations
│   ├── kitchen/            # Example kitchen node
│   │   ├── main/
│   │   │   ├── main.cpp     # Node entry point
│   │   │   ├── node_config.h # Node configuration
│   │   │   ├── certificates.h # TLS certificates
│   │   │   ├── ww_model.h    # Wake word model
│   │   │   ├── certs/       # Certificate files
│   │   │   └── models/      # Model files
│   │   └── CMakeLists.txt   # Build configuration
│   └── living_room/        # Additional nodes...
├── tools/                  # Development tools
│   ├── generate_certs.sh   # Certificate generation
│   └── setup_node.py       # Node setup automation
└── README.md               # Overview
```

## Core Components

### State Machine (`common/include/core/state_machine.hpp`)
Central coordinator that manages:
- Audio capture and streaming
- Wake word detection
- Network connectivity
- UI updates
- State transitions (Idle → Listening → Streaming → Cooldown)

### Audio Manager (`common/include/audio/audio_manager.hpp`)
Handles:
- I2S audio capture
- Voice Activity Detection (VAD)
- Audio buffering and streaming
- Back-buffer for wake word context

### Wake Word Detector (`common/include/audio/wake_word_detector.hpp`)
Manages:
- microWakeWord model inference
- PSRAM-resident model storage
- Real-time detection with <150ms latency
- Per-node custom wake words

### Network Manager (`common/include/network/network_manager.hpp`)
Coordinates:
- WiFi connectivity
- TLS mutual authentication
- WebSocket audio streaming
- Automatic reconnection

### UI Controller (`common/include/ui/ui_controller.hpp`)
Controls:
- LVGL-based circular display
- State visualization (color-coded ring)
- Clock, weather, WiFi status
- Touch and button interaction

## Creating New Nodes

### Using the Setup Tool

```bash
# Basic node creation
./tools/setup_node.py living_room

# With custom configuration
./tools/setup_node.py office \
    --wifi-ssid "OfficeWiFi" \
    --wake-word "computer" \
    --threshold 0.85

# From configuration file
./tools/setup_node.py bedroom --config bedroom_config.json
```

### Manual Configuration

1. **Copy node template**: Duplicate an existing node directory
2. **Update configuration**: Modify `node_config.h` with node-specific settings
3. **Generate certificates**: Run `./tools/generate_certs.sh node NODE_NAME`
4. **Train wake word**: Create custom model for the node's location/acoustics
5. **Build and test**: Compile and flash the firmware

## Network Setup

### Server Configuration (nginx)

Configure nginx to terminate TLS and validate client certificates:

```nginx
server {
    listen 443 ssl;
    server_name assistant.lan;

    ssl_certificate     /etc/ssl/certs/server.crt;
    ssl_certificate_key /etc/ssl/private/server.key;
    ssl_client_certificate /etc/ssl/certs/ca.crt;
    ssl_verify_client on;  # Mutual TLS

    location /stt {
        proxy_pass http://127.0.0.1:5003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```

### DNS Configuration

Add to your local DNS or `/etc/hosts`:
```
192.168.1.100  assistant.lan
```

## Security Features

### Mutual TLS Authentication
- Each node has unique client certificate
- Server validates client identity
- Man-in-the-middle protection
- Certificate-based access control

### Local Certificate Authority
- Self-signed root CA for your network
- No external certificate dependencies
- Full control over certificate lifecycle
- Ed25519 cryptography for efficiency

### Encrypted Communication
- TLS 1.2 for all WebSocket connections
- Raw PCM audio encrypted in transit
- Configuration messages over secure channel

## Performance Optimization

### Resource Usage
- **Flash**: ~770 kB total
- **RAM**: ~180 kB internal + 324 kB PSRAM
- **Wake latency**: <150ms average
- **Inference**: 25ms per frame (30ms intervals)

### Task Architecture
```
FreeRTOS Tasks (ESP32-S3 dual core):
├─ Core 0: Audio + Wake Word (real-time)
│   ├─ AudioTask (Priority 10)
│   └─ WakeWordTask (Priority 9)
└─ Core 1: Network + UI (best effort)
    ├─ NetworkTask (Priority 8)
    ├─ UITask (Priority 5)
    └─ MonitorTask (Priority 3)
```

## Troubleshooting

### Common Issues

**Certificate validation fails**:
- Verify system time is accurate (RTC/SNTP)
- Check certificate expiration dates
- Ensure CA is properly installed on server

**Wake word not triggering**:
- Check microphone hardware connections
- Verify model file is properly embedded
- Adjust threshold in `node_config.h`
- Monitor debug logs for confidence scores

**Audio streaming issues**:
- Verify network connectivity
- Check WebSocket connection status
- Monitor TLS handshake logs
- Ensure server is accepting connections

**Display not working**:
- Verify SPI connections and power
- Check LVGL configuration
- Test touch controller I2C communication

### Debug Logging

Enable detailed logging in `node_config.h`:
```c
#define DEBUG_AUDIO_STATS 1
#define DEBUG_WAKE_WORD_STATS 1
#define DEBUG_NETWORK_STATS 1
#define DEBUG_MEMORY_USAGE 1
```

### Performance Monitoring

Monitor system performance:
```c
// Check free heap
ESP_LOGI(TAG, "Free heap: %d bytes", esp_get_free_heap_size());

// Check PSRAM usage
ESP_LOGI(TAG, "Free PSRAM: %d bytes", heap_caps_get_free_size(MALLOC_CAP_SPIRAM));

// Wake word statistics
detector.log_inference_stats();
```

## Next Steps

1. **Deploy multiple nodes**: Create nodes for different rooms
2. **Customize wake words**: Train location-specific models
3. **Integrate with Irene**: Connect to the main voice assistant system
4. **Add sensors**: Extend with temperature, humidity, motion sensors
5. **OTA updates**: Implement automated firmware updates

## Support

For issues and questions:
- Check the main Irene documentation
- Review ESP-IDF documentation for hardware issues
- Examine the firmware specification in `docs/irene_firmware.md`
- Test with the wake word training tools in `ESP32/wakeword_training/` 