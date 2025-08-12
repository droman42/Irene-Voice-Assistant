"""
Workflow System

The workflow system orchestrates the complete voice assistant pipeline:
Audio → Voice Trigger → ASR → Text Processing → Intent Recognition → Intent Execution → Response

Workflows:
- UnifiedVoiceAssistantWorkflow: Single workflow for all entry points with conditional stages
"""

from .base import Workflow, RequestContext
from .voice_assistant import UnifiedVoiceAssistantWorkflow

__all__ = [
    'Workflow',
    'RequestContext', 
    'UnifiedVoiceAssistantWorkflow'
] 