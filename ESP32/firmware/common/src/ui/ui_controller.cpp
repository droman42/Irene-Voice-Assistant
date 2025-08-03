#include "ui/ui_controller.hpp"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstring>

static const char* TAG = "UIController";

namespace irene {

UIController::UIController()
    : initialized_(false)
    , current_state_(SystemState::IDLE_LISTENING)
    , current_brightness_(80)
    , display_(nullptr)
    , screen_(nullptr)
    , state_ring_(nullptr)
    , clock_label_(nullptr)
    , temperature_label_(nullptr)
    , wifi_status_label_(nullptr)
    , wifi_icon_(nullptr)
    , ota_progress_bar_(nullptr)
    , keyword_popup_(nullptr)
    , lvgl_task_handle_(nullptr)
    , screen_timeout_enabled_(true)
    , last_activity_time_(0)
    , ota_progress_visible_(false)
    , last_ota_percentage_(0) {
    
    // Initialize default colors
    color_idle_ = lv_color_hex(0x808080);      // Grey
    color_listening_ = lv_color_hex(0x0080FF);  // Blue
    color_streaming_ = lv_color_hex(0x00FF80);  // Green
    color_error_ = lv_color_hex(0xFF4040);      // Red
    color_background_ = lv_color_hex(0x000000); // Black
}

UIController::~UIController() {
    if (lvgl_task_handle_) {
        vTaskDelete(lvgl_task_handle_);
    }
}

ErrorCode UIController::initialize(const UIConfig& config) {
    ESP_LOGI(TAG, "Initializing UI controller...");
    
    config_ = config;
    
    // Initialize LVGL (placeholder - actual implementation needed)
    lv_init();
    
    // Create LVGL task
    BaseType_t result = xTaskCreatePinnedToCore(
        lvgl_task_wrapper,
        "lvgl_task",
        6144,  // Stack size
        this,
        5,     // Priority
        &lvgl_task_handle_,
        1      // Core 1
    );
    
    if (result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create LVGL task");
        return ErrorCode::DISPLAY_FAILED;
    }
    
    // Initialize display driver (placeholder)
    // In real implementation, this would configure the SPI display
    display_ = reinterpret_cast<lv_disp_t*>(0x12345678); // Placeholder
    
    // Create UI elements
    create_ui_elements();
    
    initialized_ = true;
    current_brightness_ = config.brightness;
    
    ESP_LOGI(TAG, "UI controller initialized successfully");
    ESP_LOGI(TAG, "Display: %dx%d, Brightness: %d%%", 
            config.display_width, config.display_height, config.brightness);
    
    return ErrorCode::SUCCESS;
}

void UIController::show_system_state(SystemState state) {
    if (!initialized_) return;
    
    current_state_ = state;
    last_activity_time_ = xTaskGetTickCount();
    
    // Update state ring color
    lv_color_t ring_color;
    switch (state) {
        case SystemState::IDLE_LISTENING:
            ring_color = color_idle_;
            break;
        case SystemState::STREAMING:
            ring_color = color_streaming_;
            break;
        case SystemState::COOLDOWN:
            ring_color = color_listening_;
            break;
        case SystemState::WIFI_RETRY:
        case SystemState::ERROR:
            ring_color = color_error_;
            break;
        default:
            ring_color = color_idle_;
            break;
    }
    
    set_ring_color(ring_color, 300);
    
    ESP_LOGD(TAG, "System state updated: %d", (int)state);
}

void UIController::show_wake_word_trigger(const std::string& keyword) {
    if (!initialized_) return;
    
    ESP_LOGI(TAG, "Wake word triggered: %s", keyword.c_str());
    
    // Show keyword popup
    show_keyword_popup(keyword, 1000);
    
    // Pulse the ring
    pulse_ring(color_listening_, 1000);
    
    last_activity_time_ = xTaskGetTickCount();
}

void UIController::show_error_message(const std::string& message) {
    if (!initialized_) return;
    
    ESP_LOGW(TAG, "Showing error message: %s", message.c_str());
    
    // Show error popup (placeholder implementation)
    show_keyword_popup("ERROR", 2000);
    set_ring_color(color_error_, 500);
    
    last_activity_time_ = xTaskGetTickCount();
}

void UIController::update_clock(uint8_t hour, uint8_t minute) {
    if (!initialized_ || !clock_label_) return;
    
    // Update clock display (placeholder)
    // lv_label_set_text_fmt(clock_label_, "%02d:%02d", hour, minute);
    
    ESP_LOGD(TAG, "Clock updated: %02d:%02d", hour, minute);
}

void UIController::update_temperature(float celsius, bool is_stale) {
    if (!initialized_ || !temperature_label_) return;
    
    // Update temperature display (placeholder)
    if (is_stale) {
        // lv_label_set_text(temperature_label_, "⛅ -- °C");
        ESP_LOGD(TAG, "Temperature updated: stale");
    } else {
        // lv_label_set_text_fmt(temperature_label_, "⛅ %.0f °C", celsius);
        ESP_LOGD(TAG, "Temperature updated: %.1f°C", celsius);
    }
}

void UIController::update_wifi_status(int rssi_dbm, const std::string& ip_address) {
    if (!initialized_ || !wifi_status_label_) return;
    
    // Determine WiFi signal strength
    lv_color_t signal_color;
    if (rssi_dbm >= -65) {
        signal_color = lv_color_hex(0x00FF00);  // Green
    } else if (rssi_dbm >= -80) {
        signal_color = lv_color_hex(0xFFFF00);  // Yellow
    } else {
        signal_color = lv_color_hex(0xFF0000);  // Red
    }
    
    // Update WiFi status display (placeholder)
    // lv_label_set_text_fmt(wifi_status_label_, "WiFi %d dBm", rssi_dbm);
    
    ESP_LOGD(TAG, "WiFi status updated: %d dBm, IP: %s", rssi_dbm, ip_address.c_str());
}

void UIController::show_ota_progress(int percentage) {
    if (!initialized_) return;
    
    if (!ota_progress_visible_) {
        ota_progress_visible_ = true;
        // Show OTA progress bar (placeholder)
        ESP_LOGI(TAG, "OTA progress started");
    }
    
    last_ota_percentage_ = percentage;
    
    // Update progress bar (placeholder)
    // lv_bar_set_value(ota_progress_bar_, percentage, LV_ANIM_ON);
    
    ESP_LOGD(TAG, "OTA progress: %d%%", percentage);
}

void UIController::hide_ota_progress() {
    if (!initialized_ || !ota_progress_visible_) return;
    
    ota_progress_visible_ = false;
    
    // Hide progress bar (placeholder)
    ESP_LOGI(TAG, "OTA progress hidden");
}

void UIController::set_brightness(uint8_t percentage) {
    current_brightness_ = percentage;
    
    // Set display backlight (placeholder - would control GPIO)
    ESP_LOGD(TAG, "Brightness set to: %d%%", percentage);
}

void UIController::enable_screen_timeout(bool enable) {
    screen_timeout_enabled_ = enable;
    ESP_LOGD(TAG, "Screen timeout %s", enable ? "enabled" : "disabled");
}

void UIController::wake_screen() {
    last_activity_time_ = xTaskGetTickCount();
    
    // Wake up display if sleeping (placeholder)
    ESP_LOGD(TAG, "Screen woken up");
}

void UIController::set_touch_callback(TouchCallback callback) {
    touch_callback_ = callback;
}

void UIController::set_button_callback(ButtonCallback callback) {
    button_callback_ = callback;
}

void UIController::set_ring_color(lv_color_t color, uint32_t animation_duration_ms) {
    if (!initialized_ || !state_ring_) return;
    
    // Animate ring color change (placeholder)
    // lv_obj_set_style_arc_color(state_ring_, color, LV_PART_INDICATOR);
    
    ESP_LOGD(TAG, "Ring color changed with %u ms animation", animation_duration_ms);
}

void UIController::pulse_ring(lv_color_t color, uint32_t duration_ms) {
    if (!initialized_ || !state_ring_) return;
    
    // Create pulsing animation (placeholder)
    ESP_LOGD(TAG, "Ring pulsing for %u ms", duration_ms);
}

void UIController::show_keyword_popup(const std::string& keyword, uint32_t duration_ms) {
    if (!initialized_) return;
    
    // Create/update keyword popup (placeholder)
    ESP_LOGD(TAG, "Keyword popup: '%s' for %u ms", keyword.c_str(), duration_ms);
}

void UIController::apply_dark_theme() {
    color_background_ = lv_color_hex(0x000000);
    ESP_LOGI(TAG, "Dark theme applied");
}

void UIController::apply_light_theme() {
    color_background_ = lv_color_hex(0xFFFFFF);
    ESP_LOGI(TAG, "Light theme applied");
}

void UIController::set_custom_colors(lv_color_t primary, lv_color_t secondary, lv_color_t background) {
    color_listening_ = primary;
    color_streaming_ = secondary;
    color_background_ = background;
    ESP_LOGI(TAG, "Custom colors applied");
}

void UIController::lvgl_task_wrapper(void* arg) {
    static_cast<UIController*>(arg)->update_animations();
}

void UIController::create_ui_elements() {
    ESP_LOGI(TAG, "Creating UI elements...");
    
    // Create main screen (placeholder)
    screen_ = reinterpret_cast<lv_obj_t*>(0x12345678);
    
    // Create state ring (placeholder)
    state_ring_ = reinterpret_cast<lv_obj_t*>(0x12345679);
    
    // Create labels (placeholder)
    clock_label_ = reinterpret_cast<lv_obj_t*>(0x1234567A);
    temperature_label_ = reinterpret_cast<lv_obj_t*>(0x1234567B);
    wifi_status_label_ = reinterpret_cast<lv_obj_t*>(0x1234567C);
    
    // Create progress bar (placeholder)
    ota_progress_bar_ = reinterpret_cast<lv_obj_t*>(0x1234567D);
    
    ESP_LOGI(TAG, "UI elements created");
}

void UIController::update_animations() {
    ESP_LOGI(TAG, "LVGL task started");
    
    TickType_t last_wake_time = xTaskGetTickCount();
    const TickType_t update_period = pdMS_TO_TICKS(50); // 50ms = 20 FPS
    
    while (true) {
        // Update LVGL (placeholder)
        // lv_timer_handler();
        
        // Handle screen timeout
        if (screen_timeout_enabled_) {
            TickType_t current_time = xTaskGetTickCount();
            uint32_t idle_time = (current_time - last_activity_time_) * portTICK_PERIOD_MS;
            
            if (idle_time >= config_.idle_timeout_ms) {
                // Screen should timeout (placeholder)
            }
        }
        
        vTaskDelayUntil(&last_wake_time, update_period);
    }
}

void UIController::touch_event_callback(lv_event_t* event) {
    // Handle touch events (placeholder)
}

void UIController::handle_touch_event(lv_event_t* event) {
    // Process touch input (placeholder)
    wake_screen();
    
    if (touch_callback_) {
        // touch_callback_(x, y, pressed);
    }
}

void UIController::handle_button_event(int button_id, bool pressed) {
    wake_screen();
    
    if (button_callback_) {
        button_callback_(button_id, pressed);
    }
    
    ESP_LOGD(TAG, "Button %d %s", button_id, pressed ? "pressed" : "released");
}

} // namespace irene 