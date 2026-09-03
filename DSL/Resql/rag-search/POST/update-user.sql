INSERT INTO rag_search."user" (id_code, login, password_hash, first_name, last_name, display_name, status, created, csa_title, csa_email)
SELECT
  :userIdCode,
  login,
  password_hash,
  :firstName,
  :lastName,
  :displayName,
  :status::user_status,
  :created::timestamp with time zone,
  :csaTitle,
  :csaEmail
FROM rag_search."user"
WHERE id = (
  SELECT MAX(id) FROM rag_search."user" WHERE id_code = :userIdCode
);
