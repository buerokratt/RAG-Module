"""Unit tests for InputSanitizer — focused on #service prefix safety.

Validates that strip_html_tags() and sanitize_message() leave the
#service, /POST/... routing prefix characters (#, comma, /) untouched,
so that prefix detection logic in downstream handlers can always match.
"""

import pytest

from src.utils.input_sanitizer import InputSanitizer


class TestSanitizeMessageServicePrefix:
    """Primary passthrough: #service, /METHOD/... payloads must survive sanitization unchanged."""

    def test_exact_service_prefix_passthrough(self) -> None:
        """The canonical #service prefix must survive sanitization bit-for-bit identical."""
        msg = "#service, /POST/services/active/foo"
        assert InputSanitizer.sanitize_message(msg) == msg

    @pytest.mark.parametrize(
        "msg",
        [
            "#service, /POST/services/active/foo",
            "#service, /GET/services/list",
            "#service, /DELETE/services/active/foo",
            "#service, /PUT/services/active/foo",
            "#service, /PATCH/services/active/foo",
            "#service, /POST/services/active/foo?status=true",
            "#service, /POST/services/active/foo?a=1&b=2",
            "#service, /POST/services/active/foo#anchor",
        ],
    )
    def test_service_prefix_variants_passthrough(self, msg: str) -> None:
        """All #service, /METHOD/... variants must pass through unmodified."""
        assert InputSanitizer.sanitize_message(msg) == msg


class TestSanitizeMessageHtmlStripping:
    """Confirms HTML IS stripped while #service prefix characters survive.

    These tests prove the sanitizer is active (not a no-op) and that it
    surgically removes only HTML constructs, leaving #, comma, and / intact.
    """

    def test_bold_tags_stripped_prefix_survives(self) -> None:
        result = InputSanitizer.sanitize_message(
            "#service, <b>/POST/</b>services/active/foo"
        )
        assert result == "#service, /POST/services/active/foo"

    def test_script_tag_content_stripped_path_survives(self) -> None:
        """Dangerous <script> tag and its content are removed; path remainder survives."""
        result = InputSanitizer.sanitize_message(
            "#service, /POST/<script>alert(1)</script>foo"
        )
        assert result == "#service, /POST/foo"

    def test_entity_encoded_script_tag_stripped_path_survives(self) -> None:
        """Entity-encoded <script> tag is decoded then stripped; path remainder survives.

        If html.unescape() ran *after* tag stripping, &lt;script&gt;...&lt;/script&gt;
        would survive all three stripping passes and be decoded into a live <script>
        tag in the output.  The sanitizer must unescape *before* stripping to close
        this bypass.
        """
        result = InputSanitizer.sanitize_message(
            "#service, /POST/&lt;script&gt;alert(1)&lt;/script&gt;foo"
        )
        assert result == "#service, /POST/foo"

    def test_html_entities_unescaped_prefix_intact(self) -> None:
        """html.unescape() runs inside strip_html_tags(); confirm it does not alter #, comma, or /."""
        result = InputSanitizer.sanitize_message("#service, /POST/foo&amp;bar")
        assert result == "#service, /POST/foo&bar"

    def test_hash_not_treated_as_html_tag(self) -> None:
        """# is never matched by <[^>]+>; verify it is never stripped."""
        result = InputSanitizer.sanitize_message("#service, /GET/list")
        assert result.startswith("#service")

    def test_forward_slash_not_stripped(self) -> None:
        """/ characters must survive all three passes of strip_html_tags()."""
        result = InputSanitizer.sanitize_message("#service, /POST/a/b/c")
        assert "/POST/a/b/c" in result

    def test_comma_not_stripped(self) -> None:
        """Comma separator between prefix and path must survive sanitization."""
        result = InputSanitizer.sanitize_message("#service, /GET/list")
        assert ", " in result


class TestSanitizeMessageWhitespace:
    """Documents whitespace normalisation rules that apply even to #service payloads.

    Callers constructing #service payloads must use exactly one space after
    the comma; this class documents what happens if they don't.
    """

    def test_single_space_after_comma_preserved(self) -> None:
        """A single space between the comma and the slash is NOT collapsed or removed."""
        msg = "#service, /POST/services/active/foo"
        assert InputSanitizer.sanitize_message(msg) == msg

    def test_double_space_after_comma_collapsed_to_single(self) -> None:
        """Two consecutive spaces are collapsed to one; callers must send exactly one space."""
        result = InputSanitizer.sanitize_message("#service,  /POST/services/active/foo")
        assert result == "#service, /POST/services/active/foo"

    def test_leading_whitespace_stripped(self) -> None:
        result = InputSanitizer.sanitize_message(
            "  #service, /POST/services/active/foo"
        )
        assert result == "#service, /POST/services/active/foo"

    def test_trailing_whitespace_stripped(self) -> None:
        result = InputSanitizer.sanitize_message(
            "#service, /POST/services/active/foo  "
        )
        assert result == "#service, /POST/services/active/foo"

    def test_tab_in_prefix_converted_to_space_then_collapsed(self) -> None:
        """Tabs within the prefix are normalised along with spaces; a tab after the comma becomes a single space."""
        result = InputSanitizer.sanitize_message("#service,\t/POST/services/active/foo")
        assert result == "#service, /POST/services/active/foo"
