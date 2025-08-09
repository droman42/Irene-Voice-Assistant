# MQTT Intent Handler Architecture

## Overview

This document describes the architecture for MQTT-based intent handlers with dynamic method generation, enhanced JSON donation schemas, and device discovery integration. This is a **deferred feature** for future implementation, separated from the core intent donation system to maintain architectural clarity.

## Architecture Principles

### 1. Dynamic Method Generation
- MQTT handlers generate Python methods at runtime based on device discovery
- Device templates define method patterns that scale to hundreds of devices
- JSON donations specify both static patterns and dynamic generation rules

### 2. Device Discovery Integration
- Home Assistant MQTT discovery protocol integration
- Dynamic device registry with real-time updates
- Template-based method generation for device classes (lights, climate, sensors)

### 3. Enhanced JSON Schema for Large-Scale Commands
- MQTT-specific donation schema extending base HandlerDonation
- Device templates with placeholder substitution
- Method metadata for generated functions

### 4. Scalable Pattern Management
- Template-based pattern generation for device-specific commands
- Efficient storage and lookup for thousands of device commands
- Context-aware device resolution using room/client metadata

## Enhanced MQTT Donation Schema

### A. MQTT-Specific JSON Structure

```json
{
  "schema_version": "1.0",
  "handler_domain": "mqtt",
  "handler_type": "dynamic_generator",
  "description": "MQTT home automation control with dynamic device discovery",
  
  "discovery_config": {
    "enabled": true,
    "discovery_topic": "homeassistant/+/+/config",
    "state_topic_pattern": "homeassistant/{component}/{node_id}/state",
    "command_topic_pattern": "homeassistant/{component}/{node_id}/set",
    "device_registry_file": "cache/mqtt_devices.json",
    "discovery_timeout": 30,
    "auto_refresh_interval": 300
  },
  
  "global_parameters": [
    {
      "name": "retain",
      "type": "boolean",
      "required": false,
      "default_value": false,
      "description": "Whether to retain MQTT message"
    },
    {
      "name": "qos",
      "type": "integer",
      "required": false,
      "default_value": 0,
      "description": "MQTT Quality of Service level",
      "min_value": 0,
      "max_value": 2
    }
  ],
  
  "device_templates": [
    {
      "template_name": "light_control",
      "device_types": ["light", "switch"],
      "device_classes": ["light", "outlet", "switch"],
      
      "generated_method_metadata": {
        "method_prefix": "control_light",
        "intent_prefix": "light",
        "description_template": "Control {device_name} light in {room_name}",
        "mqtt_topic_template": "{device_config.command_topic}",
        "state_topic_template": "{device_config.state_topic}",
        
        "parameters": [
          {
            "name": "mqtt_topic",
            "type": "string",
            "required": true,
            "value_source": "device.command_topic",
            "description": "MQTT command topic for device"
          },
          {
            "name": "command",
            "type": "choice",
            "required": true,
            "choices": ["ON", "OFF"],
            "default_value": "ON",
            "description": "Device command"
          },
          {
            "name": "brightness",
            "type": "integer",
            "required": false,
            "min_value": 0,
            "max_value": 255,
            "applies_to_commands": ["ON"],
            "applies_to_device_types": ["light"],
            "description": "Light brightness level"
          },
          {
            "name": "color",
            "type": "string",
            "required": false,
            "pattern": "^#[0-9a-fA-F]{6}$",
            "applies_to_commands": ["ON"],
            "applies_to_device_classes": ["color_light"],
            "description": "Light color in hex format"
          }
        ]
      },
      
      "action_donations": [
        {
          "action_type": "turn_on",
          "intent_suffix_template": "turn_on.{room_name}",
          "phrases": [
            "включи {device_display_name}",
            "turn on {device_display_name}",
            "включи {device_type} в {room_name}",
            "свет {room_name} включи",
            "turn on {room_name} {device_type}"
          ],
          "lemmas": ["включить", "свет", "{room_name}", "{device_type}"],
          "command_payload": "ON",
          "boost": 1.1,
          "conditions": {
            "device_supports": ["turn_on"],
            "room_required": false,
            "device_name_required": false
          }
        },
        {
          "action_type": "turn_off",
          "intent_suffix_template": "turn_off.{room_name}",
          "phrases": [
            "выключи {device_display_name}",
            "turn off {device_display_name}",
            "выключи {device_type} в {room_name}",
            "свет {room_name} выключи"
          ],
          "lemmas": ["выключить", "свет", "{room_name}", "{device_type}"],
          "command_payload": "OFF",
          "boost": 1.1,
          "conditions": {
            "device_supports": ["turn_off"],
            "room_required": false
          }
        },
        {
          "action_type": "set_brightness",
          "intent_suffix_template": "brightness.{room_name}",
          "phrases": [
            "яркость {device_display_name} {brightness_value}",
            "set {device_display_name} brightness to {brightness_value}",
            "сделай ярче {device_display_name}",
            "dim {device_display_name}"
          ],
          "lemmas": ["яркость", "ярче", "тусклее", "{device_type}"],
          "command_payload": "ON",
          "boost": 1.0,
          "conditions": {
            "device_supports": ["brightness"],
            "device_classes": ["light"]
          }
        }
      ]
    },
    
    {
      "template_name": "climate_control",
      "device_types": ["climate", "thermostat", "hvac"],
      "device_classes": ["climate"],
      
      "generated_method_metadata": {
        "method_prefix": "control_climate",
        "intent_prefix": "climate",
        "description_template": "Control {device_name} climate in {room_name}",
        
        "parameters": [
          {
            "name": "mqtt_topic",
            "type": "string",
            "required": true,
            "value_source": "device.command_topic"
          },
          {
            "name": "temperature",
            "type": "float",
            "required": false,
            "min_value": 5.0,
            "max_value": 35.0,
            "description": "Target temperature in Celsius"
          },
          {
            "name": "mode",
            "type": "choice",
            "required": false,
            "choices": ["heat", "cool", "auto", "off"],
            "default_value": "auto",
            "description": "Climate control mode"
          }
        ]
      },
      
      "action_donations": [
        {
          "action_type": "set_temperature",
          "intent_suffix_template": "temperature.{room_name}",
          "phrases": [
            "установи температуру {temperature_value}",
            "set temperature to {temperature_value}",
            "сделай теплее в {room_name}",
            "сделай прохладнее в {room_name}"
          ],
          "lemmas": ["температура", "теплее", "прохладнее", "градус"],
          "boost": 1.0,
          "conditions": {
            "device_supports": ["temperature"],
            "room_required": false
          }
        }
      ]
    }
  ],
  
  "static_method_donations": [
    {
      "method_name": "discover_devices",
      "intent_suffix": "discover",
      "description": "Discover and refresh MQTT devices",
      "phrases": [
        "найди устройства", 
        "discover devices", 
        "обнови список устройств",
        "refresh device list"
      ],
      "lemmas": ["найти", "устройство", "обновить", "список"],
      "parameters": [],
      "boost": 1.0
    },
    {
      "method_name": "list_devices",
      "intent_suffix": "list",
      "description": "List available MQTT devices",
      "phrases": [
        "покажи устройства",
        "list devices",
        "какие устройства доступны",
        "show available devices"
      ],
      "lemmas": ["показать", "устройство", "доступный", "список"],
      "parameters": [
        {
          "name": "room_filter",
          "type": "string",
          "required": false,
          "description": "Filter devices by room"
        }
      ],
      "boost": 1.0
    }
  ]
}
```

