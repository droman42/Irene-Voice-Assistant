"""
Text Normalizers - Shared Normalizer Utilities

Extracted and modularized normalizer classes for the Irene Voice Assistant.
These normalizers are designed to be composable and reusable across 
different text processing providers.

Phase 1 of TODO #2: Text Processing Provider Architecture Refactoring
- Removed stage-specific logic (moved to providers)
- Made normalizers more modular for composition
- Maintained existing functionality with better separation of concerns
"""

import asyncio
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class NumberNormalizer:
    """
    Number-to-text normalizer using Russian conversion.
    
    Extracted from original plugin_normalizer_numbers.py
    Stage logic removed - providers decide when to use this normalizer.
    """
    
    def __init__(self, language: str = "ru"):
        """
        Initialize number normalizer.
        
        Args:
            language: Target language for number conversion (default: "ru")
        """
        self.language = language
    

        
    async def normalize(self, text: str) -> str:
        """
        Convert numbers in text to words.
        
        Args:
            text: Text containing numbers to convert
            
        Returns:
            Text with numbers converted to words
            
        Examples:
            >>> await normalizer.normalize("У меня 5 яблок")
            'У меня пять яблок'
        """
        try:
            # Import the core function from text_processing
            from .text_processing import all_num_to_text_async
            return await all_num_to_text_async(text, self.language)
        except ImportError as e:
            logger.error(f"Failed to import number conversion function: {e}")
            return text
        except Exception as e:
            logger.warning(f"Number normalization failed: {e}")
            return text


class PrepareNormalizer:
    """
    Text preparation normalizer for symbol replacement and Latin transcription.
    
    Extracted from original plugin_normalizer_prepare.py
    Stage logic removed - providers decide when to use this normalizer.
    """
    
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        """
        Initialize prepare normalizer with configurable options.
        
        Args:
            options: Configuration options for normalization behavior
        """
        # Default options matching the original plugin
        self.options = options or {
            "changeNumbers": "process",
            "changeLatin": "process", 
            "changeSymbols": r"#$%&*+-/<=>@~[\]_`{|}№",
            "keepSymbols": r",.?!;:() ",
            "deleteUnknownSymbols": True,
        }
        

        
    async def normalize(self, text: str) -> str:
        """
        Apply text preparation: symbol replacement, Latin transcription, etc.
        
        Args:
            text: Text to prepare
            
        Returns:
            Prepared text with symbols replaced and Latin transcribed
        """
        # If only Cyrillic and punctuation - leave as is
        if not bool(re.search(r'[^,.?!;:"() ЁА-Яа-яё]', text)):
            return text
        
        # Symbol replacement
        if bool(re.search(r'["-+\-/<->@{-}№]', text)):
            text = await self._replace_symbols(text)
        
        # Number processing
        if bool(re.search(r'[0-9]', text)):
            text = await self._process_numbers(text)
        
        # Latin to Cyrillic transcription
        if bool(re.search('[a-zA-Z]', text)) and self.options['changeLatin'] == 'process':
            text = await self._transcribe_latin_to_cyrillic(text)
        
        return text
    
    async def _replace_symbols(self, text: str) -> str:
        """Replace symbols with text equivalents based on configuration."""
        symbol_dict = {
            '!': '!', '"': ' двойная кавычка ', '#': ' решётка ', '$': ' доллар ', '%': ' процент ',
            '&': ' амперсанд ', "'": ' кавычка ', '(': ' левая скобка ', ')': ' правая скобка ',
            '*': ' звёздочка ', '+': ' плюс ', ',': ',', '-': ' минус ', '.': '.', '/': ' косая черта ',
            ':': ':', ';': ';', '<': 'меньше', '=': ' равно ', '>': 'больше', '?': '?', '@': ' эт ',
            '~': ' тильда ', '[': ' левая квадратная скобка ', '\\': ' обратная косая черта ',
            ']': ' правая квадратная скобка ', '^': ' циркумфлекс ', '_': ' нижнее подчеркивание ',
            '`': ' обратная кавычка ', '{': ' левая фигурная скобка ', '|': ' вертикальная черта ',
            '}': ' правая фигурная скобка ', '№': ' номер ',
        }
        
        symbols_to_change = self.options['changeSymbols']
        filtered_symbol_dict = {key: value for key, value in symbol_dict.items() if key in symbols_to_change}
        
        symbols_to_keep = self.options['keepSymbols']
        filtered_symbol_dict.update({key: key for key in symbols_to_keep})
        
        if filtered_symbol_dict:
            translation_table = str.maketrans(filtered_symbol_dict)
            text = text.translate(translation_table)
        
        if self.options['deleteUnknownSymbols']:
            pattern = f'[^{symbols_to_change}{symbols_to_keep}A-Za-zЁА-Яа-яё ]'
            text = re.sub(pattern, '', text)
        
        text = re.sub(r'[\s]+', ' ', text)  # Remove extra spaces
        return text
    
    async def _process_numbers(self, text: str) -> str:
        """Process numbers according to configuration options."""
        if self.options['changeNumbers'].lower() == 'process':
            try:
                from .text_processing import all_num_to_text_async
                return await all_num_to_text_async(text)
            except ImportError as e:
                logger.error(f"Failed to import number conversion function: {e}")
                return text
        elif self.options['changeNumbers'].lower() == 'delete':
            return re.sub(r'[0-9]', '', text)
        return text  # 'no_process'
    
    async def _transcribe_latin_to_cyrillic(self, text: str) -> str:
        """Transcribe Latin text to Cyrillic using IPA (optional dependency)."""
        try:
            import eng_to_ipa as ipa  # type: ignore
        except ImportError:
            logger.warning("eng_to_ipa not available for Latin transcription (optional dependency)")
            return text
        
        # IPA to Russian mapping
        ipa2ru_map = {
            "p": "п", "b": "б", "t": "т", "d": "д", "k": "к", "g": "г", "m": "м", "n": "н", "ŋ": "нг", "ʧ": "ч",
            "ʤ": "дж", "f": "ф", "v": "в", "θ": "т", "ð": "з", "s": "с", "z": "з", "ʃ": "ш", "ʒ": "ж", "h": "х",
            "w": "в", "j": "й", "r": "р", "l": "л",
            # Vowels
            "i": "и", "ɪ": "и", "e": "э", "ɛ": "э", "æ": "э", "ʌ": "а", "ə": "е", "u": "у", "ʊ": "у", "oʊ": "оу",
            "ɔ": "о", "ɑ": "а", "aɪ": "ай", "aʊ": "ау", "ɔɪ": "ой", "ɛr": "ё", "ər": "ё", "ɚ": "а", "ju": "ю",
            "əv": "ов", "o": "о",
            # Stress marks
            "ˈ": "", "ˌ": "", "*": "",
        }
        
        try:
            # Convert to IPA
            ipa_text = ipa.convert(text)
            
            # Convert IPA to Russian
            result = ""
            pos = 0
            while pos < len(ipa_text):
                ch = ipa_text[pos]
                ch2 = ipa_text[pos: pos + 2]
                
                # Check for two-character sequences first
                if ch2 in ipa2ru_map:
                    result += ipa2ru_map[ch2]
                    pos += 2
                elif ch in ipa2ru_map:
                    result += ipa2ru_map[ch]
                    pos += 1
                elif ord(ch) < 128:  # ASCII characters
                    result += ch
                    pos += 1
                else:
                    result += ch
                    pos += 1
            
            return result
            
        except Exception as e:
            logger.warning(f"Latin transcription failed: {e}")
            return text


