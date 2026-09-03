-- Schema for LLM Connections
CREATE TABLE llm_connections (
    -- Metadata
    id SERIAL PRIMARY KEY,
    connection_name VARCHAR(255) NOT NULL DEFAULT '',
    connection_status VARCHAR(50) DEFAULT 'active',      -- active / inactive
    created_at TIMESTAMP DEFAULT NOW(),
    environment VARCHAR(50) NOT NULL,

    -- LLM Model Configuration
    llm_platform VARCHAR(100) NOT NULL,       -- e.g. Azure AI, OpenAI
    llm_model VARCHAR(100) NOT NULL,          -- e.g. GPT-4o
    -- Azure
    deployment_name VARCHAR(150),  -- for Azure deployments
    target_uri TEXT,                -- for custom endpoints
    api_key TEXT,                   -- secured api key mocked here
    -- AWS Bedrock
    secret_key TEXT,
    access_key TEXT, 

    -- Embedding Model Configuration
    embedding_platform VARCHAR(100) NOT NULL, -- e.g. Azure AI, OpenAI
    embedding_model VARCHAR(100) NOT NULL,    -- e.g. Ada-200-1
    -- Azure
    embedding_deployment_name VARCHAR(150),  -- for Azure deployments
    embedding_target_uri TEXT,                -- for custom endpoints
    embedding_azure_api_key TEXT,                   -- secured api key mocked here
    -- AWS Bedrock
    embedding_secret_key TEXT,
    embedding_access_key TEXT,

    -- Budget and Usage Tracking
    monthly_budget NUMERIC(12,2) NOT NULL,    -- e.g. 1000.00
    used_budget NUMERIC(12,2) DEFAULT 0.00,  -- e.g. 250.00
    warn_budget_threshold NUMERIC(5) DEFAULT 80, -- percentage to warn at
    stop_budget_threshold NUMERIC(5) DEFAULT 100, -- percentage to stop at
    disconnect_on_budget_exceed BOOLEAN DEFAULT TRUE
);

CREATE TABLE inference_results (
    id SERIAL PRIMARY KEY,
    llm_connection_id INT REFERENCES llm_connections(id) ON DELETE CASCADE,
    chat_id TEXT,                                 -- optional chat session ID
    user_question TEXT NOT NULL,                  -- raw user input
    refined_questions JSONB,                      -- list of refined questions (LLM-generated)
    conversation_history JSONB,                   -- prior messages (array of {role, content})
    ranked_chunks JSONB,                          -- retrieved chunks (ranked, with metadata)
    embedding_scores JSONB,                       -- distance scores for each chunk
    final_answer TEXT,                            -- LLM’s final generated answer
    environment TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE inference_results_references (
    id SERIAL PRIMARY KEY,
    conversation_id INT NOT NULL REFERENCES inference_results(id) ON DELETE CASCADE,
    reference_url TEXT NOT NULL
);

-- Schema for Platform and Model Management

-- Table for LLM Platforms
CREATE TABLE llm_platforms (
    id SERIAL PRIMARY KEY,
    platform_key VARCHAR(50) NOT NULL UNIQUE,    -- e.g., 'azure', 'aws'
    platform_name VARCHAR(100) NOT NULL        -- e.g., 'Azure OpenAI', 'AWS Bedrock'
);

-- Table for LLM Models
CREATE TABLE llm_models (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES llm_platforms(id) ON DELETE CASCADE,
    model_key VARCHAR(100) NOT NULL,             -- e.g., 'gpt-4o', 'anthropic-claude-3.5-sonnet'
    model_name VARCHAR(150) NOT NULL,            -- e.g., 'GPT-4o', 'Anthropic Claude 3.5 Sonnet'
    UNIQUE(platform_id, model_key)
);

-- Table for Embedding Platforms
CREATE TABLE embedding_platforms (
    id SERIAL PRIMARY KEY,
    platform_key VARCHAR(50) NOT NULL UNIQUE,    -- e.g., 'azure', 'aws'
    platform_name VARCHAR(100) NOT NULL         -- e.g., 'Azure OpenAI', 'AWS Bedrock'
   
);

-- Table for Embedding Models
CREATE TABLE embedding_models (
    id SERIAL PRIMARY KEY,
    platform_id INT NOT NULL REFERENCES embedding_platforms(id) ON DELETE CASCADE,
    model_key VARCHAR(100) NOT NULL,             -- e.g., 'text-embedding-3-large', 'amazon.titan-embed-text-v2:0'
    model_name VARCHAR(150) NOT NULL,            -- e.g., 'text-embedding-3-large', 'Amazon Titan Text Embeddings V2'
    UNIQUE(platform_id, model_key)
);

-- Insert initial LLM platforms
INSERT INTO llm_platforms (platform_key, platform_name) VALUES 
('azure', 'Azure OpenAI'),
('aws', 'AWS Bedrock');

-- Insert initial LLM models
INSERT INTO llm_models (platform_id, model_key, model_name) VALUES 
-- Azure models
((SELECT id FROM llm_platforms WHERE platform_key = 'azure'), 'gpt-4o-mini', 'GPT-4o-mini'),
((SELECT id FROM llm_platforms WHERE platform_key = 'azure'), 'gpt-4o', 'GPT-4o'),
((SELECT id FROM llm_platforms WHERE platform_key = 'azure'), 'gpt-4.1', 'GPT-4.1'),
-- AWS models
((SELECT id FROM llm_platforms WHERE platform_key = 'aws'), 'anthropic-claude-3.5-sonnet', 'Anthropic Claude 3.5 Sonnet'),
((SELECT id FROM llm_platforms WHERE platform_key = 'aws'), 'anthropic-claude-3.7-sonnet', 'Anthropic Claude 3.7 Sonnet');

-- Insert initial embedding platforms
INSERT INTO embedding_platforms (platform_key, platform_name) VALUES 
('azure', 'Azure OpenAI'),
('aws', 'AWS Bedrock');

-- Insert initial embedding models
INSERT INTO embedding_models (platform_id, model_key, model_name) VALUES 
-- Azure embedding models
((SELECT id FROM embedding_platforms WHERE platform_key = 'azure'), 'text-embedding-3-large', 'text-embedding-3-large'),
-- AWS embedding models
((SELECT id FROM embedding_platforms WHERE platform_key = 'aws'), 'amazon.titan-embed-text-v2:0', 'Amazon Titan Text Embeddings V2');

-- Add indexes for better performance
CREATE INDEX idx_llm_models_platform_id ON llm_models(platform_id);
CREATE INDEX idx_embedding_models_platform_id ON embedding_models(platform_id);

CREATE TABLE public.agency_sync (
    id                VARCHAR(50) PRIMARY KEY,
    agency_data_hash  VARCHAR(255),
    data_url          TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO public.agency_sync (id, created_at) VALUES 
('1', NOW());
