import React, { useState, useEffect } from 'react';
import { Speaker, Info, ChevronDown } from 'lucide-react';
import apiClient from '../../utils/apiClient';
import { AudioDeviceInfo } from '../../types/api';

interface AudioOutputConfigSectionProps {
  data: any;
  schema: any;
  onChange: (data: any) => void;
  disabled?: boolean;
}

export const AudioOutputConfigSection: React.FC<AudioOutputConfigSectionProps> = ({
  data,
  schema,
  onChange,
  disabled = false
}) => {
  const [devices, setDevices] = useState<AudioDeviceInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<AudioDeviceInfo | null>(null);

  useEffect(() => {
    loadAudioOutputDevices();
  }, []);

  useEffect(() => {
    // Update selected device when device_id changes
    if (data?.device_id !== undefined && devices.length > 0) {
      const device = devices.find(d => d.id === data.device_id) || null;
      setSelectedDevice(device);
    }
  }, [data?.device_id, devices]);

  const loadAudioOutputDevices = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getAvailableAudioOutputDevices();
      if (response.success) {
        setDevices(response.devices);
      } else {
        console.warn('Failed to load audio output devices:', response.message);
        setDevices([]);
      }
    } catch (error) {
      console.warn('Failed to load audio output devices:', error);
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
      sample_rate: device?.sample_rate || data.sample_rate || 44100,
      channels: device?.channels || data.channels || 2
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
        <Speaker className="h-5 w-5 text-blue-600" />
        <h3 className="text-lg font-medium text-gray-900">Audio Output Configuration</h3>
      </div>

      {/* Device Selection */}
      <div className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">
          Audio Output Device
          {schema?.device_id?.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        <div className="relative">
          <select
            value={data?.device_id === null || data?.device_id === undefined ? '' : data.device_id.toString()}
            onChange={(e) => handleDeviceChange(e.target.value)}
            disabled={disabled || loading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
          >
            <option value="">Default audio output device</option>
            {devices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name} {device.is_default ? '(system default)' : ''} - {device.channels}ch, {device.sample_rate}Hz
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        </div>
        {loading && (
          <div className="text-xs text-gray-500">Loading audio output devices...</div>
        )}
        {!loading && devices.length === 0 && (
          <div className="text-xs text-red-500">No audio output devices found. Check audio dependencies.</div>
        )}
        {schema?.device_id?.description && (
          <div className="flex items-center">
            <Info className="h-3 w-3 text-gray-400 mr-1" />
            <span className="text-xs text-gray-500">{schema.device_id.description}</span>
          </div>
        )}
      </div>

      {/* Device Information */}
      {selectedDevice && (
        <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
          <div className="text-sm font-medium text-blue-900 mb-1">Selected Device: {selectedDevice.name}</div>
          <div className="text-xs text-blue-700">
            ID: {selectedDevice.id} | Channels: {selectedDevice.channels} | Sample Rate: {selectedDevice.sample_rate} Hz
            {selectedDevice.is_default && ' | System Default'}
          </div>
        </div>
      )}

      {/* Sample Rate */}
      {schema?.sample_rate && (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            Sample Rate (Hz)
            {schema.sample_rate.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <input
            type="number"
            value={data?.sample_rate || ''}
            onChange={(e) => handleFieldChange('sample_rate', parseInt(e.target.value) || null)}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm"
            placeholder="44100"
            min="8000"
            max="192000"
            step="100"
          />
          {schema.sample_rate.description && (
            <div className="flex items-center">
              <Info className="h-3 w-3 text-gray-400 mr-1" />
              <span className="text-xs text-gray-500">{schema.sample_rate.description}</span>
            </div>
          )}
        </div>
      )}

      {/* Channels */}
      {schema?.channels && (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            Audio Channels
            {schema.channels.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <select
            value={data?.channels || ''}
            onChange={(e) => handleFieldChange('channels', parseInt(e.target.value) || null)}
            disabled={disabled}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:opacity-50 text-sm appearance-none"
          >
            <option value="">Auto-detect from device</option>
            <option value="1">Mono (1 channel)</option>
            <option value="2">Stereo (2 channels)</option>
            <option value="4">Quadraphonic (4 channels)</option>
            <option value="6">5.1 Surround (6 channels)</option>
            <option value="8">7.1 Surround (8 channels)</option>
          </select>
          {schema.channels.description && (
            <div className="flex items-center">
              <Info className="h-3 w-3 text-gray-400 mr-1" />
              <span className="text-xs text-gray-500">{schema.channels.description}</span>
            </div>
          )}
        </div>
      )}

      {/* Volume */}
      {schema?.volume && (
        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">
            Volume Level
            {schema.volume.required && <span className="text-red-500 ml-1">*</span>}
          </label>
          <div className="flex items-center space-x-3">
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={data?.volume || 1.0}
              onChange={(e) => handleFieldChange('volume', parseFloat(e.target.value))}
              disabled={disabled}
              className="flex-1"
            />
            <span className="text-sm text-gray-600 min-w-[3rem]">
              {Math.round((data?.volume || 1.0) * 100)}%
            </span>
          </div>
          {schema.volume.description && (
            <div className="flex items-center">
              <Info className="h-3 w-3 text-gray-400 mr-1" />
              <span className="text-xs text-gray-500">{schema.volume.description}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
