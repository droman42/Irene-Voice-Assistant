"""
Configuration Migration Utilities - v13→v14 migration support

Phase 1 Implementation: Migration utilities to convert v13 configuration 
structure to the new v14 clean architecture.

This module provides:
- Automatic migration from v13 to v14 structure
- Configuration transformation utilities
- Backwards compatibility helpers
- Migration validation
"""

import os
import logging
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from .models import (
    CoreConfig, SystemConfig, InputConfig, ComponentConfig, 
    TTSConfig, AudioConfig, ASRConfig, LLMConfig, 
    VoiceTriggerConfig, NLUConfig, TextProcessorConfig, IntentSystemConfig,
    AssetConfig, WorkflowConfig
)
from .schemas import SchemaVersion, CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)


class ConfigurationMigrationError(Exception):
    """Exception raised during configuration migration"""
    pass


class V13ToV14Migrator:
    """Migrates v13 configuration structure to v14 clean architecture"""
    
    def __init__(self):
        self.migration_log: List[str] = []
    
    def migrate(self, v13_config: Dict[str, Any]) -> CoreConfig:
        """
        Migrate v13 configuration to v14 structure
        
        Args:
            v13_config: Dictionary containing v13 configuration
            
        Returns:
            CoreConfig: New v14 configuration object
            
        Raises:
            ConfigurationMigrationError: If migration fails
        """
        try:
            self.migration_log.clear()
            self._log("Starting v13→v14 configuration migration")
            
            # Extract core settings
            core_settings = self._extract_core_settings(v13_config)
            
            # Migrate architecture sections
            system_config = self._migrate_system_config(v13_config)
            input_config = self._migrate_input_config(v13_config)
            component_config = self._migrate_component_config(v13_config)
            asset_config = self._migrate_asset_config(v13_config)
            workflow_config = self._migrate_workflow_config(v13_config)
            
            # Migrate component-specific configurations
            component_configs = self._migrate_component_specific_configs(v13_config)
            
            # Create new v14 configuration
            v14_config = CoreConfig(
                **core_settings,
                system=system_config,
                inputs=input_config,
                components=component_config,
                assets=asset_config,
                workflows=workflow_config,
                **component_configs
            )
            
            self._log("v13→v14 migration completed successfully")
            self._log_migration_summary()
            
            return v14_config
            
        except Exception as e:
            error_msg = f"Migration failed: {str(e)}"
            self._log(error_msg)
            raise ConfigurationMigrationError(error_msg) from e
    
    def _extract_core_settings(self, v13_config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract core settings from v13 config"""
        core_settings = {}
        
        # Basic settings
        core_settings["name"] = v13_config.get("name", "Irene")
        core_settings["version"] = "14.0.0"  # Upgrade to v14
        core_settings["debug"] = v13_config.get("debug", False)
        core_settings["log_level"] = v13_config.get("log_level", "INFO")
        
        # Runtime settings
        core_settings["max_concurrent_commands"] = v13_config.get("max_concurrent_commands", 10)
        core_settings["command_timeout_seconds"] = v13_config.get("command_timeout_seconds", 30.0)
        core_settings["context_timeout_minutes"] = v13_config.get("context_timeout_minutes", 30)
        
        # Language and locale
        core_settings["language"] = v13_config.get("language", "en-US")
        core_settings["timezone"] = v13_config.get("timezone")
        
        self._log("Extracted core settings")
        return core_settings
    
    def _migrate_system_config(self, v13_config: Dict[str, Any]) -> SystemConfig:
        """Migrate to new SystemConfig structure"""
        v13_components = v13_config.get("components", {})
        
        # Extract hardware capabilities
        microphone_enabled = v13_components.get("microphone", False)
        audio_playback_enabled = v13_components.get("audio_output", False)
        
        # Extract service capabilities
        web_api_enabled = v13_components.get("web_api", True)
        web_port = v13_components.get("web_port", 8000)
        
        # Metrics from advanced settings
        metrics_enabled = v13_config.get("enable_metrics", False)
        metrics_port = v13_config.get("metrics_port", 9090)
        
        system_config = SystemConfig(
            microphone_enabled=microphone_enabled,
            audio_playback_enabled=audio_playback_enabled,
            web_api_enabled=web_api_enabled,
            web_port=web_port,
            metrics_enabled=metrics_enabled,
            metrics_port=metrics_port
        )
        
        self._log(f"Migrated system config: microphone={microphone_enabled}, audio={audio_playback_enabled}, web_api={web_api_enabled}")
        return system_config
    
    def _migrate_input_config(self, v13_config: Dict[str, Any]) -> InputConfig:
        """Migrate to new InputConfig structure with detailed configurations"""
        v13_components = v13_config.get("components", {})
        v13_audio = v13_config.get("audio", {})
        v13_plugins = v13_config.get("plugins", {})
        
        # Infer input sources from component capabilities
        microphone = v13_components.get("microphone", False)
        web = v13_components.get("web_api", True)
        cli = True  # Always available
        
        # Determine default input
        default_input = "cli"
        if microphone:
            default_input = "microphone"
        elif web:
            default_input = "web"
        
        # Create microphone configuration from v13 audio settings
        mic_config = self._create_microphone_config(v13_audio, v13_plugins)
        
        # Create web configuration  
        web_config = self._create_web_config(v13_config)
        
        # Create CLI configuration
        cli_config = self._create_cli_config(v13_config)
        
        input_config = InputConfig(
            microphone=microphone,
            web=web,
            cli=cli,
            default_input=default_input,
            microphone_config=mic_config,
            web_config=web_config,
            cli_config=cli_config
        )
        
        self._log(f"Migrated input config: microphone={microphone}, web={web}, default={default_input}")
        return input_config
    
    def _create_microphone_config(self, v13_audio: Dict[str, Any], v13_plugins: Dict[str, Any]):
        """Create microphone configuration from v13 settings"""
        from .models import MicrophoneInputConfig
        
        # Extract audio settings
        input_settings = v13_audio.get("input", {})
        
        return MicrophoneInputConfig(
            enabled=True,
            device_id=input_settings.get("device_id"),  # None if not specified
            sample_rate=input_settings.get("sample_rate", 16000),
            channels=input_settings.get("channels", 1),
            chunk_size=input_settings.get("chunk_size", 1024)
        )
    
    def _create_web_config(self, v13_config: Dict[str, Any]):
        """Create web configuration from v13 settings"""
        from .models import WebInputConfig
        
        return WebInputConfig(
            enabled=True,
            websocket_enabled=True,  # Default to enabled
            rest_api_enabled=True    # Default to enabled
        )
    
    def _create_cli_config(self, v13_config: Dict[str, Any]):
        """Create CLI configuration from v13 settings"""
        from .models import CLIInputConfig
        
        return CLIInputConfig(
            enabled=True,
            prompt_prefix="irene> ",  # Default prefix
            history_enabled=True      # Default to enabled
        )
    
    def _migrate_component_config(self, v13_config: Dict[str, Any]) -> ComponentConfig:
        """Migrate to new ComponentConfig structure"""
        v13_components = v13_config.get("components", {})
        v13_plugins = v13_config.get("plugins", {})
        
        # Extract enabled/disabled component lists from v13 format
        enabled_components = v13_components.get("enabled", [])
        disabled_components = v13_components.get("disabled", [])
        
        # Helper function to check if component is enabled
        def is_component_enabled(component_name: str, alt_names: list = None) -> bool:
            """Check if a component is enabled, with alternative name checking"""
            if alt_names is None:
                alt_names = []
            
            # Check if component is explicitly disabled
            for name in [component_name] + alt_names:
                if name in disabled_components:
                    return False
            
            # Check if component is explicitly enabled
            for name in [component_name] + alt_names:
                if name in enabled_components:
                    return True
            
            # Fall back to plugin-based inference if not found in lists
            return False
        
        # Map v13 component flags to v14 structure
        component_config = ComponentConfig(
            tts=is_component_enabled("tts"),
            asr=is_component_enabled("asr") or self._infer_asr_enabled(v13_plugins),
            audio=is_component_enabled("audio", ["audio_output"]),
            llm=is_component_enabled("llm") or self._infer_llm_enabled(v13_plugins),
            voice_trigger=is_component_enabled("voice_trigger") or self._infer_voice_trigger_enabled(v13_config),
            nlu=is_component_enabled("nlu") or self._infer_nlu_enabled(v13_plugins),
            text_processor=is_component_enabled("text_processor") or self._infer_text_processor_enabled(v13_plugins),
            intent_system=is_component_enabled("intent_system") or v13_config.get("intents", {}).get("enabled", True)
        )
        
        self._log("Migrated component config with list-based mapping")
        return component_config
    
    def _migrate_asset_config(self, v13_config: Dict[str, Any]) -> AssetConfig:
        """Migrate to new AssetConfig structure"""
        v13_assets = v13_config.get("assets", {})
        
        # Use existing assets_root or default
        assets_root_str = v13_assets.get("assets_root")
        if assets_root_str:
            assets_root = Path(assets_root_str).expanduser()
        else:
            assets_root = Path(os.getenv("IRENE_ASSETS_ROOT", "~/.cache/irene")).expanduser()
        
        asset_config = AssetConfig(
            assets_root=assets_root,
            auto_create_dirs=v13_assets.get("auto_create_dirs", True)
        )
        
        self._log(f"Migrated asset config: assets_root={assets_root}")
        return asset_config
    
    def _migrate_workflow_config(self, v13_config: Dict[str, Any]) -> WorkflowConfig:
        """Migrate to new WorkflowConfig structure"""
        # Default v14 workflow configuration
        workflow_config = WorkflowConfig(
            enabled=["unified_voice_assistant"],
            default="unified_voice_assistant"
        )
        
        self._log("Created default workflow config")
        return workflow_config
    
    def _migrate_component_specific_configs(self, v13_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate component-specific configurations"""
        component_configs = {}
        v13_plugins = v13_config.get("plugins", {})
        
        # Migrate TTS config
        component_configs["tts"] = self._migrate_tts_config(v13_plugins)
        
        # Migrate Audio config
        component_configs["audio"] = self._migrate_audio_config(v13_plugins)
        
        # Migrate ASR config
        component_configs["asr"] = self._migrate_asr_config(v13_plugins)
        
        # Migrate LLM config
        component_configs["llm"] = self._migrate_llm_config(v13_plugins)
        
        # Migrate Voice Trigger config
        component_configs["voice_trigger"] = self._migrate_voice_trigger_config(v13_config)
        
        # Migrate NLU config
        component_configs["nlu"] = self._migrate_nlu_config(v13_plugins)
        
        # Migrate Text Processor config
        component_configs["text_processor"] = self._migrate_text_processor_config(v13_plugins)
        
        # Migrate Intent System config
        component_configs["intent_system"] = self._migrate_intent_system_config(v13_config)
        
        self._log("Migrated all component-specific configurations")
        return component_configs
    
    def _migrate_tts_config(self, v13_plugins: Dict[str, Any]) -> TTSConfig:
        """Migrate TTS configuration from v13 universal_tts plugin"""
        v13_tts = v13_plugins.get("universal_tts", {})
        
        tts_config = TTSConfig(
            enabled=v13_tts.get("enabled", False),
            default_provider=v13_tts.get("default_provider", "console"),
            fallback_providers=v13_tts.get("fallback_providers", ["console"]),
            providers=self._migrate_tts_providers(v13_tts.get("providers", {}))
        )
        
        self._log("Migrated TTS configuration")
        return tts_config
    
    def _migrate_audio_config(self, v13_plugins: Dict[str, Any]) -> AudioConfig:
        """Migrate Audio configuration from v13 universal_audio plugin"""
        v13_audio = v13_plugins.get("universal_audio", {})
        
        audio_config = AudioConfig(
            enabled=v13_audio.get("enabled", False),
            default_provider=v13_audio.get("default_provider", "console"),
            fallback_providers=v13_audio.get("fallback_providers", ["console"]),
            concurrent_playback=v13_audio.get("concurrent_playback", False),
            providers=v13_audio.get("providers", {})
        )
        
        self._log("Migrated Audio configuration")
        return audio_config
    
    def _migrate_asr_config(self, v13_plugins: Dict[str, Any]) -> ASRConfig:
        """Migrate ASR configuration from v13 universal_asr plugin"""
        v13_asr = v13_plugins.get("universal_asr", {})
        
        asr_config = ASRConfig(
            enabled=v13_asr.get("enabled", False),
            default_provider=v13_asr.get("default_provider", "whisper"),
            fallback_providers=v13_asr.get("fallback_providers", ["whisper"]),
            providers=self._migrate_asr_providers(v13_asr.get("providers", {}))
        )
        
        self._log("Migrated ASR configuration")
        return asr_config
    
    def _migrate_llm_config(self, v13_plugins: Dict[str, Any]) -> LLMConfig:
        """Migrate LLM configuration from v13 universal_llm plugin"""
        v13_llm = v13_plugins.get("universal_llm", {})
        
        llm_config = LLMConfig(
            enabled=v13_llm.get("enabled", False),
            default_provider=v13_llm.get("default_provider", "openai"),
            fallback_providers=v13_llm.get("fallback_providers", ["console"]),
            providers=self._migrate_llm_providers(v13_llm.get("providers", {}))
        )
        
        self._log("Migrated LLM configuration")
        return llm_config
    
    def _migrate_voice_trigger_config(self, v13_config: Dict[str, Any]) -> VoiceTriggerConfig:
        """Migrate Voice Trigger configuration"""
        # Check if voice trigger was configured in v13
        v13_voice_trigger = v13_config.get("voice_trigger", {})
        
        voice_trigger_config = VoiceTriggerConfig(
            enabled=v13_voice_trigger.get("enabled", False),
            default_provider=v13_voice_trigger.get("default_provider", "openwakeword"),
            wake_words=v13_voice_trigger.get("wake_words", ["irene", "jarvis"]),
            confidence_threshold=v13_voice_trigger.get("confidence_threshold", 0.8),
            buffer_seconds=v13_voice_trigger.get("buffer_seconds", 1.0),
            timeout_seconds=v13_voice_trigger.get("timeout_seconds", 5.0),
            providers=v13_voice_trigger.get("providers", {})
        )
        
        self._log("Migrated Voice Trigger configuration")
        return voice_trigger_config
    
    def _migrate_nlu_config(self, v13_plugins: Dict[str, Any]) -> NLUConfig:
        """Migrate NLU configuration from v13 universal_nlu plugin"""
        v13_nlu = v13_plugins.get("universal_nlu", {})
        
        nlu_config = NLUConfig(
            enabled=v13_nlu.get("enabled", False),
            default_provider=v13_nlu.get("default_provider", "hybrid_keyword_matcher"),
            confidence_threshold=v13_nlu.get("confidence_threshold", 0.7),
            fallback_intent=v13_nlu.get("fallback_intent", "conversation.general"),
            provider_cascade_order=v13_nlu.get("provider_cascade_order", ["hybrid_keyword_matcher", "spacy_nlu"]),
            max_cascade_attempts=v13_nlu.get("max_cascade_attempts", 4),
            cascade_timeout_ms=v13_nlu.get("cascade_timeout_ms", 200),
            cache_recognition_results=v13_nlu.get("cache_recognition_results", False),
            cache_ttl_seconds=v13_nlu.get("cache_ttl_seconds", 300),
            providers=v13_nlu.get("providers", {})
        )
        
        self._log("Migrated NLU configuration")
        return nlu_config
    
    def _migrate_text_processor_config(self, v13_plugins: Dict[str, Any]) -> TextProcessorConfig:
        """Migrate Text Processor configuration from v13 text_processing plugin"""
        v13_text_proc = v13_plugins.get("text_processing", {})
        
        text_processor_config = TextProcessorConfig(
            enabled=v13_text_proc.get("enabled", False),
            stages=v13_text_proc.get("stages", ["asr_output", "tts_input", "command_input", "general"]),
            normalizers=v13_text_proc.get("normalizers", {})
        )
        
        self._log("Migrated Text Processor configuration")
        return text_processor_config
    
    def _migrate_intent_system_config(self, v13_config: Dict[str, Any]) -> IntentSystemConfig:
        """Migrate Intent System configuration"""
        v13_intents = v13_config.get("intents", {})
        
        intent_system_config = IntentSystemConfig(
            enabled=v13_intents.get("enabled", True),
            confidence_threshold=v13_intents.get("confidence_threshold", 0.7),
            fallback_intent=v13_intents.get("fallback_handler", "conversation.general"),
            handlers=self._migrate_intent_handlers(v13_intents)
        )
        
        self._log("Migrated Intent System configuration")
        return intent_system_config
    
    def _migrate_tts_providers(self, v13_providers: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate TTS providers with environment variable patterns"""
        migrated_providers = {}
        
        for provider_name, provider_config in v13_providers.items():
            migrated_config = dict(provider_config)
            
            # Convert API key patterns
            if "api_key_env" in migrated_config:
                env_var = migrated_config.pop("api_key_env")
                if env_var:
                    migrated_config["api_key"] = f"${{{env_var}}}"
                elif provider_name == "elevenlabs":
                    migrated_config["api_key"] = "${ELEVENLABS_API_KEY}"
            
            migrated_providers[provider_name] = migrated_config
        
        return migrated_providers
    
    def _migrate_asr_providers(self, v13_providers: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate ASR providers with environment variable patterns"""
        migrated_providers = {}
        
        for provider_name, provider_config in v13_providers.items():
            migrated_config = dict(provider_config)
            
            # Convert credentials patterns
            if provider_name == "google_cloud" and "credentials_path" not in migrated_config:
                migrated_config["credentials_path"] = "${GOOGLE_APPLICATION_CREDENTIALS}"
            
            migrated_providers[provider_name] = migrated_config
        
        return migrated_providers
    
    def _migrate_llm_providers(self, v13_providers: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate LLM providers with environment variable patterns"""
        migrated_providers = {}
        
        for provider_name, provider_config in v13_providers.items():
            migrated_config = dict(provider_config)
            
            # Convert API key patterns
            if "api_key_env" in migrated_config:
                env_var = migrated_config.pop("api_key_env")
                if provider_name == "openai":
                    migrated_config["api_key"] = "${OPENAI_API_KEY}"
                elif provider_name == "anthropic":
                    migrated_config["api_key"] = "${ANTHROPIC_API_KEY}"
                elif env_var:
                    migrated_config["api_key"] = f"${{{env_var}}}"
            
            migrated_providers[provider_name] = migrated_config
        
        return migrated_providers
    
    def _migrate_intent_handlers(self, v13_intents: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate intent handler configuration"""
        handlers_config = {
            "enabled": ["conversation", "greetings", "timer", "datetime", "system"],
            "disabled": ["train_schedule"],
            "auto_discover": True,
            "discovery_paths": ["irene.intents.handlers"]
        }
        
        # Extract handler configuration if it exists
        if "handlers" in v13_intents:
            v13_handlers = v13_intents["handlers"]
            if "enabled" in v13_handlers:
                handlers_config["enabled"] = v13_handlers["enabled"]
            if "disabled" in v13_handlers:
                handlers_config["disabled"] = v13_handlers["disabled"]
            if "auto_discover" in v13_handlers:
                handlers_config["auto_discover"] = v13_handlers["auto_discover"]
        
        return handlers_config
    
    def _infer_asr_enabled(self, v13_plugins: Dict[str, Any]) -> bool:
        """Infer if ASR is enabled from v13 plugin configuration"""
        return v13_plugins.get("universal_asr", {}).get("enabled", False)
    
    def _infer_llm_enabled(self, v13_plugins: Dict[str, Any]) -> bool:
        """Infer if LLM is enabled from v13 plugin configuration"""
        return v13_plugins.get("universal_llm", {}).get("enabled", False)
    
    def _infer_voice_trigger_enabled(self, v13_config: Dict[str, Any]) -> bool:
        """Infer if voice trigger is enabled from v13 configuration"""
        return v13_config.get("voice_trigger", {}).get("enabled", False)
    
    def _infer_nlu_enabled(self, v13_plugins: Dict[str, Any]) -> bool:
        """Infer if NLU is enabled from v13 plugin configuration"""
        return v13_plugins.get("universal_nlu", {}).get("enabled", False)
    
    def _infer_text_processor_enabled(self, v13_plugins: Dict[str, Any]) -> bool:
        """Infer if text processor is enabled from v13 plugin configuration"""
        return v13_plugins.get("text_processing", {}).get("enabled", False)
    
    def _log(self, message: str) -> None:
        """Add message to migration log"""
        self.migration_log.append(message)
        logger.info(f"Migration: {message}")
    
    def _log_migration_summary(self) -> None:
        """Log migration summary"""
        summary = f"Migration completed with {len(self.migration_log)} steps"
        logger.info(summary)
        for step in self.migration_log:
            logger.debug(f"  - {step}")
    
    def get_migration_log(self) -> List[str]:
        """Get migration log"""
        return self.migration_log.copy()


class ConfigurationCompatibilityChecker:
    """Utility for checking configuration compatibility"""
    
    @staticmethod
    def detect_version(config: Dict[str, Any]) -> Optional[str]:
        """Detect configuration version"""
        # Check explicit version field
        if "version" in config:
            version = config["version"]
            if isinstance(version, str) and version.startswith(("13.", "14.")):
                return version
        
        # Infer version from structure
        # V13 indicators
        if "plugins" in config and "universal_tts" in config.get("plugins", {}):
            return "13.x"
        
        # V13: components as list-based structure
        components = config.get("components", {})
        if isinstance(components, dict) and ("enabled" in components or "disabled" in components):
            enabled = components.get("enabled", [])
            if isinstance(enabled, list) and len(enabled) > 0:
                return "13.x"
        
        # V14: system and inputs sections with boolean component structure
        if "system" in config and "inputs" in config:
            return "14.x"
        
        return None
    
    @staticmethod
    def is_v13_config(config: Dict[str, Any]) -> bool:
        """Check if configuration is v13 format"""
        version = ConfigurationCompatibilityChecker.detect_version(config)
        return version is not None and version.startswith("13")
    
    @staticmethod
    def is_v14_config(config: Dict[str, Any]) -> bool:
        """Check if configuration is v14 format"""
        version = ConfigurationCompatibilityChecker.detect_version(config)
        return version is not None and version.startswith("14")
    
    @staticmethod
    def requires_migration(config: Dict[str, Any]) -> bool:
        """Check if configuration requires migration"""
        return ConfigurationCompatibilityChecker.is_v13_config(config)


def migrate_config(config: Union[Dict[str, Any], str, Path]) -> CoreConfig:
    """
    Migrate configuration from v13 to v14 format
    
    Args:
        config: Configuration as dict, file path, or Path object
        
    Returns:
        CoreConfig: Migrated v14 configuration
        
    Raises:
        ConfigurationMigrationError: If migration fails
    """
    # Load configuration if it's a file path
    if isinstance(config, (str, Path)):
        import tomllib
        
        config_path = Path(config)
        if not config_path.exists():
            raise ConfigurationMigrationError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
    
    # Check if migration is needed
    if not ConfigurationCompatibilityChecker.requires_migration(config):
        logger.info("Configuration is already v14 format or unknown version, no migration needed")
        return CoreConfig.model_validate(config)
    
    # Perform migration
    migrator = V13ToV14Migrator()
    return migrator.migrate(config)


def create_migration_backup(config_path: Path) -> Path:
    """Create backup of configuration file before migration"""
    backup_path = config_path.with_suffix(f"{config_path.suffix}.v13.backup")
    backup_path.write_bytes(config_path.read_bytes())
    logger.info(f"Created configuration backup: {backup_path}")
    return backup_path
