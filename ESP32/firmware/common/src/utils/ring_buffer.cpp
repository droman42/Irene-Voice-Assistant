#include "utils/ring_buffer.hpp"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <algorithm>
#include <cstring>

static const char* TAG = "RingBuffer";

namespace irene {

RingBuffer::RingBuffer(size_t capacity, bool use_psram)
    : buffer_(nullptr)
    , capacity_(capacity)
    , head_(0)
    , tail_(0)
    , full_(false)
    , mutex_(nullptr) {
    
    // Allocate buffer
    uint32_t caps = use_psram ? MALLOC_CAP_SPIRAM : MALLOC_CAP_8BIT;
    buffer_ = static_cast<uint8_t*>(heap_caps_malloc(capacity, caps));
    
    if (!buffer_) {
        ESP_LOGE(TAG, "Failed to allocate ring buffer of size %d", capacity);
        throw std::bad_alloc();
    }
    
    // Create mutex for thread safety
    mutex_ = xSemaphoreCreateMutex();
    if (!mutex_) {
        heap_caps_free(buffer_);
        buffer_ = nullptr;
        ESP_LOGE(TAG, "Failed to create ring buffer mutex");
        throw std::runtime_error("Failed to create mutex");
    }
    
    ESP_LOGD(TAG, "Created ring buffer: %d bytes in %s", 
            capacity, use_psram ? "PSRAM" : "IRAM");
}

RingBuffer::~RingBuffer() {
    if (buffer_) {
        heap_caps_free(buffer_);
    }
    
    if (mutex_) {
        vSemaphoreDelete(mutex_);
    }
}

size_t RingBuffer::write(const uint8_t* data, size_t length) {
    if (!data || length == 0 || !buffer_) {
        return 0;
    }
    
    xSemaphoreTake(mutex_, portMAX_DELAY);
    
    size_t bytes_written = 0;
    
    for (size_t i = 0; i < length; i++) {
        if (full_) {
            // Buffer is full, overwrite oldest data
            tail_ = (tail_ + 1) % capacity_;
        }
        
        buffer_[head_] = data[i];
        head_ = (head_ + 1) % capacity_;
        
        if (head_ == tail_) {
            full_ = true;
        }
        
        bytes_written++;
    }
    
    xSemaphoreGive(mutex_);
    
    return bytes_written;
}

size_t RingBuffer::read(uint8_t* data, size_t length) {
    if (!data || length == 0 || !buffer_) {
        return 0;
    }
    
    xSemaphoreTake(mutex_, portMAX_DELAY);
    
    size_t bytes_read = 0;
    
    while (bytes_read < length && !empty()) {
        data[bytes_read] = buffer_[tail_];
        tail_ = (tail_ + 1) % capacity_;
        full_ = false;
        bytes_read++;
    }
    
    xSemaphoreGive(mutex_);
    
    return bytes_read;
}

size_t RingBuffer::peek(uint8_t* data, size_t length, size_t offset) const {
    if (!data || length == 0 || !buffer_) {
        return 0;
    }
    
    xSemaphoreTake(mutex_, portMAX_DELAY);
    
    size_t available_data = available();
    if (offset >= available_data) {
        xSemaphoreGive(mutex_);
        return 0;
    }
    
    size_t bytes_to_read = std::min(length, available_data - offset);
    size_t read_pos = (tail_ + offset) % capacity_;
    size_t bytes_read = 0;
    
    while (bytes_read < bytes_to_read) {
        data[bytes_read] = buffer_[read_pos];
        read_pos = (read_pos + 1) % capacity_;
        bytes_read++;
    }
    
    xSemaphoreGive(mutex_);
    
    return bytes_read;
}

void RingBuffer::clear() {
    xSemaphoreTake(mutex_, portMAX_DELAY);
    
    head_ = 0;
    tail_ = 0;
    full_ = false;
    
    xSemaphoreGive(mutex_);
}

size_t RingBuffer::available() const {
    if (full_) {
        return capacity_;
    }
    
    if (head_ >= tail_) {
        return head_ - tail_;
    } else {
        return capacity_ - tail_ + head_;
    }
}

size_t RingBuffer::free_space() const {
    return capacity_ - available();
}

bool RingBuffer::empty() const {
    return (!full_) && (head_ == tail_);
}

bool RingBuffer::full() const {
    return full_;
}

size_t RingBuffer::capacity() const {
    return capacity_;
}

void RingBuffer::skip(size_t bytes) {
    if (bytes == 0) {
        return;
    }
    
    xSemaphoreTake(mutex_, portMAX_DELAY);
    
    size_t available_data = available();
    size_t bytes_to_skip = std::min(bytes, available_data);
    
    tail_ = (tail_ + bytes_to_skip) % capacity_;
    if (bytes_to_skip > 0) {
        full_ = false;
    }
    
    xSemaphoreGive(mutex_);
}

bool RingBuffer::write_would_overflow(size_t length) const {
    return length > free_space();
}

size_t RingBuffer::write_available_space() const {
    return free_space();
}

void RingBuffer::get_stats(RingBufferStats& stats) const {
    xSemaphoreTake(mutex_, portMAX_DELAY);
    
    stats.capacity = capacity_;
    stats.available = available();
    stats.free_space = free_space();
    stats.is_full = full_;
    stats.is_empty = empty();
    stats.head_position = head_;
    stats.tail_position = tail_;
    
    xSemaphoreGive(mutex_);
}

} // namespace irene 