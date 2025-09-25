-- Schema for LLM Connections
CREATE TABLE llm_connections (
    id SERIAL PRIMARY KEY,
    
    -- LLM Model Configuration
    llm_platform VARCHAR(100) NOT NULL,       -- e.g. Azure AI, OpenAI
    llm_model VARCHAR(100) NOT NULL,          -- e.g. GPT-4o
    
    -- Embedding Model Configuration
    embedding_platform VARCHAR(100) NOT NULL, -- e.g. Azure AI, OpenAI
    embedding_model VARCHAR(100) NOT NULL,    -- e.g. Ada-200-1
    
    -- Budget and Environment
    monthly_budget NUMERIC(12,2) NOT NULL,    -- e.g. 1000.00
    environment VARCHAR(50) NOT NULL CHECK (environment IN ('Testing', 'Production')),
    
    -- Metadata
    status VARCHAR(50) DEFAULT 'active',      -- active / inactive
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE inference_results (
    id SERIAL PRIMARY KEY,
    llm_connection_id INT NOT NULL REFERENCES llm_connections(id) ON DELETE CASCADE,
    user_question TEXT NOT NULL,                  -- raw user input
    refined_questions JSONB,                      -- list of refined questions (LLM-generated)
    conversation_history JSONB,                   -- prior messages (array of {role, content})
    ranked_chunks JSONB,                          -- retrieved chunks (ranked, with metadata)
    embedding_scores JSONB,                       -- distance scores for each chunk
    final_answer TEXT,                            -- LLM’s final generated answer
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE inference_results_references (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    reference_url TEXT NOT NULL
);