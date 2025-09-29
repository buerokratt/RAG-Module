from __future__ import annotations
from typing import List, Dict, Any, Tuple, Optional
import json
import re
import dspy
import logging
from langfuse import observe

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HumanizeRAGSig(dspy.Signature):
    """Produce a grounded answer from the provided context ONLY.

    OUTPUT STRICTLY AS COMPACT JSON:
    {
      "answer": string,                     # human-friendly answer without citations
      # (no citations in answer; they are in separate field)
      "questionOutOfLLMScope": boolean      # true if context insufficient to answer
    }

    Rules:
    - Use ONLY the provided context blocks; do not invent facts.
    - If the context is insufficient, set questionOutOfLLMScope=true and say so briefly.
    - Do not reference context blocks that do not support your answer.
    - Keep the answer concise and clear; bullets are fine.
    - Respond in JSON only (no extra prose).
    """

    question = dspy.InputField()
    context_blocks = dspy.InputField()
    citations = dspy.InputField()
    answer_json = dspy.OutputField(
        desc="A JSON object string with keys: answer, questionOutOfLLMScope."
    )


def build_context_and_citations(
    chunks: List[Dict[str, Any]], use_top_k: int = 10
) -> Tuple[List[str], List[str], bool]:
    """
    Turn retriever chunks -> numbered context blocks and source labels.
    Returns (blocks, labels, has_real_context).
    """
    logger.info(f"Building context from {len(chunks)} chunks (top_k={use_top_k}).")
    blocks: List[str] = []
    labels: List[str] = []
    for i, ch in enumerate(chunks[:use_top_k]):
        text = (ch.get("text") or "").strip()
        meta: Dict[str, Any] = ch.get("meta") or {}
        source_file = meta.get("source_file")
        source = meta.get("source")
        label = source_file or source or f"Chunk-{i + 1}"
        if text:
            blocks.append(f"[Context {i + 1}]\n{text}")
            labels.append(str(label))

    has_real_context = len(blocks) > 0
    if not has_real_context:
        blocks = ["[Context 1]\n(No relevant context available.)"]
        labels = ["No source"]
    logger.info(
        f"Created {len(blocks)} context blocks. Has real context: {has_real_context}."
    )
    return blocks, labels, has_real_context


def _safe_parse_json(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s)
    except Exception as e:
        logger.warning(f"Failed to parse JSON: {e}. Raw string: '{s}...'")
        return {}


def _should_flag_out_of_scope(
    answer_text: str, has_real_context: bool, require_citation_marker: bool = False
) -> bool:
    """
    Heuristics to decide out-of-scope when model output is ambiguous:
    - No real context was supplied
    - Very short or empty answer
    - (Optional) No citation markers like [1], [2] present if require_citation_marker is True
    Args:
        answer_text: The answer string to check.
        has_real_context: Whether real context was supplied.
        require_citation_marker: If True, require at least one [n] citation marker.
    """
    if not has_real_context:
        return True
    if not answer_text.strip():
        return True
    if require_citation_marker:
        # Look for at least one numeric citation [n]
        if not re.search(r"\[\d+\]", answer_text):
            # If no explicit citations, treat as possibly out-of-scope
            return True
    return False


def _extract_usage_from_dspy_history() -> Optional[Dict[str, Any]]:
    """
    Extract token usage from DSPy's call history.
    DSPy tracks LLM calls and their metadata in dspy.settings.
    """
    try:
        # Access DSPy's internal history if available
        if hasattr(dspy.settings, 'lm') and hasattr(dspy.settings.lm, 'history'):
            # Get the most recent call from history
            history = dspy.settings.lm.history
            if history and len(history) > 0:
                last_call = history[-1]
                
                # Different LLM providers store usage differently
                # OpenAI-style usage
                if hasattr(last_call, 'response') and hasattr(last_call.response, 'usage'):
                    usage = last_call.response.usage
                    return {
                        "input_tokens": getattr(usage, 'prompt_tokens', 0),
                        "output_tokens": getattr(usage, 'completion_tokens', 0),
                        "total_tokens": getattr(usage, 'total_tokens', 0)
                    }
                
                # Alternative: check for usage in response metadata
                if hasattr(last_call, 'kwargs') and 'usage' in last_call.kwargs:
                    usage = last_call.kwargs['usage']
                    return {
                        "input_tokens": usage.get('prompt_tokens', 0),
                        "output_tokens": usage.get('completion_tokens', 0),
                        "total_tokens": usage.get('total_tokens', 0)
                    }
                
                # Try to extract from response object directly
                if hasattr(last_call, 'response'):
                    response = last_call.response
                    if hasattr(response, 'usage'):
                        usage = response.usage
                        if hasattr(usage, '__dict__'):
                            usage_dict = usage.__dict__
                            return {
                                "input_tokens": usage_dict.get('prompt_tokens', 0),
                                "output_tokens": usage_dict.get('completion_tokens', 0),
                                "total_tokens": usage_dict.get('total_tokens', 0)
                            }
                
        # Alternative approach: check if LLM adapter has usage tracking
        if hasattr(dspy.settings, 'lm') and hasattr(dspy.settings.lm, 'get_usage'):
            return dspy.settings.lm.get_usage()
            
    except Exception as e:
        logger.debug(f"Could not extract usage from DSPy: {e}")
    
    return None


