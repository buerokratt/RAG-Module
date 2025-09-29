UPDATE llm_connections 
SET 
    llm_platform = :llm_platform,
    llm_model = :llm_model,
    embedding_platform = :embedding_platform,
    embedding_model = :embedding_model,
    monthly_budget = :monthly_budget,
    environment = :environment
WHERE id = :connection_id
RETURNING id, llm_platform, llm_model, embedding_platform, embedding_model, monthly_budget, environment, connection_status, created_at;
