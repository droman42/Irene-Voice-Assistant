#include "core/state_machine.hpp"
#include "audio/audio_manager.hpp"
#include "network/network_manager.hpp"
#include "ui/ui_controller.hpp"
#include "audio/wake_word_detector.hpp"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"

static const char* TAG = "StateMachine";

namespace irene {

StateMachine::StateMachine()
    : current_state_(SystemState::IDLE_LISTENING)
    , state_entry_time_(0)
    , silence_start_time_(0)
    , stream_start_time_(0)
    , voice_detected_(false) {
}

StateMachine::~StateMachine() = default;

ErrorCode StateMachine::initialize(const AudioConfig& audio_cfg,
                                  const NetworkConfig& network_cfg,
                                  const WakeWordConfig& ww_cfg,
                                  const UIConfig& ui_cfg,
                                  const TLSConfig& tls_cfg) {
    ESP_LOGI(TAG, "Initializing state machine...");
    
    // Store configurations
    ww_config_ = ww_cfg;
    network_config_ = network_cfg;
    
    try {
        // Initialize audio manager
        audio_manager_ = std::make_unique<AudioManager>();
        ErrorCode result = audio_manager_->initialize(audio_cfg);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize audio manager: %d", (int)result);
            return result;
        }
        
        // Initialize network manager
        network_manager_ = std::make_unique<NetworkManager>();
        result = network_manager_->initialize(network_cfg, tls_cfg);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize network manager: %d", (int)result);
            return result;
        }
        
        // Initialize UI controller
        ui_controller_ = std::make_unique<UIController>();
        result = ui_controller_->initialize(ui_cfg);
        if (result != ErrorCode::SUCCESS) {
            ESP_LOGE(TAG, "Failed to initialize UI controller: %d", (int)result);
            return result;
        }
        
        // Initialize wake word detector
        wake_word_detector_ = std::make_unique<WakeWordDetector>();
        // Note: Model data should be provided by the node-specific implementation
        
        // Set up callbacks
        setup_callbacks();
        
        // Initialize state
        transition_to(SystemState::IDLE_LISTENING);
        
        ESP_LOGI(TAG, "State machine initialized successfully");
        return ErrorCode::SUCCESS;
        
    } catch (const std::exception& e) {
        ESP_LOGE(TAG, "Exception during initialization: %s", e.what());
        return ErrorCode::INIT_FAILED;
    }
}

void StateMachine::run() {
    uint32_t current_time = esp_timer_get_time() / 1000; // Convert to ms
    
    // Handle state-specific logic
    switch (current_state_) {
        case SystemState::IDLE_LISTENING:
            handle_idle_listening();
            break;
        case SystemState::STREAMING:
            handle_streaming();
            break;
        case SystemState::COOLDOWN:
            handle_cooldown();
            break;
        case SystemState::WIFI_RETRY:
            handle_wifi_retry();
            break;
        case SystemState::ERROR:
            handle_error();
            break;
    }
    
    // Check for state timeouts
    handle_state_timeout();
}

void StateMachine::on_wake_word_detected() {
    ESP_LOGI(TAG, "Wake word detected!");
    
    if (current_state_ == SystemState::IDLE_LISTENING) {
        // Get back buffer audio for context
        if (audio_manager_) {
            audio_manager_->start_streaming();
        }
        
        // Start network session
        if (network_manager_) {
            network_manager_->start_audio_session(network_config_.node_id);
        }
        
        transition_to(SystemState::STREAMING);
        
        if (event_callback_) {
            event_callback_(SystemEvent::WAKE_WORD_DETECTED);
        }
    }
}

void StateMachine::on_voice_activity_detected(bool active) {
    voice_detected_ = active;
    uint32_t current_time = esp_timer_get_time() / 1000;
    
    if (current_state_ == SystemState::STREAMING) {
        if (!active && silence_start_time_ == 0) {
            // Start silence timer
            silence_start_time_ = current_time;
        } else if (active) {
            // Reset silence timer
            silence_start_time_ = 0;
        }
    }
}