### B. Enhanced Pydantic Schema for MQTT

```python
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from enum import Enum

class MQTTDiscoveryConfig(BaseModel):
    """MQTT discovery configuration"""
    enabled: bool = True
    discovery_topic: str = "homeassistant/+/+/config"
    state_topic_pattern: str = "homeassistant/{component}/{node_id}/state"
    command_topic_pattern: str = "homeassistant/{component}/{node_id}/set"
    device_registry_file: Optional[str] = "cache/mqtt_devices.json"
    discovery_timeout: int = 30  # seconds
    auto_refresh_interval: int = 300  # seconds

class ActionConditions(BaseModel):
    """Conditions for when an action donation applies"""
    device_supports: List[str] = Field(default_factory=list, description="Required device capabilities")
    device_classes: List[str] = Field(default_factory=list, description="Required device classes")
    device_types: List[str] = Field(default_factory=list, description="Required device types")
    room_required: bool = Field(False, description="Whether room context is required")
    device_name_required: bool = Field(False, description="Whether explicit device name is required")

class GeneratedMethodMetadata(BaseModel):
    """Metadata for dynamically generated methods"""
    method_prefix: str
    intent_prefix: str  
    description_template: str
    mqtt_topic_template: Optional[str] = None
    state_topic_template: Optional[str] = None
    parameters: List[ParameterSpec]

class ActionDonation(BaseModel):
    """Action-specific donation within a device template"""
    action_type: str = Field(..., description="Type of action (turn_on, set_brightness, etc.)")
    intent_suffix_template: str = Field(..., description="Template for intent suffix with placeholders")
    phrases: List[str] = Field(..., min_items=1, description="Phrase templates with placeholders")
    lemmas: List[str] = Field(default_factory=list, description="Key lemmas with placeholders")
    command_payload: Union[str, Dict[str, Any]] = Field(..., description="MQTT command payload")
    boost: float = Field(1.0, ge=0.0, le=10.0, description="Pattern strength multiplier")
    conditions: Optional[ActionConditions] = Field(None, description="Conditions for applying this action")

class DeviceTemplate(BaseModel):
    """Template for generating methods for device types"""
    template_name: str = Field(..., description="Unique template identifier")
    device_types: List[str] = Field(..., min_items=1, description="Device types this template applies to")
    device_classes: List[str] = Field(default_factory=list, description="Device classes this template applies to")
    generated_method_metadata: GeneratedMethodMetadata
    action_donations: List[ActionDonation] = Field(..., min_items=1, description="Action-specific donations")
    
    @validator('template_name')
    def template_name_valid_identifier(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError(f'template_name must be alphanumeric with hyphens/underscores, got: {v}')
        return v

class MQTTHandlerDonation(HandlerDonation):
    """Enhanced donation schema for MQTT handlers"""
    handler_type: str = Field("dynamic_generator", description="Handler type")
    discovery_config: Optional[MQTTDiscoveryConfig] = Field(None, description="MQTT discovery configuration")
    device_templates: List[DeviceTemplate] = Field(default_factory=list, description="Device templates")
    static_method_donations: List[MethodDonation] = Field(default_factory=list, description="Static method donations")
    
    @validator('handler_type')
    def validate_handler_type(cls, v):
        allowed_types = ['dynamic_generator', 'static', 'hybrid']
        if v not in allowed_types:
            raise ValueError(f'handler_type must be one of {allowed_types}, got: {v}')
        return v
    
    @validator('device_templates')
    def unique_template_names(cls, v):
        template_names = [template.template_name for template in v]
        if len(template_names) != len(set(template_names)):
            raise ValueError('template_name must be unique within handler')
        return v
```

