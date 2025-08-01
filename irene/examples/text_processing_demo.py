#!/usr/bin/env python3
"""
Text Processing Utilities Demo

Demonstrates the migrated text processing functionality:
- Russian number-to-text conversion
- Decimal number processing  
- Text normalization with number conversion
- Async versions for v13 integration

Usage:
    python -m irene.examples.text_processing_demo
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from irene.utils.text_processing import (
    num_to_text_ru,
    decimal_to_text_ru,
    all_num_to_text,
    num_to_text_ru_async,
    decimal_to_text_ru_async,
    all_num_to_text_async,
    load_language
)


def demo_basic_number_conversion():
    """Demonstrate basic Russian number-to-text conversion."""
    print("🔢 Basic Number Conversion Demo")
    print("=" * 50)
    
    test_numbers = [0, 1, 2, 5, 10, 11, 15, 20, 25, 100, 123, 1000, 1234, 1000000, -10, -123]
    
    for num in test_numbers:
        result = num_to_text_ru(num)
        print(f"{num:>8} → {result}")
    
    print()


def demo_units_and_genders():
    """Demonstrate number conversion with units and gender agreement."""
    print("👥 Gender and Units Demo")
    print("=" * 50)
    
    test_cases = [
        (1, (('штука', 'штуки', 'штук'), 'f')),
        (2, (('штука', 'штуки', 'штук'), 'f')),
        (5, (('штука', 'штуки', 'штук'), 'f')),
        (1, (('рубль', 'рубля', 'рублей'), 'm')),
        (2, (('рубль', 'рубля', 'рублей'), 'm')),
        (5, (('рубль', 'рубля', 'рублей'), 'm')),
        (21, (('секунда', 'секунды', 'секунд'), 'f')),
        (22, (('стол', 'стола', 'столов'), 'm')),
    ]
    
    for num, units in test_cases:
        result = num_to_text_ru(num, units)
        print(f"{num} → {result}")
    
    print()


def demo_decimal_conversion():
    """Demonstrate decimal number conversion."""
    print("💰 Decimal Number Demo")
    print("=" * 50)
    
    test_cases = [
        ("12.34", 2, (('рубль', 'рубля', 'рублей'), 'm'), (('копейка', 'копейки', 'копеек'), 'f')),
        ("1.50", 2, (('метр', 'метра', 'метров'), 'm'), (('сантиметр', 'сантиметра', 'сантиметров'), 'm')),
        ("0.25", 2, (('килограмм', 'килограмма', 'килограммов'), 'm'), (('грамм', 'грамма', 'граммов'), 'm')),
        ("100.01", 2, (('', '', ''), 'm'), (('', '', ''), 'm')),
    ]
    
    for value, places, int_units, exp_units in test_cases:
        result = decimal_to_text_ru(value, places, int_units, exp_units)
        print(f"{value} → {result}")
    
    print()


def demo_text_normalization():
    """Demonstrate full text normalization with numbers."""
    print("📝 Text Normalization Demo")
    print("=" * 50)
    
    # Try to load Russian language support
    load_language("ru")
    
    test_texts = [
        "У меня 5 яблок и 2.5 кг груш",
        "Температура -10 градусов",
        "Купил 3-4 книги за 120.50 рублей",
        "Встреча назначена на 14:30",
        "Скидка составляет 25%",
        "Диапазон 120.1-120.8 мГц",
        "Получил -15.5 баллов",
        "Набрал 1234567 очков"
    ]
    
    for text in test_texts:
        result = all_num_to_text(text)
        print(f"Original: {text}")
        print(f"Converted: {result}")
        print()


async def demo_async_functions():
    """Demonstrate async versions of text processing functions."""
    print("⚡ Async Functions Demo")
    print("=" * 50)
    
    # Test async number conversion
    result1 = await num_to_text_ru_async(12345)
    print(f"Async num_to_text_ru(12345) → {result1}")
    
    # Test async decimal conversion
    result2 = await decimal_to_text_ru_async(
        "99.99", 
        int_units=(('доллар', 'доллара', 'долларов'), 'm'),
        exp_units=(('цент', 'цента', 'центов'), 'm')
    )
    print(f"Async decimal_to_text_ru(99.99) → {result2}")
    
    # Test async text normalization
    test_text = "Заработал 1000000 рублей и потратил 25.75% на покупки"
    result3 = await all_num_to_text_async(test_text)
    print(f"Async text normalization:")
    print(f"  Original: {test_text}")
    print(f"  Converted: {result3}")
    
    print()


def demo_edge_cases():
    """Demonstrate edge cases and error handling."""
    print("🛡️ Edge Cases Demo")
    print("=" * 50)
    
    edge_cases = [
        "Text without numbers",
        "123abc456",  # Mixed text and numbers
        "Price is $50.00",  # Currency symbols
        "Phone: +7-900-123-45-67",  # Phone numbers
        "IPv4: 192.168.1.1",  # IP addresses
        "Version 3.14.159",  # Version numbers
        "",  # Empty string
        "   ",  # Whitespace only
    ]
    
    for text in edge_cases:
        try:
            result = all_num_to_text(text)
            print(f"✅ '{text}' → '{result}'")
        except Exception as e:
            print(f"❌ '{text}' → Error: {e}")
    
    print()


def demo_performance():
    """Demonstrate performance with larger texts."""
    print("🚀 Performance Demo")
    print("=" * 50)
    
    import time
    
    # Generate a text with many numbers
    test_text = " ".join([f"число {i}" for i in range(1, 101)])
    
    start_time = time.time()
    result = all_num_to_text(test_text)
    end_time = time.time()
    
    print(f"Processed text with 100 numbers")
    print(f"Processing time: {end_time - start_time:.4f} seconds")
    print(f"Original length: {len(test_text)} characters")
    print(f"Converted length: {len(result)} characters")
    print(f"Sample result: {result[:100]}...")
    
    print()


async def main():
    """Run all demonstrations."""
    print("🎯 Irene Voice Assistant - Text Processing Utilities Demo")
    print("=" * 70)
    print()
    
    # Synchronous demos
    demo_basic_number_conversion()
    demo_units_and_genders()
    demo_decimal_conversion()
    demo_text_normalization()
    demo_edge_cases()
    demo_performance()
    
    # Async demo
    await demo_async_functions()
    
    print("✅ All text processing demos completed successfully!")
    print()
    print("💡 Usage in v13 plugins:")
    print("   - Use async versions: all_num_to_text_async(), num_to_text_ru_async()")
    print("   - Import from: irene.utils.text_processing")
    print("   - Legacy compatibility maintained for migration period")


if __name__ == "__main__":
    asyncio.run(main()) 