# NLU System Improvements: Real-time Quality Assurance Integration

## Situation

The Irene Voice Assistant's NLU (Natural Language Understanding) system currently faces several critical quality and usability challenges that impact both runtime performance and developer productivity:

### Current System State
- **Two NLU Providers**: HybridKeywordMatcher (primary) and SpaCyNLUProvider (secondary)
- **Donation-based Intent Definition**: JSON files defining phrases, lemmas, examples, and parameters
- **Config-UI Integration**: Existing donation editor with language-aware editing capabilities
- **Multi-language Support**: Russian and English with independent processing pipelines

### Identified Pain Points

**1. Runtime Performance Issues**
- **Keyword Collisions**: Global keyword map allows later intents to overwrite earlier ones, causing silent bias
- **Regex Explosion**: Partial-pattern generation creates combinatorially expensive alternations
- **Scale Mismatches**: Inconsistent 0-100 vs 0-1 scoring scales create brittle threshold logic
- **Language Mixing**: Single global keyword pool doesn't partition by language

**2. Quality Assurance Gaps**
- **No Conflict Detection**: Users can create overlapping intents that steal matches from each other
- **Scope Creep**: Intents accumulate phrases belonging to other domains (e.g., "set alarm" in timer.set)
- **Cross-language Inconsistencies**: RU/EN donations can drift apart without validation
- **Limited Debugging**: Difficult to understand why certain phrases match or don't match

**3. Developer Experience Limitations**
- **No Real-time Feedback**: Conflicts only discovered during runtime testing
- **Manual Quality Control**: No automated tools to catch donation quality issues
- **CI/CD Gaps**: No automated validation of donation changes in pull requests
- **Limited Provider Visibility**: Hard to understand which provider logic is being triggered

## Complication

These issues create a cascading set of problems that will worsen as the system scales:

### Immediate Impact
- **Unpredictable Intent Recognition**: Keyword collisions cause non-deterministic behavior
- **Performance Degradation**: Regex explosion slows down recognition for complex phrases
- **Maintenance Overhead**: Manual debugging of intent conflicts is time-intensive

### Long-term Risks
- **Scale Limitations**: Adding new domains becomes increasingly risky due to cross-domain conflicts
- **Quality Regression**: No systematic way to prevent quality degradation over time
- **Developer Friction**: Poor tooling discourages contribution and experimentation

### Architectural Constraints
- **Provider Interdependence**: Fixing one provider without the other creates analysis gaps
- **UI Integration Complexity**: Current config-ui lacks real-time analysis capabilities
- **CI Integration Requirements**: Quality gates needed for automated donation validation

## Question

How can we systematically improve NLU quality, performance, and developer experience through integrated real-time analysis while maintaining the existing donation-driven architecture and config-ui workflow?

## Answer

Implement a comprehensive **Real-time NLU Quality Assurance System** that integrates directly into the backend runtime and config-ui, providing immediate feedback during donation editing while maintaining CI/CD validation capabilities.

## Solution Architecture

### Core Components

**1. Backend NLU Analysis Service**
- **Real-time Contradiction Detection**: Analyze donations as they're edited
- **Provider-faithful Analysis**: Mirror exact HybridKeywordMatcher and SpaCy logic
- **Language-aware Processing**: Independent RU/EN analysis pipelines
- **Conflict Scoring**: Quantitative assessment of intent overlaps and scope creep

**2. Enhanced Config-UI Integration** 
- **Live Conflict Indicators**: Real-time visual feedback during editing
- **Validation Gates**: Block problematic saves with clear explanations
- **Analysis Dashboard**: Comprehensive system health overview
- **Guided Resolution**: Smart suggestions for conflict resolution

**3. Provider Performance Improvements**
- **Collision-free Keyword Mapping**: Store keyword → {intents} relationships
- **Language Partitioning**: Separate RU/EN processing pipelines
- **Optimized Pattern Matching**: Replace regex explosion with token counting
- **Consistent Scoring**: Unified 0-1 scale across all components

**4. CI/CD Integration**
- **API-driven Validation**: Lightweight CLI wrapper calling backend analysis
- **Automated Quality Gates**: Block merges with blocking conflicts
- **Quality Metrics**: Track improvement/regression over time

### Key Benefits

**Immediate Value**
- Real-time conflict detection prevents issues at edit-time
- Performance improvements reduce recognition latency
- Enhanced debugging visibility accelerates development

**Long-term Value**
- Systematic quality assurance enables confident scaling
- Automated validation reduces maintenance overhead
- Integrated tooling improves developer experience

## Implementation Plan

### Phase 1: Provider Performance & Reliability Foundation
**Duration: 2-3 weeks | Goal: Fix critical runtime issues**

#### 1.1 HybridKeywordMatcher Critical Fixes
**Files to modify:**
- `irene/providers/nlu/hybrid_keyword_matcher.py`

