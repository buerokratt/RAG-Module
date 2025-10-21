UPDATE llm_connections 
SET 
    used_budget = used_budget + :usage
WHERE id = :connection_id
RETURNING 
    id,
    connection_name,
    monthly_budget,
    used_budget,
    (monthly_budget - used_budget) AS remaining_budget,
    warn_budget_threshold,
    stop_budget_threshold,
    disconnect_on_budget_exceed,
    connection_status;