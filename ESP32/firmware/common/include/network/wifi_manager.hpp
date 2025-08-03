#pragma once

#include "core/types.hpp"
#include <string>
#include <functional>

namespace irene {

/**
 * WiFi connection manager with automatic reconnection
 */
class WiFiManager {
public:
    using StatusCallback = std::function<void(bool connected)>;
    
    WiFiManager();
    ~WiFiManager();
    
    // Initialize WiFi with credentials
    ErrorCode initialize(const std::string& ssid, const std::string& password);
    
    // Connection management
    ErrorCode connect();
    void disconnect();
    ErrorCode reconnect();
    
    // Status
    bool is_connected() const;
    int get_rssi() const;
    std::string get_ip_address() const;
    std::string get_mac_address() const;
    
    // Configuration
    void set_auto_reconnect(bool enable);
    void set_reconnect_interval(uint32_t interval_ms);
    void set_max_retry_count(uint32_t max_retries);
    
    // Callbacks
    void set_status_callback(StatusCallback callback);
    
    // Statistics
    uint32_t get_connection_count() const { return connection_count_; }
    uint32_t get_disconnection_count() const { return disconnection_count_; }
    uint32_t get_retry_count() const { return retry_count_; }

private:
    static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                                  int32_t event_id, void* event_data);
    void handle_wifi_event(int32_t event_id, void* event_data);
    
    std::string ssid_;
    std::string password_;
    bool initialized_;
    bool connected_;
    bool auto_reconnect_;
    uint32_t reconnect_interval_ms_;
    uint32_t max_retry_count_;
    
    StatusCallback status_callback_;
    
    // Statistics
    uint32_t connection_count_;
    uint32_t disconnection_count_;
    uint32_t retry_count_;
    uint32_t last_disconnect_time_;
};

} // namespace irene 