# LLM Connections API Endpoints

## Base URL
```
/ruuter-private/llm/connections
```

---

## 1. Create LLM Connection

### Endpoint
```http
POST /ruuter-private/llm/connections/create
```

### Request Body
```json
{
  "llmPlatform": "OpenAI",
  "llmModel": "GPT-4o",
  "llmApiKey": "your-api-key",
  "embeddingPlatform": "OpenAI",
  "embeddingModel": "text-embedding-3-small",
  "embeddingApiKey": "your-embedding-api-key",
  "monthlyBudget": 1000.00,
  "deploymentEnvironment": "Testing"
}
```

### Response (201 Created)
```json
{
  "id": 1,
  "llmPlatform": "OpenAI",
  "llmModel": "GPT-4o",
  "embeddingPlatform": "OpenAI",
  "embeddingModel": "text-embedding-3-small",
  "monthlyBudget": 1000.00,
  "deploymentEnvironment": "Testing",
  "status": "active",
  "createdAt": "2025-09-02T10:15:30.000Z",
  "updatedAt": "2025-09-02T10:15:30.000Z"
}
```

---

## 2. Update LLM Connection

### Endpoint
```http
POST /ruuter-private/llm/connections/update
```

### Request Body
```json
{
  "llmPlatform": "Azure AI",
  "llmModel": "GPT-4o-mini",
  "monthlyBudget": 2000.00,
  "deploymentEnvironment": "Production",
  "status": "inactive"
}
```

### Response (200 OK)
```json
{
  "id": 1,
  "llmPlatform": "Azure AI",
  "llmModel": "GPT-4o-mini",
  "monthlyBudget": 2000.00,
  "deploymentEnvironment": "Production",
  "status": "inactive",
  "createdAt": "2025-09-02T10:15:30.000Z",
  "updatedAt": "2025-09-02T11:00:00.000Z"
}
```

---

## 3. Delete LLM Connection

### Endpoint
```http
POST /ruuter-private/llm/connections/delete
```

### Response (200 OK)
```json
{
  "operationSuccessful": true,
  "message": "LLM Connection deleted successfully",
  "statusCode": 200
}
```

---

## 4. List All LLM Connections

### Endpoint
```http
GET /ruuter-private/llm/connections/list
```

### Query Parameters (Optional for filtering)
| Parameter | Type | Description |
|-----------|------|-------------|
| `llmPlatform` | `string` | Filter by LLM platform |
| `llmModel` | `string` | Filter by LLM model |
| `deploymentEnvironment` | `string` | Filter by environment (Testing / Production) |

### Example Request
```http
GET /ruuter-private/llm/connections/list?llmPlatform=OpenAI&deploymentEnvironment=Testing&model=GPT4
```

### Response (200 OK)
```json
[
  {
    "id": 1,
    "llmPlatform": "OpenAI",
    "llmModel": "GPT-4o",
    "embeddingPlatform": "OpenAI",
    "embeddingModel": "text-embedding-3-small",
    "monthlyBudget": 1000.00,
    "deploymentEnvironment": "Testing",
    "status": "active",
    "createdAt": "2025-09-02T10:15:30.000Z",
    "updatedAt": "2025-09-02T10:15:30.000Z"
  }
]
```

---

## 5. Get Single LLM Connection

### Endpoint
```http
GET /ruuter-private/llm/connections/overview
```

### Response (200 OK)
```json
{
  "id": 1,
  "llmPlatform": "OpenAI",
  "llmModel": "GPT-4o",
  "embeddingPlatform": "OpenAI",
  "embeddingModel": "text-embedding-3-small",
  "monthlyBudget": 1000.00,
  "deploymentEnvironment": "Testing",
  "status": "active",
  "createdAt": "2025-09-02T10:15:30.000Z",
  "updatedAt": "2025-09-02T10:15:30.000Z"
}
```

---
# Inference Results API Endpoints

## Base URL
```
/ruuter-private/inference/results
```

---

## 1. Store Inference Result

### Endpoint
```http
POST /ruuter-private/inference/results/store
```

### Request Body
```json
{
  "llmConnectionId": 1,
  "userQuestion": "What are the benefits of using LLMs?",
  "refinedQuestions": [
    "How do LLMs improve productivity?",
    "What are practical use cases of LLMs?"
  ],
  "conversationHistory": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help you?" }
  ],
  "rankedChunks": [
    { "id": "chunk_1", "content": "LLMs help in summarization", "rank": 1 },
    { "id": "chunk_2", "content": "They improve Q&A systems", "rank": 2 }
  ],
  "embeddingScores": {
    "chunk_1": 0.92,
    "chunk_2": 0.85
  },
  "finalAnswer": "LLMs can improve productivity by summarizing large documents, enabling Q&A, and enhancing automation."
}
```

### Response (201 Created)
```json
{
  "id": 10,
  "llmConnectionId": 1,
  "userQuestion": "What are the benefits of using LLMs?",
  "refinedQuestions": [
    "How do LLMs improve productivity?",
    "What are practical use cases of LLMs?"
  ],
  "conversationHistory": [
    { "role": "user", "content": "Hello" },
    { "role": "assistant", "content": "Hi! How can I help you?" }
  ],
  "rankedChunks": [
    { "id": "chunk_1", "content": "LLMs help in summarization", "rank": 1 },
    { "id": "chunk_2", "content": "They improve Q&A systems", "rank": 2 }
  ],
  "embeddingScores": {
    "chunk_1": 0.92,
    "chunk_2": 0.85
  },
  "finalAnswer": "LLMs can improve productivity by summarizing large documents, enabling Q&A, and enhancing automation.",
  "createdAt": "2025-09-02T12:15:00.000Z"
}
```

## 2. View/get Inference Result

### Endpoint
```http
POST /ruuter-private/inference/results/view
```

### Request Body
```json

{
  "llmConnectionId": 1,
  "message": "What are the benefits of using LLMs?"
}
```

### Response (200 OK)
```json
{
  "chatId": 10,
  "llmServiceActive": true,
  "questionOutOfLlmScope": true,
  "content": "Random answer with citations
  - https://gov.ee/sample1,
  - https://gov.ee/sample1"
  
}
```

## 3. Inquiry from chatbot to llm ochestration service

### Endpoint
```http
POST /ruuter-private/rag/inquiry
```

### Request Body
```json

{
    "chatId": "chat-12345",
    "message": "I need help with my electricity bill.",
    "authorId": "12345",
    "conversationHistory": [
        {
            "authorRole": "user",
            "message": "Hi, I have a billing issue",
            "timestamp": "2025-04-29T09:00:00Z"
        },
        {
            "authorRole": "bot",
            "message": "Sure, can you tell me more about the issue?",
            "timestamp": "2025-04-29T09:00:05Z"
        }
    ],
    "url": "id.ee"
}
```

### Response (200 OK)
```json
{
    "chatId": "chat-12345",
    "llmServiceActive": true,
    "questionOutOfLlmScope" : false,
    "inputGuardFailed" : true,
    "content": "This is a random answer payload. \n\n with citations. \n\n References
    - https://gov.ee/sample1,
    - https://gov.ee/sample2"
}
```