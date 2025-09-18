/**
 * Donation Sync Helper - Utility functions for lemma/token pattern synchronization
 * 
 * This module provides utilities to help with the sync functionality
 * between lemmas and token patterns in method donations.
 */

export interface SyncStatus {
  hasIssues: boolean;
  unsyncedLemmas: string[];
  extractedLemmas: string[];
}

/**
 * Extract lemmas from spaCy token patterns
 */
export function extractLemmasFromTokenPatterns(tokenPatterns: Array<Array<Record<string, any>>>): string[] {
  const extractedLemmas: Set<string> = new Set();
  
  tokenPatterns.forEach(pattern => {
    pattern.forEach(token => {
      if (token.LEMMA) {
        if (typeof token.LEMMA === 'string') {
          extractedLemmas.add(token.LEMMA);
        } else if (token.LEMMA.IN && Array.isArray(token.LEMMA.IN)) {
          token.LEMMA.IN.forEach((lemma: string) => extractedLemmas.add(lemma));
        }
      }
    });
  });
  
  return Array.from(extractedLemmas);
}

/**
 * Check sync status between lemmas and token patterns
 */
export function checkSyncStatus(lemmas: string[], tokenPatterns: Array<Array<Record<string, any>>>): SyncStatus {
  const extractedLemmas = extractLemmasFromTokenPatterns(tokenPatterns);
  const unsyncedLemmas = extractedLemmas.filter(lemma => !lemmas.includes(lemma));
  
  return {
    hasIssues: unsyncedLemmas.length > 0,
    unsyncedLemmas,
    extractedLemmas
  };
}

/**
 * Merge lemmas with extracted ones, avoiding duplicates
 */
export function mergeLemmas(currentLemmas: string[], extractedLemmas: string[]): string[] {
  return [...new Set([...currentLemmas, ...extractedLemmas])];
}

/**
 * Example usage for testing the tester's scenario
 */
export function createTestScenario() {
  // Simulate what the tester added - "ку", "здарова" in token patterns
  const testTokenPatterns = [
    [
      {
        "LEMMA": {
          "IN": ["ку", "здарова", "привет", "здравствовать"]
        }
      }
    ]
  ];
  
  // Current lemmas (what was in the file before sync)
  const currentLemmas = ["привет", "здравствовать", "приветствовать"];
  
  const syncStatus = checkSyncStatus(currentLemmas, testTokenPatterns);
  
  return {
    before: {
      lemmas: currentLemmas,
      tokenPatterns: testTokenPatterns
    },
    syncStatus,
    after: {
      lemmas: mergeLemmas(currentLemmas, syncStatus.extractedLemmas),
      tokenPatterns: testTokenPatterns
    }
  };
}
