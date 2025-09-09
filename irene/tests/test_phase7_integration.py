"""
Phase 7 Testing: Integration tests with real audio hardware simulation

This module provides integration tests that simulate real audio hardware scenarios,
testing the complete audio processing pipeline from components through providers.
"""

import pytest
import asyncio
import time
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Import components and providers for integration testing
from irene.components.asr_component import ASRComponent
from irene.components.voice_trigger_component import VoiceTriggerComponent
from irene.intents.models import AudioData, WakeWordResult
from irene.utils.audio_helpers import AudioProcessor, ConversionMethod


class MockCore:
    """Mock core object for testing component initialization."""
    
    def __init__(self, config_dict: Dict[str, Any]):
        self.config = Mock()
        # Set up config attributes
        for key, value in config_dict.items():
            setattr(self.config, key, Mock())
            getattr(self.config, key).model_dump.return_value = value


class MockASRProvider:
    """Mock ASR provider for testing."""
    
    def __init__(self, name: str, supported_rates: List[int]):
        self.name = name
        self.supported_rates = supported_rates
    
    def get_provider_name(self) -> str:
        return self.name
    
    def get_preferred_sample_rates(self) -> List[int]:
        return self.supported_rates
    
    def supports_sample_rate(self, rate: int) -> bool:
        return rate in self.supported_rates
    
    async def transcribe_audio(self, audio_data: bytes, **kwargs) -> str:
        return f"Mock transcription from {self.name}"
    
    async def is_available(self) -> bool:
        return True
    
    def get_supported_languages(self) -> List[str]:
        return ["en", "ru"]
    
    def get_supported_formats(self) -> List[str]:
        return ["pcm16"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {"sample_rates": self.supported_rates}
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {}


class MockVoiceTriggerProvider:
    """Mock voice trigger provider for testing."""
    
    def __init__(self, name: str, supported_rates: List[int], supports_resampling: bool = False):
        self.name = name
        self.supported_rates = supported_rates
        self._supports_resampling = supports_resampling
    
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
        # Simulate detection based on audio properties
        detected = audio_data.sample_rate in self.supported_rates
        confidence = 0.9 if detected else 0.1
        return WakeWordResult(
            detected=detected,
            confidence=confidence,
            word="test_word" if detected else None
        )
    
    async def is_available(self) -> bool:
        return True
    
    def get_supported_wake_words(self) -> List[str]:
        return ["test_word", "wake_up"]
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {"sample_rates": self.supported_rates, "resampling": self._supports_resampling}
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {}


class TestHardwareScenarios:
    """Test various audio hardware scenarios."""
    
    def create_test_audio_data(self, sample_rate: int, duration: float = 0.1) -> AudioData:
        """Create test audio data simulating microphone input."""
        # Simulate audio data size based on sample rate and duration
        samples = int(sample_rate * duration)
        data_size = samples * 2  # 16-bit PCM = 2 bytes per sample
        
        return AudioData(
            data=b'\x00\x01' * (data_size // 2),
            timestamp=time.time(),
            sample_rate=sample_rate,
            channels=1,
            format="pcm16",
            metadata={'source': 'microphone_simulation'}
        )
    
    @pytest.mark.asyncio
    async def test_microphone_16khz_to_asr_providers(self):
        """Test 16kHz microphone input with various ASR providers."""
        # Simulate different ASR providers with different requirements
        providers = {
            'vosk': MockASRProvider('vosk', [8000, 16000, 48000]),
            'whisper': MockASRProvider('whisper', [8000, 16000, 22050, 44100, 48000]),
            'google_cloud': MockASRProvider('google_cloud', [8000, 16000, 22050, 44100, 48000])
        }
        
        # Create ASR component with mock providers
        asr_component = ASRComponent()
        asr_component.providers = providers
        asr_component.default_provider = 'vosk'
        
        # Simulate microphone audio at 16kHz
        microphone_audio = self.create_test_audio_data(16000)
        
        # Test with each provider
        for provider_name in providers.keys():
            result = await asr_component.process_audio(
                microphone_audio, provider=provider_name
            )
            assert isinstance(result, str)
            assert len(result) > 0
            print(f"Provider {provider_name}: {result}")
    
    @pytest.mark.asyncio
    async def test_microphone_44khz_to_voice_trigger(self):
        """Test 44.1kHz microphone input with voice trigger providers."""
        # Simulate voice trigger providers with different capabilities
        providers = {
            'openwakeword': MockVoiceTriggerProvider('openwakeword', [8000, 16000, 44100], supports_resampling=True),
            'microwakeword': MockVoiceTriggerProvider('microwakeword', [16000], supports_resampling=False)
        }
        
        # Create voice trigger component with mock providers
        vt_component = VoiceTriggerComponent()
        vt_component.providers = providers
        vt_component.default_provider = 'openwakeword'
        vt_component.active = True
        
        # Simulate microphone audio at 44.1kHz
        microphone_audio = self.create_test_audio_data(44100)
        
        # Test with provider that supports resampling
        result1 = await vt_component.detect(microphone_audio)
        assert isinstance(result1, WakeWordResult)
        print(f"OpenWakeWord result: detected={result1.detected}, confidence={result1.confidence}")
        
        # Test fallback to provider that requires exact rate
        vt_component.default_provider = 'microwakeword'
        result2 = await vt_component.detect(microphone_audio)
        assert isinstance(result2, WakeWordResult)
        print(f"MicroWakeWord result: detected={result2.detected}, confidence={result2.confidence}")
    
    @pytest.mark.asyncio
    async def test_sample_rate_mismatch_scenarios(self):
        """Test various sample rate mismatch scenarios and fallback behavior."""
        test_scenarios = [
            {'mic_rate': 8000, 'asr_rates': [16000, 44100], 'expected_resampling': True},
            {'mic_rate': 48000, 'asr_rates': [16000], 'expected_resampling': True},
            {'mic_rate': 16000, 'asr_rates': [16000, 44100], 'expected_resampling': False},
            {'mic_rate': 96000, 'asr_rates': [8000, 16000], 'expected_resampling': True},
        ]
        
        for scenario in test_scenarios:
            # Create mock provider
            provider = MockASRProvider('test_provider', scenario['asr_rates'])
            
            # Create ASR component
            asr_component = ASRComponent()
            asr_component.providers = {'test_provider': provider}
            asr_component.default_provider = 'test_provider'
            
            # Create microphone audio
            mic_audio = self.create_test_audio_data(scenario['mic_rate'])
            
            # Test processing
            result = await asr_component.process_audio(mic_audio)
            assert isinstance(result, str)
            
            print(f"Scenario {scenario['mic_rate']}Hz -> {scenario['asr_rates']}: SUCCESS")
    
    @pytest.mark.asyncio
    async def test_real_time_streaming_simulation(self):
        """Simulate real-time audio streaming with continuous processing."""
        # Simulate audio chunks arriving in real-time
        chunk_duration = 0.1  # 100ms chunks
        total_duration = 1.0  # 1 second total
        sample_rate = 16000
        
        chunks = []
        for i in range(int(total_duration / chunk_duration)):
            chunk = self.create_test_audio_data(sample_rate, chunk_duration)
            chunk.metadata['chunk_index'] = i
            chunk.timestamp = time.time() + i * chunk_duration
            chunks.append(chunk)
        
        # Test voice trigger processing for each chunk
        vt_provider = MockVoiceTriggerProvider('streaming_test', [16000], supports_resampling=True)
        
        results = []
        processing_times = []
        
        for chunk in chunks:
            start_time = time.time()
            result = await vt_provider.detect_wake_word(chunk)
            processing_time = (time.time() - start_time) * 1000  # ms
            
            results.append(result)
            processing_times.append(processing_time)
        
        # Analyze real-time performance
        avg_processing_time = sum(processing_times) / len(processing_times)
        max_processing_time = max(processing_times)
        
        print(f"Streaming test results:")
        print(f"  Chunks processed: {len(chunks)}")
        print(f"  Average processing time: {avg_processing_time:.2f}ms")
        print(f"  Maximum processing time: {max_processing_time:.2f}ms")
        print(f"  Real-time constraint: {chunk_duration * 1000:.0f}ms")
        
        # For real-time processing, we should process faster than real-time
        assert avg_processing_time < (chunk_duration * 1000), \
            f"Average processing time {avg_processing_time:.2f}ms exceeds real-time constraint"
    
    @pytest.mark.asyncio
    async def test_concurrent_component_processing(self):
        """Test concurrent processing by ASR and Voice Trigger components."""
        # Create shared audio data
        audio_data = self.create_test_audio_data(16000)
        
        # Set up components with different configurations
        asr_component = ASRComponent()
        asr_component.providers = {'mock_asr': MockASRProvider('mock_asr', [16000, 44100])}
        asr_component.default_provider = 'mock_asr'
        
        vt_component = VoiceTriggerComponent()
        vt_component.providers = {'mock_vt': MockVoiceTriggerProvider('mock_vt', [16000])}
        vt_component.default_provider = 'mock_vt'
        vt_component.active = True
        
        # Process concurrently
        start_time = time.time()
        
        asr_task = asyncio.create_task(asr_component.process_audio(audio_data))
        vt_task = asyncio.create_task(vt_component.detect(audio_data))
        
        asr_result, vt_result = await asyncio.gather(asr_task, vt_task)
        
        total_time = (time.time() - start_time) * 1000
        
        # Verify results
        assert isinstance(asr_result, str)
        assert isinstance(vt_result, WakeWordResult)
        
        print(f"Concurrent processing completed in {total_time:.2f}ms")
        print(f"ASR result: {asr_result}")
        print(f"VT result: detected={vt_result.detected}, confidence={vt_result.confidence}")


class TestProviderFallbacks:
    """Test provider fallback chain functionality."""
    
    @pytest.mark.asyncio
    async def test_asr_provider_fallback_chain(self):
        """Test ASR provider fallback when primary provider fails."""
        # Create providers with different capabilities
        primary_provider = MockASRProvider('primary', [44100])  # Only supports 44.1kHz
        fallback_provider = MockASRProvider('fallback', [8000, 16000, 44100])  # More flexible
        
        # Mock the primary provider to fail on certain sample rates
        async def failing_transcribe(audio_data, **kwargs):
            raise Exception("Primary provider failed")
        
        primary_provider.transcribe_audio = failing_transcribe
        
        # Create ASR component with both providers
        asr_component = ASRComponent()
        asr_component.providers = {
            'primary': primary_provider,
            'fallback': fallback_provider
        }
        asr_component.default_provider = 'primary'
        
        # Test with 16kHz audio (should trigger fallback)
        audio_data = AudioData(
            data=b'\x00\x01' * 1000,
            timestamp=time.time(),
            sample_rate=16000,
            channels=1,
            format="pcm16",
            metadata={}
        )
        
        # Should fall back to the working provider
        result = await asr_component._handle_sample_rate_mismatch(
            audio_data, primary_provider
        )
        
        assert isinstance(result, str)
        assert "fallback" in result
        print(f"Fallback result: {result}")
    
    @pytest.mark.asyncio
    async def test_voice_trigger_fallback_chain(self):
        """Test voice trigger provider fallback scenarios."""
        # Create providers with different sample rate support
        strict_provider = MockVoiceTriggerProvider('strict', [16000], supports_resampling=False)
        flexible_provider = MockVoiceTriggerProvider('flexible', [8000, 16000, 44100], supports_resampling=True)
        
        # Create component with fallback configuration
        vt_component = VoiceTriggerComponent()
        vt_component.providers = {
            'strict': strict_provider,
            'flexible': flexible_provider
        }
        vt_component.default_provider = 'strict'
        vt_component.fallback_providers = ['flexible']
        vt_component.active = True
        
        # Test with 44.1kHz audio (strict provider can't handle)
        audio_data = AudioData(
            data=b'\x00\x01' * 1000,
            timestamp=time.time(),
            sample_rate=44100,
            channels=1,
            format="pcm16",
            metadata={}
        )
        
        # Should use fallback provider
        result = await vt_component._detect_with_fallback(audio_data, 'strict')
        
        assert isinstance(result, WakeWordResult)
        # Flexible provider should handle 44.1kHz successfully
        assert result.detected == True  # Our mock returns True for supported rates
        print(f"Fallback detection result: detected={result.detected}, confidence={result.confidence}")


class TestPerformanceRegression:
    """Test for performance regressions in audio processing."""
    
    @pytest.mark.asyncio
    async def test_resampling_performance_benchmarks(self):
        """Benchmark resampling performance across different scenarios."""
        test_scenarios = [
            {'name': 'Voice Trigger (16k->16k)', 'source': 16000, 'target': 16000, 'duration': 0.1},
            {'name': 'Voice Trigger (44k->16k)', 'source': 44100, 'target': 16000, 'duration': 0.1},
            {'name': 'ASR (16k->44k)', 'source': 16000, 'target': 44100, 'duration': 0.1},
            {'name': 'ASR (48k->16k)', 'source': 48000, 'target': 16000, 'duration': 0.1},
            {'name': 'Streaming (16k->16k)', 'source': 16000, 'target': 16000, 'duration': 1.0},
        ]
        
        benchmark_results = []
        
        for scenario in test_scenarios:
            # Create test audio
            samples = int(scenario['source'] * scenario['duration'])
            audio_data = AudioData(
                data=b'\x00\x01' * samples,
                timestamp=time.time(),
                sample_rate=scenario['source'],
                channels=1,
                format="pcm16",
                metadata={}
            )
            
            # Benchmark different conversion methods
            methods = [ConversionMethod.LINEAR, ConversionMethod.POLYPHASE, ConversionMethod.SINC_KAISER]
            
            for method in methods:
                times = []
                for _ in range(5):  # Average over 5 runs
                    start_time = time.time()
                    await AudioProcessor.resample_audio_data(audio_data, scenario['target'], method)
                    duration = (time.time() - start_time) * 1000
                    times.append(duration)
                
                avg_time = sum(times) / len(times)
                benchmark_results.append({
                    'scenario': scenario['name'],
                    'method': method.value,
                    'avg_time_ms': avg_time,
                    'audio_duration_ms': scenario['duration'] * 1000
                })
        
        # Print benchmark results
        print("\nResampling Performance Benchmarks:")
        print("=" * 80)
        for result in benchmark_results:
            real_time_factor = result['avg_time_ms'] / result['audio_duration_ms']
            print(f"{result['scenario']} - {result['method']}: "
                  f"{result['avg_time_ms']:.2f}ms "
                  f"(real-time factor: {real_time_factor:.2f}x)")
        
        # Performance assertions
        voice_trigger_results = [r for r in benchmark_results if 'Voice Trigger' in r['scenario']]
        for result in voice_trigger_results:
            # Voice trigger should process faster than real-time for responsiveness
            real_time_factor = result['avg_time_ms'] / result['audio_duration_ms']
            assert real_time_factor < 0.5, \
                f"Voice trigger processing too slow: {real_time_factor:.2f}x real-time"
    
    @pytest.mark.asyncio
    async def test_cache_effectiveness(self):
        """Test caching effectiveness under realistic usage patterns."""
        # Clear cache
        AudioProcessor.clear_cache()
        
        # Simulate repeated conversions (common in real usage)
        common_conversions = [
            (44100, 16000),  # Common: 44.1kHz -> 16kHz
            (16000, 44100),  # Reverse
            (48000, 16000),  # 48kHz -> 16kHz
        ]
        
        total_operations = 0
        cache_hits = 0
        
        for _ in range(10):  # Multiple rounds
            for source_rate, target_rate in common_conversions:
                audio_data = AudioData(
                    data=b'\x00\x01' * 1000,
                    timestamp=time.time(),
                    sample_rate=source_rate,
                    channels=1,
                    format="pcm16",
                    metadata={}
                )
                
                result = await AudioProcessor.resample_audio_data(
                    audio_data, target_rate, ConversionMethod.POLYPHASE
                )
                
                total_operations += 1
                if result.metadata.get('cache_hit', False):
                    cache_hits += 1
        
        cache_hit_rate = cache_hits / total_operations
        print(f"Cache effectiveness test:")
        print(f"  Total operations: {total_operations}")
        print(f"  Cache hits: {cache_hits}")
        print(f"  Hit rate: {cache_hit_rate:.2%}")
        
        # We expect significant cache usage for repeated conversions
        assert cache_hit_rate > 0.5, f"Cache hit rate {cache_hit_rate:.2%} is too low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
