#pragma once

#include "core/types.hpp"
#include <cstdint>
#include <cstddef>
#include <memory>
#include <vector>

namespace irene {

/**
 * @brief MFCC Frontend for wake word detection
 * 
 * Implements MFCC feature extraction with parameters matching the training setup:
 * - Sample rate: 16 kHz
 * - Window size: 30 ms (480 samples)
 * - Hop size: 10 ms (160 samples)
 * - Mel filters: 40
 * - MFCC coefficients: 40
 * - Output: 49x40 feature matrix for each inference
 */
class MFCCFrontend {
public:
    // MFCC parameters matching training
    static constexpr size_t SAMPLE_RATE = 16000;
    static constexpr size_t WINDOW_SIZE_MS = 30;
    static constexpr size_t HOP_SIZE_MS = 10;
    static constexpr size_t WINDOW_SAMPLES = (SAMPLE_RATE * WINDOW_SIZE_MS) / 1000;  // 480
    static constexpr size_t HOP_SAMPLES = (SAMPLE_RATE * HOP_SIZE_MS) / 1000;       // 160
    static constexpr size_t N_MELS = 40;
    static constexpr size_t N_MFCC = 40;
    static constexpr size_t N_FRAMES = 49;
    
    // Total feature matrix size
    static constexpr size_t FEATURE_SIZE = N_FRAMES * N_MFCC;
    
    // Input buffer size (enough for N_FRAMES with overlap)
    static constexpr size_t INPUT_BUFFER_SIZE = (N_FRAMES - 1) * HOP_SAMPLES + WINDOW_SAMPLES;  // 8160 samples

    MFCCFrontend();
    ~MFCCFrontend();

    /**
     * @brief Initialize the MFCC frontend
     * @param use_psram Whether to allocate buffers in PSRAM
     * @return Error code
     */
    ErrorCode initialize(bool use_psram = true);

    /**
     * @brief Process audio samples and extract MFCC features
     * @param audio_data Input audio samples (int16_t PCM)
     * @param samples Number of samples
     * @return True if new features are available
     */
    bool process_samples(const int16_t* audio_data, size_t samples);

    /**
     * @brief Get the latest MFCC features
     * @param features Output buffer for features [N_FRAMES][N_MFCC] = float[49*40]
     * @return True if valid features are available
     */
    bool get_features(float* features) const;

    /**
     * @brief Reset the frontend state
     */
    void reset();

    /**
     * @brief Check if enough data is available for feature extraction
     * @return True if features can be computed
     */
    bool has_sufficient_data() const;

private:
    bool initialized_;
    bool use_psram_;
    
    // Audio input buffer (ring buffer for overlapping windows)
    std::unique_ptr<int16_t[]> audio_buffer_;
    size_t buffer_write_pos_;
    size_t samples_available_;
    
    // MFCC computation buffers
    std::unique_ptr<float[]> windowed_samples_;     // WINDOW_SAMPLES
    std::unique_ptr<float[]> fft_buffer_;          // For FFT computation
    std::unique_ptr<float[]> power_spectrum_;      // WINDOW_SAMPLES/2 + 1
    std::unique_ptr<float[]> mel_energies_;        // N_MELS
    std::unique_ptr<float[]> log_mel_energies_;    // N_MELS
    std::unique_ptr<float[]> mfcc_coeffs_;         // N_MFCC
    
    // Feature output buffer
    std::unique_ptr<float[]> features_;            // N_FRAMES * N_MFCC
    size_t feature_frame_count_;
    
    // Precomputed tables
    std::unique_ptr<float[]> hann_window_;         // WINDOW_SAMPLES
    std::unique_ptr<float[]> mel_filterbank_;      // N_MELS * (WINDOW_SAMPLES/2 + 1)
    std::unique_ptr<float[]> dct_matrix_;          // N_MFCC * N_MELS

    /**
     * @brief Initialize precomputed tables
     */
    bool setup_tables();

    /**
     * @brief Apply Hann window to audio samples
     * @param samples Input samples
     * @param windowed_output Output windowed samples
     */
    void apply_window(const int16_t* samples, float* windowed_output);

    /**
     * @brief Compute FFT and power spectrum
     * @param windowed_samples Input windowed samples
     * @param power_spec Output power spectrum
     */
    void compute_power_spectrum(const float* windowed_samples, float* power_spec);

    /**
     * @brief Apply mel filterbank to power spectrum
     * @param power_spec Input power spectrum
     * @param mel_energies Output mel energies
     */
    void apply_mel_filterbank(const float* power_spec, float* mel_energies);

    /**
     * @brief Compute MFCC coefficients from mel energies
     * @param mel_energies Input mel energies
     * @param mfcc_coeffs Output MFCC coefficients
     */
    void compute_mfcc(const float* mel_energies, float* mfcc_coeffs);

    /**
     * @brief Update feature matrix with new MFCC frame
     * @param mfcc_coeffs New MFCC coefficients
     */
    void update_feature_matrix(const float* mfcc_coeffs);

    /**
     * @brief Allocate buffer with specified memory caps
     * @param size Size in bytes
     * @return Allocated pointer or nullptr
     */
    void* allocate_buffer(size_t size) const;
};

} // namespace irene 