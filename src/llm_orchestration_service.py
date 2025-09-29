"""LLM Orchestration Service - Business logic for LLM orchestration with Langfuse tracing."""

from typing import Optional, List, Dict, Union, Any
import json
import dspy
from loguru import logger
from langfuse import Langfuse, observe

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

# Constants
UNKNOWN_SOURCE = "Unknown source"


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
                        host=langfuse_secrets.get("host", "http://langfuse-web:3000")
                    )
                    logger.info("Langfuse client initialized successfully")
                else:
                    logger.warning("Langfuse secrets not found in Vault")
            else:
                logger.warning("Vault not available, Langfuse tracing disabled")
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")


class LLMOrchestrationService:
    """Stateless service class for handling LLM orchestration business logic with Langfuse tracing."""

    def __init__(self) -> None:
        """Initialize the stateless orchestration service."""
        self.langfuse_config = LangfuseConfig()

    @observe(name="orchestration_request")
    def process_orchestration_request(
        self, request: OrchestrationRequest
    ) -> OrchestrationResponse:
        """
        Process an orchestration request and return response with Langfuse tracing.

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

            # Initialize LLM Manager with configuration (per-request)
            llm_manager = self._initialize_llm_manager(
                environment=request.environment, connection_id=request.connection_id
            )

            # Initialize Hybrid Retriever (per-request)
            hybrid_retriever: Optional[HybridRetriever] = None
            try:
                hybrid_retriever = self._initialize_hybrid_retriever()
                logger.info("Hybrid Retriever initialization successful")
            except Exception as retriever_error:
                logger.warning(
                    f"Hybrid Retriever initialization failed: {str(retriever_error)}"
                )
                logger.warning("Continuing without chunk retrieval capabilities")
                hybrid_retriever = None

            # Initialize Response Generator
            response_generator: Optional[ResponseGeneratorAgent] = None
            try:
                response_generator = self._initialize_response_generator(llm_manager)
                logger.info("Response Generator initialization successful")
            except Exception as generator_error:
                logger.warning(
                    f"Response Generator initialization failed: {str(generator_error)}"
                )
                logger.warning("Continuing without response generator capabilities")
                response_generator = None

            # Step 2: Refine user prompt using loaded configuration
            refined_output = self._refine_user_prompt(
                llm_manager=llm_manager,
                original_message=request.message,
                conversation_history=request.conversationHistory,
            )

            # Step 3: Retrieve relevant chunks using hybrid retrieval
            relevant_chunks: List[Dict[str, Union[str, float, Dict[str, Any]]]] = []
            if hybrid_retriever is not None:
                try:
                    relevant_chunks = self._retrieve_relevant_chunks(
                        hybrid_retriever=hybrid_retriever, refined_output=refined_output
                    )
                    logger.info(f"Successfully retrieved {len(relevant_chunks)} chunks")
                except Exception as retrieval_error:
                    logger.warning(f"Chunk retrieval failed: {str(retrieval_error)}")
                    logger.warning(
                        "Continuing with response generation without retrieved chunks"
                    )
                    relevant_chunks = []
            else:
                logger.info("Hybrid Retriever not available, skipping chunk retrieval")

            # Step 4: Generate response using retrieved chunks and response generator
            try:
                response = self._generate_rag_response(
                    llm_manager=llm_manager,
                    request=request,
                    refined_output=refined_output,
                    relevant_chunks=relevant_chunks,
                    response_generator=response_generator,
                )
                logger.info(
                    f"Successfully generated RAG response for chatId: {request.chatId}"
                )
                        
            except Exception as response_error:
                logger.warning(f"RAG response generation failed: {str(response_error)}")
                logger.warning("Falling back to basic response")
                response = self._generate_fallback_response(
                    request.chatId, len(relevant_chunks)
                )

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

    @observe(name="prompt_refinement", as_type="chain")
    def _refine_user_prompt(
        self,
        llm_manager: LLMManager,
        original_message: str,
        conversation_history: List[ConversationItem],
    ) -> PromptRefinerOutput:
        """
        Refine user prompt using loaded LLM configuration and log all variants with Langfuse tracing.

        Args:
            llm_manager: The LLM manager instance to use
            original_message: The original user message to refine
            conversation_history: Previous conversation context

        Returns:
            PromptRefinerOutput: The refined prompt output containing original and refined questions

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
            return validated_output

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

    @observe(name="chunk_retrieval", as_type="retriever")
    def _retrieve_relevant_chunks(
        self, hybrid_retriever: HybridRetriever, refined_output: PromptRefinerOutput
    ) -> List[Dict[str, Union[str, float, Dict[str, Any]]]]:
        """
        Retrieve relevant chunks using hybrid retrieval approach with Langfuse tracing.

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

            # Log chunk information for debugging
            for i, chunk in enumerate(relevant_chunks[:3]):  # Log first 3 chunks
                logger.info(
                    f"Chunk {i + 1}: ID={chunk.get('id', 'N/A')}, Score={chunk.get('score', 'N/A'):.4f}"
                )

            return relevant_chunks

        except Exception as e:
            logger.error(f"Chunk retrieval failed: {str(e)}")
            logger.error(
                f"Failed to retrieve chunks for question: {refined_output.original_question}"
            )
            raise RuntimeError(f"Chunk retrieval process failed: {str(e)}") from e

    @observe(name="response_generation", as_type="generation")
    def _generate_rag_response(
        self,
        llm_manager: LLMManager,
        request: OrchestrationRequest,
        refined_output: PromptRefinerOutput,
        relevant_chunks: List[Dict[str, Union[str, float, Dict[str, Any]]]],
        response_generator: Optional[ResponseGeneratorAgent] = None,
    ) -> OrchestrationResponse:
        """
        Generate response using retrieved chunks and LLM with ResponseGeneratorAgent and Langfuse tracing.

        Args:
            llm_manager: The LLM manager instance to use
            request: The original orchestration request
            refined_output: The refined prompt output
            relevant_chunks: List of relevant document chunks
            response_generator: Optional response generator agent for humanized responses

        Returns:
            OrchestrationResponse with LLM-generated content
        """
        logger.info("Starting RAG response generation")

        try:
            # Use ResponseGeneratorAgent if available for better humanized responses
            if response_generator is not None and relevant_chunks:
                logger.info("Using ResponseGeneratorAgent for humanized response")

                # Set up DSPy context for response generation
                with llm_manager.use_task_local():
                    # Generate humanized response using the response generator
                    generator_result = response_generator.forward(
                        question=refined_output.original_question,
                        chunks=relevant_chunks,
                        max_blocks=10,
                    )

                # Extract answer and out-of-scope flag
                answer = generator_result.get("answer", "").strip()
                question_out_of_scope = generator_result.get(
                    "questionOutOfLLMScope", False
                )
                
                # Extract usage and model information
                usage_info = generator_result.get("usage")
                model_name = generator_result.get("model")

                # Log usage information if available
                if usage_info:
                    logger.info(f"Token usage: {usage_info}")
                if model_name:
                    logger.info(f"Model used: {model_name}")

                # Update Langfuse with usage and model information
                if self.langfuse_config.langfuse_client and (usage_info or model_name):
                    try:
                        langfuse = self.langfuse_config.langfuse_client
                        
                        update_data = {}
                        
                        # Add usage details if available
                        if usage_info:
                            usage_details = {}
                            if usage_info.get("input_tokens"):
                                usage_details["input"] = usage_info["input_tokens"]
                            if usage_info.get("output_tokens"):
                                usage_details["output"] = usage_info["output_tokens"]
                            if usage_info.get("total_tokens"):
                                usage_details["total"] = usage_info["total_tokens"]
                            if usage_details:
                                update_data["usage"] = usage_details
                        
                        # Add model name if available - normalize for Langfuse
                        if model_name:
                            normalized_model = self._normalize_model_name(model_name)
                            update_data["model"] = normalized_model
                            
                        if update_data:
                            langfuse.update_current_generation(**update_data)
                            logger.info(f"Updated Langfuse with: {update_data}")
                            
                    except Exception as e:
                        logger.warning(f"Failed to update Langfuse with usage data: {e}")

                # Add citations for transparency
                citations: List[str] = []
                for i, chunk in enumerate(relevant_chunks[:10]):
                    score = chunk.get("score", 0.0)
                    metadata = chunk.get("meta", {})
                    source_file = UNKNOWN_SOURCE
                    if isinstance(metadata, dict):
                        source_file = metadata.get("source_file", UNKNOWN_SOURCE)
                    citations.append(
                        f"[{i + 1}] {source_file} (relevance: {score:.3f})"
                    )

                # Add citations section if answer is not out of scope
                if citations and not question_out_of_scope and answer:
                    answer += "\n\nReferences:\n" + "\n".join(citations)

                logger.info(
                    f"Generated humanized response. Out of scope: {question_out_of_scope}"
                )

                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=True,
                    questionOutOfLLMScope=question_out_of_scope,
                    inputGuardFailed=False,
                    content=answer,
                )

            # Fallback to original method if ResponseGeneratorAgent is not available
            logger.info("Using fallback response generation method")
            return self._generate_fallback_rag_response(
                llm_manager, request, refined_output, relevant_chunks
            )

        except Exception as e:
            logger.error(f"RAG response generation failed: {str(e)}")
            raise RuntimeError(
                f"RAG response generation process failed: {str(e)}"
            ) from e

    def _normalize_model_name(self, model_name: str) -> str:
        """
        Normalize model names for Langfuse compatibility.
        
        Args:
            model_name: Original model name from DSPy
            
        Returns:
            Normalized model name that Langfuse can recognize
        """
        if not model_name:
            return model_name
            
        # Convert Azure model names to standard format
        if 'azure/' in model_name:
            normalized = model_name.replace('azure/', '')
            # Map specific Azure model names to Langfuse-recognized names
            return normalized
            
        return model_name

    def _generate_fallback_rag_response(
        self,
        llm_manager: LLMManager,
        request: OrchestrationRequest,
        refined_output: PromptRefinerOutput,
        relevant_chunks: List[Dict[str, Union[str, float, Dict[str, Any]]]],
    ) -> OrchestrationResponse:
        """
        Fallback RAG response generation when ResponseGeneratorAgent is not available.

        Args:
            llm_manager: The LLM manager instance to use
            request: The original orchestration request
            refined_output: The refined prompt output
            relevant_chunks: List of relevant document chunks

        Returns:
            OrchestrationResponse with LLM-generated content
        """
        logger.info("Starting fallback RAG response generation")

        try:
            # Prepare context from chunks
            context_sections: List[str] = []
            citations: List[str] = []

            for i, chunk in enumerate(relevant_chunks[:10]):  # Use top 10 chunks
                chunk_text = chunk.get("text", "")
                score = chunk.get("score", 0.0)
                metadata = chunk.get("meta", {})

                # Add chunk to context
                if chunk_text:
                    context_sections.append(f"[Context {i + 1}]\n{chunk_text}")

                    # Extract source information for citations
                    source_file = UNKNOWN_SOURCE
                    if isinstance(metadata, dict):
                        source_file = metadata.get("source_file", UNKNOWN_SOURCE)
                    citations.append(
                        f"[{i + 1}] {source_file} (relevance: {score:.3f})"
                    )

            # Combine context
            context = (
                "\n\n".join(context_sections)
                if context_sections
                else "No relevant context found."
            )

            # Create RAG prompt
            rag_prompt = f"""You are a helpful AI assistant that answers questions based on the provided context. Use the context to answer the user's question accurately and cite your sources.

