/**
 * useRealtimeAnalysis Hook - Real-time NLU analysis for donation editing
 * 
 * Provides debounced real-time analysis of donation data with conflict detection
 * and performance optimization through caching and intelligent triggering.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import apiClient from '@/utils/apiClient';
import type { ConflictReport, NLUAnalysisResult, DonationData } from '@/types';

interface UseRealtimeAnalysisOptions {
  debounceMs?: number;
  enableCaching?: boolean;
  autoAnalyze?: boolean;
}

interface UseRealtimeAnalysisReturn {
  conflicts: ConflictReport[];
  analysisStatus: 'idle' | 'analyzing' | 'complete' | 'error';
  analysisResult: NLUAnalysisResult | null;
  error: string | null;
  analyzeNow: (donationData: DonationData) => Promise<void>;
  clearAnalysis: () => void;
  lastAnalyzedHash: string | null;
}

const useRealtimeAnalysis = (
  handlerName: string | null,
  language: string | null,
  donation: DonationData | null,
  options: UseRealtimeAnalysisOptions = {}
): UseRealtimeAnalysisReturn => {
  const {
    debounceMs = 500,
    enableCaching = true,
    autoAnalyze = true
  } = options;

  // State
  const [conflicts, setConflicts] = useState<ConflictReport[]>([]);
  const [analysisStatus, setAnalysisStatus] = useState<'idle' | 'analyzing' | 'complete' | 'error'>('idle');
  const [analysisResult, setAnalysisResult] = useState<NLUAnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastAnalyzedHash, setLastAnalyzedHash] = useState<string | null>(null);

  // Refs for cleanup and debouncing
  const debounceTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const analysisCache = useRef<Map<string, NLUAnalysisResult>>(new Map());
  const abortControllerRef = useRef<AbortController | null>(null);

  // Generate hash for donation data to detect changes and enable caching
  const generateDonationHash = useCallback((donationData: DonationData): string => {
    const relevantData = {
      description: donationData.description,
      method_donations: donationData.method_donations?.map(method => ({
        method_name: method.method_name,
        phrases: method.phrases,
        lemmas: method.lemmas,
        token_patterns: method.token_patterns,
        slot_patterns: method.slot_patterns,
        examples: method.examples
      }))
    };
    // Use Unicode-safe base64 encoding for donation data that may contain non-Latin1 characters
    return btoa(unescape(encodeURIComponent(JSON.stringify(relevantData))));
  }, []);

  // Current donation hash
  const currentHash = useMemo(() => {
    if (!donation) return null;
    return generateDonationHash(donation);
  }, [donation, generateDonationHash]);

  // Note: Cache keys are generated dynamically within performAnalysis function

  // Perform analysis
  const performAnalysis = useCallback(async (donationData: DonationData): Promise<void> => {
    if (!handlerName || !language) {
      setError('Handler name and language are required for analysis');
      setAnalysisStatus('error');
      return;
    }

    const hash = generateDonationHash(donationData);
    const key = `${handlerName}:${language}:${hash}`;

    // Check cache first
    if (enableCaching && analysisCache.current.has(key)) {
      const cachedResult = analysisCache.current.get(key)!;
      setAnalysisResult(cachedResult);
      setConflicts(cachedResult.conflicts);
      setAnalysisStatus('complete');
      setError(null);
      setLastAnalyzedHash(hash);
      return;
    }

    // Cancel any ongoing analysis
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Start new analysis
    abortControllerRef.current = new AbortController();
    setAnalysisStatus('analyzing');
    setError(null);

    try {
      const result = await apiClient.analyzeDonation(
        handlerName,
        language,
        donationData
      );

      // Check if this request was aborted
      if (abortControllerRef.current?.signal.aborted) {
        return;
      }

      setAnalysisResult(result);
      setConflicts(result.conflicts);
      setAnalysisStatus('complete');
      setLastAnalyzedHash(hash);

      // Cache the result
      if (enableCaching) {
        analysisCache.current.set(key, result);
        
        // Limit cache size to prevent memory issues
        if (analysisCache.current.size > 50) {
          const firstKey = analysisCache.current.keys().next().value;
          if (firstKey) {
            analysisCache.current.delete(firstKey);
          }
        }
      }

    } catch (err) {
      // Don't set error state if the request was aborted
      if (abortControllerRef.current?.signal.aborted) {
        return;
      }

      console.error('Analysis failed:', err);
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setAnalysisStatus('error');
      setConflicts([]);
      setAnalysisResult(null);
    }
  }, [handlerName, language, generateDonationHash, enableCaching]);

  // Debounced analysis function
  const debouncedAnalyze = useCallback((donationData: DonationData) => {
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    debounceTimeoutRef.current = setTimeout(() => {
      performAnalysis(donationData);
    }, debounceMs);
  }, [performAnalysis, debounceMs]);

  // Manual analysis trigger (immediate, no debounce)
  const analyzeNow = useCallback(async (donationData: DonationData): Promise<void> => {
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
      debounceTimeoutRef.current = null;
    }
    await performAnalysis(donationData);
  }, [performAnalysis]);

  // Clear analysis state
  const clearAnalysis = useCallback(() => {
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
      debounceTimeoutRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setConflicts([]);
    setAnalysisResult(null);
    setAnalysisStatus('idle');
    setError(null);
    setLastAnalyzedHash(null);
  }, []);

  // Auto-analyze when donation changes
  useEffect(() => {
    if (!autoAnalyze || !donation || !handlerName || !language) {
      return;
    }

    // Skip analysis if data hasn't changed
    if (currentHash === lastAnalyzedHash) {
      return;
    }

    debouncedAnalyze(donation);
  }, [donation, handlerName, language, autoAnalyze, debouncedAnalyze, currentHash, lastAnalyzedHash]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return {
    conflicts,
    analysisStatus,
    analysisResult,
    error,
    analyzeNow,
    clearAnalysis,
    lastAnalyzedHash
  };
};

export default useRealtimeAnalysis;
