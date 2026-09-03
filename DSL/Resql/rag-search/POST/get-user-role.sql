SELECT ua.authority_name AS authorities
FROM rag_search."user" u
         INNER JOIN (SELECT authority_name, user_id
                     FROM rag_search.user_authority AS ua
                     WHERE ua.id IN (SELECT max(id)
                                     FROM rag_search.user_authority
                                     GROUP BY user_id)) ua ON u.id_code = ua.user_id
WHERE u.id_code = :userIdCode
  AND status <> 'deleted'
  AND id IN (SELECT max(id) FROM rag_search."user" WHERE id_code = :userIdCode)
