"""MultiAPICaller — concurrent batch execution of multiple API endpoints."""

import asyncio
from typing import Any

from loguru import logger

from tool_classifier.api_caller import APICaller
from tool_classifier.constants import (
    MULTI_API_BATCH_TIMEOUT,
    MULTI_API_PARTIAL_FAILURE_MESSAGES,
)
from tool_classifier.models import APICallResult, MultiAPICallResult
from src.utils.error_utils import generate_error_id, log_error_with_context
from llm_orchestrator_config.llm_ochestrator_constants import get_localized_message


class MultiAPICaller:
    """
    Executes multiple API endpoint calls concurrently using :func:`asyncio.gather`.

    Reuses the caller's :class:`~tool_classifier.api_caller.APICaller` instance so
    that per-URL circuit breaker state is shared across single and batch invocations.

    A batch-level timeout caps total wall-clock time.  When the timeout fires, any
    still-pending tasks are cancelled and their slots are filled with a failure result,
    ensuring the caller always receives a fully populated :class:`MultiAPICallResult`.

    Args:
        api_caller: Shared :class:`~tool_classifier.api_caller.APICaller` instance.
            Circuit breaker state is inherited from this instance.
        batch_timeout: Maximum seconds to wait for the entire batch. Defaults to
            :data:`~tool_classifier.constants.MULTI_API_BATCH_TIMEOUT`.
    """

    def __init__(
        self,
        api_caller: APICaller,
        batch_timeout: int = MULTI_API_BATCH_TIMEOUT,
    ) -> None:
        self._api_caller = api_caller
        self._batch_timeout = batch_timeout

    async def call_all(
        self,
        endpoints: list[dict[str, Any]],
        language: str = "et",
    ) -> MultiAPICallResult:
        """Execute all *endpoints* concurrently and return a consolidated result.

        Each endpoint dict must contain at minimum:
            - ``"url"`` (str): Full URL for the request.
            - ``"method"`` (str): HTTP method — ``"GET"`` or ``"POST"``.
            - ``"call_params"`` (dict): Query / body parameters to send.
              This key is intentionally distinct from the ``"params"`` key on
              endpoint schema dicts (which holds a *list* of parameter
              descriptors used during parameter collection), to prevent the
              schema list from being forwarded to the HTTP call.

        Results are returned in the same order as *endpoints*.  Failed tasks
        (exceptions or batch timeout) produce ``APICallResult(success=False, …)``.

        Args:
            endpoints: List of endpoint descriptor dicts.
            language: BCP-47 language code for user-facing error messages.

        Returns:
            :class:`~tool_classifier.models.MultiAPICallResult` with one result per
            endpoint.
        """
        if not endpoints:
            return MultiAPICallResult(results=[], endpoints=[])

        tasks: list[asyncio.Task[APICallResult]] = [
            asyncio.create_task(
                self._api_caller.call(
                    url=ep["url"],
                    method=ep["method"],
                    params=ep.get("call_params", {}),
                    language=language,
                ),
                name=f"multi_api_{i}",
            )
            for i, ep in enumerate(endpoints)
        ]

        results: list[APICallResult]
        try:
            raw = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self._batch_timeout,
            )
            results = [self._coerce_result(item, language) for item in raw]

        except asyncio.TimeoutError:
            pending = [t for t in tasks if not t.done()]
            logger.warning(
                f"[MultiAPICaller] Batch timeout ({self._batch_timeout}s) — "
                f"cancelling {len(pending)} pending task(s)"
            )
            for task in pending:
                task.cancel()
            # Await cancelled tasks so their coroutines can complete cleanup
            # (e.g. close HTTP connections) before we return.
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

            results = []
            for task in tasks:
                if task.done() and not task.cancelled():
                    exc = task.exception()
                    outcome: APICallResult | BaseException = (
                        exc if exc is not None else task.result()
                    )
                    results.append(self._coerce_result(outcome, language))
                else:
                    results.append(
                        APICallResult(
                            success=False,
                            status_code=0,
                            response_data="",
                            error=get_localized_message(
                                MULTI_API_PARTIAL_FAILURE_MESSAGES, language
                            ),
                        )
                    )

        had_failure = any(not r.success for r in results)
        if had_failure:
            logger.warning(
                "[MultiAPICaller] Partial failure: "
                f"{sum(not r.success for r in results)}/{len(results)} call(s) failed"
            )

        return MultiAPICallResult(results=results, endpoints=endpoints)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _coerce_result(
        self,
        item: APICallResult | BaseException | None,
        language: str,
    ) -> APICallResult:
        """Convert a raw gather() output item to an :class:`APICallResult`.

        :func:`asyncio.gather` with ``return_exceptions=True`` returns either the
        coroutine's return value or the exception that was raised.  We identify
        exceptions by checking against :class:`BaseException` rather than the
        positive type, which avoids issues with Python's dual import paths
        (``tool_classifier.models`` vs ``src.tool_classifier.models``).
        """
        if not isinstance(item, BaseException):
            # Assume any non-exception value is already an APICallResult.
            return item  # type: ignore[return-value]
        error_id = generate_error_id()
        exc: Exception = (
            item if isinstance(item, Exception) else RuntimeError(str(item))
        )
        log_error_with_context(
            logger,
            error_id,
            "multi_api_task_exception",
            None,
            exc,
            {},
        )
        return APICallResult(
            success=False,
            status_code=0,
            response_data="",
            error=get_localized_message(MULTI_API_PARTIAL_FAILURE_MESSAGES, language),
        )
