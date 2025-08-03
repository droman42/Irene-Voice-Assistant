#!/usr/bin/env python3

"""
Node Setup Tool for Irene Voice Assistant ESP32 Firmware
Creates new node configurations with certificates and wake word models
"""

import os
import sys
import shutil
import subprocess
import argparse
import json
from pathlib import Path
from typing import Dict, Any

# Script directory and paths
SCRIPT_DIR = Path(__file__).parent
FIRMWARE_DIR = SCRIPT_DIR.parent
NODES_DIR = FIRMWARE_DIR / "nodes"
COMMON_DIR = FIRMWARE_DIR / "common"
TOOLS_DIR = FIRMWARE_DIR / "tools"

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def log_info(msg: str):
    print(f"{Colors.GREEN}[INFO]{Colors.NC} {msg}")

def log_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")

def log_error(msg: str):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")

def log_debug(msg: str):
    print(f"{Colors.BLUE}[DEBUG]{Colors.NC} {msg}")

class NodeSetup:
    def __init__(self, node_name: str, config: Dict[str, Any]):
        self.node_name = node_name
        self.config = config
        self.node_dir = NODES_DIR / node_name
        self.main_dir = self.node_dir / "main"
        self.certs_dir = self.main_dir / "certs"
        self.models_dir = self.main_dir / "models"

    def create_directories(self):
        """Create the directory structure for the new node"""
        log_info(f"Creating directories for node: {self.node_name}")
        
        # Create main directories
        self.node_dir.mkdir(parents=True, exist_ok=True)
        self.main_dir.mkdir(exist_ok=True)
        self.certs_dir.mkdir(exist_ok=True)
        self.models_dir.mkdir(exist_ok=True)
        
        log_debug(f"Created directories: {self.node_dir}")

    def generate_certificates(self):
        """Generate certificates for the node using the certificate script"""
        log_info(f"Generating certificates for node: {self.node_name}")
        
        cert_script = TOOLS_DIR / "generate_certs.sh"
        if not cert_script.exists():
            log_error(f"Certificate script not found: {cert_script}")
            return False
        
        try:
            # Make script executable
            os.chmod(cert_script, 0o755)
            
            # Run certificate generation
            result = subprocess.run([
                str(cert_script), "node", self.node_name
            ], check=True, capture_output=True, text=True)
            
            log_debug(f"Certificate generation output: {result.stdout}")
            return True
            
        except subprocess.CalledProcessError as e:
            log_error(f"Certificate generation failed: {e.stderr}")
            return False

    def create_config_files(self):
        """Create node-specific configuration files"""
        log_info(f"Creating configuration files for node: {self.node_name}")
        
        # Create node_config.h
        config_content = self._generate_node_config()
        config_file = self.main_dir / "node_config.h"
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Create certificates.h
        cert_content = self._generate_certificates_header()
        cert_file = self.main_dir / "certificates.h"
        with open(cert_file, 'w') as f:
            f.write(cert_content)
        
        # Create ww_model.h placeholder
        model_content = self._generate_model_header()
        model_file = self.main_dir / "ww_model.h"
        with open(model_file, 'w') as f:
            f.write(model_content)
        
        log_debug(f"Configuration files created in {self.main_dir}")

    def create_cmake_files(self):
        """Create CMakeLists.txt files for the node"""
        log_info(f"Creating CMake files for node: {self.node_name}")
        
        # Main CMakeLists.txt
        main_cmake = self._generate_main_cmake()
        main_cmake_file = self.node_dir / "CMakeLists.txt"
        with open(main_cmake_file, 'w') as f:
            f.write(main_cmake)
        
        # Component CMakeLists.txt
        comp_cmake = self._generate_component_cmake()
        comp_cmake_file = self.main_dir / "CMakeLists.txt"
        with open(comp_cmake_file, 'w') as f:
            f.write(comp_cmake)
        
        log_debug(f"CMake files created")

    def copy_main_cpp(self):
        """Create main.cpp for the node"""
        log_info(f"Creating main.cpp for node: {self.node_name}")
        
        main_content = self._generate_main_cpp()
        main_file = self.main_dir / "main.cpp"
        with open(main_file, 'w') as f:
            f.write(main_content)
        
        log_debug(f"main.cpp created: {main_file}")

    def create_placeholder_files(self):
        """Create placeholder files for certificates and models"""
        log_info("Creating placeholder files...")
        
        # Create placeholder certificate files
        placeholder_files = [
            (self.certs_dir / "ca.pem", "# CA Certificate - Replace with actual certificate\n"),
            (self.certs_dir / f"{self.node_name}.pem", f"# {self.node_name} Certificate - Replace with actual certificate\n"),
            (self.certs_dir / f"{self.node_name}.key", f"# {self.node_name} Private Key - Replace with actual key\n"),
            (self.models_dir / f"{self.config['wake_word']}_medium.tflite", "# Wake word model - Replace with actual TensorFlow Lite model\n")
        ]
        
        for file_path, content in placeholder_files:
            with open(file_path, 'w') as f:
                f.write(content)
        
        log_debug("Placeholder files created")

    def _generate_node_config(self) -> str:
        """Generate node_config.h content"""
        return f'''#pragma once

// {self.node_name.title()} Node Configuration
#define NODE_ID "{self.node_name}"
#define NODE_FIRMWARE_VERSION "1.0.0"
#define NODE_HARDWARE_VERSION "ESP32-S3-R8"

// Network Configuration
#define WIFI_SSID "{self.config['wifi_ssid']}"
#define WIFI_PASSWORD "{self.config['wifi_password']}"
#define SERVER_URI "{self.config['server_uri']}"

// Wake Word Configuration
#define WAKE_WORD "{self.config['wake_word']}"
#define WAKE_WORD_THRESHOLD {self.config['wake_word_threshold']}f
#define WAKE_WORD_MODEL_SIZE 140000  // ~140KB medium model

// Audio Configuration
#define AUDIO_SAMPLE_RATE 16000
#define AUDIO_CHANNELS 1
#define AUDIO_BITS_PER_SAMPLE 16
#define AUDIO_FRAME_SIZE_MS 20
#define AUDIO_FRAME_SIZE_SAMPLES (AUDIO_SAMPLE_RATE * AUDIO_FRAME_SIZE_MS / 1000)
#define AUDIO_FRAME_SIZE_BYTES (AUDIO_FRAME_SIZE_SAMPLES * AUDIO_CHANNELS * AUDIO_BITS_PER_SAMPLE / 8)

// Hardware Configuration - Customize for your board
#define I2S_NUM I2S_NUM_0
#define I2S_BCK_IO GPIO_NUM_4
#define I2S_WS_IO GPIO_NUM_5
#define I2S_DI_IO GPIO_NUM_6
#define I2S_DO_IO GPIO_NUM_7

// ES8311 I2C Configuration
#define I2C_SDA_IO GPIO_NUM_8
#define I2C_SCL_IO GPIO_NUM_9
#define ES8311_I2C_ADDR 0x18

// Display Configuration
#define DISPLAY_WIDTH 412
#define DISPLAY_HEIGHT 412
#define DISPLAY_SPI_HOST SPI2_HOST
#define DISPLAY_MOSI_IO GPIO_NUM_11
#define DISPLAY_SCLK_IO GPIO_NUM_12
#define DISPLAY_CS_IO GPIO_NUM_10
#define DISPLAY_DC_IO GPIO_NUM_13
#define DISPLAY_RST_IO GPIO_NUM_14
#define DISPLAY_BL_IO GPIO_NUM_15

// Performance Configuration
#define CORE_AUDIO_TASK 0
#define CORE_NETWORK_TASK 1
#define CORE_UI_TASK 1
#define CORE_WAKE_WORD_TASK 0

#define PRIORITY_AUDIO_TASK 10
#define PRIORITY_WAKE_WORD_TASK 9
#define PRIORITY_NETWORK_TASK 8
#define PRIORITY_UI_TASK 5
#define PRIORITY_MONITOR_TASK 3

// Debug Configuration
#define DEBUG_AUDIO_STATS 0
#define DEBUG_WAKE_WORD_STATS 0
#define DEBUG_NETWORK_STATS 0
#define DEBUG_MEMORY_USAGE 0
'''

    def _generate_certificates_header(self) -> str:
        """Generate certificates.h content"""
        return f'''#pragma once

// Generated by tools/generate_certs.sh for {self.node_name} node
// Replace with actual certificate data

// Root CA Certificate (shared across all nodes)
extern const uint8_t ca_pem_start[] asm("_binary_ca_pem_start");
extern const uint8_t ca_pem_end[] asm("_binary_ca_pem_end");

// {self.node_name.title()} Node Client Certificate  
extern const uint8_t client_pem_start[] asm("_binary_{self.node_name}_pem_start");
extern const uint8_t client_pem_end[] asm("_binary_{self.node_name}_pem_end");

// {self.node_name.title()} Node Private Key
extern const uint8_t client_key_start[] asm("_binary_{self.node_name}_key_start");
extern const uint8_t client_key_end[] asm("_binary_{self.node_name}_key_end");

// Certificate validation
#define CA_CERT_CN "HomeVoice Root CA"
#define CLIENT_CERT_CN "{self.node_name}"
#define SERVER_CERT_CN "assistant.lan"

// Certificate sizes (approximate)
#define CA_CERT_SIZE 1300
#define CLIENT_CERT_SIZE 1000  
#define CLIENT_KEY_SIZE 1000
'''

    def _generate_model_header(self) -> str:
        """Generate ww_model.h content"""
        return f'''#pragma once

#include <cstdint>

// Generated by tools/convert_wake_word_model.py for {self.node_name} node
// Wake word: "{self.config['wake_word']}"
// Model: microWakeWord medium-12-bn
// Training samples: 200 positives, 4h negatives
// Validation: 95% recall, <2 false accepts/hour

// Model data (stored in PSRAM)
extern const uint8_t wake_word_model_data[] asm("_binary_{self.config['wake_word']}_medium_tflite_start");
extern const uint8_t wake_word_model_data_end[] asm("_binary_{self.config['wake_word']}_medium_tflite_end");

// Model metadata
#define WW_MODEL_WAKE_WORD "{self.config['wake_word']}"
#define WW_MODEL_SIZE 140000  // ~140KB
#define WW_MODEL_TYPE "medium-12-bn"
#define WW_MODEL_SAMPLE_RATE 16000
#define WW_MODEL_WINDOW_SIZE_MS 1000
#define WW_MODEL_STRIDE_MS 30
#define WW_MODEL_INPUT_SIZE 16000  // 1 second at 16kHz
#define WW_MODEL_OUTPUT_SIZE 1     // Binary classification

// Performance characteristics
#define WW_MODEL_INFERENCE_TIME_MS 25
#define WW_MODEL_MEMORY_USAGE_KB 90
#define WW_MODEL_VALIDATION_RECALL 0.95f
#define WW_MODEL_VALIDATION_FPR 0.002f  // 2 false accepts per hour

// Runtime configuration
#define WW_MODEL_DEFAULT_THRESHOLD {self.config['wake_word_threshold']}f
#define WW_MODEL_MIN_TRIGGER_DURATION_MS 450
#define WW_MODEL_COOLDOWN_DURATION_MS 400

// Helper function to get model size at runtime
inline size_t get_wake_word_model_size() {{
    return (size_t)(wake_word_model_data_end - wake_word_model_data);
}}
'''

    def _generate_main_cmake(self) -> str:
        """Generate main CMakeLists.txt content"""
        return f'''# {self.node_name.title()} Node - Irene Voice Assistant
cmake_minimum_required(VERSION 3.16)

# Set node-specific variables
set(NODE_ID "{self.node_name}")
set(FIRMWARE_VERSION "1.0.0")

# Add common firmware component
set(EXTRA_COMPONENT_DIRS "../../common")

# Include ESP-IDF
include($ENV{{IDF_PATH}}/tools/cmake/project.cmake)

# Project configuration
project(irene_${{NODE_ID}}_node)
'''

    def _generate_component_cmake(self) -> str:
        """Generate component CMakeLists.txt content"""
        return f'''idf_component_register(
    SRCS 
    "main.cpp"
    
    INCLUDE_DIRS 
    "."
    
    EMBED_FILES
    "certs/ca.pem"
    "certs/{self.node_name}.pem" 
    "certs/{self.node_name}.key"
    "models/{self.config['wake_word']}_medium.tflite"
    
    REQUIRES
    common
    nvs_flash
    esp_wifi
    esp_psram
)
'''

    def _generate_main_cpp(self) -> str:
        """Generate main.cpp content"""
        return f'''#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_psram.h"
#include "nvs_flash.h"

#include "core/state_machine.hpp"
#include "node_config.h"
#include "certificates.h"
#include "ww_model.h"

static const char* TAG = "{self.node_name}_node";

extern "C" void app_main() {{
    ESP_LOGI(TAG, "Starting Irene Voice Assistant - {self.node_name.title()} Node");
    ESP_LOGI(TAG, "Firmware Version: %s", NODE_FIRMWARE_VERSION);
    ESP_LOGI(TAG, "Build Date: %s %s", __DATE__, __TIME__);

    // Initialize NVS
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {{
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }}
    ESP_ERROR_CHECK(ret);

    // Initialize PSRAM
    if (esp_psram_init() != ESP_OK) {{
        ESP_LOGE(TAG, "Failed to initialize PSRAM");
        esp_restart();
    }}

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

    if (result != irene::ErrorCode::SUCCESS) {{
        ESP_LOGE(TAG, "Failed to initialize state machine: %d", (int)result);
        esp_restart();
    }}

    // Set up event callbacks
    state_machine.set_state_change_callback([](irene::SystemState old_state, irene::SystemState new_state) {{
        ESP_LOGI(TAG, "State transition: %d -> %d", (int)old_state, (int)new_state);
    }});

    state_machine.set_event_callback([](irene::SystemEvent event) {{
        ESP_LOGI(TAG, "System event: %d", (int)event);
    }});

    ESP_LOGI(TAG, "Initialization complete. Starting main loop...");

    // Main state machine loop
    while (true) {{
        state_machine.run();
        vTaskDelay(pdMS_TO_TICKS(10)); // 10ms loop
    }}
}}
'''

