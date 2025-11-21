from typing import Any, Dict, Optional, AsyncIterator
import asyncio
from loguru import logger
from pydantic import BaseModel, Field

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.llm.providers import register_llm_provider
from src.llm_orchestrator_config.llm_cochestrator_constants import (
    GUARDRAILS_BLOCKED_PHRASES,
)
import dspy
import re


class GuardrailCheckResult(BaseModel):
    """Result from a guardrail check."""

    allowed: bool = Field(..., description="Whether the content is allowed")
    verdict: str = Field(..., description="The verdict (safe/unsafe)")
    content: str = Field(default="", description="The processed content")
    reason: Optional[str] = Field(
        default=None, description="Reason if content was blocked"
    )
    error: Optional[str] = Field(default=None, description="Error message if any")
    usage: Dict[str, Any] = Field(
        default_factory=dict, description="Token usage information"
    )


class NeMoRailsAdapter:
    """
    Adapter for NeMo Guardrails with proper streaming support.

    CRITICAL: Uses external async generator pattern for NeMo Guardrails streaming.
    """

    def __init__(
        self,
        environment: str = "production",
        connection_id: Optional[str] = None,
    ) -> None:
        """
        Initialize NeMo Guardrails adapter.

        Args:
            environment: Environment context (production/test/development)
            connection_id: Optional connection identifier
        """
        self.environment = environment
        self.connection_id = connection_id
        self._rails: Optional[LLMRails] = None
        self._initialized = False

        logger.info(f"Initializing NeMoRailsAdapter for environment: {environment}")

    def _register_custom_provider(self) -> None:
        """Register DSPy custom LLM provider with NeMo Guardrails."""
        try:
            from src.guardrails.dspy_nemo_adapter import DSPyLLMProviderFactory

            logger.info("Registering DSPy custom LLM provider with NeMo Guardrails")

            provider_factory = DSPyLLMProviderFactory()

            register_llm_provider("dspy-custom", provider_factory)
            logger.info("DSPy custom LLM provider registered successfully")

        except Exception as e:
            logger.error(f"Failed to register DSPy custom provider: {str(e)}")
            raise

    def _ensure_initialized(self) -> None:
        """Ensure NeMo Guardrails is initialized with proper streaming support."""
        if self._initialized:
            return

        try:
            logger.info(
                "Initializing NeMo Guardrails with DSPy LLM and streaming support"
            )

            from llm_orchestrator_config.llm_manager import LLMManager

            llm_manager = LLMManager(
                environment=self.environment, connection_id=self.connection_id
            )
            llm_manager.ensure_global_config()

            self._register_custom_provider()

            from src.guardrails.optimized_guardrails_loader import (
                get_guardrails_loader,
            )

            guardrails_loader = get_guardrails_loader()
            config_path, metadata = guardrails_loader.get_optimized_config_path()

            logger.info(f"Loading guardrails config from: {config_path}")

            rails_config = RailsConfig.from_path(str(config_path.parent))

            rails_config.streaming = True

            logger.info("Streaming configuration:")
            logger.info(f"  Global streaming: {rails_config.streaming}")

            if hasattr(rails_config, "rails") and hasattr(rails_config.rails, "output"):
                logger.info(
                    f"  Output rails config exists: {rails_config.rails.output}"
                )
            else:
                logger.info("  Output rails config will be loaded from YAML")

            if metadata.get("optimized", False):
                logger.info(
                    f"Loaded OPTIMIZED guardrails config (version: {metadata.get('version', 'unknown')})"
                )
                metrics = metadata.get("metrics", {})
                if metrics:
                    logger.info(
                        f" Optimization metrics: weighted_accuracy={metrics.get('weighted_accuracy', 'N/A')}"
                    )
            else:
                logger.info("Loaded BASE guardrails config (no optimization)")

            from src.guardrails.dspy_nemo_adapter import DSPyNeMoLLM

            dspy_llm = DSPyNeMoLLM()

            self._rails = LLMRails(
                config=rails_config,
                llm=dspy_llm,
                verbose=False,
            )

            if (
                hasattr(self._rails.config, "streaming")
                and self._rails.config.streaming
            ):
                logger.info("Streaming enabled in NeMo Guardrails configuration")
            else:
                logger.warning(
                    "Streaming not enabled in configuration - this may cause issues"
                )

            self._initialized = True
            logger.info("NeMo Guardrails initialized successfully with DSPy LLM")

        except Exception as e:
            logger.error(f"Failed to initialize NeMo Guardrails: {str(e)}")
            logger.exception("Full traceback:")
            raise

    async def check_input_async(self, user_message: str) -> GuardrailCheckResult:
        """
        Check user input against guardrails (async version for streaming).

        Args:
            user_message: The user message to check

        Returns:
            GuardrailCheckResult: Result of the guardrail check
        """
        self._ensure_initialized()

        if not self._rails:
            logger.error("Rails not initialized")
            raise RuntimeError("NeMo Guardrails not initialized")

        logger.debug(f"Checking input guardrails (async) for: {user_message[:100]}...")

        lm = dspy.settings.lm
        history_length_before = len(lm.history) if lm and hasattr(lm, "history") else 0

        try:
            response = await self._rails.generate_async(
                messages=[{"role": "user", "content": user_message}]
            )

            from src.utils.cost_utils import get_lm_usage_since

            usage_info = get_lm_usage_since(history_length_before)

            content = response.get("content", "")
            allowed = not self._is_input_blocked(content, user_message)

            if allowed:
                logger.info(
                    f"Input check PASSED - cost: ${usage_info.get('total_cost', 0):.6f}"
                )
                return GuardrailCheckResult(
                    allowed=True,
                    verdict="safe",
                    content=user_message,
                    usage=usage_info,
                )
            else:
                logger.warning(f"Input check FAILED - blocked: {content}")
                return GuardrailCheckResult(
                    allowed=False,
                    verdict="unsafe",
                    content=content,
                    reason="Input violated safety policies",
                    usage=usage_info,
                )

        except Exception as e:
            logger.error(f"Input guardrail check failed: {str(e)}")
            logger.exception("Full traceback:")
            return GuardrailCheckResult(
                allowed=False,
                verdict="error",
                content="",
                error=str(e),
                usage={},
            )

    def _is_input_blocked(self, response: str, original: str) -> bool:
        """Check if input was blocked by guardrails."""

        blocked_phrases = GUARDRAILS_BLOCKED_PHRASES
        response_normalized = response.strip().lower()
        # Match if the response is exactly or almost exactly a blocked phrase (allow trailing punctuation/whitespace)
        for phrase in blocked_phrases:
            # Regex: phrase followed by optional punctuation/whitespace, and nothing else
            pattern = r"^" + re.escape(phrase) + r"[\s\.,!]*$"
            if re.match(pattern, response_normalized):
                return True
        return False

    async def stream_with_guardrails(
        self,
        user_message: str,
        bot_message_generator: AsyncIterator[str],
    ) -> AsyncIterator[str]:
        """
        Stream bot response through NeMo Guardrails with validation-first approach.

        This properly implements NeMo's external generator pattern for streaming.
        NeMo will buffer tokens (chunk_size=200) and validate before yielding.

        Args:
            user_message: The user's input message (for context)
            bot_message_generator: Async generator yielding bot response tokens

        Yields:
            Validated token strings from NeMo Guardrails

        Raises:
            RuntimeError: If streaming fails
        """
        try:
            self._ensure_initialized()

            if not self._rails:
                logger.error("Rails not initialized in stream_with_guardrails")
                raise RuntimeError("NeMo Guardrails not initialized")

            logger.info(
                f"Starting NeMo stream_async with external generator - "
                f"user_message: {user_message[:100]}"
            )

            messages = [{"role": "user", "content": user_message}]

            logger.debug(f"Messages for NeMo: {messages}")
            logger.debug(f"Generator type: {type(bot_message_generator)}")

            chunk_count = 0

            logger.info("Calling _rails.stream_async with generator parameter...")

            async for chunk in self._rails.stream_async(
                messages=messages,
                generator=bot_message_generator,
            ):
                chunk_count += 1

                if chunk_count <= 10:
                    logger.debug(
                        f"[Chunk {chunk_count}] Validated and yielded: {repr(chunk)}"
                    )

                yield chunk

            logger.info(
                f"NeMo streaming completed successfully - {chunk_count} chunks streamed"
            )

        except Exception as e:
            logger.error(f"Error in stream_with_guardrails: {str(e)}")
            logger.exception("Full traceback:")
            raise RuntimeError(f"Streaming with guardrails failed: {str(e)}") from e

    def check_input(self, user_message: str) -> GuardrailCheckResult:
        """
        Check user input against guardrails (sync version).

        Args:
            user_message: The user message to check

        Returns:
            GuardrailCheckResult: Result of the guardrail check
        """
        return asyncio.run(self.check_input_async(user_message))

    def check_output(self, assistant_message: str) -> GuardrailCheckResult:
        """
        Check assistant output against guardrails (sync version).

        Args:
            assistant_message: The assistant message to check

        Returns:
            GuardrailCheckResult: Result of the guardrail check
        """
        self._ensure_initialized()

        if not self._rails:
            logger.error("Rails not initialized")
            raise RuntimeError("NeMo Guardrails not initialized")

        logger.debug(f"Checking output guardrails for: {assistant_message[:100]}...")

        lm = dspy.settings.lm
        history_length_before = len(lm.history) if lm and hasattr(lm, "history") else 0

        try:
            response = self._rails.generate(
                messages=[
                    {"role": "user", "content": "Please respond"},
                    {"role": "assistant", "content": assistant_message},
                ]
            )

            from src.utils.cost_utils import get_lm_usage_since

            usage_info = get_lm_usage_since(history_length_before)

            final_content = response.get("content", "")
            allowed = final_content == assistant_message

            if allowed:
                logger.info(
                    f"Output check PASSED - cost: ${usage_info.get('total_cost', 0):.6f}"
                )
                return GuardrailCheckResult(
                    allowed=True,
                    verdict="safe",
                    content=assistant_message,
                    usage=usage_info,
                )
            else:
                logger.warning(
                    f"Output check FAILED - modified from: {assistant_message[:100]}... to: {final_content[:100]}..."
                )
                return GuardrailCheckResult(
                    allowed=False,
                    verdict="unsafe",
                    content=final_content,
                    reason="Output violated safety policies",
                    usage=usage_info,
                )

        except Exception as e:
            logger.error(f"Output guardrail check failed: {str(e)}")
            logger.exception("Full traceback:")
            return GuardrailCheckResult(
                allowed=False,
                verdict="error",
                content="",
                error=str(e),
                usage={},
            )