**Changes:**
```python
# Fix keyword collisions
self.global_keyword_map: Dict[str, Set[str]] = {}  # keyword → {intents}

# Language partitioning
self.global_keyword_map_ru: Dict[str, Set[str]] = {}
self.global_keyword_map_en: Dict[str, Set[str]] = {}
self.fuzzy_keywords_ru: List[str] = []
self.fuzzy_keywords_en: List[str] = []

# Improved normalization
def _normalize_text(self, text: str) -> str:
    import unicodedata
    text = unicodedata.normalize('NFKD', text.casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))

# Token-based partial matching (replace regex explosion)
def _check_partial_match(self, input_tokens: List[str], phrase_tokens: List[str]) -> bool:
    required_hits = math.ceil(0.7 * len(phrase_tokens))
    hits = sum(1 for token in phrase_tokens if token in input_tokens)
    return hits >= required_hits
```

**Testing:**
- Unit tests for keyword collision resolution
- Performance benchmarks for partial matching
- Language detection accuracy tests
- Stress tests with large donation sets

#### 1.2 SpaCy Provider Language Awareness
**Files to modify:**
- `irene/providers/nlu/spacy_provider.py`

**Changes:**
```python
# Multi-model management
self.available_models: Dict[str, spacy.Language] = {}
language_preferences = {
    'ru': ['ru_core_news_md', 'ru_core_news_sm'],
    'en': ['en_core_web_md', 'en_core_web_sm']
}

# Language routing
def _detect_language(self, text: str) -> str:
    # Cyrillic script detection for Russian
    if any('\u0400' <= char <= '\u04FF' for char in text):
        return 'ru'
    return 'en'

# Runtime language rejection
async def recognize(self, text: str, context: ConversationContext) -> Intent:
    detected_lang = self._detect_language(text)
    if detected_lang not in self.available_models:
        return Intent(name="conversation.general", confidence=0.6, ...)
```

**Testing:**
- Model availability tests for different environments
- Language detection accuracy benchmarks
- Fallback behavior validation
- Performance impact measurement

#### 1.3 Scoring Scale Consistency
**Files to modify:**
- Both provider implementations
- Configuration schemas

**Changes:**
- Normalize all scores to 0-1 range
- Add configuration validation for score thresholds
- Update documentation for consistent scoring

**Testing:**
- Cross-provider scoring consistency tests
- Configuration validation tests
- Threshold behavior verification

**Phase 1 Success Criteria:**
- [x] Zero keyword collisions in provider logic
- [x] Language-specific processing pipelines working
- [x] Performance benchmarks show improvement
- [x] All existing functionality preserved
- [x] Comprehensive test coverage for changes

**Phase 1 Implementation Summary:**

*HybridKeywordMatcher Improvements:*
- ✅ Fixed keyword collisions by using `Dict[str, Set[str]]` instead of `Dict[str, str]`
- ✅ Implemented language partitioning with separate RU/EN keyword maps
- ✅ Added improved Unicode normalization with combining character removal
- ✅ Replaced regex explosion in partial matching with token-based counting
- ✅ Added comprehensive configuration validation
- ✅ Normalized confidence threshold default to 0.7 for consistency

*SpaCy Provider Improvements:*
- ✅ Implemented multi-model management with language-specific model preferences
- ✅ Added Cyrillic script-based language detection
- ✅ Implemented runtime language rejection for unsupported languages
- ✅ Enhanced model loading with graceful fallback chains
- ✅ Updated asset configuration and Python dependencies for multi-model support
- ✅ Maintained backward compatibility with legacy configuration

*Cross-Provider Consistency:*
- ✅ Normalized all scoring to 0-1 range across both providers
- ✅ Implemented consistent language detection logic
- ✅ Added configuration validation for both providers
- ✅ Unified confidence threshold defaults to 0.7

*Configuration & Infrastructure:*
- ✅ Updated parameter schemas to reflect Phase 1 changes in both providers
- ✅ Modified config-master.toml with new multi-model and enhanced parameters
- ✅ Verified configuration UI compatibility with nested object support
- ✅ Updated pyproject.toml with all 4 multi-language SpaCy models for installation
- ✅ Aligned provider dependencies with actual installation requirements

*Testing & Quality Assurance:*
- ✅ Created comprehensive test suite with 60+ test cases
- ✅ Added performance benchmarks and stress tests
- ✅ Implemented cross-provider consistency verification
- ✅ Validated memory efficiency with large datasets

---

### Phase 2: Backend Analysis Service Foundation
**Duration: 3-4 weeks | Goal: Real-time analysis capabilities**

#### 2.1 NLU Analysis Component
**New files to create:**
```
irene/components/nlu_analysis_component.py
irene/analysis/
├── __init__.py
├── base.py                    # Analysis interfaces
├── hybrid_analyzer.py         # Mirror HybridKeywordMatcher logic
├── spacy_analyzer.py         # Mirror SpaCy provider logic
├── conflict_detector.py      # Overlap detection algorithms
├── scope_analyzer.py         # Scope creep detection
└── report_generator.py       # Analysis result formatting
```

