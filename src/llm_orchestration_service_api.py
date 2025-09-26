"""LLM Orchestration Service API with Proper Langfuse Integration - FastAPI application."""

import os
import signal
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any
import asyncio

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger
import uvicorn
from langfuse import observe, get_client

from llm_orchestration_service import LLMOrchestrationService
from models.request_models import OrchestrationRequest, OrchestrationResponse


# Global service instance
orchestration_service: LLMOrchestrationService | None = None


class LangfuseConfig:
    """Configuration class for Langfuse settings."""
    
    def __init__(self):
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        self.enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
        self.flush_at = int(os.getenv("LANGFUSE_FLUSH_AT", "1"))
        self.flush_interval = int(os.getenv("LANGFUSE_FLUSH_INTERVAL", "5"))
        self.max_retries = int(os.getenv("LANGFUSE_MAX_RETRIES", "3"))
        self.timeout = int(os.getenv("LANGFUSE_TIMEOUT", "30"))
        self.debug = os.getenv("LANGFUSE_DEBUG", "false").lower() == "true"
    
    def is_configured(self) -> bool:
        """Check if Langfuse is properly configured."""
        return bool(self.secret_key and self.public_key and self.enabled)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        return {
            "host": self.host,
            "enabled": self.enabled,
            "flush_at": self.flush_at,
            "flush_interval": self.flush_interval,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
            "debug": self.debug,
            "configured": self.is_configured()
        }


# Initialize Langfuse configuration
langfuse_config = LangfuseConfig()


async def graceful_shutdown():
    """Handle graceful shutdown of the service."""
    global orchestration_service
    logger.info("Initiating graceful shutdown...")
    
    if orchestration_service:
        try:
            # Flush any pending Langfuse traces
            orchestration_service.flush_langfuse_traces()
            logger.info("Langfuse traces flushed during shutdown")
        except Exception as e:
            logger.error(f"Error flushing Langfuse traces during shutdown: {e}")
    
    # Also flush the global Langfuse client
    try:
        langfuse_client = get_client()
        if langfuse_client:
            langfuse_client.flush()
            logger.info("Global Langfuse client flushed")
    except Exception as e:
        logger.error(f"Error flushing global Langfuse client: {e}")
    
    logger.info("Graceful shutdown completed")


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(graceful_shutdown())
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager with enhanced initialization and cleanup."""
    # Startup
    logger.info("Starting LLM Orchestration Service API with Langfuse integration")
    
    # Setup signal handlers for graceful shutdown
    setup_signal_handlers()
    
    # Log Langfuse configuration
    if langfuse_config.is_configured():
        logger.info(f"Langfuse tracing enabled, host: {langfuse_config.host}")
        if langfuse_config.debug:
            logger.debug(f"Langfuse config: {langfuse_config.get_config_dict()}")
    else:
        logger.warning("Langfuse not properly configured - tracing will be disabled")
        logger.info("Required environment variables: LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY")
    
    # Initialize orchestration service
    global orchestration_service
    try:
        orchestration_service = LLMOrchestrationService()
        logger.info("LLM Orchestration Service initialized successfully")
        
        # Log tracing statistics
        tracing_stats = orchestration_service.get_tracing_stats()
        logger.info(f"Tracing stats: {tracing_stats}")
        
    except Exception as e:
        logger.error(f"Failed to initialize LLM Orchestration Service: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down LLM Orchestration Service API")
    await graceful_shutdown()


# Create FastAPI application with enhanced configuration
app = FastAPI(
    title="LLM Orchestration Service API",
    description="Enhanced API for orchestrating LLM requests with Langfuse tracing and configuration management",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add middleware for security and CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your security requirements
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure based on your security requirements
)


@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """Add request ID and basic request logging."""
    request_id = str(uuid.uuid4())
    
    # Add request ID to headers for tracing
    request.state.request_id = request_id
    
    # Log request details
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Log response details
        processing_time = time.time() - start_time
        logger.info(
            f"Request {request_id} completed: {response.status_code} "
            f"in {processing_time:.3f}s"
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        return response
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            f"Request {request_id} failed: {str(e)} "
            f"after {processing_time:.3f}s"
        )
        raise


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Enhanced health check endpoint with service status."""
    try:
        health_data = {
            "status": "healthy",
            "service": "llm-orchestration-service",
            "version": "2.0.0",
            "langfuse": {
                "enabled": langfuse_config.enabled,
                "configured": langfuse_config.is_configured(),
                "host": langfuse_config.host if langfuse_config.is_configured() else None,
            },
            "service_initialized": orchestration_service is not None,
        }
        
        # Add tracing stats if service is initialized
        if orchestration_service:
            health_data["tracing_stats"] = orchestration_service.get_tracing_stats()
            
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "llm-orchestration-service",
            "error": str(e)
        }


