#pragma once

#include "core/types.hpp"
#include "driver/i2s.h"

namespace irene {

/**
 * I2S driver for audio capture from ES8311 codec
 * Handles DMA-based audio streaming with configurable parameters
 */
class I2SDriver {
public:
    I2SDriver();
    ~I2SDriver();
    
    // Initialize I2S with audio configuration
    ErrorCode initialize(const AudioConfig& config);
    
    // Control
    ErrorCode start();
    ErrorCode stop();
    
    // Audio I/O
    esp_err_t read_frame(uint8_t* data, size_t length, size_t* bytes_read);
    esp_err_t write_frame(const uint8_t* data, size_t length);
    
    // Configuration
    void set_gain(int8_t gain_db);
    void set_sample_rate(uint32_t sample_rate);
    
    // Status
    bool is_running() const { return is_running_; }
    uint32_t get_sample_rate() const { return sample_rate_; }
    size_t get_frame_size() const { return frame_size_; }

private:
    ErrorCode configure_i2s_pins();
    ErrorCode configure_i2s_driver();
    
    AudioConfig config_;
    i2s_config_t i2s_config_;
    i2s_pin_config_t pin_config_;
    
    bool is_running_;
    uint32_t sample_rate_;
    size_t frame_size_;
    i2s_port_t i2s_port_;
};

} // namespace irene 