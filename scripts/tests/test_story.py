"""
tests/test_story.py
-------------------
Tests for story generation logic.

Unit tests (no API):   pytest scripts/tests/test_story.py -v
Integration tests:     pytest scripts/tests/test_story.py -v -m integration
                       (Requires GEMINI_API_KEY set in environment / .env)
"""

import os
import sys
import pytest
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_story import (
    validate_english_story,
    validate_translations,
    get_date_inspiration,
    generate_english_story,
    translate_to_portuguese,
    get_word_translations,
    run_story_pipeline,
    configure_gemini,
    PT_WORD_RE,
)



# ===========================================================================
# UNIT TESTS — no API calls
# ===========================================================================

class TestValidateEnglishStory:

    def _make_story(self, words=175, topic="Test", fun_fact="A fact."):
        return {"story": " ".join(["word"] * words), "topic": topic, "fun_fact": fun_fact}

    def test_valid_story_passes(self):
        result = validate_english_story(self._make_story(175))
        assert result["all_passed"]
        assert result["word_count"] == 175
        assert result["word_count_ok"]

    def test_too_short_fails(self):
        result = validate_english_story(self._make_story(100))
        assert not result["word_count_ok"]
        assert not result["all_passed"]

    def test_too_long_fails(self):
        result = validate_english_story(self._make_story(250))
        assert not result["word_count_ok"]
        assert not result["all_passed"]

    def test_boundary_140_ok(self):
        """140 words should pass (lower boundary)."""
        result = validate_english_story(self._make_story(140))
        assert result["word_count_ok"]

    def test_boundary_220_ok(self):
        """220 words should pass (upper boundary)."""
        result = validate_english_story(self._make_story(220))
        assert result["word_count_ok"]

    def test_boundary_139_fails(self):
        result = validate_english_story(self._make_story(139))
        assert not result["word_count_ok"]

    def test_boundary_221_fails(self):
        result = validate_english_story(self._make_story(221))
        assert not result["word_count_ok"]

    def test_missing_topic_fails(self):
        result = validate_english_story({"story": " ".join(["w"] * 175), "fun_fact": "f", "topic": ""})
        assert not result["has_topic"]
        assert not result["all_passed"]

    def test_missing_fun_fact_fails(self):
        result = validate_english_story({"story": " ".join(["w"] * 175), "topic": "T", "fun_fact": ""})
        assert not result["has_fun_fact"]
        assert not result["all_passed"]

    def test_grade_level_key_present(self):
        """grade_level key must always be present in result (may be None if NLTK unavailable)."""
        story_data = {
            "story": "The cat sat on the mat. The dog ran fast. The sun is hot.",
            "topic": "Cats",
            "fun_fact": "Cats purr.",
        }
        result = validate_english_story(story_data)
        assert "grade_level" in result
        assert "reading_level_ok" in result
        # grade_level is None when NLTK cmudict is unavailable (CI sandbox) — that's OK
        # When it IS a number, it should be a float/int
        if result["grade_level"] is not None:
            assert isinstance(result["grade_level"], (int, float))


class TestValidateTranslations:

    def test_full_coverage_passes(self):
        story = "O gato dorme aqui"
        translations = {"o": "the", "gato": "cat", "dorme": "sleeps", "aqui": "here"}
        result = validate_translations(story, translations)
        assert result["all_passed"]
        assert result["missing"] == []
        assert result["coverage_pct"] == 100.0

    def test_missing_words_detected(self):
        story = "O gato dorme aqui"
        translations = {"o": "the", "gato": "cat"}
        result = validate_translations(story, translations)
        assert not result["all_passed"]
        missing = set(result["missing"])
        assert "dorme" in missing or "aqui" in missing

    def test_empty_story(self):
        """Empty story should pass trivially."""
        result = validate_translations("", {"word": "w"})
        assert result["all_passed"]

    def test_accented_words_matched(self):
        """Accented Portuguese words should be correctly matched."""
        story = "O coração está aqui"
        translations = {"o": "the", "coração": "heart", "está": "is", "aqui": "here"}
        result = validate_translations(story, translations)
        assert result["all_passed"]

    def test_case_insensitive_keys(self):
        """Translations with uppercase keys should match lowercase words."""
        story = "Olá mundo"
        translations = {"olá": "hello", "mundo": "world"}
        result = validate_translations(story, translations)
        assert result["all_passed"]