void StateMachine::on_stream_connected() {
    ESP_LOGI(TAG, "Stream connected");
    if (event_callback_) {
        event_callback_(SystemEvent::STREAM_STARTED);
    }
}

void StateMachine::on_stream_disconnected() {
    ESP_LOGI(TAG, "Stream disconnected");
    if (current_state_ == SystemState::STREAMING) {
        transition_to(SystemState::COOLDOWN);
    }
    
    if (event_callback_) {
        event_callback_(SystemEvent::STREAM_ENDED);
    }
}

void StateMachine::on_tls_error() {
    ESP_LOGE(TAG, "TLS error occurred");
    transition_to(SystemState::WIFI_RETRY);
    
    if (event_callback_) {
        event_callback_(SystemEvent::TLS_ERROR);
    }
}

void StateMachine::on_wifi_disconnected() {
    ESP_LOGW(TAG, "WiFi disconnected");
    transition_to(SystemState::WIFI_RETRY);
    
    if (event_callback_) {
        event_callback_(SystemEvent::WIFI_DISCONNECTED);
    }
}

void StateMachine::on_wifi_connected() {
    ESP_LOGI(TAG, "WiFi connected");
    if (current_state_ == SystemState::WIFI_RETRY) {
        transition_to(SystemState::IDLE_LISTENING);
    }
    
    if (event_callback_) {
        event_callback_(SystemEvent::WIFI_CONNECTED);
    }
}

void StateMachine::on_ota_event(SystemEvent event, int progress) {
    ESP_LOGI(TAG, "OTA event: %d, progress: %d%%", (int)event, progress);
    
    if (ui_controller_) {
        switch (event) {
            case SystemEvent::OTA_STARTED:
                ui_controller_->show_ota_progress(0);
                break;
            case SystemEvent::OTA_PROGRESS:
                ui_controller_->show_ota_progress(progress);
                break;
            case SystemEvent::OTA_FINISHED:
                ui_controller_->hide_ota_progress();
                break;
            case SystemEvent::OTA_ERROR:
                ui_controller_->hide_ota_progress();
                ui_controller_->show_error_message("OTA Failed");
                break;
            default:
                break;
        }
    }
    
    if (event_callback_) {
        event_callback_(event);
    }
}

void StateMachine::trigger_push_to_talk() {
    ESP_LOGI(TAG, "Push-to-talk triggered");
    if (current_state_ == SystemState::IDLE_LISTENING) {
        on_wake_word_detected();
    }
}

void StateMachine::trigger_cooldown() {
    if (current_state_ == SystemState::STREAMING) {
        transition_to(SystemState::COOLDOWN);
    }
}

void StateMachine::set_state_change_callback(StateChangeCallback callback) {
    state_change_callback_ = callback;
}

void StateMachine::set_event_callback(EventCallback callback) {
    event_callback_ = callback;
}

void StateMachine::transition_to(SystemState new_state) {
    if (new_state == current_state_) return;
    
    SystemState old_state = current_state_;
    current_state_ = new_state;
    state_entry_time_ = esp_timer_get_time() / 1000;
    
    ESP_LOGI(TAG, "State transition: %d -> %d", (int)old_state, (int)new_state);
    
    // Reset state-specific variables
    silence_start_time_ = 0;
    if (new_state == SystemState::STREAMING) {
        stream_start_time_ = state_entry_time_;
    }
    
    // Update UI
    update_ui_for_state();
    
    // Notify callback
    if (state_change_callback_) {
        state_change_callback_(old_state, new_state);
    }
}

