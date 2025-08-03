#include "network/network_manager.hpp"
#include "network/wifi_manager.hpp"
#include "network/tls_manager.hpp"
#include "network/websocket_client.hpp"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include <sstream>
#include <iomanip>

static const char* TAG = "NetworkManager";

namespace irene {

NetworkManager::NetworkManager()
    : audio_session_active_(false)
    , monitor_task_handle_(nullptr)
    , bytes_sent_(0)
    , bytes_received_(0)
    , connection_attempts_(0)
    , reconnection_count_(0)
    , last_reconnect_time_(0)
    , wifi_connected_(false)
    , websocket_connected_(false)
    , connection_start_time_(0) {
}

NetworkManager::~NetworkManager() {
    disconnect();
    
    if (monitor_task_handle_) {
        vTaskDelete(monitor_task_handle_);
    }
}

ErrorCode NetworkManager::initialize(const NetworkConfig& config, const TLSConfig& tls_config) {
    ESP_LOGI(TAG, "Initializing network manager...");
    
    config_ = config;
    tls_config_ = tls_config;
    
    try {
        // Initialize WiFi manager
        wifi_manager_ = std::make_unique<WiFiManager>();
        ErrorCode result = wifi_manager_->initialize(config.ssid, config.password);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize WiFi manager");
            return result;
        }
        
        // Initialize TLS manager
        tls_manager_ = std::make_unique<TLSManager>();
        result = tls_manager_->initialize(tls_config);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize TLS manager");
            return result;
        }
        
        // Initialize WebSocket client
        websocket_client_ = std::make_unique<WebSocketClient>();
        result = websocket_client_->initialize(config.server_uri);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize WebSocket client");
            return result;
        }
        
        // Set up callbacks
        setup_callbacks();
        
        // Create connection monitor task
        BaseType_t task_result = xTaskCreatePinnedToCore(
            connection_monitor_task_wrapper,
            "net_monitor",
            4096,  // Stack size
            this,
            5,     // Priority
            &monitor_task_handle_,
            1      // Core 1
        );
        
        if (task_result != pdPASS) {
            ESP_LOGE(TAG, "Failed to create network monitor task");
            return ErrorCode::INIT_FAILED;
        }
        
        ESP_LOGI(TAG, "Network manager initialized successfully");
        return ErrorCode::SUCCESS;
        
    } catch (const std::exception& e) {
        ESP_LOGE(TAG, "Exception during network manager initialization: %s", e.what());
        return ErrorCode::INIT_FAILED;
    }
}

ErrorCode NetworkManager::connect() {
    ESP_LOGI(TAG, "Connecting to network...");
    
    connection_attempts_++;
    connection_start_time_ = esp_timer_get_time() / 1000;
    
    // Connect to WiFi first
    ErrorCode result = wifi_manager_->connect();
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "WiFi connection failed");
        handle_connection_error(ErrorCode::WIFI_FAILED);
        return result;
    }
    
    wifi_connected_ = true;
    ESP_LOGI(TAG, "WiFi connected successfully");
    
    // Wait for IP address
    vTaskDelay(pdMS_TO_TICKS(2000));
    
    // Connect WebSocket with TLS
    result = websocket_client_->connect_tls(tls_manager_.get());
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "WebSocket TLS connection failed");
        handle_connection_error(ErrorCode::TLS_FAILED);
        return result;
    }
    
    websocket_connected_ = true;
    ESP_LOGI(TAG, "WebSocket TLS connection established");
    
    if (connection_callback_) {
        connection_callback_(true);
    }
    
    return ErrorCode::SUCCESS;
}

void NetworkManager::disconnect() {
    ESP_LOGI(TAG, "Disconnecting from network...");
    
    // End any active session
    if (audio_session_active_) {
        end_audio_session();
    }
    
    // Disconnect WebSocket
    if (websocket_client_) {
        websocket_client_->disconnect();
    }
    websocket_connected_ = false;
    
    // Disconnect WiFi
    if (wifi_manager_) {
        wifi_manager_->disconnect();
    }
    wifi_connected_ = false;
    
    if (connection_callback_) {
        connection_callback_(false);
    }
    
    ESP_LOGI(TAG, "Network disconnected");
}