### C. Static MQTT Handler Example (Standard JSON Donation Format)

For simpler MQTT use cases or initial implementation, MQTT handlers can use the standard JSON donation format without dynamic generation:

```json
{
  "schema_version": "1.0",
  "handler_domain": "mqtt",
  "description": "MQTT home automation control with static method definitions",
  
  "global_parameters": [
    {
      "name": "retain",
      "type": "boolean",
      "required": false,
      "default_value": false,
      "description": "Whether to retain MQTT message"
    },
    {
      "name": "qos",
      "type": "integer",
      "required": false,
      "default_value": 0,
      "description": "MQTT Quality of Service level",
      "min_value": 0,
      "max_value": 2
    }
  ],
  
  "method_donations": [
    {
      "method_name": "turn_on_living_room_light",
      "intent_suffix": "light.turn_on.living_room",
      "description": "Turn on living room light via MQTT",
      "phrases": [
        "включи свет в гостиной", 
        "turn on living room light", 
        "включи гостиную", 
        "light on living room"
      ],
      "lemmas": ["включить", "свет", "гостиная"],
      "parameters": [
        {
          "name": "mqtt_topic",
          "type": "string",
          "required": true,
          "default_value": "home/living_room/light",
          "description": "MQTT topic for living room light"
        },
        {
          "name": "command",
          "type": "string",
          "required": true,
          "default_value": "ON",
          "description": "MQTT command payload"
        }
      ],
      "boost": 1.1
    },
    {
      "method_name": "turn_off_living_room_light",
      "intent_suffix": "light.turn_off.living_room",
      "description": "Turn off living room light via MQTT",
      "phrases": [
        "выключи свет в гостиной", 
        "turn off living room light", 
        "выключи гостиную", 
        "light off living room"
      ],
      "lemmas": ["выключить", "свет", "гостиная"],
      "parameters": [
        {
          "name": "mqtt_topic",
          "type": "string",
          "required": true,
          "default_value": "home/living_room/light",
          "description": "MQTT topic for living room light"
        },
        {
          "name": "command",
          "type": "string",
          "required": true,
          "default_value": "OFF",
          "description": "MQTT command payload"
        }
      ],
      "boost": 1.1
    },
    {
      "method_name": "set_living_room_temperature",
      "intent_suffix": "climate.temperature.living_room",
      "description": "Set living room temperature via MQTT",
      "phrases": [
        "установи температуру в гостиной {temperature}",
        "set living room temperature to {temperature}",
        "температура гостиная {temperature}",
        "сделай в гостиной {temperature} градусов"
      ],
      "lemmas": ["установить", "температура", "гостиная", "градус"],
      "parameters": [
        {
          "name": "mqtt_topic",
          "type": "string",
          "required": true,
          "default_value": "home/living_room/climate",
          "description": "MQTT topic for living room climate control"
        },
        {
          "name": "temperature",
          "type": "float",
          "required": true,
          "min_value": 5.0,
          "max_value": 35.0,
          "description": "Target temperature in Celsius",
          "extraction_patterns": [
            {"pattern": [{"LIKE_NUM": true}], "label": "TEMPERATURE_VALUE"}
          ]
        }
      ],
      "boost": 1.0
    }
  ]
}
```

