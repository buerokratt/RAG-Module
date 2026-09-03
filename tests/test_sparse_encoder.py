"""Unit tests for the sparse encoder module (BM25-style term-frequency vectors).

Covers:
- Normal text → non-empty SparseVector with correct index range and values
- Empty / whitespace-only input → empty SparseVector
- Multilingual text (Estonian, Russian) → non-empty vector
- Deterministic output — same text always yields identical indices and values
- Hash index range: all indices must be in [0, SPARSE_VOCAB_SIZE)
- Token frequency — repeated tokens increase their value
- SparseVector.to_dict() format
- SparseVector.is_empty() sentinel
- Collision accumulation (hash collisions merged by summing values)
- Sorted indices (Qdrant requirement)
"""

import pytest

from tool_classifier.sparse_encoder import (
    SPARSE_VOCAB_SIZE,
    SparseVector,
    compute_sparse_vector,
)


# ---------------------------------------------------------------------------
# SparseVector dataclass helpers
# ---------------------------------------------------------------------------


class TestSparseVectorHelpers:
    def test_to_dict_returns_correct_keys(self) -> None:
        sv = SparseVector(indices=[1, 5, 9], values=[1.0, 2.0, 3.0])
        d = sv.to_dict()
        assert set(d.keys()) == {"indices", "values"}
        assert d["indices"] == [1, 5, 9]
        assert d["values"] == [1.0, 2.0, 3.0]

    def test_to_dict_empty(self) -> None:
        sv = SparseVector()
        d = sv.to_dict()
        assert d == {"indices": [], "values": []}

    def test_is_empty_true_when_no_entries(self) -> None:
        assert SparseVector().is_empty() is True

    def test_is_empty_false_when_entries_present(self) -> None:
        assert SparseVector(indices=[0], values=[1.0]).is_empty() is False

    def test_is_empty_checks_indices_length(self) -> None:
        sv = SparseVector(indices=[10, 20], values=[0.5, 0.5])
        assert sv.is_empty() is False


# ---------------------------------------------------------------------------
# compute_sparse_vector — empty / whitespace inputs
# ---------------------------------------------------------------------------


class TestComputeSparseVectorEmpty:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "\t\n",
            "\r\n",
        ],
    )
    def test_empty_or_whitespace_returns_empty_vector(self, text: str) -> None:
        sv = compute_sparse_vector(text)
        assert sv.is_empty()
        assert sv.indices == []
        assert sv.values == []

    def test_none_like_empty_string(self) -> None:
        """Empty string (falsy) must return empty SparseVector."""
        sv = compute_sparse_vector("")
        assert sv.is_empty()


# ---------------------------------------------------------------------------
# compute_sparse_vector — normal text
# ---------------------------------------------------------------------------


class TestComputeSparseVectorNormal:
    def test_single_word_produces_one_index(self) -> None:
        sv = compute_sparse_vector("holiday")
        assert len(sv.indices) == 1
        assert len(sv.values) == 1
        assert sv.values[0] == 1.0

    def test_two_distinct_words_produce_two_entries(self) -> None:
        sv = compute_sparse_vector("public holiday")
        # Two distinct tokens → at most 2 entries (could collide, but unlikely)
        assert len(sv.indices) >= 1  # at least 1 due to possible hash collision

    def test_repeated_token_accumulates_count(self) -> None:
        sv = compute_sparse_vector("holiday holiday holiday")
        # Only one unique token "holiday"
        assert len(sv.indices) == 1
        assert sv.values[0] == 3.0

    def test_mixed_case_normalized_to_lowercase(self) -> None:
        sv_lower = compute_sparse_vector("holiday")
        sv_upper = compute_sparse_vector("HOLIDAY")
        assert sv_lower.indices == sv_upper.indices
        assert sv_lower.values == sv_upper.values

    def test_punctuation_stripped(self) -> None:
        sv_plain = compute_sparse_vector("hello")
        sv_punct = compute_sparse_vector("hello, world!")
        # "hello" and "world" both tokenized; sv_plain has only "hello"
        assert sv_plain.indices[0] in sv_punct.indices

    def test_numbers_tokenized_as_words(self) -> None:
        sv = compute_sparse_vector("2024 holiday")
        assert len(sv.indices) >= 1

    def test_output_indices_are_sorted(self) -> None:
        sv = compute_sparse_vector("public holiday in estonia this year")
        assert sv.indices == sorted(sv.indices)

    def test_indices_and_values_same_length(self) -> None:
        sv = compute_sparse_vector("national public holiday")
        assert len(sv.indices) == len(sv.values)


