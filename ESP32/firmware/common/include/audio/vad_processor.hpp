#pragma once

#include "core/types.hpp"
#include <cstdint>

namespace irene {

/**
 * Voice Activity Detection processor
 * Uses energy-based and spectral features to detect speech
 */
class VADProcessor {
public:
    VADProcessor();
    ~VADProcessor();
    
    // Initialize VAD with sample rate
    ErrorCode initialize(uint32_t sample_rate);
    
    // Process audio frame and return voice detection result
    bool process_frame(const int16_t* audio_data, size_t samples);
    
    // Configuration
    void set_sensitivity(float sensitivity);  // 0.0 to 1.0
    void set_energy_threshold(float threshold);
    void set_silence_duration_ms(uint32_t duration_ms);
    void set_voice_duration_ms(uint32_t duration_ms);
    
    // Status
    bool is_voice_detected() const { return voice_detected_; }
    float get_current_energy() const { return current_energy_; }
    float get_sensitivity() const { return sensitivity_; }
    
    // Statistics
    uint32_t get_voice_frames() const { return voice_frames_; }
    uint32_t get_silence_frames() const { return silence_frames_; }
    void reset_stats();

private:
    float calculate_energy(const int16_t* audio_data, size_t samples);
    float calculate_zero_crossing_rate(const int16_t* audio_data, size_t samples);
    bool apply_hysteresis(bool current_detection);
    
    uint32_t sample_rate_;
    float sensitivity_;
    float energy_threshold_;
    uint32_t silence_duration_ms_;
    uint32_t voice_duration_ms_;
    
    bool voice_detected_;
    float current_energy_;
    float energy_history_[8];  // Simple smoothing
    size_t history_index_;
    
    uint32_t consecutive_voice_frames_;
    uint32_t consecutive_silence_frames_;
    uint32_t frames_for_voice_decision_;
    uint32_t frames_for_silence_decision_;
    
    // Statistics
    uint32_t voice_frames_;
    uint32_t silence_frames_;
    uint32_t total_frames_;
};

} // namespace irene 