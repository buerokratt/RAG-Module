"""LLM Orchestration Service API - FastAPI application."""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict

from fastapi import FastAPI, HTTPException, status, Request
from loguru import logger
import uvicorn

from llm_orchestration_service import LLMOrchestrationService
from models.request_models import (
    OrchestrationRequest,
    OrchestrationResponse,
    TestOrchestrationRequest,
    TestOrchestrationResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ContextGenerationRequest,
    ContextGenerationResponse,
    EmbeddingErrorResponse,
    DeepEvalTestOrchestrationResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting LLM Orchestration Service API")
    try:
        app.state.orchestration_service = LLMOrchestrationService()
        logger.info("LLM Orchestration Service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LLM Orchestration Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down LLM Orchestration Service API")
    # Clean up resources if needed
    if hasattr(app.state, "orchestration_service"):
        app.state.orchestration_service = None


# Create FastAPI application
app = FastAPI(
    title="LLM Orchestration Service API",
    description="API for orchestrating LLM requests with configuration management",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check(request: Request) -> dict[str, str]:
    """Health check endpoint."""
    service_status = (
        "initialized"
        if hasattr(request.app.state, "orchestration_service")
        and request.app.state.orchestration_service is not None
        else "not_initialized"
    )
    return {
        "status": "healthy",
        "service": "llm-orchestration-service",
        "orchestration_service": service_status,
    }


@app.post(
    "/orchestrate",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process LLM orchestration request",
    description="Processes a user message through the LLM orchestration pipeline",
)
def orchestrate_llm_request(
    http_request: Request,
    request: OrchestrationRequest,
) -> OrchestrationResponse:
    """
    Process LLM orchestration request.

    Args:
        http_request: FastAPI Request object for accessing app state
        request: OrchestrationRequest containing user message and context

    Returns:
        OrchestrationResponse: Response with LLM output and status flags

    Raises:
        HTTPException: For processing errors
    """
    try:
        logger.info(f"Received orchestration request for chatId: {request.chatId}")

        # Get the orchestration service from app state
        if not hasattr(http_request.app.state, "orchestration_service"):
            logger.error("Orchestration service not found in app state")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        orchestration_service = http_request.app.state.orchestration_service
        if orchestration_service is None:
            logger.error("Orchestration service is None")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        # Process the request
        response = orchestration_service.process_orchestration_request(request)

        logger.info(f"Successfully processed request for chatId: {request.chatId}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred",
        )


@app.post(
    "/orchestrate/test",
    response_model=TestOrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process test LLM orchestration request",
    description="Processes a simplified test message through the LLM orchestration pipeline",
)
def test_orchestrate_llm_request(
    http_request: Request,
    request: TestOrchestrationRequest,
) -> TestOrchestrationResponse:
    """
    Process test LLM orchestration request with simplified input.

    Args:
        http_request: FastAPI Request object for accessing app state
        request: TestOrchestrationRequest containing only message, environment, and connection_id

    Returns:
        TestOrchestrationResponse: Response with LLM output and status flags (without chatId)

    Raises:
        HTTPException: For processing errors
    """
    try:
        logger.info(
            f"Received test orchestration request for environment: {request.environment}"
        )

        # Get the orchestration service from app state
        if not hasattr(http_request.app.state, "orchestration_service"):
            logger.error("Orchestration service not found in app state")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        orchestration_service = http_request.app.state.orchestration_service
        if orchestration_service is None:
            logger.error("Orchestration service is None")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        # Map TestOrchestrationRequest to OrchestrationRequest with defaults
        full_request = OrchestrationRequest(
            chatId="test-session",
            message=request.message,
            authorId="test-user",
            conversationHistory=[],
            url="test-context",
            environment=request.environment,
            connection_id=str(request.connectionId),
        )

        logger.info(f"This is full request constructed for testing: {full_request}")

        # Process the request using the same logic
        response = orchestration_service.process_orchestration_request(full_request)

        # Convert to TestOrchestrationResponse (exclude chatId)
        test_response = TestOrchestrationResponse(
            llmServiceActive=response.llmServiceActive,
            questionOutOfLLMScope=response.questionOutOfLLMScope,
            inputGuardFailed=response.inputGuardFailed,
            content=response.content,
        )

        logger.info(
            f"Successfully processed test request for environment: {request.environment}"
        )
        return test_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing test request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred",
        )


@app.post(
    "/embeddings",
    response_model=EmbeddingResponse,
    responses={500: {"model": EmbeddingErrorResponse}},
)
async def create_embeddings(request: EmbeddingRequest) -> EmbeddingResponse:
    """
    Create embeddings using DSPy with vault-driven model resolution.

    Model selection is automatic based on environment and connection_id:
    - Production: Uses first available embedding model from vault
    - Development/Test: Uses model associated with connection_id

    Supports Azure OpenAI, AWS Bedrock, and OpenAI embedding models.
    Includes automatic retry with exponential backoff.
    """
    try:
        logger.info(
            f"Creating embeddings for {len(request.texts)} texts in {request.environment} environment"
        )

        result: Dict[str, Any] = (
            app.state.orchestration_service.create_embeddings_for_indexer(
                texts=request.texts,
                environment=request.environment,
                connection_id=request.connection_id,
                batch_size=request.batch_size or 50,
            )
        )

        return EmbeddingResponse(**result)

    except Exception as e:
        logger.error(f"Embedding creation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "failed_texts": request.texts[:5],  # Don't log all texts for privacy
                "retry_after": 30,
            },
        )


