INSERT INTO rag_search.prompt_configuration (prompt)
VALUES (:prompt)
RETURNING id, prompt
