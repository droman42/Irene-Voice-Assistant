#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_psram.h"
#include "nvs_flash.h"

#include "core/state_machine.hpp"
#include "node_config.h"
#include "certificates.h"
#include "ww_model.h"

static const char* TAG = "kitchen_node";

extern "C" void app_main() {
    ESP_LOGI(TAG, "Starting Irene Voice Assistant - Kitchen Node");
    ESP_LOGI(TAG, "Firmware Version: %s", NODE_FIRMWARE_VERSION);
    ESP_LOGI(TAG, "Build Date: %s %s", __DATE__, __TIME__);

    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Initialize PSRAM
    if (esp_psram_init() != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize PSRAM");
        esp_restart();
    }

    ESP_LOGI(TAG, "PSRAM initialized: %d KB available", esp_psram_get_size() / 1024);

    // Create configuration structures
    irene::AudioConfig audio_config;
    audio_config.sample_rate = 16000;
    audio_config.channels = 1;
    audio_config.bits_per_sample = 16;
    audio_config.frame_size = 320;  // 20ms
    audio_config.buffer_count = 8;

    irene::NetworkConfig network_config;
    network_config.ssid = WIFI_SSID;
    network_config.password = WIFI_PASSWORD;
    network_config.server_uri = SERVER_URI;
    network_config.node_id = NODE_ID;
    network_config.reconnect_delay_ms = 5000;
    network_config.max_retry_count = 10;

    irene::WakeWordConfig ww_config;
    ww_config.threshold = WAKE_WORD_THRESHOLD;
    ww_config.trigger_duration_ms = 450;
    ww_config.back_buffer_ms = 300;
    ww_config.use_psram = true;

    irene::UIConfig ui_config;
    ui_config.display_width = 412;
    ui_config.display_height = 412;
    ui_config.brightness = 80;
    ui_config.idle_timeout_ms = 30000;
    ui_config.show_debug_info = false;

    irene::TLSConfig tls_config;
    tls_config.ca_cert_pem = ca_pem_start;
    tls_config.client_cert_pem = client_pem_start;
    tls_config.client_key_pem = client_key_start;
    tls_config.handshake_timeout_ms = 10000;

    // Initialize state machine
    irene::StateMachine state_machine;
    
    irene::ErrorCode result = state_machine.initialize(
        audio_config, 
        network_config, 
        ww_config, 
        ui_config, 
        tls_config
    );

    if (result != irene::ErrorCode::SUCCESS) {
        ESP_LOGE(TAG, "Failed to initialize state machine: %d", (int)result);
        esp_restart();
    }

    // Set up event callbacks
    state_machine.set_state_change_callback([](irene::SystemState old_state, irene::SystemState new_state) {
        ESP_LOGI(TAG, "State transition: %d -> %d", (int)old_state, (int)new_state);
    });

    state_machine.set_event_callback([](irene::SystemEvent event) {
        ESP_LOGI(TAG, "System event: %d", (int)event);
    });

    ESP_LOGI(TAG, "Initialization complete. Starting main loop...");

    // Main state machine loop
    while (true) {
        state_machine.run();
        vTaskDelay(pdMS_TO_TICKS(10)); // 10ms loop
    }
} 