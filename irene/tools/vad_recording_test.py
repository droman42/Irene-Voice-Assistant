#!/usr/bin/env python3
"""
VAD Recording Test Script

This script records audio using the current microphone configuration and VAD pipeline,
then saves exactly what would be sent to ASR as WAV files for analysis.

Usage: 
  As entry point: irene-vad-recording-test [options]
  Direct execution: uv run python irene/tools/vad_recording_test.py [options]
  
  Use --help for full options list and examples.
"""

import argparse
import asyncio
import logging
import time
import wave
from pathlib import Path
from typing import AsyncIterator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Irene components
from irene.config.manager import ConfigManager
from irene.inputs.microphone import MicrophoneInput
from irene.workflows.audio_processor import AudioProcessorInterface
from irene.intents.models import AudioData
from irene.workflows.base import RequestContext


class VADRecordingTester:
    """Test VAD recording pipeline and save results"""
    
    def __init__(self, config_path: str = "configs/config-master.toml", output_dir: str = "test_recordings"):
        self.config_path = config_path
        self.config = None
        self.microphone = None
        self.vad_processor = None
        self.output_dir = Path(output_dir)
        self.segment_count = 0
        self.recording_complete = False
        
    async def initialize(self):
        """Initialize components using current configuration"""
        # Load configuration
        config_manager = ConfigManager()
        self.config = await config_manager.load_config(Path(self.config_path))
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        logger.info(f"Output directory: {self.output_dir}")
        
        # Initialize microphone with current config
        mic_config = self.config.inputs.microphone_config
        self.microphone = MicrophoneInput()
        
        await self.microphone.configure_input(
            device_id=mic_config.device_id,
            samplerate=mic_config.sample_rate,
            blocksize=mic_config.chunk_size,
            buffer_queue_size=mic_config.buffer_queue_size
        )
        
        await self.microphone.initialize()
        logger.info(f"Microphone initialized: {self.microphone.get_settings()}")
        
        # Initialize VAD processor with current config
        vad_config = self.config.vad
        self.vad_processor = AudioProcessorInterface(vad_config)
        logger.info(f"VAD processor initialized with config: threshold={vad_config.energy_threshold}, "
                   f"sensitivity={vad_config.sensitivity}")
    
    async def record_and_process(self, duration_seconds: int = 30):
        """Record audio and process through VAD pipeline"""
        logger.info(f"Starting recording for {duration_seconds} seconds...")
        logger.info("VAD will detect voice segments and save them as WAV files")
        logger.info("Speak clearly into the microphone...")
        
        # Start microphone
        await self.microphone.start_listening()
        
        # Create request context
        context = RequestContext(
            source="test_recording",
            skip_wake_word=True,
            wants_audio=False
        )
        
        # Voice segment handler
        async def voice_segment_handler(voice_segment, ctx):
            """Save each voice segment as a WAV file"""
            self.segment_count += 1
            
            # Save original audio (44100Hz)
            original_filename = self.output_dir / f"segment_{self.segment_count:02d}_original_44100hz.wav"
            await self._save_wav_file(voice_segment.combined_audio, original_filename)
            
            logger.info(f"💾 Saved original audio: {original_filename}")
            logger.info(f"   Duration: {voice_segment.total_duration_ms:.1f}ms")
            logger.info(f"   Chunks: {voice_segment.chunk_count}")
            logger.info(f"   Size: {len(voice_segment.combined_audio.data)} bytes")
            
            # Create normalized version for ASR (only if enabled in config)
            normalized_filename = self.output_dir / f"segment_{self.segment_count:02d}_normalized_44100hz.wav"
            
            if getattr(self.config.vad, 'normalize_for_asr', False):
                normalized_segment = voice_segment.normalize_for_asr(target_rms=getattr(self.config.vad, 'asr_target_rms', 0.15))
                audio_for_resampling = normalized_segment.combined_audio
                logger.info(f"💾 Audio normalized for ASR (target RMS: {getattr(self.config.vad, 'asr_target_rms', 0.15)})")
            else:
                # Use original audio if normalization is disabled
                audio_for_resampling = voice_segment.combined_audio
                logger.info(f"💾 Normalization disabled - using original audio")
            
            # Save the audio that will be used for ASR (normalized or original)
            await self._save_wav_file(audio_for_resampling, normalized_filename)
            logger.info(f"💾 Saved normalized audio: {normalized_filename}")
            
            # Resample to 16kHz (what ASR receives)
            resampled_audio = await self._resample_to_16khz(audio_for_resampling)
            resampled_filename = self.output_dir / f"segment_{self.segment_count:02d}_asr_ready_16khz.wav"
            await self._save_wav_file(resampled_audio, resampled_filename)
            
            logger.info(f"💾 Saved ASR-ready audio: {resampled_filename}")
            logger.info(f"   Size after resampling: {len(resampled_audio.data)} bytes")
            
            # Mark that we have completed a recording
            self.recording_complete = True
        
        # Process audio through VAD pipeline
        try:
            start_time = time.time()
            
            async for voice_segment in self.vad_processor.process_audio_pipeline(
                self._get_audio_stream(), context, voice_segment_handler
            ):
                # Voice segment is already handled by the callback
                # Exit after first recording is complete
                if self.recording_complete:
                    logger.info("🎯 Recording complete! Exiting...")
                    break
                    
                # Also exit if we've reached the time limit
                elapsed = time.time() - start_time
                if elapsed >= duration_seconds:
                    logger.info("⏰ Time limit reached, exiting...")
                    break
                
        except KeyboardInterrupt:
            logger.info("Recording interrupted by user")
        finally:
            await self.microphone.stop_listening()
    
    async def _get_audio_stream(self) -> AsyncIterator[AudioData]:
        """Get audio stream from microphone"""
        start_time = time.time()
        duration = 30  # seconds
        
        async for audio_data in self.microphone.listen():
            # Stop after duration
            if time.time() - start_time > duration:
                break
            yield audio_data
    
    async def _save_wav_file(self, audio_data: AudioData, filename: Path):
        """Save AudioData as WAV file"""
        with wave.open(str(filename), 'wb') as wav_file:
            wav_file.setnchannels(audio_data.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(audio_data.sample_rate)
            wav_file.writeframes(audio_data.data)
    
    async def _resample_to_16khz(self, audio_data: AudioData) -> AudioData:
        """Resample audio to 16kHz (simulate ASR preprocessing)"""
        if audio_data.sample_rate == 16000:
            return audio_data
            
        # Use the same resampling that ASR component uses
        from irene.utils.audio_helpers import AudioProcessor, ConversionMethod
        
        try:
            conversion_method = AudioProcessor.get_optimal_conversion_path(
                audio_data.sample_rate, 16000, use_case="asr"
            )
            
            resampled_audio = await AudioProcessor.resample_audio_data(
                audio_data, 16000, conversion_method
            )
            
            return resampled_audio
            
        except Exception as e:
            logger.error(f"Resampling failed: {e}")
            # Return original if resampling fails
            return audio_data
    
    def get_summary(self):
        """Get recording session summary"""
        return {
            "segments_recorded": self.segment_count,
            "output_directory": str(self.output_dir),
            "config_file": self.config_path,
            "vad_config": {
                "threshold": self.config.vad.energy_threshold,
                "sensitivity": self.config.vad.sensitivity,
                "voice_duration_ms": self.config.vad.voice_duration_ms,
                "silence_duration_ms": self.config.vad.silence_duration_ms
            } if self.config else None
        }


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="VAD Recording Test Script - Test voice activity detection and record audio segments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default settings
  %(prog)s --config configs/voice.toml       # Use specific config file
  %(prog)s --duration 60 --output my_tests   # Record for 60 seconds, save to my_tests/
  %(prog)s --help                            # Show this help message

The script will:
1. Initialize audio input using the specified configuration
2. Record audio and detect voice segments using VAD
3. Save both original (44100Hz) and resampled (16kHz) WAV files
4. Exit after recording one voice segment or reaching the time limit
        """
    )
    
    parser.add_argument(
        "--config", "-c",
        default="configs/config-master.toml",
        help="Path to configuration file (default: configs/config-master.toml)"
    )
    
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=30,
        help="Maximum recording duration in seconds (default: 30)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default="test_recordings",
        help="Output directory for recorded files (default: test_recordings)"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce output verbosity (only show essential information)"
    )
    
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Skip the 3-second countdown before recording"
    )
    
    return parser.parse_args()


async def main():
    """Main test function"""
    args = parse_arguments()
    
    # Set logging level based on quiet flag
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    tester = VADRecordingTester(config_path=args.config, output_dir=args.output)
    
    try:
        # Initialize
        await tester.initialize()
        
        # Record and process
        if not args.quiet:
            print("\n" + "="*60)
            print("VAD RECORDING TEST")
            print("="*60)
            print("This will record audio using the current VAD configuration")
            print("and save voice segments as WAV files for analysis.")
            print(f"\nConfiguration: {args.config}")
            print(f"Output directory: {args.output}")
            print(f"Max duration: {args.duration} seconds")
            print("\nInstructions:")
            print("1. Speak clearly into the microphone")
            print("2. Try phrases like: 'Привет', 'Как дела', 'Тест записи'")
            print("3. The script will automatically exit after recording one voice segment")
            print("4. Both original (44100Hz) and resampled (16kHz) files will be saved")
            
            if not args.no_wait:
                print("\nStarting in 3 seconds...")
                print("="*60)
                await asyncio.sleep(3)
            else:
                print("="*60)
        else:
            print(f"Recording audio (max {args.duration}s) to {args.output}/")
        
        # Record for specified duration
        await tester.record_and_process(args.duration)
        
        # Show summary
        summary = tester.get_summary()
        if not args.quiet:
            print("\n" + "="*60)
            print("RECORDING COMPLETE")
            print("="*60)
            print(f"Segments recorded: {summary['segments_recorded']}")
            print(f"Output directory: {summary['output_directory']}")
            print(f"\nVAD Configuration:")
            print(f"  Energy threshold: {summary['vad_config']['threshold']}")
            print(f"  Sensitivity: {summary['vad_config']['sensitivity']}")
            print(f"  Voice duration: {summary['vad_config']['voice_duration_ms']}ms")
            print(f"  Silence duration: {summary['vad_config']['silence_duration_ms']}ms")
            
            if summary['segments_recorded'] > 0:
                print(f"\n📁 Check the '{summary['output_directory']}' folder for:")
                print("  - *_original_44100hz.wav (raw microphone input)")
                print("  - *_normalized_44100hz.wav (volume normalized to prevent ASR clipping)")
                print("  - *_asr_ready_16khz.wav (final audio sent to ASR)")
                print("\n🎧 Play these files to hear exactly what the system recorded!")
                print("📊 Compare original vs normalized to see volume adjustment")
            else:
                print("\n⚠️  No voice segments detected!")
                print("Possible issues:")
                print("  - VAD threshold too high")
                print("  - Microphone not working")
                print("  - Audio too quiet")
                print("  - Background noise issues")
            
            print("="*60)
        else:
            if summary['segments_recorded'] > 0:
                print(f"✅ Recorded {summary['segments_recorded']} segments to {summary['output_directory']}/")
            else:
                print("❌ No voice segments detected")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


def cli_main():
    """Entry point for command line usage"""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
