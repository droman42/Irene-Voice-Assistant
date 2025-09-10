"""
TTS-Audio Separation Tests - Phase 4 Implementation

Comprehensive tests for TTS-Audio separation architecture including:
- Configuration validation (TTS-Audio dependency)
- TTS-Audio integration with temp file coordination
- Parallel session conflict prevention
- Error condition handling
- Temp file cleanup verification
"""

import pytest
import asyncio
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from pydantic import ValidationError

from irene.config.models import CoreConfig, ComponentConfig, AssetConfig
from irene.config.manager import ConfigValidationError
from irene.workflows.voice_assistant import UnifiedVoiceAssistantWorkflow
from irene.workflows.base import RequestContext
from irene.intents.models import IntentResult
from irene.providers.tts.base import TTSProvider
from irene.providers.audio.base import AudioProvider


class TestConfigurationValidation:
    """Test configuration validation for TTS-Audio dependency checks"""
    
    def test_tts_without_audio_raises_validation_error(self):
        """Test that TTS enabled without Audio component raises ValidationError"""
        config_data = {
            "components": {
                "tts": True,
                "audio_output": False
            }
        }
        
        with pytest.raises(ValueError) as exc_info:
            CoreConfig(**config_data)
        
        # Verify the error message is about TTS requiring Audio
        error_msg = str(exc_info.value)
        assert "TTS component requires Audio component" in error_msg
    
    def test_audio_without_tts_is_valid(self):
        """Test that Audio without TTS is valid (audio-only use cases)"""
        config_data = {
            "components": {
                "tts": False,
                "audio_output": True
            }
        }
        
        # Should not raise any error
        config = CoreConfig(**config_data)
        assert config.components.tts is False
        assert config.components.audio_output is True
    
    def test_both_tts_and_audio_enabled_is_valid(self):
        """Test that both TTS and Audio enabled is valid"""
        config_data = {
            "components": {
                "tts": True,
                "audio_output": True
            }
        }
        
        # Should not raise any error
        config = CoreConfig(**config_data)
        assert config.components.tts is True
        assert config.components.audio_output is True
    
    def test_both_tts_and_audio_disabled_is_valid(self):
        """Test that both TTS and Audio disabled is valid"""
        config_data = {
            "components": {
                "tts": False,
                "audio_output": False
            }
        }
        
        # Should not raise any error
        config = CoreConfig(**config_data)
        assert config.components.tts is False
        assert config.components.audio_output is False
    
    def test_asset_config_creates_temp_directory(self):
        """Test that AssetConfig creates temp_audio_dir"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_assets_root = Path(temp_dir) / "assets"
            
            config = AssetConfig(
                assets_root=test_assets_root,
                auto_create_dirs=True
            )
            
            # Directory should be created
            assert config.temp_audio_dir.exists()
            assert config.temp_audio_dir.is_dir()
            assert config.temp_audio_dir == test_assets_root / "temp" / "audio"
    
    def test_asset_config_validates_permissions(self):
        """Test that AssetConfig validates directory permissions"""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_assets_root = Path(temp_dir) / "assets"
            
            # Should succeed with writable directory
            config = AssetConfig(
                assets_root=test_assets_root,
                auto_create_dirs=True
            )
            
            # Verify we can write to the directory
            test_file = config.temp_audio_dir / "test.txt"
            test_file.write_text("test")
            assert test_file.read_text() == "test"


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.synthesize_calls = []
        self.should_fail = False
    
    async def synthesize_to_file(self, text: str, output_path: Path, **kwargs) -> None:
        """Mock synthesize_to_file implementation"""
        self.synthesize_calls.append((text, output_path, kwargs))
        
        if self.should_fail:
            raise RuntimeError("Mock TTS failure")
        
        # Create a fake audio file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"Mock audio for: {text}")
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {"text": {"type": "string"}}
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {"languages": ["en"], "voices": ["mock"], "formats": ["wav"]}
    
    async def is_available(self) -> bool:
        """Mock is_available implementation"""
        return True
    
    def get_provider_name(self) -> str:
        """Mock get_provider_name implementation"""
        return "mock_tts"


class MockAudioProvider(AudioProvider):
    """Mock Audio provider for testing"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.play_calls = []
        self.should_fail = False
    
    async def play_file(self, file_path: Path, **kwargs) -> None:
        """Mock play_file implementation"""
        self.play_calls.append((file_path, kwargs))
        
        if self.should_fail:
            raise RuntimeError("Mock Audio failure")
        
        # Verify file exists
        if not file_path.exists():
            raise FileNotFoundError(f"Audio file not found: {file_path}")
    
    async def play_stream(self, audio_stream, **kwargs) -> None:
        """Mock play_stream implementation"""
        pass
    
    def get_parameter_schema(self) -> Dict[str, Any]:
        return {"volume": {"type": "number"}}
    
    async def is_available(self) -> bool:
        """Mock is_available implementation"""
        return True
    
    def get_provider_name(self) -> str:
        """Mock get_provider_name implementation"""
        return "mock_audio"
    
    def get_supported_formats(self) -> List[str]:
        """Mock get_supported_formats implementation"""
        return ["wav", "mp3"]
    
    async def set_volume(self, volume: float) -> None:
        """Mock set_volume implementation"""
        pass
    
    async def stop_playback(self) -> None:
        """Mock stop_playback implementation"""
        pass


