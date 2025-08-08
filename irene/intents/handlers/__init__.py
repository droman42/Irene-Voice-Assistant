"""
Intent Handlers - Processing specific intent types

Intent handlers are now discovered dynamically via entry-points.
This module provides only the base class and minimal exports for backward compatibility.
"""

from .base import IntentHandler

# NOTE: Specific handler classes are no longer imported here.
# They are discovered dynamically via entry-points by the IntentHandlerManager.
# This eliminates hardcoded loading patterns and enables configuration-driven filtering.

__all__ = [
    'IntentHandler',
    # Individual handlers are now discovered via entry-points
    # See: IntentHandlerManager in irene.intents.manager
] 