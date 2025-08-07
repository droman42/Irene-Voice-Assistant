"""
Text Processing Providers

Stage-specific text processing providers that compose shared normalizer utilities
for focused, efficient text processing workflows.

TODO #2 Complete: Text Processing Provider Architecture Refactoring
- Stage-specific providers for optimal performance per use case
- Each provider optimized for specific processing stages
- Compose shared normalizers from irene/utils/text_normalizers.py
"""

# Stage-specific providers (TODO #2 implementation)
from .asr_text_processor import ASRTextProcessor
from .general_text_processor import GeneralTextProcessor
from .tts_text_processor import TTSTextProcessor
from .number_text_processor import NumberTextProcessor

__all__ = [
    'ASRTextProcessor',
    'GeneralTextProcessor', 
    'TTSTextProcessor',
    'NumberTextProcessor'
] 