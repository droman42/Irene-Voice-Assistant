/**
 * HandlerList Component - Navigation list for donation handlers
 * 
 * Displays a list of available donation handlers with metadata,
 * allows selection for editing, and shows change indicators.
 */

import { useState, useMemo } from 'react';
import { 
  FileText, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  Users,
  Hash,
  Circle,
  Sliders,
  Search,
  Filter
} from 'lucide-react';
import Badge from '@/components/ui/Badge';
import type { HandlerListProps } from '@/types';

const HandlerList: React.FC<HandlerListProps> = ({ 
  handlers, 
  selectedHandler, 
  onSelect, 
  searchQuery,
  onSearchChange,
  filterDomain,
  onFilterDomainChange,
  filterMethodCount,
  onFilterMethodCountChange,
  filterModified,
  onFilterModifiedChange,
  bulkSelection,
  onBulkSelectionChange,
  hasChanges = {}, 
  loading = false,
  error = null
}) => {
  const [showFilters, setShowFilters] = useState(false);

  // Get unique domains for filter
  const uniqueDomains = useMemo(() => {
    return Array.from(new Set(handlers.map(h => h.domain))).sort();
  }, [handlers]);

  // Advanced filtering logic
  const filteredHandlers = useMemo(() => {
    return handlers.filter(handler => {
      // Text search
      const search = searchQuery.toLowerCase();
      const matchesSearch = search === '' || 
        handler.handler_name.toLowerCase().includes(search) ||
        handler.domain.toLowerCase().includes(search) ||
        (handler.description && handler.description.toLowerCase().includes(search));
      
      // Filter by changes
      if (filterModified && !hasChanges[handler.handler_name]) {
        return false;
      }
      
      // Filter by domain
      if (filterDomain && handler.domain !== filterDomain) {
        return false;
      }
      
      // Filter by method count
      if (filterMethodCount) {
        const count = handler.methods_count;
        switch (filterMethodCount) {
          case 'none':
            if (count > 0) return false;
            break;
          case 'few':
            if (count < 1 || count > 3) return false;
            break;
          case 'many':
            if (count <= 3) return false;
            break;
        }
      }
      
      return matchesSearch;
    });
  }, [handlers, searchQuery, filterModified, filterDomain, filterMethodCount, hasChanges]);

  const getHandlerIcon = (handler: typeof handlers[0]) => {
    if (hasChanges[handler.handler_name]) {
      return <AlertCircle className="w-4 h-4 text-orange-500" />;
    }
    if (handler.methods_count === 0) {
      return <Circle className="w-4 h-4 text-gray-400" />;
    }
    return <CheckCircle2 className="w-4 h-4 text-green-500" />;
  };

  const getStatusBadge = (handler: typeof handlers[0]) => {
    if (hasChanges[handler.handler_name]) {
      return <Badge variant="warning">Modified</Badge>;
    }
    if (handler.methods_count === 0) {
      return <Badge variant="default">Empty</Badge>;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="w-80 border-r border-gray-200 bg-gray-50">
        <div className="p-4">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-gray-200 rounded"></div>
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-80 border-r border-gray-200 bg-gray-50">
        <div className="p-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-3">
            <div className="flex items-start">
              <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 mr-2 flex-shrink-0" />
              <div className="text-sm">
                <p className="text-red-800 font-medium">Failed to load handlers</p>
                <p className="text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 border-r border-gray-200 bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 p-4 bg-white">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Handlers</h2>
        
        {/* Search */}
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search handlers..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Filter toggle */}
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center justify-between w-full px-3 py-2 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-300 rounded-lg hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <div className="flex items-center">
            <Filter className="w-4 h-4 mr-2" />
            Filters
          </div>
          <Sliders className="w-4 h-4" />
        </button>

        {/* Filters */}
        {showFilters && (
          <div className="mt-3 space-y-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
            {/* Domain filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Domain</label>
              <select
                value={filterDomain}
                onChange={(e) => onFilterDomainChange(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">All domains</option>
                {uniqueDomains.map(domain => (
                  <option key={domain} value={domain}>{domain}</option>
                ))}
              </select>
            </div>

            {/* Method count filter */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Methods</label>
              <select
                value={filterMethodCount}
                onChange={(e) => onFilterMethodCountChange(e.target.value)}
                className="w-full text-sm border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Any count</option>
                <option value="none">No methods</option>
                <option value="few">1-3 methods</option>
                <option value="many">4+ methods</option>
              </select>
            </div>

            {/* Modified filter */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="filter-modified"
                checked={filterModified}
                onChange={(e) => onFilterModifiedChange(e.target.checked)}
                className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="filter-modified" className="ml-2 text-xs font-medium text-gray-700">
                Only modified
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Handlers list */}
      <div className="flex-1 overflow-auto">
        <div className="p-2">
          {filteredHandlers.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No handlers found</p>
            </div>
          ) : (
            <div className="space-y-1">
              {filteredHandlers.map((handler) => (
                <button
                  key={handler.handler_name}
                  onClick={() => onSelect(handler.handler_name)}
                  className={`w-full text-left p-3 rounded-lg border transition-all duration-150 hover:shadow-sm ${
                    selectedHandler === handler.handler_name
                      ? 'bg-blue-50 border-blue-200 shadow-sm'
                      : 'bg-white border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center space-x-2 min-w-0 flex-1">
                      {getHandlerIcon(handler)}
                      <span className="font-medium text-sm text-gray-900 truncate">
                        {handler.handler_name}
                      </span>
                    </div>
                    {getStatusBadge(handler)}
                  </div>
                  
                  <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                    {handler.description || 'No description'}
                  </p>
                  
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <div className="flex items-center space-x-3">
                      <div className="flex items-center space-x-1">
                        <Hash className="w-3 h-3" />
                        <span>{handler.domain}</span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <Users className="w-3 h-3" />
                        <span>{handler.methods_count}</span>
                      </div>
                    </div>
                    {handler.last_modified && (
                      <div className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(handler.last_modified * 1000).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer with stats */}
      <div className="border-t border-gray-200 p-3 bg-white">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>
            {filteredHandlers.length} of {handlers.length} handlers
          </span>
          {Object.values(hasChanges).filter(Boolean).length > 0 && (
            <span className="text-orange-600 font-medium">
              {Object.values(hasChanges).filter(Boolean).length} modified
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default HandlerList;
