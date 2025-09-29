"""LLM Orchestration Service API - FastAPI application with Langfuse tracing."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import time

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from loguru import logger
from langfuse import observe
import uvicorn

from llm_orchestration_service import LLMOrchestrationService
from models.request_models import OrchestrationRequest, OrchestrationResponse


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
    description="API for orchestrating LLM requests with configuration management and Langfuse tracing",
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


@observe()
@app.post(
    "/orchestrate",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process LLM orchestration request",
    description="Processes a user message through the LLM orchestration pipeline with Langfuse tracing",
)
def orchestrate_llm_request(
    http_request: Request,
    request: OrchestrationRequest,
) -> OrchestrationResponse:
    """
    Process LLM orchestration request with Langfuse tracing.

    Args:
        http_request: FastAPI Request object for accessing app state
        request: OrchestrationRequest containing user message and context

    Returns:
        OrchestrationResponse: Response with LLM output and status flags

    Raises:
        HTTPException: For processing errors
    """
    start_time = time.time()
    
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
        
        processing_time = time.time() - start_time
        logger.info(
            f"Successfully processed request for chatId: {request.chatId} "
            f"in {processing_time:.2f}s"
        )
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Unexpected error processing request: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred",
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: object, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    logger.info("Starting LLM Orchestration Service API server on port 8100")
    uvicorn.run(
        "llm_orchestration_service_api:app",
        host="0.0.0.0",
        port=8100,
        log_level="info",
    )