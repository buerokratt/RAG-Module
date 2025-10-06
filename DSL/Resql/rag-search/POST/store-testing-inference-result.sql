INSERT INTO inference_results (
    llm_connection_id,
    user_question,
    final_answer,
    environment,
    created_at
) VALUES (
    :llm_connection_id,
    :user_question,
    :final_answer,
    :environment,
    :created_at::timestamp with time zone
) RETURNING id, llm_connection_id, user_question, final_answer, environment, created_at;