def _get_model_name_from_dspy() -> Optional[str]:
    """Extract the model name from DSPy settings."""
    try:
        if hasattr(dspy.settings, 'lm'):
            lm = dspy.settings.lm
            # Different LLM adapters store model name differently
            if hasattr(lm, 'model'):
                return lm.model
            elif hasattr(lm, 'model_name'):
                return lm.model_name
            elif hasattr(lm, '_model'):
                return lm._model
            elif hasattr(lm, 'kwargs') and 'model' in lm.kwargs:
                return lm.kwargs['model']
    except Exception as e:
        logger.debug(f"Could not extract model name from DSPy: {e}")
    return None


class ResponseGeneratorAgent(dspy.Module):
    """
    Creates a grounded, humanized answer from retrieved chunks.
    Returns a dict: {"answer": str, "questionOutOfLLMScope": bool, "usage": dict, "model": str}
    """

    def __init__(self) -> None:
        super().__init__()
        self._predictor = dspy.Predict(HumanizeRAGSig)

    @observe(
        name="response_generation_internal",
        as_type="generation",
        capture_input=True,
        capture_output=True
    )
    def forward(
        self, question: str, chunks: List[Dict[str, Any]], max_blocks: int = 10
    ) -> Dict[str, Any]:
        logger.info(f"Generating response for question: '{question}...'")
        context_blocks, citation_labels, has_real_context = build_context_and_citations(
            chunks, use_top_k=max_blocks
        )

        # Make the LLM call
        result = self._predictor(
            question=question, context_blocks=context_blocks, citations=citation_labels
        )

        # Extract usage information from DSPy
        usage_info = _extract_usage_from_dspy_history()
        model_name = _get_model_name_from_dspy()

        raw = getattr(result, "answer_json", "") or ""
        parsed = _safe_parse_json(raw)
        logger.info(f"LLM raw output: {raw}")

        # If model returned valid JSON with required keys, trust it (with a safety fallback)
        if "answer" in parsed and "questionOutOfLLMScope" in parsed:
            # Validate types
            ans = parsed.get("answer")
            scope = parsed.get("questionOutOfLLMScope")
            if not isinstance(ans, str):
                ans = "" if ans is None else str(ans)
            if not isinstance(scope, bool):
                scope = _should_flag_out_of_scope(ans, has_real_context)
            # If model claims in-scope but our heuristics disagree (e.g., no citations), flip to True
            if scope is False and _should_flag_out_of_scope(ans, has_real_context):
                scope = True
                logger.warning("Flipping out-of-scope to True based on heuristics.")

            logger.info(f"Successfully parsed LLM response. Out of scope: {scope}.")

            response: dict[str, Any] = {
                "answer": ans.strip(),
                "questionOutOfLLMScope": scope
            }
            
            # Add usage and model information if available
            if usage_info:
                response["usage"] = usage_info
                logger.info(f"Token usage: {usage_info}")
            
            if model_name:
                response["model"] = model_name
                logger.info(f"Model used: {model_name}")
            
            return response

        # Fallbacks if parsing failed or structure wrong
        logger.warning(
            "Failed to parse LLM response or structure was incorrect. Using fallback."
        )
        # Try to use the raw string as the answer
        fallback_answer = raw.strip() if isinstance(raw, str) else ""
        scope_flag = _should_flag_out_of_scope(fallback_answer, has_real_context)
        if not fallback_answer:
            fallback_answer = (
                "I don't have enough grounded information in the provided context to answer. "
                "Please provide more details or additional sources."
            )
            scope_flag = True
            logger.warning(
                "Fallback answer is empty; using default out-of-scope message."
            )

        response = {
            "answer": fallback_answer, 
            "questionOutOfLLMScope": scope_flag
        }
        
        # Add usage and model information if available
        if usage_info:
            response["usage"] = usage_info
        
        if model_name:
            response["model"] = model_name
            
        return response