ErrorCode NetworkManager::reconnect() {
    ESP_LOGI(TAG, "Attempting to reconnect...");
    
    reconnection_count_++;
    last_reconnect_time_ = esp_timer_get_time() / 1000;
    
    disconnect();
    vTaskDelay(pdMS_TO_TICKS(1000)); // Brief delay before reconnect
    
    return connect();
}

ErrorCode NetworkManager::start_audio_session(const std::string& room_id) {
    if (audio_session_active_) {
        ESP_LOGW(TAG, "Audio session already active");
        return ErrorCode::SUCCESS;
    }
    
    if (!websocket_connected_) {
        ESP_LOGE(TAG, "Cannot start audio session - WebSocket not connected");
        return ErrorCode::WIFI_FAILED;
    }
    
    ESP_LOGI(TAG, "Starting audio session for room: %s", room_id.c_str());
    
    // Send configuration message
    ErrorCode result = send_config_message(room_id, 16000);
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to send config message");
        return result;
    }
    
    audio_session_active_ = true;
    ESP_LOGI(TAG, "Audio session started");
    
    return ErrorCode::SUCCESS;
}

ErrorCode NetworkManager::send_audio_data(const uint8_t* data, size_t length) {
    if (!audio_session_active_ || !websocket_connected_) {
        return ErrorCode::WIFI_FAILED;
    }
    
    if (!data || length == 0) {
        return ErrorCode::SUCCESS;
    }
    
    // Send raw PCM data over WebSocket
    ErrorCode result = websocket_client_->send_binary(data, length);
    if (result == ErrorCode::SUCCESS) {
        bytes_sent_ += length;
    }
    
    return result;
}

ErrorCode NetworkManager::end_audio_session() {
    if (!audio_session_active_) {
        return ErrorCode::SUCCESS;
    }
    
    ESP_LOGI(TAG, "Ending audio session...");
    
    // Send EOF message
    send_eof_message();
    
    audio_session_active_ = false;
    ESP_LOGI(TAG, "Audio session ended");
    
    return ErrorCode::SUCCESS;
}

ErrorCode NetworkManager::send_config_message(const std::string& room_id, uint32_t sample_rate) {
    if (!websocket_connected_) {
        return ErrorCode::WIFI_FAILED;
    }
    
    // Create JSON configuration message
    std::ostringstream json;
    json << R"({"config":{"sample_rate":)" << sample_rate 
         << R"(,"room":")" << room_id << R"("}})";
    
    std::string config_msg = json.str();
    ESP_LOGI(TAG, "Sending config: %s", config_msg.c_str());
    
    return websocket_client_->send_text(config_msg);
}

ErrorCode NetworkManager::send_eof_message() {
    if (!websocket_connected_) {
        return ErrorCode::WIFI_FAILED;
    }
    
    std::string eof_msg = R"({"eof":1})";
    ESP_LOGI(TAG, "Sending EOF message");
    
    return websocket_client_->send_text(eof_msg);
}

bool NetworkManager::is_wifi_connected() const {
    return wifi_connected_ && wifi_manager_ && wifi_manager_->is_connected();
}

bool NetworkManager::is_websocket_connected() const {
    return websocket_connected_ && websocket_client_ && websocket_client_->is_connected();
}

int NetworkManager::get_wifi_rssi() const {
    return wifi_manager_ ? wifi_manager_->get_rssi() : -100;
}

std::string NetworkManager::get_ip_address() const {
    return wifi_manager_ ? wifi_manager_->get_ip_address() : "0.0.0.0";
}

void NetworkManager::set_connection_callback(ConnectionCallback callback) {
    connection_callback_ = callback;
}

void NetworkManager::set_message_callback(MessageCallback callback) {
    message_callback_ = callback;
}

void NetworkManager::set_error_callback(ErrorCallback callback) {
    error_callback_ = callback;
}

void NetworkManager::connection_monitor_task_wrapper(void* arg) {
    static_cast<NetworkManager*>(arg)->connection_monitor_task();
}

