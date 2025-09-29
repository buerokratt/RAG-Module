SELECT 
    id,
    llm_platform,
    llm_model,
    embedding_platform,
    embedding_model,
    monthly_budget,
    environment,
    connection_status,
    created_at
FROM llm_connections
WHERE id = :connection_id
  AND connection_status <> 'deleted';
