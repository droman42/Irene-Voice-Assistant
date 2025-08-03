# Irene Voice Assistant - ESP32 Firmware

```mermaid
graph TD
    A["ESP32/firmware/"] --> B["common/"]
    A --> C["nodes/"]
    A --> D["tools/"]
    A --> E["README.md"]

    B --> B1["CMakeLists.txt"]
    B --> B2["include/"]
    B --> B3["src/"]

    B2 --> B2A["core/types.hpp<br/>core/state_machine.hpp"]
    B2 --> B2B["audio/audio_manager.hpp<br/>audio/wake_word_detector.hpp"]
    B2 --> B2C["network/network_manager.hpp<br/>network/tls_manager.hpp"]
    B2 --> B2D["ui/ui_controller.hpp<br/>ui/display_manager.hpp"]
    B2 --> B2E["hardware/i2s_driver.hpp<br/>hardware/codec_es8311.hpp"]

    B3 --> B3A["core/state_machine.cpp<br/>core/task_manager.cpp"]
    B3 --> B3B["audio/audio_manager.cpp<br/>audio/vad_processor.cpp"]
    B3 --> B3C["network/websocket_client.cpp<br/>network/wifi_manager.cpp"]
    B3 --> B3D["ui/ui_controller.cpp<br/>ui/themes.cpp"]

    C --> C1["kitchen/"]
    C --> C2["living_room/"]

    C1 --> C1A["CMakeLists.txt"]
    C1 --> C1B["main/"]
    C1B --> C1C["main.cpp<br/>node_config.h<br/>certificates.h<br/>ww_model.h"]
    C1B --> C1D["certs/<br/>ca.pem<br/>kitchen.pem<br/>kitchen.key"]
    C1B --> C1E["models/<br/>jarvis_medium.tflite"]

    D --> D1["generate_certs.sh"]
    D --> D2["setup_node.py"]

    style A fill:#e1f5fe
    style B fill:#f3e5f5
    style C fill:#e8f5e8
    style D fill:#fff3e0
```

## Overview

This firmware implements secure voice assistant nodes for the Irene system, featuring:
- Local wake-word detection with microWakeWord
- Mutual TLS authentication with local CA
- Raw PCM audio streaming over WebSocket
- LVGL-based circular UI with real-time status
- Per-node wake-word models and certificates

## Hardware Requirements

- ESP32-S3-R8 development board
- 16MB Flash + 8MB PSRAM
- ES8311 audio codec
- 1.46" round IPS display (412×412)
- PCF85063 RTC

## Directory Structure

```
firmware/
├── common/                    # Shared components across all nodes
├── nodes/                     # Per-node configurations
│   ├── kitchen/              # Example node
│   └── living_room/          # Example node
├── tools/                    # Build and certificate tools
└── README.md                 # This file
```

## Building

1. Set up ESP-IDF v5.3+
2. Generate certificates (see tools/generate_certs.sh)
3. Build for specific node:

```bash
export NODE_ID=kitchen
cd nodes/${NODE_ID}
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## Node Configuration

Each node requires:
- Unique client certificate (client_pem.h, client_key.h)
- Trained wake-word model (ww_model.h)
- Node-specific configuration (node_config.h)

See `tools/setup_node.py` for automated node setup. 