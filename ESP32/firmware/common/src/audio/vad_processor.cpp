#include "audio/vad_processor.hpp"
#include "esp_log.h"
#include <cmath>
#include <algorithm>
#include <cstring>

static const char* TAG = "VADProcessor";

namespace irene {

VADProcessor::VADProcessor()
    : sample_rate_(16000)
    , sensitivity_(0.5f)
    , energy_threshold_(0.01f)
    , silence_duration_ms_(200)
    , voice_duration_ms_(100)
    , voice_detected_(false)
    , current_energy_(0.0f)
    , history_index_(0)
    , consecutive_voice_frames_(0)
    , consecutive_silence_frames_(0)
    , frames_for_voice_decision_(5)
    , frames_for_silence_decision_(10)
    , voice_frames_(0)
    , silence_frames_(0)
    , total_frames_(0) {
    
    // Initialize energy history
    std::memset(energy_history_, 0, sizeof(energy_history_));
}

VADProcessor::~VADProcessor() = default;

ErrorCode VADProcessor::initialize(uint32_t sample_rate) {
    ESP_LOGI(TAG, "Initializing VAD processor...");
    
    sample_rate_ = sample_rate;
    
    // Calculate frame decision thresholds based on sample rate and frame size
    // Assuming 20ms frames
    uint32_t frames_per_second = 50; // 1000ms / 20ms
    frames_for_voice_decision_ = (voice_duration_ms_ * frames_per_second) / 1000;
    frames_for_silence_decision_ = (silence_duration_ms_ * frames_per_second) / 1000;
    
    // Ensure minimum thresholds
    frames_for_voice_decision_ = std::max(frames_for_voice_decision_, 2u);
    frames_for_silence_decision_ = std::max(frames_for_silence_decision_, 5u);
    
    ESP_LOGI(TAG, "VAD initialized: %u Hz, voice=%u frames, silence=%u frames",
             sample_rate_, frames_for_voice_decision_, frames_for_silence_decision_);
    
    return ErrorCode::SUCCESS;
}

bool VADProcessor::process_frame(const int16_t* audio_data, size_t samples) {
    if (!audio_data || samples == 0) {
        return voice_detected_;
    }
    
    total_frames_++;
    
    // Calculate energy and zero crossing rate
    float energy = calculate_energy(audio_data, samples);
    float zcr = calculate_zero_crossing_rate(audio_data, samples);
    
    // Update energy history for smoothing
    energy_history_[history_index_] = energy;
    history_index_ = (history_index_ + 1) % 8;
    
    // Calculate smoothed energy
    float smoothed_energy = 0.0f;
    for (int i = 0; i < 8; i++) {
        smoothed_energy += energy_history_[i];
    }
    smoothed_energy /= 8.0f;
    
    current_energy_ = smoothed_energy;
    
    // Adaptive threshold based on sensitivity
    float adaptive_threshold = energy_threshold_ * (2.0f - sensitivity_);
    
    // Voice detection logic combining energy and ZCR
    bool current_detection = false;
    
    // Primary energy-based detection
    if (smoothed_energy > adaptive_threshold) {
        current_detection = true;
    }
    
    // Secondary ZCR-based detection for low-energy speech
    if (zcr > 0.1f && smoothed_energy > adaptive_threshold * 0.5f) {
        current_detection = true;
    }
    
    // Apply hysteresis to prevent rapid switching
    bool final_detection = apply_hysteresis(current_detection);
    
    // Update statistics
    if (final_detection) {
        voice_frames_++;
    } else {
        silence_frames_++;
    }
    
    return final_detection;
}

void VADProcessor::set_sensitivity(float sensitivity) {
    sensitivity_ = std::max(0.0f, std::min(1.0f, sensitivity));
    ESP_LOGD(TAG, "VAD sensitivity set to: %.3f", sensitivity_);
}

void VADProcessor::set_energy_threshold(float threshold) {
    energy_threshold_ = std::max(0.001f, threshold);
    ESP_LOGD(TAG, "Energy threshold set to: %.6f", energy_threshold_);
}

void VADProcessor::set_silence_duration_ms(uint32_t duration_ms) {
    silence_duration_ms_ = duration_ms;
    uint32_t frames_per_second = 50; // 20ms frames
    frames_for_silence_decision_ = (duration_ms * frames_per_second) / 1000;
    frames_for_silence_decision_ = std::max(frames_for_silence_decision_, 5u);
    ESP_LOGD(TAG, "Silence duration set to: %u ms (%u frames)", 
             duration_ms, frames_for_silence_decision_);
}

void VADProcessor::set_voice_duration_ms(uint32_t duration_ms) {
    voice_duration_ms_ = duration_ms;
    uint32_t frames_per_second = 50; // 20ms frames
    frames_for_voice_decision_ = (duration_ms * frames_per_second) / 1000;
    frames_for_voice_decision_ = std::max(frames_for_voice_decision_, 2u);
    ESP_LOGD(TAG, "Voice duration set to: %u ms (%u frames)", 
             duration_ms, frames_for_voice_decision_);
}

void VADProcessor::reset_stats() {
    voice_frames_ = 0;
    silence_frames_ = 0;
    total_frames_ = 0;
    consecutive_voice_frames_ = 0;
    consecutive_silence_frames_ = 0;
    std::memset(energy_history_, 0, sizeof(energy_history_));
    history_index_ = 0;
    ESP_LOGI(TAG, "VAD statistics reset");
}

float VADProcessor::calculate_energy(const int16_t* audio_data, size_t samples) {
    if (!audio_data || samples == 0) return 0.0f;
    
    int64_t sum_squares = 0;
    for (size_t i = 0; i < samples; i++) {
        int32_t sample = audio_data[i];
        sum_squares += sample * sample;
    }
    
    // Normalize by sample count and max value
    float rms = sqrtf(static_cast<float>(sum_squares) / samples) / 32768.0f;
    return rms;
}

float VADProcessor::calculate_zero_crossing_rate(const int16_t* audio_data, size_t samples) {
    if (!audio_data || samples < 2) return 0.0f;
    
    uint32_t zero_crossings = 0;
    
    for (size_t i = 1; i < samples; i++) {
        // Check for sign change
        if ((audio_data[i-1] >= 0 && audio_data[i] < 0) ||
            (audio_data[i-1] < 0 && audio_data[i] >= 0)) {
            zero_crossings++;
        }
    }
    
    return static_cast<float>(zero_crossings) / (samples - 1);
}

bool VADProcessor::apply_hysteresis(bool current_detection) {
    if (current_detection) {
        consecutive_voice_frames_++;
        consecutive_silence_frames_ = 0;
        
        // Switch to voice if we have enough consecutive voice frames
        if (!voice_detected_ && consecutive_voice_frames_ >= frames_for_voice_decision_) {
            voice_detected_ = true;
            ESP_LOGD(TAG, "Voice detected after %u frames", consecutive_voice_frames_);
        }
    } else {
        consecutive_silence_frames_++;
        consecutive_voice_frames_ = 0;
        
        // Switch to silence if we have enough consecutive silence frames
        if (voice_detected_ && consecutive_silence_frames_ >= frames_for_silence_decision_) {
            voice_detected_ = false;
            ESP_LOGD(TAG, "Silence detected after %u frames", consecutive_silence_frames_);
        }
    }
    
    return voice_detected_;
}

} // namespace irene 