"""
Asset Management System

Centralized management of models, cache, and credentials for Irene Voice Assistant.
Supports environment variable configuration for Docker-friendly deployments.
"""

import os
import asyncio
import hashlib
import logging
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
    
    @classmethod
    def from_env(cls) -> "AssetManager":
        """Create AssetManager from environment variables"""
        from ..config.models import AssetConfig
        config = AssetConfig()
        return cls(config)
    
    def get_model_path(self, provider: str, model_id: str, filename: Optional[str] = None) -> Path:
        """Get standardized model path"""
        provider_dir = getattr(self.config, f"{provider}_models_dir", self.config.models_root / provider)
        
        if filename:
            return provider_dir / filename
        
        # Auto-generate filename based on provider conventions
        if provider == "whisper":
            return provider_dir / f"{model_id}.pt"
        elif provider == "silero":
            return provider_dir / f"{model_id}.pt"
        elif provider == "vosk":
            return provider_dir / model_id
        else:
            return provider_dir / model_id
    
    def get_cache_path(self, cache_type: str = "runtime") -> Path:
        """Get cache directory path"""
        cache_attr = f"{cache_type}_cache_dir"
        return getattr(self.config, cache_attr, self.config.cache_root / cache_type)
    
    def get_credentials_path(self, provider: str, filename: Optional[str] = None) -> Path:
        """Get credentials file path"""
        if filename:
            return self.config.credentials_root / filename
        return self.config.credentials_root / f"{provider}.json"
    
    def get_credentials(self, provider: str) -> Dict[str, Any]:
        """Get credentials from environment variables or files"""
        credentials = {}
        
        # Common environment variable patterns
        env_patterns = {
            "openai": ["OPENAI_API_KEY"],
            "anthropic": ["ANTHROPIC_API_KEY"],
            "elevenlabs": ["ELEVENLABS_API_KEY"],
            "google_cloud": ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT_ID"],
            "vsegpt": ["VSEGPT_API_KEY"]
        }
        
        # Try environment variables first
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


# Global asset manager instance (lazy-loaded)
_asset_manager: Optional[AssetManager] = None


def get_asset_manager() -> AssetManager:
    """Get global asset manager instance"""
    global _asset_manager
    if _asset_manager is None:
        _asset_manager = AssetManager.from_env()
    return _asset_manager 