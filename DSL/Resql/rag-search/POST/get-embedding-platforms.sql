SELECT 
    id,
    platform_key as value,
    platform_name as label
FROM rag_search.embedding_platforms 
ORDER BY platform_name;