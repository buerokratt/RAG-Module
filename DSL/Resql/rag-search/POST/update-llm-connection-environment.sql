UPDATE llm_connections 
SET 
    environment = :environment
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
