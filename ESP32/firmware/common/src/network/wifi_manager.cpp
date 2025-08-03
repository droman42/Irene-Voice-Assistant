#include "network/wifi_manager.hpp"
#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
#include "esp_timer.h"
#include <cstring>

static const char* TAG = "WiFiManager";

// WiFi event bits
#define WIFI_CONNECTED_BIT BIT0
#define WIFI_FAIL_BIT BIT1

namespace irene {

WiFiManager::WiFiManager()
    : initialized_(false)
    , connected_(false)
    , auto_reconnect_(true)
    , reconnect_interval_ms_(5000)
    , max_retry_count_(10)
    , connection_count_(0)
    , disconnection_count_(0)
    , retry_count_(0)
    , last_disconnect_time_(0) {
}

WiFiManager::~WiFiManager() {
    disconnect();
}

ErrorCode WiFiManager::initialize(const std::string& ssid, const std::string& password) {
    ESP_LOGI(TAG, "Initializing WiFi manager...");
    
    if (initialized_) {
        ESP_LOGW(TAG, "WiFi manager already initialized");
        return ErrorCode::SUCCESS;
    }
    
    ssid_ = ssid;
    password_ = password;
    
    // Initialize TCP/IP stack
    ESP_ERROR_CHECK(esp_netif_init());
    
    // Create default event loop
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    
    // Create default WiFi station
    esp_netif_create_default_wifi_sta();
    
    // Initialize WiFi with default config
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    
    // Register event handler
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, 
                                              &wifi_event_handler, this));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, 
                                              &wifi_event_handler, this));
    
    // Set WiFi mode to station
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    
    initialized_ = true;
    ESP_LOGI(TAG, "WiFi manager initialized for SSID: %s", ssid_.c_str());
    
    return ErrorCode::SUCCESS;
}

