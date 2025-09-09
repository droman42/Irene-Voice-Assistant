"""
Phase 7 Testing: Fallback provider chain testing

This module tests the complete fallback provider chain functionality for both
ASR and Voice Trigger components, ensuring robust operation when providers fail
or don't support specific sample rates.
"""

import pytest
import asyncio
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch

from irene.components.asr_component import ASRComponent
from irene.components.voice_trigger_component import VoiceTriggerComponent
from irene.intents.models import AudioData, WakeWordResult
from irene.providers.asr.base import ASRProvider
from irene.providers.voice_trigger.base import VoiceTriggerProvider


class MockFailingASRProvider(ASRProvider):
    """Mock ASR provider that fails under certain conditions."""
    
    def __init__(self, name: str, supported_rates: List[int], failure_mode: str = "none"):
        self.name = name
        self.supported_rates = supported_rates
        self.failure_mode = failure_mode  # "none", "always", "sample_rate", "random"
        self.call_count = 0
    
    def get_provider_name(self) -> str:
        return self.name
    
    def get_preferred_sample_rates(self) -> List[int]:
        return self.supported_rates
    
    def supports_sample_rate(self, rate: int) -> bool:
        return rate in self.supported_rates
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        self.call_count += 1
        
        if self.failure_mode == "always":
            raise Exception(f"Provider {self.name} always fails")
        elif self.failure_mode == "sample_rate":
            # Fail if audio doesn't match expected sample rate
            raise Exception(f"Provider {self.name} doesn't support this sample rate")
        elif self.failure_mode == "random" and self.call_count % 3 == 0:
            raise Exception(f"Provider {self.name} random failure #{self.call_count}")
        
        return f"Transcription from {self.name} (call #{self.call_count})"
    
    async def transcribe_stream(self, audio_stream, **kwargs):
        """Mock streaming transcription."""
        async for chunk in audio_stream:
            yield await self.transcribe_audio(chunk, **kwargs)
    
    async def is_available(self) -> bool:
        return self.failure_mode != "always"
    
    def get_supported_languages(self) -> List[str]:
        return ["en", "ru"]
    
    def get_supported_formats(self) -> List[str]:
        return ["pcm16"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {"sample_rates": self.supported_rates, "failure_mode": self.failure_mode}
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {}


class MockFailingVoiceTriggerProvider(VoiceTriggerProvider):
    """Mock Voice Trigger provider that fails under certain conditions."""
    
    def __init__(self, name: str, supported_rates: List[int], failure_mode: str = "none", supports_resampling: bool = False):
        self.name = name
        self.supported_rates = supported_rates
        self.failure_mode = failure_mode
        self._supports_resampling = supports_resampling
        self.call_count = 0
    
    def get_provider_name(self) -> str:
        return self.name
    
    def get_supported_sample_rates(self) -> List[int]:
        return self.supported_rates
    
    def get_default_sample_rate(self) -> int:
        return self.supported_rates[0] if self.supported_rates else 16000
    
    def supports_resampling(self) -> bool:
        return self._supports_resampling
    
    def get_default_channels(self) -> int:
        return 1
    
    async def detect_wake_word(self, audio_data: AudioData) -> WakeWordResult:
        self.call_count += 1
        
        if self.failure_mode == "always":
            raise Exception(f"Provider {self.name} always fails")
        elif self.failure_mode == "sample_rate" and audio_data.sample_rate not in self.supported_rates:
            raise Exception(f"Provider {self.name} doesn't support {audio_data.sample_rate}Hz")
        elif self.failure_mode == "random" and self.call_count % 2 == 0:
            raise Exception(f"Provider {self.name} random failure #{self.call_count}")
        
        # Simulate successful detection for supported rates
        detected = audio_data.sample_rate in self.supported_rates or self._supports_resampling
        confidence = 0.9 if detected else 0.1
        
        return WakeWordResult(
            detected=detected,
            confidence=confidence,
            word="test_wake_word" if detected else None
        )
    
    async def is_available(self) -> bool:
        return self.failure_mode != "always"
    
    def get_supported_wake_words(self) -> List[str]:
        return ["test_wake_word", "irene"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "sample_rates": self.supported_rates,
            "resampling": self._supports_resampling,
            "failure_mode": self.failure_mode
        }
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {}


class TestASRFallbackChains:
    """Test ASR provider fallback chains."""
    
    def create_test_audio_data(self, sample_rate: int = 16000) -> AudioData:
        """Create test audio data."""
        return AudioData(
            data=b'\x00\x01' * 1000,
            timestamp=1234567890.0,
            sample_rate=sample_rate,
            channels=1,
            format="pcm16",
            metadata={}
        )
    
    @pytest.mark.asyncio
    async def test_primary_provider_failure_fallback(self):
        """Test fallback when primary ASR provider fails completely."""
        # Create providers: primary fails, backup works
        primary = MockFailingASRProvider("primary", [16000, 44100], failure_mode="always")
        backup = MockFailingASRProvider("backup", [16000, 44100], failure_mode="none")
        
        # Set up ASR component
        asr_component = ASRComponent()
        asr_component.providers = {"primary": primary, "backup": backup}
        asr_component.default_provider = "primary"
        
        # Test fallback mechanism
        audio_data = self.create_test_audio_data(16000)
        
        # Should fall back to backup provider
        result = await asr_component._handle_sample_rate_mismatch(audio_data, primary)
        
        assert isinstance(result, str)
        assert "backup" in result
        assert backup.call_count > 0
        print(f"Fallback test result: {result}")
    
    @pytest.mark.asyncio
    async def test_sample_rate_compatibility_fallback(self):
        """Test fallback based on sample rate compatibility."""
        # Create providers with different sample rate support
        strict_provider = MockFailingASRProvider("strict", [16000], failure_mode="sample_rate")
        flexible_provider = MockFailingASRProvider("flexible", [8000, 16000, 44100, 48000], failure_mode="none")
        
        # Set up ASR component
        asr_component = ASRComponent()
        asr_component.providers = {"strict": strict_provider, "flexible": flexible_provider}
        asr_component.default_provider = "strict"
        
        # Test with unsupported sample rate for primary provider
        audio_data = self.create_test_audio_data(44100)
        
        # Should fall back to flexible provider
        result = await asr_component._handle_sample_rate_mismatch(audio_data, strict_provider)
        
        assert isinstance(result, str)
        assert "flexible" in result
        assert flexible_provider.call_count > 0
        print(f"Sample rate fallback result: {result}")
    
    @pytest.mark.asyncio
    async def test_multiple_provider_fallback_chain(self):
        """Test fallback through multiple providers."""
        # Create chain: first fails, second fails, third succeeds
        provider1 = MockFailingASRProvider("provider1", [16000], failure_mode="always")
        provider2 = MockFailingASRProvider("provider2", [16000], failure_mode="always")
        provider3 = MockFailingASRProvider("provider3", [16000], failure_mode="none")
        
        # Set up ASR component
        asr_component = ASRComponent()
        asr_component.providers = {
            "provider1": provider1,
            "provider2": provider2,
            "provider3": provider3
        }
        asr_component.default_provider = "provider1"
        
        # Test fallback chain
        audio_data = self.create_test_audio_data(16000)
        
        result = await asr_component._handle_sample_rate_mismatch(audio_data, provider1)
        
        assert isinstance(result, str)
        assert "provider3" in result
        assert provider3.call_count > 0
        print(f"Chain fallback result: {result}")
    
    @pytest.mark.asyncio
    async def test_all_providers_fail_graceful_degradation(self):
        """Test graceful degradation when all providers fail."""
        # Create providers that all fail
        provider1 = MockFailingASRProvider("provider1", [16000], failure_mode="always")
        provider2 = MockFailingASRProvider("provider2", [16000], failure_mode="always")
        
        # Set up ASR component
        asr_component = ASRComponent()
        asr_component.providers = {"provider1": provider1, "provider2": provider2}
        asr_component.default_provider = "provider1"
        
        # Test graceful degradation
        audio_data = self.create_test_audio_data(16000)
        
        # Should attempt force resampling and graceful degradation
        result = await asr_component._handle_sample_rate_mismatch(audio_data, provider1)
        
        # Should return some result even if degraded
        assert isinstance(result, str)
        print(f"Graceful degradation result: {result}")
    
    @pytest.mark.asyncio
    async def test_intermittent_provider_failures(self):
        """Test handling of intermittent provider failures."""
        # Create provider that fails randomly
        intermittent_provider = MockFailingASRProvider("intermittent", [16000], failure_mode="random")
        reliable_backup = MockFailingASRProvider("reliable", [16000], failure_mode="none")
        
        # Set up ASR component
        asr_component = ASRComponent()
        asr_component.providers = {"intermittent": intermittent_provider, "reliable": reliable_backup}
        asr_component.default_provider = "intermittent"
        
        # Test multiple requests to see fallback behavior
        audio_data = self.create_test_audio_data(16000)
        results = []
        
        for i in range(6):  # Test multiple calls
            try:
                result = await asr_component.process_audio(audio_data)
                results.append(f"Call {i+1}: {result[:50]}...")
            except Exception as e:
                results.append(f"Call {i+1}: FAILED - {str(e)}")
        
        # Print results to see fallback pattern
        for result in results:
            print(result)
        
        # Should have some successful results (either primary or backup)
        successful_results = [r for r in results if "FAILED" not in r]
        assert len(successful_results) > 0, "No successful transcriptions"


class TestVoiceTriggerFallbackChains:
    """Test Voice Trigger provider fallback chains."""
    
    def create_test_audio_data(self, sample_rate: int = 16000) -> AudioData:
        """Create test audio data."""
        return AudioData(
            data=b'\x00\x01' * 1000,
            timestamp=1234567890.0,
            sample_rate=sample_rate,
            channels=1,
            format="pcm16",
            metadata={}
        )
    
    @pytest.mark.asyncio
    async def test_voice_trigger_provider_fallback(self):
        """Test voice trigger fallback when primary provider fails."""
        # Create providers: primary fails, backup works
        primary = MockFailingVoiceTriggerProvider("primary", [16000], failure_mode="always")
        backup = MockFailingVoiceTriggerProvider("backup", [16000], failure_mode="none")
        
        # Set up voice trigger component
        vt_component = VoiceTriggerComponent()
        vt_component.providers = {"primary": primary, "backup": backup}
        vt_component.default_provider = "primary"
        vt_component.fallback_providers = ["backup"]
        vt_component.active = True
        
        # Test fallback mechanism
        audio_data = self.create_test_audio_data(16000)
        
        result = await vt_component._detect_with_fallback(audio_data, "primary")
        
        assert isinstance(result, WakeWordResult)
        assert backup.call_count > 0
        print(f"VT fallback result: detected={result.detected}, confidence={result.confidence}")
    
    @pytest.mark.asyncio
    async def test_sample_rate_resampling_fallback(self):
        """Test fallback based on resampling capabilities."""
        # Create providers: strict (no resampling), flexible (with resampling)
        strict = MockFailingVoiceTriggerProvider("strict", [16000], failure_mode="sample_rate", supports_resampling=False)
        flexible = MockFailingVoiceTriggerProvider("flexible", [16000], failure_mode="none", supports_resampling=True)
        
        # Set up voice trigger component
        vt_component = VoiceTriggerComponent()
        vt_component.providers = {"strict": strict, "flexible": flexible}
        vt_component.default_provider = "strict"
        vt_component.fallback_providers = ["flexible"]
        vt_component.active = True
        
        # Test with non-supported sample rate
        audio_data = self.create_test_audio_data(44100)
        
        result = await vt_component._detect_with_fallback(audio_data, "strict")
        
        assert isinstance(result, WakeWordResult)
        assert result.detected == True  # Flexible provider should handle resampling
        assert flexible.call_count > 0
        print(f"Resampling fallback result: detected={result.detected}, provider used flexible")
    
    @pytest.mark.asyncio
    async def test_voice_trigger_fallback_chain_ordering(self):
        """Test ordered fallback chain for voice triggers."""
        # Create multiple providers with different capabilities
        provider1 = MockFailingVoiceTriggerProvider("vt1", [16000], failure_mode="always")
        provider2 = MockFailingVoiceTriggerProvider("vt2", [16000], failure_mode="always") 
        provider3 = MockFailingVoiceTriggerProvider("vt3", [16000], failure_mode="none")
        
        # Set up voice trigger component with ordered fallbacks
        vt_component = VoiceTriggerComponent()
        vt_component.providers = {"vt1": provider1, "vt2": provider2, "vt3": provider3}
        vt_component.default_provider = "vt1"
        vt_component.fallback_providers = ["vt2", "vt3"]  # Order matters
        vt_component.active = True
        
        # Test fallback chain
        audio_data = self.create_test_audio_data(16000)
        
        result = await vt_component._detect_with_fallback(audio_data, "vt1")
        
        assert isinstance(result, WakeWordResult)
        assert provider3.call_count > 0  # Should reach the working provider
        print(f"Ordered fallback result: detected={result.detected}, final provider: vt3")
    
    @pytest.mark.asyncio
    async def test_voice_trigger_no_fallback_available(self):
        """Test behavior when no fallback providers are available."""
        # Create single failing provider
        failing_provider = MockFailingVoiceTriggerProvider("only", [16000], failure_mode="always")
        
        # Set up voice trigger component with no fallbacks
        vt_component = VoiceTriggerComponent()
        vt_component.providers = {"only": failing_provider}
        vt_component.default_provider = "only"
        vt_component.fallback_providers = []  # No fallbacks
        vt_component.active = True
        
        # Test graceful handling
        audio_data = self.create_test_audio_data(16000)
        
        result = await vt_component._detect_with_fallback(audio_data, "only")
        
        assert isinstance(result, WakeWordResult)
        assert result.detected == False  # Should gracefully fail
        assert result.confidence == 0.0
        print(f"No fallback result: detected={result.detected}, confidence={result.confidence}")


class TestComplexFallbackScenarios:
    """Test complex fallback scenarios with realistic conditions."""
    
    def create_mock_core_with_config(self, config: Dict[str, Any]):
        """Create mock core with specific configuration."""
        mock_core = Mock()
        mock_core.config = Mock()
        
        # Set up ASR config
        if 'asr' in config:
            mock_asr_config = Mock()
            mock_asr_config.model_dump.return_value = config['asr']
            mock_core.config.asr = mock_asr_config
        
        # Set up Voice Trigger config
        if 'voice_trigger' in config:
            mock_vt_config = Mock()
            mock_vt_config.model_dump.return_value = config['voice_trigger']
            mock_core.config.voice_trigger = mock_vt_config
        
        return mock_core
    
    @pytest.mark.asyncio
    async def test_realistic_hardware_failure_scenario(self):
        """Test realistic scenario where hardware-specific providers fail."""
        # Simulate scenario where hardware-optimized providers fail
        # but software fallbacks work
        
        # Hardware-optimized provider (fails on non-native sample rates)
        hw_optimized = MockFailingASRProvider("hw_optimized", [48000], failure_mode="sample_rate")
        
        # Software fallback (more flexible but slower)
        sw_fallback = MockFailingASRProvider("sw_fallback", [8000, 16000, 22050, 44100, 48000], failure_mode="none")
        
        # Set up ASR component
        asr_component = ASRComponent()
        asr_component.providers = {"hw_optimized": hw_optimized, "sw_fallback": sw_fallback}
        asr_component.default_provider = "hw_optimized"
        
        # Simulate microphone providing 16kHz audio (common rate)
        audio_data = AudioData(
            data=b'\x00\x01' * 1600,  # 1600 samples = 100ms at 16kHz
            timestamp=1234567890.0,
            sample_rate=16000,
            channels=1,
            format="pcm16",
            metadata={'source': 'microphone'}
        )
        
        # Test fallback behavior
        result = await asr_component._handle_sample_rate_mismatch(audio_data, hw_optimized)
        
        assert isinstance(result, str)
        assert sw_fallback.call_count > 0
        print(f"Hardware failure fallback: {result}")
    
    @pytest.mark.asyncio 
    async def test_cascading_failure_recovery(self):
        """Test recovery from cascading failures across multiple components."""
        # Scenario: Multiple providers fail in sequence, system should recover
        
        providers = {}
        for i in range(5):
            # Create providers that fail intermittently
            failure_mode = "random" if i < 3 else "none"  # First 3 fail, last 2 work
            providers[f"provider_{i}"] = MockFailingASRProvider(
                f"provider_{i}", 
                [16000], 
                failure_mode=failure_mode
            )
        
        # Set up component
        asr_component = ASRComponent()
        asr_component.providers = providers
        asr_component.default_provider = "provider_0"
        
        # Test multiple requests to see recovery
        audio_data = AudioData(
            data=b'\x00\x01' * 1000,
            timestamp=1234567890.0,
            sample_rate=16000,
            channels=1,
            format="pcm16",
            metadata={}
        )
        
        success_count = 0
        total_attempts = 10
        
        for attempt in range(total_attempts):
            try:
                result = await asr_component._handle_sample_rate_mismatch(audio_data, providers["provider_0"])
                if isinstance(result, str) and len(result) > 0:
                    success_count += 1
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
        
        success_rate = success_count / total_attempts
        print(f"Cascading failure recovery: {success_count}/{total_attempts} successful ({success_rate:.1%})")
        
        # Should have reasonable success rate despite failures
        assert success_rate >= 0.5, f"Recovery rate {success_rate:.1%} too low"
    
    @pytest.mark.asyncio
    async def test_configuration_driven_fallback_preferences(self):
        """Test that fallback behavior respects configuration preferences."""
        # Create providers with different characteristics
        fast_low_quality = MockFailingASRProvider("fast", [16000], failure_mode="none")
        slow_high_quality = MockFailingASRProvider("quality", [16000], failure_mode="none") 
        
        # Simulate different configurations
        configs = [
            {
                'asr': {
                    'allow_resampling': True,
                    'resample_quality': 'fast',
                    'preferred_providers': ['fast', 'quality']
                }
            },
            {
                'asr': {
                    'allow_resampling': True,
                    'resample_quality': 'high',
                    'preferred_providers': ['quality', 'fast']
                }
            }
        ]
        
        for config in configs:
            mock_core = self.create_mock_core_with_config(config)
            
            asr_component = ASRComponent()
            asr_component.core = mock_core
            asr_component.providers = {"fast": fast_low_quality, "quality": slow_high_quality}
            asr_component.default_provider = "fast" if config['asr']['resample_quality'] == 'fast' else "quality"
            
            audio_data = AudioData(
                data=b'\x00\x01' * 1000,
                timestamp=1234567890.0,
                sample_rate=44100,  # Requires resampling
                channels=1,
                format="pcm16",
                metadata={}
            )
            
            # Test processing respects configuration
            result = await asr_component.process_audio(audio_data)
            
            assert isinstance(result, str)
            expected_provider = "fast" if config['asr']['resample_quality'] == 'fast' else "quality"
            assert expected_provider in result
            print(f"Config-driven fallback: {config['asr']['resample_quality']} -> {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
