#include "core/task_manager.hpp"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include <algorithm>

static const char* TAG = "TaskManager";

namespace irene {

TaskManager::TaskManager() 
    : tasks_mutex_(nullptr) {
    
    tasks_mutex_ = xSemaphoreCreateMutex();
    if (!tasks_mutex_) {
        ESP_LOGE(TAG, "Failed to create tasks mutex");
    }
    
    ESP_LOGI(TAG, "Task manager initialized");
}

TaskManager::~TaskManager() {
    cleanup_all_tasks();
    
    if (tasks_mutex_) {
        vSemaphoreDelete(tasks_mutex_);
    }
}

ErrorCode TaskManager::create_task(const std::string& name,
                                  TaskFunction task_func,
                                  uint32_t stack_size,
                                  UBaseType_t priority,
                                  BaseType_t core_id) {
    
    if (!tasks_mutex_) {
        ESP_LOGE(TAG, "Task manager not properly initialized");
        return ErrorCode::INIT_FAILED;
    }
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    // Check if task already exists
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    if (it != tasks_.end()) {
        ESP_LOGW(TAG, "Task '%s' already exists", name.c_str());
        xSemaphoreGive(tasks_mutex_);
        return ErrorCode::SUCCESS;
    }
    
    // Create task info
    TaskInfo task_info;
    task_info.name = name;
    task_info.function = task_func;
    task_info.stack_size = stack_size;
    task_info.priority = priority;
    task_info.core_id = core_id;
    task_info.is_running = false;
    
    // Create FreeRTOS task
    BaseType_t result;
    if (core_id == tskNO_AFFINITY) {
        result = xTaskCreate(task_wrapper,
                           name.c_str(),
                           stack_size,
                           &task_info,
                           priority,
                           &task_info.handle);
    } else {
        result = xTaskCreatePinnedToCore(task_wrapper,
                                       name.c_str(),
                                       stack_size,
                                       &task_info,
                                       priority,
                                       &task_info.handle,
                                       core_id);
    }
    
    if (result != pdPASS) {
        ESP_LOGE(TAG, "Failed to create task '%s'", name.c_str());
        xSemaphoreGive(tasks_mutex_);
        return ErrorCode::INIT_FAILED;
    }
    
    task_info.is_running = true;
    tasks_.push_back(task_info);
    
    xSemaphoreGive(tasks_mutex_);
    
    ESP_LOGI(TAG, "Created task '%s': stack=%u, priority=%u, core=%d", 
             name.c_str(), stack_size, priority, core_id);
    
    return ErrorCode::SUCCESS;
}

void TaskManager::delete_task(const std::string& name) {
    if (!tasks_mutex_) return;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    if (it != tasks_.end()) {
        if (it->handle) {
            vTaskDelete(it->handle);
        }
        
        ESP_LOGI(TAG, "Deleted task '%s'", name.c_str());
        tasks_.erase(it);
    }
    
    xSemaphoreGive(tasks_mutex_);
}

void TaskManager::suspend_task(const std::string& name) {
    if (!tasks_mutex_) return;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    if (it != tasks_.end() && it->handle) {
        vTaskSuspend(it->handle);
        it->is_running = false;
        ESP_LOGI(TAG, "Suspended task '%s'", name.c_str());
    }
    
    xSemaphoreGive(tasks_mutex_);
}

void TaskManager::resume_task(const std::string& name) {
    if (!tasks_mutex_) return;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    if (it != tasks_.end() && it->handle) {
        vTaskResume(it->handle);
        it->is_running = true;
        ESP_LOGI(TAG, "Resumed task '%s'", name.c_str());
    }
    
    xSemaphoreGive(tasks_mutex_);
}

bool TaskManager::is_task_running(const std::string& name) const {
    if (!tasks_mutex_) return false;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    bool running = (it != tasks_.end()) && it->is_running;
    
    xSemaphoreGive(tasks_mutex_);
    
    return running;
}

uint32_t TaskManager::get_task_stack_free(const std::string& name) const {
    if (!tasks_mutex_) return 0;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    uint32_t free_stack = 0;
    if (it != tasks_.end() && it->handle) {
        free_stack = uxTaskGetStackHighWaterMark(it->handle);
    }
    
    xSemaphoreGive(tasks_mutex_);
    
    return free_stack;
}

UBaseType_t TaskManager::get_task_priority(const std::string& name) const {
    if (!tasks_mutex_) return 0;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    auto it = std::find_if(tasks_.begin(), tasks_.end(),
                          [&name](const TaskInfo& info) {
                              return info.name == name;
                          });
    
    UBaseType_t priority = 0;
    if (it != tasks_.end() && it->handle) {
        priority = uxTaskPriorityGet(it->handle);
    }
    
    xSemaphoreGive(tasks_mutex_);
    
    return priority;
}

void TaskManager::print_task_list() const {
    ESP_LOGI(TAG, "=== Task List ===");
    ESP_LOGI(TAG, "Name                State  Priority  Stack  Core");
    ESP_LOGI(TAG, "--------------------------------------------");
    
    if (!tasks_mutex_) return;
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    for (const auto& task : tasks_) {
        uint32_t free_stack = 0;
        if (task.handle) {
            free_stack = uxTaskGetStackHighWaterMark(task.handle);
        }
        
        ESP_LOGI(TAG, "%-20s %-6s %-8u %-6u %-4d", 
                task.name.c_str(),
                task.is_running ? "RUN" : "SUSP",
                task.priority,
                free_stack,
                task.core_id);
    }
    
    xSemaphoreGive(tasks_mutex_);
    
    ESP_LOGI(TAG, "=================");
}

void TaskManager::print_heap_stats() const {
    uint32_t free_heap = esp_get_free_heap_size();
    uint32_t min_free_heap = esp_get_minimum_free_heap_size();
    uint32_t largest_block = heap_caps_get_largest_free_block(MALLOC_CAP_8BIT);
    
    ESP_LOGI(TAG, "=== Heap Statistics ===");
    ESP_LOGI(TAG, "Free heap: %u bytes", free_heap);
    ESP_LOGI(TAG, "Minimum free heap: %u bytes", min_free_heap);
    ESP_LOGI(TAG, "Largest free block: %u bytes", largest_block);
    
    // PSRAM statistics if available
    if (esp_psram_is_initialized()) {
        uint32_t free_psram = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
        uint32_t total_psram = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
        ESP_LOGI(TAG, "PSRAM: %u / %u bytes free", free_psram, total_psram);
    }
    
    ESP_LOGI(TAG, "=======================");
}

uint32_t TaskManager::get_free_heap_size() const {
    return esp_get_free_heap_size();
}

uint32_t TaskManager::get_minimum_free_heap_size() const {
    return esp_get_minimum_free_heap_size();
}

void TaskManager::cleanup_all_tasks() {
    if (!tasks_mutex_) return;
    
    ESP_LOGI(TAG, "Cleaning up all tasks...");
    
    xSemaphoreTake(tasks_mutex_, portMAX_DELAY);
    
    for (auto& task : tasks_) {
        if (task.handle) {
            ESP_LOGI(TAG, "Deleting task: %s", task.name.c_str());
            vTaskDelete(task.handle);
            task.handle = nullptr;
            task.is_running = false;
        }
    }
    
    tasks_.clear();
    
    xSemaphoreGive(tasks_mutex_);
    
    ESP_LOGI(TAG, "All tasks cleaned up");
}

void TaskManager::task_wrapper(void* param) {
    TaskInfo* task_info = static_cast<TaskInfo*>(param);
    
    if (task_info && task_info->function) {
        ESP_LOGI(TAG, "Starting task: %s", task_info->name.c_str());
        
        try {
            task_info->function();
        } catch (const std::exception& e) {
            ESP_LOGE(TAG, "Task '%s' threw exception: %s", 
                    task_info->name.c_str(), e.what());
        } catch (...) {
            ESP_LOGE(TAG, "Task '%s' threw unknown exception", 
                    task_info->name.c_str());
        }
        
        ESP_LOGI(TAG, "Task '%s' finished", task_info->name.c_str());
    }
    
    // Task should delete itself if it reaches here
    vTaskDelete(nullptr);
}

} // namespace irene 