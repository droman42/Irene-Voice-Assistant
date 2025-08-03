#pragma once

#include "core/types.hpp"
#include <string>
#include <functional>

namespace irene {

/**
 * OTA (Over-The-Air) firmware update manager
 * Handles secure firmware updates via HTTPS
 */
class OTAManager {
public:
    using ProgressCallback = std::function<void(int percentage)>;
    using CompleteCallback = std::function<void(bool success, const std::string& error)>;
    
    OTAManager();
    ~OTAManager();
    
    // Initialize OTA subsystem
    ErrorCode initialize();
    
    // Start OTA update
    ErrorCode start_update(const std::string& url,
                          const char* server_cert = nullptr);
    
    // Cancel ongoing update
    void cancel_update();
    
    // Check for updates
    bool check_for_update(const std::string& version_url);
    
    // Get current firmware info
    std::string get_current_version() const;
    std::string get_current_app_name() const;
    std::string get_current_app_description() const;
    
    // Get update status
    bool is_update_in_progress() const { return update_in_progress_; }
    int get_update_progress() const { return update_progress_; }
    
    // Callbacks
    void set_progress_callback(ProgressCallback callback);
    void set_complete_callback(CompleteCallback callback);
    
    // Partition info
    void print_partition_info() const;
    bool validate_current_partition() const;

private:
    bool update_in_progress_;
    int update_progress_;
    
    ProgressCallback progress_callback_;
    CompleteCallback complete_callback_;
    
    void ota_task(const std::string url, const char* cert);
    static void ota_task_wrapper(void* param);
};

} // namespace irene 