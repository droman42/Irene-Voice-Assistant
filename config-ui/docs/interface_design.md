# Config-UI Architecture Document

## Overview

This document defines the architecture for transforming the Irene config-ui into a comprehensive web-based administration interface. The interface will provide three main sections: Donations Editor, Monitoring Dashboard, and Configuration Editor, all communicating with Irene's WebAPI for live system management.

## Core Requirements

### 1. **Donations Editor** (WebAPI-based)
- Replace file-based operations with WebAPI calls
- Fetch JSON schema dynamically from backend on startup
- Maintain local state with manual "Apply Changes" workflow
- Backend stores changes to respective files with hot reload
- Validation feedback before saving (dry-run mode)

### 2. **Monitoring Dashboard** (Full Frontend)
- Replace backend HTML generation with React-based dashboard
- Read-only monitoring data with periodic refresh
- Monitoring component configuration via dedicated config widget
- Real-time updates via WebSocket for monitoring data

### 3. **Configuration Editor** (TOML-driven)
- Single page with collapsible sections for each TOML section
- Pre-built widgets for known configuration types
- Individual section testing and validation
- TOML preview before applying changes
- Backend stores changes to TOML file

### 4. **Extensible Architecture**
- Collapsible sidebar navigation for multiple pages/sections
- Each section manages its own save/apply workflow
- Prepared for additional pages and functionality
- Optional cross-section dependency visualization

## System Architecture

### Frontend Architecture

#### Application Structure
```
src/
├── components/
│   ├── layout/
│   │   ├── Sidebar.jsx              # Collapsible navigation
│   │   ├── Header.jsx               # Connection status, system info
│   │   └── Layout.jsx               # Main layout wrapper
│   ├── donations/
│   │   ├── DonationEditor.jsx       # Main donations interface
│   │   ├── MethodEditor.jsx         # Method donation editor
│   │   ├── ValidationPanel.jsx      # Validation feedback
│   │   └── ApplyChangesBar.jsx      # Save/apply controls
│   ├── monitoring/
│   │   ├── Dashboard.jsx            # Main monitoring dashboard
│   │   ├── MetricsPanel.jsx         # System metrics display
│   │   ├── ComponentStatus.jsx      # Component health status
│   │   └── RealtimeUpdates.jsx      # WebSocket updates
│   ├── configuration/
│   │   ├── ConfigEditor.jsx         # Main config interface
│   │   ├── SectionEditor.jsx        # Individual TOML sections
│   │   ├── ConfigWidgets/           # Pre-built config widgets
│   │   │   ├── BooleanWidget.jsx
│   │   │   ├── ProviderSelector.jsx
│   │   │   ├── NumberInput.jsx
│   │   │   └── StringInput.jsx
│   │   ├── TomlPreview.jsx          # TOML output preview
│   │   └── TestResults.jsx          # Configuration test results
│   └── shared/
│       ├── ApiClient.js             # Centralized API communication
│       ├── WebSocketManager.js      # WebSocket management
│       └── ValidationUtils.js       # Common validation logic
└── pages/
    ├── DonationsPage.jsx            # /donations route
    ├── MonitoringPage.jsx           # /monitoring route
    ├── ConfigurationPage.jsx        # /configuration route
    └── HomePage.jsx                 # / route (dashboard overview)
```

#### Navigation Structure
```jsx
const navigationSections = [
  {
    id: 'overview',
    title: 'Overview',
    icon: 'Home',
    path: '/'
  },
  {
    id: 'donations',
    title: 'Donations',
    icon: 'FileText',
    path: '/donations'
  },
  {
    id: 'monitoring',
    title: 'Monitoring',
    icon: 'Activity',
    path: '/monitoring'
  },
  {
    id: 'configuration',
    title: 'Configuration',
    icon: 'Settings',
    path: '/configuration'
  }
  // Prepared for future sections
];
```  

## Required Backend API Enhancements

### 1. Donations Management APIs

**Extend IntentComponent WebAPI Router**:
```python
# Core donation operations
GET    /intents/donations                           # List all donations with metadata
GET    /intents/donations/{handler_name}            # Get specific donation JSON
PUT    /intents/donations/{handler_name}            # Update donation + hot reload
POST   /intents/donations/{handler_name}/validate   # Dry-run validation
POST   /intents/reload                              # Reload entire intent system

# Schema discovery for donations
GET    /intents/schema                              # Get donation JSON schema
```

