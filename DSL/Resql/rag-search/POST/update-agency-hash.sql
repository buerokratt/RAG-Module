UPDATE public.agency_sync 
SET 
    agency_data_hash = :newAgencyDataHash,
    data_url = :dataUrl,
    updated_at = NOW()
WHERE agency_id = :agencyId
RETURNING 
    agency_id,
    agency_data_hash,
    data_url,
    updated_at;
