#pragma once

#include "core/types.hpp"
#include "audio/mfcc_frontend.hpp"
#include <functional>
#include <memory>

// TensorFlow Lite Micro includes
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/version.h"

namespace irene {

/**
 * Wake word detection using INT8 quantized TensorFlow Lite model
 * Features MFCC frontend (49x40) and INT8 inference for optimal performance
 * Runs on PSRAM-resident model with per-node training
 */
class WakeWordDetector {
public:
    using DetectionCallback = std::function<void(float confidence, uint32_t latency_ms)>;

    WakeWordDetector();
    ~WakeWordDetector();

    // Initialize with node-specific model data
    ErrorCode initialize(const WakeWordConfig& config, 
                        const uint8_t* model_data, 
                        size_t model_size);

    // Process audio frame (typically 480 samples = 30ms at 16kHz)
    bool process_frame(const int16_t* audio_data, size_t samples);

    // Configure detection
    void set_threshold(float threshold);
    void set_detection_callback(DetectionCallback callback);
    
    // Control
    void enable();
    void disable();
    void reset();
    
    // Status
    bool is_enabled() const { return enabled_; }
    float get_threshold() const { return config_.threshold; }
    float get_last_confidence() const { return last_confidence_; }
    uint32_t get_last_latency_ms() const { return last_latency_ms_; }
    
    // Statistics
    uint32_t get_detection_count() const { return detection_count_; }
    uint32_t get_false_positive_count() const { return false_positive_count_; }
    float get_average_latency_ms() const;
    
    // Debugging
    void log_inference_stats() const;

private:
    void wake_word_task();
    void process_inference();
    bool validate_detection(float confidence);
    static void wake_word_task_wrapper(void* arg);
    
    // TensorFlow Lite inference methods
    bool setup_tf_lite_model();
    float run_inference(const float* mfcc_features, size_t feature_count);
    void cleanup_tf_lite_model();
    void perform_sanity_checks();
    
    // MFCC processing methods
    bool process_mfcc_features();
    
    WakeWordConfig config_;
    bool enabled_;
    bool initialized_;
    
    // Model data (stored in PSRAM)
    const uint8_t* model_data_;
    size_t model_size_;
    
    // TensorFlow Lite Micro components
    const tflite::Model* model_;
    tflite::MicroInterpreter* interpreter_;
    tflite::MicroMutableOpResolver<9>* resolver_;
    uint8_t* tensor_arena_;
    static constexpr size_t kTensorArenaSize = 160 * 1024; // 160KB initial size for INT8 model
                                                                       // Can be reduced gradually (128KB->96KB) after validation
    
    // MFCC frontend for feature extraction
    std::unique_ptr<MFCCFrontend> mfcc_frontend_;
    
    // Audio buffering (legacy - now handled by MFCC frontend)
    std::unique_ptr<class RingBuffer> audio_buffer_;
    int16_t* inference_buffer_;
    size_t inference_buffer_size_;
    
    // Feature buffers for INT8 processing
    std::unique_ptr<float[]> mfcc_features_;       // 49x40 MFCC features
    std::unique_ptr<int8_t[]> quantized_features_; // Quantized input for model
    
    // Detection state
    float last_confidence_;
    uint32_t last_latency_ms_;
    uint32_t detection_start_time_;
    uint32_t consecutive_detections_;
    
    // Callback
    DetectionCallback detection_callback_;
    
    // Task management
    TaskHandle_t wake_word_task_handle_;
    QueueHandle_t audio_queue_;
    
    // Statistics
    uint32_t detection_count_;
    uint32_t false_positive_count_;
    uint32_t total_latency_ms_;
    uint32_t inference_count_;
    
    // Timing
    uint32_t last_inference_time_;
    uint32_t inference_interval_us_;
}; 