class TestTTSAudioIntegration:
    """Test TTS-Audio integration with temp file coordination"""
    
    @pytest.fixture
    def temp_audio_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_tts(self):
        """Create mock TTS provider"""
        return MockTTSProvider({})
    
    @pytest.fixture
    def mock_audio(self):
        """Create mock Audio provider"""
        return MockAudioProvider({})
    
    @pytest.fixture
    def mock_config(self, temp_audio_dir):
        """Create mock configuration"""
        mock_config = Mock()
        mock_config.assets.temp_audio_dir = temp_audio_dir
        return mock_config
    
    @pytest.fixture
    def workflow(self, mock_config, mock_tts, mock_audio):
        """Create workflow with mocked components"""
        workflow = UnifiedVoiceAssistantWorkflow()
        workflow.components = {}
        workflow.add_component('config', mock_config)
        workflow.add_component('tts', mock_tts)
        workflow.add_component('audio', mock_audio)
        workflow.tts = mock_tts
        workflow.audio = mock_audio
        return workflow
    
    @pytest.mark.asyncio
    async def test_successful_tts_audio_coordination(self, workflow, mock_tts, mock_audio, temp_audio_dir):
        """Test successful TTS-Audio coordination with temp file"""
        intent_result = IntentResult(
            text="Hello, this is a test message",
            success=True,
            should_speak=True
        )
        context = RequestContext(wants_audio=True)
        
        # Execute TTS-Audio coordination
        await workflow._handle_tts_output(intent_result, context)
        
        # Verify TTS was called
        assert len(mock_tts.synthesize_calls) == 1
        text, output_path, kwargs = mock_tts.synthesize_calls[0]
        assert text == "Hello, this is a test message"
        assert output_path.parent == temp_audio_dir
        assert output_path.name.startswith("tts_")
        assert output_path.name.endswith(".wav")
        
        # Verify Audio was called
        assert len(mock_audio.play_calls) == 1
        file_path, kwargs = mock_audio.play_calls[0]
        assert file_path == output_path
        
        # Verify temp file was cleaned up
        assert not output_path.exists()
    
    @pytest.mark.asyncio
    async def test_uuid_based_temp_file_naming(self, workflow, mock_tts, mock_audio, temp_audio_dir):
        """Test that temp files use UUID-based naming for parallel safety"""
        intent_result = IntentResult(
            text="Test message",
            success=True,
            should_speak=True
        )
        context = RequestContext(wants_audio=True)
        
        # Execute multiple times to check naming pattern
        temp_files = []
        for _ in range(3):
            await workflow._handle_tts_output(intent_result, context)
            if mock_tts.synthesize_calls:
                _, output_path, _ = mock_tts.synthesize_calls[-1]
                temp_files.append(output_path.name)
        
        # Verify all filenames are unique and follow pattern
        assert len(set(temp_files)) == 3  # All unique
        for filename in temp_files:
            assert filename.startswith("tts_")
            assert filename.endswith(".wav")
            assert len(filename) == 40  # "tts_" + 32 hex chars + ".wav"
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_success(self, workflow, mock_tts, mock_audio, temp_audio_dir):
        """Test that temp files are cleaned up on successful execution"""
        intent_result = IntentResult(
            text="Test cleanup",
            success=True,
            should_speak=True
        )
        context = RequestContext(wants_audio=True)
        
        # Track temp file path
        await workflow._handle_tts_output(intent_result, context)
        
        _, temp_path, _ = mock_tts.synthesize_calls[0]
        
        # Verify temp file was cleaned up
        assert not temp_path.exists()
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_tts_failure(self, workflow, mock_tts, mock_audio, temp_audio_dir):
        """Test that temp files are cleaned up even when TTS fails"""
        intent_result = IntentResult(
            text="Test TTS failure",
            success=True,
            should_speak=True
        )
        context = RequestContext(wants_audio=True)
        
        # Make TTS fail
        mock_tts.should_fail = True
        
        # Execute should not raise but should handle error
        await workflow._handle_tts_output(intent_result, context)
        
        # Verify no temp files left behind
        temp_files = list(temp_audio_dir.glob("tts_*.wav"))
        assert len(temp_files) == 0
    
    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_audio_failure(self, workflow, mock_tts, mock_audio, temp_audio_dir):
        """Test that temp files are cleaned up even when Audio fails"""
        intent_result = IntentResult(
            text="Test Audio failure",
            success=True,
            should_speak=True
        )
        context = RequestContext(wants_audio=True)
        
        # Make Audio fail
        mock_audio.should_fail = True
        
        # Execute should not raise but should handle error
        await workflow._handle_tts_output(intent_result, context)
        
        # Verify no temp files left behind
        temp_files = list(temp_audio_dir.glob("tts_*.wav"))
        assert len(temp_files) == 0


