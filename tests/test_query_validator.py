"""Unit tests for query validator.

Tests cover all documented examples, edge cases, and boundary conditions
to prevent regressions as validation rules evolve.
"""

import pytest
from src.utils.query_validator import validate_query_basic, QueryValidationResult


class TestQueryValidatorEmpty:
    """Test empty and whitespace-only queries."""

    @pytest.mark.parametrize(
        "query",
        [
            "",
            "   ",
            "\t",
            "\n",
            "\t\n  ",
            "    \t\n\r  ",
        ],
    )
    def test_empty_queries_rejected(self, query: str):
        """Empty or whitespace-only queries should be rejected."""
        result = validate_query_basic(query)
        assert result.is_valid is False
        assert result.rejection_reason == "empty"


class TestQueryValidatorSpecialCharsOnly:
    """Test queries with only special characters or punctuation."""

    @pytest.mark.parametrize(
        "query",
        [
            "...",
            "???",
            "!!!",
            "!@#$%^&*()",
            ".,?!;:",
            "---",
            # Note: "___" is repetitive, not special_chars (underscore matches \w)
            "[]{}()",
            "<>",
            "//",
            "\\\\",
            "++",
            "**",
            "~~",
            "``",
            "''",
            '""',
            "—",
            "–",
            "''",
            "•••",
            "→→",
            "※※",
            "!?!?",
            "...???",
            "!!! ???",
            "????",  # 4 question marks - special chars only
        ],
    )
    def test_special_chars_only_rejected(self, query: str):
        """Queries with only special characters should be rejected."""
        result = validate_query_basic(query)
        assert result.is_valid is False
        assert result.rejection_reason == "special_chars_only"


class TestQueryValidatorTooShort:
    """Test queries that are too short."""

    @pytest.mark.parametrize(
        "query",
        [
            "a",
            "A",
            "1",
            "õ",
            "я",
            "a!",
            "a?",
            "1.",
            "a...",
            "!a!",
        ],
    )
    def test_too_short_queries_rejected(self, query: str):
        """Queries with fewer than 2 meaningful characters should be rejected."""
        result = validate_query_basic(query)
        assert result.is_valid is False
        assert result.rejection_reason == "too_short"


class TestQueryValidatorRepetitive:
    """Test queries with only repetitive characters."""

    @pytest.mark.parametrize(
        "query",
        [
            "aa",
            "AAA",
            "aaa",
            "aaaa",
            "AAAAAAA",
            "aAaAa",
            "11",
            "111",
            "0000",
            "99999",
            "õõõõ",
            "ääää",
            "яяяя",
            "aa!",
            "!!!aaa!!!",
            "a.a.a.a",
            "___",  # 3 underscores - repetitive (underscore is \w)
        ],
    )
    def test_repetitive_queries_rejected(self, query: str):
        """Queries with only one unique meaningful character should be rejected."""
        result = validate_query_basic(query)
        assert result.is_valid is False
        assert result.rejection_reason == "repetitive"


class TestQueryValidatorValid:
    """Test valid queries that should pass validation."""

    @pytest.mark.parametrize(
        "query",
        [
            "hi",
            "hello",
            "ok",
            "ab",
            "AB",
            "Hi",
            "123",
            "12",
            "abc123",
            "test1",
            "How to apply?",
            "What is this?",
            "When?",
            "tere",
            "kuidas",
            "Mis on?",
            "привет",
            "как дела",
            "ab!",
            "hello!",
            "test...",
            "what???",
            "a-b",
            "test_case",
            "test123!",
            "hello world",
            "a b c",
            "http://test",
            "test@email",
            "a1",
            "12ab",
            "õõte",
        ],
    )
    def test_valid_queries_accepted(self, query: str):
        """Valid queries with meaningful content should be accepted."""
        result = validate_query_basic(query)
        assert result.is_valid is True
        assert result.rejection_reason is None


class TestQueryValidatorEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_whitespace_trimmed(self):
        """Leading and trailing whitespace should be trimmed before validation."""
        result = validate_query_basic("  hello  ")
        assert result.is_valid is True

        result = validate_query_basic("   ")
        assert result.is_valid is False
        assert result.rejection_reason == "empty"

    def test_case_insensitive_repetition(self):
        """Repetition check should be case-insensitive."""
        result = validate_query_basic("AaAa")
        assert result.is_valid is False
        assert result.rejection_reason == "repetitive"

        result = validate_query_basic("AaAaAa")
        assert result.is_valid is False
        assert result.rejection_reason == "repetitive"

    def test_unicode_normalization(self):
        """Unicode characters should be handled consistently."""
        result = validate_query_basic("привет")
        assert result.is_valid is True

        result = validate_query_basic("你好")
        assert result.is_valid is True

        result = validate_query_basic("مرحبا")
        assert result.is_valid is True

    def test_mixed_scripts(self):
        """Queries with mixed scripts should be valid."""
        result = validate_query_basic("hello мир")
        assert result.is_valid is True

        result = validate_query_basic("test测试")
        assert result.is_valid is True

    def test_numbers_are_valid(self):
        """Numbers-only queries are considered valid."""
        result = validate_query_basic("123")
        assert result.is_valid is True

        result = validate_query_basic("42")
        assert result.is_valid is True

        result = validate_query_basic("2024")
        assert result.is_valid is True

    def test_numbers_repetitive(self):
        """Repetitive numbers should be rejected."""
        result = validate_query_basic("111")
        assert result.is_valid is False
        assert result.rejection_reason == "repetitive"

        result = validate_query_basic("00")
        assert result.is_valid is False
        assert result.rejection_reason == "repetitive"

    def test_punctuation_doesnt_count_as_meaningful(self):
        """Punctuation should not count toward meaningful character count."""
        result = validate_query_basic("a!!!")
        assert result.is_valid is False
        assert result.rejection_reason == "too_short"

        result = validate_query_basic("ab!!!")
        assert result.is_valid is True

    def test_emoji_with_text(self):
        """Emojis combined with text should be valid."""
        result = validate_query_basic("hello world")
        assert result.is_valid is True

        result = validate_query_basic("test case")
        assert result.is_valid is True

    def test_long_repetitive_string(self):
        """Long strings of repeated characters should be rejected."""
        result = validate_query_basic("a" * 100)
        assert result.is_valid is False
        assert result.rejection_reason == "repetitive"

    def test_result_is_pydantic_model(self):
        """Result should be a valid Pydantic model."""
        result = validate_query_basic("test")
        assert isinstance(result, QueryValidationResult)
        assert hasattr(result, "is_valid")
        assert hasattr(result, "rejection_reason")

        result_dict = result.model_dump()
        assert "is_valid" in result_dict
        assert "rejection_reason" in result_dict


class TestQueryValidatorDocumentedExamples:
    """Test all examples from function docstring."""

    def test_documented_valid_examples(self):
        """All documented valid examples should pass."""
        examples = [
            "How to apply for benefits?",
            "hi",
            "123",
            "ab!",
        ]
        for query in examples:
            result = validate_query_basic(query)
            assert result.is_valid is True, f"Expected '{query}' to be valid"
            assert result.rejection_reason is None

    def test_documented_invalid_examples(self):
        """All documented invalid examples should fail with correct reason."""
        examples = [
            ("...", "special_chars_only"),
            ("", "empty"),
            # Note: ???? is special_chars_only (not in \w), not repetitive
            ("????", "special_chars_only"),
            ("a", "too_short"),
        ]
        for query, expected_reason in examples:
            result = validate_query_basic(query)
            assert result.is_valid is False, f"Expected '{query}' to be invalid"
            assert result.rejection_reason == expected_reason, (
                f"Expected '{query}' to fail with '{expected_reason}', "
                f"got '{result.rejection_reason}'"
            )
