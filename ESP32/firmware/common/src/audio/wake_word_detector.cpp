#include "audio/wake_word_detector.hpp"
#include "utils/ring_buffer.hpp"

#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_heap_caps.h"
#include <cstring>
#include <algorithm>

static const char* TAG = "WakeWordDetector";

namespace irene {

WakeWordDetector::WakeWordDetector()
    : enabled_(false)
    , initialized_(false)
    , model_data_(nullptr)
    , model_size_(0)
    , interpreter_(nullptr)
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
    
    // Allocate inference buffer in PSRAM if requested
    inference_buffer_size_ = 16000; // 1 second at 16kHz
    uint32_t caps = config.use_psram ? MALLOC_CAP_SPIRAM : MALLOC_CAP_8BIT;
    
    inference_buffer_ = static_cast<int16_t*>(
        heap_caps_malloc(inference_buffer_size_ * sizeof(int16_t), caps)
    );
    
    if (!inference_buffer_) {
        ESP_LOGE(TAG, "Failed to allocate inference buffer");
        return ErrorCode::MEMORY_ERROR;
    }
    
    ESP_LOGI(TAG, "Allocated inference buffer: %d samples in %s", 
            inference_buffer_size_, config.use_psram ? "PSRAM" : "IRAM");
    
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
    
    // Initialize TensorFlow Lite Micro (placeholder - actual implementation needed)
    // This would include loading the model and setting up the interpreter
    interpreter_ = reinterpret_cast<void*>(0x12345678); // Placeholder
    
    initialized_ = true;
    ESP_LOGI(TAG, "Wake word detector initialized successfully");
    ESP_LOGI(TAG, "Model size: %d bytes, Threshold: %.3f", model_size_, config_.threshold);
    
    return ErrorCode::SUCCESS;
}

bool WakeWordDetector::process_frame(const int16_t* audio_data, size_t samples) {
    if (!enabled_ || !initialized_ || !audio_data || samples == 0) {
        return false;
    }
    
    // Add audio data to ring buffer
    size_t bytes_written = audio_buffer_->write(
        reinterpret_cast<const uint8_t*>(audio_data), 
        samples * sizeof(int16_t)
    );
    
    if (bytes_written != samples * sizeof(int16_t)) {
        ESP_LOGW(TAG, "Audio buffer overflow, data may be lost");
    }
    
    // Check if enough data for inference
    size_t available_samples = audio_buffer_->available() / sizeof(int16_t);
    if (available_samples >= inference_buffer_size_) {
        // Signal wake word task to process
        size_t signal = available_samples;
        if (xQueueSend(audio_queue_, &signal, 0) != pdTRUE) {
            // Queue full, skip this frame
        }
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
    if (!audio_buffer_ || !inference_buffer_) return;
    
    uint32_t start_time = esp_timer_get_time();
    
    // Read audio data for inference
    size_t bytes_read = audio_buffer_->read(
        reinterpret_cast<uint8_t*>(inference_buffer_),
        inference_buffer_size_ * sizeof(int16_t)
    );
    
    size_t samples_read = bytes_read / sizeof(int16_t);
    if (samples_read < inference_buffer_size_) {
        return; // Not enough data
    }
    
    // Perform inference (placeholder - actual TF Lite implementation needed)
    float confidence = run_inference_placeholder(inference_buffer_, inference_buffer_size_);
    
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

float WakeWordDetector::run_inference_placeholder(const int16_t* audio_data, size_t samples) {
    // Placeholder implementation - replace with actual TensorFlow Lite Micro inference
    // This simulates the inference process and returns a confidence score
    
    if (!audio_data || samples == 0) return 0.0f;
    
    // Simple energy-based detection as placeholder
    int64_t energy = 0;
    for (size_t i = 0; i < samples; i++) {
        energy += abs(audio_data[i]);
    }
    
    float normalized_energy = static_cast<float>(energy) / (samples * 32768.0f);
    
    // Simulate wake word detection with some randomness
    float base_confidence = normalized_energy * 0.5f;
    
    // Add some noise to simulate actual model behavior
    static uint32_t seed = 12345;
    seed = seed * 1103515245 + 12345; // Simple LCG
    float noise = (seed % 1000) / 10000.0f - 0.05f; // -0.05 to +0.05
    
    float confidence = base_confidence + noise;
    return std::max(0.0f, std::min(1.0f, confidence));
}

} // namespace irene 