#include "network/websocket_client.hpp"
#include "esp_log.h"
#include "esp_websocket_client.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"

static const char* TAG = "WebSocketClient";

namespace irene {

WebSocketClient::WebSocketClient()
    : websocket_handle_(nullptr)
    , tls_manager_(nullptr)
    , connected_(false)
    , tls_enabled_(false)
    , keep_alive_interval_ms_(30000)
    , connection_timeout_ms_(10000)
    , max_message_size_(65536)
    , bytes_sent_(0)
    , bytes_received_(0)
    , message_count_(0)
    , error_count_(0) {
}

WebSocketClient::~WebSocketClient() {
    disconnect();
}

ErrorCode WebSocketClient::initialize(const std::string& uri) {
    ESP_LOGI(TAG, "Initializing WebSocket client...");
    
    uri_ = uri;
    
    ESP_LOGI(TAG, "WebSocket client initialized for URI: %s", uri_.c_str());
    return ErrorCode::SUCCESS;
}

ErrorCode WebSocketClient::connect() {
    ESP_LOGI(TAG, "Connecting to WebSocket server (non-TLS)...");
    
    if (connected_) {
        ESP_LOGW(TAG, "WebSocket already connected");
        return ErrorCode::SUCCESS;
    }
    
    esp_websocket_client_config_t websocket_cfg = {};
    websocket_cfg.uri = uri_.c_str();
    websocket_cfg.keepalive_idle = keep_alive_interval_ms_ / 1000;
    websocket_cfg.keepalive_interval = 5;
    websocket_cfg.keepalive_count = 3;
    websocket_cfg.network_timeout_ms = connection_timeout_ms_;
    websocket_cfg.buffer_size = max_message_size_;
    
    websocket_handle_ = esp_websocket_client_init(&websocket_cfg);
    if (!websocket_handle_) {
        ESP_LOGE(TAG, "Failed to initialize WebSocket client");
        return ErrorCode::TLS_FAILED;
    }
    
    // Register event handler
    esp_websocket_register_events(static_cast<esp_websocket_client_handle_t>(websocket_handle_),
                                 WEBSOCKET_EVENT_ANY,
                                 websocket_event_handler,
                                 this);
    
    esp_err_t result = esp_websocket_client_start(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WebSocket client: %s", esp_err_to_name(result));
        esp_websocket_client_destroy(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
        websocket_handle_ = nullptr;
        return ErrorCode::TLS_FAILED;
    }
    
    tls_enabled_ = false;
    ESP_LOGI(TAG, "WebSocket connection initiated");
    return ErrorCode::SUCCESS;
}

ErrorCode WebSocketClient::connect_tls(TLSManager* tls_manager) {
    ESP_LOGI(TAG, "Connecting to WebSocket server (TLS)...");
    
    if (!tls_manager || !tls_manager->is_initialized()) {
        ESP_LOGE(TAG, "TLS manager not initialized");
        return ErrorCode::TLS_FAILED;
    }
    
    if (connected_) {
        ESP_LOGW(TAG, "WebSocket already connected");
        return ErrorCode::SUCCESS;
    }
    
    tls_manager_ = tls_manager;
    
    esp_websocket_client_config_t websocket_cfg = {};
    websocket_cfg.uri = uri_.c_str();
    websocket_cfg.keepalive_idle = keep_alive_interval_ms_ / 1000;
    websocket_cfg.keepalive_interval = 5;
    websocket_cfg.keepalive_count = 3;
    websocket_cfg.network_timeout_ms = connection_timeout_ms_;
    websocket_cfg.buffer_size = max_message_size_;
    
    // Configure TLS
    esp_tls_cfg_t* tls_cfg = static_cast<esp_tls_cfg_t*>(tls_manager->get_tls_context());
    if (tls_cfg) {
        websocket_cfg.cert_pem = reinterpret_cast<const char*>(tls_cfg->cacert_buf);
        websocket_cfg.client_cert = reinterpret_cast<const char*>(tls_cfg->clientcert_buf);
        websocket_cfg.client_key = reinterpret_cast<const char*>(tls_cfg->clientkey_buf);
        websocket_cfg.skip_cert_common_name_check = false;
    }
    
    websocket_handle_ = esp_websocket_client_init(&websocket_cfg);
    if (!websocket_handle_) {
        ESP_LOGE(TAG, "Failed to initialize WebSocket client with TLS");
        return ErrorCode::TLS_FAILED;
    }
    
    // Register event handler
    esp_websocket_register_events(static_cast<esp_websocket_client_handle_t>(websocket_handle_),
                                 WEBSOCKET_EVENT_ANY,
                                 websocket_event_handler,
                                 this);
    
    esp_err_t result = esp_websocket_client_start(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WebSocket client with TLS: %s", esp_err_to_name(result));
        esp_websocket_client_destroy(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
        websocket_handle_ = nullptr;
        return ErrorCode::TLS_FAILED;
    }
    
    tls_enabled_ = true;
    ESP_LOGI(TAG, "WebSocket TLS connection initiated");
    return ErrorCode::SUCCESS;
}

void WebSocketClient::disconnect() {
    if (!websocket_handle_) {
        return;
    }
    
    ESP_LOGI(TAG, "Disconnecting WebSocket...");
    
    connected_ = false;
    
    esp_websocket_client_close(static_cast<esp_websocket_client_handle_t>(websocket_handle_), portMAX_DELAY);
    esp_websocket_client_stop(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
    esp_websocket_client_destroy(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
    
    websocket_handle_ = nullptr;
    tls_manager_ = nullptr;
    tls_enabled_ = false;
    
    ESP_LOGI(TAG, "WebSocket disconnected");
}

ErrorCode WebSocketClient::send_text(const std::string& message) {
    if (!connected_ || !websocket_handle_) {
        ESP_LOGW(TAG, "Cannot send text - WebSocket not connected");
        return ErrorCode::TLS_FAILED;
    }
    
    if (message.empty()) {
        return ErrorCode::SUCCESS;
    }
    
    if (message.length() > max_message_size_) {
        ESP_LOGW(TAG, "Message too large: %d > %d", message.length(), max_message_size_);
        return ErrorCode::TLS_FAILED;
    }
    
    esp_err_t result = esp_websocket_client_send_text(
        static_cast<esp_websocket_client_handle_t>(websocket_handle_),
        message.c_str(),
        message.length(),
        portMAX_DELAY
    );
    
    if (result == ESP_OK) {
        bytes_sent_ += message.length();
        message_count_++;
        ESP_LOGD(TAG, "Sent text message: %d bytes", message.length());
        return ErrorCode::SUCCESS;
    } else {
        ESP_LOGW(TAG, "Failed to send text message: %s", esp_err_to_name(result));
        error_count_++;
        return ErrorCode::TLS_FAILED;
    }
}

ErrorCode WebSocketClient::send_binary(const uint8_t* data, size_t length) {
    if (!connected_ || !websocket_handle_) {
        ESP_LOGW(TAG, "Cannot send binary - WebSocket not connected");
        return ErrorCode::TLS_FAILED;
    }
    
    if (!data || length == 0) {
        return ErrorCode::SUCCESS;
    }
    
    if (length > max_message_size_) {
        ESP_LOGW(TAG, "Binary data too large: %d > %d", length, max_message_size_);
        return ErrorCode::TLS_FAILED;
    }
    
    esp_err_t result = esp_websocket_client_send_bin(
        static_cast<esp_websocket_client_handle_t>(websocket_handle_),
        reinterpret_cast<const char*>(data),
        length,
        portMAX_DELAY
    );
    
    if (result == ESP_OK) {
        bytes_sent_ += length;
        ESP_LOGD(TAG, "Sent binary data: %d bytes", length);
        return ErrorCode::SUCCESS;
    } else {
        ESP_LOGW(TAG, "Failed to send binary data: %s", esp_err_to_name(result));
        error_count_++;
        return ErrorCode::TLS_FAILED;
    }
}

ErrorCode WebSocketClient::send_ping() {
    if (!connected_ || !websocket_handle_) {
        ESP_LOGW(TAG, "Cannot send ping - WebSocket not connected");
        return ErrorCode::TLS_FAILED;
    }
    
    esp_err_t result = esp_websocket_client_send_ping(
        static_cast<esp_websocket_client_handle_t>(websocket_handle_),
        portMAX_DELAY
    );
    
    if (result == ESP_OK) {
        ESP_LOGD(TAG, "Ping sent");
        return ErrorCode::SUCCESS;
    } else {
        ESP_LOGW(TAG, "Failed to send ping: %s", esp_err_to_name(result));
        error_count_++;
        return ErrorCode::TLS_FAILED;
    }
}

void WebSocketClient::set_message_callback(MessageCallback callback) {
    message_callback_ = callback;
}

void WebSocketClient::set_error_callback(ErrorCallback callback) {
    error_callback_ = callback;
}

void WebSocketClient::set_connection_callback(ConnectionCallback callback) {
    connection_callback_ = callback;
}

bool WebSocketClient::is_connected() const {
    return connected_ && websocket_handle_ && 
           esp_websocket_client_is_connected(static_cast<esp_websocket_client_handle_t>(websocket_handle_));
}

void WebSocketClient::set_keep_alive_interval(uint32_t interval_ms) {
    keep_alive_interval_ms_ = interval_ms;
    ESP_LOGI(TAG, "Keep-alive interval set to: %u ms", interval_ms);
}

void WebSocketClient::set_connection_timeout(uint32_t timeout_ms) {
    connection_timeout_ms_ = timeout_ms;
    ESP_LOGI(TAG, "Connection timeout set to: %u ms", timeout_ms);
}

void WebSocketClient::set_max_message_size(size_t max_size) {
    max_message_size_ = max_size;
    ESP_LOGI(TAG, "Max message size set to: %d bytes", max_size);
}

void WebSocketClient::websocket_event_handler(void* handler_args, esp_event_base_t base,
                                             int32_t event_id, void* event_data) {
    WebSocketClient* client = static_cast<WebSocketClient*>(handler_args);
    client->handle_websocket_event(event_id, event_data);
}

void WebSocketClient::handle_websocket_event(int32_t event_id, void* event_data) {
    esp_websocket_event_data_t* data = static_cast<esp_websocket_event_data_t*>(event_data);
    
    switch (event_id) {
        case WEBSOCKET_EVENT_CONNECTED:
            ESP_LOGI(TAG, "WebSocket connected");
            connected_ = true;
            if (connection_callback_) {
                connection_callback_(true);
            }
            break;
            
        case WEBSOCKET_EVENT_DISCONNECTED:
            ESP_LOGI(TAG, "WebSocket disconnected");
            connected_ = false;
            if (connection_callback_) {
                connection_callback_(false);
            }
            break;
            
        case WEBSOCKET_EVENT_DATA:
            if (data) {
                bytes_received_ += data->data_len;
                
                if (data->op_code == 0x1) { // Text frame
                    std::string message(static_cast<const char*>(data->data_ptr), data->data_len);
                    ESP_LOGD(TAG, "Received text data: %d bytes", data->data_len);
                    
                    if (message_callback_) {
                        message_callback_(message);
                    }
                } else if (data->op_code == 0x2) { // Binary frame
                    ESP_LOGD(TAG, "Received binary data: %d bytes", data->data_len);
                    // Binary data handling could be added here if needed
                } else if (data->op_code == 0x8) { // Close frame
                    ESP_LOGI(TAG, "Received close frame");
                    connected_ = false;
                }
            }
            break;
            
        case WEBSOCKET_EVENT_ERROR:
            ESP_LOGE(TAG, "WebSocket error occurred");
            error_count_++;
            connected_ = false;
            
            if (error_callback_) {
                error_callback_("WebSocket connection error");
            }
            
            if (connection_callback_) {
                connection_callback_(false);
            }
            break;
            
        default:
            ESP_LOGD(TAG, "Unhandled WebSocket event: %d", (int)event_id);
            break;
    }
}

} // namespace irene 