"""
Irene Providers - Implementation modules for Universal Plugins

This package contains provider implementations that are managed by Universal Plugins.
Providers are pure implementation classes without plugin overhead, following the
configuration-driven instantiation pattern.

Package Structure:
- base.py: Common provider utilities and base classes
- tts/: Text-to-speech provider implementations
- audio/: Audio playback provider implementations (Phase 2)
- asr/: Speech recognition provider implementations (Phase 4)
- llm/: Language model provider implementations (Phase 4)
"""

from .base import ProviderBase, ProviderStatus, EntryPointMetadata

__all__ = ["ProviderBase", "ProviderStatus", "EntryPointMetadata"] 