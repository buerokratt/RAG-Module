# LLM Orchestration Service API

A FastAPI-based service for orchestrating LLM requests with configuration management, prompt refinement, and proper validation.

## Overview

The LLM Orchestration Service provides a unified API for processing user queries through a sophisticated pipeline that includes configuration management, prompt refinement, and LLM interaction. The service integrates multiple components to deliver intelligent responses with proper validation and error handling.

## Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   Client Request                                   │
│                              POST /orchestrate                                     │
└─────────────────────────┬───────────────────────────────────────────────────────────┘
                          │ OrchestrationRequest
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Application                                     │
│                        (llm_orchestration_service_api.py)                          │
│  • Request validation with Pydantic                                                │
│  • Lifespan management                                                             │
│  • Error handling & logging                                                        │
└─────────────────────────┬───────────────────────────────────────────────────────────┘
                          │ Validated Request
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          Business Logic Service                                    │
│                        (llm_orchestration_service.py)                              │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │ Step 1: LLM Configuration Management                                       │   │
│  │ • Initialize LLMManager with environment context                           │   │
│  │ • Load configuration from Vault (via llm_config_module)                    │   │
│  │ • Select appropriate LLM provider (Azure OpenAI, AWS Bedrock, etc.)       │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                          │                                                         │
│                          ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │ Step 2: Prompt Refinement                                                  │   │
│  │ • Create PromptRefinerAgent with LLMManager instance                        │   │
│  │ • Convert conversation history to DSPy format                              │   │
│  │ • Generate N distinct refined question variants                            │   │
│  │ • Validate output with PromptRefinerOutput schema                          │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                          │                                                         │
│                          ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │ Step 3: LLM Processing Pipeline (TODO)                                     │   │
│  │ • Input validation and guard checks                                        │   │
│  │ • Context preparation from conversation history                            │   │
│  │ • Question scope validation                                                │   │
│  │ • LLM inference execution                                                  │   │
│  │ • Response post-processing                                                 │   │
│  │ • Citation generation                                                      │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────┬───────────────────────────────────────────────────────────┘
                          │ OrchestrationResponse
                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                Client Response                                      │
│                              JSON with status flags                                │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Component Integration

### 1. LLM Configuration Module Reuse

The `llm_config_module` is the core configuration management system that's reused throughout the orchestration flow:

```python
# Initialization in orchestration service
self.llm_manager = LLMManager(
    environment=environment,      # production/test/development
    connection_id=connection_id   # tenant/client identifier
)
```

**Configuration Flow:**
1. **Vault Integration**: LLMManager connects to HashiCorp Vault using `rag_config_manager.vault.client`
2. **Schema Validation**: Configuration is validated against `llm_config_module.config.schema`
3. **Provider Selection**: Based on config, appropriate provider is selected (Azure OpenAI, AWS Bedrock)
4. **LLM Instance Creation**: Provider-specific LLM instances are created and cached

### 2. Prompt Refiner Integration

The prompt refiner reuses the same LLMManager instance for consistency:

```python
# Create refiner with shared configuration
refiner = PromptRefinerAgent(llm_manager=self.llm_manager)

# Generate structured refinement output
refinement_result = refiner.forward_structured(
    history=conversation_history,
    question=original_message
)
```

## API Endpoints

### POST /orchestrate

Processes LLM orchestration requests through the complete pipeline.

**Input Schema** (`OrchestrationRequest`):
```json
{
    "chatId": "string - Unique chat session identifier",
    "message": "string - User's input message",
    "authorId": "string - User/author identifier", 
    "conversationHistory": [
        {
            "authorRole": "user|bot|assistant",
            "message": "string - Message content",
            "timestamp": "ISO 8601 datetime string"
        }
    ],
    "url": "string - Context URL (e.g., 'id.ee')",
    "environment": "production|test|development",
    "connection_id": "string (optional) - Tenant/connection identifier"
}
```

**Output Schema** (`OrchestrationResponse`):
```json
{
    "chatId": "string - Same as input",
    "llmServiceActive": "boolean - Whether LLM processing succeeded",
    "questionOutOfLLMScope": "boolean - Whether question is out of scope",
    "inputGuardFailed": "boolean - Whether input validation failed",
    "content": "string - Response content with citations"
}
```

**Prompt Refiner Output Schema** (`PromptRefinerOutput`):
```json
{
    "original_question": "string - The original user question",
    "refined_questions": [
        "string - Refined variant 1",
        "string - Refined variant 2", 
        "string - Refined variant N"
    ]
}
```
```

### GET /health
Health check endpoint for monitoring service availability.

**Response:**
```json
{
    "status": "healthy",
    "service": "llm-orchestration-service"
}
```

## Running the API

### Local Development:
```bash
uv run uvicorn src.llm_orchestration_service_api:app --host 0.0.0.0 --port 8100 --reload
```

### Docker (Standalone):
```bash
# Build and run with custom script
.\build-llm-service.bat run       # Windows
./build-llm-service.sh run        # Linux/Mac

# Or manually
docker build -f Dockerfile.llm_orchestration_service -t llm-orchestration-service .
docker run -p 8100:8100 --env-file .env llm-orchestration-service
```

### Docker Compose (Production):
```bash
docker-compose up llm-orchestration-service
```

### Docker Compose (Development with hot reload):
```bash
docker-compose -f docker-compose.yml -f docker-compose.llm-dev.yml up llm-orchestration-service
```

### Test the API:
```bash
uv run python test_api.py
```

## Features

- ✅ FastAPI with automatic OpenAPI documentation
- ✅ Pydantic validation for requests/responses
- ✅ Proper error handling and logging with Loguru
- ✅ Integration with existing LLM config module
- ✅ Type-safe implementation
- ✅ Health check endpoint
- 🔄 Hardcoded responses (TODO: Implement actual LLM pipeline)

## Documentation

When the server is running, visit:
- API docs: http://localhost:8100/docs
- ReDoc: http://localhost:8100/redoc

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                     │
│                (llm_orchestration_service_api.py)          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                Business Logic Service                      │
│                (llm_orchestration_service.py)              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLM Config Module                         │
│                   (llm_manager.py)                         │
└─────────────────────────────────────────────────────────────┘
```

## TODO Items

- [ ] Implement actual LLM processing pipeline
- [ ] Add input validation and guard checks
- [ ] Implement question scope validation
- [ ] Add proper citation generation
- [ ] Handle multi-tenant scenarios with connection_id
- [ ] Add authentication/authorization
- [ ] Add comprehensive error handling
- [ ] Add request/response logging
- [ ] Add metrics and monitoring
