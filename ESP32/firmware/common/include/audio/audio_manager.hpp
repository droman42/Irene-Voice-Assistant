#pragma once

#include "core/types.hpp"
#include <functional>
#include <memory>

namespace irene {

class I2SDriver;
class VADProcessor;
class RingBuffer;

/**
 * Manages audio capture, VAD, and streaming
 * Coordinates I2S DMA, voice activity detection, and audio buffering
 */
class AudioManager {
public:
    using AudioDataCallback = std::function<void(const int16_t* data, size_t samples)>;
    using VADCallback = std::function<void(bool voice_detected)>;

    AudioManager();
    ~AudioManager();

    // Initialize audio subsystem
    ErrorCode initialize(const AudioConfig& config);
    
    // Control
    ErrorCode start_capture();
    ErrorCode stop_capture();
    ErrorCode start_streaming();
    ErrorCode stop_streaming();
    
    // Configuration
    void set_gain(int8_t gain_db);  // -6 to +18 dB range
    void set_vad_sensitivity(float sensitivity);
    
    // Callbacks
    void set_audio_data_callback(AudioDataCallback callback);
    void set_vad_callback(VADCallback callback);
    
    // Back buffer for wake word context (300ms)
    size_t get_back_buffer_samples(int16_t* buffer, size_t max_samples);
    
    // Status
    bool is_capturing() const { return is_capturing_; }
    bool is_streaming() const { return is_streaming_; }
    bool is_voice_detected() const;
    uint32_t get_sample_rate() const { return config_.sample_rate; }
    
    // Statistics
    uint32_t get_samples_captured() const;
    uint32_t get_samples_streamed() const;
    float get_audio_level() const;  // Current RMS level
    
private:
    void audio_task();
    void process_audio_frame(const int16_t* data, size_t samples);
    static void audio_task_wrapper(void* arg);
    
    AudioConfig config_;
    bool is_capturing_;
    bool is_streaming_;
    
    // Components
    std::unique_ptr<I2SDriver> i2s_driver_;
    std::unique_ptr<VADProcessor> vad_processor_;
    std::unique_ptr<RingBuffer> audio_buffer_;
    std::unique_ptr<RingBuffer> back_buffer_;
    
    // Callbacks
    AudioDataCallback audio_data_callback_;
    VADCallback vad_callback_;
    
    // Task management
    TaskHandle_t audio_task_handle_;
    SemaphoreHandle_t audio_mutex_;
    
    // Statistics
    uint32_t samples_captured_;
    uint32_t samples_streamed_;
    float current_audio_level_;
}; 