**Core Analysis Logic:**
```python
class NLUAnalysisComponent(Component):
    async def analyze_donation_realtime(
        self, 
        handler_name: str, 
        language: str, 
        donation_data: DonationData
    ) -> AnalysisResult:
        """Real-time analysis of single donation"""
        
    async def analyze_changes_impact(
        self, 
        changes: Dict[str, DonationData]
    ) -> ChangeImpactAnalysis:
        """Analyze impact of proposed changes across system"""
        
    async def validate_before_save(
        self, 
        handler_name: str, 
        language: str, 
        donation_data: DonationData
    ) -> ValidationResult:
        """Pre-save validation with blocking/warning classification"""
        
    async def run_batch_analysis(self) -> BatchAnalysisResult:
        """Full system analysis for reporting/CI"""
```

**Analysis Algorithms:**
```python
class ConflictDetector:
    def detect_phrase_overlap(self, intent_a: IntentUnit, intent_b: IntentUnit) -> OverlapScore:
        """Jaccard similarity + token F1 for phrase overlap"""
        
    def detect_keyword_collisions(self, units: List[IntentUnit]) -> List[KeywordCollision]:
        """Mirror hybrid provider's keyword mapping logic"""
        
    def detect_pattern_crosshits(self, intent_a: IntentUnit, intent_b: IntentUnit) -> List[CrossHit]:
        """Test flexible/partial patterns against rival phrases"""
        
    def calculate_ambiguity_score(self, conflicts: List[Conflict]) -> float:
        """Weighted scoring: 0.4*surface + 0.3*hybrid + 0.3*spacy"""

class ScopeAnalyzer:
    def detect_cross_domain_attraction(self, intent: IntentUnit, corpus: List[IntentUnit]) -> List[ScopeIssue]:
        """Find phrases that belong to other domains"""
        
    def analyze_pattern_breadth(self, intent: IntentUnit) -> BreadthAnalysis:
        """Detect overly broad patterns that steal traffic"""
```

**Testing:**
- Mirror existing provider test cases
- Verify analysis accuracy against known conflicts  
- Performance benchmarks for real-time analysis
- Edge case handling (empty donations, malformed data)

#### 2.2 Web API Integration  
**New file:**
- `irene/web_api/nlu_analysis_router.py`

**API Endpoints:**
```python
@router.post("/nlu/analyze/donation")
async def analyze_donation(request: AnalyzeDonationRequest) -> AnalysisResult:
    """Real-time analysis endpoint for config-ui"""

@router.post("/nlu/analyze/changes") 
async def analyze_changes(
    request: AnalyzeChangesRequest,
    language: Optional[str] = None  # ru, en, or None for all
) -> ChangeImpactAnalysis:
    """Impact analysis for multiple changes with optional language scoping"""

@router.post("/nlu/validate/save")
async def validate_before_save(request: ValidateRequest) -> ValidationResult:
    """Pre-save validation with severity classification"""

@router.get("/nlu/conflicts/{handler_name}")
async def get_handler_conflicts(
    handler_name: str,
    language: Optional[str] = None  # ru, en, or None for all
) -> List[ConflictReport]:
    """Get existing conflicts for specific handler with optional language filtering"""

@router.get("/nlu/analysis/batch")
async def run_batch_analysis(
    language: Optional[str] = None  # ru, en, or None for all
) -> BatchAnalysisResult:
    """Full system analysis for dashboard/CI with optional language scoping"""

@router.get("/nlu/health")
async def get_system_health() -> SystemHealthReport:
    """Overall NLU system health metrics"""
```

**Language Parameter Validation:**
```python
def validate_language_param(language: Optional[str]) -> Optional[str]:
    """Validate and normalize language parameter for API endpoints"""
    if language is None:
        return None
    if language not in ['ru', 'en']:
        raise HTTPException(400, f"Unsupported language: {language}")
    return language

# Applied in all endpoints with language filtering
@router.get("/nlu/conflicts/{handler_name}")
async def get_handler_conflicts(
    handler_name: str,
    language: Optional[str] = None
) -> List[ConflictReport]:
    validated_language = validate_language_param(language)
    conflicts = await analysis_component.get_handler_conflicts(handler_name)
    
    if validated_language:
        conflicts = [c for c in conflicts if c.language == validated_language]
    
    return conflicts
```

**Testing:**
- API endpoint integration tests
- Response schema validation
- Error handling and edge cases
- Performance under load
- Language parameter validation tests
- Server-side filtering accuracy tests

#### 2.3 Data Models & Schemas
**New files:**
```
irene/analysis/models.py       # Analysis result models
irene/api/schemas.py          # API request/response schemas  
```

**API Design Benefits:**
The consistent language parameter design provides several advantages:
- **Reduced payload sizes**: Language-scoped requests eliminate unnecessary data transfer
- **Improved caching**: Server can cache language-specific result sets efficiently  
- **Better UX**: UI components can request precisely the data they need
- **Backwards compatibility**: Optional language parameters maintain existing behavior when unspecified

**Key Data Structures:**
```python
@dataclass
class ConflictReport:
    intent_a: str
    intent_b: str
    language: str
    severity: Literal['blocker', 'warning', 'info']
    score: float
    conflict_type: str
    signals: Dict[str, Any]
    suggestions: List[str]

@dataclass 
class ValidationResult:
    is_valid: bool
    has_blocking_conflicts: bool
    has_warnings: bool
    conflicts: List[ConflictReport]
    suggestions: List[str]

@dataclass
class AnalysisResult:
    conflicts: List[ConflictReport]
    scope_issues: List[ScopeIssue]
    performance_metrics: Dict[str, float]
    language_coverage: Dict[str, float]
```

