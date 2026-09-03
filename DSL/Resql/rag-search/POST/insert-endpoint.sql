-- Insert a new API endpoint into the endpoints table
-- Returns the generated endpoint_id for use in indexing pipeline

INSERT INTO rag_search.mock_endpoints (
    service_id,
    name,
    description,
    type,
    visibility,
    method,
    url,
    params
) VALUES (
    NULLIF(:serviceId, '')::uuid,
    :name,
    :description,
    :type,
    :visibility,
    :method,
    :url,
    :params::jsonb
) RETURNING
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
