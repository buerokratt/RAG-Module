"""Unit tests for context analyzer - greeting detection and context analysis."""

import pytest
from collections.abc import Generator
from unittest.mock import MagicMock, patch
import json
import dspy

from src.tool_classifier.context_analyzer import (
    ContextAnalyzer,
)
from src.tool_classifier.greeting_constants import get_greeting_response


@pytest.fixture(autouse=True)
def mock_dspy_lm() -> Generator[MagicMock, None, None]:
    """Mock DSPy LM to prevent 'No LM is loaded' errors."""
    mock_lm = MagicMock()
    mock_lm.history = []
    with patch("dspy.settings") as mock_settings:
        mock_settings.lm = mock_lm
        # Configure DSPy with mock LM
        dspy.configure(lm=mock_lm)
        yield mock_lm


class TestContextAnalyzerInit:
    """Test ContextAnalyzer initialization."""

    def test_init_creates_analyzer(self) -> None:
        """ContextAnalyzer should initialize with LLM manager."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        assert analyzer.llm_manager is llm_manager
        assert analyzer._module is None
        assert analyzer._summary_module is None
        assert analyzer._summary_analysis_module is None


class TestConversationHistoryFormatting:
    """Test conversation history formatting."""

    def test_format_empty_history(self) -> None:
        """Empty history should return empty JSON array."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        result = analyzer._format_conversation_history([])

        assert result == "[]"

    def test_format_single_turn(self) -> None:
        """Single conversation turn should be formatted correctly."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        history = [
            {
                "authorRole": "user",
                "message": "Hello",
                "timestamp": "2024-01-01T12:00:00",
            }
        ]

        result = analyzer._format_conversation_history(history)
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["role"] == "user"
        assert parsed[0]["message"] == "Hello"

    def test_format_multiple_turns(self) -> None:
        """Multiple conversation turns should be formatted correctly."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        history = [
            {
                "authorRole": "user",
                "message": "What is tax?",
                "timestamp": "2024-01-01T12:00:00",
            },
            {
                "authorRole": "bot",
                "message": "Tax is a mandatory financial charge.",
                "timestamp": "2024-01-01T12:00:01",
            },
            {
                "authorRole": "user",
                "message": "Thank you",
                "timestamp": "2024-01-01T12:00:02",
            },
        ]

        result = analyzer._format_conversation_history(history)
        parsed = json.loads(result)

        assert len(parsed) == 3
        assert parsed[0]["role"] == "user"
        assert parsed[1]["role"] == "bot"
        assert parsed[2]["role"] == "user"

    def test_format_truncates_to_max_turns(self) -> None:
        """History should be truncated to last 10 turns."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Create 15 turns
        history = [
            {
                "authorRole": "user" if i % 2 == 0 else "bot",
                "message": f"Message {i}",
                "timestamp": f"2024-01-01T12:00:{i:02d}",
            }
            for i in range(15)
        ]

        result = analyzer._format_conversation_history(history, max_turns=10)
        parsed = json.loads(result)

        assert len(parsed) == 10
        # Should have last 10 turns (indices 5-14)
        assert parsed[0]["message"] == "Message 5"
        assert parsed[-1]["message"] == "Message 14"


class TestGreetingDetection:
    """Test greeting detection functionality."""

    @pytest.mark.asyncio
    async def test_detect_estonian_greeting(self) -> None:
        """Should detect Estonian greeting 'Tere' and generate response."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Mock DSPy module response
        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": True,
                "can_answer_from_context": False,
                "answer": "Tere! Kuidas ma saan sind aidata?",
                "reasoning": "User said hello in Estonian",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, cost_dict = await analyzer.analyze_context(
                    query="Tere!",
                    conversation_history=[],
                    language="et",
                )

        assert result.is_greeting is True
        assert result.can_answer_from_context is False
        assert "Tere" in result.answer
        assert cost_dict["total_cost"] == 0.001

    @pytest.mark.asyncio
    async def test_detect_english_greeting(self) -> None:
        """Should detect English greeting 'Hello' and generate response."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Mock DSPy module response
        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": True,
                "can_answer_from_context": False,
                "answer": "Hello! How can I help you?",
                "reasoning": "User said hello in English",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, cost_dict = await analyzer.analyze_context(
                    query="Hello!",
                    conversation_history=[],
                    language="en",
                )

        assert result.is_greeting is True
        assert "Hello" in result.answer or "hello" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_detect_goodbye(self) -> None:
        """Should detect goodbye greeting."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": True,
                "can_answer_from_context": False,
                "answer": "Goodbye! Have a great day!",
                "reasoning": "User said goodbye",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="Bye!",
                    conversation_history=[],
                    language="en",
                )

        assert result.is_greeting is True

    @pytest.mark.asyncio
    async def test_detect_thanks(self) -> None:
        """Should detect thank you greeting."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": True,
                "can_answer_from_context": False,
                "answer": "You're welcome! Feel free to ask if you have more questions.",
                "reasoning": "User said thank you",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="Thank you!",
                    conversation_history=[],
                    language="en",
                )

        assert result.is_greeting is True


class TestContextBasedAnswering:
    """Test context-based question answering."""

    @pytest.mark.asyncio
    async def test_answer_from_conversation_history(self) -> None:
        """Should extract answer from conversation history when query references it."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        history = [
            {
                "authorRole": "user",
                "message": "What is the tax rate?",
                "timestamp": "2024-01-01T12:00:00",
            },
            {
                "authorRole": "bot",
                "message": "The tax rate is 20%.",
                "timestamp": "2024-01-01T12:00:01",
            },
        ]

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": True,
                "answer": "I mentioned that the tax rate is 20%.",
                "reasoning": "User is asking about previously mentioned tax rate",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.002,
                    "total_tokens": 100,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="What was the rate you mentioned?",
                    conversation_history=history,
                    language="en",
                )

        assert result.is_greeting is False
        assert result.can_answer_from_context is True
        assert result.answer is not None
        assert "20%" in result.answer

    @pytest.mark.asyncio
    async def test_cannot_answer_from_context(self) -> None:
        """Should return cannot answer when query doesn't reference history."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        history = [
            {
                "authorRole": "user",
                "message": "What is the weather?",
                "timestamp": "2024-01-01T12:00:00",
            },
        ]

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": False,
                "answer": None,
                "reasoning": "Query is about taxes, not previous weather discussion",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.002,
                    "total_tokens": 100,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="What is the tax rate?",
                    conversation_history=history,
                    language="en",
                )

        assert result.is_greeting is False
        assert result.can_answer_from_context is False
        assert result.answer is None


class TestErrorHandling:
    """Test error handling in context analyzer."""

    @pytest.mark.asyncio
    async def test_handles_llm_json_parse_error(self) -> None:
        """Should handle invalid JSON response from LLM gracefully."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Mock DSPy module to return invalid JSON
        mock_response = MagicMock()
        mock_response.analysis_result = "Invalid JSON response"

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="Hello",
                    conversation_history=[],
                    language="en",
                )

        # Should fallback to safe default
        assert result.is_greeting is False
        assert result.can_answer_from_context is False
        assert result.answer is None
        assert "Failed to parse" in result.reasoning

    @pytest.mark.asyncio
    async def test_handles_llm_exception(self) -> None:
        """Should handle LLM call exceptions gracefully."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Mock DSPy module to raise exception
        with patch.object(
            dspy,
            "ChainOfThought",
            return_value=MagicMock(side_effect=Exception("LLM error")),
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "num_calls": 0,
                }

                result, _ = await analyzer.analyze_context(
                    query="Hello",
                    conversation_history=[],
                    language="en",
                )

        # Should fallback to safe default
        assert result.is_greeting is False
        assert result.can_answer_from_context is False
        assert result.answer is None
        assert "error" in result.reasoning.lower()


class TestFallbackGreeting:
    """Test fallback greeting responses."""

    def test_fallback_estonian_greeting(self) -> None:
        """Should return Estonian fallback greeting."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        response = analyzer.get_fallback_greeting_response("et")

        assert "Tere" in response

    def test_fallback_english_greeting(self) -> None:
        """Should return English fallback greeting."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        response = analyzer.get_fallback_greeting_response("en")

        assert "Hello" in response or "hello" in response

    def test_fallback_unknown_language_defaults_to_estonian(self) -> None:
        """Should default to Estonian for unknown language codes."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        response = analyzer.get_fallback_greeting_response("xx")

        assert "Tere" in response or "tere" in response.lower()


