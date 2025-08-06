#include "audio/mfcc_frontend.hpp"

#include "esp_log.h"
#include "esp_heap_caps.h"
#include <cmath>
#include <cstring>
#include <algorithm>

static const char* TAG = "MFCCFrontend";

// Mathematical constants
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace irene {

MFCCFrontend::MFCCFrontend()
    : initialized_(false)
    , use_psram_(true)
    , buffer_write_pos_(0)
    , samples_available_(0)
    , feature_frame_count_(0) {
}

MFCCFrontend::~MFCCFrontend() {
    // Smart pointers handle cleanup automatically
}

ErrorCode MFCCFrontend::initialize(bool use_psram) {
    ESP_LOGI(TAG, "Initializing MFCC frontend...");
    
    use_psram_ = use_psram;
    
    // Allocate audio input buffer
    size_t audio_buffer_bytes = INPUT_BUFFER_SIZE * sizeof(int16_t);
    audio_buffer_.reset(static_cast<int16_t*>(allocate_buffer(audio_buffer_bytes)));
    if (!audio_buffer_) {
        ESP_LOGE(TAG, "Failed to allocate audio buffer (%d bytes)", audio_buffer_bytes);
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Allocate MFCC computation buffers
    windowed_samples_.reset(static_cast<float*>(allocate_buffer(WINDOW_SAMPLES * sizeof(float))));
    fft_buffer_.reset(static_cast<float*>(allocate_buffer(WINDOW_SAMPLES * 2 * sizeof(float)))); // Complex FFT
    power_spectrum_.reset(static_cast<float*>(allocate_buffer((WINDOW_SAMPLES/2 + 1) * sizeof(float))));
    mel_energies_.reset(static_cast<float*>(allocate_buffer(N_MELS * sizeof(float))));
    log_mel_energies_.reset(static_cast<float*>(allocate_buffer(N_MELS * sizeof(float))));
    mfcc_coeffs_.reset(static_cast<float*>(allocate_buffer(N_MFCC * sizeof(float))));
    
    if (!windowed_samples_ || !fft_buffer_ || !power_spectrum_ || 
        !mel_energies_ || !log_mel_energies_ || !mfcc_coeffs_) {
        ESP_LOGE(TAG, "Failed to allocate MFCC computation buffers");
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Allocate feature output buffer
    features_.reset(static_cast<float*>(allocate_buffer(FEATURE_SIZE * sizeof(float))));
    if (!features_) {
        ESP_LOGE(TAG, "Failed to allocate feature buffer");
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Allocate precomputed tables
    hann_window_.reset(static_cast<float*>(allocate_buffer(WINDOW_SAMPLES * sizeof(float))));
    mel_filterbank_.reset(static_cast<float*>(allocate_buffer(N_MELS * (WINDOW_SAMPLES/2 + 1) * sizeof(float))));
    dct_matrix_.reset(static_cast<float*>(allocate_buffer(N_MFCC * N_MELS * sizeof(float))));
    
    if (!hann_window_ || !mel_filterbank_ || !dct_matrix_) {
        ESP_LOGE(TAG, "Failed to allocate precomputed tables");
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Setup precomputed tables
    if (!setup_tables()) {
        ESP_LOGE(TAG, "Failed to setup precomputed tables");
        return ErrorCode::WAKE_WORD_FAILED;
    }
    
    // Initialize state
    reset();
    
    initialized_ = true;
    ESP_LOGI(TAG, "MFCC frontend initialized successfully");
    ESP_LOGI(TAG, "Parameters: %d Hz, %d ms window, %d ms hop, %d mels, %d MFCCs, %dx%d features",
             SAMPLE_RATE, WINDOW_SIZE_MS, HOP_SIZE_MS, N_MELS, N_MFCC, N_FRAMES, N_MFCC);
    
    return ErrorCode::SUCCESS;
}

bool MFCCFrontend::process_samples(const int16_t* audio_data, size_t samples) {
    if (!initialized_ || !audio_data || samples == 0) {
        return false;
    }
    
    // Add samples to ring buffer
    for (size_t i = 0; i < samples; i++) {
        audio_buffer_[buffer_write_pos_] = audio_data[i];
        buffer_write_pos_ = (buffer_write_pos_ + 1) % INPUT_BUFFER_SIZE;
        
        if (samples_available_ < INPUT_BUFFER_SIZE) {
            samples_available_++;
        }
    }
    
    // Check if we can extract features (need enough data for 49 frames)
    if (samples_available_ >= INPUT_BUFFER_SIZE) {
        // Extract MFCC features frame by frame
        size_t start_pos = (buffer_write_pos_ >= INPUT_BUFFER_SIZE) ? 
                          (buffer_write_pos_ - INPUT_BUFFER_SIZE) : 
                          (INPUT_BUFFER_SIZE + buffer_write_pos_ - INPUT_BUFFER_SIZE);
        
        feature_frame_count_ = 0;
        
        for (size_t frame = 0; frame < N_FRAMES; frame++) {
            size_t frame_start = start_pos + frame * HOP_SAMPLES;
            
            // Extract windowed frame
            for (size_t i = 0; i < WINDOW_SAMPLES; i++) {
                size_t pos = (frame_start + i) % INPUT_BUFFER_SIZE;
                windowed_samples_[i] = static_cast<float>(audio_buffer_[pos]) / 32768.0f;
            }
            
            // Compute power spectrum
            compute_power_spectrum(windowed_samples_.get(), power_spectrum_.get());
            
            // Apply mel filterbank
            apply_mel_filterbank(power_spectrum_.get(), mel_energies_.get());
            
            // Compute MFCC
            compute_mfcc(mel_energies_.get(), mfcc_coeffs_.get());
            
            // Update feature matrix
            update_feature_matrix(mfcc_coeffs_.get());
        }
        
        return true; // New features available
    }
    
    return false;
}

bool MFCCFrontend::get_features(float* features) const {
    if (!initialized_ || !features || feature_frame_count_ != N_FRAMES) {
        return false;
    }
    
    std::memcpy(features, features_.get(), FEATURE_SIZE * sizeof(float));
    return true;
}

void MFCCFrontend::reset() {
    buffer_write_pos_ = 0;
    samples_available_ = 0;
    feature_frame_count_ = 0;
    
    if (audio_buffer_) {
        std::memset(audio_buffer_.get(), 0, INPUT_BUFFER_SIZE * sizeof(int16_t));
    }
    
    if (features_) {
        std::memset(features_.get(), 0, FEATURE_SIZE * sizeof(float));
    }
}

bool MFCCFrontend::has_sufficient_data() const {
    return samples_available_ >= INPUT_BUFFER_SIZE;
}

void* MFCCFrontend::allocate_buffer(size_t size) const {
    uint32_t caps = use_psram_ ? (MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT) : MALLOC_CAP_8BIT;
    return heap_caps_malloc(size, caps);
}

bool MFCCFrontend::setup_tables() {
    ESP_LOGI(TAG, "Setting up precomputed tables...");
    
    // Setup Hann window
    for (size_t i = 0; i < WINDOW_SAMPLES; i++) {
        hann_window_[i] = 0.5f * (1.0f - cosf(2.0f * M_PI * i / (WINDOW_SAMPLES - 1)));
    }
    
    // Setup mel filterbank
    const float mel_low = 0.0f;
    const float mel_high = 2595.0f * log10f(1.0f + (SAMPLE_RATE / 2.0f) / 700.0f);
    const size_t n_fft_bins = WINDOW_SAMPLES / 2 + 1;
    
    // Create mel scale points
    std::vector<float> mel_points(N_MELS + 2);
    for (size_t i = 0; i < N_MELS + 2; i++) {
        mel_points[i] = mel_low + (mel_high - mel_low) * i / (N_MELS + 1);
    }
    
    // Convert mel to Hz
    std::vector<float> hz_points(N_MELS + 2);
    for (size_t i = 0; i < N_MELS + 2; i++) {
        hz_points[i] = 700.0f * (powf(10.0f, mel_points[i] / 2595.0f) - 1.0f);
    }
    
    // Convert Hz to FFT bin numbers
    std::vector<size_t> bin_points(N_MELS + 2);
    for (size_t i = 0; i < N_MELS + 2; i++) {
        bin_points[i] = static_cast<size_t>(floorf((WINDOW_SAMPLES + 1) * hz_points[i] / SAMPLE_RATE));
    }
    
    // Create triangular mel filters
    std::memset(mel_filterbank_.get(), 0, N_MELS * n_fft_bins * sizeof(float));
    
    for (size_t m = 0; m < N_MELS; m++) {
        size_t left = bin_points[m];
        size_t center = bin_points[m + 1];
        size_t right = bin_points[m + 2];
        
        for (size_t k = left; k < center; k++) {
            if (center > left) {
                mel_filterbank_[m * n_fft_bins + k] = static_cast<float>(k - left) / (center - left);
            }
        }
        
        for (size_t k = center; k < right; k++) {
            if (right > center) {
                mel_filterbank_[m * n_fft_bins + k] = static_cast<float>(right - k) / (right - center);
            }
        }
    }
    
    // Setup DCT matrix
    for (size_t i = 0; i < N_MFCC; i++) {
        for (size_t j = 0; j < N_MELS; j++) {
            dct_matrix_[i * N_MELS + j] = cosf(M_PI * i * (j + 0.5f) / N_MELS);
            if (i == 0) {
                dct_matrix_[i * N_MELS + j] *= sqrtf(1.0f / N_MELS);
            } else {
                dct_matrix_[i * N_MELS + j] *= sqrtf(2.0f / N_MELS);
            }
        }
    }
    
    ESP_LOGI(TAG, "Precomputed tables setup complete");
    return true;
}

void MFCCFrontend::apply_window(const int16_t* samples, float* windowed_output) {
    // This method is now unused - windowing is done inline in process_samples
    // Kept for interface compatibility
    *windowed_output = static_cast<float>(*samples) / 32768.0f;
}

void MFCCFrontend::compute_power_spectrum(const float* windowed_samples, float* power_spec) {
    // Apply Hann window
    for (size_t i = 0; i < WINDOW_SAMPLES; i++) {
        fft_buffer_[2*i] = windowed_samples[i] * hann_window_[i];  // Real part
        fft_buffer_[2*i + 1] = 0.0f;  // Imaginary part
    }
    
    // Simple DFT implementation (could be optimized with FFT library)
    const size_t n_fft_bins = WINDOW_SAMPLES / 2 + 1;
    for (size_t k = 0; k < n_fft_bins; k++) {
        float real = 0.0f, imag = 0.0f;
        for (size_t n = 0; n < WINDOW_SAMPLES; n++) {
            float angle = -2.0f * M_PI * k * n / WINDOW_SAMPLES;
            real += fft_buffer_[2*n] * cosf(angle);
            imag += fft_buffer_[2*n] * sinf(angle);
        }
        power_spec[k] = real * real + imag * imag;
    }
}

void MFCCFrontend::apply_mel_filterbank(const float* power_spec, float* mel_energies) {
    const size_t n_fft_bins = WINDOW_SAMPLES / 2 + 1;
    
    for (size_t m = 0; m < N_MELS; m++) {
        mel_energies[m] = 0.0f;
        for (size_t k = 0; k < n_fft_bins; k++) {
            mel_energies[m] += power_spec[k] * mel_filterbank_[m * n_fft_bins + k];
        }
        
        // Apply log and ensure minimum value
        mel_energies[m] = log10f(std::max(mel_energies[m], 1e-10f));
    }
}

void MFCCFrontend::compute_mfcc(const float* mel_energies, float* mfcc_coeffs) {
    for (size_t i = 0; i < N_MFCC; i++) {
        mfcc_coeffs[i] = 0.0f;
        for (size_t j = 0; j < N_MELS; j++) {
            mfcc_coeffs[i] += mel_energies[j] * dct_matrix_[i * N_MELS + j];
        }
    }
}

void MFCCFrontend::update_feature_matrix(const float* mfcc_coeffs) {
    if (feature_frame_count_ < N_FRAMES) {
        size_t offset = feature_frame_count_ * N_MFCC;
        std::memcpy(&features_[offset], mfcc_coeffs, N_MFCC * sizeof(float));
        feature_frame_count_++;
    }
}

} // namespace irene 