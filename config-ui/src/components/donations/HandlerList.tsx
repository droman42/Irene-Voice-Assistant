/**
 * HandlerList Component - Simplified navigation list for donation handlers
 * 
 * Displays donation handlers with basic status indicators, allows selection for editing.
 * Language selection is handled by the language tabs in the main editor area.
 */

import { useMemo } from 'react';
import { 
  AlertCircle, 
  CheckCircle2, 
  Search
} from 'lucide-react';
import Badge from '@/components/ui/Badge';
import type { HandlerLanguageListProps } from '@/types';

const HandlerList: React.FC<HandlerLanguageListProps> = ({ 
  handlers, 
  selectedHandler, 
  selectedLanguage: _selectedLanguage,
  onSelect, 
  onLanguageSelect: _onLanguageSelect,
  onCreateLanguage: _onCreateLanguage,
  onDeleteLanguage: _onDeleteLanguage,
  searchQuery,
  onSearchChange,
  filterLanguageCount,
  onFilterLanguageCountChange: _onFilterLanguageCountChange,
  hasChanges: _hasChanges = {}, 
  loading = false,
  error = null
}) => {

  // Simple filtering logic
  const filteredHandlers = useMemo(() => {
    return handlers.filter(handler => {
      // Text search
      const search = searchQuery.toLowerCase();
      if (search && !handler.handler_name.toLowerCase().includes(search)) {
        return false;
      }
      
      // Language count filter
      const languageCount = handler.languages.length;
      if (filterLanguageCount === 'single' && languageCount !== 1) return false;
      if (filterLanguageCount === 'multiple' && languageCount <= 1) return false;
      
      return true;
    });
  }, [handlers, searchQuery, filterLanguageCount]);

  const getStatusBadge = (handler: any) => {
    const availableLanguages = handler.languages.length;
    
    if (availableLanguages === 0) {
      return <Badge variant="error">No Languages</Badge>;
    }
    return <Badge variant="success">Available</Badge>;
  };

  const getStatusIcon = (handler: any) => {
    const availableLanguages = handler.languages.length;
    if (availableLanguages === 0) {
      return <AlertCircle className="w-4 h-4 text-red-500" />;
    }
    return <CheckCircle2 className="w-4 h-4 text-green-500" />;
  };

  if (loading) {
    return (
      <div className="w-80 bg-gray-50 border-r border-gray-200 flex items-center justify-center">
        <div className="text-gray-500">Loading handlers...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-80 bg-gray-50 border-r border-gray-200 p-4">
        <div className="text-red-600">
          <AlertCircle className="w-5 h-5 inline mr-2" />
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-gray-50 border-r border-gray-200 flex flex-col">
      {/* Search Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search handlers..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
      </div>

      {/* Handlers List */}
      <div className="flex-1 overflow-auto">
        {filteredHandlers.length === 0 ? (
          <div className="p-4 text-gray-500 text-center">
            {searchQuery ? 'No matching handlers' : 'No handlers available'}
          </div>
        ) : (
          <div className="space-y-1 p-2">
            {filteredHandlers.map((handler) => (
              <div key={handler.handler_name} className="space-y-1">
                {/* Handler Item */}
                <div
                  onClick={() => onSelect(handler.handler_name)}
                  className={`
                    flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors
                    ${selectedHandler === handler.handler_name
                      ? 'bg-blue-100 border border-blue-300 text-blue-900'
                      : 'bg-white border border-gray-200 hover:bg-gray-50'
                    }
                  `}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2">
                      {getStatusIcon(handler)}
                      <span className="font-medium truncate">{handler.handler_name}</span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end space-y-1">
                    {getStatusBadge(handler)}
                  </div>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="text-xs text-gray-500">
          {filteredHandlers.length} handlers
        </div>
      </div>
    </div>
  );
};

export default HandlerList;