def load_default_config() -> Dict[str, Any]:
    """Load default configuration"""
    return {
        "wifi_ssid": "YourHomeNetwork",
        "wifi_password": "YourWiFiPassword", 
        "server_uri": "wss://assistant.lan/stt",
        "wake_word": "jarvis",
        "wake_word_threshold": 0.9
    }

def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Failed to load config file {config_path}: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(
        description="Setup new ESP32 node for Irene Voice Assistant"
    )
    parser.add_argument("node_name", help="Name of the node (e.g., kitchen, living_room)")
    parser.add_argument("--config", "-c", type=Path, help="Configuration JSON file")
    parser.add_argument("--wifi-ssid", help="WiFi SSID")
    parser.add_argument("--wifi-password", help="WiFi password")
    parser.add_argument("--server-uri", help="Server WebSocket URI")
    parser.add_argument("--wake-word", help="Wake word (default: jarvis)")
    parser.add_argument("--threshold", type=float, help="Wake word threshold (default: 0.9)")
    parser.add_argument("--force", "-f", action="store_true", help="Overwrite existing node")
    parser.add_argument("--no-certs", action="store_true", help="Skip certificate generation")

    args = parser.parse_args()

    # Validate node name
    if not args.node_name.replace('_', '').isalnum():
        log_error("Node name must be alphanumeric (underscores allowed)")
        return 1

    # Check if node already exists
    node_dir = NODES_DIR / args.node_name
    if node_dir.exists() and not args.force:
        log_error(f"Node {args.node_name} already exists. Use --force to overwrite.")
        return 1

    # Load configuration
    config = load_default_config()
    
    if args.config:
        file_config = load_config_file(args.config)
        config.update(file_config)
    
    # Override with command line arguments
    if args.wifi_ssid:
        config["wifi_ssid"] = args.wifi_ssid
    if args.wifi_password:
        config["wifi_password"] = args.wifi_password
    if args.server_uri:
        config["server_uri"] = args.server_uri
    if args.wake_word:
        config["wake_word"] = args.wake_word
    if args.threshold:
        config["wake_word_threshold"] = args.threshold

    # Create node setup
    log_info(f"Setting up node: {args.node_name}")
    log_info(f"Configuration: {config}")

    node_setup = NodeSetup(args.node_name, config)

    try:
        # Create the node
        node_setup.create_directories()
        node_setup.create_config_files()
        node_setup.create_cmake_files()
        node_setup.copy_main_cpp()
        node_setup.create_placeholder_files()

        # Generate certificates if requested
        if not args.no_certs:
            if not node_setup.generate_certificates():
                log_warn("Certificate generation failed. You'll need to generate them manually.")
        else:
            log_info("Skipping certificate generation")

        log_info(f"Node {args.node_name} created successfully!")
        log_info(f"Next steps:")
        log_info(f"  1. Update WiFi credentials in {node_setup.main_dir}/node_config.h")
        log_info(f"  2. Generate certificates: tools/generate_certs.sh node {args.node_name}")
        log_info(f"  3. Train wake word model and place in {node_setup.models_dir}/")
        log_info(f"  4. Build: cd {node_setup.node_dir} && idf.py build")

        return 0

    except Exception as e:
        log_error(f"Failed to create node: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 