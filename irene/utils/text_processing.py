"""
Text Processing Utilities

Modern async-compatible text processing utilities for Irene Voice Assistant.
Migrated from legacy utils/ with improvements:
- Async/await support
- Modern Python 3.11+ patterns  
- Type annotations
- Better error handling
- Optional dependencies
"""

import asyncio
import decimal
import logging
import re
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Russian number-to-text conversion constants
# Migrated from utils/num_to_text_ru.py

UNITS = (
    'ноль',
    ('один', 'одна'),
    ('два', 'две'),
    'три', 'четыре', 'пять',
    'шесть', 'семь', 'восемь', 'девять'
)

TEENS = (
    'десять', 'одиннадцать',
    'двенадцать', 'тринадцать',
    'четырнадцать', 'пятнадцать',
    'шестнадцать', 'семнадцать',
    'восемнадцать', 'девятнадцать'
)

TENS = (
    TEENS,
    'двадцать', 'тридцать',
    'сорок', 'пятьдесят',
    'шестьдесят', 'семьдесят',
    'восемьдесят', 'девяносто'
)

HUNDREDS = (
    'сто', 'двести',
    'триста', 'четыреста',
    'пятьсот', 'шестьсот',
    'семьсот', 'восемьсот',
    'девятьсот'
)

ORDERS = (  # plural forms and gender
    (('тысяча', 'тысячи', 'тысяч'), 'f'),
    (('миллион', 'миллиона', 'миллионов'), 'm'),
    (('миллиард', 'миллиарда', 'миллиардов'), 'm'),
)

MINUS = 'минус'


def _thousand(rest: int, sex: str) -> tuple[int, list[str]]:
    """
    Convert numbers from 19 to 999 to Russian text.
    
    Args:
        rest: Number to convert (0-999)
        sex: Gender ('m' for masculine, 'f' for feminine)
        
    Returns:
        Tuple of (plural_form_index, word_list)
    """
    prev = 0
    plural = 2
    name = []
    use_teens = rest % 100 >= 10 and rest % 100 <= 19
    
    if not use_teens:
        data = ((UNITS, 10), (TENS, 100), (HUNDREDS, 1000))
    else:
        data = ((TEENS, 10), (HUNDREDS, 1000))
        
    for names, x in data:
        cur = int(((rest - prev) % x) * 10 / x)
        prev = rest % x
        
        if x == 10 and use_teens:
            plural = 2
            name.append(TEENS[cur])
        elif cur == 0:
            continue
        elif x == 10:
            name_ = names[cur]
            if isinstance(name_, tuple):
                name_ = name_[0 if sex == 'm' else 1]
            name.append(name_)
            if cur >= 2 and cur <= 4:
                plural = 1
            elif cur == 1:
                plural = 0
            else:
                plural = 2
        else:
            name.append(names[cur-1])
            
    return plural, name


def num_to_text_ru(num: int, main_units: tuple[tuple[str, str, str], str] = (('', '', ''), 'm')) -> str:
    """
    Convert integer to Russian text representation.
    
    Args:
        num: Integer to convert
        main_units: Tuple of ((singular, few, many), gender) for the main unit
        
    Returns:
        Russian text representation of the number
        
    Examples:
        >>> num_to_text_ru(123)
        'сто двадцать три'
        >>> num_to_text_ru(1, (('штука', 'штуки', 'штук'), 'f'))
        'одна штука'
    """
    _orders = (main_units,) + ORDERS
    
    if num == 0:
        return ' '.join((UNITS[0], _orders[0][0][2])).strip()
    
    rest = abs(num)
    ord = 0
    name = []
    
    while rest > 0:
        plural, nme = _thousand(rest % 1000, _orders[ord][1])
        if nme or ord == 0:
            name.append(_orders[ord][0][plural])
        name += nme
        rest = int(rest / 1000)
        ord += 1
        
    if num < 0:
        name.append(MINUS)
        
    name.reverse()
    return ' '.join(name).strip()


def decimal_to_text_ru(
    value: Union[str, int, float, decimal.Decimal], 
    places: int = 2,
    int_units: tuple[tuple[str, str, str], str] = (('', '', ''), 'm'),
    exp_units: tuple[tuple[str, str, str], str] = (('', '', ''), 'm')
) -> str:
    """
    Convert decimal number to Russian text representation.
    
    Args:
        value: Decimal value to convert
        places: Number of decimal places
        int_units: Units for the integer part
        exp_units: Units for the decimal part
        
    Returns:
        Russian text representation of the decimal number
        
    Examples:
        >>> decimal_to_text_ru("12.34", int_units=(('рубль', 'рубля', 'рублей'), 'm'), 
        ...                   exp_units=(('копейка', 'копейки', 'копеек'), 'f'))
        'двенадцать рублей тридцать четыре копейки'
    """
    value = decimal.Decimal(str(value))
    q = decimal.Decimal(10) ** -places
    
    integral, exp = str(value.quantize(q)).split('.')
    return '{} {}'.format(
        num_to_text_ru(int(integral), int_units),
        num_to_text_ru(int(exp), exp_units)
    )


