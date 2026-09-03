WITH active_administrators AS (SELECT user_id
                               FROM rag_search.user_authority
                               WHERE 'ROLE_ADMINISTRATOR' = ANY (authority_name)
                                 AND id IN (SELECT max(id)
                                            FROM rag_search.user_authority
                                            GROUP BY user_id)),
delete_user AS (
INSERT
INTO rag_search."user" (login, password_hash, first_name, last_name, id_code, display_name, status, created, csa_title, csa_email)
SELECT login,
       password_hash,
       first_name,
       last_name,
       id_code,
       display_name,
       'deleted',
       :created::timestamp with time zone,
       csa_title,
       csa_email
FROM rag_search."user"
WHERE id_code = :userIdCode
  AND status <> 'deleted'
  AND id IN (SELECT max(id) FROM rag_search."user" WHERE id_code = :userIdCode)
  AND (1 < (SELECT COUNT(user_id) FROM active_administrators)
    OR (1 = (SELECT COUNT(user_id) FROM active_administrators)
        AND :userIdCode NOT IN (SELECT user_id FROM active_administrators)))),
delete_authority AS (
INSERT
INTO rag_search.user_authority (user_id, authority_name, created)
SELECT :userIdCode as users, ARRAY []::varchar[], :created::timestamp with time zone
FROM rag_search.user_authority
WHERE 1 < (SELECT COUNT(user_id) FROM active_administrators)
   OR (1 = (SELECT COUNT(user_id) FROM active_administrators)
    AND :userIdCode NOT IN (SELECT user_id FROM active_administrators))
GROUP BY users)
SELECT max(status) FROM rag_search."user" WHERE id_code = :userIdCode;
