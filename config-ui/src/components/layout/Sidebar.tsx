/**
 * Sidebar Component - Collapsible navigation sidebar
 * 
 * Provides navigation between different sections of the admin interface
 * with support for collapsing to save space.
 */

import { useNavigate, useLocation } from 'react-router-dom';
import { 
  ChevronLeft, 
  ChevronRight, 
  Home, 
  FileText, 
  Code,
  Activity, 
  Settings,
  Menu,
  LucideIcon,
  MessageSquare
} from 'lucide-react';
import type { SidebarProps } from '@/types';

interface NavigationSection {
  id: string;
  title: string;
  icon: LucideIcon;
  path: string;
  description: string;
}

// Navigation sections configuration
const navigationSections: NavigationSection[] = [
  {
    id: 'overview',
    title: 'Overview',
    icon: Home,
    path: '/',
    description: 'System overview and status'
  },
  {
    id: 'donations',
    title: 'Donations',
    icon: FileText,
    path: '/donations',
    description: 'Edit intent handler donations'
  },
  {
    id: 'templates',
    title: 'Templates',
    icon: Code,
    path: '/templates',
    description: 'Edit response templates'
  },
  {
    id: 'prompts',
    title: 'Prompts',
    icon: MessageSquare,
    path: '/prompts',
    description: 'Edit LLM prompts'
  },
  {
    id: 'monitoring',
    title: 'Monitoring',
    icon: Activity,
    path: '/monitoring',
    description: 'System monitoring and metrics'
  },
  {
    id: 'configuration',
    title: 'Configuration',
    icon: Settings,
    path: '/configuration',
    description: 'System configuration management'
  }
];

const Sidebar = ({ collapsed, onToggle }: SidebarProps) => {
  const navigate = useNavigate();
  const location = useLocation();

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  const isActivePath = (path: string): boolean => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className={`bg-gray-900 text-white transition-all duration-300 flex flex-col ${
      collapsed ? 'w-16' : 'w-64'
    }`}>
      {/* Header with toggle */}
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        {!collapsed && (
          <div>
            <h2 className="text-lg font-semibold">Navigation</h2>
            <p className="text-xs text-gray-300 mt-0.5">Admin Interface</p>
          </div>
        )}
        <button
          onClick={() => onToggle(!collapsed)}
          className="p-2 rounded-lg hover:bg-gray-800 transition-colors"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Navigation menu */}
      <nav className="flex-1 mt-6" role="navigation">
        <div className="px-2 space-y-1">
          {navigationSections.map((section) => {
            const Icon = section.icon;
            const isActive = isActivePath(section.path);
            
            return (
              <button
                key={section.id}
                onClick={() => handleNavigation(section.path)}
                className={`w-full flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-colors group ${
                  isActive
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`}
                title={collapsed ? section.description : ''}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="w-5 h-5 flex-shrink-0" />
                {!collapsed && (
                  <>
                    <span className="ml-3">{section.title}</span>
                    {isActive && (
                      <div 
                        className="ml-auto w-2 h-2 bg-blue-400 rounded-full"
                        aria-hidden="true"
                      />
                    )}
                  </>
                )}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Footer with version info */}
      {!collapsed && (
        <div className="p-4 border-t border-gray-700">
          <div className="text-xs text-gray-400">
            <p className="font-medium">Irene Admin v1.0.0</p>
            <p className="mt-1">Voice Assistant Management</p>
          </div>
        </div>
      )}

      {/* Collapsed footer */}
      {collapsed && (
        <div className="p-4 border-t border-gray-700 flex justify-center">
          <Menu className="w-4 h-4 text-gray-400" />
        </div>
      )}
    </div>
  );
};

export default Sidebar;