class TestGreetingConstants:
    """Test greeting constants and helper functions."""

    def test_get_estonian_hello(self) -> None:
        """Should return Estonian hello greeting."""
        response = get_greeting_response("hello", "et")
        assert "Tere" in response

    def test_get_english_goodbye(self) -> None:
        """Should return English goodbye greeting."""
        response = get_greeting_response("goodbye", "en")
        assert "Goodbye" in response or "goodbye" in response

    def test_get_estonian_thanks(self) -> None:
        """Should return Estonian thanks greeting."""
        response = get_greeting_response("thanks", "et")
        assert "Palun" in response

    def test_unknown_greeting_type_defaults_to_hello(self) -> None:
        """Should default to hello for unknown greeting types."""
        response = get_greeting_response("unknown", "en")
        assert "Hello" in response or "hello" in response


def _make_history(num_turns: int) -> list[dict[str, str]]:
    """Helper to create a conversation history with the specified number of turns."""
    return [
        {
            "authorRole": "user" if i % 2 == 0 else "bot",
            "message": f"Message {i}",
            "timestamp": f"2024-01-01T12:00:{i:02d}",
        }
        for i in range(num_turns)
    ]


class TestCostMerging:
    """Test cost dictionary merging."""

    def test_merge_cost_dicts(self) -> None:
        """Should sum all numeric values from two cost dicts."""
        cost1 = {
            "total_cost": 0.001,
            "total_tokens": 50,
            "total_prompt_tokens": 30,
            "total_completion_tokens": 20,
            "num_calls": 1,
        }
        cost2 = {
            "total_cost": 0.002,
            "total_tokens": 100,
            "total_prompt_tokens": 60,
            "total_completion_tokens": 40,
            "num_calls": 1,
        }

        merged = ContextAnalyzer._merge_cost_dicts(cost1, cost2)

        assert merged["total_cost"] == pytest.approx(0.003)
        assert merged["total_tokens"] == 150
        assert merged["total_prompt_tokens"] == 90
        assert merged["total_completion_tokens"] == 60
        assert merged["num_calls"] == 2

    def test_merge_cost_dicts_with_empty(self) -> None:
        """Should handle merging with an empty cost dict."""
        cost1 = {
            "total_cost": 0.001,
            "total_tokens": 50,
            "total_prompt_tokens": 30,
            "total_completion_tokens": 20,
            "num_calls": 1,
        }

        merged = ContextAnalyzer._merge_cost_dicts(cost1, {})

        assert merged["total_cost"] == 0.001
        assert merged["total_tokens"] == 50
        assert merged["num_calls"] == 1