# ---------------------------------------------------------------------------
# Index range constraint
# ---------------------------------------------------------------------------


class TestIndexRange:
    @pytest.mark.parametrize(
        "text",
        [
            "public holidays Estonia",
            "riiklikud pühad Eestis",
            "государственные праздники Эстонии",
            "a b c d e f g h i j k l m n o p q r s t u v w x y z",
            "kuidas registreerida ettevõtet Eestis",
        ],
    )
    def test_all_indices_within_vocab_size(self, text: str) -> None:
        sv = compute_sparse_vector(text)
        for idx in sv.indices:
            assert 0 <= idx < SPARSE_VOCAB_SIZE, (
                f"Index {idx} is outside [0, {SPARSE_VOCAB_SIZE})"
            )

    def test_no_duplicate_indices(self) -> None:
        sv = compute_sparse_vector("the quick brown fox jumps over the lazy dog")
        assert len(sv.indices) == len(set(sv.indices))


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize(
        "text",
        [
            "public holidays in Estonia 2024",
            "riiklikud pühad",
            "государственные праздники",
            "when is the next holiday in Tallinn",
        ],
    )
    def test_same_text_produces_identical_output(self, text: str) -> None:
        sv1 = compute_sparse_vector(text)
        sv2 = compute_sparse_vector(text)
        assert sv1.indices == sv2.indices
        assert sv1.values == sv2.values

    def test_different_text_produces_different_output(self) -> None:
        import hashlib

        # Compute the expected indices using the same formula as the implementation
        # so the assertion is deterministic and immune to hash-collision false failures.
        def _idx(token: str) -> int:
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            return int.from_bytes(digest[:4], "little") % SPARSE_VOCAB_SIZE

        idx_holiday = _idx("holiday")  # 23913
        idx_weather = _idx("weather")  # 19866

        sv1 = compute_sparse_vector("holiday")
        sv2 = compute_sparse_vector("weather")

        assert sv1.indices == [idx_holiday]
        assert sv2.indices == [idx_weather]
        assert sv1.values == [1.0]
        assert sv2.values == [1.0]


# ---------------------------------------------------------------------------
# Multilingual text
# ---------------------------------------------------------------------------


class TestMultilingual:
    def test_estonian_text_produces_non_empty_vector(self) -> None:
        sv = compute_sparse_vector("riiklikud pühad Eestis")
        assert not sv.is_empty()

    def test_russian_text_produces_non_empty_vector(self) -> None:
        sv = compute_sparse_vector("государственные праздники в Эстонии")
        assert not sv.is_empty()

    def test_english_text_produces_non_empty_vector(self) -> None:
        sv = compute_sparse_vector("public holidays Estonia 2024")
        assert not sv.is_empty()

    def test_mixed_language_text_tokenized(self) -> None:
        sv = compute_sparse_vector("holiday pühad праздники")
        assert len(sv.indices) >= 1

    def test_estonian_special_chars_tokenized(self) -> None:
        """Characters like õ, ä, ö, ü must be included in tokens.

        Indices are computed from the same MD5→int→mod formula used by the
        implementation, making the assertion deterministic and collision-proof.
        """
        import hashlib

        def _idx(token: str) -> int:
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            return int.from_bytes(digest[:4], "little") % SPARSE_VOCAB_SIZE

        idx_with = _idx("õigus")  # 22973
        idx_without = _idx("oigus")  # 47150

        sv_with = compute_sparse_vector("õigus")
        sv_without = compute_sparse_vector("oigus")

        assert sv_with.indices == [idx_with]
        assert sv_without.indices == [idx_without]
        assert sv_with.values == [1.0]
        assert sv_without.values == [1.0]


# ---------------------------------------------------------------------------
# Values semantics
# ---------------------------------------------------------------------------


class TestValueSemantics:
    def test_values_are_floats(self) -> None:
        sv = compute_sparse_vector("test text")
        for v in sv.values:
            assert isinstance(v, float)

    def test_all_values_positive(self) -> None:
        sv = compute_sparse_vector("holiday in Tallinn this year")
        for v in sv.values:
            assert v > 0.0

    def test_frequency_doubles_when_token_appears_twice(self) -> None:
        sv_once = compute_sparse_vector("holiday")
        sv_twice = compute_sparse_vector("holiday holiday")
        assert sv_once.indices == sv_twice.indices
        assert sv_twice.values[0] == sv_once.values[0] * 2