### 2. Configuration Management APIs

**New ConfigurationComponent with WebAPI Interface**:
```python
# TOML configuration management
GET    /config                                      # Get current TOML configuration
GET    /config/schema                               # Get configuration schema/structure
PUT    /config/sections/{section_name}              # Update specific TOML section
POST   /config/sections/{section_name}/validate     # Test section configuration
POST   /config/sections/{section_name}/preview      # Preview TOML output
POST   /config/apply                                # Apply all pending changes

# Widget specifications
GET    /config/widgets                              # Get widget definitions for UI
```

### 3. Enhanced Monitoring APIs

**Extend MonitoringComponent for Frontend Dashboard**:
```python
# Dashboard data (replace HTML generation)
GET    /monitoring/dashboard/data                   # JSON dashboard data
GET    /monitoring/metrics/summary                  # Summary metrics
GET    /monitoring/components/health                # Component health status
GET    /monitoring/system/overview                  # System overview stats

# WebSocket for real-time updates
WS     /ws/monitoring/live                          # Live monitoring updates
```

### 4. Configuration Widget System

**Widget Definition API**:
```python
# Widget specifications for config sections
{
  "tts": {
    "enabled": {"type": "boolean", "label": "Enable TTS"},
    "default_provider": {"type": "select", "options": ["console", "elevenlabs"], "label": "Default Provider"},
    "providers": {
      "elevenlabs": {
        "api_key": {"type": "password", "label": "API Key"},
        "voice_id": {"type": "string", "label": "Voice ID"}
      }
    }
  }
}
```

## Section-Specific Implementations

### 1. Donations Editor Implementation

#### Component Architecture
```jsx
// Main donations page
const DonationsPage = () => {
  const [donations, setDonations] = useState({});
  const [schema, setSchema] = useState(null);
  const [hasChanges, setHasChanges] = useState(false);
  const [selectedHandler, setSelectedHandler] = useState(null);

  // Load initial data
  useEffect(() => {
    Promise.all([
      apiClient.get('/intents/donations'),
      apiClient.get('/intents/schema')
    ]).then(([donationsData, schemaData]) => {
      setDonations(donationsData);
      setSchema(schemaData);
    });
  }, []);

  return (
    <div className="flex h-full">
      <HandlerList 
        handlers={Object.keys(donations)}
        selected={selectedHandler}
        onSelect={setSelectedHandler}
        hasChanges={hasChanges}
      />
      <DonationEditor 
        donation={donations[selectedHandler]}
        schema={schema}
        onChange={(updated) => {
          setDonations({...donations, [selectedHandler]: updated});
          setHasChanges(true);
        }}
      />
      <ApplyChangesBar 
        visible={hasChanges}
        onApply={async () => {
          await apiClient.put(`/intents/donations/${selectedHandler}`, donations[selectedHandler]);
          setHasChanges(false);
        }}
        onValidate={async () => {
          return await apiClient.post(`/intents/donations/${selectedHandler}/validate`, donations[selectedHandler]);
        }}
      />
    </div>
  );
};
```

#### Data Flow
```
1. Page Load → Fetch donations + schema from API
2. User Edits → Update local state, mark hasChanges=true
3. Validate → API call for dry-run validation
4. Apply → PUT to API → Backend saves file + hot reload → Reset hasChanges
```

### 2. Monitoring Dashboard Implementation

#### Component Architecture
```jsx
// Main monitoring page
const MonitoringPage = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [refreshInterval, setRefreshInterval] = useState(30000); // 30 seconds

  // Periodic refresh
  useEffect(() => {
    const fetchData = async () => {
      const data = await apiClient.get('/monitoring/dashboard/data');
      setDashboardData(data);
    };

    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  // WebSocket for real-time updates (optional enhancement)
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/monitoring/live');
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data);
      setDashboardData(prev => ({ ...prev, ...update }));
    };
    return () => ws.close();
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <SystemOverview data={dashboardData?.system} />
      <ComponentHealth data={dashboardData?.components} />
      <MetricsPanel data={dashboardData?.metrics} />
      <RecentActivity data={dashboardData?.activity} />
    </div>
  );
};
```

### 3. Configuration Editor Implementation

