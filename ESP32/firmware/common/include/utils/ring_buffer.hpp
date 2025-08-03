#pragma once

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include <cstdint>
#include <stdexcept>

namespace irene {

/**
 * Thread-safe ring buffer statistics
 */
struct RingBufferStats {
    size_t capacity;
    size_t available;
    size_t free_space;
    bool is_full;
    bool is_empty;
    size_t head_position;
    size_t tail_position;
};

/**
 * Thread-safe circular buffer implementation
 * Supports both internal RAM and PSRAM allocation
 * Automatically overwrites oldest data when full
 */
class RingBuffer {
public:
    /**
     * Create ring buffer with specified capacity
     * @param capacity Buffer size in bytes
     * @param use_psram If true, allocate in PSRAM, otherwise in internal RAM
     */
    RingBuffer(size_t capacity, bool use_psram = false);
    
    ~RingBuffer();
    
    // Non-copyable
    RingBuffer(const RingBuffer&) = delete;
    RingBuffer& operator=(const RingBuffer&) = delete;
    
    /**
     * Write data to buffer
     * @param data Data to write
     * @param length Number of bytes to write
     * @return Number of bytes actually written
     */
    size_t write(const uint8_t* data, size_t length);
    
    /**
     * Read data from buffer
     * @param data Buffer to read into
     * @param length Maximum number of bytes to read
     * @return Number of bytes actually read
     */
    size_t read(uint8_t* data, size_t length);
    
    /**
     * Peek at data without removing it from buffer
     * @param data Buffer to read into
     * @param length Maximum number of bytes to read
     * @param offset Offset from current read position
     * @return Number of bytes actually read
     */
    size_t peek(uint8_t* data, size_t length, size_t offset = 0) const;
    
    /**
     * Clear all data from buffer
     */
    void clear();
    
    /**
     * Skip bytes without reading them
     * @param bytes Number of bytes to skip
     */
    void skip(size_t bytes);
    
    // Status queries
    size_t available() const;      // Bytes available to read
    size_t free_space() const;     // Bytes available to write
    bool empty() const;            // True if buffer is empty
    bool full() const;             // True if buffer is full
    size_t capacity() const;       // Total buffer capacity
    
    // Utility functions
    bool write_would_overflow(size_t length) const;
    size_t write_available_space() const;
    void get_stats(RingBufferStats& stats) const;

private:
    uint8_t* buffer_;
    size_t capacity_;
    volatile size_t head_;
    volatile size_t tail_;
    volatile bool full_;
    SemaphoreHandle_t mutex_;
};

} // namespace irene 