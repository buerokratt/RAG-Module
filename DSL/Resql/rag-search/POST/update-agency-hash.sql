UPDATE rag_search.agency_sync 
SET 
    agency_data_hash = :newAgencyDataHash,
    data_url = :dataUrl,
    updated_at = NOW()
WHERE id = :id
RETURNING 
    id,
    agency_data_hash,
    data_url,
    updated_at;
