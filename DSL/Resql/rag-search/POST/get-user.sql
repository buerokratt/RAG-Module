SELECT id_code
FROM rag_search."user"
WHERE id_code = :userIdCode
  AND status <> 'deleted'
  AND id IN (SELECT max(id) FROM rag_search."user" WHERE id_code = :userIdCode)