# Text processing with lingua_franca integration
# Migrated from utils/all_num_to_text.py

def _convert_one_num_float(match_obj: re.Match) -> str:
    """Convert single number match to text using lingua_franca."""
    if match_obj.group() is not None:
        try:
            # Try to use lingua_franca if available
            from lingua_franca.format import pronounce_number  # type: ignore
            return pronounce_number(float(match_obj.group()))
        except ImportError:
            # Fallback to Russian implementation for integers
            try:
                if '.' in match_obj.group():
                    return decimal_to_text_ru(match_obj.group())
                else:
                    return num_to_text_ru(int(match_obj.group()))
            except (ValueError, decimal.InvalidOperation):
                logger.warning(f"Could not convert number: {match_obj.group()}")
                return match_obj.group()
    return match_obj.group()


def _convert_diapazon(match_obj: re.Match) -> str:
    """Convert range (e.g., '120-130') to text."""
    if match_obj.group() is not None:
        text = str(match_obj.group())
        text = text.replace("-", " тире ")
        return all_num_to_text(text)
    return match_obj.group()


def all_num_to_text(text: str, language: str = "ru") -> str:
    """
    Convert all numbers in text to spoken representation.
    
    This function processes various number formats:
    - Integers: "123" → "сто двадцать три"
    - Decimals: "12.34" → "двенадцать целых тридцать четыре сотых"
    - Ranges: "120-130" → "сто двадцать тире сто тридцать"
    - Negative numbers: "-10" → "минус десять"
    - Percentages: "50%" → "пятьдесят процентов"
    
    Args:
        text: Input text containing numbers
        language: Language code (default: "ru" for Russian)
        
    Returns:
        Text with numbers converted to words
        
    Examples:
        >>> all_num_to_text("У меня 5 яблок и 2.5 кг груш")
        'У меня пять яблок и два целых пять десятых кг груш'
        >>> all_num_to_text("Температура -10 градусов")
        'Температура минус десять градусов'
    """
    try:
        # Try to load lingua_franca if available
        import lingua_franca  # type: ignore
        lingua_franca.load_language(language)
        logger.debug(f"Using lingua_franca for language: {language}")
    except ImportError:
        logger.debug("lingua_franca not available, using fallback Russian implementation")
    
    # Process different number patterns in order of complexity
    # Decimal ranges (e.g., "120.1-120.8")
    text = re.sub(r'[\d]*[.][\d]+-[\d]*[.][\d]+', _convert_diapazon, text)
    
    # Negative decimals (e.g., "-30.1")
    text = re.sub(r'-[\d]*[.][\d]+', _convert_one_num_float, text)
    
    # Positive decimals (e.g., "44.05")
    text = re.sub(r'[\d]*[.][\d]+', _convert_one_num_float, text)
    
    # Integer ranges (e.g., "5-10")
    text = re.sub(r'[\d]-[\d]+', _convert_diapazon, text)
    
    # Negative integers (e.g., "-10")
    text = re.sub(r'-[\d]+', _convert_one_num_float, text)
    
    # Positive integers (e.g., "123")
    text = re.sub(r'[\d]+', _convert_one_num_float, text)
    
    # Convert percentages
    text = text.replace("%", " процентов")
    
    return text


# Async versions for modern v13 architecture

async def num_to_text_ru_async(num: int, main_units: tuple[tuple[str, str, str], str] = (('', '', ''), 'm')) -> str:
    """Async version of num_to_text_ru for non-blocking operation."""
    return await asyncio.to_thread(num_to_text_ru, num, main_units)


async def decimal_to_text_ru_async(
    value: Union[str, int, float, decimal.Decimal], 
    places: int = 2,
    int_units: tuple[tuple[str, str, str], str] = (('', '', ''), 'm'),
    exp_units: tuple[tuple[str, str, str], str] = (('', '', ''), 'm')
) -> str:
    """Async version of decimal_to_text_ru for non-blocking operation."""
    return await asyncio.to_thread(decimal_to_text_ru, value, places, int_units, exp_units)


