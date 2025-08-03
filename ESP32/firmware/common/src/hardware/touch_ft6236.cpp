#include "esp_log.h"

// Basic FT6236 touch controller stub implementation

static const char* TAG = "FT6236";

extern "C" {
    void ft6236_init(void) {
        ESP_LOGI(TAG, "FT6236 touch controller initialized (stub)");
    }
    
    bool ft6236_read_touch(int16_t* x, int16_t* y) {
        // Placeholder - no touch detected
        return false;
    }
    
    void ft6236_set_threshold(uint8_t threshold) {
        ESP_LOGD(TAG, "Set touch threshold to %d (stub)", threshold);
    }
} 