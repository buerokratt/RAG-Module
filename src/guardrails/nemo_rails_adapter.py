"""
Improved NeMo Guardrails Adapter with robust type checking and cost tracking.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List, Tuple, Union
from pydantic import BaseModel, Field
import dspy

from nemoguardrails import RailsConfig, LLMRails
from nemoguardrails.llm.providers import register_llm_provider
from loguru import logger

from src.guardrails.dspy_nemo_adapter import DSPyNeMoLLM
from src.guardrails.rails_config import RAILS_CONFIG_PATH
from src.llm_orchestrator_config.llm_manager import LLMManager
from src.utils.cost_utils import get_lm_usage_since


class GuardrailCheckResult(BaseModel):
    """Result of a guardrail check operation."""

    allowed: bool = Field(description="Whether the content is allowed")
    verdict: str = Field(description="'yes' if blocked, 'no' if allowed")
    content: str = Field(description="Response content from guardrail")
    blocked_by_rail: Optional[str] = Field(
        default=None, description="Which rail blocked the content"
    )
    reason: Optional[str] = Field(
        default=None, description="Optional reason for decision"
    )
    error: Optional[str] = Field(default=None, description="Optional error message")
    usage: Dict[str, Union[float, int]] = Field(
        default_factory=dict, description="Token usage and cost information"
    )


class NeMoRailsAdapter:
    """
    Production-ready adapter for NeMo Guardrails with DSPy LLM integration.

    Features:
    - Robust type checking and error handling
    - Cost and token usage tracking
    - Native NeMo blocking detection
    - Lazy initialization for performance
    """

    def __init__(self, environment: str, connection_id: Optional[str] = None) -> None:
        """
        Initialize the NeMo Rails adapter.

        Args:
            environment: Environment context (production/test/development)
            connection_id: Optional connection identifier for Vault integration
        """
        self.environment: str = environment
        self.connection_id: Optional[str] = connection_id
        self._rails: Optional[LLMRails] = None
        self._manager: Optional[LLMManager] = None
        self._provider_registered: bool = False
        logger.info(f"Initializing NeMoRailsAdapter for environment: {environment}")

    def _register_custom_provider(self) -> None:
        """Register the custom DSPy LLM provider with NeMo Guardrails."""
        if not self._provider_registered:
            logger.info("Registering DSPy custom LLM provider with NeMo Guardrails")
            try:
                register_llm_provider("dspy_custom", DSPyNeMoLLM)
                self._provider_registered = True
                logger.info("DSPy custom LLM provider registered successfully")
            except Exception as e:
                logger.error(f"Failed to register custom provider: {str(e)}")
                raise RuntimeError(f"Provider registration failed: {str(e)}") from e

    def _ensure_initialized(self) -> None:
        """
        Lazy initialization of NeMo Rails with DSPy LLM.

        Raises:
            RuntimeError: If initialization fails
        """
        if self._rails is not None:
            return

        try:
            logger.info("Initializing NeMo Guardrails with DSPy LLM")

            # Step 1: Initialize LLM Manager with Vault integration
            self._manager = LLMManager(
                environment=self.environment, connection_id=self.connection_id
            )
            self._manager.ensure_global_config()

            # Step 2: Register custom LLM provider
            self._register_custom_provider()

            # Step 3: Load rails configuration from YAML file
            try:
                if not RAILS_CONFIG_PATH.exists():
                    raise FileNotFoundError(
                        f"Rails config file not found: {RAILS_CONFIG_PATH}"
                    )

                rails_config = RailsConfig.from_path(str(RAILS_CONFIG_PATH))
                logger.info(f"Loaded rails config from: {RAILS_CONFIG_PATH}")
            except Exception as yaml_error:
                logger.error(
                    f"Failed to load Rails YAML configuration: {str(yaml_error)}"
                )
                raise RuntimeError(
                    f"Rails YAML configuration error: {str(yaml_error)}"
                ) from yaml_error

            # Step 4: Initialize LLMRails with custom DSPy LLM
            self._rails = LLMRails(config=rails_config, llm=DSPyNeMoLLM())

            logger.info("NeMo Guardrails initialized successfully with DSPy LLM")

        except Exception as e:
            logger.error(f"Failed to initialize NeMo Guardrails: {str(e)}")
            raise RuntimeError(
                f"NeMo Guardrails initialization failed: {str(e)}"
            ) from e

    def check_input(self, user_message: str) -> GuardrailCheckResult:
        """
        Check user input against input guardrails with usage tracking.

        Args:
            user_message: The user's input message to check

        Returns:
            GuardrailCheckResult with decision, metadata, and usage info
        """
        self._ensure_initialized()

        # Record history length before guardrail check
        lm = dspy.settings.lm
        history_length_before = len(lm.history) if lm and hasattr(lm, "history") else 0

        try:
            logger.debug(f"Checking input guardrails for: {user_message[:100]}...")

            # Use NeMo's generate API with input rails enabled
            response = self._rails.generate(
                messages=[{"role": "user", "content": user_message}]
            )

            # Extract usage information
            usage_info = get_lm_usage_since(history_length_before)

            # Check if NeMo blocked the content
            is_blocked, block_info = self._check_if_blocked(response)

            if is_blocked:
                logger.warning(
                    f"Input BLOCKED by guardrail: {block_info.get('rail', 'unknown')}"
                )
                return GuardrailCheckResult(
                    allowed=False,
                    verdict="yes",
                    content=block_info.get("message", "Input blocked by guardrails"),
                    blocked_by_rail=block_info.get("rail"),
                    reason=block_info.get("reason"),
                    usage=usage_info,
                )

            # Extract normal response content
            content = self._extract_content(response)

            result = GuardrailCheckResult(
                allowed=True,
                verdict="no",
                content=content,
                usage=usage_info,
            )

            logger.info(
                f"Input check PASSED - cost: ${usage_info.get('total_cost', 0):.6f}"
            )
            return result

        except Exception as e:
            logger.error(f"Error checking input guardrails: {str(e)}")
            # Extract usage even on error
            usage_info = get_lm_usage_since(history_length_before)
            # On error, be conservative and block
            return GuardrailCheckResult(
                allowed=False,
                verdict="yes",
                content="Error during guardrail check",
                error=str(e),
                usage=usage_info,
            )

    def check_output(self, assistant_message: str) -> GuardrailCheckResult:
        """
        Check assistant output against output guardrails with usage tracking.

        Args:
            assistant_message: The assistant's response to check

        Returns:
            GuardrailCheckResult with decision, metadata, and usage info
        """
        self._ensure_initialized()

        # Record history length before guardrail check
        lm = dspy.settings.lm
        history_length_before = len(lm.history) if lm and hasattr(lm, "history") else 0

        try:
            logger.debug(
                f"Checking output guardrails for: {assistant_message[:100]}..."
            )

            # Use NeMo's generate API with output rails enabled
            response = self._rails.generate(
                messages=[
                    {"role": "user", "content": "test query"},
                    {"role": "assistant", "content": assistant_message},
                ]
            )

            # Extract usage information
            usage_info = get_lm_usage_since(history_length_before)

            # Check if NeMo blocked the content
            is_blocked, block_info = self._check_if_blocked(response)

            if is_blocked:
                logger.warning(
                    f"Output BLOCKED by guardrail: {block_info.get('rail', 'unknown')}"
                )
                return GuardrailCheckResult(
                    allowed=False,
                    verdict="yes",
                    content=block_info.get("message", "Output blocked by guardrails"),
                    blocked_by_rail=block_info.get("rail"),
                    reason=block_info.get("reason"),
                    usage=usage_info,
                )

            # Extract normal response content
            content = self._extract_content(response)

            result = GuardrailCheckResult(
                allowed=True,
                verdict="no",
                content=content,
                usage=usage_info,
            )

            logger.info(
                f"Output check PASSED - cost: ${usage_info.get('total_cost', 0):.6f}"
            )
            return result

        except Exception as e:
            logger.error(f"Error checking output guardrails: {str(e)}")
            # Extract usage even on error
            usage_info = get_lm_usage_since(history_length_before)
            # On error, be conservative and block
            return GuardrailCheckResult(
                allowed=False,
                verdict="yes",
                content="Error during guardrail check",
                error=str(e),
                usage=usage_info,
            )

    def _check_if_blocked(
        self, response: Union[Dict[str, Any], List[Dict[str, Any]], Any]
    ) -> Tuple[bool, Dict[str, str]]:
        """
        Check if NeMo Guardrails blocked the content.

        Args:
            response: Response from NeMo Guardrails

        Returns:
            Tuple of (is_blocked: bool, block_info: dict)
        """
        # Check for exception format (most reliable)
        exception_info = self._check_exception_format(response)
        if exception_info:
            return True, exception_info

        # Fallback detection (use only if exception format not available)
        fallback_info = self._check_fallback_patterns(response)
        if fallback_info:
            return True, fallback_info

        return False, {}

    def _check_exception_format(
        self, response: Union[Dict[str, Any], List[Dict[str, Any]], Any]
    ) -> Optional[Dict[str, str]]:
        """
        Check for exception format in response.

        Args:
            response: Response from NeMo Guardrails

        Returns:
            Block info dict if exception found, None otherwise
        """
        # Check dict format
        if isinstance(response, dict):
            exception_info = self._extract_exception_info(response)
            if exception_info:
                return exception_info

        # Check list format
        if isinstance(response, list):
            for msg in response:
                if isinstance(msg, dict):
                    exception_info = self._extract_exception_info(msg)
                    if exception_info:
                        return exception_info

        return None

    def _extract_exception_info(self, msg: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Extract exception information from a message dict.

        Args:
            msg: Message dictionary

        Returns:
            Block info dict if exception found, None otherwise
        """
        exception_content = self._get_exception_content(msg)
        if exception_content:
            exception_type = str(exception_content.get("type", "UnknownException"))
            return {
                "rail": exception_type,
                "message": str(
                    exception_content.get("message", "Content blocked by guardrail")
                ),
                "reason": f"Blocked by {exception_type}",
            }
        return None

    def _get_exception_content(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Safely extract exception content from a message if it's an exception.

        Args:
            msg: Message dictionary

        Returns:
            Exception content dict if found, None otherwise
        """
        if msg.get("role") != "exception":
            return None

        exception_content = msg.get("content", {})
        return exception_content if isinstance(exception_content, dict) else None

    def _check_fallback_patterns(
        self, response: Union[Dict[str, Any], List[Dict[str, Any]], Any]
    ) -> Optional[Dict[str, str]]:
        """
        Check for standard refusal patterns in response content.

        Args:
            response: Response from NeMo Guardrails

        Returns:
            Block info dict if pattern matched, None otherwise
        """
        content = self._extract_content(response)
        if not content:
            return None

        content_lower = content.lower()
        nemo_standard_refusals = [
            "i'm not able to respond to that",
            "i cannot respond to that request",
        ]

        for pattern in nemo_standard_refusals:
            if pattern in content_lower:
                logger.warning(
                    "Guardrail blocking detected via FALLBACK text matching. "
                    "Consider enabling 'enable_rails_exceptions: true' in config "
                    "for more reliable detection."
                )
                return {
                    "rail": "detected_via_fallback",
                    "message": content,
                    "reason": "Content matched NeMo standard refusal pattern",
                }

        return None

    def _extract_content(
        self, response: Union[Dict[str, Any], List[Dict[str, Any]], Any]
    ) -> str:
        """
        Extract content string from various NeMo response formats.

        Args:
            response: Response from NeMo Guardrails

        Returns:
            Extracted content string
        """
        if isinstance(response, dict):
            return self._extract_content_from_dict(response)

        if isinstance(response, list) and len(response) > 0:
            last_msg = response[-1]
            if isinstance(last_msg, dict):
                return self._extract_content_from_dict(last_msg)

        return ""

    def _extract_content_from_dict(self, msg: Dict[str, Any]) -> str:
        """
        Extract content from a single message dictionary.

        Args:
            msg: Message dictionary

        Returns:
            Extracted content string
        """
        # Check for exception format first
        exception_content = self._get_exception_content(msg)
        if exception_content:
            return str(exception_content.get("message", ""))

        # Normal response
        content = msg.get("content", "")
        return str(content) if content is not None else ""
