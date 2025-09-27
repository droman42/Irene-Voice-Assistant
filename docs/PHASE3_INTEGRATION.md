# Phase 3 Services Integration Guide

This document explains how the Phase 3 fire-and-forget monitoring services are integrated into the Irene Voice Assistant system and how users can access them.

## 🏗️ **Architecture Overview**

The Phase 3 services are integrated through the **MonitoringComponent** (`irene/components/monitoring_component.py`), which follows the established component architecture pattern used throughout Irene.

### **Integration Pattern**

```
┌─────────────────────────────────────────────────────────────┐
│                    AsyncVACore                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              ComponentManager                           ││
│  │  ┌─────────────────┐  ┌─────────────────────────────────┐││
│  │  │ Intent Component│  │    Monitoring Component         │││
│  │  │                 │  │  ┌─────────────────────────────┐│││
│  │  │ ┌─────────────┐ │  │  │ Phase 3.1: Notifications   ││││
│  │  │ │Intent       │ │  │  │ Phase 3.2: Metrics         ││││
│  │  │ │Handlers     │◄┼──┼──┤ Phase 3.3: Memory Mgmt     ││││
│  │  │ │             │ │  │  │ Phase 3.4: Debug Tools     ││││
│  │  │ └─────────────┘ │  │  │ Phase 3.5: Analytics       ││││
│  │  └─────────────────┘  │  └─────────────────────────────┘│││
│  └─────────────────────────────────────────────────────────┘││
└─────────────────────────────────────────────────────────────┘
```

## 🔧 **System Integration**

### **1. Component Registration**

The MonitoringComponent is registered as an entry-point in `pyproject.toml`:

```toml
[project.entry-points."irene.components"]
monitoring = "irene.components.monitoring_component:MonitoringComponent"
```

### **2. Automatic Discovery**

The system automatically discovers and loads the monitoring component when:
- It's enabled in the configuration: `components.monitoring.enabled = true`
- Required dependencies are available (FastAPI, Pydantic)

### **3. Service Initialization**

During startup (`AsyncVACore.start()`), the MonitoringComponent:

1. **Initializes Phase 3 Services**:
   - NotificationService (Phase 3.1)
   - MetricsCollector (Phase 3.2) 
   - MemoryManager (Phase 3.3)
   - ActionDebugger (Phase 3.4)
   - AnalyticsDashboard (Phase 3.5)

2. **Integrates with Intent Handlers**:
   - Injects services into existing intent handlers
   - Enables fire-and-forget action monitoring
   - Provides lifecycle management capabilities

## 🌐 **User Access Methods**

### **1. Web API Endpoints**

When the WebAPI runner is used, monitoring endpoints are automatically exposed:

#### **Base URL**: `http://localhost:8000/monitoring`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/monitoring/status` | GET | Overall monitoring system status |
| `/monitoring/metrics` | GET | Comprehensive system metrics |
| `/monitoring/memory` | GET | Memory usage and management status |
| `/monitoring/memory/cleanup` | POST | Trigger system memory cleanup |
| `/monitoring/notifications/test` | POST | Send test notification |
| `/monitoring/debug` | GET | Debug system status |
| `/monitoring/dashboard` | GET | Analytics dashboard data (JSON) |
| `/monitoring/dashboard/html` | GET | Analytics dashboard (HTML) |

#### **Example API Usage**:

```bash
# Get system status
curl http://localhost:8000/monitoring/status

# Get metrics
curl http://localhost:8000/monitoring/metrics

# Trigger memory cleanup
curl -X POST http://localhost:8000/monitoring/memory/cleanup?aggressive=false

# View analytics dashboard
curl http://localhost:8000/monitoring/dashboard/html
```

### **2. Configuration-Based Access**

Enable monitoring in your configuration file:

```toml
# Phase 3 Monitoring Component
[monitoring]
enabled = true
# Phase 3.1: User Notification System
notifications_enabled = true
notifications_default_channel = "log"
notifications_tts_enabled = true

# Phase 3.2: Metrics and Monitoring
metrics_enabled = true
metrics_monitoring_interval = 300
metrics_retention_hours = 24

# Phase 3.3: Memory Management
memory_management_enabled = true
memory_cleanup_interval = 1800
memory_aggressive_cleanup = false

# Phase 3.4: Debug Tools
debug_tools_enabled = true
debug_auto_inspect_failures = true
debug_max_history = 1000

# Phase 3.5: Analytics Dashboard
analytics_dashboard_enabled = true
analytics_refresh_interval = 30
# NOTE: Analytics dashboard served via unified web API at system.web_port
```

### **3. Programmatic Access**

Access services programmatically through the component:

```python
# Get monitoring component
monitoring_component = core.component_manager.get_component('monitoring')

# Access individual services
notification_service = monitoring_component.get_notification_service()
metrics_collector = monitoring_component.get_metrics_collector()
memory_manager = monitoring_component.get_memory_manager()
action_debugger = monitoring_component.get_action_debugger()
analytics_dashboard = monitoring_component.get_analytics_dashboard()

# Use services
await notification_service.send_notification(
    session_id="user123",
    message="Action completed successfully",
    notification_type="completion"
)

metrics = metrics_collector.get_all_metrics()
memory_status = await memory_manager.analyze_system_memory_usage()
```

## 🎯 **Feature Capabilities**

### **Phase 3.1: User Notification System**

**Access**: `/monitoring/notifications/*`

- **Completion Notifications**: Automatic notifications when long-running actions complete
- **Failure Alerts**: Critical failure notifications with error details
- **Multi-Channel Delivery**: Log, TTS, UI, and push notification support
- **User Preferences**: Configurable notification settings per user/session

