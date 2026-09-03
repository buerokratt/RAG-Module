SELECT 
    em.id,
    em.model_key as value,
    em.model_name as label,
    em.platform_id,
    ep.platform_key,
    ep.platform_name
FROM rag_search.embedding_models em
JOIN rag_search.embedding_platforms ep ON em.platform_id = ep.id
WHERE (:embedding_platform_key IS NULL OR ep.platform_key = :embedding_platform_key)
ORDER BY em.model_name;