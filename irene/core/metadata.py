"""
Universal Entry-Point Metadata Interface

Central metadata interface for all entry-points in the Irene Voice Assistant project.
Supports both asset configuration (TODO #4) and build dependencies (TODO #5).
Enables configuration-driven systems and external package integration.

Relocated from irene/providers/base.py in TODO #5 Phase 0.
"""

from abc import ABC
from typing import Dict, Any, List


class EntryPointMetadata(ABC):
    """
    Universal metadata interface for all entry-points.
    
    Supports both asset configuration (TODO #4) and build dependencies (TODO #5).
    Enables configuration-driven systems and external package integration.
    
    This interface provides:
    1. Asset configuration with intelligent defaults and TOML overrides
    2. Build dependency declaration for system packages and Python dependencies  
    3. Platform support specification for multi-platform builds
    4. External package integration capabilities
    """
    
    # ✅ Asset configuration methods (implemented in TODO #4)
    @classmethod
    def get_asset_config(cls) -> Dict[str, Any]:
        """
        Get asset configuration with intelligent defaults.
        
        Returns:
            Dictionary containing:
            - file_extension: Default file extension for models/assets
            - directory_name: Default directory name for asset storage
            - credential_patterns: List of environment variable patterns needed
            - cache_types: List of cache types used (models, runtime, temp, etc.)
            - model_urls: Dictionary of model URLs for downloads
        """
        return {
            "file_extension": cls._get_default_extension(),
            "directory_name": cls._get_default_directory(),
            "credential_patterns": cls._get_default_credentials(),
            "cache_types": cls._get_default_cache_types(),
            "model_urls": cls._get_default_model_urls()
        }
    
    # 🆕 Build dependency methods (TODO #5)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """
        Python dependency groups from pyproject.toml optional-dependencies.
        
        Returns:
            List of dependency group names that this entry-point requires.
            These should correspond to groups defined in pyproject.toml [project.optional-dependencies].
            
        Examples:
            - Audio providers: ["audio-input", "audio-output"]  
            - TTS providers: ["tts"]
            - ASR providers: ["asr"]
            - Web components: ["web-api"]
        """
        return []
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """
        Supported platforms for this entry-point.
        
        Returns:
            List of supported platforms: ["linux.ubuntu", "linux.alpine", "macos", "windows"]
            Uses same platform keys as get_platform_dependencies() for consistency.
            
        Default supports all common platforms. Override for platform-specific limitations.
        """
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
        
    @classmethod  
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """
        Platform-specific system package mappings.
        
        Returns:
            Dictionary mapping platform names to lists of required system packages.
            
        Platform keys:
            - "linux.ubuntu": Ubuntu/Debian system packages (apt)
            - "linux.alpine": Alpine Linux packages (apk) - used for ARMv7 builds
            - "macos": macOS Homebrew packages (brew)
            - "windows": Windows system packages (typically none needed)
            
        Examples:
            Audio providers might return:
            {
                "linux.ubuntu": ["libportaudio2", "libsndfile1"],
                "linux.alpine": ["portaudio-dev", "libsndfile-dev"],  
                "macos": [],  # Homebrew handles dependencies automatically
                "windows": []  # Windows package management differs
            }
        """
        return {
            "linux.ubuntu": [],  # Ubuntu/Debian system packages
            "linux.alpine": [],  # Alpine Linux (ARMv7) packages
            "macos": [],          # macOS Homebrew packages
            "windows": []         # Windows system packages
        }
        
    # Asset configuration helper methods (moved from providers/base.py)
    @classmethod
    def _get_default_extension(cls) -> str:
        """
        Override in provider classes for intelligent file extension defaults.
        
        Returns:
            Default file extension (e.g., ".pt", ".wav", ".json")
        """
        return ""
    
    @classmethod
    def _get_default_directory(cls) -> str:
        """
        Override in provider classes for intelligent directory name defaults.
        
        Returns:
            Default directory name for asset storage
        """
        # Default to lowercase class name without "Provider" suffix
        name = cls.__name__.lower()
        if name.endswith('provider'):
            name = name[:-8]  # Remove 'provider' suffix
        return name
    
    @classmethod
    def _get_default_credentials(cls) -> List[str]:
        """
        Override in provider classes for intelligent credential defaults.
        
        Returns:
            List of environment variable patterns needed by provider
        """
        return []
    
    @classmethod
    def _get_default_cache_types(cls) -> List[str]:
        """
        Override in provider classes for intelligent cache type defaults.
        
        Returns:
            List of cache types used: ["models", "runtime", "temp", "downloads"]
        """
        return ["runtime"]
    
    @classmethod
    def _get_default_model_urls(cls) -> Dict[str, str]:
        """
        Override in provider classes for intelligent model URL defaults.
        
        Returns:
            Dictionary mapping model IDs to download URLs
        """
        return {} 