class TestConversationSummary:
    """Test conversation summary generation."""

    @pytest.mark.asyncio
    async def test_generate_summary_from_older_turns(self) -> None:
        """Should generate summary from older conversation turns."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        older_history = _make_history(6)

        mock_response = MagicMock()
        mock_response.summary = "User discussed messages 0-5 about various topics."

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                summary, cost_dict = await analyzer._generate_conversation_summary(
                    older_history
                )

        assert summary == "User discussed messages 0-5 about various topics."
        assert cost_dict["total_cost"] == 0.001

    @pytest.mark.asyncio
    async def test_generate_summary_handles_exception(self) -> None:
        """Should return empty string when summary generation fails."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        with patch.object(
            dspy,
            "ChainOfThought",
            return_value=MagicMock(side_effect=Exception("LLM error")),
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "num_calls": 0,
                }

                summary, _ = await analyzer._generate_conversation_summary(
                    _make_history(5)
                )

        assert summary == ""

    @pytest.mark.asyncio
    async def test_analyze_from_summary_can_answer(self) -> None:
        """Should answer from summary when information is available."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "can_answer_from_context": True,
                "answer": "The tax rate discussed earlier was 20%.",
                "reasoning": "Summary contains tax rate information",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.002,
                    "total_tokens": 100,
                    "num_calls": 1,
                }

                result, cost_dict = await analyzer._analyze_from_summary(
                    query="What was the tax rate?",
                    summary="User asked about tax. Bot replied: tax rate is 20%.",
                )

        assert result.can_answer_from_context is True
        assert result.answered_from_summary is True
        assert result.answer is not None
        assert "20%" in result.answer

    @pytest.mark.asyncio
    async def test_analyze_from_summary_cannot_answer(self) -> None:
        """Should return cannot answer when summary doesn't contain relevant info."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "can_answer_from_context": False,
                "answer": None,
                "reasoning": "Summary does not contain information about weather",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.002,
                    "total_tokens": 100,
                    "num_calls": 1,
                }

                result, _ = await analyzer._analyze_from_summary(
                    query="What is the weather?",
                    summary="User discussed tax rates and filing.",
                )

        assert result.can_answer_from_context is False
        assert result.answered_from_summary is False
        assert result.answer is None

    @pytest.mark.asyncio
    async def test_analyze_from_summary_handles_exception(self) -> None:
        """Should return safe fallback when summary analysis fails."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        with patch.object(
            dspy,
            "ChainOfThought",
            return_value=MagicMock(side_effect=Exception("LLM error")),
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.0,
                    "total_tokens": 0,
                    "num_calls": 0,
                }

                result, _ = await analyzer._analyze_from_summary(
                    query="test", summary="test summary"
                )

        assert result.can_answer_from_context is False
        assert result.answered_from_summary is False
        assert result.answer is None


class TestSummaryFlow:
    """Test the full analyze_context flow with summary logic."""

    @pytest.mark.asyncio
    async def test_short_history_skips_summary(self) -> None:
        """With <= 10 turns, should use recent history only, no summary."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Cannot answer from recent history, but only 8 turns - should NOT trigger summary
        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": False,
                "answer": None,
                "reasoning": "Cannot answer from context",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="What is digital signature?",
                    conversation_history=_make_history(8),
                    language="en",
                )

        # Should not answer (no summary triggered for <= 10 turns)
        assert result.can_answer_from_context is False
        assert result.answered_from_summary is False
        assert result.answer is None

    @pytest.mark.asyncio
    async def test_long_history_answers_from_recent(self) -> None:
        """With > 10 turns, if recent 10 can answer, should not trigger summary."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Can answer from recent history
        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": True,
                "answer": "The rate is 20%.",
                "reasoning": "Found in recent history",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="What was the rate?",
                    conversation_history=_make_history(15),
                    language="en",
                )

        assert result.can_answer_from_context is True
        assert result.answered_from_summary is False
        assert result.answer == "The rate is 20%."

    @pytest.mark.asyncio
    async def test_long_history_answers_from_summary(self) -> None:
        """With > 10 turns, if recent can't answer but summary can, should return summary answer."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Step 1: Recent history cannot answer
        recent_response = MagicMock()
        recent_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": False,
                "answer": None,
                "reasoning": "Not in recent history",
            }
        )

        # Step 2: Summary generation
        summary_response = MagicMock()
        summary_response.summary = (
            "User asked about tax rates. Bot said the tax rate is 20%."
        )

        # Step 3: Summary analysis can answer
        summary_analysis_response = MagicMock()
        summary_analysis_response.analysis_result = json.dumps(
            {
                "can_answer_from_context": True,
                "answer": "Based on our earlier discussion, the tax rate is 20%.",
                "reasoning": "Found tax rate in conversation summary",
            }
        )

        # Chain of Thought is called 3 times: recent analysis, summary gen, summary analysis
        call_count = 0
        mock_modules = [
            MagicMock(return_value=recent_response),
            MagicMock(return_value=summary_response),
            MagicMock(return_value=summary_analysis_response),
        ]

        def chain_of_thought_factory(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            module = mock_modules[call_count]
            call_count += 1
            return module

        with patch.object(dspy, "ChainOfThought", side_effect=chain_of_thought_factory):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, cost_dict = await analyzer.analyze_context(
                    query="What was the tax rate we discussed?",
                    conversation_history=_make_history(15),
                    language="en",
                )

        assert result.can_answer_from_context is True
        assert result.answered_from_summary is True
        assert result.answer is not None
        assert "20%" in result.answer
        # Costs should be merged from all 3 calls
        assert cost_dict["num_calls"] == 3

    @pytest.mark.asyncio
    async def test_long_history_falls_to_rag(self) -> None:
        """With > 10 turns, if neither recent nor summary can answer, should fall through."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        # Step 1: Recent history cannot answer
        recent_response = MagicMock()
        recent_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": False,
                "answer": None,
                "reasoning": "Not in recent history",
            }
        )

        # Step 2: Summary generation
        summary_response = MagicMock()
        summary_response.summary = "User discussed weather and greetings."

        # Step 3: Summary analysis cannot answer
        summary_analysis_response = MagicMock()
        summary_analysis_response.analysis_result = json.dumps(
            {
                "can_answer_from_context": False,
                "answer": None,
                "reasoning": "Summary does not contain tax information",
            }
        )

        call_count = 0
        mock_modules = [
            MagicMock(return_value=recent_response),
            MagicMock(return_value=summary_response),
            MagicMock(return_value=summary_analysis_response),
        ]

        def chain_of_thought_factory(*args: object, **kwargs: object) -> MagicMock:
            nonlocal call_count
            module = mock_modules[call_count]
            call_count += 1
            return module

        with patch.object(dspy, "ChainOfThought", side_effect=chain_of_thought_factory):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="What is the tax rate?",
                    conversation_history=_make_history(15),
                    language="en",
                )

        # Should not be able to answer -> falls to RAG
        assert result.can_answer_from_context is False
        assert result.answered_from_summary is False
        assert result.answer is None

    @pytest.mark.asyncio
    async def test_answered_from_summary_flag_is_false_for_recent(self) -> None:
        """The answered_from_summary flag should be False for recent history answers."""
        llm_manager = MagicMock()
        analyzer = ContextAnalyzer(llm_manager)

        mock_response = MagicMock()
        mock_response.analysis_result = json.dumps(
            {
                "is_greeting": False,
                "can_answer_from_context": True,
                "answer": "The answer from recent history.",
                "reasoning": "Found in recent conversation",
            }
        )

        with patch.object(
            dspy, "ChainOfThought", return_value=MagicMock(return_value=mock_response)
        ):
            with patch(
                "src.tool_classifier.context_analyzer.get_lm_usage_since"
            ) as mock_cost:
                mock_cost.return_value = {
                    "total_cost": 0.001,
                    "total_tokens": 50,
                    "num_calls": 1,
                }

                result, _ = await analyzer.analyze_context(
                    query="What did you say?",
                    conversation_history=_make_history(5),
                    language="en",
                )

        assert result.answered_from_summary is False
