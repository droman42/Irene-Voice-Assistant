"""
Text Processing Providers

Providers that wrap existing text processing utilities from irene/utils/text_processing.py
to provide consistent provider interfaces for the intent system.
"""

from .unified_processor import UnifiedTextProcessor
from .number_processor import NumberTextProcessor

__all__ = [
    'UnifiedTextProcessor',
    'NumberTextProcessor'
] 