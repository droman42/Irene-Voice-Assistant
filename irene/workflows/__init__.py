"""
Workflow System

The workflow system orchestrates the complete voice assistant pipeline:
Audio → Voice Trigger → ASR → Text Processing → Intent Recognition → Intent Execution → Response

Workflows:
- VoiceAssistantWorkflow: Complete pipeline with wake word detection
- ContinuousListeningWorkflow: Direct ASR processing for backward compatibility
"""

from .base import Workflow, RequestContext
from .voice_assistant import VoiceAssistantWorkflow
from .continuous_listening import ContinuousListeningWorkflow

__all__ = [
    'Workflow',
    'RequestContext', 
    'VoiceAssistantWorkflow',
    'ContinuousListeningWorkflow'
] 