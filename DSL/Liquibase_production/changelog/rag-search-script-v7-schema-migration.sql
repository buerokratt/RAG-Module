-- liquibase formatted sql

-- changeset rag-schema-migration:rag-script-v7-changeset1
CREATE SCHEMA IF NOT EXISTS rag_search;
GRANT USAGE ON SCHEMA rag_search TO PUBLIC;
-- rollback DROP SCHEMA IF EXISTS rag_search;

-- changeset rag-schema-migration:rag-script-v7-changeset2
-- Move RAG module tables from public schema to rag_search schema

-- v1: LLM connection and inference tables
ALTER TABLE IF EXISTS public.llm_connections SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.inference_results SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.inference_results_references SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.llm_platforms SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.llm_models SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.embedding_platforms SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.embedding_models SET SCHEMA rag_search;

-- v2: User management tables
ALTER TABLE IF EXISTS public."user" SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.authority SET SCHEMA rag_search;
ALTER TABLE IF EXISTS public.user_authority SET SCHEMA rag_search;

-- v3: Configuration table
ALTER TABLE IF EXISTS public.configuration SET SCHEMA rag_search;

-- v5: Prompt configuration table
ALTER TABLE IF EXISTS public.prompt_configuration SET SCHEMA rag_search;

-- v6: Endpoints table
ALTER TABLE IF EXISTS public.mock_endpoints SET SCHEMA rag_search;

-- v1: Agency sync table
ALTER TABLE IF EXISTS public.agency_sync SET SCHEMA rag_search;

-- Grant permissions on all tables and sequences in rag_search schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA rag_search TO PUBLIC;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA rag_search TO PUBLIC;

-- rollback ALTER TABLE IF EXISTS rag_search.llm_connections SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.inference_results SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.inference_results_references SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.llm_platforms SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.llm_models SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.embedding_platforms SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.embedding_models SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search."user" SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.authority SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.user_authority SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.configuration SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.prompt_configuration SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.mock_endpoints SET SCHEMA public;
-- rollback ALTER TABLE IF EXISTS rag_search.agency_sync SET SCHEMA public;
-- rollback DROP SCHEMA IF EXISTS rag_search;
