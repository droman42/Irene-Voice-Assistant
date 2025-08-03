#pragma once

#include "types.hpp"
#include <functional>
#include <memory>

namespace irene {

class AudioManager;
class NetworkManager; 
class UIController;
class WakeWordDetector;

/**
 * Main state machine that coordinates all firmware components
 * Implements the state transitions defined in the specification
 */
class StateMachine {
public:
    using StateChangeCallback = std::function<void(SystemState, SystemState)>;
    using EventCallback = std::function<void(SystemEvent)>;

    StateMachine();
    ~StateMachine();

    // Initialize all components
    ErrorCode initialize(const AudioConfig& audio_cfg,
                        const NetworkConfig& network_cfg,
                        const WakeWordConfig& ww_cfg,
                        const UIConfig& ui_cfg,
                        const TLSConfig& tls_cfg);

    // Main state machine loop (called from main task)
    void run();

    // Event handlers
    void on_wake_word_detected();
    void on_voice_activity_detected(bool active);
    void on_stream_connected();
    void on_stream_disconnected();
    void on_tls_error();
    void on_wifi_disconnected();
    void on_wifi_connected();
    void on_ota_event(SystemEvent event, int progress = 0);

    // State queries
    SystemState get_current_state() const { return current_state_; }
    bool is_streaming() const { return current_state_ == SystemState::STREAMING; }
    bool is_listening() const { return current_state_ == SystemState::IDLE_LISTENING; }

    // Callbacks
    void set_state_change_callback(StateChangeCallback callback);
    void set_event_callback(EventCallback callback);

    // Manual triggers (for testing/debugging)
    void trigger_push_to_talk();
    void trigger_cooldown();

private:
    void transition_to(SystemState new_state);
    void handle_state_timeout();
    void update_ui_for_state();
    
    // State handlers
    void handle_idle_listening();
    void handle_streaming();
    void handle_cooldown();
    void handle_wifi_retry();
    void handle_error();

    SystemState current_state_;
    uint32_t state_entry_time_;
    
    // Component managers
    std::unique_ptr<AudioManager> audio_manager_;
    std::unique_ptr<NetworkManager> network_manager_;
    std::unique_ptr<UIController> ui_controller_;
    std::unique_ptr<WakeWordDetector> wake_word_detector_;

    // Callbacks
    StateChangeCallback state_change_callback_;
    EventCallback event_callback_;

    // Timing
    uint32_t silence_start_time_;
    uint32_t stream_start_time_;
    bool voice_detected_;
    
    // Configuration
    WakeWordConfig ww_config_;
    NetworkConfig network_config_;
}; 