**Testing:**
- Schema validation tests
- Serialization/deserialization tests
- Type safety verification

**Phase 2 Success Criteria:**
- [ ] Analysis service running and integrated with web API
- [ ] Real-time analysis completing within 200ms for typical donations
- [ ] Analysis results mirror actual provider behavior
- [ ] Comprehensive conflict detection across all categories
- [ ] API endpoints tested and documented
- [ ] Consistent language parameter handling across all endpoints
- [ ] Server-side language filtering operational and tested

---

### Phase 3: Enhanced Config-UI Integration
**Duration: 2-3 weeks | Goal: Real-time user feedback**

#### 3.1 Real-time Conflict Detection
**Files to modify:**
- `config-ui/src/pages/DonationsPage.tsx`
- `config-ui/src/components/donations/LanguageTabs.tsx`

**Enhanced Donation Editor:**
```typescript
// Add real-time analysis hook
const useRealtimeAnalysis = (handlerName: string, language: string, donation: DonationData) => {
  const [conflicts, setConflicts] = useState<ConflictReport[]>([]);
  const [analysisStatus, setAnalysisStatus] = useState<'idle' | 'analyzing' | 'complete'>('idle');
  
  const debouncedAnalyze = useMemo(
    () => debounce(async (donationData: DonationData) => {
      setAnalysisStatus('analyzing');
      try {
        const result = await apiClient.analyzeDonation(handlerName, language, donationData);
        setConflicts(result.conflicts);
        setAnalysisStatus('complete');
      } catch (error) {
        console.error('Analysis failed:', error);
        setAnalysisStatus('idle');
      }
    }, 500),
    [handlerName, language]
  );
  
  return { conflicts, analysisStatus, analyzeNow: debouncedAnalyze };
};

// Enhanced editor with conflict indicators
const DonationEditor: React.FC<DonationEditorProps> = ({ donation, onChange }) => {
  const { conflicts, analysisStatus } = useRealtimeAnalysis(handlerName, language, donation);
  
  return (
    <div className="donation-editor">
      <ConflictStatusBar conflicts={conflicts} status={analysisStatus} />
      
      <PhrasesEditor 
        phrases={donation.phrases}
        conflicts={conflicts.filter(c => c.conflict_type === 'phrase_overlap')}
        onChange={(phrases) => onChange({...donation, phrases})}
      />
      
      <LemmasEditor
        lemmas={donation.lemmas}  
        conflicts={conflicts.filter(c => c.conflict_type === 'lemma_overlap')}
        onChange={(lemmas) => onChange({...donation, lemmas})}
      />
      
      <ConflictSuggestionPanel conflicts={conflicts} onApplySuggestion={handleApplySuggestion} />
    </div>
  );
};
```

**Testing:**
- Real-time analysis integration tests
- Debouncing behavior verification
- Conflict display accuracy
- Performance under rapid editing

#### 3.2 Enhanced Validation Workflow
**Files to modify:**
- `config-ui/src/components/common/ApplyChangesBar.tsx`

**Smart Validation Gates:**
```typescript
const ApplyChangesBar: React.FC<ApplyChangesBarProps> = ({ hasChanges, onApply }) => {
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [showingConflicts, setShowingConflicts] = useState(false);
  
  const validateChanges = async () => {
    const result = await apiClient.validateBeforeSave(handlerName, language, donationData);
    setValidationResult(result);
    return result;
  };
  
  const handleApply = async () => {
    const validation = await validateChanges();
    
    if (validation.has_blocking_conflicts) {
      setShowingConflicts(true);
      return; // Block save
    }
    
    if (validation.has_warnings) {
      const proceed = await showWarningDialog(validation.conflicts);
      if (!proceed) return;
    }
    
    await onApply();
  };
  
  return (
    <div className="apply-changes-bar">
      <ValidationIndicator result={validationResult} />
      <button onClick={validateChanges}>Validate</button>
      <button 
        onClick={handleApply}
        disabled={validationResult?.has_blocking_conflicts}
        className={validationResult?.has_warnings ? 'warning' : ''}
      >
        Apply Changes
      </button>
      
      {showingConflicts && (
        <BlockingConflictsDialog 
          conflicts={validationResult.conflicts}
          onResolve={handleResolveConflict}
          onClose={() => setShowingConflicts(false)}
        />
      )}
    </div>
  );
};
```

**Testing:**
- Validation workflow tests
- Blocking conflict prevention
- Warning confirmation flow
- Dialog interaction tests

#### 3.3 Visual Conflict Indicators
**New components to create:**
```
config-ui/src/components/analysis/
├── ConflictStatusBar.tsx      # Real-time status indicator
├── ConflictBadge.tsx         # Inline conflict markers
├── ConflictTooltip.tsx       # Detailed conflict information
├── SuggestionPanel.tsx       # Smart fix suggestions
└── ValidationIndicator.tsx   # Validation status display
```

