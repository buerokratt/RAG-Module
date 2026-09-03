-- Get a specific endpoint by its UUID
-- Used by the indexing pipeline after creation and by the workflow executor

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
WHERE
    endpoint_id = :endpointId::uuid