#### Component Architecture
```jsx
// Main configuration page
const ConfigurationPage = () => {
  const [config, setConfig] = useState({});
  const [widgets, setWidgets] = useState({});
  const [previewToml, setPreviewToml] = useState('');
  const [sectionChanges, setSectionChanges] = useState({});

  // Load initial data
  useEffect(() => {
    Promise.all([
      apiClient.get('/config'),
      apiClient.get('/config/widgets')
    ]).then(([configData, widgetData]) => {
      setConfig(configData);
      setWidgets(widgetData);
    });
  }, []);

  const updateSection = (sectionName, sectionData) => {
    setConfig(prev => ({ ...prev, [sectionName]: sectionData }));
    setSectionChanges(prev => ({ ...prev, [sectionName]: true }));
  };

  const applySection = async (sectionName) => {
    await apiClient.put(`/config/sections/${sectionName}`, config[sectionName]);
    setSectionChanges(prev => ({ ...prev, [sectionName]: false }));
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 space-y-4">
        {Object.keys(config).map(sectionName => (
          <ConfigSection
            key={sectionName}
            name={sectionName}
            data={config[sectionName]}
            widgets={widgets[sectionName]}
            hasChanges={sectionChanges[sectionName]}
            onChange={(data) => updateSection(sectionName, data)}
            onTest={async () => {
              return await apiClient.post(`/config/sections/${sectionName}/validate`, config[sectionName]);
            }}
            onApply={() => applySection(sectionName)}
          />
        ))}
      </div>
      <TomlPreviewPanel config={config} />
    </div>
  );
};
```

#### Pre-built Configuration Widgets
```jsx
// Widget factory based on widget specifications
const ConfigWidget = ({ type, value, onChange, options, label, ...props }) => {
  switch (type) {
    case 'boolean':
      return <BooleanWidget value={value} onChange={onChange} label={label} />;
    case 'string':
      return <StringInput value={value} onChange={onChange} label={label} {...props} />;
    case 'password':
      return <PasswordInput value={value} onChange={onChange} label={label} />;
    case 'number':
      return <NumberInput value={value} onChange={onChange} label={label} {...props} />;
    case 'select':
      return <SelectWidget value={value} onChange={onChange} options={options} label={label} />;
    case 'provider_selector':
      return <ProviderSelector value={value} onChange={onChange} component={props.component} />;
    default:
      return <StringInput value={value} onChange={onChange} label={label} />;
  }
};
```

## Core Infrastructure

### 1. API Client Architecture

```jsx
// Centralized API client with error handling
class IreneApiClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async request(endpoint, options = {}) {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    
    return response.json();
  }

  // Donations API
  async getDonations() { return this.request('/intents/donations'); }
  async getDonation(handler) { return this.request(`/intents/donations/${handler}`); }
  async updateDonation(handler, data) { 
    return this.request(`/intents/donations/${handler}`, { method: 'PUT', body: JSON.stringify(data) }); 
  }
  async validateDonation(handler, data) { 
    return this.request(`/intents/donations/${handler}/validate`, { method: 'POST', body: JSON.stringify(data) }); 
  }
  async getDonationSchema() { return this.request('/intents/schema'); }

  // Configuration API
  async getConfig() { return this.request('/config'); }
  async getConfigWidgets() { return this.request('/config/widgets'); }
  async updateConfigSection(section, data) { 
    return this.request(`/config/sections/${section}`, { method: 'PUT', body: JSON.stringify(data) }); 
  }
  async validateConfigSection(section, data) { 
    return this.request(`/config/sections/${section}/validate`, { method: 'POST', body: JSON.stringify(data) }); 
  }

  // Monitoring API
  async getMonitoringData() { return this.request('/monitoring/dashboard/data'); }
  async getSystemMetrics() { return this.request('/monitoring/metrics/summary'); }
}
```

### 2. WebSocket Management

```jsx
// WebSocket manager for real-time updates
class WebSocketManager {
  constructor(baseUrl = 'ws://localhost:8000') {
    this.baseUrl = baseUrl;
    this.connections = new Map();
  }

  connect(endpoint, onMessage) {
    if (this.connections.has(endpoint)) {
      this.connections.get(endpoint).close();
    }

    const ws = new WebSocket(`${this.baseUrl}/ws/${endpoint}`);
    ws.onmessage = (event) => onMessage(JSON.parse(event.data));
    ws.onclose = () => this.connections.delete(endpoint);
    
    this.connections.set(endpoint, ws);
    return ws;
  }

  disconnect(endpoint) {
    if (this.connections.has(endpoint)) {
      this.connections.get(endpoint).close();
      this.connections.delete(endpoint);
    }
  }

  disconnectAll() {
    this.connections.forEach(ws => ws.close());
    this.connections.clear();
  }
}
```