**Conflict Visualization:**
```typescript
const ConflictBadge: React.FC<{conflict: ConflictReport}> = ({ conflict }) => {
  const severityColors = {
    blocker: 'bg-red-100 text-red-800 border-red-300',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-300', 
    info: 'bg-blue-100 text-blue-800 border-blue-300'
  };
  
  return (
    <Tooltip content={<ConflictTooltip conflict={conflict} />}>
      <Badge className={`${severityColors[conflict.severity]} cursor-help`}>
        {conflict.severity === 'blocker' && <AlertCircle className="w-3 h-3 mr-1" />}
        {conflict.conflict_type.replace('_', ' ')}
      </Badge>
    </Tooltip>
  );
};

const PhrasesEditor: React.FC<PhrasesEditorProps> = ({ phrases, conflicts, onChange }) => {
  return (
    <div className="phrases-editor">
      {phrases.map((phrase, index) => {
        const phraseConflicts = conflicts.filter(c => 
          c.signals.shared_phrases?.includes(phrase)
        );
        
        return (
          <div key={index} className="phrase-item">
            <Input 
              value={phrase}
              onChange={(value) => updatePhrase(index, value)}
              className={phraseConflicts.length > 0 ? 'border-red-300' : ''}
            />
            {phraseConflicts.map(conflict => (
              <ConflictBadge key={conflict.intent_b} conflict={conflict} />
            ))}
          </div>
        );
      })}
    </div>
  );
};
```

**Testing:**
- Visual indicator accuracy
- Tooltip interaction tests
- Badge color/severity mapping
- Accessibility compliance

#### 3.4 API Client Enhancement
**Files to modify:**
- `config-ui/src/utils/apiClient.ts`
- `config-ui/src/types/api.ts`

**New API Methods:**
```typescript
class ApiClient {
  async analyzeDonation(
    handlerName: string, 
    language: string, 
    donation: DonationData
  ): Promise<AnalysisResult> {
    return this.post('/nlu/analyze/donation', { handlerName, language, donation });
  }
  
  async validateBeforeSave(
    handlerName: string,
    language: string, 
    donation: DonationData
  ): Promise<ValidationResult> {
    return this.post('/nlu/validate/save', { handlerName, language, donation });
  }
  
  async getHandlerConflicts(
    handlerName: string, 
    language?: string
  ): Promise<ConflictReport[]> {
    const params = language ? `?language=${language}` : '';
    return this.get(`/nlu/conflicts/${handlerName}${params}`);
  }
  
  async runBatchAnalysis(language?: string): Promise<BatchAnalysisResult> {
    const params = language ? `?language=${language}` : '';
    return this.get(`/nlu/analysis/batch${params}`);
  }
  
  async analyzeChanges(
    changes: AnalyzeChangesRequest,
    language?: string
  ): Promise<ChangeImpactAnalysis> {
    const params = language ? `?language=${language}` : '';
    return this.post(`/nlu/analyze/changes${params}`, changes);
  }
}
```

**Enhanced Type Definitions:**
```typescript
interface AnalysisResult {
  conflicts: ConflictReport[];
  scope_issues: ScopeIssue[];
  performance_metrics: Record<string, number>;
  language_coverage: Record<string, number>;
}

interface ConflictReport {
  intent_a: string;
  intent_b: string;
  language: string;
  severity: 'blocker' | 'warning' | 'info';
  score: number;
  conflict_type: string;
  signals: Record<string, any>;
  suggestions: string[];
}

interface ValidationResult {
  is_valid: boolean;
  has_blocking_conflicts: boolean;
  has_warnings: boolean;
  conflicts: ConflictReport[];
  suggestions: string[];
}
```

**Testing:**
- API method integration tests
- Type safety verification
- Error handling tests
- Response schema validation

**Phase 3 Success Criteria:**
- [ ] Real-time conflict detection working in donation editor
- [ ] Validation gates preventing problematic saves
- [ ] Visual conflict indicators showing appropriate severity
- [ ] Smooth user experience with responsive analysis
- [ ] Comprehensive testing coverage for UI components

---

### Phase 4: Analysis Dashboard & Advanced Features  
**Duration: 3-4 weeks | Goal: Comprehensive system analysis**

#### 4.1 NLU Analysis Dashboard
**New page to create:**
- `config-ui/src/pages/NLUAnalysisPage.tsx`

**Dashboard Components:**
```typescript
const NLUAnalysisPage: React.FC = () => {
  const [batchAnalysis, setBatchAnalysis] = useState<BatchAnalysisResult | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [currentLanguage, setCurrentLanguage] = useState<string>('all');
  const [filters, setFilters] = useState<AnalysisFilters>({
    severity: ['blocker', 'warning'],
    conflictType: 'all'
  });

  // Language-scoped API calls for better performance
  const runFullAnalysis = async () => {
    setIsRunning(true);
    const result = await apiClient.runBatchAnalysis(
      currentLanguage === 'all' ? undefined : currentLanguage
    );
    setBatchAnalysis(result);
    setIsRunning(false);
  };

  return (
    <div className="nlu-analysis-page">
      <DashboardHeader 
        onRunAnalysis={runFullAnalysis}
        isRunning={isRunning}
        lastRun={batchAnalysis?.timestamp}
      />
      
      <SystemHealthOverview analysis={batchAnalysis} />
      
      <ConflictSummaryGrid 
        conflicts={batchAnalysis?.conflicts}
        filters={filters}
        onFilterChange={setFilters}
      />
      
      <DetailedConflictsList 
        conflicts={filteredConflicts}
        onResolveConflict={handleResolveConflict}
        onNavigateToEditor={handleNavigateToEditor}
      />
      
      <ScopeCreepAnalysis 
        scopeIssues={batchAnalysis?.scope_issues}
        onFixScopeIssue={handleFixScopeIssue}
      />
      
      <PerformanceMetrics metrics={batchAnalysis?.performance_metrics} />
    </div>
  );
};
```

