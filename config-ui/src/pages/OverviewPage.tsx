/**
 * OverviewPage Component - System overview and status dashboard
 * 
 * Provides a high-level view of the Irene system status,
 * component health, and quick access to management tasks.
 */

import { useState, useEffect } from 'react';
import { 
  Activity, 
  FileText, 
  Settings, 
  AlertCircle, 
  CheckCircle2,
  Users,
  Database,
  Zap
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import apiClient from '@/utils/apiClient';
import type { IntentStatusResponse, IntentHandlersResponse } from '@/types';

interface SystemStatusData {
  intent: IntentStatusResponse;
  handlers: IntentHandlersResponse;
}

const OverviewPage: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadSystemStatus();
  }, []);

  const loadSystemStatus = async () => {
    try {
      setLoading(true);
      setError(null);

      const [statusResponse, handlersResponse] = await Promise.all([
        apiClient.getIntentStatus(),
        apiClient.getIntentHandlers()
      ]);

      setSystemStatus({
        intent: statusResponse,
        handlers: handlersResponse
      });
    } catch (err) {
      console.error('Failed to load system status:', err);
      setError(err instanceof Error ? err.message : 'Failed to load system status');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case 'healthy':
        return 'text-green-600';
      case 'warning':
        return 'text-yellow-600';
      case 'error':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const getStatusIcon = (status: string): React.ReactElement => {
    switch (status?.toLowerCase()) {
      case 'healthy':
        return <CheckCircle2 className="w-5 h-5 text-green-600" />;
      case 'warning':
        return <AlertCircle className="w-5 h-5 text-yellow-600" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-600" />;
      default:
        return <AlertCircle className="w-5 h-5 text-gray-600" />;
    }
  };

  const quickActions = [
    {
      title: 'Manage Donations',
      description: 'Edit intent handler donations and configurations',
      icon: FileText,
      path: '/donations',
      color: 'bg-blue-50 text-blue-700 border-blue-200'
    },
    {
      title: 'System Monitoring',
      description: 'View system health and performance metrics',
      icon: Activity,
      path: '/monitoring',
      color: 'bg-green-50 text-green-700 border-green-200'
    },
    {
      title: 'Configuration',
      description: 'System settings and configuration management',
      icon: Settings,
      path: '/configuration',
      color: 'bg-purple-50 text-purple-700 border-purple-200'
    }
  ];

  if (loading) {
    return (
      <div className="p-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded mb-4"></div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start">
            <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" />
            <div>
              <h3 className="text-red-800 font-medium">Failed to load system status</h3>
              <p className="text-red-700 text-sm mt-1">{error}</p>
              <button
                onClick={loadSystemStatus}
                className="mt-3 px-3 py-1 bg-red-100 text-red-800 rounded text-sm hover:bg-red-200 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">System Overview</h1>
        <p className="text-gray-600 mt-1">Monitor system health and manage components</p>
      </div>

      {/* System Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Intent System Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              {getStatusIcon(systemStatus?.intent?.status?.status || 'unknown')}
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Intent System</h3>
              <p className={`text-sm font-medium ${getStatusColor(systemStatus?.intent?.status?.status || 'unknown')}`}>
                {systemStatus?.intent?.status?.status || 'Unknown'}
              </p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {systemStatus?.intent?.handlers_count || 0}
              </p>
              <p className="text-xs text-gray-500">Handlers Loaded</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {systemStatus?.intent?.donations_count || 0}
              </p>
              <p className="text-xs text-gray-500">Donations Loaded</p>
            </div>
          </div>
        </div>

        {/* Handlers Status */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Users className="w-5 h-5 text-blue-600" />
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">Intent Handlers</h3>
              <p className="text-sm text-blue-600 font-medium">Active</p>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-2xl font-bold text-gray-900">
              {systemStatus?.handlers?.total_count || 0}
            </p>
            <p className="text-xs text-gray-500">Total Handlers</p>
          </div>
        </div>

        {/* System Info */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <Zap className="w-5 h-5 text-green-600" />
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-medium text-gray-900">System</h3>
              <p className="text-sm text-green-600 font-medium">
                {systemStatus?.intent?.system_info?.version || 'Unknown Version'}
              </p>
            </div>
          </div>
          <div className="mt-4">
            <p className="text-sm text-gray-600">
              Uptime: {systemStatus?.intent?.system_info?.uptime || 'Unknown'}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Last reload: {systemStatus?.intent?.last_reload ? 
                new Date(systemStatus.intent.last_reload).toLocaleString() : 'Never'}
            </p>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <button
                key={action.path}
                onClick={() => navigate(action.path)}
                className={`p-6 rounded-lg border text-left hover:shadow-md transition-all duration-200 ${action.color}`}
              >
                <div className="flex items-center mb-3">
                  <Icon className="w-6 h-6 mr-3" />
                  <h3 className="text-lg font-medium">{action.title}</h3>
                </div>
                <p className="text-sm opacity-80">{action.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Recent Activity Placeholder */}
      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Activity</h2>
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <div className="text-center py-8">
            <Database className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <h3 className="text-gray-900 font-medium mb-1">Activity Monitoring</h3>
            <p className="text-gray-500 text-sm">
              Activity tracking will be available in the monitoring dashboard
            </p>
            <button
              onClick={() => navigate('/monitoring')}
              className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
            >
              Go to Monitoring
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OverviewPage;
