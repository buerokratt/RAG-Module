"""LLM Orchestration Service - Business logic for LLM orchestration."""

from typing import Optional, List, Dict, Union, Any
import json
import asyncio
import os
from loguru import logger
from langfuse import Langfuse, observe

from llm_orchestrator_config.llm_manager import LLMManager
from models.request_models import (
    OrchestrationRequest,
    OrchestrationResponse,
    ConversationItem,
    PromptRefinerOutput,
    ContextGenerationRequest,
    TestOrchestrationResponse,
)
from prompt_refine_manager.prompt_refiner import PromptRefinerAgent
from src.response_generator.response_generate import ResponseGeneratorAgent
from src.llm_orchestrator_config.llm_cochestrator_constants import (
    OUT_OF_SCOPE_MESSAGE,
    TECHNICAL_ISSUE_MESSAGE,
    INPUT_GUARDRAIL_VIOLATION_MESSAGE,
    OUTPUT_GUARDRAIL_VIOLATION_MESSAGE,
)
from src.utils.cost_utils import calculate_total_costs
from src.guardrails import NeMoRailsAdapter, GuardrailCheckResult
from src.contextual_retrieval import ContextualRetriever


class LangfuseConfig:
    """Configuration for Langfuse integration."""

    def __init__(self):
        self.langfuse_client: Optional[Langfuse] = None
        self._initialize_langfuse()

    def _initialize_langfuse(self):
        """Initialize Langfuse client with Vault secrets."""
        try:
            from llm_orchestrator_config.vault.vault_client import VaultAgentClient

            vault = VaultAgentClient()
            if vault.is_vault_available():
                langfuse_secrets = vault.get_secret("langfuse/config")
                if langfuse_secrets:
                    self.langfuse_client = Langfuse(
                        public_key=langfuse_secrets.get("public_key"),
                        secret_key=langfuse_secrets.get("secret_key"),
                        host=langfuse_secrets.get("host", "http://langfuse-web:3000"),
                    )
                    logger.info("Langfuse client initialized successfully")
                else:
                    logger.warning("Langfuse secrets not found in Vault")
            else:
                logger.warning("Vault not available, Langfuse tracing disabled")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")


