SELECT 
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
    -- Azure credentials
    deployment_name,
    target_uri,
    api_key,
    -- AWS Bedrock credentials
    secret_key,
    access_key,
    -- Embedding model credentials
    embedding_model_api_key
FROM llm_connections
WHERE id = :connection_id
  AND connection_status <> 'deleted';
