#include "audio/wake_word_detector.hpp"
#include "audio/mfcc_frontend.hpp"
#include "utils/ring_buffer.hpp"

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_heap_caps.h"
#include <cstring>
#include <algorithm>
#include <cmath>

// TensorFlow Lite Micro includes
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "tensorflow/lite/version.h"

static const char* TAG = "WakeWordDetector";

namespace irene {

WakeWordDetector::WakeWordDetector()
    : enabled_(false)
    , initialized_(false)
    , model_data_(nullptr)
    , model_size_(0)
    , model_(nullptr)
    , interpreter_(nullptr)
    , resolver_(nullptr)
    , tensor_arena_(nullptr)
    , inference_buffer_(nullptr)
    , inference_buffer_size_(0)
    , last_confidence_(0.0f)
    , last_latency_ms_(0)
    , detection_start_time_(0)
    , consecutive_detections_(0)
    , wake_word_task_handle_(nullptr)
    , audio_queue_(nullptr)
    , detection_count_(0)
    , false_positive_count_(0)
    , total_latency_ms_(0)
    , inference_count_(0)
    , last_inference_time_(0)
    , inference_interval_us_(30000) { // 30ms intervals
}

WakeWordDetector::~WakeWordDetector() {
    disable();
    cleanup_tf_lite_model();
    
    if (audio_queue_) {
        vQueueDelete(audio_queue_);
    }
    
    if (inference_buffer_) {
        heap_caps_free(inference_buffer_);
    }
}

ErrorCode WakeWordDetector::initialize(const WakeWordConfig& config, 
                                      const uint8_t* model_data, 
                                      size_t model_size) {
    ESP_LOGI(TAG, "Initializing wake word detector...");
    
    config_ = config;
    model_data_ = model_data;
    model_size_ = model_size;
    
    if (!model_data || model_size == 0) {
        ESP_LOGE(TAG, "Invalid model data");
        return ErrorCode::WAKE_WORD_FAILED;
    }
    
    // Initialize MFCC frontend
    mfcc_frontend_ = std::make_unique<MFCCFrontend>();
    ErrorCode mfcc_result = mfcc_frontend_->initialize(config.use_psram);
    if (mfcc_result != ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to initialize MFCC frontend");
        return mfcc_result;
    }
    
    // Allocate feature buffers
    uint32_t caps = config.use_psram ? MALLOC_CAP_SPIRAM : MALLOC_CAP_8BIT;
    
    mfcc_features_.reset(static_cast<float*>(
        heap_caps_malloc(MFCCFrontend::FEATURE_SIZE * sizeof(float), caps)
    ));
    
    quantized_features_.reset(static_cast<int8_t*>(
        heap_caps_malloc(MFCCFrontend::FEATURE_SIZE * sizeof(int8_t), caps)
    ));
    
    if (!mfcc_features_ || !quantized_features_) {
        ESP_LOGE(TAG, "Failed to allocate feature buffers");
        return ErrorCode::MEMORY_ERROR;
    }
    
    ESP_LOGI(TAG, "Allocated MFCC feature buffers: %dx%d in %s", 
            MFCCFrontend::N_FRAMES, MFCCFrontend::N_MFCC, 
            config.use_psram ? "PSRAM" : "IRAM");
    
    // Allocate legacy inference buffer (for compatibility)
    inference_buffer_size_ = 16000; // 1 second at 16kHz
    inference_buffer_ = static_cast<int16_t*>(
        heap_caps_malloc(inference_buffer_size_ * sizeof(int16_t), caps)
    );
    
    if (!inference_buffer_) {
        ESP_LOGE(TAG, "Failed to allocate inference buffer");
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Create audio buffer for wake word processing
    try {
        audio_buffer_ = std::make_unique<RingBuffer>(
            inference_buffer_size_ * sizeof(int16_t) * 2 // Double buffer
        );
    } catch (const std::exception& e) {
        ESP_LOGE(TAG, "Failed to create audio buffer: %s", e.what());
        return ErrorCode::MEMORY_ERROR;
    }
    
    // Create audio queue for task communication
    audio_queue_ = xQueueCreate(16, sizeof(size_t));
    if (!audio_queue_) {
        ESP_LOGE(TAG, "Failed to create audio queue");
        return ErrorCode::WAKE_WORD_FAILED;
    }
    
    // Initialize TensorFlow Lite Micro
    if (!setup_tf_lite_model()) {
        ESP_LOGE(TAG, "Failed to setup TensorFlow Lite model");
        return ErrorCode::WAKE_WORD_FAILED;
    }
    
    initialized_ = true;
    ESP_LOGI(TAG, "Wake word detector initialized successfully");
    ESP_LOGI(TAG, "Model size: %d bytes, Threshold: %.3f", model_size_, config_.threshold);
    ESP_LOGI(TAG, "INT8 quantized model with MFCC frontend enabled");
    
    return ErrorCode::SUCCESS;
}

bool WakeWordDetector::process_frame(const int16_t* audio_data, size_t samples) {
    if (!enabled_ || !initialized_ || !audio_data || samples == 0) {
        return false;
    }
    
    // Process audio data through MFCC frontend
    bool features_ready = mfcc_frontend_->process_samples(audio_data, samples);
    
    if (features_ready) {
        // Signal wake word task to process MFCC features
        size_t signal = 1; // Signal that features are ready
        if (xQueueSend(audio_queue_, &signal, 0) != pdTRUE) {
            // Queue full, skip this frame
        }
    }
    
    // Also maintain legacy ring buffer for compatibility
    size_t bytes_written = audio_buffer_->write(
        reinterpret_cast<const uint8_t*>(audio_data), 
        samples * sizeof(int16_t)
    );
    
    if (bytes_written != samples * sizeof(int16_t)) {
        ESP_LOGW(TAG, "Audio buffer overflow, data may be lost");
    }
    
    return false; // Actual detection result comes from the task
}

void WakeWordDetector::set_threshold(float threshold) {
    config_.threshold = threshold;
    ESP_LOGI(TAG, "Wake word threshold set to: %.3f", threshold);
}

void WakeWordDetector::set_detection_callback(DetectionCallback callback) {
    detection_callback_ = callback;
}

void WakeWordDetector::enable() {
    if (enabled_) return;
    
    ESP_LOGI(TAG, "Enabling wake word detection...");
    
    if (!initialized_) {
        ESP_LOGE(TAG, "Wake word detector not initialized");
        return;
    }
    
    // Create wake word processing task
    BaseType_t result = xTaskCreatePinnedToCore(
        wake_word_task_wrapper,
        "wake_word_task",
        8192, // Stack size for TF Lite inference
        this,
        9,    // High priority
        &wake_word_task_handle_,
        0     // Core 0 for consistent timing
    );
    
    if (result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create wake word task");
        return;
    }
    
    enabled_ = true;
    ESP_LOGI(TAG, "Wake word detection enabled");
}

void WakeWordDetector::disable() {
    if (!enabled_) return;
    
    ESP_LOGI(TAG, "Disabling wake word detection...");
    
    enabled_ = false;
    
    // Delete wake word task
    if (wake_word_task_handle_) {
        vTaskDelete(wake_word_task_handle_);
        wake_word_task_handle_ = nullptr;
    }
    
    ESP_LOGI(TAG, "Wake word detection disabled");
}

void WakeWordDetector::reset() {
    consecutive_detections_ = 0;
    detection_start_time_ = 0;
    last_confidence_ = 0.0f;
    
    // Reset MFCC frontend
    if (mfcc_frontend_) {
        mfcc_frontend_->reset();
    }
    
    if (audio_buffer_) {
        audio_buffer_->clear();
    }
    
    // Clear audio queue
    if (audio_queue_) {
        xQueueReset(audio_queue_);
    }
}

uint32_t WakeWordDetector::get_detection_count() const {
    return detection_count_;
}

uint32_t WakeWordDetector::get_false_positive_count() const {
    return false_positive_count_;
}

float WakeWordDetector::get_average_latency_ms() const {
    return detection_count_ > 0 ? 
           static_cast<float>(total_latency_ms_) / detection_count_ : 0.0f;
}

void WakeWordDetector::log_inference_stats() const {
    ESP_LOGI(TAG, "Wake Word Statistics:");
    ESP_LOGI(TAG, "  Detections: %u", detection_count_);
    ESP_LOGI(TAG, "  False Positives: %u", false_positive_count_);
    ESP_LOGI(TAG, "  Average Latency: %.1f ms", get_average_latency_ms());
    ESP_LOGI(TAG, "  Inference Count: %u", inference_count_);
    ESP_LOGI(TAG, "  Last Confidence: %.3f", last_confidence_);
}

void WakeWordDetector::wake_word_task_wrapper(void* arg) {
    static_cast<WakeWordDetector*>(arg)->wake_word_task();
}

void WakeWordDetector::wake_word_task() {
    ESP_LOGI(TAG, "Wake word task started");
    
    size_t signal;
    TickType_t last_inference = 0;
    const TickType_t inference_period = pdMS_TO_TICKS(30); // 30ms intervals
    
    while (enabled_) {
        // Wait for audio data or timeout
        if (xQueueReceive(audio_queue_, &signal, inference_period) == pdTRUE) {
            
            // Throttle inference rate
            TickType_t current_time = xTaskGetTickCount();
            if (current_time - last_inference >= inference_period) {
                process_inference();
                last_inference = current_time;
            }
        }
    }
    
    ESP_LOGI(TAG, "Wake word task ended");
}

void WakeWordDetector::process_inference() {
    if (!mfcc_frontend_ || !mfcc_features_) return;
    
    uint32_t start_time = esp_timer_get_time();
    
    // Get MFCC features from frontend
    if (!mfcc_frontend_->get_features(mfcc_features_.get())) {
        return; // No valid features available
    }
    
    // Perform TensorFlow Lite inference with MFCC features
    float confidence = run_inference(mfcc_features_.get(), MFCCFrontend::FEATURE_SIZE);
    
    uint32_t inference_time = (esp_timer_get_time() - start_time) / 1000; // Convert to ms
    inference_count_++;
    last_confidence_ = confidence;
    
    // Check for detection
    if (validate_detection(confidence)) {
        uint32_t detection_latency = inference_time;
        last_latency_ms_ = detection_latency;
        total_latency_ms_ += detection_latency;
        detection_count_++;
        
        ESP_LOGI(TAG, "Wake word detected! Confidence: %.3f, Latency: %u ms", 
                confidence, detection_latency);
        
        if (detection_callback_) {
            detection_callback_(confidence, detection_latency);
        }
    }
    
    // Log performance periodically
    if (inference_count_ % 100 == 0) {
        ESP_LOGD(TAG, "Inference #%u: %.3f confidence, %u ms", 
                inference_count_, confidence, inference_time);
    }
}

bool WakeWordDetector::validate_detection(float confidence) {
    uint32_t current_time = esp_timer_get_time() / 1000;
    
    // Note: Threshold may need re-tuning for INT8 quantized models
    // INT8 quantization can shift the confidence score distribution
    // Consider using trainer-suggested threshold or empirical validation
    if (confidence >= config_.threshold) {
        if (detection_start_time_ == 0) {
            detection_start_time_ = current_time;
            consecutive_detections_ = 1;
        } else {
            consecutive_detections_++;
        }
        
        // Check if we've had consistent detections for the required duration
        uint32_t detection_duration = current_time - detection_start_time_;
        if (detection_duration >= config_.trigger_duration_ms) {
            // Reset for next detection
            detection_start_time_ = 0;
            consecutive_detections_ = 0;
            return true;
        }
    } else {
        // Reset if confidence drops below threshold
        detection_start_time_ = 0;
        consecutive_detections_ = 0;
    }
    
    return false;
}

bool WakeWordDetector::setup_tf_lite_model() {
    ESP_LOGI(TAG, "Setting up TensorFlow Lite model...");
    
    // Load model from embedded data
    model_ = tflite::GetModel(model_data_);
    if (model_->version() != TFLITE_SCHEMA_VERSION) {
        ESP_LOGE(TAG, "Model schema version %d not supported. Supported version is %d",
                model_->version(), TFLITE_SCHEMA_VERSION);
        return false;
    }
    
    // Allocate tensor arena in PSRAM (optimized for INT8 models)
    tensor_arena_ = static_cast<uint8_t*>(
        heap_caps_malloc(kTensorArenaSize, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)
    );
    
    if (!tensor_arena_) {
        ESP_LOGE(TAG, "Failed to allocate tensor arena (%d bytes) in PSRAM", kTensorArenaSize);
        return false;
    }
    
    ESP_LOGI(TAG, "Allocated tensor arena: %d KB in PSRAM (optimized for INT8)", kTensorArenaSize / 1024);
    
    // Create and configure operation resolver (optimized for INT8)
    resolver_ = new tflite::MicroMutableOpResolver<9>();
    resolver_->AddConv2D();
    resolver_->AddMaxPool2D();
    resolver_->AddReshape();
    resolver_->AddFullyConnected();
    // Removed AddSoftmax() - typically unused for binary classification
    resolver_->AddDepthwiseConv2D();
    resolver_->AddAdd();
    resolver_->AddMul();
    resolver_->AddQuantize();
    resolver_->AddDequantize();
    
    // Create interpreter
    static tflite::MicroInterpreter static_interpreter(
        model_, *resolver_, tensor_arena_, kTensorArenaSize
    );
    interpreter_ = &static_interpreter;
    
    // Allocate tensors
    TfLiteStatus allocate_status = interpreter_->AllocateTensors();
    if (allocate_status != kTfLiteOk) {
        ESP_LOGE(TAG, "AllocateTensors() failed with status: %d", allocate_status);
        return false;
    }
    
    // Log tensor information and validate INT8 types
    TfLiteTensor* input = interpreter_->input(0);
    TfLiteTensor* output = interpreter_->output(0);
    
    ESP_LOGI(TAG, "Model input shape: [%d, %d, %d, %d]", 
             input->dims->data[0], input->dims->data[1], 
             input->dims->data[2], input->dims->data[3]);
    ESP_LOGI(TAG, "Model input type: %d", input->type);
    ESP_LOGI(TAG, "Model output shape: [%d]", output->dims->data[0]);
    ESP_LOGI(TAG, "Model output type: %d", output->type);
    
    // Validate and log quantization parameters for INT8 model
    if (input->type == kTfLiteInt8) {
        ESP_LOGI(TAG, "Input quantization: scale=%f, zero_point=%d", 
                input->params.scale, input->params.zero_point);
    } else {
        ESP_LOGW(TAG, "Warning: Expected INT8 input tensor, got type %d", input->type);
    }
    
    if (output->type == kTfLiteInt8) {
        ESP_LOGI(TAG, "Output quantization: scale=%f, zero_point=%d", 
                output->params.scale, output->params.zero_point);
    } else {
        ESP_LOGW(TAG, "Warning: Expected INT8 output tensor, got type %d", output->type);
    }
    
    // Verify tensor dimensions match expected MFCC input
    size_t expected_features = MFCCFrontend::N_FRAMES * MFCCFrontend::N_MFCC;
    size_t tensor_elements = 1;
    for (int i = 0; i < input->dims->size; i++) {
        tensor_elements *= input->dims->data[i];
    }
    
    if (tensor_elements != expected_features) {
        ESP_LOGE(TAG, "Tensor size mismatch: expected %d, got %d", 
                expected_features, tensor_elements);
        return false;
    }
    
    ESP_LOGI(TAG, "TensorFlow Lite INT8 model setup complete");
    ESP_LOGI(TAG, "Model validated for %dx%d MFCC features", 
             MFCCFrontend::N_FRAMES, MFCCFrontend::N_MFCC);
    
    // Device sanity checklist for debugging
    perform_sanity_checks();
    
    return true;
}

void WakeWordDetector::cleanup_tf_lite_model() {
    if (resolver_) {
        delete resolver_;
        resolver_ = nullptr;
    }
    
    if (tensor_arena_) {
        heap_caps_free(tensor_arena_);
        tensor_arena_ = nullptr;
    }
    
    model_ = nullptr;
    interpreter_ = nullptr;
}

void WakeWordDetector::perform_sanity_checks() {
    ESP_LOGI(TAG, "=== Device Sanity Checklist ===");
    
    if (!interpreter_) {
        ESP_LOGE(TAG, "Sanity check failed: No interpreter available");
        return;
    }
    
    // C2.1: Log input/output types + scales/zero points
    TfLiteTensor* input = interpreter_->input(0);
    TfLiteTensor* output = interpreter_->output(0);
    
    ESP_LOGI(TAG, "Input tensor: type=%s, scale=%f, zero_point=%d",
             input->type == kTfLiteInt8 ? "INT8" : 
             input->type == kTfLiteFloat32 ? "FLOAT32" : "UNKNOWN",
             input->params.scale, input->params.zero_point);
    
    ESP_LOGI(TAG, "Output tensor: type=%s, scale=%f, zero_point=%d",
             output->type == kTfLiteInt8 ? "INT8" : 
             output->type == kTfLiteFloat32 ? "FLOAT32" : "UNKNOWN",
             output->params.scale, output->params.zero_point);
    
    // C2.2: Log input dimensions and arena size used vs. reserved
    ESP_LOGI(TAG, "Input dimensions: [%d, %d, %d, %d] (%d elements)",
             input->dims->data[0], input->dims->data[1], 
             input->dims->data[2], input->dims->data[3],
             input->bytes / (input->type == kTfLiteInt8 ? sizeof(int8_t) : sizeof(float)));
    
    // Calculate actual arena usage
    size_t arena_used = interpreter_->arena_used_bytes();
    ESP_LOGI(TAG, "Tensor arena: %d KB used / %d KB reserved (%.1f%% utilization)",
             arena_used / 1024, kTensorArenaSize / 1024, 
             (arena_used * 100.0f) / kTensorArenaSize);
    
    if (arena_used > kTensorArenaSize * 0.9f) {
        ESP_LOGW(TAG, "Warning: High arena usage (>90%%), consider increasing size");
    }
    
    // C2.3: One-off test: feed zeros MFCC and confirm stable low score
    ESP_LOGI(TAG, "Running zero-input stability test...");
    
    // Create zero MFCC features
    const size_t feature_size = MFCCFrontend::N_FRAMES * MFCCFrontend::N_MFCC;
    std::unique_ptr<float[]> zero_features(new float[feature_size]);
    std::fill_n(zero_features.get(), feature_size, 0.0f);
    
    // Run inference with zero input
    float zero_confidence = run_inference(zero_features.get(), feature_size);
    
    ESP_LOGI(TAG, "Zero-input confidence: %.6f", zero_confidence);
    
    // Validate stable low score (should be well below threshold)
    const float expected_max_zero_confidence = 0.1f; // Conservative threshold
    if (zero_confidence > expected_max_zero_confidence) {
        ESP_LOGW(TAG, "Warning: Zero-input confidence (%.6f) higher than expected (%.6f)", 
                zero_confidence, expected_max_zero_confidence);
        ESP_LOGW(TAG, "This may indicate model bias or quantization issues");
    } else {
        ESP_LOGI(TAG, "✓ Zero-input test passed: stable low confidence");
    }
    
    // Additional shape validation
    size_t expected_input_elements = MFCCFrontend::N_FRAMES * MFCCFrontend::N_MFCC;
    size_t actual_input_elements = input->bytes / (input->type == kTfLiteInt8 ? sizeof(int8_t) : sizeof(float));
    
    if (actual_input_elements != expected_input_elements) {
        ESP_LOGE(TAG, "Shape error: Expected %d input elements, got %d", 
                expected_input_elements, actual_input_elements);
    } else {
        ESP_LOGI(TAG, "✓ Input shape validation passed");
    }
    
    ESP_LOGI(TAG, "=== Sanity Check Complete ===");
}

float WakeWordDetector::run_inference(const float* mfcc_features, size_t feature_count) {
    if (!interpreter_ || !mfcc_features || feature_count == 0) {
        return 0.0f;
    }
    
    // Get input tensor
    TfLiteTensor* input = interpreter_->input(0);
    if (!input || input->bytes == 0) {
        ESP_LOGE(TAG, "Invalid input tensor");
        return 0.0f;
    }
    
    // Handle INT8 quantized input
    if (input->type == kTfLiteInt8) {
        int8_t* input_data = input->data.int8;
        const float scale = input->params.scale;
        const int zero_point = input->params.zero_point;
        
        // Quantize MFCC features to INT8
        size_t input_elements = input->bytes / sizeof(int8_t);
        size_t copy_elements = std::min(feature_count, input_elements);
        
        for (size_t i = 0; i < copy_elements; i++) {
            // Quantize: q = round(f / scale) + zero_point
            const int32_t quantized = static_cast<int32_t>(lroundf(mfcc_features[i] / scale)) + zero_point;
            input_data[i] = static_cast<int8_t>(std::min(127, std::max(-128, quantized)));
        }
        
        // Zero-pad if necessary
        for (size_t i = copy_elements; i < input_elements; i++) {
            input_data[i] = static_cast<int8_t>(zero_point);
        }
    } else if (input->type == kTfLiteFloat32) {
        // Fallback to float32 for compatibility
        float* input_data = input->data.f;
        size_t input_elements = input->bytes / sizeof(float);
        size_t copy_elements = std::min(feature_count, input_elements);
        
        std::memcpy(input_data, mfcc_features, copy_elements * sizeof(float));
        
        // Zero-pad if necessary
        for (size_t i = copy_elements; i < input_elements; i++) {
            input_data[i] = 0.0f;
        }
    } else {
        ESP_LOGE(TAG, "Unsupported input tensor type: %d", input->type);
        return 0.0f;
    }
    
    // Run inference
    TfLiteStatus invoke_status = interpreter_->Invoke();
    if (invoke_status != kTfLiteOk) {
        ESP_LOGE(TAG, "Invoke() failed with status: %d", invoke_status);
        return 0.0f;
    }
    
    // Get output
    TfLiteTensor* output = interpreter_->output(0);
    if (!output || output->bytes == 0) {
        ESP_LOGE(TAG, "Invalid output tensor");
        return 0.0f;
    }
    
    float confidence = 0.0f;
    
    // Handle INT8 quantized output
    if (output->type == kTfLiteInt8) {
        const float out_scale = output->params.scale;
        const int out_zero_point = output->params.zero_point;
        const int8_t quantized_output = output->data.int8[0];
        
        // Dequantize: f = (q - zero_point) * scale
        confidence = (quantized_output - out_zero_point) * out_scale;
    } else if (output->type == kTfLiteFloat32) {
        // Direct float32 output
        confidence = output->data.f[0];
    } else {
        ESP_LOGE(TAG, "Unsupported output tensor type: %d", output->type);
        return 0.0f;
    }
    
    // Clamp confidence to valid range
    confidence = std::max(0.0f, std::min(1.0f, confidence));
    
    return confidence;
}

} // namespace irene 