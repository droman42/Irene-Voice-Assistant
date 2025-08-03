#include "core/config_manager.hpp"
#include "esp_log.h"
#include <cstring>

static const char* TAG = "ConfigManager";

namespace irene {

ConfigManager::ConfigManager()
    : nvs_handle_(0)
    , initialized_(false)
    , namespace_("irene_config") {
}

ConfigManager::~ConfigManager() {
    close_nvs();
}

ErrorCode ConfigManager::initialize() {
    ESP_LOGI(TAG, "Initializing configuration manager...");
    
    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS partition truncated, erasing...");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize NVS: %s", esp_err_to_name(ret));
        return ErrorCode::INIT_FAILED;
    }
    
    ErrorCode result = open_nvs();
    if (result != ErrorCode::SUCCESS) {
        return result;
    }
    
    initialized_ = true;
    ESP_LOGI(TAG, "Configuration manager initialized");
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::set_string(const std::string& key, const std::string& value) {
    if (!initialized_) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_set_str(nvs_handle_, key.c_str(), value.c_str());
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set string '%s': %s", key.c_str(), esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

std::string ConfigManager::get_string(const std::string& key, const std::string& default_value) {
    if (!initialized_) return default_value;
    
    size_t required_size = 0;
    esp_err_t err = nvs_get_str(nvs_handle_, key.c_str(), nullptr, &required_size);
    
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return default_value;
    }
    
    if (err != ESP_OK || required_size == 0) {
        ESP_LOGW(TAG, "Failed to get string size for '%s': %s", key.c_str(), esp_err_to_name(err));
        return default_value;
    }
    
    std::string value(required_size - 1, '\0'); // -1 for null terminator
    err = nvs_get_str(nvs_handle_, key.c_str(), &value[0], &required_size);
    
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to get string '%s': %s", key.c_str(), esp_err_to_name(err));
        return default_value;
    }
    
    return value;
}

ErrorCode ConfigManager::set_int32(const std::string& key, int32_t value) {
    if (!initialized_) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_set_i32(nvs_handle_, key.c_str(), value);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set int32 '%s': %s", key.c_str(), esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

int32_t ConfigManager::get_int32(const std::string& key, int32_t default_value) {
    if (!initialized_) return default_value;
    
    int32_t value;
    esp_err_t err = nvs_get_i32(nvs_handle_, key.c_str(), &value);
    
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return default_value;
    }
    
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to get int32 '%s': %s", key.c_str(), esp_err_to_name(err));
        return default_value;
    }
    
    return value;
}

ErrorCode ConfigManager::set_uint32(const std::string& key, uint32_t value) {
    if (!initialized_) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_set_u32(nvs_handle_, key.c_str(), value);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set uint32 '%s': %s", key.c_str(), esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

uint32_t ConfigManager::get_uint32(const std::string& key, uint32_t default_value) {
    if (!initialized_) return default_value;
    
    uint32_t value;
    esp_err_t err = nvs_get_u32(nvs_handle_, key.c_str(), &value);
    
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return default_value;
    }
    
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to get uint32 '%s': %s", key.c_str(), esp_err_to_name(err));
        return default_value;
    }
    
    return value;
}

ErrorCode ConfigManager::set_float(const std::string& key, float value) {
    // NVS doesn't have native float support, so we store as blob
    return set_blob(key, &value, sizeof(float));
}

float ConfigManager::get_float(const std::string& key, float default_value) {
    float value;
    size_t bytes_read = get_blob(key, &value, sizeof(float));
    
    if (bytes_read != sizeof(float)) {
        return default_value;
    }
    
    return value;
}

ErrorCode ConfigManager::set_bool(const std::string& key, bool value) {
    return set_uint32(key, value ? 1 : 0);
}

bool ConfigManager::get_bool(const std::string& key, bool default_value) {
    return get_uint32(key, default_value ? 1 : 0) != 0;
}

ErrorCode ConfigManager::set_blob(const std::string& key, const void* data, size_t length) {
    if (!initialized_ || !data || length == 0) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_set_blob(nvs_handle_, key.c_str(), data, length);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set blob '%s': %s", key.c_str(), esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

size_t ConfigManager::get_blob(const std::string& key, void* data, size_t max_length) {
    if (!initialized_ || !data || max_length == 0) return 0;
    
    size_t required_size = 0;
    esp_err_t err = nvs_get_blob(nvs_handle_, key.c_str(), nullptr, &required_size);
    
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return 0;
    }
    
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to get blob size for '%s': %s", key.c_str(), esp_err_to_name(err));
        return 0;
    }
    
    if (required_size > max_length) {
        ESP_LOGW(TAG, "Blob '%s' too large: %d > %d", key.c_str(), required_size, max_length);
        return 0;
    }
    
    err = nvs_get_blob(nvs_handle_, key.c_str(), data, &required_size);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to get blob '%s': %s", key.c_str(), esp_err_to_name(err));
        return 0;
    }
    
    return required_size;
}