class TestWordRegex:
    """Ensure the PT_WORD_RE extracts words correctly."""

    def test_basic_words(self):
        words = PT_WORD_RE.findall("O gato dorme.")
        assert "O" in words
        assert "gato" in words
        assert "dorme" in words

    def test_accented_words(self):
        words = PT_WORD_RE.findall("coração está bem")
        assert "coração" in words
        assert "está" in words
        assert "bem" in words

    def test_punctuation_excluded(self):
        words = PT_WORD_RE.findall("Sim! Não.")
        assert "!" not in words
        assert "." not in words

    def test_hyphenated_words(self):
        """Each part of a hyphenated word should be extracted."""
        words = PT_WORD_RE.findall("bem-estar")
        assert "bem" in words
        assert "estar" in words


# ===========================================================================
# INTEGRATION TESTS — require GEMINI_API_KEY
# ===========================================================================

def _skip_if_no_gemini():
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")


@pytest.mark.integration
class TestDateInspiration:

    def test_returns_non_empty_text(self):
        _skip_if_no_gemini()
        configure_gemini(os.environ["GEMINI_API_KEY"])
        result = get_date_inspiration(date(2026, 7, 4))
        assert isinstance(result, str)
        assert len(result) > 50

    def test_relevant_to_date(self):
        """July 4 inspiration should mention USA or Independence Day."""
        _skip_if_no_gemini()
        configure_gemini(os.environ["GEMINI_API_KEY"])
        result = get_date_inspiration(date(2026, 7, 4))
        lower = result.lower()
        assert any(kw in lower for kw in ["independence", "america", "usa", "july"]), (
            f"Expected July 4 reference in: {result[:300]}"
        )


@pytest.mark.integration
class TestEnglishStoryGeneration:

    def setup_method(self):
        _skip_if_no_gemini()
        configure_gemini(os.environ["GEMINI_API_KEY"])

    def test_word_count_in_range(self):
        inspiration = "1. Neil Armstrong walked on the Moon on July 20, 1969."
        story = generate_english_story(date(2026, 7, 20), inspiration)
        count = len(story["story"].split())
        assert 140 <= count <= 220, f"Word count {count} outside range"

    def test_required_fields_present(self):
        inspiration = "1. Marie Curie, physicist and chemist, born November 7, 1867."
        story = generate_english_story(date(2026, 11, 7), inspiration)
        assert story.get("topic")
        assert story.get("story")
        assert story.get("fun_fact")


@pytest.mark.integration
class TestFullPipeline:

    def test_pipeline_returns_complete_dict(self):
        _skip_if_no_gemini()
        result = run_story_pipeline(date(2026, 7, 4), os.environ["GEMINI_API_KEY"])

        # Required keys
        for key in ["date", "date_formatted", "title_pt", "story_en", "story_pt",
                    "word_translations", "fun_fact_pt", "validation"]:
            assert key in result, f"Missing key: {key}"

        # Portuguese story is non-trivial
        assert len(result["story_pt"]) > 100

        # Word translations exist
        assert isinstance(result["word_translations"], dict)
        assert len(result["word_translations"]) > 5

        # Translation coverage >= 85%
        coverage = result["validation"]["translations"]["coverage_pct"]
        assert coverage >= 85, f"Translation coverage too low: {coverage}%"

        print(f"\n✓ Story: '{result['title_pt']}'")
        print(f"✓ EN word count: {result['validation']['english']['word_count']}")
        print(f"✓ Translation coverage: {coverage}%")
        print(f"✓ PT preview: {result['story_pt'][:120]}...")