class TestParallelSessionConflicts:
    """Test parallel session conflict prevention with UUID-based naming"""
    
    @pytest.fixture
    def temp_audio_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_parallel_sessions_no_file_conflicts(self, temp_audio_dir):
        """Test that parallel sessions don't have file name conflicts"""
        
        async def create_temp_file():
            """Simulate temp file creation like in workflow"""
            temp_filename = f"tts_{uuid.uuid4().hex}.wav"
            temp_path = temp_audio_dir / temp_filename
            temp_path.write_text("test")
            return temp_path
        
        # Simulate 10 parallel sessions
        tasks = [create_temp_file() for _ in range(10)]
        temp_paths = await asyncio.gather(*tasks)
        
        # Verify all paths are unique
        path_names = [p.name for p in temp_paths]
        assert len(set(path_names)) == 10  # All unique
        
        # Verify all files exist
        for temp_path in temp_paths:
            assert temp_path.exists()
            temp_path.unlink()  # Cleanup
    
    @pytest.mark.asyncio
    async def test_uuid_collision_resistance(self, temp_audio_dir):
        """Test that UUID generation is collision-resistant over many iterations"""
        filenames = set()
        
        # Generate 1000 UUID-based filenames
        for _ in range(1000):
            temp_filename = f"tts_{uuid.uuid4().hex}.wav"
            filenames.add(temp_filename)
        
        # Should have 1000 unique filenames
        assert len(filenames) == 1000