bool ConfigManager::has_key(const std::string& key) {
    if (!initialized_) return false;
    
    size_t required_size = 0;
    esp_err_t err = nvs_get_blob(nvs_handle_, key.c_str(), nullptr, &required_size);
    
    return err != ESP_ERR_NVS_NOT_FOUND;
}

ErrorCode ConfigManager::remove_key(const std::string& key) {
    if (!initialized_) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_erase_key(nvs_handle_, key.c_str());
    if (err != ESP_OK && err != ESP_ERR_NVS_NOT_FOUND) {
        ESP_LOGE(TAG, "Failed to remove key '%s': %s", key.c_str(), esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::clear_all() {
    if (!initialized_) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_erase_all(nvs_handle_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to clear all keys: %s", esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return commit();
}

ErrorCode ConfigManager::commit() {
    if (!initialized_) return ErrorCode::INIT_FAILED;
    
    esp_err_t err = nvs_commit(nvs_handle_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to commit changes: %s", esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::load_audio_config(AudioConfig& config) {
    config.sample_rate = get_uint32("audio.sample_rate", 16000);
    config.channels = static_cast<uint8_t>(get_uint32("audio.channels", 1));
    config.bits_per_sample = static_cast<uint8_t>(get_uint32("audio.bits_per_sample", 16));
    config.frame_size = get_uint32("audio.frame_size", 320);
    config.buffer_count = get_uint32("audio.buffer_count", 8);
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::save_audio_config(const AudioConfig& config) {
    set_uint32("audio.sample_rate", config.sample_rate);
    set_uint32("audio.channels", config.channels);
    set_uint32("audio.bits_per_sample", config.bits_per_sample);
    set_uint32("audio.frame_size", config.frame_size);
    set_uint32("audio.buffer_count", config.buffer_count);
    
    return commit();
}

ErrorCode ConfigManager::load_network_config(NetworkConfig& config) {
    config.ssid = get_string("network.ssid", "");
    config.password = get_string("network.password", "");
    config.server_uri = get_string("network.server_uri", "wss://assistant.lan/stt");
    config.node_id = get_string("network.node_id", "unknown");
    config.reconnect_delay_ms = get_uint32("network.reconnect_delay_ms", 5000);
    config.max_retry_count = get_uint32("network.max_retry_count", 10);
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::save_network_config(const NetworkConfig& config) {
    set_string("network.ssid", config.ssid);
    set_string("network.password", config.password);
    set_string("network.server_uri", config.server_uri);
    set_string("network.node_id", config.node_id);
    set_uint32("network.reconnect_delay_ms", config.reconnect_delay_ms);
    set_uint32("network.max_retry_count", config.max_retry_count);
    
    return commit();
}

ErrorCode ConfigManager::load_wake_word_config(WakeWordConfig& config) {
    config.threshold = get_float("ww.threshold", 0.9f);
    config.trigger_duration_ms = get_uint32("ww.trigger_duration_ms", 450);
    config.back_buffer_ms = get_uint32("ww.back_buffer_ms", 300);
    config.use_psram = get_bool("ww.use_psram", true);
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::save_wake_word_config(const WakeWordConfig& config) {
    set_float("ww.threshold", config.threshold);
    set_uint32("ww.trigger_duration_ms", config.trigger_duration_ms);
    set_uint32("ww.back_buffer_ms", config.back_buffer_ms);
    set_bool("ww.use_psram", config.use_psram);
    
    return commit();
}

ErrorCode ConfigManager::load_ui_config(UIConfig& config) {
    config.display_width = static_cast<uint16_t>(get_uint32("ui.display_width", 412));
    config.display_height = static_cast<uint16_t>(get_uint32("ui.display_height", 412));
    config.brightness = static_cast<uint8_t>(get_uint32("ui.brightness", 80));
    config.idle_timeout_ms = get_uint32("ui.idle_timeout_ms", 30000);
    config.show_debug_info = get_bool("ui.show_debug_info", false);
    
    return ErrorCode::SUCCESS;
}

ErrorCode ConfigManager::save_ui_config(const UIConfig& config) {
    set_uint32("ui.display_width", config.display_width);
    set_uint32("ui.display_height", config.display_height);
    set_uint32("ui.brightness", config.brightness);
    set_uint32("ui.idle_timeout_ms", config.idle_timeout_ms);
    set_bool("ui.show_debug_info", config.show_debug_info);
    
    return commit();
}

ErrorCode ConfigManager::open_nvs() {
    esp_err_t err = nvs_open(namespace_.c_str(), NVS_READWRITE, &nvs_handle_);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS namespace '%s': %s", 
                namespace_.c_str(), esp_err_to_name(err));
        return ErrorCode::INIT_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

void ConfigManager::close_nvs() {
    if (nvs_handle_ != 0) {
        nvs_close(nvs_handle_);
        nvs_handle_ = 0;
    }
    initialized_ = false;
}

} // namespace irene 