ErrorCode WiFiManager::connect() {
    if (!initialized_) {
        ESP_LOGE(TAG, "WiFi manager not initialized");
        return ErrorCode::WIFI_FAILED;
    }
    
    if (connected_) {
        ESP_LOGI(TAG, "WiFi already connected");
        return ErrorCode::SUCCESS;
    }
    
    ESP_LOGI(TAG, "Connecting to WiFi: %s", ssid_.c_str());
    
    // Configure WiFi connection
    wifi_config_t wifi_config = {};
    std::strncpy(reinterpret_cast<char*>(wifi_config.sta.ssid), 
                ssid_.c_str(), sizeof(wifi_config.sta.ssid) - 1);
    std::strncpy(reinterpret_cast<char*>(wifi_config.sta.password), 
                password_.c_str(), sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
    ESP_ERROR_CHECK(esp_wifi_connect());
    
    connection_count_++;
    
    ESP_LOGI(TAG, "WiFi connection initiated");
    return ErrorCode::SUCCESS;
}

void WiFiManager::disconnect() {
    if (!initialized_) {
        return;
    }
    
    ESP_LOGI(TAG, "Disconnecting WiFi...");
    
    connected_ = false;
    esp_wifi_disconnect();
    esp_wifi_stop();
    
    if (connected_) {
        disconnection_count_++;
        last_disconnect_time_ = esp_timer_get_time() / 1000;
    }
    
    ESP_LOGI(TAG, "WiFi disconnected");
}

ErrorCode WiFiManager::reconnect() {
    ESP_LOGI(TAG, "Attempting WiFi reconnection...");
    
    retry_count_++;
    
    disconnect();
    vTaskDelay(pdMS_TO_TICKS(1000)); // Brief delay
    
    return connect();
}

bool WiFiManager::is_connected() const {
    // Check actual WiFi status
    wifi_ap_record_t ap_info;
    return connected_ && (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK);
}

int WiFiManager::get_rssi() const {
    if (!connected_) {
        return -100;
    }
    
    wifi_ap_record_t ap_info;
    if (esp_wifi_sta_get_ap_info(&ap_info) == ESP_OK) {
        return ap_info.rssi;
    }
    
    return -100;
}

std::string WiFiManager::get_ip_address() const {
    if (!connected_) {
        return "0.0.0.0";
    }
    
    esp_netif_t* netif = esp_netif_get_handle_from_ifkey("WIFI_STA_DEF");
    if (!netif) {
        return "0.0.0.0";
    }
    
    esp_netif_ip_info_t ip_info;
    if (esp_netif_get_ip_info(netif, &ip_info) == ESP_OK) {
        char ip_str[16];
        snprintf(ip_str, sizeof(ip_str), IPSTR, IP2STR(&ip_info.ip));
        return std::string(ip_str);
    }
    
    return "0.0.0.0";
}

std::string WiFiManager::get_mac_address() const {
    uint8_t mac[6];
    if (esp_wifi_get_mac(WIFI_IF_STA, mac) == ESP_OK) {
        char mac_str[18];
        snprintf(mac_str, sizeof(mac_str), "%02x:%02x:%02x:%02x:%02x:%02x",
                mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
        return std::string(mac_str);
    }
    
    return "00:00:00:00:00:00";
}

void WiFiManager::set_auto_reconnect(bool enable) {
    auto_reconnect_ = enable;
    ESP_LOGI(TAG, "Auto-reconnect %s", enable ? "enabled" : "disabled");
}

void WiFiManager::set_reconnect_interval(uint32_t interval_ms) {
    reconnect_interval_ms_ = interval_ms;
    ESP_LOGI(TAG, "Reconnect interval set to: %u ms", interval_ms);
}

void WiFiManager::set_max_retry_count(uint32_t max_retries) {
    max_retry_count_ = max_retries;
    ESP_LOGI(TAG, "Max retry count set to: %u", max_retries);
}

void WiFiManager::set_status_callback(StatusCallback callback) {
    status_callback_ = callback;
}

void WiFiManager::wifi_event_handler(void* arg, esp_event_base_t event_base,
                                    int32_t event_id, void* event_data) {
    WiFiManager* manager = static_cast<WiFiManager*>(arg);
    manager->handle_wifi_event(event_id, event_data);
}

void WiFiManager::handle_wifi_event(int32_t event_id, void* event_data) {
    switch (event_id) {
        case WIFI_EVENT_STA_START:
            ESP_LOGI(TAG, "WiFi station started");
            break;
            
        case WIFI_EVENT_STA_CONNECTED:
            ESP_LOGI(TAG, "WiFi station connected");
            break;
            
        case WIFI_EVENT_STA_DISCONNECTED: {
            wifi_event_sta_disconnected_t* event = 
                static_cast<wifi_event_sta_disconnected_t*>(event_data);
            
            ESP_LOGW(TAG, "WiFi disconnected, reason: %d", event->reason);
            
            connected_ = false;
            disconnection_count_++;
            last_disconnect_time_ = esp_timer_get_time() / 1000;
            
            if (status_callback_) {
                status_callback_(false);
            }
            
            // Auto-reconnect logic
            if (auto_reconnect_ && retry_count_ < max_retry_count_) {
                ESP_LOGI(TAG, "Attempting auto-reconnect (%u/%u)...", 
                        retry_count_ + 1, max_retry_count_);
                vTaskDelay(pdMS_TO_TICKS(reconnect_interval_ms_));
                esp_wifi_connect();
                retry_count_++;
            } else if (retry_count_ >= max_retry_count_) {
                ESP_LOGE(TAG, "Max reconnection attempts reached");
            }
            break;
        }
        
        case IP_EVENT_STA_GOT_IP: {
            ip_event_got_ip_t* event = static_cast<ip_event_got_ip_t*>(event_data);
            ESP_LOGI(TAG, "Got IP address: " IPSTR, IP2STR(&event->ip_info.ip));
            
            connected_ = true;
            retry_count_ = 0; // Reset retry count on successful connection
            
            if (status_callback_) {
                status_callback_(true);
            }
            break;
        }
        
        default:
            ESP_LOGD(TAG, "Unhandled WiFi event: %d", (int)event_id);
            break;
    }
}

} // namespace irene 