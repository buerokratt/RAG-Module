"""LLM Orchestration Service with Fixed DSPy Async Context - Business logic for LLM orchestration."""

import os
import json
import time
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from functools import wraps

from loguru import logger
from langfuse import observe, get_client
import dspy

from llm_config_module.llm_manager import LLMManager
from models.request_models import (
    OrchestrationRequest,
    OrchestrationResponse,
    ConversationItem,
    PromptRefinerOutput,
)
from prompt_refiner_module.prompt_refiner import PromptRefinerAgent


def run_in_thread(func):
    """Decorator to run DSPy operations in a separate thread to avoid async context issues."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        import threading
        import queue
        
        result_queue = queue.Queue()
        exception_queue = queue.Queue()
        
        def thread_worker():
            try:
                result = func(*args, **kwargs)
                result_queue.put(result)
            except Exception as e:
                exception_queue.put(e)
        
        thread = threading.Thread(target=thread_worker)
        thread.start()
        thread.join()
        
        if not exception_queue.empty():
            raise exception_queue.get()
        
        return result_queue.get()
    
    return wrapper


class LLMOrchestrationService:
    """Service class for handling LLM orchestration business logic with Langfuse tracing."""

    def __init__(self) -> None:
        """Initialize the orchestration service with Langfuse."""
        self.llm_manager: Optional[LLMManager] = None
        self._initialize_langfuse()

    def _initialize_langfuse(self) -> None:
        """Initialize Langfuse client for tracing."""
        try:
            # Get the Langfuse client - it will use environment variables automatically
            self.langfuse_client = get_client()
            
            # Check if Langfuse is properly configured
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            
            if secret_key and public_key:
                logger.info("Langfuse tracing initialized successfully")
                logger.info(f"Langfuse host: {os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')}")
            else:
                logger.warning("Langfuse credentials not found - tracing will be disabled")
                self.langfuse_client = None
            
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {str(e)}")
            # Don't fail the service if Langfuse initialization fails
            self.langfuse_client = None

    @observe(name="orchestration_request")
    def process_orchestration_request(
        self, request: OrchestrationRequest
    ) -> OrchestrationResponse:
        """
        Process an orchestration request and return response with comprehensive tracing.

        Args:
            request: The orchestration request containing user message and context

        Returns:
            OrchestrationResponse: Response with LLM output and status flags
        """
        # Start timing for performance metrics
        start_time = time.time()
        
        try:
            logger.info(
                f"Processing orchestration request for chatId: {request.chatId}, "
                f"authorId: {request.authorId}, environment: {request.environment}"
            )

            # Step 1: Initialize LLM Manager with configuration
            self._initialize_llm_manager_with_tracing(
                environment=request.environment, 
                connection_id=request.connection_id
            )

            # Step 2: Refine user prompt using loaded configuration (with thread safety)
            refined_output = self._refine_user_prompt_with_tracing_safe(
                original_message=request.message,
                conversation_history=request.conversationHistory,
            )

            # Step 3: Generate response (currently hardcoded for testing)
            response = self._generate_hardcoded_response_with_tracing(
                request.chatId, refined_output
            )

            # Calculate processing time
            processing_time = time.time() - start_time

            logger.info(
                f"Successfully processed request for chatId: {request.chatId} "
                f"in {processing_time:.2f}s"
            )
            
            return response

        except Exception as e:
            processing_time = time.time() - start_time
            
            logger.error(
                f"Error processing orchestration request for chatId: {request.chatId}, "
                f"error: {str(e)}, processing_time: {processing_time:.2f}s"
            )

            # Return error response
            error_response = OrchestrationResponse(
                chatId=request.chatId,
                llmServiceActive=False,
                questionOutOfLLMScope=False,
                inputGuardFailed=True,
                content="An error occurred while processing your request. Please try again later.",
            )
            
            return error_response

    @observe(name="llm_manager_initialization")
    def _initialize_llm_manager_with_tracing(
        self, environment: str, connection_id: Optional[str]
    ) -> None:
        """
        Initialize LLM Manager with proper configuration and tracing.

        Args:
            environment: Environment context (production/test/development)
            connection_id: Optional connection identifier
        """
        try:
            logger.info(f"Initializing LLM Manager for environment: {environment}")

            self.llm_manager = LLMManager(
                environment=environment, connection_id=connection_id
            )

            # Get provider information for logging
            available_providers = self.llm_manager.get_available_providers()
            logger.info(f"Available providers: {list(available_providers.keys())}")

            logger.info("LLM Manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize LLM Manager: {str(e)}")
            raise

    @observe(name="prompt_refinement")
    def _refine_user_prompt_with_tracing_safe(
        self, original_message: str, conversation_history: List[ConversationItem]
    ) -> PromptRefinerOutput:
        """
        Thread-safe wrapper for prompt refinement to avoid DSPy async context issues.
        """
        return self._refine_user_prompt_in_thread(original_message, conversation_history)

    @run_in_thread
    def _refine_user_prompt_in_thread(
        self, original_message: str, conversation_history: List[ConversationItem]
    ) -> PromptRefinerOutput:
        """
        Refine user prompt using loaded LLM configuration in a separate thread.
        This avoids DSPy async context conflicts.

        Args:
            original_message: The original user message to refine
            conversation_history: Previous conversation context

        Returns:
            PromptRefinerOutput: The refined prompt output
        """
        logger.info("Starting prompt refinement process (thread-safe)")

        # Check if LLM Manager is initialized
        if self.llm_manager is None:
            error_msg = "LLM Manager not initialized, cannot refine prompts"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            # Convert conversation history to DSPy format
            history: List[Dict[str, str]] = []
            for item in conversation_history:
                role = "assistant" if item.authorRole == "bot" else item.authorRole
                history.append({"role": role, "content": item.message})

            # Create prompt refiner using the same LLM manager instance
            # Reset DSPy configuration in this thread to avoid conflicts
            with dspy.context():
                refiner = PromptRefinerAgent(llm_manager=self.llm_manager)

                # Generate structured prompt refinement output
                start_time = time.time()
                refinement_result = refiner.forward_structured(
                    history=history, question=original_message
                )
                processing_time = time.time() - start_time

            # Validate the output schema using Pydantic
            try:
                validated_output = PromptRefinerOutput(**refinement_result)
            except Exception as validation_error:
                logger.error(
                    f"Prompt refinement output validation failed: {str(validation_error)}"
                )
                logger.error(f"Invalid refinement result: {refinement_result}")
                raise ValueError(
                    f"Prompt refinement validation failed: {str(validation_error)}"
                ) from validation_error

            output_json = validated_output.model_dump()
            
            logger.info(
                f"Prompt refinement completed successfully in {processing_time:.2f}s"
            )
            logger.debug(f"Prompt refinement output: {json.dumps(output_json, indent=2)}")
            
            return validated_output

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Prompt refinement failed: {str(e)}")
            logger.error(f"Failed to refine message: {original_message}")
            
            raise RuntimeError(f"Prompt refinement process failed: {str(e)}") from e

    @observe(name="response_generation")
    def _generate_hardcoded_response_with_tracing(
        self, chat_id: str, refined_output: Optional[PromptRefinerOutput] = None
    ) -> OrchestrationResponse:
        """
        Generate hardcoded response for testing purposes with tracing.

        Args:
            chat_id: Chat session identifier
            refined_output: Optional refined prompt output for context

        Returns:
            OrchestrationResponse with hardcoded values
        """
        logger.info("Generating response")

        # Create more dynamic content based on refined output
        base_content = "This is a comprehensive response with full tracing enabled."
        
        if refined_output:
            refined_questions = getattr(refined_output, 'refined_questions', [])
            if refined_questions:
                base_content += f"\n\nBased on your message, I understand you're asking about: {refined_questions[0]}"
                
                if len(refined_questions) > 1:
                    base_content += f"\n\nI've also considered these alternative interpretations:"
                    for i, alt_question in enumerate(refined_questions[1:3], 1):  # Show max 2 alternatives
                        base_content += f"\n{i}. {alt_question}"

        hardcoded_content = f"""{base_content}