### 3. Layout Components

```jsx
// Main layout with collapsible sidebar
const Layout = ({ children }) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar collapsed={sidebarCollapsed} onToggle={setSidebarCollapsed} />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

// Collapsible sidebar navigation
const Sidebar = ({ collapsed, onToggle }) => {
  const navigate = useNavigate();
  const location = useLocation();
  
  return (
    <div className={`bg-gray-900 text-white transition-all duration-300 ${collapsed ? 'w-16' : 'w-64'}`}>
      <div className="flex items-center justify-between p-4">
        {!collapsed && <h1 className="text-xl font-bold">Irene Admin</h1>}
        <button onClick={() => onToggle(!collapsed)} className="p-2">
          {collapsed ? <ChevronRight /> : <ChevronLeft />}
        </button>
      </div>
      
      <nav className="mt-8">
        {navigationSections.map(section => (
          <button
            key={section.id}
            onClick={() => navigate(section.path)}
            className={`w-full flex items-center p-4 hover:bg-gray-800 ${
              location.pathname === section.path ? 'bg-gray-700' : ''
            }`}
          >
            <section.icon className="w-5 h-5" />
            {!collapsed && <span className="ml-3">{section.title}</span>}
          </button>
        ))}
      </nav>
    </div>
  );
};
```

## Implementation Roadmap

### Phase 1: Backend API Development (2-3 weeks)

#### 1.1 Donations API (IntentComponent Extension)
```python
# Priority: HIGH - Core requirement
# Location: irene/components/intent_component.py

@router.get("/donations")
async def get_all_donations():
    """List all donations with metadata"""
    
@router.get("/donations/{handler_name}")
async def get_donation(handler_name: str):
    """Get specific donation JSON"""
    
@router.put("/donations/{handler_name}")
async def update_donation(handler_name: str, donation: dict):
    """Update donation + trigger hot reload"""
    
@router.post("/donations/{handler_name}/validate")
async def validate_donation(handler_name: str, donation: dict):
    """Dry-run validation without saving"""
    
@router.get("/schema")
async def get_donation_schema():
    """Get JSON schema for donations"""
```

#### 1.2 Configuration API (New ConfigurationComponent)
```python
# Priority: HIGH - Core requirement
# Location: irene/components/configuration_component.py

@router.get("/config")
async def get_current_config():
    """Get current TOML configuration"""
    
@router.get("/config/widgets")
async def get_widget_specifications():
    """Get widget definitions for UI rendering"""
    
@router.put("/config/sections/{section_name}")
async def update_config_section(section_name: str, data: dict):
    """Update specific TOML section"""
    
@router.post("/config/sections/{section_name}/validate")
async def validate_config_section(section_name: str, data: dict):
    """Test section configuration"""
    
@router.post("/config/sections/{section_name}/preview")
async def preview_toml_output(section_name: str, data: dict):
    """Preview TOML output for section"""
```

#### 1.3 Monitoring API Enhancement
```python
# Priority: MEDIUM - Replace HTML generation
# Location: irene/components/monitoring_component.py

@router.get("/dashboard/data")
async def get_dashboard_data():
    """JSON dashboard data (replace HTML generation)"""
    
@router.get("/metrics/summary")
async def get_metrics_summary():
    """Summary metrics for overview"""
```

### Phase 2: Frontend Architecture (3-4 weeks)

#### 2.1 Core Infrastructure Setup
- Set up React Router for multi-page navigation
- Implement `IreneApiClient` with error handling
- Create `WebSocketManager` for real-time updates
- Build collapsible sidebar layout

#### 2.2 Donations Editor Page
```jsx
// Priority: HIGH - Direct replacement of current functionality
// Components: DonationsPage, DonationEditor, ApplyChangesBar
// Features: 
// - Load donations + schema from API
// - Local state with change tracking
// - Validation before apply
// - Apply changes with hot reload
```

#### 2.3 Configuration Editor Page
```jsx
// Priority: HIGH - New functionality
// Components: ConfigurationPage, ConfigSection, ConfigWidgets
// Features:
// - Load TOML config + widget specs from API
// - Collapsible sections with individual apply
// - Pre-built widgets (boolean, string, select, etc.)
// - TOML preview panel
// - Section validation and testing
```