**Note**: Static MQTT handlers require manual definition of each device command, which can result in hundreds of method donations for complex home automation setups. The dynamic generation approach (described in subsequent sections) is recommended for large-scale deployments.

## Dynamic Method Generation Architecture

### A. MQTT Device Discovery

```python
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from paho.mqtt.client import Client as MQTTClient

logger = logging.getLogger(__name__)

class MQTTDeviceDiscovery:
    """Handles MQTT device discovery and registry management"""
    
    def __init__(self, config: MQTTDiscoveryConfig, mqtt_client: MQTTClient):
        self.config = config
        self.mqtt_client = mqtt_client
        self.discovered_devices: Dict[str, Dict[str, Any]] = {}
        self.discovery_complete = False
        
    async def discover_devices(self) -> Dict[str, Dict[str, Any]]:
        """Discover devices using Home Assistant MQTT discovery protocol"""
        
        if not self.config.enabled:
            logger.info("MQTT discovery disabled, returning empty device list")
            return {}
        
        logger.info(f"Starting MQTT device discovery on topic: {self.config.discovery_topic}")
        
        # Subscribe to discovery topic
        self.mqtt_client.on_message = self._on_discovery_message
        self.mqtt_client.subscribe(self.config.discovery_topic)
        
        # Wait for discovery timeout
        await asyncio.sleep(self.config.discovery_timeout)
        
        # Unsubscribe from discovery topic
        self.mqtt_client.unsubscribe(self.config.discovery_topic)
        self.discovery_complete = True
        
        logger.info(f"Discovery complete: found {len(self.discovered_devices)} devices")
        
        # Save to registry file
        if self.config.device_registry_file:
            await self._save_device_registry()
        
        return self.discovered_devices
    
    def _on_discovery_message(self, client, userdata, message):
        """Handle incoming discovery messages"""
        try:
            topic_parts = message.topic.split('/')
            if len(topic_parts) >= 4:
                # Extract component and node_id from topic
                component = topic_parts[1]  # e.g., 'light', 'switch', 'climate'
                node_id = topic_parts[2]    # e.g., 'living_room_light'
                
                # Parse device configuration
                device_config = json.loads(message.payload.decode())
                
                # Create device identifier
                device_id = f"{component}.{node_id}"
                
                # Extract device information
                device_info = {
                    'id': device_id,
                    'name': device_config.get('name', node_id),
                    'component': component,
                    'node_id': node_id,
                    'device_class': device_config.get('device_class'),
                    'command_topic': device_config.get('command_topic'),
                    'state_topic': device_config.get('state_topic'),
                    'supported_features': device_config.get('supported_features', []),
                    'room': self._extract_room_from_name(device_config.get('name', node_id)),
                    'config': device_config
                }
                
                self.discovered_devices[device_id] = device_info
                logger.debug(f"Discovered device: {device_id} ({device_info['name']})")
                
        except Exception as e:
            logger.warning(f"Failed to parse discovery message from {message.topic}: {e}")
    
    def _extract_room_from_name(self, device_name: str) -> Optional[str]:
        """Extract room name from device name using common patterns"""
        # Simple heuristic - could be enhanced with configuration
        room_keywords = ['living_room', 'bedroom', 'kitchen', 'bathroom', 'office']
        
        device_name_lower = device_name.lower()
        for room in room_keywords:
            if room in device_name_lower:
                return room.replace('_', ' ')
        
        # Try to extract room from name patterns like "Living Room Light"
        words = device_name.split()
        if len(words) >= 2:
            # Assume first part is room if it contains common room words
            potential_room = ' '.join(words[:-1])
            return potential_room if any(word in potential_room.lower() for word in ['room', 'kitchen', 'bath']) else None
        
        return None
    
    async def _save_device_registry(self):
        """Save discovered devices to registry file"""
        try:
            import aiofiles
            
            registry_data = {
                'discovery_timestamp': asyncio.get_event_loop().time(),
                'device_count': len(self.discovered_devices),
                'devices': self.discovered_devices
            }
            
            async with aiofiles.open(self.config.device_registry_file, 'w') as f:
                await f.write(json.dumps(registry_data, indent=2))
                
            logger.info(f"Saved device registry to {self.config.device_registry_file}")
            
        except Exception as e:
            logger.error(f"Failed to save device registry: {e}")
```

