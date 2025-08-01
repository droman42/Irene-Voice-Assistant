#!/usr/bin/env python3
"""
Multilingual Text Processing Demo

Demonstrates optional lingua-franca integration:
- Shows fallback to Russian when lingua-franca not available
- Shows enhanced multilingual capabilities when lingua-franca is installed
- Installation guide for users who want multilingual support

Usage:
    # Without multilingual support (Russian fallback):
    python -m irene.examples.multilingual_demo
    
    # With multilingual support:
    uv add irene-voice-assistant[text-multilingual]
    python -m irene.examples.multilingual_demo
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from irene.utils.text_processing import all_num_to_text


def test_lingua_franca_availability():
    """Check if lingua-franca is available."""
    try:
        import lingua_franca  # type: ignore
        return True, lingua_franca.__version__
    except ImportError:
        return False, None


def demo_text_processing():
    """Demonstrate text processing with and without lingua-franca."""
    available, version = test_lingua_franca_availability()
    
    print("🌍 Multilingual Text Processing Demo")
    print("=" * 50)
    
    if available:
        print(f"✅ lingua-franca {version} is available")
        print("🎉 Enhanced multilingual support enabled!")
    else:
        print("❌ lingua-franca not available")
        print("📝 Using Russian fallback implementation")
    
    print()
    
    test_cases = [
        "У меня 123 рубля и 45 копеек",
        "Температура -10.5 градусов",
        "Скидка 25% на товары от 1000 до 5000 рублей",
        "I have 42 dollars and 75 cents",  # English
        "J'ai 123 euros et 45 centimes",   # French  
        "Ich habe 99 Euro und 50 Cent",    # German
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"Test {i}: {text}")
        try:
            result = all_num_to_text(text, language="ru")
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
        print()


def show_installation_guide():
    """Show installation guide for multilingual support."""
    print("💡 Installation Guide")
    print("=" * 50)
    
    available, version = test_lingua_franca_availability()
    
    if not available:
        print("To enable enhanced multilingual support, install lingua-franca:")
        print()
        print("🔧 Installation Options:")
        print("1. Add multilingual support:")
        print("   uv add irene-voice-assistant[text-multilingual]")
        print()
        print("2. Add to existing installation:")
        print("   uv add 'lingua-franca>=0.4.0'")
        print()
        print("3. Full voice assistant with multilingual:")
        print("   uv add irene-voice-assistant[voice]")
        print("   (already includes text-multilingual)")
        print()
        print("📋 Benefits of lingua-franca:")
        print("- Enhanced number pronunciation")
        print("- Multi-language date/time formatting")
        print("- Better text parsing capabilities")
        print("- Support for 75+ languages")
    else:
        print("✅ lingua-franca is already installed!")
        print(f"Version: {version}")
        print()
        print("🎯 You have enhanced multilingual support:")
        print("- Improved number pronunciation")
        print("- Multi-language text processing")
        print("- Better parsing for dates and times")
        print("- Support for 75+ languages")


def show_usage_examples():
    """Show code examples for developers."""
    print("👨‍💻 Usage Examples")
    print("=" * 50)
    
    print("Basic usage (works with or without lingua-franca):")
    print("""
from irene.utils import all_num_to_text_async

# Async text processing (recommended for v13 plugins)
normalized = await all_num_to_text_async("У меня 123 рубля", language="ru")

# Synchronous version
from irene.utils import all_num_to_text
normalized = all_num_to_text("I have 42 dollars", language="en")
""")
    
    print("Advanced usage with lingua-franca (when available):")
    print("""
try:
    import lingua_franca
    lingua_franca.load_language("en")
    # Enhanced multilingual processing available
except ImportError:
    # Graceful fallback to Russian implementation
    pass

# Your code works the same way regardless!
result = all_num_to_text("Some text with 123 numbers")
""")


def main():
    """Run multilingual demonstration."""
    print("🎯 Irene Voice Assistant - Multilingual Support Demo")
    print("=" * 70)
    print()
    
    demo_text_processing()
    show_installation_guide()
    show_usage_examples()
    
    print("=" * 70)
    print("🌟 Key Benefits:")
    print("✅ Works perfectly without lingua-franca (Russian fallback)")
    print("✅ Enhanced capabilities when lingua-franca is installed")
    print("✅ No code changes needed - automatic detection")
    print("✅ Optional dependency keeps core installation lightweight")
    print("✅ Users choose their level of multilingual support")


if __name__ == "__main__":
    main() 