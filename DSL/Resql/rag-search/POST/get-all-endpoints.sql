-- Get all endpoints
-- Used by the API Tool indexing pipeline to bulk-index all endpoints into Qdrant

SELECT
    endpoint_id,
    service_id,
    name,
    description,
    type,
    visibility,
    method,
    url,
    params,
    created_at,
    updated_at
FROM
    rag_search.mock_endpoints
ORDER BY
    created_at ASC
