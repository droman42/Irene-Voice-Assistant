#pragma once

#include "core/types.hpp"
#include "nvs_flash.h"
#include <string>
#include <map>

namespace irene {

/**
 * Configuration manager for persistent settings storage
 * Uses NVS (Non-Volatile Storage) for configuration persistence
 */
class ConfigManager {
public:
    ConfigManager();
    ~ConfigManager();
    
    // Initialize NVS and load configurations
    ErrorCode initialize();
    
    // String configuration
    ErrorCode set_string(const std::string& key, const std::string& value);
    std::string get_string(const std::string& key, const std::string& default_value = "");
    
    // Integer configuration
    ErrorCode set_int32(const std::string& key, int32_t value);
    int32_t get_int32(const std::string& key, int32_t default_value = 0);
    
    ErrorCode set_uint32(const std::string& key, uint32_t value);
    uint32_t get_uint32(const std::string& key, uint32_t default_value = 0);
    
    // Float configuration
    ErrorCode set_float(const std::string& key, float value);
    float get_float(const std::string& key, float default_value = 0.0f);
    
    // Boolean configuration
    ErrorCode set_bool(const std::string& key, bool value);
    bool get_bool(const std::string& key, bool default_value = false);
    
    // Binary data configuration
    ErrorCode set_blob(const std::string& key, const void* data, size_t length);
    size_t get_blob(const std::string& key, void* data, size_t max_length);
    
    // Key management
    bool has_key(const std::string& key);
    ErrorCode remove_key(const std::string& key);
    ErrorCode clear_all();
    
    // Commit changes
    ErrorCode commit();
    
    // Configuration presets
    ErrorCode load_audio_config(AudioConfig& config);
    ErrorCode save_audio_config(const AudioConfig& config);
    
    ErrorCode load_network_config(NetworkConfig& config);
    ErrorCode save_network_config(const NetworkConfig& config);
    
    ErrorCode load_wake_word_config(WakeWordConfig& config);
    ErrorCode save_wake_word_config(const WakeWordConfig& config);
    
    ErrorCode load_ui_config(UIConfig& config);
    ErrorCode save_ui_config(const UIConfig& config);

private:
    nvs_handle_t nvs_handle_;
    bool initialized_;
    std::string namespace_;
    
    ErrorCode open_nvs();
    void close_nvs();
};

} // namespace irene 