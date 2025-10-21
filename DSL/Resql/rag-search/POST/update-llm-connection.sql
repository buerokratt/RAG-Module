UPDATE llm_connections 
SET 
    connection_name = :connection_name,
    llm_platform = :llm_platform,
    llm_model = :llm_model,
    embedding_platform = :embedding_platform,
    embedding_model = :embedding_model,
    monthly_budget = :monthly_budget,
    warn_budget_threshold = :warn_budget_threshold,
    stop_budget_threshold = :stop_budget_threshold,
    disconnect_on_budget_exceed = :disconnect_on_budget_exceed,
    environment = :environment,
    -- Azure credentials
    deployment_name = :deployment_name,
    target_uri = :target_uri,
    api_key = :api_key,
    -- AWS Bedrock credentials
    secret_key = :secret_key,
    access_key = :access_key,
    -- Embedding model credentials
    embedding_model_api_key = :embedding_model_api_key
WHERE id = :connection_id
RETURNING 
    id, 
    connection_name,
    llm_platform, 
    llm_model, 
    embedding_platform, 
    embedding_model, 
    monthly_budget, 
    warn_budget_threshold,
    stop_budget_threshold,
    disconnect_on_budget_exceed,
    environment, 
    connection_status, 
    created_at,
    deployment_name,
    target_uri,
    api_key,
    secret_key,
    access_key,
    embedding_model_api_key;