Context:
{context}

Question: {refined_output.original_question}

Instructions:
1. Answer the question based only on the information provided in the context
2. If the context doesn't contain enough information to answer the question, say so clearly
3. Include relevant citations in your response
4. Be concise but thorough in your answer

Answer:"""

            # Generate response using LLM
            try:
                
                # Create the prediction and make the LLM call
                generate = dspy.Predict("prompt -> response")
                
                # Make the LLM call with task-local context
                with llm_manager.use_task_local():
                    result = generate(prompt=rag_prompt)
                
                response_text = str(getattr(result, "response", result))                
                # Extract model name and normalize it
                model_name = self._get_model_name_from_dspy()
                normalized_model = self._normalize_model_name(model_name) if model_name else None
                
                # Update Langfuse with model information
                if self.langfuse_config.langfuse_client and normalized_model:
                    try:
                        langfuse = self.langfuse_config.langfuse_client
                        
                        update_data = {"model": normalized_model}
                        langfuse.update_current_generation(**update_data)
                        
                    except Exception as e:
                        logger.warning(f"Failed to update Langfuse: {e}")

                # Add citations section
                if citations:
                    response_text += "\n\nReferences:\n" + "\n".join(citations)


                return OrchestrationResponse(
                    chatId=request.chatId,
                    llmServiceActive=True,
                    questionOutOfLLMScope=False,
                    inputGuardFailed=False,
                    content=response_text,
                )

            except Exception as llm_error:
                logger.error(f"LLM generation failed: {str(llm_error)}")
                raise RuntimeError(f"LLM response generation failed: {str(llm_error)}") from llm_error

        except Exception as e:
            logger.error(f"RAG response generation failed: {str(e)}")
            raise RuntimeError(f"RAG response generation process failed: {str(e)}") from e

    def _get_model_name_from_dspy(self) -> Optional[str]:
        """Extract the model name from DSPy settings."""
        try:
            logger.info("COST_DEBUG: Extracting model name from DSPy")
            
            if hasattr(dspy.settings, 'lm'):
                lm = dspy.settings.lm
                
                # Try different model name attributes
                if hasattr(lm, 'model'):
                    model_name = lm.model
                    return model_name
                elif hasattr(lm, 'model_name'):
                    model_name = lm.model_name
                    return model_name
                elif hasattr(lm, '_model'):
                    model_name = lm._model
                    return model_name
                elif hasattr(lm, 'kwargs') and isinstance(lm.kwargs, dict) and 'model' in lm.kwargs:
                    model_name = lm.kwargs['model']
                    return model_name
                else:
                    return None
            else:
                return None                
        except Exception as e:
            logger.warning(f"Failed to extract model name from DSPy: {e}")
        return None

    def _generate_fallback_response(
        self, chat_id: str, chunk_count: Optional[int] = None
    ) -> OrchestrationResponse:
        """
        Generate fallback response when RAG generation fails.

        Args:
            chat_id: Chat session identifier
            chunk_count: Optional number of retrieved chunks for debugging

        Returns:
            OrchestrationResponse with fallback content
        """
        fallback_content = """I apologize, but I'm currently unable to generate a complete response based on the available information. 

This could be due to:
- Insufficient relevant context in the knowledge base
- Technical issues with the response generation system

Please try rephrasing your question or contact support if the issue persists."""

        if chunk_count is not None:
            fallback_content += f"\n\n[Debug: Retrieved {chunk_count} relevant chunks]"

        return OrchestrationResponse(
            chatId=chat_id,
            llmServiceActive=True,
            questionOutOfLLMScope=False,
            inputGuardFailed=False,
            content=fallback_content,
        )