#include "ota/ota_manager.hpp"
#include "esp_log.h"
#include "esp_https_ota.h"
#include "esp_ota_ops.h"
#include "esp_app_desc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char* TAG = "OTAManager";

namespace irene {

struct OTATaskParams {
    OTAManager* manager;
    std::string url;
    const char* cert;
};

OTAManager::OTAManager()
    : update_in_progress_(false)
    , update_progress_(0) {
}

OTAManager::~OTAManager() {
    cancel_update();
}

ErrorCode OTAManager::initialize() {
    ESP_LOGI(TAG, "Initializing OTA manager...");
    
    // Print current partition info
    print_partition_info();
    
    ESP_LOGI(TAG, "OTA manager initialized");
    return ErrorCode::SUCCESS;
}

ErrorCode OTAManager::start_update(const std::string& url, const char* server_cert) {
    if (update_in_progress_) {
        ESP_LOGW(TAG, "OTA update already in progress");
        return ErrorCode::OTA_FAILED;
    }
    
    ESP_LOGI(TAG, "Starting OTA update from: %s", url.c_str());
    
    update_in_progress_ = true;
    update_progress_ = 0;
    
    // Create task parameters
    OTATaskParams* params = new OTATaskParams{this, url, server_cert};
    
    // Create OTA task
    BaseType_t result = xTaskCreate(
        ota_task_wrapper,
        "ota_task",
        8192,  // Stack size
        params,
        5,     // Priority
        nullptr
    );
    
    if (result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create OTA task");
        delete params;
        update_in_progress_ = false;
        return ErrorCode::OTA_FAILED;
    }
    
    return ErrorCode::SUCCESS;
}

void OTAManager::cancel_update() {
    if (update_in_progress_) {
        ESP_LOGI(TAG, "Cancelling OTA update...");
        update_in_progress_ = false;
        // Note: Actual cancellation would require more sophisticated task coordination
    }
}

bool OTAManager::check_for_update(const std::string& version_url) {
    // Placeholder implementation
    ESP_LOGI(TAG, "Checking for updates at: %s", version_url.c_str());
    
    // In a real implementation, this would:
    // 1. Fetch version info from server
    // 2. Compare with current version
    // 3. Return true if update available
    
    return false;
}

std::string OTAManager::get_current_version() const {
    const esp_app_desc_t* app_desc = esp_ota_get_app_description();
    return std::string(app_desc->version);
}

std::string OTAManager::get_current_app_name() const {
    const esp_app_desc_t* app_desc = esp_ota_get_app_description();
    return std::string(app_desc->project_name);
}

std::string OTAManager::get_current_app_description() const {
    const esp_app_desc_t* app_desc = esp_ota_get_app_description();
    return std::string(app_desc->date) + " " + std::string(app_desc->time);
}

void OTAManager::set_progress_callback(ProgressCallback callback) {
    progress_callback_ = callback;
}

void OTAManager::set_complete_callback(CompleteCallback callback) {
    complete_callback_ = callback;
}

void OTAManager::print_partition_info() const {
    ESP_LOGI(TAG, "=== Partition Information ===");
    
    const esp_partition_t* running = esp_ota_get_running_partition();
    const esp_partition_t* boot = esp_ota_get_boot_partition();
    
    ESP_LOGI(TAG, "Running partition: %s", running->label);
    ESP_LOGI(TAG, "Boot partition: %s", boot->label);
    
    const esp_app_desc_t* app_desc = esp_ota_get_app_description();
    ESP_LOGI(TAG, "Current version: %s", app_desc->version);
    ESP_LOGI(TAG, "Project: %s", app_desc->project_name);
    ESP_LOGI(TAG, "Build date: %s %s", app_desc->date, app_desc->time);
    
    ESP_LOGI(TAG, "=============================");
}

bool OTAManager::validate_current_partition() const {
    const esp_partition_t* running = esp_ota_get_running_partition();
    
    esp_ota_img_states_t ota_state;
    esp_err_t err = esp_ota_get_state_partition(running, &ota_state);
    
    if (err == ESP_OK) {
        ESP_LOGI(TAG, "Partition state: %d", ota_state);
        return ota_state == ESP_OTA_IMG_VALID;
    }
    
    ESP_LOGW(TAG, "Failed to get partition state: %s", esp_err_to_name(err));
    return false;
}

void OTAManager::ota_task_wrapper(void* param) {
    OTATaskParams* params = static_cast<OTATaskParams*>(param);
    params->manager->ota_task(params->url, params->cert);
    delete params;
    vTaskDelete(nullptr);
}

void OTAManager::ota_task(const std::string url, const char* cert) {
    ESP_LOGI(TAG, "OTA task started");
    
    esp_http_client_config_t config = {};
    config.url = url.c_str();
    config.cert_pem = cert;
    config.timeout_ms = 30000;
    config.keep_alive_enable = true;
    
    esp_https_ota_config_t ota_config = {};
    ota_config.http_config = &config;
    
    esp_https_ota_handle_t https_ota_handle = nullptr;
    esp_err_t err = esp_https_ota_begin(&ota_config, &https_ota_handle);
    
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ESP HTTPS OTA Begin failed: %s", esp_err_to_name(err));
        update_in_progress_ = false;
        if (complete_callback_) {
            complete_callback_(false, "Failed to begin OTA");
        }
        return;
    }
    
    // Get image size for progress calculation
    int total_size = esp_https_ota_get_image_size(https_ota_handle);
    ESP_LOGI(TAG, "OTA image size: %d bytes", total_size);
    
    // Download and write firmware
    while (update_in_progress_) {
        err = esp_https_ota_perform(https_ota_handle);
        
        if (err != ESP_ERR_HTTPS_OTA_IN_PROGRESS) {
            break;
        }
        
        // Update progress
        int downloaded = esp_https_ota_get_image_len_read(https_ota_handle);
        if (total_size > 0) {
            int progress = (downloaded * 100) / total_size;
            if (progress != update_progress_) {
                update_progress_ = progress;
                ESP_LOGI(TAG, "OTA progress: %d%% (%d/%d bytes)", 
                        progress, downloaded, total_size);
                
                if (progress_callback_) {
                    progress_callback_(progress);
                }
            }
        }
        
        vTaskDelay(pdMS_TO_TICKS(100)); // Small delay
    }
    
    if (err == ESP_OK) {
        // Finalize OTA
        err = esp_https_ota_finish(https_ota_handle);
        if (err == ESP_OK) {
            ESP_LOGI(TAG, "OTA update successful! Restart required.");
            update_progress_ = 100;
            
            if (progress_callback_) {
                progress_callback_(100);
            }
            
            if (complete_callback_) {
                complete_callback_(true, "");
            }
            
            // Mark as valid and restart
            esp_ota_mark_app_valid_cancel_rollback();
            vTaskDelay(pdMS_TO_TICKS(1000));
            esp_restart();
        } else {
            ESP_LOGE(TAG, "OTA finish failed: %s", esp_err_to_name(err));
        }
    } else {
        ESP_LOGE(TAG, "OTA failed: %s", esp_err_to_name(err));
        esp_https_ota_abort(https_ota_handle);
    }
    
    update_in_progress_ = false;
    
    if (complete_callback_ && err != ESP_OK) {
        complete_callback_(false, esp_err_to_name(err));
    }
    
    ESP_LOGI(TAG, "OTA task finished");
}

} // namespace irene 