**Example**:
```bash
# Send test notification
curl -X POST http://localhost:8000/monitoring/notifications/test
```

### **Phase 3.2: Metrics and Monitoring**

**Access**: `/monitoring/metrics`

- **Action Metrics**: Success/failure rates, durations, error types
- **System Metrics**: Concurrent actions, peak usage, uptime
- **Domain Analytics**: Per-domain performance statistics
- **Real-time Monitoring**: Live action tracking and alerts

**Example**:
```bash
# Get comprehensive metrics
curl http://localhost:8000/monitoring/metrics | jq '.system_metrics'
```

### **Phase 3.3: Memory Management**

**Access**: `/monitoring/memory/*`

- **Usage Analysis**: Memory consumption across conversation contexts
- **Automatic Cleanup**: Configurable retention policies and cleanup intervals
- **Memory Alerts**: Warnings for high memory usage
- **Optimization Recommendations**: Suggestions for memory efficiency

**Example**:
```bash
# Check memory status
curl http://localhost:8000/monitoring/memory

# Trigger cleanup
curl -X POST http://localhost:8000/monitoring/memory/cleanup?aggressive=true
```

### **Phase 3.4: Debug Tools**

**Access**: `/monitoring/debug`

- **Action Inspection**: Detailed inspection of active and historical actions
- **Test Utilities**: Simulated actions for testing error scenarios
- **Debug Reports**: Comprehensive debugging information export
- **Failure Analysis**: Automatic inspection of failed actions

**Example**:
```bash
# Get debug status
curl http://localhost:8000/monitoring/debug
```

### **Phase 3.5: Analytics Dashboard**

**Access**: `/monitoring/dashboard/html`

- **Visual Dashboard**: Web-based analytics interface
- **Performance Charts**: Graphical representation of system metrics
- **Health Summary**: Overall system health indicators
- **Real-time Updates**: Auto-refreshing dashboard data

**Example**:
```bash
# View dashboard in browser
open http://localhost:8000/monitoring/dashboard/html
```

## 🚀 **Getting Started**

### **1. Enable Monitoring**

Use the provided configuration example:

```bash
# Copy monitoring configuration
cp configs/monitoring-example.toml configs/my-monitoring-config.toml

# Start with monitoring enabled
uv run irene webapi --config configs/my-monitoring-config.toml
```

### **2. Access Web Interface**

1. Start the WebAPI runner: `uv run irene webapi`
2. Open browser to: `http://localhost:8000`
3. Navigate to monitoring endpoints:
   - Status: `http://localhost:8000/monitoring/status`
   - Dashboard: `http://localhost:8000/monitoring/dashboard/html`
   - API Docs: `http://localhost:8000/docs` (includes monitoring endpoints)

### **3. Test Fire-and-Forget Actions**

Fire-and-forget actions are **implemented in the intent handler code**, not configured. The monitoring system automatically tracks any actions that handlers execute asynchronously.

```bash
# Send commands that trigger fire-and-forget actions
curl -X POST http://localhost:8000/execute/command \
  -H "Content-Type: application/json" \
  -d '{"command": "set timer for 30 seconds"}'

curl -X POST http://localhost:8000/execute/command \
  -H "Content-Type: application/json" \
  -d '{"command": "play some music"}'

# Check monitoring dashboard to see action tracking
curl http://localhost:8000/monitoring/dashboard/html
```

**Note**: Fire-and-forget functionality is built into the intent handlers themselves using the `execute_fire_and_forget_action()` method. No configuration is needed - the monitoring system automatically detects and tracks these actions.

## 🔍 **Troubleshooting**

### **Component Not Loading**

If the monitoring component doesn't load:

1. **Check Dependencies**:
   ```bash
   uv run python -c "import fastapi, pydantic; print('Dependencies OK')"
   ```

2. **Verify Configuration**:
   ```toml
   [monitoring]
   enabled = true
   ```

3. **Check Logs**:
   ```bash
   uv run irene webapi --log-level DEBUG
   ```

### **Services Not Available**

If individual services aren't working:

1. **Check Component Status**:
   ```bash
   curl http://localhost:8000/monitoring/status
   ```

2. **Verify Integration**:
   - Ensure intent_system component is enabled
   - Check that required components (TTS, Audio) are available

3. **Review Service Logs**:
   - Look for initialization errors in the logs
   - Check for missing dependencies or configuration issues

## 📊 **Monitoring Best Practices**

1. **Resource Management**:
   - Monitor memory usage regularly
   - Configure appropriate cleanup intervals
   - Set reasonable retention policies

2. **Performance Optimization**:
   - Review metrics regularly for performance trends
   - Use debug tools to identify bottlenecks
   - Optimize based on analytics recommendations

3. **User Experience**:
   - Configure notifications based on user preferences
   - Use appropriate notification channels
   - Monitor action completion rates

4. **System Health**:
   - Set up automated health checks
   - Monitor error rates and types
   - Use analytics dashboard for system overview

## 🔗 **Integration with Existing Features**

The Phase 3 services integrate seamlessly with existing Irene features:

- **Intent Handlers**: Automatic fire-and-forget action tracking
- **Context Management**: Memory usage monitoring and cleanup
- **Web API**: RESTful endpoints for all monitoring features
- **Configuration System**: Standard TOML configuration support
- **Component Architecture**: Follows established patterns and conventions

This integration ensures that Phase 3 monitoring capabilities are available as first-class features within the Irene ecosystem, accessible through familiar interfaces and patterns.
