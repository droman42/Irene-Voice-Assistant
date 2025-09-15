/**
 * Layout Component - Main application layout wrapper
 * 
 * Provides the overall layout structure with sidebar navigation,
 * header, and main content area. Handles responsive behavior
 * and layout state management.
 */

import { useState } from 'react';
import Sidebar from './Sidebar';
import Header from './Header';
import type { LayoutProps } from '@/types';

const Layout = ({ children }: LayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <Sidebar 
        collapsed={sidebarCollapsed} 
        onToggle={setSidebarCollapsed} 
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <Header />

        {/* Main content */}
        <main className="flex-1 overflow-auto">
          <div className="h-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;
