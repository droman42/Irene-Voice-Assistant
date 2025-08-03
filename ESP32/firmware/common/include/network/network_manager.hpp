#pragma once

#include "core/types.hpp"
#include <functional>
#include <memory>

namespace irene {

class WiFiManager;
class TLSManager;
class WebSocketClient;

/**
 * Manages network connectivity and secure audio streaming
 * Coordinates WiFi, TLS mutual authentication, and WebSocket communication
 */
class NetworkManager {
public:
    using ConnectionCallback = std::function<void(bool connected)>;
    using MessageCallback = std::function<void(const std::string& message)>;
    using ErrorCallback = std::function<void(ErrorCode error, const std::string& details)>;

    NetworkManager();
    ~NetworkManager();

    // Initialize network subsystem
    ErrorCode initialize(const NetworkConfig& config, const TLSConfig& tls_config);

    // Connection management
    ErrorCode connect();
    void disconnect();
    ErrorCode reconnect();

    // Audio streaming
    ErrorCode start_audio_session(const std::string& room_id);
    ErrorCode send_audio_data(const uint8_t* data, size_t length);
    ErrorCode end_audio_session();

    // Configuration messages
    ErrorCode send_config_message(const std::string& room_id, uint32_t sample_rate);
    ErrorCode send_eof_message();

    // Status
    bool is_wifi_connected() const;
    bool is_websocket_connected() const;
    bool is_audio_session_active() const { return audio_session_active_; }
    int get_wifi_rssi() const;
    std::string get_ip_address() const;

    // Callbacks
    void set_connection_callback(ConnectionCallback callback);
    void set_message_callback(MessageCallback callback);
    void set_error_callback(ErrorCallback callback);

    // Statistics
    uint32_t get_bytes_sent() const { return bytes_sent_; }
    uint32_t get_bytes_received() const { return bytes_received_; }
    uint32_t get_connection_attempts() const { return connection_attempts_; }
    uint32_t get_reconnection_count() const { return reconnection_count_; }

private:
    void connection_monitor_task();
    void handle_websocket_message(const std::string& message);
    void handle_connection_error(ErrorCode error);
    static void connection_monitor_task_wrapper(void* arg);

    NetworkConfig config_;
    TLSConfig tls_config_;
    bool audio_session_active_;

    // Component managers
    std::unique_ptr<WiFiManager> wifi_manager_;
    std::unique_ptr<TLSManager> tls_manager_;
    std::unique_ptr<WebSocketClient> websocket_client_;

    // Callbacks
    ConnectionCallback connection_callback_;
    MessageCallback message_callback_;
    ErrorCallback error_callback_;

    // Task management
    TaskHandle_t monitor_task_handle_;

    // Statistics
    uint32_t bytes_sent_;
    uint32_t bytes_received_;
    uint32_t connection_attempts_;
    uint32_t reconnection_count_;
    uint32_t last_reconnect_time_;

    // Connection state
    bool wifi_connected_;
    bool websocket_connected_;
    uint32_t connection_start_time_;
}; 