"""LLM Orchestration Service API - FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from loguru import logger
import uvicorn

from llm_orchestration_service import LLMOrchestrationService
from models.request_models import OrchestrationRequest, OrchestrationResponse


# Global service instance
orchestration_service: LLMOrchestrationService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting LLM Orchestration Service API")
    global orchestration_service
    orchestration_service = LLMOrchestrationService()
    logger.info("LLM Orchestration Service initialized")

    yield

    # Shutdown
    logger.info("Shutting down LLM Orchestration Service API")


# Create FastAPI application
app = FastAPI(
    title="LLM Orchestration Service API",
    description="API for orchestrating LLM requests with configuration management",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "llm-orchestration-service"}


@app.post(
    "/orchestrate",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process LLM orchestration request",
    description="Processes a user message through the LLM orchestration pipeline",
)
async def orchestrate_llm_request(
    request: OrchestrationRequest,
) -> OrchestrationResponse:
    """
    Process LLM orchestration request.

    Args:
        request: OrchestrationRequest containing user message and context

    Returns:
        OrchestrationResponse: Response with LLM output and status flags

    Raises:
        HTTPException: For processing errors
    """
    try:
        logger.info(f"Received orchestration request for chatId: {request.chatId}")

        if orchestration_service is None:
            logger.error("Orchestration service not initialized")
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
        reload=True,
        log_level="info",
    )
