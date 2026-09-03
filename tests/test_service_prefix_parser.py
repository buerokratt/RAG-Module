"""Unit tests for ServiceWorkflowExecutor._parse_service_prefix().

Validates that the parser correctly extracts (http_method, endpoint_url) from
#service and #common_service button-payload strings, and returns None for any
input that does not match the expected format.
"""

import pytest

from src.tool_classifier.constants import (
    RUUTER_COMMON_SERVICE_BASE_URL,
    RUUTER_SERVICE_BASE_URL,
)
from src.tool_classifier.workflows.service_workflow import ServiceWorkflowExecutor


class TestParseServicePrefixValidInputs:
    """Happy-path cases: well-formed payloads must produce correct tuples."""

    def test_post_service_prefix(self) -> None:
        result = ServiceWorkflowExecutor._parse_service_prefix(
            "#service, /POST/services/active/application_mcq_step_passport"
        )
        assert result == (
            "POST",
            f"{RUUTER_SERVICE_BASE_URL}/services/active/application_mcq_step_passport",
        )

    def test_get_service_prefix(self) -> None:
        result = ServiceWorkflowExecutor._parse_service_prefix(
            "#service, /GET/services/active/some_service"
        )
        assert result == (
            "GET",
            f"{RUUTER_SERVICE_BASE_URL}/services/active/some_service",
        )

    def test_common_service_prefix(self) -> None:
        result = ServiceWorkflowExecutor._parse_service_prefix(
            "#common_service, /POST/common/some_step"
        )
        assert result == (
            "POST",
            f"{RUUTER_COMMON_SERVICE_BASE_URL}/common/some_step",
        )

    def test_method_uppercased(self) -> None:
        """Lowercase method in payload is normalised to uppercase."""
        result = ServiceWorkflowExecutor._parse_service_prefix(
            "#service, /post/services/active/foo"
        )
        assert result is not None
        assert result[0] == "POST"

    def test_leading_trailing_whitespace_stripped(self) -> None:
        """Extra whitespace around the payload is handled gracefully."""
        result = ServiceWorkflowExecutor._parse_service_prefix(
            "  #service, /POST/services/active/foo  "
        )
        assert result is not None
        assert result[0] == "POST"


class TestParseServicePrefixInvalidInputs:
    """All malformed inputs must return None for safe fallback."""

    def test_empty_string(self) -> None:
        assert ServiceWorkflowExecutor._parse_service_prefix("") is None

    def test_no_prefix(self) -> None:
        assert (
            ServiceWorkflowExecutor._parse_service_prefix("/POST/services/active/foo")
            is None
        )

    def test_plain_user_message(self) -> None:
        assert (
            ServiceWorkflowExecutor._parse_service_prefix(
                "I want to apply for a passport"
            )
            is None
        )

    def test_bare_prefix_no_path(self) -> None:
        assert ServiceWorkflowExecutor._parse_service_prefix("#service,") is None

    def test_prefix_missing_method(self) -> None:
        """Path with only one segment after the leading slash is malformed."""
        assert ServiceWorkflowExecutor._parse_service_prefix("#service, /POST") is None

    def test_prefix_no_leading_slash(self) -> None:
        """Path not starting with '/' is malformed."""
        assert (
            ServiceWorkflowExecutor._parse_service_prefix(
                "#service, POST/services/active/foo"
            )
            is None
        )

    def test_partial_prefix(self) -> None:
        """'#serv' is not a recognised prefix."""
        assert (
            ServiceWorkflowExecutor._parse_service_prefix(
                "#serv, /POST/services/active/foo"
            )
            is None
        )

    @pytest.mark.parametrize(
        "payload",
        [
            "#service, /123/services/active/foo",  # numeric "method"
            "#service, /PO ST/services/active/foo",  # method with space
        ],
    )
    def test_non_alpha_method(self, payload: str) -> None:
        """Methods containing non-alpha characters are rejected."""
        assert ServiceWorkflowExecutor._parse_service_prefix(payload) is None
