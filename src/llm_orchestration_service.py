"""LLM Orchestration Service - Business logic for LLM orchestration."""

from typing import Optional, List, Dict
import json
from loguru import logger

from llm_config_module.llm_manager import LLMManager
from models.request_models import (
    OrchestrationRequest,
    OrchestrationResponse,
    ConversationItem,
    PromptRefinerOutput,
)
from prompt_refiner_module.prompt_refiner import PromptRefinerAgent


class LLMOrchestrationService:
    """Service class for handling LLM orchestration business logic."""

    def __init__(self) -> None:
        """Initialize the orchestration service."""
        self.llm_manager: Optional[LLMManager] = None

    def process_orchestration_request(
        self, request: OrchestrationRequest
    ) -> OrchestrationResponse:
        """
        Process an orchestration request and return response.

        Args:
            request: The orchestration request containing user message and context

        Returns:
            OrchestrationResponse: Response with LLM output and status flags

        Raises:
            Exception: For any processing errors
        """
        try:
            logger.info(
                f"Processing orchestration request for chatId: {request.chatId}, "
                f"authorId: {request.authorId}, environment: {request.environment}"
            )

            # Initialize LLM Manager with configuration
            self._initialize_llm_manager(
                environment=request.environment, connection_id=request.connection_id
            )

            # Step 2: Refine user prompt using loaded configuration
            self._refine_user_prompt(
                original_message=request.message,
                conversation_history=request.conversationHistory,
            )

            # TODO: Implement actual LLM processing pipeline
            # 3. Chunk retriever
            # 4. Re-ranker
            # 5. Response Generator
            # 6. Output Validator

            # For now, return hardcoded response
            response = self._generate_hardcoded_response(request.chatId)

            logger.info(f"Successfully processed request for chatId: {request.chatId}")
            return response

        except Exception as e:
            logger.error(
                f"Error processing orchestration request for chatId: {request.chatId}, "
                f"error: {str(e)}"
            )
            # Return error response
            return OrchestrationResponse(
                chatId=request.chatId,
                llmServiceActive=False,
                questionOutOfLLMScope=False,
                inputGuardFailed=True,
                content="An error occurred while processing your request. Please try again later.",
            )

    def _initialize_llm_manager(
        self, environment: str, connection_id: Optional[str]
    ) -> None:
        """
        Initialize LLM Manager with proper configuration.

        Args:
            environment: Environment context (production/test/development)
            connection_id: Optional connection identifier
        """
        try:
            logger.info(f"Initializing LLM Manager for environment: {environment}")

            self.llm_manager = LLMManager(
                environment=environment, connection_id=connection_id
            )

            logger.info("LLM Manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize LLM Manager: {str(e)}")
            raise

    def _refine_user_prompt(
        self, original_message: str, conversation_history: List[ConversationItem]
    ) -> None:
        """
        Refine user prompt using loaded LLM configuration and log all variants.

        Args:
            original_message: The original user message to refine
            conversation_history: Previous conversation context

        Raises:
            ValueError: When LLM Manager is not initialized
            ValidationError: When prompt refinement output validation fails
            Exception: For other prompt refinement failures
        """
        logger.info("Starting prompt refinement process")

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
            refiner = PromptRefinerAgent(llm_manager=self.llm_manager)

            # Generate structured prompt refinement output
            refinement_result = refiner.forward_structured(
                history=history, question=original_message
            )

            # Validate the output schema using Pydantic - this will raise ValidationError if invalid
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
                f"Prompt refinement output: {json.dumps(output_json, indent=2)}"
            )

            logger.info("Prompt refinement completed successfully")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Prompt refinement failed: {str(e)}")
            logger.error(f"Failed to refine message: {original_message}")
            raise RuntimeError(f"Prompt refinement process failed: {str(e)}") from e

    def _generate_hardcoded_response(self, chat_id: str) -> OrchestrationResponse:
        """
        Generate hardcoded response for testing purposes.

        Args:
            chat_id: Chat session identifier

        Returns:
            OrchestrationResponse with hardcoded values
        """
        hardcoded_content = """This is a random answer payload.

with citations.

References
- https://gov.ee/sample1,
- https://gov.ee/sample2"""

        return OrchestrationResponse(
            chatId=chat_id,
            llmServiceActive=True,
            questionOutOfLLMScope=False,
            inputGuardFailed=False,
            content=hardcoded_content,
        )