void NetworkManager::connection_monitor_task() {
    ESP_LOGI(TAG, "Network monitor task started");
    
    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t monitor_period = pdMS_TO_TICKS(5000); // 5 second intervals
    
    while (true) {
        // Check WiFi connection status
        bool wifi_status = is_wifi_connected();
        if (wifi_connected_ != wifi_status) {
            wifi_connected_ = wifi_status;
            ESP_LOGI(TAG, "WiFi status changed: %s", wifi_status ? "connected" : "disconnected");
            
            if (!wifi_status) {
                handle_connection_error(ErrorCode::WIFI_FAILED);
            }
        }
        
        // Check WebSocket connection status
        bool ws_status = is_websocket_connected();
        if (websocket_connected_ != ws_status) {
            websocket_connected_ = ws_status;
            ESP_LOGI(TAG, "WebSocket status changed: %s", ws_status ? "connected" : "disconnected");
            
            if (!ws_status && wifi_connected_) {
                handle_connection_error(ErrorCode::TLS_FAILED);
            }
        }
        
        // Log connection statistics periodically
        static uint32_t last_stats_log = 0;
        uint32_t current_time = esp_timer_get_time() / 1000000; // Convert to seconds
        if (current_time - last_stats_log >= 60) { // Every minute
            log_connection_stats();
            last_stats_log = current_time;
        }
        
        vTaskDelayUntil(&last_wake_time, monitor_period);
    }
}

void NetworkManager::handle_websocket_message(const std::string& message) {
    ESP_LOGD(TAG, "Received WebSocket message: %s", message.c_str());
    
    bytes_received_ += message.length();
    
    if (message_callback_) {
        message_callback_(message);
    }
}

void NetworkManager::handle_connection_error(ErrorCode error) {
    ESP_LOGW(TAG, "Connection error: %d", (int)error);
    
    // Update connection state
    if (error == ErrorCode::WIFI_FAILED) {
        wifi_connected_ = false;
        websocket_connected_ = false;
    } else if (error == ErrorCode::TLS_FAILED) {
        websocket_connected_ = false;
    }
    
    // End any active session
    if (audio_session_active_) {
        audio_session_active_ = false;
    }
    
    // Notify callback
    if (error_callback_) {
        std::string error_details;
        switch (error) {
            case ErrorCode::WIFI_FAILED:
                error_details = "WiFi connection lost";
                break;
            case ErrorCode::TLS_FAILED:
                error_details = "TLS/WebSocket connection failed";
                break;
            default:
                error_details = "Unknown network error";
                break;
        }
        error_callback_(error, error_details);
    }
    
    if (connection_callback_) {
        connection_callback_(false);
    }
}

void NetworkManager::setup_callbacks() {
    // Set up WiFi manager callbacks
    if (wifi_manager_) {
        wifi_manager_->set_status_callback([this](bool connected) {
            if (!connected) {
                handle_connection_error(ErrorCode::WIFI_FAILED);
            }
        });
    }
    
    // Set up WebSocket client callbacks
    if (websocket_client_) {
        websocket_client_->set_message_callback([this](const std::string& message) {
            handle_websocket_message(message);
        });
        
        websocket_client_->set_error_callback([this](const std::string& error) {
            ESP_LOGE(TAG, "WebSocket error: %s", error.c_str());
            handle_connection_error(ErrorCode::TLS_FAILED);
        });
    }
}

void NetworkManager::log_connection_stats() const {
    ESP_LOGI(TAG, "Network Statistics:");
    ESP_LOGI(TAG, "  WiFi: %s (RSSI: %d dBm)", 
            wifi_connected_ ? "connected" : "disconnected", get_wifi_rssi());
    ESP_LOGI(TAG, "  WebSocket: %s", 
            websocket_connected_ ? "connected" : "disconnected");
    ESP_LOGI(TAG, "  IP Address: %s", get_ip_address().c_str());
    ESP_LOGI(TAG, "  Bytes sent: %u, received: %u", bytes_sent_, bytes_received_);
    ESP_LOGI(TAG, "  Connection attempts: %u, reconnections: %u", 
            connection_attempts_, reconnection_count_);
    ESP_LOGI(TAG, "  Audio session: %s", audio_session_active_ ? "active" : "inactive");
}

} // namespace irene 