**System Health Widgets:**
```typescript
const SystemHealthOverview: React.FC<{analysis: BatchAnalysisResult}> = ({ analysis }) => {
  const healthScore = calculateHealthScore(analysis);
  
  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      <HealthScoreCard score={healthScore} />
      <ConflictCountCard conflicts={analysis?.conflicts} />
      <LanguageCoverageCard coverage={analysis?.language_coverage} />
      <PerformanceCard metrics={analysis?.performance_metrics} />
    </div>
  );
};

const ConflictSummaryGrid: React.FC = ({ conflicts, filters, onFilterChange }) => {
  const groupedConflicts = useMemo(() => 
    groupConflictsBySeverityAndType(conflicts, filters), [conflicts, filters]
  );
  
  return (
    <div className="conflict-summary">
      <FilterBar filters={filters} onChange={onFilterChange} />
      <ConflictMatrix data={groupedConflicts} />
      <TrendChart conflicts={conflicts} />
    </div>
  );
};
```

**Testing:**
- Dashboard component rendering tests
- Data visualization accuracy
- Filter functionality tests
- Performance with large datasets

#### 4.2 Guided Conflict Resolution
**New components:**
```
config-ui/src/components/analysis/resolution/
├── ConflictResolutionWizard.tsx
├── SuggestionApplicator.tsx  
├── ResolutionPreview.tsx
└── BatchResolutionDialog.tsx
```

**Smart Resolution Workflows:**
```typescript
const ConflictResolutionWizard: React.FC<{conflict: ConflictReport}> = ({ conflict }) => {
  const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<ResolutionPreview | null>(null);
  
  const applySuggestion = async (suggestion: string) => {
    const preview = await apiClient.previewResolution(conflict, suggestion);
    setPreviewResult(preview);
  };
  
  const confirmResolution = async () => {
    if (!selectedSuggestion) return;
    
    await apiClient.applyResolution(conflict, selectedSuggestion);
    // Refresh analysis and navigate back to editor
  };
  
  return (
    <Dialog className="conflict-resolution-wizard">
      <ConflictSummary conflict={conflict} />
      
      <SuggestionList 
        suggestions={conflict.suggestions}
        selected={selectedSuggestion}
        onSelect={setSelectedSuggestion}
        onPreview={applySuggestion}
      />
      
      {previewResult && (
        <ResolutionPreview 
          preview={previewResult}
          onConfirm={confirmResolution}
          onCancel={() => setPreviewResult(null)}
        />
      )}
    </Dialog>
  );
};
```

**Testing:**
- Resolution wizard workflow tests
- Suggestion application accuracy  
- Preview functionality verification
- Undo/rollback capability tests

#### 4.3 Navigation Integration
**Files to modify:**
- `config-ui/src/components/layout/Sidebar.tsx`
- `config-ui/src/App.tsx`

**Add NLU Analysis to Navigation:**
```typescript
const navigationSections = [
  // ... existing sections
  {
    id: 'nlu-analysis',
    title: 'NLU Analysis', 
    icon: GitBranch,
    path: '/nlu-analysis',
    badge: conflictCount > 0 ? conflictCount : undefined
  }
];
```

**Testing:**
- Navigation integration tests
- Badge notification accuracy
- Route handling verification

#### 4.4 Advanced Analysis Features
**Enhanced Analysis Capabilities:**

1. **Historical Tracking**
   ```typescript
   // Track analysis results over time
   interface AnalysisHistory {
     timestamp: Date;
     conflicts_count: number;
     health_score: number;
     changes: ChangeRecord[];
   }
   ```

2. **Impact Analysis**
   ```typescript
   // Analyze impact of proposed changes
   const analyzeChangeImpact = async (changes: DonationChanges) => {
     return apiClient.analyzeChangesImpact(changes);
   };
   ```

3. **Bulk Operations**
   ```typescript
   // Bulk conflict resolution
   const resolveBulkConflicts = async (resolutions: BulkResolution[]) => {
     return apiClient.applyBulkResolutions(resolutions);
   };
   ```

**Testing:**
- Historical data accuracy
- Impact analysis precision
- Bulk operation reliability

**Phase 4 Success Criteria:**
- [ ] Comprehensive analysis dashboard operational
- [ ] Guided conflict resolution workflows functional
- [ ] Advanced analysis features working
- [ ] Navigation integration seamless
- [ ] Performance acceptable with large datasets