### B. Dynamic Method Generator

```python
class MQTTDynamicMethodGenerator:
    """Generates Python methods and donations from device templates"""
    
    def __init__(self, donation: MQTTHandlerDonation):
        self.donation = donation
        self.generated_methods: Dict[str, callable] = {}
        self.generated_donations: List[MethodDonation] = []
    
    async def generate_methods_from_devices(self, devices: Dict[str, Dict[str, Any]]) -> Dict[str, callable]:
        """Generate methods for discovered devices using templates"""
        
        self.generated_methods.clear()
        self.generated_donations.clear()
        
        for template in self.donation.device_templates:
            await self._generate_methods_for_template(template, devices)
        
        logger.info(f"Generated {len(self.generated_methods)} methods from {len(devices)} devices")
        return self.generated_methods
    
    async def _generate_methods_for_template(self, template: DeviceTemplate, devices: Dict[str, Dict[str, Any]]):
        """Generate methods for devices matching a template"""
        
        # Filter devices that match this template
        matching_devices = []
        for device_id, device_info in devices.items():
            if self._device_matches_template(device_info, template):
                matching_devices.append(device_info)
        
        logger.debug(f"Template '{template.template_name}' matches {len(matching_devices)} devices")
        
        # Generate methods for each matching device and action
        for device_info in matching_devices:
            for action_donation in template.action_donations:
                if self._action_applies_to_device(action_donation, device_info):
                    await self._generate_method_for_device_action(template, device_info, action_donation)
    
    def _device_matches_template(self, device_info: Dict[str, Any], template: DeviceTemplate) -> bool:
        """Check if device matches template criteria"""
        
        # Check device type
        if device_info.get('component') in template.device_types:
            return True
        
        # Check device class
        device_class = device_info.get('device_class')
        if device_class and device_class in template.device_classes:
            return True
        
        return False
    
    def _action_applies_to_device(self, action_donation: ActionDonation, device_info: Dict[str, Any]) -> bool:
        """Check if action applies to specific device"""
        
        if not action_donation.conditions:
            return True
        
        conditions = action_donation.conditions
        
        # Check device support requirements
        if conditions.device_supports:
            device_features = device_info.get('supported_features', [])
            if not all(feature in device_features for feature in conditions.device_supports):
                return False
        
        # Check device class requirements
        if conditions.device_classes:
            device_class = device_info.get('device_class')
            if device_class not in conditions.device_classes:
                return False
        
        # Check device type requirements  
        if conditions.device_types:
            if device_info.get('component') not in conditions.device_types:
                return False
        
        return True
    
    async def _generate_method_for_device_action(self, template: DeviceTemplate, 
                                               device_info: Dict[str, Any], 
                                               action_donation: ActionDonation):
        """Generate a specific method for device and action combination"""
        
        # Generate method name
        device_safe_name = self._make_safe_identifier(device_info['node_id'])
        method_name = f"{template.generated_method_metadata.method_prefix}_{action_donation.action_type}_{device_safe_name}"
        
        # Generate intent suffix with placeholder substitution
        intent_suffix = self._substitute_placeholders(
            action_donation.intent_suffix_template, 
            device_info
        )
        
        # Generate phrases with placeholder substitution
        generated_phrases = []
        for phrase_template in action_donation.phrases:
            phrase = self._substitute_placeholders(phrase_template, device_info)
            generated_phrases.append(phrase)
        
        # Generate lemmas with placeholder substitution
        generated_lemmas = []
        for lemma_template in action_donation.lemmas:
            lemma = self._substitute_placeholders(lemma_template, device_info)
            generated_lemmas.append(lemma)
        
        # Generate parameters with device-specific values
        generated_parameters = []
        for param_spec in template.generated_method_metadata.parameters:
            if param_spec.value_source:
                # Resolve parameter value from device info
                param_value = self._resolve_parameter_value(param_spec.value_source, device_info)
                if param_value:
                    generated_param = param_spec.copy()
                    generated_param.default_value = param_value
                    generated_parameters.append(generated_param)
            else:
                generated_parameters.append(param_spec)
        
        # Create method donation
        method_donation = MethodDonation(
            method_name=method_name,
            intent_suffix=intent_suffix,
            description=self._substitute_placeholders(
                template.generated_method_metadata.description_template, 
                device_info
            ),
            phrases=generated_phrases,
            lemmas=generated_lemmas,
            parameters=generated_parameters,
            boost=action_donation.boost
        )
        
        # Generate actual Python method
        generated_method = self._create_dynamic_method(device_info, action_donation, template)
        
        # Store results
        self.generated_methods[method_name] = generated_method
        self.generated_donations.append(method_donation)
        
        logger.debug(f"Generated method: {method_name} for device {device_info['name']}")
    
    def _substitute_placeholders(self, template: str, device_info: Dict[str, Any]) -> str:
        """Substitute placeholders in template strings"""
        
        placeholders = {
            'device_name': device_info['name'],
            'device_display_name': device_info['name'],
            'device_type': device_info['component'],
            'room_name': device_info.get('room', 'unknown'),
            'node_id': device_info['node_id']
        }
        
        result = template
        for placeholder, value in placeholders.items():
            if value:
                result = result.replace(f'{{{placeholder}}}', str(value))
        
        return result
    
    def _resolve_parameter_value(self, value_source: str, device_info: Dict[str, Any]) -> Optional[str]:
        """Resolve parameter value from device info using value_source path"""
        
        # Simple dot notation resolver
        if value_source.startswith('device.'):
            key = value_source[7:]  # Remove 'device.' prefix
            return device_info.get(key)
        
        return None
    
    def _make_safe_identifier(self, name: str) -> str:
        """Convert name to safe Python identifier"""
        import re
        # Replace non-alphanumeric characters with underscores
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        # Ensure it starts with a letter or underscore
        if safe_name and safe_name[0].isdigit():
            safe_name = f'device_{safe_name}'
        return safe_name.lower()
    
    def _create_dynamic_method(self, device_info: Dict[str, Any], 
                             action_donation: ActionDonation, 
                             template: DeviceTemplate) -> callable:
        """Create the actual Python method that will be called"""
        
        async def dynamic_mqtt_method(intent: Intent, context: ConversationContext) -> IntentResult:
            """Dynamically generated MQTT method"""
            
            # Extract parameters from intent
            mqtt_topic = intent.entities.get('mqtt_topic', device_info.get('command_topic'))
            if not mqtt_topic:
                return IntentResult(
                    text=f"No MQTT topic configured for device {device_info['name']}", 
                    success=False
                )
            
            # Build MQTT payload
            if isinstance(action_donation.command_payload, str):
                payload = action_donation.command_payload
            else:
                # Handle complex payloads
                payload = json.dumps(action_donation.command_payload)
            
            # Add additional parameters to payload if needed
            if action_donation.action_type == "set_brightness":
                brightness = intent.entities.get('brightness')
                if brightness is not None:
                    payload = json.dumps({"state": "ON", "brightness": brightness})
            elif action_donation.action_type == "set_temperature":
                temperature = intent.entities.get('temperature')
                if temperature is not None:
                    payload = json.dumps({"temperature": temperature})
            
            # Publish MQTT message
            try:
                # This would use the actual MQTT client from the handler
                # mqtt_client.publish(mqtt_topic, payload, qos=intent.entities.get('qos', 0))
                
                return IntentResult(
                    text=f"Sent {action_donation.action_type} command to {device_info['name']}",
                    success=True,
                    metadata={
                        "device_id": device_info['id'],
                        "device_name": device_info['name'],
                        "mqtt_topic": mqtt_topic,
                        "payload": payload,
                        "action_type": action_donation.action_type
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to send MQTT command to {device_info['name']}: {e}")
                return IntentResult(
                    text=f"Failed to control {device_info['name']}: {e}",
                    success=False
                )
        
        return dynamic_mqtt_method
    
    def get_generated_donations_as_handler_donation(self) -> HandlerDonation:
        """Convert generated donations to HandlerDonation format"""
        
        return HandlerDonation(
            schema_version="1.0",
            handler_domain=self.donation.handler_domain,
            description=f"Dynamically generated methods for {len(self.generated_methods)} MQTT devices",
            method_donations=self.generated_donations,
            global_parameters=self.donation.global_parameters
        )
```

