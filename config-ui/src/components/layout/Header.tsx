/**
 * Header Component - Top navigation and connection status
 * 
 * Displays the application title, connection status to the Irene API,
 * and provides system information when connected.
 */

import { useState, useEffect } from 'react';
import { Wifi, WifiOff, AlertCircle, CheckCircle2 } from 'lucide-react';
import apiClient from '@/utils/apiClient';
import type { HeaderProps, ConnectionStatus } from '@/types';

interface SystemInfo {
  handlersCount: number;
  donationsCount: number;
  status: string;
}

const Header = ({ connectionStatus: externalStatus, systemInfo: externalSystemInfo }: HeaderProps) => {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // Use external props if provided, otherwise manage internally
  const currentStatus = externalStatus || connectionStatus;
  const currentSystemInfo = externalSystemInfo || systemInfo;

  // Check connection status on mount and periodically with exponential backoff
  useEffect(() => {
    if (!externalStatus) {
      checkConnection();
      
      // Dynamic interval based on connection status and retry count
      const getNextInterval = () => {
        if (connectionStatus === 'connected') {
          return 30000; // 30 seconds when connected
        } else {
          // Exponential backoff: 5s, 10s, 20s, 30s (max)
          const backoffSeconds = Math.min(5 * Math.pow(2, retryCount), 30);
          return backoffSeconds * 1000;
        }
      };

      const scheduleNextCheck = () => {
        const interval = getNextInterval();
        return setTimeout(() => {
          checkConnection().then(scheduleNextCheck);
        }, interval);
      };

      const timeoutId = scheduleNextCheck();
      return () => clearTimeout(timeoutId);
    }
  }, [externalStatus, connectionStatus, retryCount]);

  const checkConnection = async () => {
    // Prevent multiple simultaneous connection checks
    if (isChecking) {
      return;
    }

    try {
      setIsChecking(true);
      setConnectionStatus('connecting');
      
      const isConnected = await apiClient.checkConnection();
      
      if (isConnected) {
        setConnectionStatus('connected');
        setRetryCount(0); // Reset retry count on successful connection
        
        // Get system info if connected
        try {
          const status = await apiClient.getIntentStatus();
          setSystemInfo({
            handlersCount: status.handlers_count || 0,
            donationsCount: status.donations_count || 0,
            status: status.status?.status || 'unknown'
          });
        } catch (e) {
          console.warn('Failed to get system info:', e instanceof Error ? e.message : String(e));
          setSystemInfo(null);
        }
      } else {
        setConnectionStatus('disconnected');
        setSystemInfo(null);
        setRetryCount(prev => prev + 1);
      }
      
      setLastCheck(new Date());
    } catch (error) {
      console.error('Connection check failed:', error);
      setConnectionStatus('disconnected');
      setSystemInfo(null);
      setLastCheck(new Date());
      setRetryCount(prev => prev + 1);
    } finally {
      setIsChecking(false);
    }
  };

  const getConnectionIcon = () => {
    switch (currentStatus) {
      case 'connected':
        return <CheckCircle2 className="w-4 h-4 text-green-600" />;
      case 'disconnected':
      case 'error':
        return <WifiOff className="w-4 h-4 text-red-600" />;
      case 'connecting':
      default:
        return <Wifi className="w-4 h-4 text-yellow-600 animate-pulse" />;
    }
  };

  const getConnectionText = () => {
    switch (currentStatus) {
      case 'connected':
        return currentSystemInfo 
          ? `Connected • ${currentSystemInfo.handlersCount} handlers • ${currentSystemInfo.donationsCount} donations`
          : 'Connected to Irene API';
      case 'disconnected':
      case 'error':
        return 'Disconnected from Irene API';
      case 'connecting':
      default:
        return 'Checking connection...';
    }
  };

  const getConnectionColor = () => {
    switch (currentStatus) {
      case 'connected':
        return 'text-green-700';
      case 'disconnected':
      case 'error':
        return 'text-red-700';
      case 'connecting':
      default:
        return 'text-yellow-700';
    }
  };

  const getConnectionBgColor = () => {
    switch (currentStatus) {
      case 'connected':
        return 'bg-green-50 border-green-200';
      case 'disconnected':
      case 'error':
        return 'bg-red-50 border-red-200';
      case 'connecting':
      default:
        return 'bg-yellow-50 border-yellow-200';
    }
  };

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Left side - Application title */}
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            Irene Admin
          </h1>
          <p className="text-sm text-gray-500">
            Voice Assistant Administration Interface
          </p>
        </div>

        {/* Right side - Connection status */}
        <div className="flex items-center space-x-4">
          {/* Connection status indicator */}
          <div className="flex items-center space-x-2">
            <div className={`px-3 py-1.5 rounded-lg border ${getConnectionBgColor()}`}>
              <div className="flex items-center space-x-2">
                {getConnectionIcon()}
                <span className={`text-sm font-medium ${getConnectionColor()}`}>
                  {getConnectionText()}
                </span>
              </div>
            </div>
          </div>

          {/* Refresh button */}
          {!externalStatus && (
            <button
              onClick={checkConnection}
              disabled={isChecking || currentStatus === 'connecting'}
              className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh connection status"
            >
              <Wifi className={`w-3 h-3 mr-1 ${isChecking || currentStatus === 'connecting' ? 'animate-spin' : ''}`} />
              {isChecking ? 'Checking...' : 'Refresh'}
            </button>
          )}

          {/* Last check time */}
          {lastCheck && (
            <span className="text-xs text-gray-400">
              Last check: {lastCheck.toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      {/* Connection error banner */}
      {(currentStatus === 'disconnected' || currentStatus === 'error') && (
        <div className="mt-3 bg-red-50 border border-red-200 rounded-md p-3">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 mr-2 flex-shrink-0" />
            <div className="text-sm">
              <p className="text-red-800 font-medium">
                Cannot connect to Irene API
              </p>
              <p className="text-red-700 mt-1">
                Make sure the Irene Voice Assistant is running and accessible at{' '}
                <code className="bg-red-100 px-1 rounded text-xs">
                  {apiClient['baseUrl']}
                </code>
              </p>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;