---

### Phase 5: CI/CD Integration & Production Hardening
**Duration: 1-2 weeks | Goal: Automated quality gates**

#### 5.1 CI/CD CLI Wrapper
**New file to create:**
- `irene/tools/nlu_ci_check.py`

**Lightweight CLI for CI:**
```python
#!/usr/bin/env python3
"""
NLU CI Validation Tool

Lightweight wrapper around backend analysis API for CI/CD integration.
Calls the running Irene backend to perform analysis and returns appropriate exit codes.
"""

import asyncio
import sys
import json
import argparse
from typing import Optional
import aiohttp

async def run_ci_analysis(base_url: str, timeout: int = 300) -> int:
    """Run batch analysis via API and return exit code"""
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        try:
            # Health check first
            async with session.get(f"{base_url}/nlu/health") as resp:
                if resp.status != 200:
                    print(f"❌ Backend health check failed: {resp.status}")
                    return 1
            
            # Run batch analysis
            print("🔍 Running NLU analysis...")
            async with session.get(f"{base_url}/nlu/analysis/batch") as resp:
                if resp.status != 200:
                    print(f"❌ Analysis failed: {resp.status}")
                    return 1
                
                result = await resp.json()
                
                # Process results
                blockers = result['summary']['blockers']
                warnings = result['summary']['warnings']
                
                if blockers > 0:
                    print(f"❌ {blockers} blocking conflicts found")
                    print_conflicts(result['conflicts'], 'blocker')
                    return 3  # Blocking conflicts
                elif warnings > 0:
                    print(f"⚠️  {warnings} warnings found")
                    print_conflicts(result['conflicts'], 'warning')
                    return 2  # Warnings only
                else:
                    print("✅ No conflicts detected")
                    return 0  # All clear
                    
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return 1

def print_conflicts(conflicts, severity):
    """Print conflicts of specified severity"""
    filtered = [c for c in conflicts if c['severity'] == severity]
    for conflict in filtered[:10]:  # Limit output
        print(f"  • {conflict['intent_a']} ↔ {conflict['intent_b']}: {conflict['conflict_type']}")
    
    if len(filtered) > 10:
        print(f"  ... and {len(filtered) - 10} more")

async def main():
    parser = argparse.ArgumentParser(description="NLU CI Validation")
    parser.add_argument("--backend-url", default="http://localhost:8000", 
                       help="Backend API URL")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Analysis timeout in seconds") 
    parser.add_argument("--output", help="Output analysis results to file")
    
    args = parser.parse_args()
    
    exit_code = await run_ci_analysis(args.backend_url, args.timeout)
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())
```

**Testing:**
- CLI integration with running backend
- Exit code accuracy
- Timeout handling
- Output formatting

#### 5.2 GitHub Actions Integration
**New file to create:**
- `.github/workflows/nlu-validation.yml`

**CI Workflow:**
```yaml
name: NLU Quality Validation

on:
  pull_request:
    paths: 
      - "assets/donations/**/*.json"
      - "irene/providers/nlu/**/*.py"
      - "irene/analysis/**/*.py"
  push:
    branches: [main, master]

jobs:
  nlu-validation:
    runs-on: ubuntu-latest
    
    services:
      irene-backend:
        image: irene:latest
        ports:
          - 8000:8000
        env:
          IRENE_CONFIG_PATH: /app/configs/ci-testing.toml
          IRENE_LOG_LEVEL: WARNING
        options: >-
          --health-cmd "curl -f http://localhost:8000/health || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install aiohttp
          
      - name: Wait for backend
        run: |
          for i in {1..30}; do
            if curl -f http://localhost:8000/health; then
              echo "Backend is ready"
              break
            fi
            echo "Waiting for backend... ($i/30)"
            sleep 2
          done
          
      - name: Run NLU Analysis
        id: analysis
        run: |
          python irene/tools/nlu_ci_check.py \
            --backend-url http://localhost:8000 \
            --timeout 180 \
            --output nlu-analysis.json
        continue-on-error: true
        
      - name: Upload analysis results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: nlu-analysis-results
          path: nlu-analysis.json
          
      - name: Comment PR with results
        uses: actions/github-script@v7
        if: github.event_name == 'pull_request' && always()
        with:
          script: |
            const fs = require('fs');
            const exitCode = ${{ steps.analysis.outcome === 'success' ? 0 : 1 }};
            
            let comment = '## 🔍 NLU Quality Analysis\n\n';
            
            if (exitCode === 0) {
              comment += '✅ **All checks passed** - No conflicts detected\n';
            } else {
              comment += '❌ **Issues detected** - Check the analysis results\n';
            }
            
            try {
              const analysis = JSON.parse(fs.readFileSync('nlu-analysis.json', 'utf8'));
              comment += `\n📊 **Summary:**\n`;
              comment += `- Blockers: ${analysis.summary.blockers}\n`;
              comment += `- Warnings: ${analysis.summary.warnings}\n`;
              comment += `- Total conflicts: ${analysis.conflicts.length}\n`;
            } catch (e) {
              comment += '\n⚠️ Could not parse analysis results\n';
            }
            
            comment += '\n📋 **View detailed results in the workflow artifacts**\n';
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            });
            
      - name: Fail on blocking conflicts
        if: steps.analysis.outputs.exit-code == '3'
        run: |
          echo "❌ Blocking conflicts detected - failing CI"
          exit 1
```

