"""
Conversation Intent Handler - Interactive LLM Chat for Intent System

Provides conversational interactions using LLM components.
Adapted from conversation_plugin.py for the new intent architecture.
"""

import logging
import time
from typing import Dict, List, Optional, Any, Type, TYPE_CHECKING

from .base import IntentHandler
from ..models import Intent, IntentResult, UnifiedConversationContext, ConversationState, ContextLayer

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ConversationSession class removed - functionality moved to UnifiedConversationContext.handler_contexts


class ConversationIntentHandler(IntentHandler):
    """
    Handles conversational intents with LLM integration.
    
    Manages conversation flow, maintains context, and provides 
    intelligent responses using Large Language Models.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.conversation_context: List[Dict[str, str]] = []
# Session management now handled by UnifiedConversationContext handler_contexts
        self.llm_component = None
        
        # Phase 5: Configuration injection via Pydantic ConversationHandlerConfig
        if config:
            self.config = config
            self.max_context_length = config.get("max_context_length", 10)
            logger.info(f"ConversationIntentHandler initialized with config: session_timeout={config.get('session_timeout')}, max_sessions={config.get('max_sessions')}, max_context_length={self.max_context_length}")
        else:
            # Fallback defaults (should not be used in production with proper config)
            self.config = {
                "session_timeout": 1800,  # 30 minutes
                "max_sessions": 50,
                "max_context_length": 10,
                "default_conversation_confidence": 0.6  # Lower confidence for fallback
            }
            self.max_context_length = 10
            logger.warning("ConversationIntentHandler initialized without configuration - using fallback defaults")
    
    # Build dependency methods (TODO #5 Phase 2)
    @classmethod
    def get_python_dependencies(cls) -> List[str]:
        """Conversation handler needs no external dependencies - uses LLM providers through components"""
        return []
        
    @classmethod
    def get_platform_dependencies(cls) -> Dict[str, List[str]]:
        """Conversation handler has no system dependencies - uses LLM providers through components"""
        return {
            "linux.ubuntu": [],
            "linux.alpine": [],
            "macos": [],
            "windows": []
        }
        
    @classmethod
    def get_platform_support(cls) -> List[str]:
        """Conversation handler supports all platforms"""
        return ["linux.ubuntu", "linux.alpine", "macos", "windows"]
    
    # Configuration metadata methods
    @classmethod
    def get_config_schema(cls) -> Type["BaseModel"]:
        """Return configuration schema for conversation handler"""
        from ...config.models import ConversationHandlerConfig
        return ConversationHandlerConfig
    
    @classmethod
    def get_config_defaults(cls) -> Dict[str, Any]:
        """Return default configuration values matching TOML"""
        return {
            "session_timeout": 1800,  # matches config-master.toml line 414
            "max_sessions": 50,       # matches config-master.toml line 415
            "max_context_length": 10, # matches config-master.toml line 416
            "default_conversation_confidence": 0.6  # matches config-master.toml line 417
        }
        
    async def can_handle(self, intent: Intent) -> bool:
        """Check if this handler can process conversation intents"""
        if not self.has_donation():
            raise RuntimeError(f"ConversationIntentHandler: Missing JSON donation file - conversation.json is required")
        
        # Use JSON donation patterns exclusively
        donation = self.get_donation()
        
        # Check domain patterns
        if hasattr(donation, 'domain_patterns') and intent.domain in donation.domain_patterns:
            return True
        
        # Check intent name patterns
        if hasattr(donation, 'intent_name_patterns') and intent.name in donation.intent_name_patterns:
            return True
        
        # Check action patterns
        if hasattr(donation, 'action_patterns') and intent.action in donation.action_patterns:
            return True
        
        # Check fallback conditions
        if hasattr(donation, 'fallback_conditions'):
            for condition in donation.fallback_conditions:
                if (intent.domain == condition.get('domain') and 
                    intent.confidence < condition.get('confidence_threshold', 1.0)):
                    return True
        
        return False
    
    async def execute(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Execute conversation intent using LLM or fallback handling"""
        try:
            # Check if this is a fallback scenario (when NLU failed to recognize intent)
            is_fallback = intent.entities.get("_recognition_provider") == "fallback"
            
            # For fallback scenarios, check if LLM is available before deciding on fallback approach
            if is_fallback:
                llm_component = await self._get_llm_component()
                if llm_component and await llm_component.is_available():
                    # LLM is available - treat as conversation.general and use LLM
                    logger.info(f"NLU fallback detected but LLM available - using LLM for: {intent.raw_text}")
                    return await self._handle_continue_conversation(intent, context)
                else:
                    # LLM not available - use template-based fallback
                    logger.info(f"NLU fallback detected and LLM unavailable - using templates for: {intent.raw_text}")
                    return await self._handle_fallback_without_llm(intent, context)
            
            # Handle specific conversation actions using unified context
            if intent.action == "start":
                return await self._handle_start_conversation(intent, context)
            elif intent.action == "end":
                return await self._handle_end_conversation(intent, context)
            elif intent.action == "clear":
                return await self._handle_clear_conversation(intent, context)
            elif intent.action == "reference":
                return await self._handle_reference_query(intent, context)
            else:
                # Default: continue conversation
                return await self._handle_continue_conversation(intent, context)
                
        except Exception as e:
            logger.error(f"Conversation intent execution failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка в обработке диалога.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    def set_llm_component(self, llm_component):
        """Set the LLM component reference"""
        self.llm_component = llm_component
    
    async def _get_llm_component(self):
        """Get LLM component from core (dynamic access pattern)"""
        if self.llm_component is None:
            try:
                from ...core.engine import get_core
                core = get_core()
                if core and hasattr(core, 'component_manager'):
                    self.llm_component = await core.component_manager.get_component('llm')
            except Exception as e:
                self.logger.error(f"Failed to get LLM component: {e}")
                return None
        
        return self.llm_component
    
    def _get_prompt(self, prompt_type: str, language: str = "ru") -> str:
        """Get prompt from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"ConversationIntentHandler: Asset loader not initialized. "
                f"Cannot access prompt '{prompt_type}' for language '{language}'. "
                f"This is a fatal configuration error - prompts must be externalized."
            )
        
        # Get prompt from asset loader
        prompt = self.asset_loader.get_prompt("conversation", prompt_type, language)
        if prompt is None:
            raise RuntimeError(
                f"ConversationIntentHandler: Required prompt '{prompt_type}' for language '{language}' "
                f"not found in assets/prompts/conversation/{language}/conversation_prompts.yaml. "
                f"This is a fatal error - all conversation prompts must be externalized."
            )
        
        return prompt

    def _get_template_data(self, template_name: str, language: str = "ru") -> List[str]:
        """Get template data (arrays) from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"ConversationIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - templates must be externalized."
            )
        
        # Get template from asset loader
        template_data = self.asset_loader.get_template("conversation", template_name, language)
        if template_data is None:
            raise RuntimeError(
                f"ConversationIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/conversation/{language}/responses.yaml. "
                f"This is a fatal error - all conversation templates must be externalized."
            )
        
        # Ensure it's a list
        if not isinstance(template_data, list):
            raise RuntimeError(
                f"ConversationIntentHandler: Template '{template_name}' should be a list but got {type(template_data)}. "
                f"Check assets/templates/conversation/{language}/responses.yaml"
            )
        
        return template_data

    def _get_template(self, template_name: str, language: str = "ru", **format_args) -> str:
        """Get template string from asset loader - raises fatal error if not available"""
        if not self.has_asset_loader():
            raise RuntimeError(
                f"ConversationIntentHandler: Asset loader not initialized. "
                f"Cannot access template '{template_name}' for language '{language}'. "
                f"This is a fatal configuration error - templates must be externalized."
            )
        
        # Get template from asset loader
        template_content = self.asset_loader.get_template("conversation", template_name, language)
        if template_content is None:
            raise RuntimeError(
                f"ConversationIntentHandler: Required template '{template_name}' for language '{language}' "
                f"not found in assets/templates/conversation/{language}/responses.yaml. "
                f"This is a fatal error - all conversation templates must be externalized."
            )
        
        # Format template with provided arguments if any
        if format_args:
            try:
                return template_content.format(**format_args)
            except KeyError as e:
                raise RuntimeError(
                    f"ConversationIntentHandler: Template '{template_name}' missing required format argument: {e}. "
                    f"Check assets/templates/conversation/{language}/responses.yaml for correct placeholders."
                )
        
        return template_content
    
    async def is_available(self) -> bool:
        """Check if LLM component is available for conversation"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return False
        return await llm_component.is_available()
    
# Session management removed - now handled by UnifiedConversationContext handler_contexts
    
    async def _handle_start_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle conversation start intent"""
        # Clear any existing conversation history in unified context
        conversation_type = "reference" if intent.action == "reference" else "chat"
        system_prompt = (self._get_prompt("reference_system") if conversation_type == "reference" 
                        else self._get_prompt("chat_system"))
        
        # Initialize or reset handler context for conversation
        handler_context = context.get_handler_context("conversation")
        handler_context["conversation_type"] = conversation_type
        handler_context["model_preference"] = ""
        
        # Clear and set system message if needed
        context.clear_handler_context("conversation", keep_system=True)
        if system_prompt and not handler_context["messages"]:
            handler_context["messages"] = [{"role": "system", "content": system_prompt}]
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get greeting templates from asset loader
        greetings = self._get_template_data("start_greetings", language)
        
        import random
        response = random.choice(greetings)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={
                "conversation_type": conversation_type,
                "session_id": context.session_id
            }
        )
    
    async def _handle_end_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle conversation end intent"""
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get farewell templates from asset loader
        farewells = self._get_template_data("end_farewells", language)
        
        import random
        response = random.choice(farewells)
        
        # Clear conversation handler context
        context.clear_handler_context("conversation", keep_system=False)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"conversation_ended": True}
        )
    
    async def _handle_clear_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle conversation clear/reset intent"""
        # Clear conversation handler context but keep system message
        context.clear_handler_context("conversation", keep_system=True)
        
        # Use language from context (detected by NLU)
        language = context.language or "ru"
        
        # Get clear response template from asset loader
        response = self._get_template("clear_response", language)
        
        return IntentResult(
            text=response,
            should_speak=True,
            metadata={"conversation_cleared": True}
        )
    
    async def _handle_reference_query(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle reference/factual query intent"""
        llm_component = await self._get_llm_component()
        if not llm_component:
            return IntentResult(
                text="Извините, справочный режим недоступен.",
                should_speak=True,
                success=False
            )
        
        # Format query for reference mode
        query = intent.raw_text
        template = self._get_prompt("reference_template")
        formatted_prompt = template.format(query)
        
        try:
            # Use LLM component's default model for factual queries
            response = await llm_component.generate_response(
                messages=[{"role": "user", "content": formatted_prompt}],
                trace_context=self._trace_context
            )
            
            return IntentResult(
                text=response,
                should_speak=True,
                metadata={
                    "conversation_type": "reference",
                    "query": query
                }
            )
            
        except Exception as e:
            logger.error(f"Reference query failed: {e}")
            return IntentResult(
                text="Извините, не удалось получить справочную информацию.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    
    async def _handle_continue_conversation(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """Handle ongoing conversation intent - donation-compatible method signature"""
        # Note: Fallback logic is now handled in execute() method, not here
        
        # For conversation (including NLU fallback when LLM is available), require LLM
        llm_component = await self._get_llm_component()
        if not llm_component:
            return IntentResult(
                text="Извините, диалоговый режим недоступен.",
                should_speak=True,
                success=False
            )
        
        try:
            # Get or create conversation handler context
            handler_context = context.get_handler_context("conversation")
            
            # Check if this was an NLU fallback that we're now handling with LLM
            is_fallback = intent.entities.get("_recognition_provider") == "fallback"
            fallback_context = intent.entities.get("_fallback_context")
            
            # Manage conversation state transitions (Phase 2)
            self._manage_conversation_state(context, intent, is_fallback)
            
            if is_fallback:
                logger.debug(f"Processing NLU fallback with LLM: '{intent.raw_text}' -> conversation.general")
                
                # Inject fallback context information if available
                if fallback_context:
                    context_prompt = self._build_fallback_context_prompt(fallback_context)
                    handler_context["messages"].append({
                        "role": "system", 
                        "content": context_prompt
                    })
            
            # Add user message to handler context (LLM-specific conversation management)
            handler_context["messages"].append({"role": "user", "content": intent.raw_text})
            
            # Prepare LLM context with smart contextual information injection
            messages = self._prepare_llm_context(intent, context, handler_context)
            
            # Phase 3: Detect domain for threading (before generating response)
            target_domain = self._detect_conversation_domain(intent, context)
            
            # Generate response using LLM component's default model
            response = await llm_component.generate_response(
                messages=messages,
                trace_context=self._trace_context
            )
            
            # Add assistant response to handler context
            handler_context["messages"].append({"role": "assistant", "content": response})
            
            # Phase 3: Save response to domain thread if applicable
            if target_domain:
                self._save_assistant_response_to_thread(target_domain, response, context)
            
            return IntentResult(
                text=response,
                should_speak=True,
                metadata={
                    "conversation_type": handler_context.get("conversation_type", "chat"),
                    "message_count": len(handler_context["messages"]),
                    "session_id": context.session_id,
                    "nlu_fallback_handled_by_llm": is_fallback,
                    "original_recognition_provider": intent.entities.get("_recognition_provider"),
                    "cascade_attempts": intent.entities.get("_cascade_attempts", 0),
                    # Phase 2: Add conversation state information
                    "conversation_state": context.get_conversation_state().value,
                    "state_duration": context.get_state_duration(),
                    "context_injection_active": bool(context.active_actions or self._has_recent_domain_activity(context, intent)),
                    # Phase 3: Add threading information
                    "threading_domain": target_domain,
                    "active_threads": len(context.get_active_threads()) if target_domain else 0,
                    "thread_message_count": context.get_thread_summary(target_domain)["message_count"] if target_domain else 0,
                    # Phase 3: Add progressive context information
                    "context_layers_used": len(context.resolve_layered_context([ContextLayer.SESSION, ContextLayer.ACTION, ContextLayer.THREAD], target_domain)),
                    "progressive_context_active": bool(target_domain or context.active_actions or context.get_active_threads())
                }
            )
            
        except Exception as e:
            logger.error(f"Conversation continuation failed: {e}")
            return IntentResult(
                text="Извините, произошла ошибка в диалоге. Попробуйте ещё раз.",
                should_speak=True,
                success=False,
                error=str(e)
            )
    async def _handle_fallback_without_llm(self, intent: Intent, context: UnifiedConversationContext) -> IntentResult:
        """
        Handle fallback scenario when NLU failed to recognize intent.
        
        This method works without LLM and provides helpful feedback to the user
        about their unrecognized input, encouraging them to rephrase or use specific commands.
        
        Args:
            intent: The fallback intent containing original user text
            context: Conversation context with language information
            
        Returns:
            IntentResult with helpful fallback response and suggestions
        """
        try:
            # Use language from context (detected by NLU) or default to Russian
            language = context.language or "ru"
            
            # Get the original text that couldn't be recognized
            original_text = intent.raw_text or intent.entities.get("original_text", "")
            
            # Get fallback response templates
            fallback_responses = self._get_template_data("fallback_no_llm_responses", language)
            help_suggestions = self._get_template_data("fallback_help_suggestions", language)
            
            # Select random responses
            import random
            fallback_response = random.choice(fallback_responses)
            help_suggestion = random.choice(help_suggestions)
            
            # Format the response with the original text
            formatted_response = fallback_response.format(original_text=original_text)
            
            # Combine response with helpful suggestion
            full_response = f"{formatted_response} {help_suggestion}"
            
            # Get cascade attempt information if available
            cascade_attempts = intent.entities.get("_cascade_attempts", 0)
            
            logger.info(f"Handled fallback without LLM: original_text='{original_text}', "
                       f"cascade_attempts={cascade_attempts}, language={language}")
            
            return IntentResult(
                text=full_response,
                should_speak=True,
                success=True,  # This is successful fallback handling, not an error
                metadata={
                    "conversation_type": "fallback",
                    "original_text": original_text,
                    "cascade_attempts": cascade_attempts,
                    "language": language,
                    "recognition_provider": "fallback",
                    "llm_required": False
                }
            )
            
        except Exception as e:
            logger.error(f"Fallback handling failed: {e}")
            
            # Final emergency fallback - hardcoded message
            language = context.language or "ru"
            if language == "en":
                emergency_response = f"I couldn't understand '{intent.raw_text}'. Please try using simpler commands."
            else:
                emergency_response = f"Я не понимаю '{intent.raw_text}'. Попробуйте использовать более простые команды."
            
            return IntentResult(
                text=emergency_response,
                should_speak=True,
                success=True,
                metadata={
                    "conversation_type": "emergency_fallback",
                    "error": str(e)
                }
            )
    
    def _build_fallback_context_prompt(self, fallback_context: Dict[str, Any]) -> str:
        """Build context prompt for LLM when handling NLU fallback."""
        context_parts = []
        
        # Add information about what the user was likely trying to do
        likely_domain = fallback_context.get("likely_domain")
        likely_action = fallback_context.get("likely_action")
        
        if likely_domain or likely_action:
            context_parts.append("Context: The user's request seems to be related to")
            if likely_domain:
                context_parts.append(f"the {likely_domain} domain")
            if likely_action:
                action_part = f"and trying to {likely_action} something" if likely_domain else f"trying to {likely_action} something"
                context_parts.append(action_part)
            context_parts.append(".")
        
        # Add information about ambiguous entities
        ambiguous_entities = fallback_context.get("ambiguous_entities", [])
        if ambiguous_entities:
            context_parts.append(f"Detected potential entities: {', '.join(ambiguous_entities[:3])}")  # Limit to 3 entities
        
        # Add information about provider attempts
        provider_attempts = fallback_context.get("provider_attempts", [])
        if provider_attempts:
            attempted_providers = [attempt["provider"] for attempt in provider_attempts]
            context_parts.append(f"NLU providers attempted: {', '.join(attempted_providers)}")
        
        context_parts.append("Please help the user clarify their request or provide helpful suggestions.")
        
        return " ".join(context_parts)
    
    def _prepare_llm_context(self, intent: Intent, context: UnifiedConversationContext, handler_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Prepare contextually appropriate information for LLM"""
        # Phase 3: Detect if this is a domain-specific conversation
        target_domain = self._detect_conversation_domain(intent, context)
        
        if target_domain:
            # Use domain-specific thread for enhanced continuity
            messages = self._prepare_threaded_context(target_domain, intent, context, handler_context)
        else:
            # Use general conversation context
            messages = handler_context["messages"].copy()
        
        # Smart context injection - insert system messages before the user's current message
        context_messages = []
        
        # 1. Inject active actions summary if present
        if context.active_actions:
            actions_summary = self._build_active_actions_summary(context.active_actions)
            context_messages.append({
                "role": "system",
                "content": f"Currently active: {actions_summary}"
            })
        
        # 2. Inject recent domain activity context if relevant
        if self._has_recent_domain_activity(context, intent):
            domain_context = self._build_domain_context_summary(context, intent)
            context_messages.append({
                "role": "system",
                "content": domain_context
            })
        
        # 3. Inject domain thread context if using threading
        if target_domain:
            thread_context = self._build_thread_context_summary(target_domain, context)
            if thread_context:
                context_messages.append({
                    "role": "system",
                    "content": thread_context
                })
        
        # 4. Phase 3: Inject progressive layered context
        layered_context = self._build_progressive_context_summary(intent, context, target_domain)
        if layered_context:
            context_messages.append({
                "role": "system",
                "content": layered_context
            })
        
        # 4. Special handling for fallback conversations (already handled in main method)
        # Note: Fallback context injection is already handled in the main method above
        
        # Insert context messages before the latest user message
        if context_messages and len(messages) > 0:
            # Insert all context messages before the last user message
            user_message = messages.pop()  # Remove last user message temporarily
            messages.extend(context_messages)  # Add context messages
            messages.append(user_message)  # Re-add user message at the end
        
        return messages
    
    def _build_active_actions_summary(self, active_actions: Dict[str, Any]) -> str:
        """Build a summary of currently active actions for LLM context"""
        if not active_actions:
            return "No active actions"
        
        summaries = []
        for domain, action_info in active_actions.items():
            action_name = action_info.get("action", "unknown")
            started_at = action_info.get("started_at", 0)
            metadata = action_info.get("metadata", {})
            
            # Calculate duration
            import time
            duration = time.time() - started_at
            duration_str = f"{int(duration)}s ago" if duration < 60 else f"{int(duration/60)}m ago"
            
            # Build action summary
            summary_parts = [f"{domain}.{action_name} (started {duration_str})"]
            
            # Add relevant metadata
            if metadata:
                relevant_metadata = []
                for key, value in metadata.items():
                    if key in ["track", "artist", "volume", "duration", "timer_name", "text"]:
                        relevant_metadata.append(f"{key}: {value}")
                if relevant_metadata:
                    summary_parts.append(f"[{', '.join(relevant_metadata)}]")
            
            summaries.append(" ".join(summary_parts))
        
        return "; ".join(summaries)
    
    def _has_recent_domain_activity(self, context: UnifiedConversationContext, intent: Intent) -> bool:
        """Check if there's recent activity in domains related to the current intent"""
        # Check if there are recent actions in the conversation history
        if not context.recent_actions:
            return False
        
        # Look at the last 3 actions to see if they're relevant
        import time
        current_time = time.time()
        recent_threshold = 300  # 5 minutes
        
        recent_relevant_actions = []
        for action in context.recent_actions[-3:]:
            completed_at = action.get("completed_at", 0)
            if current_time - completed_at < recent_threshold:
                action_domain = action.get("domain", "")
                # Check if this domain might be relevant to current intent
                if self._is_domain_relevant(action_domain, intent):
                    recent_relevant_actions.append(action)
        
        return len(recent_relevant_actions) > 0
    
    def _is_domain_relevant(self, action_domain: str, intent: Intent) -> bool:
        """Check if an action domain is relevant to the current intent"""
        # Check for direct domain match
        if intent.domain == action_domain:
            return True
        
        # Check for related domains
        domain_relationships = {
            "audio": ["music", "sound", "volume"],
            "timer": ["time", "alarm", "reminder"],
            "system": ["status", "config", "settings"],
            "translation": ["language", "translate"]
        }
        
        intent_keywords = intent.raw_text.lower() if intent.raw_text else ""
        
        if action_domain in domain_relationships:
            related_keywords = domain_relationships[action_domain]
            return any(keyword in intent_keywords for keyword in related_keywords)
        
        return False
    
    def _build_domain_context_summary(self, context: UnifiedConversationContext, intent: Intent) -> str:
        """Build a summary of recent domain-specific activity for LLM context"""
        if not context.recent_actions:
            return ""
        
        # Get recent relevant actions
        import time
        current_time = time.time()
        recent_threshold = 300  # 5 minutes
        
        relevant_actions = []
        for action in context.recent_actions[-5:]:  # Last 5 actions
            completed_at = action.get("completed_at", 0)
            if current_time - completed_at < recent_threshold:
                action_domain = action.get("domain", "")
                if self._is_domain_relevant(action_domain, intent):
                    relevant_actions.append(action)
        
        if not relevant_actions:
            return ""
        
        # Build context summary
        summaries = []
        for action in relevant_actions[-3:]:  # Last 3 relevant actions
            domain = action.get("domain", "unknown")
            action_name = action.get("action", "unknown")
            success = action.get("success", True)
            completed_at = action.get("completed_at", 0)
            
            # Calculate time ago
            time_ago = current_time - completed_at
            time_str = f"{int(time_ago)}s ago" if time_ago < 60 else f"{int(time_ago/60)}m ago"
            
            # Build action description
            status = "completed" if success else "failed"
            summary = f"{domain}.{action_name} ({status} {time_str})"
            
            # Add error info if failed
            if not success and action.get("error"):
                summary += f" - {action['error']}"
            
            summaries.append(summary)
        
        return f"Recent activity: {'; '.join(summaries)}"
    
    def _manage_conversation_state(self, context: UnifiedConversationContext, intent: Intent, is_fallback: bool) -> None:
        """Manage conversation state transitions based on intent and context"""
        current_state = context.get_conversation_state()
        
        # Determine target state based on intent type and context
        target_state = self._determine_target_state(context, intent, is_fallback)
        
        if target_state != current_state:
            # Prepare state context
            state_context = self._build_state_context(intent, is_fallback)
            
            # Attempt state transition
            if context.transition_state(target_state, state_context):
                logger.debug(f"Conversation state transition: {current_state.value} → {target_state.value}")
            else:
                logger.warning(f"Invalid conversation state transition: {current_state.value} → {target_state.value}")
    
    def _determine_target_state(self, context: UnifiedConversationContext, intent: Intent, is_fallback: bool) -> ConversationState:
        """Determine the appropriate target state based on intent and context"""
        current_state = context.get_conversation_state()
        
        # Handle fallback scenarios (NLU failure)
        if is_fallback:
            if current_state == ConversationState.IDLE:
                return ConversationState.CLARIFYING
            elif current_state == ConversationState.CONVERSING:
                return ConversationState.CLARIFYING
            else:
                return ConversationState.CLARIFYING
        
        # Handle conversation ending scenarios (check before general conversation)
        if self._is_conversation_ending_intent(intent):
            return ConversationState.IDLE
        
        # Handle regular conversation intents
        if intent.name == "conversation.general":
            if current_state == ConversationState.IDLE:
                return ConversationState.CONVERSING
            elif current_state == ConversationState.CLARIFYING:
                return ConversationState.CONVERSING
            else:
                return ConversationState.CONVERSING
        
        # Handle contextual commands (if they ever route through conversation handler)
        if intent.domain == "contextual":
            return ConversationState.CONTEXTUAL
        
        # Default: maintain current state or go to conversing
        if current_state == ConversationState.IDLE:
            return ConversationState.CONVERSING
        else:
            return current_state
    
    def _build_state_context(self, intent: Intent, is_fallback: bool) -> Dict[str, Any]:
        """Build context data for the new conversation state"""
        state_context = {
            "last_intent": intent.name,
            "last_raw_text": intent.raw_text,
            "is_fallback": is_fallback,
            "timestamp": time.time()
        }
        
        # Add fallback-specific context
        if is_fallback:
            fallback_data = intent.entities.get("_fallback_context")
            if fallback_data:
                state_context["fallback_info"] = {
                    "likely_domain": fallback_data.get("likely_domain"),
                    "likely_action": fallback_data.get("likely_action"),
                    "provider_attempts": len(fallback_data.get("provider_attempts", []))
                }
        
        # Add conversation-specific context
        if intent.name == "conversation.general":
            state_context["conversation_type"] = "general"
            
        return state_context
    
    def _is_conversation_ending_intent(self, intent: Intent) -> bool:
        """Check if the intent indicates conversation should end"""
        # Check for explicit conversation ending patterns
        ending_patterns = [
            "пока", "досвидания", "спасибо", "хватит", "стоп",
            "bye", "goodbye", "thanks", "stop", "enough", "end"
        ]
        
        text_lower = intent.raw_text.lower() if intent.raw_text else ""
        return any(pattern in text_lower for pattern in ending_patterns)
    
    def _detect_conversation_domain(self, intent: Intent, context: UnifiedConversationContext) -> Optional[str]:
        """Detect if the conversation is domain-specific and should use threading"""
        text_lower = intent.raw_text.lower() if intent.raw_text else ""
        
        # Domain detection keywords
        domain_keywords = {
            "audio": ["music", "song", "play", "volume", "sound", "audio", "track", "громкость", "музыка", "песня"],
            "timer": ["timer", "alarm", "remind", "schedule", "таймер", "будильник", "напомни"],
            "system": ["status", "system", "component", "service", "статус", "система", "компонент"],
            "translation": ["translate", "language", "переведи", "язык", "перевод"],
            "datetime": ["time", "date", "when", "schedule", "время", "дата", "когда"]
        }
        
        # Check for domain keywords in user text
        for domain, keywords in domain_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return domain
        
        # Check for active actions in the same domain
        if context.active_actions:
            for domain in context.active_actions.keys():
                if self._is_domain_relevant(domain, intent):
                    return domain
        
        # Check for recent domain activity
        active_threads = context.get_active_threads(since_seconds=600)  # 10 minutes
        if active_threads:
            # Use the most recent active thread if the conversation seems related
            for domain in active_threads:
                if self._is_domain_relevant(domain, intent):
                    return domain
        
        return None
    
    def _prepare_threaded_context(self, domain: str, intent: Intent, context: UnifiedConversationContext, handler_context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Prepare LLM context using domain-specific thread"""
        # Get domain-specific thread messages
        thread_messages = context.get_thread_messages(domain, limit=10)  # Last 10 messages in this domain
        
        # Convert thread messages to LLM format
        domain_context = []
        for msg in thread_messages:
            domain_context.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Combine with recent general conversation if thread is sparse
        if len(domain_context) < 4:  # If less than 4 messages in domain thread
            # Add some general context for continuity
            general_messages = handler_context["messages"][-4:]  # Last 4 general messages
            
            # Merge contexts, preferring domain-specific messages
            combined_messages = general_messages + domain_context
        else:
            combined_messages = domain_context
        
        # Add current user message to domain thread
        context.add_to_thread(domain, "user", intent.raw_text, {"intent": intent.name})
        
        # Include the current user message in the context
        combined_messages.append({
            "role": "user",
            "content": intent.raw_text
        })
        
        return combined_messages
    
    def _build_thread_context_summary(self, domain: str, context: UnifiedConversationContext) -> str:
        """Build summary of domain thread context for LLM"""
        thread_summary = context.get_thread_summary(domain)
        thread_context = context.get_thread_context(domain)
        
        context_parts = []
        
        # Add thread information
        if thread_summary["message_count"] > 0:
            context_parts.append(f"Domain thread '{domain}': {thread_summary['message_count']} messages")
        
        # Add active context information
        if thread_context:
            context_keys = list(thread_context.keys())[:3]  # Limit to 3 keys
            if context_keys:
                context_parts.append(f"Active context: {', '.join(context_keys)}")
        
        # Add thread age if recent
        if thread_summary["age_seconds"] < 3600:  # Less than 1 hour
            age_minutes = int(thread_summary["age_seconds"] / 60)
            context_parts.append(f"Thread age: {age_minutes}m")
        
        return " | ".join(context_parts) if context_parts else ""
    
    def _save_assistant_response_to_thread(self, domain: str, response: str, context: UnifiedConversationContext) -> None:
        """Save assistant response to the appropriate domain thread"""
        if domain:
            context.add_to_thread(domain, "assistant", response, {"response_type": "threaded"})
    
    def _build_progressive_context_summary(self, intent: Intent, context: UnifiedConversationContext, domain: Optional[str] = None) -> str:
        """Build progressive context summary using layered context resolution"""
        # Define context layers based on conversation type and domain
        if domain:
            # Domain-specific conversation: prioritize thread and action context
            priority_layers = [ContextLayer.THREAD, ContextLayer.ACTION, ContextLayer.SESSION]
        else:
            # General conversation: prioritize intent and session context
            priority_layers = [ContextLayer.INTENT, ContextLayer.ACTION, ContextLayer.SESSION]
        
        # Resolve layered context
        layered_context = context.resolve_layered_context(priority_layers, domain)
        
        # Build human-readable summary
        context_parts = []
        
        # Process each layer
        for layer_name, layer_data in layered_context.items():
            layer_summary = self._summarize_context_layer(layer_name, layer_data, domain)
            if layer_summary:
                context_parts.append(layer_summary)
        
        if context_parts:
            return f"Context layers: {' | '.join(context_parts)}"
        return ""
    
    def _summarize_context_layer(self, layer_name: str, layer_data: Dict[str, Any], domain: Optional[str] = None) -> str:
        """Summarize a specific context layer for LLM consumption"""
        if layer_name == "session":
            # Session layer: room and device info
            room = layer_data.get("room_name", layer_data.get("client_id", "unknown"))
            device_count = len(layer_data.get("available_devices", []))
            return f"Session: {room} ({device_count} devices)"
        
        elif layer_name == "thread" and domain:
            # Thread layer: domain conversation summary
            msg_count = layer_data.get("message_count", 0)
            if msg_count > 0:
                age_min = int(layer_data.get("age_seconds", 0) / 60)
                return f"Thread: {domain} ({msg_count} msgs, {age_min}m)"
        
        elif layer_name == "action":
            # Action layer: active and recent actions
            active_count = len(layer_data.get("active_actions", {}))
            recent_count = len(layer_data.get("recent_actions", []))
            if active_count > 0 or recent_count > 0:
                return f"Actions: {active_count} active, {recent_count} recent"
        
        elif layer_name == "intent":
            # Intent layer: recent conversation flow
            history_count = len(layer_data.get("conversation_history", []))
            state = layer_data.get("state_context", {})
            if history_count > 0:
                state_info = f", state: {len(state)} items" if state else ""
                return f"Intent: {history_count} recent{state_info}"
        
        return ""
    
    def _get_context_coordination_summary(self, context: UnifiedConversationContext, domain: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive context coordination summary for debugging/monitoring"""
        return {
            "domain": domain,
            "contextual_summary": context.get_contextual_summary(domain, max_layers=4),
            "active_threads": context.get_active_threads(),
            "conversation_state": context.get_conversation_state().value,
            "layered_resolution": {
                "session": bool(context.resolve_context(ContextLayer.SESSION)),
                "action": bool(context.resolve_context(ContextLayer.ACTION, domain)),
                "thread": bool(context.resolve_context(ContextLayer.THREAD, domain)) if domain else False,
                "intent": bool(context.resolve_context(ContextLayer.INTENT))
            }
        }

    
    async def cleanup(self) -> None:
        """Clean up conversation sessions - now handled by ContextManager"""
        # Session cleanup is now handled by the ContextManager for UnifiedConversationContext
        # No local session management needed
        logger.debug("Conversation handler cleanup completed - session management delegated to ContextManager") 