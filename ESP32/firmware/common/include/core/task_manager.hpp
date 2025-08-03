#pragma once

#include "core/types.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include <functional>
#include <string>
#include <vector>

namespace irene {

/**
 * Task management and coordination for the firmware
 * Handles FreeRTOS task creation, monitoring, and cleanup
 */
class TaskManager {
public:
    using TaskFunction = std::function<void()>;
    
    TaskManager();
    ~TaskManager();
    
    // Task creation
    ErrorCode create_task(const std::string& name,
                         TaskFunction task_func,
                         uint32_t stack_size,
                         UBaseType_t priority,
                         BaseType_t core_id = tskNO_AFFINITY);
    
    // Task control
    void delete_task(const std::string& name);
    void suspend_task(const std::string& name);
    void resume_task(const std::string& name);
    
    // Task monitoring
    bool is_task_running(const std::string& name) const;
    uint32_t get_task_stack_free(const std::string& name) const;
    UBaseType_t get_task_priority(const std::string& name) const;
    
    // System monitoring
    void print_task_list() const;
    void print_heap_stats() const;
    uint32_t get_free_heap_size() const;
    uint32_t get_minimum_free_heap_size() const;
    
    // Cleanup
    void cleanup_all_tasks();

private:
    struct TaskInfo {
        std::string name;
        TaskHandle_t handle;
        TaskFunction function;
        uint32_t stack_size;
        UBaseType_t priority;
        BaseType_t core_id;
        bool is_running;
    };
    
    static void task_wrapper(void* param);
    
    std::vector<TaskInfo> tasks_;
    SemaphoreHandle_t tasks_mutex_;
};

} // namespace irene 