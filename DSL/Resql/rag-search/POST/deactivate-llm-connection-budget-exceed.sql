UPDATE llm_connections 
SET 
    connection_status = 'inactive'
WHERE id = :connection_id
RETURNING 
    id,
    connection_name,
    connection_status,
    used_budget,
    stop_budget_threshold,
    disconnect_on_budget_exceed;