class LLMOrchestrationService:
    """
    Service class for handling LLM orchestration with integrated guardrails.
    Features:
    - Input guardrails before prompt refinement
    - Output guardrails after response generation
    - Comprehensive cost tracking for all components
    """

    def __init__(self) -> None:
        """Initialize the orchestration service."""
        self.langfuse_config = LangfuseConfig()

    @observe(name="orchestration_request", as_type="agent")
    def process_orchestration_request(
        self, request: OrchestrationRequest
    ) -> Union[OrchestrationResponse, TestOrchestrationResponse]:
        """
        Process an orchestration request with guardrails and return response.

        Pipeline:
        1. Input Guardrails Check
        2. Prompt Refinement (if input allowed)
        3. Chunk Retrieval
        4. Response Generation
        5. Output Guardrails Check
        6. Cost Logging

        Args:
            request: The orchestration request containing user message and context

        Returns:
            OrchestrationResponse: Response with LLM output and status flags

        Raises:
            Exception: For any processing errors
        """
        costs_dict: Dict[str, Dict[str, Any]] = {}

        try:
            logger.info(
                f"Processing orchestration request for chatId: {request.chatId}, "
                f"authorId: {request.authorId}, environment: {request.environment}"
            )

            # Initialize all service components
            components = self._initialize_service_components(request)

            # Execute the orchestration pipeline
            response = self._execute_orchestration_pipeline(
                request, components, costs_dict
            )

            # Log final costs and return response
            self._log_costs(costs_dict)
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                total_costs = calculate_total_costs(costs_dict)

                total_input_tokens = sum(
                    c.get("total_prompt_tokens", 0) for c in costs_dict.values()
                )
                total_output_tokens = sum(
                    c.get("total_completion_tokens", 0) for c in costs_dict.values()
                )

                langfuse.update_current_generation(
                    model=components["llm_manager"]
                    .get_provider_info()
                    .get("model", "unknown"),
                    usage_details={
                        "input": total_input_tokens,
                        "output": total_output_tokens,
                        "total": total_costs.get("total_tokens", 0),
                    },
                    cost_details={
                        "total": total_costs.get("total_cost", 0.0),
                    },
                    metadata={
                        "total_calls": total_costs.get("total_calls", 0),
                        "cost_breakdown": costs_dict,
                        "chat_id": request.chatId,
                        "author_id": request.authorId,
                        "environment": request.environment,
                    },
                )
                langfuse.flush()
            return response

        except Exception as e:
            logger.error(
                f"Error processing orchestration request for chatId: {request.chatId}, "
                f"error: {str(e)}"
            )
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "response_type": "technical_issue",
                    }
                )
                langfuse.flush()
            self._log_costs(costs_dict)
            return self._create_error_response(request)

    @observe(name="initialize_service_components", as_type="span")
    def _initialize_service_components(
        self, request: OrchestrationRequest
    ) -> Dict[str, Any]:
        """Initialize all service components and return them as a dictionary."""
        components: Dict[str, Any] = {}

        # Initialize LLM Manager
        components["llm_manager"] = self._initialize_llm_manager(
            environment=request.environment, connection_id=request.connection_id
        )

        # Initialize Guardrails Adapter (optional)
        components["guardrails_adapter"] = self._safe_initialize_guardrails(
            request.environment, request.connection_id
        )

        # Initialize Contextual Retriever (replaces hybrid retriever)
        components["contextual_retriever"] = self._safe_initialize_contextual_retriever(
            request.environment, request.connection_id
        )

        # Initialize Response Generator
        components["response_generator"] = self._safe_initialize_response_generator(
            components["llm_manager"]
        )

        # Log optimization status for all components
        self._log_optimization_status(components)

        return components

    def _log_optimization_status(self, components: Dict[str, Any]) -> None:
        """Log optimization status for all initialized components."""
        try:
            logger.info("=== OPTIMIZATION STATUS ===")

            self._log_guardrails_status(components)
            self._log_refiner_status(components)
            self._log_generator_status(components)

            logger.info("=== END OPTIMIZATION STATUS ===")

        except Exception as e:
            logger.warning(f"Failed to log optimization status: {str(e)}")

    def _log_guardrails_status(self, components: Dict[str, Any]) -> None:
        """Log guardrails optimization status."""
        if not components.get("guardrails_adapter"):
            logger.info(" Guardrails: Not initialized")
            return

        try:
            from src.guardrails.optimized_guardrails_loader import get_guardrails_loader

            guardrails_loader = get_guardrails_loader()
            _, metadata = guardrails_loader.get_optimized_config_path()

            if metadata.get("optimized", False):
                logger.info(
                    f"✓ Guardrails: OPTIMIZED (version: {metadata.get('version', 'unknown')})"
                )
                metrics = metadata.get("metrics", {})
                if metrics:
                    logger.info(
                        f"  Metrics: weighted_accuracy={metrics.get('weighted_accuracy', 'N/A')}"
                    )
            else:
                logger.info(" Guardrails: BASE (no optimization)")
        except Exception as e:
            logger.warning(f" Guardrails: Status check failed - {str(e)}")

    def _log_refiner_status(self, components: Dict[str, Any]) -> None:
        """Log refiner optimization status."""
        if not hasattr(components.get("llm_manager"), "__class__"):
            logger.info("⚠ Refiner: LLM Manager not available")
            return

        try:
            from src.prompt_refine_manager.prompt_refiner import PromptRefinerAgent

            test_refiner = PromptRefinerAgent(llm_manager=components["llm_manager"])
            refiner_info = test_refiner.get_module_info()

            if refiner_info.get("optimized", False):
                logger.info(
                    f"✓ Refiner: OPTIMIZED (version: {refiner_info.get('version', 'unknown')})"
                )
                metrics = refiner_info.get("metrics", {})
                if metrics:
                    logger.info(
                        f"  Metrics: avg_quality={metrics.get('average_quality', 'N/A')}"
                    )
            else:
                logger.info("⚠ Refiner: BASE (no optimization)")
        except Exception as e:
            logger.warning(f"⚠ Refiner: Status check failed - {str(e)}")

    def _log_generator_status(self, components: Dict[str, Any]) -> None:
        """Log generator optimization status."""
        if not components.get("response_generator"):
            logger.info(" Generator: Not initialized")
            return

        try:
            generator_info = components["response_generator"].get_module_info()

            if generator_info.get("optimized", False):
                logger.info(
                    f"✓ Generator: OPTIMIZED (version: {generator_info.get('version', 'unknown')})"
                )
                metrics = generator_info.get("metrics", {})
                if metrics:
                    logger.info(
                        f"  Metrics: avg_quality={metrics.get('average_quality', 'N/A')}"
                    )
            else:
                logger.info(" Generator: BASE (no optimization)")
        except Exception as e:
            logger.warning(f" Generator: Status check failed - {str(e)}")

    @observe(name="execute_orchestration_pipeline", as_type="span")
    def _execute_orchestration_pipeline(
        self,
        request: OrchestrationRequest,
        components: Dict[str, Any],
        costs_dict: Dict[str, Dict[str, Any]],
    ) -> OrchestrationResponse:
        """Execute the main orchestration pipeline with all components."""
        # Step 1: Input Guardrails Check
        if components["guardrails_adapter"]:
            input_blocked_response = self.handle_input_guardrails(
                components["guardrails_adapter"], request, costs_dict
            )
            if input_blocked_response:
                return input_blocked_response

        # Step 2: Refine user prompt
        refined_output, refiner_usage = self._refine_user_prompt(
            llm_manager=components["llm_manager"],
            original_message=request.message,
            conversation_history=request.conversationHistory,
        )
        costs_dict["prompt_refiner"] = refiner_usage

        # Step 3: Retrieve relevant chunks using contextual retrieval
        relevant_chunks = self._safe_retrieve_contextual_chunks(
            components["contextual_retriever"], refined_output, request
        )
        if relevant_chunks is None:  # Retrieval failed
            return self._create_out_of_scope_response(request)

        # Handle zero chunks scenario - return out-of-scope response
        if len(relevant_chunks) == 0:
            logger.info("No relevant chunks found - returning out-of-scope response")
            return self._create_out_of_scope_response(request)

        # Step 4: Generate response
        generated_response = self._generate_rag_response(
            llm_manager=components["llm_manager"],
            request=request,
            refined_output=refined_output,
            relevant_chunks=relevant_chunks,
            response_generator=components["response_generator"],
            costs_dict=costs_dict,
        )

        # Step 5: Output Guardrails Check
        return self.handle_output_guardrails(
            components["guardrails_adapter"], generated_response, request, costs_dict
        )

    @observe(name="safe_initialize_guardrails", as_type="span")
    def _safe_initialize_guardrails(
        self, environment: str, connection_id: Optional[str]
    ) -> Optional[NeMoRailsAdapter]:
        """Safely initialize guardrails adapter with error handling."""
        try:
            adapter = self._initialize_guardrails(environment, connection_id)
            logger.info("Guardrails adapter initialization successful")
            return adapter
        except Exception as guardrails_error:
            logger.warning(f"Guardrails initialization failed: {str(guardrails_error)}")
            logger.warning("Continuing without guardrails protection")
            return None

    @observe(name="safe_initialize_contextual_retriever", as_type="span")
    def _safe_initialize_contextual_retriever(
        self, environment: str, connection_id: Optional[str]
    ) -> Optional[ContextualRetriever]:
        """Safely initialize contextual retriever with error handling."""
        try:
            retriever = self._initialize_contextual_retriever(
                environment, connection_id
            )
            logger.info("Contextual Retriever initialization successful")
            return retriever
        except Exception as retriever_error:
            logger.warning(
                f"Contextual Retriever initialization failed: {str(retriever_error)}"
            )
            logger.warning("Continuing without chunk retrieval capabilities")
            return None

    @observe(name="safe_initialize_response_generator", as_type="span")
    def _safe_initialize_response_generator(
        self, llm_manager: LLMManager
    ) -> Optional[ResponseGeneratorAgent]:
        """Safely initialize response generator with error handling."""
        try:
            generator = self._initialize_response_generator(llm_manager)
            logger.info("Response Generator initialization successful")
            return generator
        except Exception as generator_error:
            logger.warning(
                f"Response Generator initialization failed: {str(generator_error)}"
            )
            return None

    def handle_input_guardrails(
        self,
        guardrails_adapter: NeMoRailsAdapter,
        request: OrchestrationRequest,
        costs_dict: Dict[str, Dict[str, Any]],
    ) -> Union[OrchestrationResponse, TestOrchestrationResponse, None]:
        """Check input guardrails and return blocked response if needed."""
        input_check_result = self._check_input_guardrails(
            guardrails_adapter=guardrails_adapter,
            user_message=request.message,
            costs_dict=costs_dict,
        )

        if not input_check_result.allowed:
            logger.warning(f"Input blocked by guardrails: {input_check_result.reason}")
            if request.environment == "test":
                logger.info(
                    "Test environment detected – returning input guardrail violation message."
                )
                return TestOrchestrationResponse(
                    llmServiceActive=True,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=True,
                    content=INPUT_GUARDRAIL_VIOLATION_MESSAGE,
                )
            else:
                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=True,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=True,
                    content=INPUT_GUARDRAIL_VIOLATION_MESSAGE,
                )

        logger.info("Input guardrails check passed")
        return None

    def _safe_retrieve_contextual_chunks(
        self,
        contextual_retriever: Optional[ContextualRetriever],
        refined_output: PromptRefinerOutput,
        request: OrchestrationRequest,
    ) -> Optional[List[Dict[str, Union[str, float, Dict[str, Any]]]]]:
        """Safely retrieve chunks using contextual retrieval with error handling."""
        if not contextual_retriever:
            logger.info("Contextual Retriever not available, skipping chunk retrieval")
            return []

        try:
            # Define async wrapper for initialization and retrieval
            async def async_retrieve():
                # Ensure retriever is initialized
                if not contextual_retriever.initialized:
                    initialization_success = await contextual_retriever.initialize()
                    if not initialization_success:
                        logger.warning("Failed to initialize contextual retriever")
                        return None

                relevant_chunks = await contextual_retriever.retrieve_contextual_chunks(
                    original_question=refined_output.original_question,
                    refined_questions=refined_output.refined_questions,
                    environment=request.environment,
                    connection_id=request.connection_id,
                )
                return relevant_chunks

            # Run async retrieval synchronously
            relevant_chunks = asyncio.run(async_retrieve())

            if relevant_chunks is None:
                return None

            logger.info(
                f"Successfully retrieved {len(relevant_chunks)} contextual chunks"
            )
            return relevant_chunks
        except Exception as retrieval_error:
            logger.warning(f"Contextual chunk retrieval failed: {str(retrieval_error)}")
            logger.warning("Returning out-of-scope message due to retrieval failure")
            return None

    def handle_output_guardrails(
        self,
        guardrails_adapter: Optional[NeMoRailsAdapter],
        generated_response: OrchestrationResponse,
        request: OrchestrationRequest,
        costs_dict: Dict[str, Dict[str, Any]],
    ) -> OrchestrationResponse:
        """Check output guardrails and handle blocked responses."""
        if (
            guardrails_adapter is not None
            and generated_response.llmServiceActive
            and not generated_response.questionOutOfLLMScope
        ):
            output_check_result = self._check_output_guardrails(
                guardrails_adapter=guardrails_adapter,
                assistant_message=generated_response.content,
                costs_dict=costs_dict,
            )

            if not output_check_result.allowed:
                logger.warning(
                    f"Output blocked by guardrails: {output_check_result.reason}"
                )
                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=True,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=OUTPUT_GUARDRAIL_VIOLATION_MESSAGE,
                )

            logger.info("Output guardrails check passed")
        else:
            logger.info("Skipping output guardrails check")

        logger.info(f"Successfully generated RAG response for chatId: {request.chatId}")
        return generated_response

    def _create_error_response(
        self, request: OrchestrationRequest
    ) -> OrchestrationResponse:
        """Create standardized error response."""
        return OrchestrationResponse(
            chatId=request.chatId,
            llmServiceActive=False,
            questionOutOfLLMScope=False,
            inputGuardFailed=False,
            content=TECHNICAL_ISSUE_MESSAGE,
        )

    def _create_out_of_scope_response(
        self, request: OrchestrationRequest
    ) -> OrchestrationResponse:
        """Create standardized out-of-scope response."""
        return OrchestrationResponse(
            chatId=request.chatId,
            llmServiceActive=True,
            questionOutOfLLMScope=True,
            inputGuardFailed=False,
            content=OUT_OF_SCOPE_MESSAGE,
        )

    @observe(name="initialize_guardrails", as_type="span")
    def _initialize_guardrails(
        self, environment: str, connection_id: Optional[str]
    ) -> NeMoRailsAdapter:
        """
        Initialize NeMo Guardrails adapter.

        Args:
            environment: Environment context (production/test/development)
            connection_id: Optional connection identifier

        Returns:
            NeMoRailsAdapter: Initialized guardrails adapter instance

        Raises:
            Exception: For initialization errors
        """
        try:
            logger.info(f"Initializing Guardrails for environment: {environment}")

            guardrails_adapter = NeMoRailsAdapter(
                environment=environment, connection_id=connection_id
            )

            logger.info("Guardrails adapter initialized successfully")
            return guardrails_adapter

        except Exception as e:
            logger.error(f"Failed to initialize Guardrails adapter: {str(e)}")
            raise

    @observe(name="check_input_guardrails", as_type="span")
    def _check_input_guardrails(
        self,
        guardrails_adapter: NeMoRailsAdapter,
        user_message: str,
        costs_dict: Dict[str, Dict[str, Any]],
    ) -> GuardrailCheckResult:
        """
        Check user input against guardrails and track costs.

        Args:
            guardrails_adapter: The guardrails adapter instance
            user_message: The user message to check
            costs_dict: Dictionary to store cost information

        Returns:
            GuardrailCheckResult: Result of the guardrail check
        """
        logger.info("Starting input guardrails check")

        try:
            result = guardrails_adapter.check_input(user_message)

            # Store guardrail costs
            costs_dict["input_guardrails"] = result.usage
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    input=user_message,
                    metadata={
                        "guardrail_type": "input",
                        "allowed": result.allowed,
                        "verdict": result.verdict,
                        "blocked_reason": result.reason if not result.allowed else None,
                        "error": result.error if result.error else None,
                    },
                    usage_details={
                        "input": result.usage.get("total_prompt_tokens", 0),
                        "output": result.usage.get("total_completion_tokens", 0),
                        "total": result.usage.get("total_tokens", 0),
                    },  # type: ignore
                    cost_details={
                        "total": result.usage.get("total_cost", 0.0),
                    },
                )
            logger.info(
                f"Input guardrails check completed: allowed={result.allowed}, "
                f"cost=${result.usage.get('total_cost', 0):.6f}"
            )

            return result

        except Exception as e:
            logger.error(f"Input guardrails check failed: {str(e)}")
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "guardrail_type": "input",
                    }
                )
            # Return conservative result on error
            return GuardrailCheckResult(
                allowed=False,
                verdict="yes",
                content="Error during input guardrail check",
                error=str(e),
                usage={},
            )

    @observe(name="check_output_guardrails", as_type="span")
    def _check_output_guardrails(
        self,
        guardrails_adapter: NeMoRailsAdapter,
        assistant_message: str,
        costs_dict: Dict[str, Dict[str, Any]],
    ) -> GuardrailCheckResult:
        """
        Check assistant output against guardrails and track costs.

        Args:
            guardrails_adapter: The guardrails adapter instance
            assistant_message: The assistant message to check
            costs_dict: Dictionary to store cost information

        Returns:
            GuardrailCheckResult: Result of the guardrail check
        """
        logger.info("Starting output guardrails check")

        try:
            result = guardrails_adapter.check_output(assistant_message)

            # Store guardrail costs
            costs_dict["output_guardrails"] = result.usage
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    input=assistant_message[:500],  # Truncate for readability
                    output=result.verdict,
                    metadata={
                        "guardrail_type": "output",
                        "allowed": result.allowed,
                        "verdict": result.verdict,
                        "reason": result.reason if not result.allowed else None,
                        "error": result.error if result.error else None,
                        "response_length": len(assistant_message),
                    },
                    usage_details={
                        "input": result.usage.get("total_prompt_tokens", 0),
                        "output": result.usage.get("total_completion_tokens", 0),
                        "total": result.usage.get("total_tokens", 0),
                    },  # type: ignore
                    cost_details={
                        "total": result.usage.get("total_cost", 0.0),
                    },
                )
            logger.info(
                f"Output guardrails check completed: allowed={result.allowed}, "
                f"cost=${result.usage.get('total_cost', 0):.6f}"
            )

            return result

        except Exception as e:
            logger.error(f"Output guardrails check failed: {str(e)}")
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "guardrail_type": "output",
                    }
                )
            # Return conservative result on error
            return GuardrailCheckResult(
                allowed=False,
                verdict="yes",
                content="Error during output guardrail check",
                error=str(e),
                usage={},
            )

    def _log_costs(self, costs_dict: Dict[str, Dict[str, Any]]) -> None:
        """
        Log cost information for tracking.

        Args:
            costs_dict: Dictionary of costs per component
        """
        try:
            if not costs_dict:
                return

            total_costs = calculate_total_costs(costs_dict)

            logger.info("LLM USAGE COSTS BREAKDOWN:")

            for component, costs in costs_dict.items():
                logger.info(
                    f"  {component:20s}: ${costs.get('total_cost', 0):.6f} "
                    f"({costs.get('num_calls', 0)} calls, "
                    f"{costs.get('total_tokens', 0)} tokens)"
                )

            logger.info(
                f"  {'TOTAL':20s}: ${total_costs['total_cost']:.6f} "
                f"({total_costs['total_calls']} calls, "
                f"{total_costs['total_tokens']} tokens)"
            )

            # Log module versions being used
            logger.info("\nMODULE VERSIONS IN USE:")
            try:
                from src.optimization.optimized_module_loader import get_module_loader
                from src.guardrails.optimized_guardrails_loader import (
                    get_guardrails_loader,
                )

                loader = get_module_loader()
                guardrails_loader = get_guardrails_loader()

                # Log refiner version
                _, refiner_meta = loader.load_refiner_module()
                logger.info(
                    f"  Refiner: {refiner_meta.get('version', 'unknown')} "
                    f"({'optimized' if refiner_meta.get('optimized') else 'base'})"
                )

                # Log generator version
                _, generator_meta = loader.load_generator_module()
                logger.info(
                    f"  Generator: {generator_meta.get('version', 'unknown')} "
                    f"({'optimized' if generator_meta.get('optimized') else 'base'})"
                )

                # Log guardrails version
                _, guardrails_meta = guardrails_loader.get_optimized_config_path()
                logger.info(
                    f"  Guardrails: {guardrails_meta.get('version', 'unknown')} "
                    f"({'optimized' if guardrails_meta.get('optimized') else 'base'})"
                )

            except Exception as version_error:
                logger.debug(f"Could not log module versions: {str(version_error)}")

        except Exception as e:
            logger.warning(f"Failed to log costs: {str(e)}")

    @observe(name="initialize_llm_manager", as_type="span")
    def _initialize_llm_manager(
        self, environment: str, connection_id: Optional[str]
    ) -> LLMManager:
        """
        Initialize LLM Manager with proper configuration.

        Args:
            environment: Environment context (production/test/development)
            connection_id: Optional connection identifier

        Returns:
            LLMManager: Initialized LLM manager instance
        """
        try:
            logger.info(f"Initializing LLM Manager for environment: {environment}")

            llm_manager = LLMManager(
                environment=environment, connection_id=connection_id
            )

            llm_manager.ensure_global_config()

            logger.info("LLM Manager initialized successfully")
            return llm_manager

        except Exception as e:
            logger.error(f"Failed to initialize LLM Manager: {str(e)}")
            raise

    @observe(name="refine_user_prompt", as_type="chain")
    def _refine_user_prompt(
        self,
        llm_manager: LLMManager,
        original_message: str,
        conversation_history: List[ConversationItem],
    ) -> tuple[PromptRefinerOutput, Dict[str, Any]]:
        """
        Refine user prompt using loaded LLM configuration and return usage info.

        Args:
            llm_manager: The LLM manager instance to use
            original_message: The original user message to refine
            conversation_history: Previous conversation context

        Returns:
            Tuple of (PromptRefinerOutput, usage_dict): The refined prompt output and usage info

        Raises:
            ValueError: When LLM Manager is not initialized
            ValidationError: When prompt refinement output validation fails
            Exception: For other prompt refinement failures
        """
        logger.info("Starting prompt refinement process")

        try:
            # Convert conversation history to DSPy format
            history: List[Dict[str, str]] = []
            for item in conversation_history:
                role = "assistant" if item.authorRole == "bot" else item.authorRole
                history.append({"role": role, "content": item.message})

            # Create prompt refiner using the same LLM manager instance
            refiner = PromptRefinerAgent(llm_manager=llm_manager)

            # Generate structured prompt refinement output with usage tracking
            refinement_result = refiner.forward_structured(
                history=history, question=original_message
            )

            # Extract usage information
            usage_info = refinement_result.get(
                "usage",
                {
                    "total_cost": 0.0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "total_tokens": 0,
                    "num_calls": 0,
                },
            )

            # Validate the output schema using Pydantic
            try:
                validated_output = PromptRefinerOutput(
                    original_question=refinement_result["original_question"],
                    refined_questions=refinement_result["refined_questions"],
                )
            except Exception as validation_error:
                logger.error(
                    f"Prompt refinement output validation failed: {str(validation_error)}"
                )
                logger.error(f"Invalid refinement result: {refinement_result}")
                raise ValueError(
                    f"Prompt refinement validation failed: {str(validation_error)}"
                ) from validation_error
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                refinement_applied = (
                    original_message.strip()
                    != validated_output.original_question.strip()
                )
                langfuse.update_current_generation(
                    model=llm_manager.get_provider_info().get("model", "unknown"),
                    input=original_message,
                    usage_details={
                        "input": usage_info.get("total_prompt_tokens", 0),
                        "output": usage_info.get("total_completion_tokens", 0),
                        "total": usage_info.get("total_tokens", 0),
                    },
                    cost_details={
                        "total": usage_info.get("total_cost", 0.0),
                    },
                    metadata={
                        "num_calls": usage_info.get("num_calls", 0),
                        "num_refined_questions": len(
                            validated_output.refined_questions
                        ),
                        "refinement_applied": refinement_applied,
                        "conversation_history_length": len(history),
                    },  # type: ignore
                )
            output_json = validated_output.model_dump()
            logger.info(
                f"Prompt refinement output: {json.dumps(output_json, indent=2)}"
            )

            logger.info("Prompt refinement completed successfully")
            return validated_output, usage_info

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Prompt refinement failed: {str(e)}")
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "refinement_failed": True,
                    }
                )
            logger.error(f"Failed to refine message: {original_message}")
            raise RuntimeError(f"Prompt refinement process failed: {str(e)}") from e

    @observe(name="initialize_contextual_retriever", as_type="span")
    def _initialize_contextual_retriever(
        self, environment: str, connection_id: Optional[str]
    ) -> ContextualRetriever:
        """
        Initialize contextual retriever for enhanced document retrieval.

        Args:
            environment: Environment for model resolution
            connection_id: Optional connection ID

        Returns:
            ContextualRetriever: Initialized contextual retriever instance
        """
        logger.info("Initializing contextual retriever")

        try:
            # Initialize with Qdrant URL - use environment variable or default
            qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")

            contextual_retriever = ContextualRetriever(
                qdrant_url=qdrant_url,
                environment=environment,
                connection_id=connection_id,
                llm_service=self,  # Inject self to eliminate circular dependency
            )

            logger.info("Contextual retriever initialized successfully")
            return contextual_retriever

        except Exception as e:
            logger.error(f"Failed to initialize contextual retriever: {str(e)}")
            raise

    @observe(name="initialize_response_generator", as_type="span")
    def _initialize_response_generator(
        self, llm_manager: LLMManager
    ) -> ResponseGeneratorAgent:
        """
        Initialize Response Generator with the provided LLM manager.

        Args:
            llm_manager: The LLM manager instance to use for response generation

        Returns:
            ResponseGeneratorAgent: Initialized response generator instance
        """
        logger.info("Initializing response generator")

        try:
            # Set up DSPy configuration for the response generator
            with llm_manager.use_task_local():
                response_generator = ResponseGeneratorAgent()

            logger.info("Response generator initialized successfully")
            return response_generator

        except Exception as e:
            logger.error(f"Failed to initialize response generator: {str(e)}")
            raise

    @observe(name="generate_rag_response", as_type="generation")
    def _generate_rag_response(
        self,
        llm_manager: LLMManager,
        request: OrchestrationRequest,
        refined_output: PromptRefinerOutput,
        relevant_chunks: List[Dict[str, Union[str, float, Dict[str, Any]]]],
        response_generator: Optional[ResponseGeneratorAgent] = None,
        costs_dict: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Union[OrchestrationResponse, TestOrchestrationResponse]:
        """
        Generate response using retrieved chunks and ResponseGeneratorAgent only.
        No secondary LLM paths; no citations appended.
        """
        logger.info("Starting RAG response generation")

        if costs_dict is None:
            costs_dict = {}

        # If response generator is not available -> standardized technical issue
        if response_generator is None:
            logger.warning(
                "Response generator unavailable – returning technical issue message."
            )
            if request.environment == "test":
                logger.info(
                    "Test environment detected – returning technical issue message."
                )
                return TestOrchestrationResponse(
                    llmServiceActive=False,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=TECHNICAL_ISSUE_MESSAGE,
                )
            else:
                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=False,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=TECHNICAL_ISSUE_MESSAGE,
                )

        try:
            with llm_manager.use_task_local():
                generator_result = response_generator.forward(
                    question=refined_output.original_question,
                    chunks=relevant_chunks or [],
                    max_blocks=10,
                )

            answer = (generator_result.get("answer") or "").strip()
            question_out_of_scope = bool(
                generator_result.get("questionOutOfLLMScope", False)
            )

            # Extract and store response generator costs
            generator_usage = generator_result.get(
                "usage",
                {
                    "total_cost": 0.0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "total_tokens": 0,
                    "num_calls": 0,
                },
            )
            costs_dict["response_generator"] = generator_usage
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    model=llm_manager.get_provider_info().get("model", "unknown"),
                    usage_details={
                        "input": generator_usage.get("total_prompt_tokens", 0),
                        "output": generator_usage.get("total_completion_tokens", 0),
                        "total": generator_usage.get("total_tokens", 0),
                    },
                    cost_details={
                        "total": generator_usage.get("total_cost", 0.0),
                    },
                    metadata={
                        "num_calls": generator_usage.get("num_calls", 0),
                        "question_out_of_scope": question_out_of_scope,
                        "num_chunks_used": len(relevant_chunks)
                        if relevant_chunks
                        else 0,
                    },
                    output=answer,
                )
            if question_out_of_scope:
                logger.info("Question determined out-of-scope – sending fixed message.")
                if request.environment == "test":
                    logger.info(
                        "Test environment detected – returning out-of-scope message."
                    )
                    return TestOrchestrationResponse(
                        llmServiceActive=True,  # service OK; insufficient context
                        questionOutOfLLMScope=True,
                        inputGuardFailed=False,
                        content=OUT_OF_SCOPE_MESSAGE,
                    )
                else:
                    return OrchestrationResponse(
                        chatId=request.chatId,
                        llmServiceActive=True,  # service OK; insufficient context
                        questionOutOfLLMScope=True,
                        inputGuardFailed=False,
                        content=OUT_OF_SCOPE_MESSAGE,
                    )

            # In-scope: return the answer as-is (NO citations)
            logger.info("Returning in-scope answer without citations.")
            if request.environment == "test":
                logger.info("Test environment detected – returning generated answer.")
                return TestOrchestrationResponse(
                    llmServiceActive=True,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=answer,
                )
            else:
                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=True,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=answer,
                )

        except Exception as e:
            logger.error(f"RAG Response generation failed: {str(e)}")
            if self.langfuse_config.langfuse_client:
                langfuse = self.langfuse_config.langfuse_client
                langfuse.update_current_generation(
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "response_type": "technical_issue",
                        "refinement_failed": False,
                    }
                )
            # Standardized technical issue; no second LLM call, no citations
            if request.environment == "test":
                logger.info(
                    "Test environment detected – returning technical issue message."
                )
                return TestOrchestrationResponse(
                    llmServiceActive=False,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=TECHNICAL_ISSUE_MESSAGE,
                )
            else:
                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=False,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=TECHNICAL_ISSUE_MESSAGE,
                )

    # ========================================================================
    # Vector Indexer Support Methods (Isolated from RAG Pipeline)
    # ========================================================================
    @observe(name="create_embeddings_for_indexer", as_type="span")
    def create_embeddings_for_indexer(
        self,
        texts: List[str],
        environment: str = "production",
        connection_id: Optional[str] = None,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """Create embeddings for vector indexer using vault-driven model resolution.

        This method is completely isolated from the RAG pipeline and uses lazy
        initialization to avoid interfering with the main orchestration flow.

        Args:
            texts: List of texts to embed
            environment: Environment (production, development, test)
            connection_id: Optional connection ID for dev/test environments
            batch_size: Batch size for processing

        Returns:
            Dictionary with embeddings and metadata
        """
        logger.info(
            f"Creating embeddings for vector indexer: {len(texts)} texts in {environment} environment"
        )

        try:
            # Lazy initialization of embedding manager
            embedding_manager = self._get_embedding_manager()

            return embedding_manager.create_embeddings(
                texts=texts,
                environment=environment,
                connection_id=connection_id,
                batch_size=batch_size,
            )
        except Exception as e:
            logger.error(f"Vector indexer embedding creation failed: {e}")
            raise

    def generate_context_for_chunks(
        self, request: ContextGenerationRequest
    ) -> Dict[str, Any]:
        """Generate context for chunks using Anthropic methodology.

        This method is completely isolated from the RAG pipeline and uses lazy
        initialization to avoid interfering with the main orchestration flow.

        Args:
            request: Context generation request with document and chunk prompts

        Returns:
            Dictionary with generated context and metadata
        """
        logger.info("Generating context for chunks using Anthropic methodology")

        try:
            # Lazy initialization of context manager
            context_manager = self._get_context_manager()

            return context_manager.generate_context_with_caching(request)
        except Exception as e:
            logger.error(f"Vector indexer context generation failed: {e}")
            raise

    def get_available_embedding_models_for_indexer(
        self, environment: str = "production"
    ) -> Dict[str, Any]:
        """Get available embedding models for vector indexer.

        Args:
            environment: Environment (production, development, test)

        Returns:
            Dictionary with available models and default model info
        """
        try:
            # Lazy initialization of embedding manager
            embedding_manager = self._get_embedding_manager()
            config_loader = self._get_config_loader()

            available_models: List[str] = embedding_manager.get_available_models(
                environment
            )

            # Get default model by resolving what would be used
            try:
                provider_name, model_name = config_loader.resolve_embedding_model(
                    environment
                )
                default_model: str = f"{provider_name}/{model_name}"
            except Exception as e:
                logger.warning(f"Could not resolve default embedding model: {e}")
                default_model = "azure_openai/text-embedding-3-large"  # Fallback

            return {
                "available_models": available_models,
                "default_model": default_model,
                "environment": environment,
            }
        except Exception as e:
            logger.error(f"Failed to get embedding models for vector indexer: {e}")
            raise

    # ========================================================================
    # Lazy Initialization Helpers for Vector Indexer (Private Methods)
    # ========================================================================

    def _get_embedding_manager(self):
        """Lazy initialization of EmbeddingManager for vector indexer."""
        if not hasattr(self, "_embedding_manager"):
            from src.llm_orchestrator_config.embedding_manager import EmbeddingManager
            from src.llm_orchestrator_config.vault.vault_client import VaultAgentClient

            vault_client = VaultAgentClient()
            config_loader = self._get_config_loader()

            self._embedding_manager = EmbeddingManager(vault_client, config_loader)
            logger.debug("Lazy initialized EmbeddingManager for vector indexer")

        return self._embedding_manager

    def _get_context_manager(self):
        """Lazy initialization of ContextGenerationManager for vector indexer."""
        if not hasattr(self, "_context_manager"):
            from src.llm_orchestrator_config.context_manager import (
                ContextGenerationManager,
            )

            # Use existing LLM manager or create new one for context generation
            llm_manager = LLMManager()
            self._context_manager = ContextGenerationManager(llm_manager)
            logger.debug("Lazy initialized ContextGenerationManager for vector indexer")

        return self._context_manager

    def _get_config_loader(self):
        """Lazy initialization of ConfigurationLoader for vector indexer."""
        if not hasattr(self, "_config_loader"):
            from src.llm_orchestrator_config.config.loader import ConfigurationLoader

            self._config_loader = ConfigurationLoader()
            logger.debug("Lazy initialized ConfigurationLoader for vector indexer")

        return self._config_loader