#### 2.4 Monitoring Dashboard Page
```jsx
// Priority: MEDIUM - Replace backend HTML
// Components: MonitoringPage, MetricsPanel, ComponentStatus
// Features:
// - Periodic refresh (30s default)
// - Real-time WebSocket updates
// - System overview and component health
// - Metrics visualization
```

### Phase 3: Polish and Enhancement (1-2 weeks)

#### 3.1 User Experience
- Error boundaries and error handling
- Loading states and progress indicators
- Responsive design optimization
- Keyboard shortcuts and accessibility

#### 3.2 Advanced Features
- Cross-section dependency visualization (optional)
- Configuration history and rollback
- Bulk operations support
- Export/import configurations

### Phase 4: Testing and Documentation (1 week)

#### 4.1 Testing
- Unit tests for API client
- Integration tests for key workflows
- E2E tests for critical paths

#### 4.2 Documentation
- User guide for each section
- Developer documentation for extending
- API documentation updates

## Key Technical Decisions

### 1. State Management Strategy
- **Local State with Manual Apply**: Each section maintains local state until user clicks "Apply Changes"
- **No Auto-Save**: Explicit user control over when changes are applied
- **Change Tracking**: Visual indicators for modified sections
- **Validation Before Apply**: Dry-run validation prevents invalid configurations

### 2. API Design Principles
- **RESTful Endpoints**: Standard HTTP methods for CRUD operations
- **Section-Based Updates**: Individual TOML sections can be updated independently
- **Schema-Driven Validation**: Backend provides schemas for frontend validation
- **Hot Reload Support**: Configuration changes trigger automatic system reload

### 3. WebSocket Usage
- **Monitoring Only**: Real-time updates primarily for monitoring dashboard
- **Optional Enhancement**: Configuration testing may use WebSocket for live feedback
- **Graceful Degradation**: System works without WebSocket (periodic refresh)

### 4. Widget System Architecture
- **Pre-built Widgets**: Known configuration types have dedicated widgets
- **Schema-Driven**: Widget selection based on backend-provided specifications
- **Extensible**: Easy to add new widget types for future config options
- **Type Safety**: Widgets enforce proper data types and validation

## Architecture Benefits

### Immediate Value
1. **Donations Editor**: Direct API integration eliminates file management
2. **Configuration Management**: Visual TOML editing with validation
3. **Monitoring Dashboard**: React-based dashboard replaces backend HTML
4. **Extensible Foundation**: Prepared for additional admin features

### Long-term Benefits
1. **System Integration**: Deep integration with Irene's component architecture
2. **Developer Experience**: Live configuration testing and validation
3. **Operational Efficiency**: Single interface for all system administration
4. **Scalability**: Foundation for multi-instance management

## Success Criteria

### Phase 1 Success (Backend APIs)
- [ ] Donations can be loaded, edited, and saved via API
- [ ] Configuration sections can be retrieved and updated
- [ ] Monitoring data available as JSON (HTML generation removed)
- [ ] All APIs include proper validation and error handling

### Phase 2 Success (Frontend)
- [ ] Donations editor works identically to current file-based version
- [ ] Configuration editor allows editing all TOML sections
- [ ] Monitoring dashboard displays system health and metrics
- [ ] Navigation between sections is smooth and intuitive

### Phase 3 Success (Polish)
- [ ] Error handling prevents data loss and provides clear feedback
- [ ] Performance is responsive for all operations
- [ ] UI is accessible and follows design standards
- [ ] Documentation covers all features and use cases

## Migration Strategy

### Backward Compatibility
- Current file-based donations editor remains functional during development
- New API endpoints are additive (no breaking changes to existing APIs)
- Frontend transformation is complete replacement (no gradual migration needed)

### Deployment Approach
- Backend APIs deployed first (tested independently)
- Frontend deployed as complete replacement
- Old file-based UI can be preserved as backup during initial rollout

### Risk Mitigation
- **API Testing**: Comprehensive testing of all backend endpoints before frontend work
- **Progressive Enhancement**: Core functionality works without WebSocket
- **Error Boundaries**: Frontend handles all API failures gracefully
- **Rollback Plan**: Ability to revert to file-based UI if needed

This architecture provides a solid foundation for transforming the config-ui into a comprehensive administration interface while maintaining the reliability and usability that users expect.
