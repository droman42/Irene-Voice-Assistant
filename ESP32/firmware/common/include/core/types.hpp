#pragma once

#include <cstdint>
#include <string>

namespace irene {

// System states
enum class SystemState {
    IDLE_LISTENING,
    STREAMING,
    COOLDOWN,
    WIFI_RETRY,
    ERROR
};

// Audio configuration
struct AudioConfig {
    uint32_t sample_rate = 16000;
    uint8_t channels = 1;
    uint8_t bits_per_sample = 16;
    uint32_t frame_size = 320;  // 20ms at 16kHz
    uint32_t buffer_count = 8;
};

// Network configuration
struct NetworkConfig {
    std::string ssid;
    std::string password;
    std::string server_uri;
    std::string node_id;
    uint32_t reconnect_delay_ms = 5000;
    uint32_t max_retry_count = 10;
};

// Wake word configuration
struct WakeWordConfig {
    float threshold = 0.9f;
    uint32_t trigger_duration_ms = 450;
    uint32_t back_buffer_ms = 300;
    bool use_psram = true;
};

// UI configuration
struct UIConfig {
    uint16_t display_width = 412;
    uint16_t display_height = 412;
    uint8_t brightness = 80;
    uint32_t idle_timeout_ms = 30000;
    bool show_debug_info = false;
};

// TLS configuration
struct TLSConfig {
    const char* ca_cert_pem;
    const char* client_cert_pem;
    const char* client_key_pem;
    uint32_t handshake_timeout_ms = 10000;
};

// System events
enum class SystemEvent {
    WAKE_WORD_DETECTED,
    STREAM_STARTED,
    STREAM_ENDED,
    TLS_ERROR,
    WIFI_DISCONNECTED,
    WIFI_CONNECTED,
    OTA_STARTED,
    OTA_PROGRESS,
    OTA_FINISHED,
    OTA_ERROR
};

// Error codes
enum class ErrorCode {
    SUCCESS = 0,
    INIT_FAILED,
    WIFI_FAILED,
    TLS_FAILED,
    AUDIO_FAILED,
    WAKE_WORD_FAILED,
    DISPLAY_FAILED,
    OTA_FAILED,
    MEMORY_ERROR,
    TIMEOUT_ERROR
};

} // namespace irene 