class RunormNormalizer:
    """
    Advanced Russian text normalizer using RUNorm model.
    
    Extracted from original plugin_normalizer_runorm.py
    Stage logic removed - providers decide when to use this normalizer.
    Optional dependency: runorm library
    """
    
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        """
        Initialize RunormNormalizer with configurable options.
        
        Args:
            options: Configuration options for RUNorm model
        """
        self.options = options or {
            "modelSize": "small",
            "device": "cpu"
        }
        self._normalizer = None
        

        
    async def normalize(self, text: str) -> str:
        """
        Apply advanced Russian text normalization using RUNorm.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text (or original if RUNorm unavailable)
        """
        try:
            if self._normalizer is None:
                await self._initialize_runorm()
            
            if self._normalizer:
                return await asyncio.to_thread(self._normalizer.norm, text)
            else:
                logger.warning("RUNorm not available, skipping normalization")
                return text
                
        except Exception as e:
            logger.warning(f"RUNorm normalization failed: {e}")
            return text
    
    async def _initialize_runorm(self) -> None:
        """Initialize RUNorm model (optional dependency)."""
        try:
            from runorm import RUNorm  # type: ignore
            
            self._normalizer = RUNorm()
            await asyncio.to_thread(
                self._normalizer.load,
                model_size=self.options["modelSize"],
                device=self.options["device"]
            )
            logger.info(f"RUNorm initialized with model: {self.options['modelSize']}")
            
        except ImportError:
            logger.warning("RUNorm library not available (optional dependency: pip install runorm)")
            self._normalizer = None
        except Exception as e:
            logger.error(f"Failed to initialize RUNorm: {e}")
            self._normalizer = None
    
    async def cleanup(self) -> None:
        """Clean up RUNorm resources."""
        if self._normalizer:
            # RUNorm doesn't require explicit cleanup
            self._normalizer = None
            logger.debug("RUNorm normalizer cleaned up")


# Export normalizer classes
__all__ = [
    'NumberNormalizer',
    'PrepareNormalizer', 
    'RunormNormalizer'
] 