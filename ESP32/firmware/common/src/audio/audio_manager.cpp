#include "audio/audio_manager.hpp"
#include "hardware/i2s_driver.hpp"
#include "audio/vad_processor.hpp"
#include "utils/ring_buffer.hpp"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_timer.h"
#include <cstring>
#include <algorithm>

static const char* TAG = "AudioManager";

namespace irene {

AudioManager::AudioManager()
    : is_capturing_(false)
    , is_streaming_(false)
    , audio_task_handle_(nullptr)
    , audio_mutex_(nullptr)
    , samples_captured_(0)
    , samples_streamed_(0)
    , current_audio_level_(0.0f) {
}

AudioManager::~AudioManager() {
    stop_capture();
    
    if (audio_mutex_) {
        vSemaphoreDelete(audio_mutex_);
    }
}

ErrorCode AudioManager::initialize(const AudioConfig& config) {
    ESP_LOGI(TAG, "Initializing audio manager...");
    
    config_ = config;
    
    // Create mutex for thread safety
    audio_mutex_ = xSemaphoreCreateMutex();
    if (!audio_mutex_) {
        ESP_LOGE(TAG, "Failed to create audio mutex");
        return ErrorCode::AUDIO_FAILED;
    }
    
    try {
        // Initialize I2S driver
        i2s_driver_ = std::make_unique<I2SDriver>();
        ErrorCode result = i2s_driver_->initialize(config);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize I2S driver");
            return result;
        }
        
        // Initialize VAD processor
        vad_processor_ = std::make_unique<VADProcessor>();
        result = vad_processor_->initialize(config.sample_rate);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize VAD processor");
            return result;
        }
        
        // Create audio buffers
        size_t buffer_size_samples = config.frame_size * config.buffer_count;
        audio_buffer_ = std::make_unique<RingBuffer>(buffer_size_samples * sizeof(int16_t));
        
        // Back buffer for wake word context (300ms)
        size_t back_buffer_samples = (config.sample_rate * 300) / 1000; // 300ms
        back_buffer_ = std::make_unique<RingBuffer>(back_buffer_samples * sizeof(int16_t));
        
        ESP_LOGI(TAG, "Audio manager initialized successfully");
        ESP_LOGI(TAG, "Sample rate: %u Hz, Frame size: %u samples", 
                config.sample_rate, config.frame_size);
        
        return ErrorCode::SUCCESS;
        
    } catch (const std::exception& e) {
        ESP_LOGE(TAG, "Exception during audio manager initialization: %s", e.what());
        return ErrorCode::AUDIO_FAILED;
    }
}

ErrorCode AudioManager::start_capture() {
    if (is_capturing_) {
        return ErrorCode::SUCCESS;
    }
    
    ESP_LOGI(TAG, "Starting audio capture...");
    
    // Start I2S
    ErrorCode result = i2s_driver_->start();
    if (result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to start I2S driver");
        return result;
    }
    
    // Create audio processing task
    BaseType_t task_result = xTaskCreatePinnedToCore(
        audio_task_wrapper,
        "audio_task",
        4096,  // Stack size
        this,
        10,    // Priority
        &audio_task_handle_,
        0      // Core 0 for real-time audio
    );
    
    if (task_result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create audio task");
        i2s_driver_->stop();
        return ErrorCode::AUDIO_FAILED;
    }
    
    is_capturing_ = true;
    ESP_LOGI(TAG, "Audio capture started");
    
    return ErrorCode::SUCCESS;
}

ErrorCode AudioManager::stop_capture() {
    if (!is_capturing_) {
        return ErrorCode::SUCCESS;
    }
    
    ESP_LOGI(TAG, "Stopping audio capture...");
    
    is_capturing_ = false;
    is_streaming_ = false;
    
    // Delete audio task
    if (audio_task_handle_) {
        vTaskDelete(audio_task_handle_);
        audio_task_handle_ = nullptr;
    }
    
    // Stop I2S
    if (i2s_driver_) {
        i2s_driver_->stop();
    }
    
    ESP_LOGI(TAG, "Audio capture stopped");
    return ErrorCode::SUCCESS;
}

ErrorCode AudioManager::start_streaming() {
    xSemaphoreTake(audio_mutex_, portMAX_DELAY);
    is_streaming_ = true;
    xSemaphoreGive(audio_mutex_);
    
    ESP_LOGI(TAG, "Audio streaming started");
    return ErrorCode::SUCCESS;
}

ErrorCode AudioManager::stop_streaming() {
    xSemaphoreTake(audio_mutex_, portMAX_DELAY);
    is_streaming_ = false;
    xSemaphoreGive(audio_mutex_);
    
    ESP_LOGI(TAG, "Audio streaming stopped");
    return ErrorCode::SUCCESS;
}