class TestErrorConditionHandling:
    """Test error condition handling for TTS/Audio failures"""
    
    @pytest.fixture
    def temp_audio_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def workflow_with_failing_components(self, temp_audio_dir):
        """Create workflow with components that can be made to fail"""
        mock_config = Mock()
        mock_config.assets.temp_audio_dir = temp_audio_dir
        
        mock_tts = MockTTSProvider({})
        mock_audio = MockAudioProvider({})
        
        workflow = UnifiedVoiceAssistantWorkflow()
        workflow.components = {}
        workflow.add_component('config', mock_config)
        workflow.add_component('tts', mock_tts)
        workflow.add_component('audio', mock_audio)
        workflow.tts = mock_tts
        workflow.audio = mock_audio
        
        return workflow, mock_tts, mock_audio
    
    @pytest.mark.asyncio
    async def test_missing_tts_component_graceful_handling(self, temp_audio_dir):
        """Test graceful handling when TTS component is missing"""
        mock_config = Mock()
        mock_config.assets.temp_audio_dir = temp_audio_dir
        
        workflow = UnifiedVoiceAssistantWorkflow()
        workflow.components = {}
        workflow.add_component('config', mock_config)
        workflow.tts = None
        workflow.audio = MockAudioProvider({})
        
        intent_result = IntentResult(text="Test", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Should not raise error, just return early
        await workflow._handle_tts_output(intent_result, context)
        
        # No temp files should be created
        temp_files = list(temp_audio_dir.glob("tts_*.wav"))
        assert len(temp_files) == 0
    
    @pytest.mark.asyncio
    async def test_missing_audio_component_graceful_handling(self, temp_audio_dir):
        """Test graceful handling when Audio component is missing"""
        mock_config = Mock()
        mock_config.assets.temp_audio_dir = temp_audio_dir
        
        workflow = UnifiedVoiceAssistantWorkflow()
        workflow.components = {}
        workflow.add_component('config', mock_config)
        workflow.tts = MockTTSProvider({})
        workflow.audio = None
        
        intent_result = IntentResult(text="Test", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Should not raise error, just return early
        await workflow._handle_tts_output(intent_result, context)
        
        # No temp files should be created
        temp_files = list(temp_audio_dir.glob("tts_*.wav"))
        assert len(temp_files) == 0
    
    @pytest.mark.asyncio
    async def test_tts_failure_error_handling(self, workflow_with_failing_components):
        """Test error handling when TTS component fails"""
        workflow, mock_tts, mock_audio = workflow_with_failing_components
        
        # Make TTS fail
        mock_tts.should_fail = True
        
        intent_result = IntentResult(text="Test TTS failure", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Should not raise error but handle gracefully
        await workflow._handle_tts_output(intent_result, context)
        
        # TTS should have been called
        assert len(mock_tts.synthesize_calls) == 1
        
        # Audio should not have been called due to TTS failure
        assert len(mock_audio.play_calls) == 0
    
    @pytest.mark.asyncio
    async def test_audio_failure_error_handling(self, workflow_with_failing_components):
        """Test error handling when Audio component fails"""
        workflow, mock_tts, mock_audio = workflow_with_failing_components
        
        # Make Audio fail
        mock_audio.should_fail = True
        
        intent_result = IntentResult(text="Test Audio failure", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Should not raise error but handle gracefully
        await workflow._handle_tts_output(intent_result, context)
        
        # Both TTS and Audio should have been called
        assert len(mock_tts.synthesize_calls) == 1
        assert len(mock_audio.play_calls) == 1


class TestTempFileCleanupVerification:
    """Test comprehensive temp file cleanup verification"""
    
    @pytest.fixture
    def temp_audio_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def workflow_with_cleanup_tracking(self, temp_audio_dir):
        """Create workflow that tracks cleanup operations"""
        mock_config = Mock()
        mock_config.assets.temp_audio_dir = temp_audio_dir
        
        workflow = UnifiedVoiceAssistantWorkflow()
        workflow.components = {}
        workflow.add_component('config', mock_config)
        workflow.add_component('tts', MockTTSProvider({}))
        workflow.add_component('audio', MockAudioProvider({}))
        workflow.tts = workflow.components['tts']
        workflow.audio = workflow.components['audio']
        
        return workflow
    
    @pytest.mark.asyncio
    async def test_cleanup_verification_successful_case(self, workflow_with_cleanup_tracking, temp_audio_dir):
        """Test that cleanup works in successful execution case"""
        intent_result = IntentResult(text="Cleanup test", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Record initial file count
        initial_files = list(temp_audio_dir.glob("*"))
        initial_count = len(initial_files)
        
        # Execute workflow
        await workflow_with_cleanup_tracking._handle_tts_output(intent_result, context)
        
        # Verify no additional files remain
        final_files = list(temp_audio_dir.glob("*"))
        final_count = len(final_files)
        
        assert final_count == initial_count
    
    @pytest.mark.asyncio
    async def test_cleanup_verification_with_pre_existing_files(self, workflow_with_cleanup_tracking, temp_audio_dir):
        """Test cleanup doesn't affect pre-existing files"""
        # Create some pre-existing files
        existing_file1 = temp_audio_dir / "existing1.wav"
        existing_file2 = temp_audio_dir / "existing2.wav"
        existing_file1.write_text("existing")
        existing_file2.write_text("existing")
        
        intent_result = IntentResult(text="Cleanup test", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Execute workflow
        await workflow_with_cleanup_tracking._handle_tts_output(intent_result, context)
        
        # Verify pre-existing files are still there
        assert existing_file1.exists()
        assert existing_file2.exists()
        assert existing_file1.read_text() == "existing"
        assert existing_file2.read_text() == "existing"
        
        # Verify no new files remain
        all_files = list(temp_audio_dir.glob("*"))
        assert len(all_files) == 2  # Only the pre-existing files
    
    @pytest.mark.asyncio
    async def test_cleanup_verification_multiple_sessions(self, workflow_with_cleanup_tracking, temp_audio_dir):
        """Test cleanup works correctly with multiple sequential sessions"""
        intent_result = IntentResult(text="Multi-session test", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Execute multiple sessions
        for i in range(5):
            await workflow_with_cleanup_tracking._handle_tts_output(intent_result, context)
            
            # After each session, verify no temp files remain
            temp_files = list(temp_audio_dir.glob("tts_*.wav"))
            assert len(temp_files) == 0, f"Session {i+1} left temp files behind"
    
    @pytest.mark.asyncio
    async def test_cleanup_verification_with_exceptions(self, workflow_with_cleanup_tracking, temp_audio_dir):
        """Test cleanup works even when exceptions occur"""
        intent_result = IntentResult(text="Exception test", success=True, should_speak=True)
        context = RequestContext(wants_audio=True)
        
        # Make components fail
        workflow_with_cleanup_tracking.tts.should_fail = True
        workflow_with_cleanup_tracking.audio.should_fail = True
        
        # Execute workflow (should handle errors gracefully)
        await workflow_with_cleanup_tracking._handle_tts_output(intent_result, context)
        
        # Verify no temp files remain even after failures
        temp_files = list(temp_audio_dir.glob("tts_*.wav"))
        assert len(temp_files) == 0