**Testing:**
- Workflow execution tests
- Service health validation
- Artifact generation verification
- PR comment functionality

#### 5.3 Production Configuration
**New configuration files:**
```
configs/
├── ci-testing.toml           # Minimal config for CI
├── nlu-analysis.toml         # Analysis-specific settings
└── production-hardened.toml  # Production-ready config
```

**Analysis Configuration:**
```toml
# nlu-analysis.toml
[nlu_analysis]
# Severity thresholds
blocker_threshold = 0.75
warning_threshold = 0.55

# Performance limits
max_analysis_time = 30.0  # seconds
max_concurrent_analyses = 3

# Conflict detection settings
enable_spacy_analysis = true
enable_scope_creep_detection = true
cross_domain_analysis = true

# Language settings
supported_languages = ["ru", "en"]
language_detection_threshold = 0.8

[nlu_analysis.hybrid]
# Mirror provider settings
fuzzy_threshold = 0.82
score_cutoff = 70
max_text_length_for_fuzzy = 140
partial_match_boost = 0.75

[nlu_analysis.spacy]
# Model preferences per language
ru_models = ["ru_core_news_md", "ru_core_news_sm"] 
en_models = ["en_core_web_md", "en_core_web_sm"]
confidence_threshold = 0.7
```

**Testing:**
- Configuration validation tests
- Production environment simulation
- Performance under production load
- Security and reliability validation

#### 5.4 Monitoring & Observability
**Enhanced logging and metrics:**

```python
# Analysis performance monitoring
@monitor_performance
async def analyze_donation_realtime(self, handler_name: str, language: str, donation_data: DonationData):
    start_time = time.time()
    try:
        result = await self._perform_analysis(handler_name, language, donation_data)
        self.metrics.analysis_duration.observe(time.time() - start_time)
        self.metrics.analysis_conflicts.observe(len(result.conflicts))
        return result
    except Exception as e:
        self.metrics.analysis_errors.inc()
        logger.error(f"Analysis failed for {handler_name}:{language}: {e}")
        raise

# Health check endpoint
@router.get("/nlu/health")
async def health_check():
    return {
        "status": "healthy",
        "analysis_service": await analysis_component.health_check(),
        "providers": {
            "hybrid": hybrid_provider.is_healthy(),
            "spacy": spacy_provider.is_healthy()
        },
        "last_analysis": analysis_component.last_successful_analysis
    }
```

**Testing:**
- Monitoring accuracy verification
- Health check reliability
- Performance metrics validation
- Error tracking functionality

**Phase 5 Success Criteria:**
- [ ] CI/CD integration working reliably
- [ ] Quality gates blocking problematic changes
- [ ] Production configuration tested and validated
- [ ] Monitoring and observability operational
- [ ] Documentation complete and accurate

---

## Success Metrics

### Quantitative Metrics
- **Conflict Detection Accuracy**: >95% of known conflicts detected
- **Analysis Performance**: <200ms for real-time analysis, <30s for batch
- **False Positive Rate**: <5% of flagged conflicts are actually acceptable
- **CI Integration**: <3 minutes end-to-end validation time
- **User Adoption**: >80% of donation edits use real-time analysis

### Qualitative Metrics  
- **Developer Experience**: Reduced time to identify and fix intent conflicts
- **System Reliability**: Improved predictability of intent recognition
- **Quality Assurance**: Systematic prevention of intent quality regression
- **Maintainability**: Easier onboarding and contribution to NLU system

### Monitoring Dashboards
- **System Health**: Real-time conflict counts, analysis performance
- **Quality Trends**: Historical conflict resolution and prevention
- **Usage Analytics**: Feature adoption and user interaction patterns
- **Performance Metrics**: Analysis speed, accuracy, and resource usage

## Risk Mitigation

### Technical Risks
- **Analysis Accuracy**: Comprehensive testing against known conflict scenarios
- **Performance Impact**: Careful optimization and monitoring of analysis overhead
- **Integration Complexity**: Phased rollout with feature flags and rollback plans
- **Provider Compatibility**: Extensive testing across different provider configurations

### Operational Risks
- **User Adoption**: Gradual feature introduction with clear value demonstration
- **CI Disruption**: Careful threshold tuning to minimize false positives
- **Maintenance Overhead**: Clear documentation and automated testing
- **Scalability**: Performance testing with realistic data volumes

### Mitigation Strategies
- **Feature Flags**: Gradual rollout with ability to disable problematic features
- **Rollback Plans**: Clear procedures for reverting to previous versions
- **Monitoring**: Comprehensive observability to detect issues early
- **Testing**: Extensive automated testing at unit, integration, and system levels

---

This comprehensive implementation plan provides a systematic approach to transforming the NLU system from a manual, error-prone process to an automated, quality-assured workflow with real-time feedback and robust CI/CD integration. Each phase builds upon the previous one while delivering immediate value and maintaining system reliability.