@app.get("/config/langfuse")
async def get_langfuse_config() -> dict[str, Any]:
    """Get Langfuse configuration status (without sensitive data)."""
    return {
        "langfuse_config": {
            "host": langfuse_config.host,
            "enabled": langfuse_config.enabled,
            "configured": langfuse_config.is_configured(),
            "flush_at": langfuse_config.flush_at,
            "flush_interval": langfuse_config.flush_interval,
            "max_retries": langfuse_config.max_retries,
            "timeout": langfuse_config.timeout,
            "debug": langfuse_config.debug,
        }
    }


@app.post("/config/langfuse/flush")
async def flush_langfuse_traces() -> dict[str, Any]:
    """Manually flush Langfuse traces."""
    if not orchestration_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service not initialized",
        )
    
    try:
        orchestration_service.flush_langfuse_traces()
        
        # Also flush the global client
        langfuse_client = get_client()
        if langfuse_client:
            langfuse_client.flush()
        
        return {
            "status": "success",
            "message": "Langfuse traces flushed successfully"
        }
    except Exception as e:
        logger.error(f"Failed to flush Langfuse traces: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to flush traces: {str(e)}"
        )


@app.post(
    "/orchestrate",
    response_model=OrchestrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Process LLM orchestration request with tracing",
    description="Processes a user message through the LLM orchestration pipeline with comprehensive Langfuse tracing",
)
@observe(name="api_orchestrate_request")
async def orchestrate_llm_request(
    request: OrchestrationRequest,
    http_request: Request,
) -> OrchestrationResponse:
    """
    Process LLM orchestration request with comprehensive tracing and error handling.

    Args:
        request: OrchestrationRequest containing user message and context
        http_request: FastAPI request object for metadata

    Returns:
        OrchestrationResponse: Response with LLM output and status flags
    """
    request_id = getattr(http_request.state, 'request_id', 'unknown')
    
    try:
        logger.info(f"[{request_id}] Received orchestration request for chatId: {request.chatId}")

        if orchestration_service is None:
            logger.error(f"[{request_id}] Orchestration service not initialized")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service not initialized",
            )

        # Process the request - the @observe decorator will handle tracing
        response = orchestration_service.process_orchestration_request(request)

        logger.info(f"[{request_id}] Successfully processed request for chatId: {request.chatId}")
        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error processing request: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred",
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Enhanced global exception handler with tracing."""
    request_id = getattr(request.state, 'request_id', 'unknown')
    
    logger.error(f"[{request_id}] Unhandled exception: {str(exc)}")
    logger.exception(f"[{request_id}] Exception details:")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id}
    )


@app.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Get service metrics and statistics."""
    try:
        metrics = {
            "service": "llm-orchestration-service",
            "version": "2.0.0",
            "status": "running",
            "langfuse": langfuse_config.get_config_dict(),
        }
        
        if orchestration_service:
            metrics["tracing_stats"] = orchestration_service.get_tracing_stats()
        
        return metrics
    
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@app.get("/cost-estimate")
async def estimate_cost(
    input_text: str = "Hello world",
    output_text: str = "Hello! How can I help you today?",
    model: str = "gpt-4o"
) -> dict[str, Any]:
    """Estimate cost for an LLM operation."""
    if not orchestration_service:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Service not initialized",
        )
    
    try:
        cost_estimate = orchestration_service.estimate_operation_cost(
            input_text=input_text,
            output_text=output_text,
            model=model
        )
        return cost_estimate
    except Exception as e:
        logger.error(f"Failed to estimate cost: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to estimate cost: {str(e)}"
        )


if __name__ == "__main__":
    # Configure logging for production
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    
    logger.info("Starting LLM Orchestration Service API server")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Langfuse enabled: {langfuse_config.enabled}")
    logger.info(f"Langfuse configured: {langfuse_config.is_configured()}")
    
    uvicorn.run(
        "llm_orchestration_service_api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8100")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
        log_level=log_level,
        access_log=True,
        use_colors=True,
    )