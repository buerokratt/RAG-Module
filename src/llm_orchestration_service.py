"""LLM Orchestration Service - Business logic for LLM orchestration."""

from typing import Optional, List, Dict, Union, Any
import json
from loguru import logger

from llm_orchestrator_config.llm_manager import LLMManager
from models.request_models import (
    OrchestrationRequest,
    OrchestrationResponse,
    ConversationItem,
    PromptRefinerOutput,
)
from prompt_refine_manager.prompt_refiner import PromptRefinerAgent
from vector_indexer.chunk_config import ChunkConfig
from vector_indexer.hybrid_retrieval import HybridRetriever
from src.response_generator.response_generate import ResponseGeneratorAgent
from src.llm_orchestrator_config.llm_cochestrator_constants import (
    OUT_OF_SCOPE_MESSAGE,
    TECHNICAL_ISSUE_MESSAGE,
    INPUT_GUARDRAIL_VIOLATION_MESSAGE,
    OUTPUT_GUARDRAIL_VIOLATION_MESSAGE,
)
from src.utils.cost_utils import calculate_total_costs
from src.guardrails import NeMoRailsAdapter, GuardrailCheckResult


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
        pass

    def process_orchestration_request(
        self, request: OrchestrationRequest
    ) -> OrchestrationResponse:
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
            return response

        except Exception as e:
            logger.error(
                f"Error processing orchestration request for chatId: {request.chatId}, "
                f"error: {str(e)}"
            )
            self._log_costs(costs_dict)
            return self._create_error_response(request)

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

        # Initialize Hybrid Retriever (optional)
        components["hybrid_retriever"] = self._safe_initialize_hybrid_retriever()

        # Initialize Response Generator (optional)
        components["response_generator"] = self._safe_initialize_response_generator(
            components["llm_manager"]
        )

        return components

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

        # Step 3: Retrieve relevant chunks
        relevant_chunks = self._safe_retrieve_chunks(
            components["hybrid_retriever"], refined_output
        )
        if relevant_chunks is None:  # Retrieval failed
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

    def _safe_initialize_hybrid_retriever(self) -> Optional[HybridRetriever]:
        """Safely initialize hybrid retriever with error handling."""
        try:
            retriever = self._initialize_hybrid_retriever()
            logger.info("Hybrid Retriever initialization successful")
            return retriever
        except Exception as retriever_error:
            logger.warning(
                f"Hybrid Retriever initialization failed: {str(retriever_error)}"
            )
            logger.warning("Continuing without chunk retrieval capabilities")
            return None

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
    ) -> Optional[OrchestrationResponse]:
        """Check input guardrails and return blocked response if needed."""
        input_check_result = self._check_input_guardrails(
            guardrails_adapter=guardrails_adapter,
            user_message=request.message,
            costs_dict=costs_dict,
        )

        if not input_check_result.allowed:
            logger.warning(f"Input blocked by guardrails: {input_check_result.reason}")
            return OrchestrationResponse(
                chatId=request.chatId,
                llmServiceActive=True,
                questionOutOfLLMScope=False,
                inputGuardFailed=True,
                content=INPUT_GUARDRAIL_VIOLATION_MESSAGE,
            )

        logger.info("Input guardrails check passed")
        return None

    def _safe_retrieve_chunks(
        self,
        hybrid_retriever: Optional[HybridRetriever],
        refined_output: PromptRefinerOutput,
    ) -> Optional[List[Dict[str, Union[str, float, Dict[str, Any]]]]]:
        """Safely retrieve chunks with error handling."""
        if not hybrid_retriever:
            logger.info("Hybrid Retriever not available, skipping chunk retrieval")
            return []

        try:
            relevant_chunks = self._retrieve_relevant_chunks(
                hybrid_retriever=hybrid_retriever, refined_output=refined_output
            )
            logger.info(f"Successfully retrieved {len(relevant_chunks)} chunks")
            return relevant_chunks
        except Exception as retrieval_error:
            logger.warning(f"Chunk retrieval failed: {str(retrieval_error)}")
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

            logger.info(
                f"Input guardrails check completed: allowed={result.allowed}, "
                f"cost=${result.usage.get('total_cost', 0):.6f}"
            )

            return result

        except Exception as e:
            logger.error(f"Input guardrails check failed: {str(e)}")
            # Return conservative result on error
            return GuardrailCheckResult(
                allowed=False,
                verdict="yes",
                content="Error during input guardrail check",
                error=str(e),
                usage={},
            )

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

            logger.info(
                f"Output guardrails check completed: allowed={result.allowed}, "
                f"cost=${result.usage.get('total_cost', 0):.6f}"
            )

            return result

        except Exception as e:
            logger.error(f"Output guardrails check failed: {str(e)}")
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

        except Exception as e:
            logger.warning(f"Failed to log costs: {str(e)}")

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
            logger.error(f"Failed to refine message: {original_message}")
            raise RuntimeError(f"Prompt refinement process failed: {str(e)}") from e

    def _initialize_hybrid_retriever(self) -> HybridRetriever:
        """
        Initialize hybrid retriever for document retrieval.

        Returns:
            HybridRetriever: Initialized hybrid retriever instance
        """
        logger.info("Initializing hybrid retriever")

        try:
            # Initialize vector store with chunk config
            chunk_config = ChunkConfig()
            hybrid_retriever = HybridRetriever(cfg=chunk_config)

            logger.info("Hybrid retriever initialized successfully")
            return hybrid_retriever

        except Exception as e:
            logger.error(f"Failed to initialize hybrid retriever: {str(e)}")
            raise

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

    def _retrieve_relevant_chunks(
        self, hybrid_retriever: HybridRetriever, refined_output: PromptRefinerOutput
    ) -> List[Dict[str, Union[str, float, Dict[str, Any]]]]:
        """
        Retrieve relevant chunks using hybrid retrieval approach.

        Args:
            hybrid_retriever: The hybrid retriever instance to use
            refined_output: The output from prompt refinement containing original and refined questions

        Returns:
            List of relevant document chunks with scores and metadata

        Raises:
            ValueError: When Hybrid Retriever is not initialized
            Exception: For retrieval errors
        """
        logger.info("Starting chunk retrieval process")

        try:
            # Use the hybrid retriever to get relevant chunks
            relevant_chunks = hybrid_retriever.retrieve(
                original_question=refined_output.original_question,
                refined_questions=refined_output.refined_questions,
                topk_dense=40,
                topk_bm25=40,
                fused_cap=120,
                final_topn=12,
            )

            logger.info(f"Retrieved {len(relevant_chunks)} relevant chunks")

            # Log first 3 for debugging (safe formatting for score)
            for i, chunk in enumerate(relevant_chunks[:3]):
                score = chunk.get("score", 0.0)
                try:
                    score_str = (
                        f"{float(score):.4f}"
                        if isinstance(score, (int, float))
                        else str(score)
                    )
                except Exception:
                    score_str = str(score)
                logger.info(
                    f"Chunk {i + 1}: ID={chunk.get('id', 'N/A')}, Score={score_str}"
                )

            return relevant_chunks

        except Exception as e:
            logger.error(f"Chunk retrieval failed: {str(e)}")
            logger.error(
                f"Failed to retrieve chunks for question: {refined_output.original_question}"
            )
            raise RuntimeError(f"Chunk retrieval process failed: {str(e)}") from e

    def _generate_rag_response(
        self,
        llm_manager: LLMManager,
        request: OrchestrationRequest,
        refined_output: PromptRefinerOutput,
        relevant_chunks: List[Dict[str, Union[str, float, Dict[str, Any]]]],
        response_generator: Optional[ResponseGeneratorAgent] = None,
        costs_dict: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> OrchestrationResponse:
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

            if question_out_of_scope:
                logger.info("Question determined out-of-scope – sending fixed message.")
                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=True,  # service OK; insufficient context
                    questionOutOfLLMScope=True,
                    inputGuardFailed=False,
                    content=OUT_OF_SCOPE_MESSAGE,
                )

            # In-scope: return the answer as-is (NO citations)
            logger.info("Returning in-scope answer without citations.")
            return OrchestrationResponse(
                chatId=request.chatId,
                llmServiceActive=True,
                questionOutOfLLMScope=False,
                inputGuardFailed=False,
                content=answer,
            )

        except Exception as e:
            logger.error(f"RAG Response generation failed: {str(e)}")
            # Standardized technical issue; no second LLM call, no citations
            return OrchestrationResponse(
                chatId=request.chatId,
                llmServiceActive=False,
                questionOutOfLLMScope=False,
                inputGuardFailed=False,
                content=TECHNICAL_ISSUE_MESSAGE,
            )
