#pragma once

#include "core/types.hpp"
#include "lvgl.h"
#include <functional>
#include <string>

namespace irene {

/**
 * Controls the LVGL-based circular UI on 1.46" round display
 * Manages state ring, clock, weather, WiFi status, and OTA progress
 */
class UIController {
public:
    using TouchCallback = std::function<void(int x, int y, bool pressed)>;
    using ButtonCallback = std::function<void(int button_id, bool pressed)>;

    UIController();
    ~UIController();

    // Initialize display and LVGL
    ErrorCode initialize(const UIConfig& config);

    // State visualization
    void show_system_state(SystemState state);
    void show_wake_word_trigger(const std::string& keyword);
    void show_error_message(const std::string& message);

    // Status displays
    void update_clock(uint8_t hour, uint8_t minute);
    void update_temperature(float celsius, bool is_stale = false);
    void update_wifi_status(int rssi_dbm, const std::string& ip_address);
    
    // OTA progress
    void show_ota_progress(int percentage);
    void hide_ota_progress();

    // Display control
    void set_brightness(uint8_t percentage);
    void enable_screen_timeout(bool enable);
    void wake_screen();

    // Touch and button handling
    void set_touch_callback(TouchCallback callback);
    void set_button_callback(ButtonCallback callback);

    // Animation control
    void set_ring_color(lv_color_t color, uint32_t animation_duration_ms = 300);
    void pulse_ring(lv_color_t color, uint32_t duration_ms = 1000);
    void show_keyword_popup(const std::string& keyword, uint32_t duration_ms = 1000);

    // Theme and styling
    void apply_dark_theme();
    void apply_light_theme();
    void set_custom_colors(lv_color_t primary, lv_color_t secondary, lv_color_t background);

    // Status
    bool is_initialized() const { return initialized_; }
    uint8_t get_brightness() const { return current_brightness_; }
    SystemState get_displayed_state() const { return current_state_; }

private:
    void create_ui_elements();
    void create_state_ring();
    void create_clock_label();
    void create_temperature_label();
    void create_wifi_status();
    void create_ota_progress_bar();
    
    void update_animations();
    void handle_touch_event(lv_event_t* event);
    void handle_button_event(int button_id, bool pressed);
    
    static void lvgl_task_wrapper(void* arg);
    static void touch_event_callback(lv_event_t* event);
    
    UIConfig config_;
    bool initialized_;
    SystemState current_state_;
    uint8_t current_brightness_;
    
    // LVGL objects
    lv_disp_t* display_;
    lv_obj_t* screen_;
    lv_obj_t* state_ring_;
    lv_obj_t* clock_label_;
    lv_obj_t* temperature_label_;
    lv_obj_t* wifi_status_label_;
    lv_obj_t* wifi_icon_;
    lv_obj_t* ota_progress_bar_;
    lv_obj_t* keyword_popup_;
    
    // Animations
    lv_anim_t ring_anim_;
    lv_anim_t pulse_anim_;
    lv_anim_t keyword_anim_;
    
    // Callbacks
    TouchCallback touch_callback_;
    ButtonCallback button_callback_;
    
    // Task management
    TaskHandle_t lvgl_task_handle_;
    
    // State tracking
    bool screen_timeout_enabled_;
    uint32_t last_activity_time_;
    bool ota_progress_visible_;
    int last_ota_percentage_;
    
    // Color scheme
    lv_color_t color_idle_;
    lv_color_t color_listening_;
    lv_color_t color_streaming_;
    lv_color_t color_error_;
    lv_color_t color_background_;
}; 