void AudioManager::set_gain(int8_t gain_db) {
    if (i2s_driver_) {
        i2s_driver_->set_gain(gain_db);
    }
}

void AudioManager::set_vad_sensitivity(float sensitivity) {
    if (vad_processor_) {
        vad_processor_->set_sensitivity(sensitivity);
    }
}

void AudioManager::set_audio_data_callback(AudioDataCallback callback) {
    audio_data_callback_ = callback;
}

void AudioManager::set_vad_callback(VADCallback callback) {
    vad_callback_ = callback;
}

size_t AudioManager::get_back_buffer_samples(int16_t* buffer, size_t max_samples) {
    if (!back_buffer_ || !buffer) {
        return 0;
    }
    
    xSemaphoreTake(audio_mutex_, portMAX_DELAY);
    
    size_t available_bytes = back_buffer_->available();
    size_t available_samples = available_bytes / sizeof(int16_t);
    size_t samples_to_copy = std::min(available_samples, max_samples);
    
    size_t bytes_read = back_buffer_->read(reinterpret_cast<uint8_t*>(buffer), 
                                          samples_to_copy * sizeof(int16_t));
    
    xSemaphoreGive(audio_mutex_);
    
    return bytes_read / sizeof(int16_t);
}

bool AudioManager::is_voice_detected() const {
    return vad_processor_ ? vad_processor_->is_voice_detected() : false;
}

uint32_t AudioManager::get_samples_captured() const {
    return samples_captured_;
}

uint32_t AudioManager::get_samples_streamed() const {
    return samples_streamed_;
}

float AudioManager::get_audio_level() const {
    return current_audio_level_;
}

void AudioManager::audio_task_wrapper(void* arg) {
    static_cast<AudioManager*>(arg)->audio_task();
}

void AudioManager::audio_task() {
    ESP_LOGI(TAG, "Audio task started");
    
    const size_t frame_size_bytes = config_.frame_size * sizeof(int16_t);
    int16_t* audio_frame = static_cast<int16_t*>(malloc(frame_size_bytes));
    
    if (!audio_frame) {
        ESP_LOGE(TAG, "Failed to allocate audio frame buffer");
        return;
    }
    
    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t frame_period = pdMS_TO_TICKS(20); // 20ms frame period
    
    while (is_capturing_) {
        // Read audio frame from I2S
        size_t bytes_read = 0;
        esp_err_t result = i2s_driver_->read_frame(
            reinterpret_cast<uint8_t*>(audio_frame), 
            frame_size_bytes, 
            &bytes_read
        );
        
        if (result == ESP_OK && bytes_read == frame_size_bytes) {
            size_t samples_read = bytes_read / sizeof(int16_t);
            process_audio_frame(audio_frame, samples_read);
            
            samples_captured_ += samples_read;
        } else {
            ESP_LOGW(TAG, "I2S read failed or incomplete: %s, bytes: %d/%d", 
                    esp_err_to_name(result), bytes_read, frame_size_bytes);
        }
        
        // Maintain frame timing
        vTaskDelayUntil(&last_wake_time, frame_period);
    }
    
    free(audio_frame);
    ESP_LOGI(TAG, "Audio task ended");
}

void AudioManager::process_audio_frame(const int16_t* data, size_t samples) {
    if (!data || samples == 0) return;
    
    xSemaphoreTake(audio_mutex_, portMAX_DELAY);
    
    // Calculate audio level (RMS)
    int64_t sum_squares = 0;
    for (size_t i = 0; i < samples; i++) {
        sum_squares += static_cast<int64_t>(data[i]) * data[i];
    }
    current_audio_level_ = sqrtf(static_cast<float>(sum_squares) / samples) / 32768.0f;
    
    // Store in back buffer for wake word context
    if (back_buffer_) {
        back_buffer_->write(reinterpret_cast<const uint8_t*>(data), 
                          samples * sizeof(int16_t));
    }
    
    // Process with VAD
    bool voice_detected = false;
    if (vad_processor_) {
        voice_detected = vad_processor_->process_frame(data, samples);
        
        // Call VAD callback if voice state changed
        static bool last_voice_state = false;
        if (voice_detected != last_voice_state) {
            last_voice_state = voice_detected;
            if (vad_callback_) {
                vad_callback_(voice_detected);
            }
        }
    }
    
    // Stream audio if active and voice detected
    bool should_stream = is_streaming_ && (voice_detected || current_audio_level_ > 0.01f);
    
    if (should_stream && audio_data_callback_) {
        audio_data_callback_(data, samples);
        samples_streamed_ += samples;
    }
    
    xSemaphoreGive(audio_mutex_);
}

} // namespace irene 