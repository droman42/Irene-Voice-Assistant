"""
Irene Voice Assistant Utilities

Modern utility functions for Irene v13:
- Component loading and dependency management
- Logging configuration
- Text processing and number-to-text conversion
"""

from .loader import *
from .logging import *
from .text_processing import *
from .audio_helpers import *

__all__ = [
    # Component loading utilities
    'ComponentLoader',
    'safe_import',
    'get_component_status', 
    'suggest_installation',
    
    # Logging utilities
    'setup_logging',
    'get_logger',
    
    # Text processing utilities (migrated from legacy utils/)
    'num_to_text_ru',
    'decimal_to_text_ru',
    'all_num_to_text',
    'num_to_text_ru_async',
    'decimal_to_text_ru_async', 
    'all_num_to_text_async',
    'load_language',
    
    # Audio processing helpers
    'validate_audio_file',
    'normalize_volume',
    'format_audio_duration',
    'detect_sample_rate',
    'get_audio_devices',
    'get_default_audio_device', 
    'calculate_audio_buffer_size',
    'AudioFormatConverter',
    'get_audio_info',
    'test_audio_playback_capability'
] 