@app.post("/generate-context", response_model=ContextGenerationResponse)
async def generate_context_with_caching(
    request: ContextGenerationRequest,
) -> ContextGenerationResponse:
    """
    Generate contextual descriptions using Anthropic methodology.

    Uses exact Anthropic prompt templates and supports structure for
    future prompt caching implementation for cost optimization.
    """
    try:
        result = app.state.orchestration_service.generate_context_for_chunks(request)

        return ContextGenerationResponse(**result)

    except Exception as e:
        logger.error(f"Context generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/embedding-models")
async def get_available_embedding_models(
    environment: str = "production",
) -> Dict[str, Any]:
    """Get available embedding models from vault configuration.

    Args:
        environment: Environment to get models for (production, development, test)

    Returns:
        Dictionary with available models and default model information
    """
    try:
        # Get available embedding models using vault-driven resolution
        result: Dict[str, Any] = (
            app.state.orchestration_service.get_available_embedding_models_for_indexer(
                environment=environment
            )
        )
        return result

    except Exception as e:
        logger.error(f"Failed to get embedding models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrate-test")
def orchestrate_llm_request_test(
    http_request: Request,
    request: OrchestrationRequest,
) -> DeepEvalTestOrchestrationResponse:
    """
    Process LLM orchestration request with additional testing data.

    This endpoint is only available when TESTING_MODE=true and returns
    retrieval context and refined questions for DeepEval metrics evaluation.

    Args:
        http_request: FastAPI Request object for accessing app state
        request: OrchestrationRequest containing user message and context

    Returns:
        DeepEvalTestOrchestrationResponse: Response with LLM output, status flags, and test data

    Raises:
        HTTPException: For processing errors or if not in testing mode
    """
    # Check if testing mode is enabled
    testing_mode = os.getenv("TESTING_MODE", "false").lower() == "true"
    if not testing_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Testing endpoint not available in production mode",
        )

    try:
        logger.info(f"Received TEST orchestration request for chatId: {request.chatId}")

        if not hasattr(http_request.app.state, "orchestration_service"):
            logger.error("Orchestration service not found in app state")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        orchestration_service = http_request.app.state.orchestration_service
        if orchestration_service is None:
            logger.error("Orchestration service is None")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        # Process the request (will include test data due to TESTING_MODE env var)
        response = orchestration_service.process_orchestration_request(request)

        # Convert to test response with additional fields
        test_response = DeepEvalTestOrchestrationResponse(
            chatId=response.chatId,
            llmServiceActive=response.llmServiceActive,
            questionOutOfLLMScope=response.questionOutOfLLMScope,
            inputGuardFailed=response.inputGuardFailed,
            content=response.content,
            retrieval_context=response.retrieval_context,
            refined_questions=response.refined_questions,
            expected_output=None,  # Will be populated by test framework
        )

        logger.info(f"Successfully processed TEST request for chatId: {request.chatId}")
        return test_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing TEST request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred",
        )


if __name__ == "__main__":
    logger.info("Starting LLM Orchestration Service API server on port 8100")
    uvicorn.run(
        "llm_orchestration_service_api:app",
        host="0.0.0.0",
        port=8100,
        log_level="info",
    )
