from __future__ import annotations
from typing import List, Dict, Any, Tuple
import re
import dspy
import logging

from src.llm_orchestrator_config.llm_cochestrator_constants import OUT_OF_SCOPE_MESSAGE
from src.utils.cost_utils import get_lm_usage_since

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ResponseGenerator(dspy.Signature):
    """Produce a grounded answer from the provided context ONLY.

    Rules:
    - Use ONLY the provided context blocks; do not invent facts.
    - If the context is insufficient, set questionOutOfLLMScope=true and say so briefly.
    - Do not include citations in the 'answer' field.
    """

    question: str = dspy.InputField()
    context_blocks: List[str] = dspy.InputField()
    citations: List[str] = dspy.InputField()
    answer: str = dspy.OutputField(desc="Human-friendly answer without citations")
    questionOutOfLLMScope: bool = dspy.OutputField(
        desc="True if context is insufficient to answer"
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


def _should_flag_out_of_scope(
    answer_text: str, has_real_context: bool, require_citation_marker: bool = False
) -> bool:
    """
    Heuristics to decide out-of-scope when model output is ambiguous:
    - No real context was supplied
    - Very short or empty answer
    - (Optional) No citation markers like [1], [2] present if require_citation_marker is True
    """
    if not has_real_context:
        return True
    if not (answer_text or "").strip():
        return True
    if require_citation_marker and not re.search(r"\[\d+\]", answer_text or ""):
        return True
    return False


class ResponseGeneratorAgent(dspy.Module):
    """
    Creates a grounded, humanized answer from retrieved chunks.
    Returns a dict: {"answer": str, "questionOutOfLLMScope": bool, "usage": dict}
    """

    def __init__(self, max_retries: int = 2) -> None:
        super().__init__()
        self._predictor = dspy.Predict(ResponseGenerator)
        self._max_retries = max(0, int(max_retries))

    def _predict_once(
        self, question: str, context_blocks: List[str], citation_labels: List[str]
    ) -> dspy.Prediction:
        """Single LM call. Returns Prediction object."""
        result = self._predictor(
            question=question, context_blocks=context_blocks, citations=citation_labels
        )
        logger.info(f"LLM output - answer: {getattr(result, 'answer', '')[:200]}...")
        logger.info(
            f"LLM output - out_of_scope: {getattr(result, 'questionOutOfLLMScope', None)}"
        )
        return result

    def _validate_prediction(self, pred: dspy.Prediction) -> bool:
        """Validate that prediction has required fields with correct types."""
        try:
            answer = getattr(pred, "answer", None)
            out_of_scope = getattr(pred, "questionOutOfLLMScope", None)

            if not isinstance(answer, str):
                return False
            if not isinstance(out_of_scope, bool):
                return False
            return True
        except Exception as e:
            logger.warning(f"Validation failed: {e}")
            return False

    def forward(
        self, question: str, chunks: List[Dict[str, Any]], max_blocks: int = 10
    ) -> Dict[str, Any]:
        logger.info(f"Generating response for question: '{question}...'")

        # Record history length before operation
        lm = dspy.settings.lm
        history_length_before = len(lm.history) if lm and hasattr(lm, "history") else 0

        context_blocks, citation_labels, has_real_context = build_context_and_citations(
            chunks, use_top_k=max_blocks
        )

        # First attempt
        pred = self._predict_once(question, context_blocks, citation_labels)
        valid = self._validate_prediction(pred)

        # Retry logic if validation fails
        attempts = 0
        while not valid and attempts < self._max_retries:
            attempts += 1
            logger.warning(f"Retry attempt {attempts}/{self._max_retries}")

            # Re-invoke with fresh rollout to avoid cache
            pred = self._predictor(
                question=question,
                context_blocks=context_blocks,
                citations=citation_labels,
                config={"rollout_id": attempts, "temperature": 0.1},
            )
            valid = self._validate_prediction(pred)

        # Extract usage using centralized utility
        usage_info = get_lm_usage_since(history_length_before)

        # If still invalid after retries, apply fallback
        if not valid:
            logger.warning(
                "Failed to obtain valid prediction after retries. Using fallback."
            )
            answer = getattr(pred, "answer", "")
            if not isinstance(answer, str):
                answer = str(answer) if answer else ""

            scope_flag = _should_flag_out_of_scope(answer, has_real_context)
            if not answer or scope_flag:
                answer = OUT_OF_SCOPE_MESSAGE
                scope_flag = True

            return {
                "answer": answer,
                "questionOutOfLLMScope": scope_flag,
                "usage": usage_info,
            }

        # Valid prediction with required fields
        ans: str = getattr(pred, "answer", "")
        scope: bool = bool(getattr(pred, "questionOutOfLLMScope", False))

        # Final sanity check: if scope is False but heuristics say it's out-of-scope, flip it
        if scope is False and _should_flag_out_of_scope(ans, has_real_context):
            logger.warning("Flipping out-of-scope to True based on heuristics.")
            scope = True

        return {
            "answer": ans.strip(),
            "questionOutOfLLMScope": scope,
            "usage": usage_info,
        }
