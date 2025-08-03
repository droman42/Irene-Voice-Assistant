#pragma once

#include "core/types.hpp"
#include "network/tls_manager.hpp"
#include <string>
#include <functional>

namespace irene {

/**
 * WebSocket client with TLS support for audio streaming
 * Handles secure WebSocket connections with mutual TLS authentication
 */
class WebSocketClient {
public:
    using MessageCallback = std::function<void(const std::string& message)>;
    using ErrorCallback = std::function<void(const std::string& error)>;
    using ConnectionCallback = std::function<void(bool connected)>;
    
    WebSocketClient();
    ~WebSocketClient();
    
    // Initialize with server URI
    ErrorCode initialize(const std::string& uri);
    
    // Connection management
    ErrorCode connect();
    ErrorCode connect_tls(TLSManager* tls_manager);
    void disconnect();
    
    // Send data
    ErrorCode send_text(const std::string& message);
    ErrorCode send_binary(const uint8_t* data, size_t length);
    ErrorCode send_ping();
    
    // Callbacks
    void set_message_callback(MessageCallback callback);
    void set_error_callback(ErrorCallback callback);
    void set_connection_callback(ConnectionCallback callback);
    
    // Status
    bool is_connected() const;
    bool is_tls_enabled() const { return tls_enabled_; }
    uint32_t get_bytes_sent() const { return bytes_sent_; }
    uint32_t get_bytes_received() const { return bytes_received_; }
    
    // Configuration
    void set_keep_alive_interval(uint32_t interval_ms);
    void set_connection_timeout(uint32_t timeout_ms);
    void set_max_message_size(size_t max_size);

private:
    static void websocket_event_handler(void* handler_args, esp_event_base_t base,
                                       int32_t event_id, void* event_data);
    void handle_websocket_event(int32_t event_id, void* event_data);
    
    std::string uri_;
    void* websocket_handle_;
    TLSManager* tls_manager_;
    bool connected_;
    bool tls_enabled_;
    
    // Callbacks
    MessageCallback message_callback_;
    ErrorCallback error_callback_;
    ConnectionCallback connection_callback_;
    
    // Configuration
    uint32_t keep_alive_interval_ms_;
    uint32_t connection_timeout_ms_;
    size_t max_message_size_;
    
    // Statistics
    uint32_t bytes_sent_;
    uint32_t bytes_received_;
    uint32_t message_count_;
    uint32_t error_count_;
};

} // namespace irene 