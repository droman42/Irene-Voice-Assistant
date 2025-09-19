/**
 * Smart Microphone Configuration Section
 * 
 * Provides intelligent microphone configuration with device detection,
 * automatic field population, and real-time capability validation.
 */

import React, { useState, useEffect } from 'react';
import { ChevronDown, Mic, Info } from 'lucide-react';
import apiClient from '@/utils/apiClient';
import type { AudioDeviceInfo } from '@/types/api';
// ConfigWidgetProps import removed - not used in this component

interface MicrophoneConfigSectionProps {
  data: any;
  schema: any;
  onChange: (data: any) => void;
  disabled?: boolean;
}

export const MicrophoneConfigSection: React.FC<MicrophoneConfigSectionProps> = ({
  data,
  schema,
  onChange,
  disabled = false
}) => {
  const [devices, setDevices] = useState<AudioDeviceInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<AudioDeviceInfo | null>(null);

  useEffect(() => {
    loadAudioDevices();
  }, []);

  useEffect(() => {
    // Update selected device when device_id changes
    if (data?.device_id !== undefined && devices.length > 0) {
      const device = devices.find(d => d.id === data.device_id) || null;
      setSelectedDevice(device);
    }
  }, [data?.device_id, devices]);

  const loadAudioDevices = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getAvailableAudioDevices();
      if (response.success) {
        setDevices(response.devices);
      } else {
        console.warn('Failed to load audio devices:', response.message);
        setDevices([]);
      }
    } catch (error) {
      console.warn('Failed to load audio devices:', error);
      setDevices([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDeviceChange = (deviceId: string) => {
    const numericId = deviceId === '' ? null : parseInt(deviceId, 10);
    const device = deviceId === '' ? null : devices.find(d => d.id === numericId);
    
    setSelectedDevice(device || null);
    
    // Auto-populate device capabilities
    const newData = {
      ...data,
      device_id: numericId,
      // Auto-set sample rate and channels from device capabilities
      sample_rate: device?.sample_rate || data.sample_rate || 16000,
      channels: device?.channels || data.channels || 1
    };
    
    onChange(newData);
  };

  const handleFieldChange = (fieldName: string, value: any) => {
    onChange({
      ...data,
      [fieldName]: value
    });
  };

  return (
    <div className="space-y-4 p-4 border rounded-lg bg-gray-50">
      <div className="flex items-center space-x-2 mb-4">
        <Mic className="h-5 w-5 text-blue-600" />
        <h3 className="text-lg font-medium text-gray-900">Microphone Configuration</h3>
      </div>

      {/* Device Selection */}
      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">
          Audio Device
          {schema?.device_id?.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        <div className="relative">
          <select
            value={data?.device_id === null || data?.device_id === undefined ? '' : data.device_id.toString()}
            onChange={(e) => handleDeviceChange(e.target.value)}
            disabled={disabled || loading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
          >
            <option value="">Default device</option>
            {devices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name} {device.is_default ? '(system default)' : ''} - {device.channels}ch, {device.sample_rate}Hz
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        </div>
        {loading && (
          <div className="text-xs text-gray-500">Loading audio devices...</div>
        )}
        {!loading && devices.length === 0 && (
          <div className="text-xs text-red-500">No audio devices found. Check audio dependencies.</div>
        )}
        {schema?.device_id?.description && (
          <div className="flex items-center">
            <Info className="h-3 w-3 text-gray-400 mr-1" />
            <span className="text-xs text-gray-500">{schema.device_id.description}</span>
          </div>
        )}
      </div>

      {/* Device Capabilities (Read-only) */}
      {selectedDevice && (
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">Sample Rate (Hz)</label>
            <div className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600 text-sm">
              {selectedDevice.sample_rate}
            </div>
            <div className="text-xs text-gray-500">Auto-detected from device</div>
          </div>
          
          <div className="space-y-1">
            <label className="block text-sm font-medium text-gray-700">Channels</label>
            <div className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600 text-sm">
              {selectedDevice.channels}
            </div>
            <div className="text-xs text-gray-500">Auto-detected from device</div>
          </div>
        </div>
      )}

      {/* Other Configuration Fields */}
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            Chunk Size
            {schema?.chunk_size?.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <input
            type="number"
            value={data?.chunk_size ?? schema?.chunk_size?.default ?? 1024}
            onChange={(e) => handleFieldChange('chunk_size', parseInt(e.target.value, 10))}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
          />
          {schema?.chunk_size?.description && (
            <div className="flex items-center">
              <Info className="h-3 w-3 text-gray-400 mr-1" />
              <span className="text-xs text-gray-500">{schema.chunk_size.description}</span>
            </div>
          )}
        </div>

        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            Buffer Queue Size
            {schema?.buffer_queue_size?.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <input
            type="number"
            value={data?.buffer_queue_size ?? schema?.buffer_queue_size?.default ?? 50}
            onChange={(e) => handleFieldChange('buffer_queue_size', parseInt(e.target.value, 10))}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
          />
          {schema?.buffer_queue_size?.description && (
            <div className="flex items-center">
              <Info className="h-3 w-3 text-gray-400 mr-1" />
              <span className="text-xs text-gray-500">{schema.buffer_queue_size.description}</span>
            </div>
          )}
        </div>
      </div>

      {/* Enable/Disable Toggle */}
      <div className="flex items-center space-x-3">
        <input
          type="checkbox"
          id="microphone-enabled"
          checked={data?.enabled ?? true}
          onChange={(e) => handleFieldChange('enabled', e.target.checked)}
          disabled={disabled}
          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
        />
        <label htmlFor="microphone-enabled" className="text-sm font-medium text-gray-700">
          Enable microphone input
        </label>
      </div>
    </div>
  );
};

export default MicrophoneConfigSection;
