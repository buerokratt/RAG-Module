INSERT INTO llm_connections (
    llm_platform,
    llm_model,
    embedding_platform,
    embedding_model,
    monthly_budget,
    environment,
    connection_status,
    created_at
) VALUES (
    :llm_platform,
    :llm_model,
    :embedding_platform,
    :embedding_model,
    :monthly_budget,
    :environment,
    :connection_status,
    :created_at::timestamp with time zone
);
