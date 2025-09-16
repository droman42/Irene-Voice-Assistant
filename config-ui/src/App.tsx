/**
 * App.tsx - Main application component with React Router
 * 
 * Transformed from file-based donations editor to multi-page admin interface.
 * Uses React Router for navigation and Layout component for consistent structure.
 */

import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'

// Layout components
import Layout from '@/components/layout/Layout'

// Page components
import OverviewPage from '@/pages/OverviewPage'
import DonationsPage from '@/pages/DonationsPage'
import TemplatesPage from '@/pages/TemplatesPage'
import MonitoringPage from '@/pages/MonitoringPage'
import ConfigurationPage from '@/pages/ConfigurationPage'

const App: React.FC = () => {
  return (
    <Router 
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true
      }}
    >
      <Layout>
        <Routes>
          {/* Overview/Dashboard page */}
          <Route path="/" element={<OverviewPage />} />
          
          {/* Donations management */}
          <Route path="/donations" element={<DonationsPage />} />
          
          {/* Templates management */}
          <Route path="/templates" element={<TemplatesPage />} />
          
          {/* Monitoring dashboard */}
          <Route path="/monitoring" element={<MonitoringPage />} />
          
          {/* Configuration editor */}
          <Route path="/configuration" element={<ConfigurationPage />} />
          
          {/* Catch-all route - redirect to overview */}
          <Route path="*" element={<OverviewPage />} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App;