### C. MQTT Handler Implementation

```python
class MQTTDynamicHandler(IntentHandler):
    """MQTT handler with dynamic method generation"""
    
    def __init__(self, mqtt_client: MQTTClient, config: Dict[str, Any]):
        super().__init__()
        self.mqtt_client = mqtt_client
        self.config = config
        self.device_discovery = None
        self.method_generator = None
        self.discovered_devices: Dict[str, Dict[str, Any]] = {}
        
    async def initialize_from_donation(self, donation: MQTTHandlerDonation):
        """Initialize with MQTT-specific donation"""
        self.set_donation(donation)
        
        # Initialize device discovery
        if donation.discovery_config:
            self.device_discovery = MQTTDeviceDiscovery(donation.discovery_config, self.mqtt_client)
        
        # Initialize method generator
        self.method_generator = MQTTDynamicMethodGenerator(donation)
        
        # Discover devices and generate methods
        await self.discover_and_generate_methods()
    
    async def discover_and_generate_methods(self):
        """Discover MQTT devices and generate methods"""
        
        if self.device_discovery:
            # Discover devices
            self.discovered_devices = await self.device_discovery.discover_devices()
            
            # Generate methods from devices
            if self.method_generator:
                generated_methods = await self.method_generator.generate_methods_from_devices(self.discovered_devices)
                
                # Add generated methods to this handler instance
                for method_name, method_func in generated_methods.items():
                    setattr(self, method_name, method_func)
                
                logger.info(f"MQTT handler initialized with {len(generated_methods)} dynamic methods")
    
    async def get_dynamic_donation(self) -> HandlerDonation:
        """Get donation including dynamically generated methods"""
        
        if self.method_generator:
            return self.method_generator.get_generated_donations_as_handler_donation()
        
        return self.donation
    
    # Static methods defined in JSON
    async def discover_devices(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """Rediscover MQTT devices"""
        await self.discover_and_generate_methods()
        
        return IntentResult(
            text=f"Discovered {len(self.discovered_devices)} MQTT devices",
            metadata={"device_count": len(self.discovered_devices)}
        )
    
    async def list_devices(self, intent: Intent, context: ConversationContext) -> IntentResult:
        """List available MQTT devices"""
        
        room_filter = intent.entities.get('room_filter')
        
        devices_to_show = self.discovered_devices.values()
        if room_filter:
            devices_to_show = [d for d in devices_to_show if d.get('room') == room_filter]
        
        device_list = [f"{d['name']} ({d['component']})" for d in devices_to_show]
        
        return IntentResult(
            text=f"Available devices: {', '.join(device_list)}",
            metadata={
                "devices": list(devices_to_show),
                "total_count": len(device_list),
                "room_filter": room_filter
            }
        )
```