async def all_num_to_text_async(text: str, language: str = "ru") -> str:
    """
    Async version of all_num_to_text for non-blocking operation.
    
    This is the main function that should be used in v13 async plugins.
    """
    return await asyncio.to_thread(all_num_to_text, text, language)


# Legacy compatibility functions for migration period

def load_language(lang: str) -> None:
    """
    Legacy compatibility function for lingua_franca language loading.
    
    Args:
        lang: Language code to load
    """
    try:
        import lingua_franca  # type: ignore
        lingua_franca.load_language(lang)
        logger.debug(f"Loaded lingua_franca language: {lang}")
    except ImportError:
        logger.debug("lingua_franca not available, language loading skipped")


# Phase 4 Enhancement: Unified Text Processing Pipeline
# Following the document specification for normalizer migration

class TextProcessor:
    """Unified text processing pipeline for ASR, LLM, and TTS stages"""
    
    def __init__(self):
        self.normalizers = [
            NumberNormalizer(),      # "123" → "сто двадцать три"
            PrepareNormalizer(),     # Latin→Cyrillic, symbols cleanup
            RunormNormalizer()       # Advanced Russian normalization
        ]
        
    async def process_pipeline(self, text: str, stage: str = "general") -> str:
        """Apply normalizers based on processing stage"""
        processed_text = text
        
        for normalizer in self.normalizers:
            if normalizer.applies_to_stage(stage):
                try:
                    processed_text = await normalizer.normalize(processed_text)
                except Exception as e:
                    logger.warning(f"Normalizer {normalizer.__class__.__name__} failed: {e}")
                    
        return processed_text


class NumberNormalizer:
    """Extracted from plugin_normalizer_numbers.py"""
    
    def applies_to_stage(self, stage: str) -> bool:
        return stage in ["asr_output", "general", "tts_input"]
        
    async def normalize(self, text: str) -> str:
        # Move core.all_num_to_text() functionality here
        return await all_num_to_text_async(text, language="ru")


class PrepareNormalizer:
    """Extracted from plugin_normalizer_prepare.py"""
    
    def __init__(self):
        # Default options matching the original plugin
        self.options = {
            "changeNumbers": "process",
            "changeLatin": "process", 
            "changeSymbols": r"#$%&*+-/<=>@~[\]_`{|}№",
            "keepSymbols": r",.?!;:() ",
            "deleteUnknownSymbols": True,
        }
    
    def applies_to_stage(self, stage: str) -> bool:
        return stage in ["tts_input", "general"]
        
    async def normalize(self, text: str) -> str:
        """
        Latin→Cyrillic transcription, symbol replacement, etc.
        Extracted from plugin_normalizer_prepare.py
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
        """Replace symbols with text equivalents"""
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
        """Process numbers according to options"""
        if self.options['changeNumbers'].lower() == 'process':
            return await all_num_to_text_async(text)
        elif self.options['changeNumbers'].lower() == 'delete':
            return re.sub(r'[0-9]', '', text)
        return text  # 'no_process'
    
    async def _transcribe_latin_to_cyrillic(self, text: str) -> str:
        """Transcribe Latin text to Cyrillic using IPA"""
        try:
            import eng_to_ipa as ipa
        except ImportError:
            logger.warning("eng_to_ipa not available for Latin transcription")
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
    """Extracted from plugin_normalizer_runorm.py"""
    
    def __init__(self):
        self.options = {
            "modelSize": "small",
            "device": "cpu"
        }
        self._normalizer = None
    
    def applies_to_stage(self, stage: str) -> bool:
        return stage in ["tts_input"]
        
    async def normalize(self, text: str) -> str:
        """Advanced Russian text normalization using RUNorm"""
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
        """Initialize RUNorm model"""
        try:
            from runorm import RUNorm
            
            self._normalizer = RUNorm()
            await asyncio.to_thread(
                self._normalizer.load,
                model_size=self.options["modelSize"],
                device=self.options["device"]
            )
            logger.info(f"RUNorm initialized with model: {self.options['modelSize']}")
            
        except ImportError:
            logger.warning("RUNorm library not available (pip install runorm)")
            self._normalizer = None
        except Exception as e:
            logger.error(f"Failed to initialize RUNorm: {e}")
            self._normalizer = None


# Export commonly used functions
__all__ = [
    'num_to_text_ru',
    'decimal_to_text_ru', 
    'all_num_to_text',
    'num_to_text_ru_async',
    'decimal_to_text_ru_async',
    'all_num_to_text_async',
    'load_language',
    # Phase 4 additions
    'TextProcessor',
    'NumberNormalizer',
    'PrepareNormalizer', 
    'RunormNormalizer'
] 