SELECT id, key, value
FROM rag_search.configuration
WHERE key=:key
AND id IN (SELECT max(id) from rag_search.configuration GROUP BY key)
AND NOT deleted;