## Configuration Integration

### A. TOML Configuration

```toml
# Static MQTT Handler (Available Now)
[intents.handlers.mqtt_static]
enabled = false  # Can be enabled for simple MQTT use cases
handler_class = "StaticMQTTHandler"
config_file = "irene/intents/handlers/mqtt_static.json"

[intents.handlers.mqtt_static.connection]
host = "localhost"
port = 1883
username = ""
password = ""
client_id = "irene-voice-assistant"
keepalive = 60

# Dynamic MQTT Handler (Deferred Feature)
[intents.handlers.mqtt_dynamic]
enabled = false  # Deferred feature
handler_class = "MQTTDynamicHandler"
config_file = "irene/intents/handlers/mqtt/mqtt_handler.json"

[intents.handlers.mqtt_dynamic.connection]
host = "localhost"
port = 1883
username = ""
password = ""
client_id = "irene-voice-assistant"
keepalive = 60

[intents.handlers.mqtt_dynamic.discovery]
enabled = true
discovery_topic = "homeassistant/+/+/config"
discovery_timeout = 30
auto_refresh_interval = 300
device_registry_file = "cache/mqtt_devices.json"

[intents.handlers.mqtt_dynamic.generation]
max_devices_per_template = 1000
method_name_max_length = 100
enable_method_caching = true
validate_generated_methods = true
```

