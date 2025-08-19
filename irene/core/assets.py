"""
Asset Management System

Centralized management of models, cache, and credentials for Irene Voice Assistant.
Supports environment variable configuration for Docker-friendly deployments.

Enhanced in TODO #4 Phase 2 with configuration-driven asset management.
"""

import os
import asyncio
import hashlib
import logging
import pickle
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

logger = logging.getLogger(__name__)


# AssetConfig moved to config.models to avoid circular imports


class AssetManager:
    """Centralized asset manager for models, cache, and credentials"""
    
    def __init__(self, config: "AssetConfig"):  # type: ignore
        self.config = config
        self._download_locks: Dict[str, asyncio.Lock] = {}
        self._provider_asset_cache: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def from_env(cls) -> "AssetManager":
        """Create AssetManager from environment variables"""
        from ..config.models import AssetConfig
        config = AssetConfig()
        return cls(config)
    
    def _get_provider_asset_config(self, provider: str) -> Dict[str, Any]:
        """
        Get asset configuration for a provider by querying the provider class.
        
        This replaces hardcoded mappings with configuration-driven approach.
        Uses provider class asset methods implemented in TODO #4 Phase 1.
        
        Args:
            provider: Provider name (e.g., 'whisper', 'silero', 'elevenlabs')
            
        Returns:
            Asset configuration dictionary with defaults and TOML overrides
        """
        # Check cache first
        if provider in self._provider_asset_cache:
            return self._provider_asset_cache[provider]
        
        # Discover provider class and get asset config
        from ..utils.loader import dynamic_loader
        
        # Map provider names to namespaces
        provider_namespace_map = {
            'whisper': 'irene.providers.asr',
            'silero': 'irene.providers.tts',
            'vosk': 'irene.providers.asr',
            'openwakeword': 'irene.providers.voice_trigger',
            'microwakeword': 'irene.providers.voice_trigger',
            'elevenlabs': 'irene.providers.tts',
            'openai': 'irene.providers.llm',
            'anthropic': 'irene.providers.llm',
            'google_cloud': 'irene.providers.asr',
            'sounddevice': 'irene.providers.audio',
            'console': 'irene.providers.audio',
        }
        
        # Try to find the provider in appropriate namespace
        provider_class = None
        if provider in provider_namespace_map:
            namespace = provider_namespace_map[provider]
            provider_class = dynamic_loader.get_provider_class(namespace, provider)
        else:
            # Search across all provider namespaces
            namespaces = [
                'irene.providers.tts',
                'irene.providers.asr', 
                'irene.providers.audio',
                'irene.providers.llm',
                'irene.providers.voice_trigger',
                'irene.providers.nlu',
                'irene.providers.text_processing'
            ]
            for namespace in namespaces:
                provider_class = dynamic_loader.get_provider_class(namespace, provider)
                if provider_class:
                    break
        
        if provider_class and hasattr(provider_class, 'get_asset_config'):
            try:
                asset_config = provider_class.get_asset_config()
                logger.debug(f"Loaded asset config for provider '{provider}': {asset_config}")
            except Exception as e:
                logger.warning(f"Failed to get asset config for provider '{provider}': {e}")
                asset_config = self._get_fallback_asset_config(provider)
        else:
            logger.debug(f"Provider '{provider}' not found or no asset config method, using fallback")
            asset_config = self._get_fallback_asset_config(provider)
        
        # Cache the result
        self._provider_asset_cache[provider] = asset_config
        return asset_config
    
    def _get_fallback_asset_config(self, provider: str) -> Dict[str, Any]:
        """
        Minimal fallback asset configuration for providers without explicit config.
        
        Uses generic defaults instead of hardcoded provider-specific mappings.
        All known providers should implement asset configuration methods.
        """
        logger.warning(f"Provider '{provider}' not found or missing asset config - using generic defaults")
        
        # Generic defaults that work for any provider
        return {
            "file_extension": "",                  # No extension assumption
            "directory_name": provider,            # Use provider name as directory
            "credential_patterns": [],             # No credentials assumed
            "cache_types": ["runtime"],            # Minimal cache usage
            "model_urls": {}                       # No model URLs
        }
    
    def get_model_path(self, provider: str, model_id: str, filename: Optional[str] = None) -> Path:
        """Get standardized model path using provider asset configuration"""
        # Get provider asset configuration instead of hardcoded mapping
        asset_config = self._get_provider_asset_config(provider)
        
        # Use configured directory name
        directory_name = asset_config.get("directory_name", provider)
        provider_dir = self.config.models_root / directory_name
        
        if filename:
            return provider_dir / filename
        
        # Use configured file extension
        file_extension = asset_config.get("file_extension", "")
        if file_extension:
            return provider_dir / f"{model_id}{file_extension}"
        else:
            return provider_dir / model_id
    
    def get_cache_path(self, cache_type: str = "runtime") -> Path:
        """Get cache directory path"""
        cache_attr = f"{cache_type}_cache_dir"
        return getattr(self.config, cache_attr, self.config.cache_root / cache_type)
    
    def get_provider_cache_path(self, provider_name: str) -> Path:
        """Get provider-specific cache directory path"""
        return self.config.cache_root / provider_name
    
    async def get_cached_data(self, cache_key: str, provider_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data by key with comprehensive error handling.
        
        Args:
            cache_key: Unique cache identifier
            provider_name: Optional provider name for provider-specific cache directory
            
        Returns:
            Cached data dictionary or None if not found/invalid
        """
        if not cache_key or not isinstance(cache_key, str):
            logger.error(f"Invalid cache key: {cache_key}")
            return None
        
        try:
            if provider_name:
                cache_dir = self.get_provider_cache_path(provider_name)
            else:
                cache_dir = self.get_cache_path("runtime")
            cache_file = cache_dir / f"{cache_key}.cache"
            
            if not cache_file.exists():
                logger.debug(f"Cache miss: {cache_key}")
                return None
            
            # Check file size and age
            file_stat = cache_file.stat()
            if file_stat.st_size == 0:
                logger.warning(f"Empty cache file: {cache_key}")
                cache_file.unlink()  # Remove corrupted file
                return None
            
            # Load cached data with additional error handling
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
            except (pickle.PickleError, EOFError) as e:
                logger.warning(f"Corrupted cache file {cache_key}: {e}")
                cache_file.unlink()  # Remove corrupted file
                return None
            except PermissionError as e:
                logger.error(f"Permission denied reading cache file {cache_key}: {e}")
                return None
            
            # Basic validation
            if not isinstance(cached_data, dict):
                logger.warning(f"Invalid cache data format for {cache_key}")
                cache_file.unlink()  # Remove invalid file
                return None
            
            logger.debug(f"Cache hit: {cache_key} ({file_stat.st_size} bytes)")
            return cached_data
            
        except Exception as e:
            logger.warning(f"Failed to load cached data for {cache_key}: {e}")
            return None
    
    async def set_cached_data(self, cache_key: str, data: Dict[str, Any], provider_name: str = None) -> bool:
        """
        Store data in cache with given key and comprehensive error handling.
        
        Args:
            cache_key: Unique cache identifier
            data: Data to cache
            provider_name: Optional provider name for provider-specific cache directory
            
        Returns:
            True if successful, False otherwise
        """
        if not cache_key or not isinstance(cache_key, str):
            logger.error(f"Invalid cache key: {cache_key}")
            return False
        
        if not isinstance(data, dict):
            logger.error(f"Invalid data type for caching: {type(data)}")
            return False
        
        try:
            if provider_name:
                cache_dir = self.get_provider_cache_path(provider_name)
            else:
                cache_dir = self.get_cache_path("runtime")
            
            # Ensure cache directory exists with proper permissions
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                logger.error(f"Permission denied creating cache directory {cache_dir}: {e}")
                return False
            
            cache_file = cache_dir / f"{cache_key}.cache"
            temp_file = cache_dir / f"{cache_key}.cache.tmp"
            
            # Store to temporary file first (atomic operation)
            try:
                with open(temp_file, 'wb') as f:
                    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                # Atomic move to final location
                temp_file.rename(cache_file)
                
            except (pickle.PickleError, PermissionError, OSError) as e:
                logger.error(f"Failed to serialize/write cache data for {cache_key}: {e}")
                # Clean up temporary file
                if temp_file.exists():
                    temp_file.unlink()
                return False
            
            # Verify the file was written correctly
            file_stat = cache_file.stat()
            if file_stat.st_size == 0:
                logger.error(f"Cache file written with zero size: {cache_key}")
                cache_file.unlink()
                return False
            
            logger.debug(f"Cached data: {cache_key} ({file_stat.st_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache data for {cache_key}: {e}")
            return False
    
    async def invalidate_cache(self, cache_pattern: str = None, provider_name: str = None) -> int:
        """
        Invalidate cached data based on pattern or clear all cache.
        
        Args:
            cache_pattern: Pattern to match cache keys (None = clear all)
            
        Returns:
            Number of cache files removed
        """
        try:
            if provider_name:
                cache_dir = self.get_provider_cache_path(provider_name)
            else:
                cache_dir = self.get_cache_path("runtime")
            if not cache_dir.exists():
                return 0
            
            removed_count = 0
            
            for cache_file in cache_dir.glob("*.cache"):
                if cache_pattern is None or cache_pattern in cache_file.stem:
                    try:
                        cache_file.unlink()
                        removed_count += 1
                        logger.debug(f"Removed cache file: {cache_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {cache_file}: {e}")
            
            logger.info(f"Cache invalidation: removed {removed_count} files")
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return 0
    
    async def get_cache_stats(self, provider_name: str = None) -> Dict[str, Any]:
        """
        Get cache statistics and health information.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            if provider_name:
                cache_dir = self.get_provider_cache_path(provider_name)
            else:
                cache_dir = self.get_cache_path("runtime")
            if not cache_dir.exists():
                return {"cache_files": 0, "total_size": 0, "cache_dir": str(cache_dir)}
            
            cache_files = list(cache_dir.glob("*.cache"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            stats = {
                "cache_files": len(cache_files),
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "cache_dir": str(cache_dir),
                "files": []
            }
            
            # Add details for each cache file
            for cache_file in cache_files:
                try:
                    file_stat = cache_file.stat()
                    stats["files"].append({
                        "name": cache_file.name,
                        "size": file_stat.st_size,
                        "modified": file_stat.st_mtime
                    })
                except Exception as e:
                    logger.debug(f"Failed to stat cache file {cache_file}: {e}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
    
    def get_credentials_path(self, provider: str, filename: Optional[str] = None) -> Path:
        """Get credentials file path"""
        if filename:
            return self.config.credentials_root / filename
        return self.config.credentials_root / f"{provider}.json"
    
    def get_credentials(self, provider: str) -> Dict[str, Any]:
        """Get credentials from environment variables or files using provider configuration"""
        credentials = {}
        
        # Get credential patterns from provider configuration
        asset_config = self._get_provider_asset_config(provider)
        credential_patterns = asset_config.get("credential_patterns", [])
        
        # Try environment variables from provider config
        for env_var in credential_patterns:
            value = os.getenv(env_var)
            if value:
                credentials[env_var.lower()] = value
        
        # Fallback to legacy hardcoded patterns for backward compatibility
        if not credentials:
            env_patterns = {
                "openai": ["OPENAI_API_KEY"],
                "anthropic": ["ANTHROPIC_API_KEY"],
                "elevenlabs": ["ELEVENLABS_API_KEY"],
                "google_cloud": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT_ID"],
                "vsegpt": ["VSEGPT_API_KEY"]
            }
            
            if provider in env_patterns:
                for env_var in env_patterns[provider]:
                    value = os.getenv(env_var)
                    if value:
                        credentials[env_var.lower()] = value
        
        # Try credentials file
        cred_file = self.get_credentials_path(provider)
        if cred_file.exists():
            try:
                with open(cred_file, 'r') as f:
                    file_creds = json.load(f)
                credentials.update(file_creds)
            except Exception as e:
                logger.warning(f"Failed to load credentials from {cred_file}: {e}")
        
        return credentials
    
    async def download_model(self, provider: str, model_id: str, force: bool = False) -> Path:
        """Download model if not cached, return path"""
        # Get download lock to prevent concurrent downloads of same model
        lock_key = f"{provider}:{model_id}"
        if lock_key not in self._download_locks:
            self._download_locks[lock_key] = asyncio.Lock()
        
        async with self._download_locks[lock_key]:
            return await self._download_model_impl(provider, model_id, force)
    
    async def _download_model_impl(self, provider: str, model_id: str, force: bool) -> Path:
        """Internal download implementation"""
        model_path = self.get_model_path(provider, model_id)
        
        # Check if already exists
        if model_path.exists() and not force:
            logger.info(f"Model already exists: {model_path}")
            return model_path
        
        # Get model info from registry
        if provider not in self.config.model_registry:
            raise ValueError(f"Unknown provider: {provider}")
        
        if model_id not in self.config.model_registry[provider]:
            raise ValueError(f"Unknown model: {provider}/{model_id}")
        
        model_info = self.config.model_registry[provider][model_id]
        
        # Handle special cases
        if provider == "whisper" and model_info["url"] == "auto":
            # Let whisper library handle download
            logger.info(f"Whisper model will be auto-downloaded by library: {model_id}")
            return model_path
        
        if provider == "openwakeword" and model_info["url"] == "auto":
            # Let OpenWakeWord library handle download
            logger.info(f"OpenWakeWord model will be auto-downloaded by library: {model_id}")
            return model_path
        
        if provider == "microwakeword" and model_info["url"] == "local":
            # Local model - should be provided manually to the models directory
            logger.info(f"microWakeWord model should be provided locally: {model_path}")
            if not model_path.exists():
                raise FileNotFoundError(f"Local microWakeWord model not found: {model_path}")
            return model_path
        
        # Download the model
        url = model_info["url"]
        logger.info(f"Downloading {provider}/{model_id} from {url}")
        
        # Create parent directory
        model_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Download to temporary file first
        temp_path = self.config.downloads_cache_dir / f"{provider}_{model_id}_downloading"
        
        try:
            await self._download_file(url, temp_path)
            
            # Handle extraction if needed
            if model_info.get("extract", False):
                await self._extract_archive(temp_path, model_path)
                temp_path.unlink()  # Remove downloaded archive
            else:
                # Move to final location
                temp_path.rename(model_path)
            
            logger.info(f"Successfully downloaded: {model_path}")
            return model_path
            
        except Exception as e:
            # Clean up on failure
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Failed to download {provider}/{model_id}: {e}")
            raise
    
    async def _download_file(self, url: str, target_path: Path) -> None:
        """Download file with progress tracking"""
        try:
            import aiohttp  # type: ignore
        except ImportError:
            raise RuntimeError("aiohttp required for model downloads. Install with: pip install aiohttp")
        
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                
                with open(target_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
    
    async def _extract_archive(self, archive_path: Path, target_dir: Path) -> None:
        """Extract archive to target directory"""
        import zipfile
        import tarfile
        
        target_dir.mkdir(parents=True, exist_ok=True)
        
        def extract_sync():
            if archive_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
            elif archive_path.suffix.lower() in ['.tar', '.tar.gz', '.tgz']:
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    tar_ref.extractall(target_dir)
            else:
                raise ValueError(f"Unsupported archive format: {archive_path.suffix}")
        
        await asyncio.to_thread(extract_sync)
    
    def model_exists(self, provider: str, model_id: str) -> bool:
        """Check if model exists locally"""
        model_path = self.get_model_path(provider, model_id)
        return model_path.exists()
    
    def get_model_info(self, provider: str, model_id: str) -> Dict[str, Any]:
        """Get model information from registry"""
        if provider not in self.config.model_registry:
            return {}
        return self.config.model_registry[provider].get(model_id, {})
    
    async def ensure_model_available(self, provider_name: str, model_name: str, asset_config: Dict[str, Any]) -> Optional[Path]:
        """
        Ensure model is available, downloading if necessary.
        
        This method bridges the gap between provider asset configurations
        and actual model availability, following patterns from existing
        ASR and TTS providers.
        
        Args:
            provider_name: Provider identifier (e.g., "spacy", "vosk")
            model_name: Model identifier (e.g., "ru_core_news_sm", "en_core_web_sm")
            asset_config: Provider asset configuration
            
        Returns:
            Path to available model, or None if model cannot be ensured
        """
        try:
            logger.info(f"Ensuring model availability: {provider_name}/{model_name}")
            
            # Check if model already exists
            if self.model_exists(provider_name, model_name):
                model_path = self.get_model_path(provider_name, model_name)
                logger.info(f"Model already available: {model_path}")
                return model_path
            
            # Special handling for spaCy models
            if provider_name == "spacy":
                return await self._ensure_spacy_model_available(model_name)
            
            # For other providers, attempt download through registry
            try:
                model_path = await self.download_model(provider_name, model_name)
                logger.info(f"Model downloaded and available: {model_path}")
                return model_path
            except Exception as e:
                logger.warning(f"Failed to download model {provider_name}/{model_name}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to ensure model availability {provider_name}/{model_name}: {e}")
            return None
    
    async def _ensure_spacy_model_available(self, model_name: str) -> Optional[Path]:
        """
        Ensure spaCy model is available using spaCy's download mechanism.
        
        spaCy models are installed as Python packages, not downloaded as files.
        This method uses spaCy's built-in download system.
        
        Args:
            model_name: spaCy model name (e.g., "ru_core_news_sm")
            
        Returns:
            Path to model package location, or None if installation failed
        """
        try:
            import subprocess
            import sys
            
            logger.info(f"Installing spaCy model: {model_name}")
            
            # Use spaCy's download command
            cmd = [sys.executable, "-m", "spacy", "download", model_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Successfully installed spaCy model: {model_name}")
                
                # Return a symbolic path - spaCy models are installed as packages
                # The actual model will be loaded via spacy.load(model_name)
                model_path = self.get_model_path("spacy", model_name)
                model_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create a marker file to indicate the model is installed
                marker_file = model_path.parent / f"{model_name}.installed"
                marker_file.touch()
                
                return marker_file
            else:
                logger.error(f"Failed to install spaCy model {model_name}: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error installing spaCy model {model_name}: {e}")
            return None


# Global asset manager instance (lazy-loaded)
_asset_manager: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    """Get global asset manager instance"""
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = AssetManager.from_env()
    return _asset_manager 