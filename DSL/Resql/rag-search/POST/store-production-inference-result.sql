INSERT INTO inference_results (
    chat_id,
    user_question,
    refined_questions,
    conversation_history,
    ranked_chunks,
    embedding_scores,
    final_answer,
    environment,
    created_at
) VALUES (
    :chat_id,
    :user_question,
    :refined_questions::JSONB,
    :conversation_history::JSONB,
    :ranked_chunks::JSONB,
    :embedding_scores::JSONB,
    :final_answer,
    :environment,
    :created_at::timestamp with time zone
) RETURNING 
    id, 
    chat_id, 
    user_question, 
    refined_questions, 
    conversation_history, 
    ranked_chunks, 
    embedding_scores, 
    final_answer, 
    environment, 
    created_at;