## Performance Considerations

### A. Scalability Metrics

| Scale | Device Count | Generated Methods | Memory Usage | Init Time |
|-------|--------------|-------------------|--------------|-----------|
| Small | 1-50 | 50-200 | ~10 MB | ~5-10s |
| Medium | 50-200 | 200-800 | ~25 MB | ~15-30s |
| Large | 200-500 | 800-2000 | ~50 MB | ~30-60s |
| Enterprise | 500+ | 2000+ | ~100+ MB | ~60s+ |

### B. Optimization Strategies

- **Lazy Loading**: Generate methods only for devices in active use
- **Template Caching**: Cache compiled templates to reduce generation time
- **Device Filtering**: Filter devices by room/area to reduce scope
- **Batch Generation**: Generate methods in batches to prevent blocking
- **Method Pooling**: Reuse method implementations for similar devices

## Implementation Roadmap

### Phase 1: Foundation (Future)
1. Implement basic MQTT connection and discovery
2. Create device template system
3. Basic method generation for simple devices (lights, switches)

### Phase 2: Enhanced Generation (Future)
1. Complex device support (climate, sensors)
2. Advanced parameter handling
3. Device state monitoring and feedback

### Phase 3: Production Features (Future)
1. Performance optimization and caching
2. Device filtering and scoping
3. Hot-reload for device discovery
4. Integration with existing asset management

### Phase 4: Advanced Features (Future)
1. Custom device templates via configuration
2. Device grouping and scenes
3. Advanced MQTT features (retained messages, QoS)
4. Integration with home automation platforms

## Benefits of Deferred Implementation

1. **Architectural Clarity**: Separating MQTT complexity from core intent system
2. **Reduced Complexity**: Focus on foundational intent donation system first
3. **Better Design**: MQTT-specific features can be designed after core system is stable
4. **Resource Management**: Large-scale device management requires careful planning
5. **User Feedback**: Core system feedback can inform MQTT implementation

This MQTT architecture provides a comprehensive framework for handling dynamic, large-scale device control while maintaining separation from the core intent donation system. The deferred implementation allows focus on the foundational architecture first. 