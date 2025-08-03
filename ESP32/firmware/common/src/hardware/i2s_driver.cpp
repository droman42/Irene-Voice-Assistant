#include "hardware/i2s_driver.hpp"
#include "esp_log.h"
#include "driver/i2s.h"
#include "driver/gpio.h"
#include "esp_timer.h"

static const char* TAG = "I2SDriver";

namespace irene {

I2SDriver::I2SDriver()
    : is_running_(false)
    , sample_rate_(16000)
    , frame_size_(320)
    , i2s_port_(I2S_NUM_0) {
}

I2SDriver::~I2SDriver() {
    stop();
}

ErrorCode I2SDriver::initialize(const AudioConfig& config) {
    ESP_LOGI(TAG, "Initializing I2S driver...");
    
    config_ = config;
    sample_rate_ = config.sample_rate;
    frame_size_ = config.frame_size;
    
    // Configure I2S pins
    ErrorCode result = configure_i2s_pins();
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to configure I2S pins");
        return result;
    }
    
    // Configure I2S driver
    result = configure_i2s_driver();
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to configure I2S driver");
        return result;
    }
    
    ESP_LOGI(TAG, "I2S driver initialized successfully");
    ESP_LOGI(TAG, "Sample rate: %u Hz, Frame size: %u samples, Channels: %u",
             config.sample_rate, config.frame_size, config.channels);
    
    return ErrorCode::SUCCESS;
}

ErrorCode I2SDriver::start() {
    if (is_running_) {
        ESP_LOGW(TAG, "I2S driver already running");
        return ErrorCode::SUCCESS;
    }
    
    ESP_LOGI(TAG, "Starting I2S driver...");
    
    esp_err_t result = i2s_start(i2s_port_);
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start I2S: %s", esp_err_to_name(result));
        return ErrorCode::AUDIO_FAILED;
    }
    
    // Clear any existing data in the DMA buffer
    i2s_zero_dma_buffer(i2s_port_);
    
    is_running_ = true;
    ESP_LOGI(TAG, "I2S driver started");
    
    return ErrorCode::SUCCESS;
}

ErrorCode I2SDriver::stop() {
    if (!is_running_) {
        return ErrorCode::SUCCESS;
    }
    
    ESP_LOGI(TAG, "Stopping I2S driver...");
    
    esp_err_t result = i2s_stop(i2s_port_);
    if (result != ESP_OK) {
        ESP_LOGW(TAG, "Failed to stop I2S: %s", esp_err_to_name(result));
    }
    
    is_running_ = false;
    ESP_LOGI(TAG, "I2S driver stopped");
    
    return ErrorCode::SUCCESS;
}

esp_err_t I2SDriver::read_frame(uint8_t* data, size_t length, size_t* bytes_read) {
    if (!is_running_ || !data || length == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    
    return i2s_read(i2s_port_, data, length, bytes_read, portMAX_DELAY);
}

esp_err_t I2SDriver::write_frame(const uint8_t* data, size_t length) {
    if (!is_running_ || !data || length == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    
    size_t bytes_written = 0;
    return i2s_write(i2s_port_, data, length, &bytes_written, portMAX_DELAY);
}

void I2SDriver::set_gain(int8_t gain_db) {
    // Gain control would be implemented via ES8311 codec I2C commands
    // This is a placeholder for codec-specific gain control
    ESP_LOGI(TAG, "Setting gain to: %d dB (codec control needed)", gain_db);
    
    // In a real implementation, this would:
    // 1. Calculate register values for the desired gain
    // 2. Send I2C commands to the ES8311 codec
    // 3. Update the analog/digital gain settings
    
    // Example pseudo-code:
    // es8311_set_mic_gain(gain_db);
    // es8311_set_adc_volume(gain_db);
}

void I2SDriver::set_sample_rate(uint32_t sample_rate) {
    if (sample_rate_ == sample_rate) {
        return;
    }
    
    ESP_LOGI(TAG, "Changing sample rate from %u to %u Hz", sample_rate_, sample_rate);
    
    bool was_running = is_running_;
    
    // Stop I2S if running
    if (was_running) {
        stop();
    }
    
    // Update configuration
    sample_rate_ = sample_rate;
    config_.sample_rate = sample_rate;
    
    // Reconfigure I2S driver
    i2s_driver_uninstall(i2s_port_);
    configure_i2s_driver();
    
    // Restart if it was running
    if (was_running) {
        start();
    }
}

ErrorCode I2SDriver::configure_i2s_pins() {
    ESP_LOGI(TAG, "Configuring I2S pins...");
    
    // I2S pin configuration for ES8311 codec
    pin_config_.bck_io_num = GPIO_NUM_4;    // Bit clock
    pin_config_.ws_io_num = GPIO_NUM_5;     // Word select (LRCLK)
    pin_config_.data_out_num = GPIO_NUM_7;  // Data out (to codec)
    pin_config_.data_in_num = GPIO_NUM_6;   // Data in (from codec)
    
    ESP_LOGI(TAG, "I2S pins configured - BCK:%d, WS:%d, DIN:%d, DOUT:%d",
             pin_config_.bck_io_num, pin_config_.ws_io_num,
             pin_config_.data_in_num, pin_config_.data_out_num);
    
    return ErrorCode::SUCCESS;
}

ErrorCode I2SDriver::configure_i2s_driver() {
    ESP_LOGI(TAG, "Configuring I2S driver...");
    
    // I2S configuration
    i2s_config_.mode = static_cast<i2s_mode_t>(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX);
    i2s_config_.sample_rate = sample_rate_;
    i2s_config_.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    i2s_config_.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT; // Mono
    i2s_config_.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    i2s_config_.intr_alloc_flags = ESP_INTR_FLAG_LEVEL2;
    i2s_config_.dma_buf_count = config_.buffer_count;
    i2s_config_.dma_buf_len = config_.frame_size;
    i2s_config_.use_apll = true;  // Use APLL for better clock accuracy
    i2s_config_.tx_desc_auto_clear = true;
    i2s_config_.fixed_mclk = 0;
    
    // Install I2S driver
    esp_err_t result = i2s_driver_install(i2s_port_, &i2s_config_, 0, nullptr);
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "Failed to install I2S driver: %s", esp_err_to_name(result));
        return ErrorCode::AUDIO_FAILED;
    }
    
    // Set I2S pins
    result = i2s_set_pin(i2s_port_, &pin_config_);
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set I2S pins: %s", esp_err_to_name(result));
        i2s_driver_uninstall(i2s_port_);
        return ErrorCode::AUDIO_FAILED;
    }
    
    // Configure I2S clock
    result = i2s_set_clk(i2s_port_, sample_rate_, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
    if (result != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set I2S clock: %s", esp_err_to_name(result));
        i2s_driver_uninstall(i2s_port_);
        return ErrorCode::AUDIO_FAILED;
    }
    
    ESP_LOGI(TAG, "I2S driver configured successfully");
    ESP_LOGI(TAG, "Mode: Master RX/TX, Sample rate: %u Hz, Bits: 16, Channels: 1",
             sample_rate_);
    ESP_LOGI(TAG, "DMA buffers: %u x %u samples, Use APLL: yes",
             config_.buffer_count, config_.frame_size);
    
    return ErrorCode::SUCCESS;
}

} // namespace irene 