void StateMachine::handle_state_timeout() {
    uint32_t current_time = esp_timer_get_time() / 1000;
    uint32_t time_in_state = current_time - state_entry_time_;
    
    switch (current_state_) {
        case SystemState::STREAMING:
            // Check for silence timeout or max stream time
            if (silence_start_time_ > 0) {
                uint32_t silence_duration = current_time - silence_start_time_;
                if (silence_duration >= 700) { // 700ms silence timeout
                    ESP_LOGI(TAG, "Silence timeout, ending stream");
                    transition_to(SystemState::COOLDOWN);
                }
            }
            
            if (time_in_state >= 8000) { // 8 second max stream time
                ESP_LOGI(TAG, "Max stream time reached, ending stream");
                transition_to(SystemState::COOLDOWN);
            }
            break;
            
        case SystemState::COOLDOWN:
            if (time_in_state >= 400) { // 400ms cooldown
                transition_to(SystemState::IDLE_LISTENING);
            }
            break;
            
        case SystemState::WIFI_RETRY:
            if (time_in_state >= network_config_.reconnect_delay_ms) {
                // Attempt reconnection
                if (network_manager_) {
                    network_manager_->reconnect();
                }
            }
            break;
            
        default:
            break;
    }
}

void StateMachine::update_ui_for_state() {
    if (!ui_controller_) return;
    
    ui_controller_->show_system_state(current_state_);
}

void StateMachine::handle_idle_listening() {
    // Wake word detection is handled by callback
    // Just ensure audio capture is running
    if (audio_manager_ && !audio_manager_->is_capturing()) {
        audio_manager_->start_capture();
    }
}

void StateMachine::handle_streaming() {
    // Audio streaming is handled by the audio manager
    // Network transmission is handled by network manager
    // We just monitor for end conditions in handle_state_timeout()
}

void StateMachine::handle_cooldown() {
    // Stop audio streaming
    if (audio_manager_) {
        audio_manager_->stop_streaming();
    }
    
    // End network session
    if (network_manager_) {
        network_manager_->end_audio_session();
    }
}

void StateMachine::handle_wifi_retry() {
    // WiFi reconnection logic is handled in handle_state_timeout()
    // UI should show retry status
}

void StateMachine::handle_error() {
    // Error recovery logic
    ESP_LOGW(TAG, "In error state - attempting recovery");
    
    // Try to restart components
    uint32_t current_time = esp_timer_get_time() / 1000;
    uint32_t time_in_state = current_time - state_entry_time_;
    
    if (time_in_state >= 5000) { // Try recovery after 5 seconds
        transition_to(SystemState::WIFI_RETRY);
    }
}

void StateMachine::setup_callbacks() {
    // Set up audio manager callbacks
    if (audio_manager_) {
        audio_manager_->set_vad_callback([this](bool voice_detected) {
            on_voice_activity_detected(voice_detected);
        });
        
        audio_manager_->set_audio_data_callback([this](const int16_t* data, size_t samples) {
            // Forward audio data to network manager for streaming
            if (current_state_ == SystemState::STREAMING && network_manager_) {
                network_manager_->send_audio_data(reinterpret_cast<const uint8_t*>(data), 
                                                 samples * sizeof(int16_t));
            }
        });
    }
    
    // Set up network manager callbacks
    if (network_manager_) {
        network_manager_->set_connection_callback([this](bool connected) {
            if (connected) {
                on_stream_connected();
            } else {
                on_stream_disconnected();
            }
        });
        
        network_manager_->set_error_callback([this](ErrorCode error, const std::string& details) {
            ESP_LOGE(TAG, "Network error: %d - %s", (int)error, details.c_str());
            if (error == ErrorCode::TLS_FAILED) {
                on_tls_error();
            } else if (error == ErrorCode::WIFI_FAILED) {
                on_wifi_disconnected();
            }
        });
    }
    
    // Set up wake word detector callback
    if (wake_word_detector_) {
        wake_word_detector_->set_detection_callback([this](float confidence, uint32_t latency_ms) {
            ESP_LOGI(TAG, "Wake word detected with confidence: %.3f, latency: %u ms", 
                    confidence, latency_ms);
            on_wake_word_detected();
        });
    }
}

} // namespace irene 