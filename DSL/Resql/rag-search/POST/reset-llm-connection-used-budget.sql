UPDATE rag_search.llm_connections 
SET 
    used_budget = 0.00
WHERE connection_status <> 'deleted'
RETURNING 
    id,
    connection_name,
    monthly_budget,
    used_budget,
    (monthly_budget - used_budget) AS remaining_budget,
    warn_budget_threshold,
    stop_budget_threshold,
    disconnect_on_budget_exceed;
