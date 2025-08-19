"""
NLU Providers

Natural Language Understanding providers for intent recognition and entity extraction.
"""

from .base import NLUProvider
from .spacy_provider import SpaCyNLUProvider

__all__ = [
    'NLUProvider',
    'SpaCyNLUProvider'
] 