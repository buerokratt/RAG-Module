SELECT 
    lm.id,
    lm.model_key as value,
    lm.model_name as label,
    lm.platform_id,
    lp.platform_key,
    lp.platform_name
FROM rag_search.llm_models lm
JOIN rag_search.llm_platforms lp ON lm.platform_id = lp.id
AND (:platform_key IS NULL OR lp.platform_key = :platform_key)
ORDER BY lm.model_name;