The request has been processed through the complete pipeline:
✅ LLM Manager initialization
✅ Prompt refinement with DSPy context management
✅ Response generation with comprehensive tracing

All operations are being monitored in Langfuse for cost analysis and performance optimization.

References:
- https://gov.ee/sample1
- https://gov.ee/sample2"""

        response = OrchestrationResponse(
            chatId=chat_id,
            llmServiceActive=True,
            questionOutOfLLMScope=False,
            inputGuardFailed=False,
            content=hardcoded_content,
        )

        logger.info("Response generated successfully")
        return response

    def flush_langfuse_traces(self) -> None:
        """
        Manually flush all pending Langfuse traces.
        This is useful for ensuring traces are sent before service shutdown.
        """
        if self.langfuse_client:
            try:
                self.langfuse_client.flush()
                logger.info("Langfuse traces flushed successfully")
            except Exception as e:
                logger.error(f"Failed to flush Langfuse traces: {e}")

    def get_tracing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tracing operations.

        Returns:
            Dictionary containing tracing statistics
        """
        return {
            "langfuse_enabled": self.langfuse_client is not None,
            "langfuse_host": os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            "tracing_active": True,
            "langfuse_configured": bool(
                os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY")
            ),
            "dspy_thread_safe": True,
        }

    @observe(name="cost_estimation")
    def estimate_operation_cost(
        self, 
        input_text: str, 
        output_text: str, 
        model: str = "gpt-4o"
    ) -> Dict[str, Any]:
        """
        Estimate the cost of an LLM operation.
        
        Args:
            input_text: Input text
            output_text: Output text
            model: Model name
            
        Returns:
            Dictionary with cost estimation
        """
        # Simple token estimation (4 chars ≈ 1 token)
        input_tokens = len(input_text) // 4
        output_tokens = len(output_text) // 4
        total_tokens = input_tokens + output_tokens
        
        # Updated pricing per 1K tokens (as of 2024)
        pricing = {
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
            "claude-3-sonnet": {"input": 0.003, "output": 0.015},
            "claude-3-opus": {"input": 0.015, "output": 0.075},
        }
        
        model_pricing = pricing.get(model, pricing["gpt-4o"])
        input_cost = (input_tokens / 1000) * model_pricing["input"]
        output_cost = (output_tokens / 1000) * model_pricing["output"]
        total_cost = input_cost + output_cost
        
        cost_info = {
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_cost_usd": round(input_cost, 8),
            "output_cost_usd": round(output_cost, 8),
            "total_cost_usd": round(total_cost, 8),
            "pricing_date": "2024-09-26"
        }
        
        logger.info(f"Estimated cost for {model}: ${total_cost:.6f}")
        return cost_info

    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of the service."""
        try:
            health_info = {
                "service_status": "healthy",
                "llm_manager_initialized": self.llm_manager is not None,
                "langfuse_enabled": self.langfuse_client is not None,
                "dspy_context_management": "thread_safe",
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if self.llm_manager:
                try:
                    providers = self.llm_manager.get_available_providers()
                    health_info["available_providers"] = [p.value for p in providers.keys()]
                    health_info["provider_count"] = len(providers)
                except Exception as e:
                    health_info["provider_error"] = str(e)
            
            return health_info
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service_status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }