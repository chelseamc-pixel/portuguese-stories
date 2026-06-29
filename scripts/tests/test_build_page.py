"""
tests/test_build_page.py
------------------------
Tests for HTML page building and tokenisation.
All tests run without API calls.

Run: pytest scripts/tests/test_build_page.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from build_page import tokenize_story, render_story_html, build_html_page, validate_html_page


# ---------------------------------------------------------------------------
# Tokeniser tests
# ---------------------------------------------------------------------------

class TestTokenizeStory:

    def test_basic_split(self):
        tokens = tokenize_story("Olá, mundo!")
        types = [t["type"] for t in tokens]
        texts = [t["text"] for t in tokens]
        assert "word" in types
        assert "other" in types
        assert "Olá" in texts
        assert "mundo" in texts

    def test_all_tokens_cover_input(self):
        """Reassembling tokens should reproduce the original text."""
        original = "Era uma vez um pequeno gato."
        tokens = tokenize_story(original)
        reassembled = "".join(t["text"] for t in tokens)
        assert reassembled == original

    def test_accented_words_are_word_tokens(self):
        tokens = tokenize_story("coração está aqui")
        word_texts = {t["text"] for t in tokens if t["type"] == "word"}
        assert "coração" in word_texts
        assert "está" in word_texts

    def test_punctuation_is_other(self):
        tokens = tokenize_story("Sim!")
        other_texts = "".join(t["text"] for t in tokens if t["type"] == "other")
        assert "!" in other_texts

    def test_empty_string(self):
        tokens = tokenize_story("")
        assert tokens == []

    def test_numbers_are_other(self):
        tokens = tokenize_story("Tinha 3 gatos")
        word_texts = {t["text"] for t in tokens if t["type"] == "word"}
        assert "3" not in word_texts

    def test_newlines_preserved_in_other(self):
        tokens = tokenize_story("Olá\nmundo")
        reassembled = "".join(t["text"] for t in tokens)
        assert "\n" in reassembled


# ---------------------------------------------------------------------------
# render_story_html tests
# ---------------------------------------------------------------------------

class TestRenderStoryHtml:

    def _tokens(self, text):
        return tokenize_story(text)

    def test_word_with_translation_gets_clickable(self):
        tokens = self._tokens("gato")
        html = render_story_html(tokens, {}, {"gato": "cat"})
        assert 'class="word clickable"' in html
        assert 'data-translation="cat"' in html

    def test_word_with_audio_gets_data_audio(self):
        tokens = self._tokens("gato")
        html = render_story_html(tokens, {"gato": "word_abc.mp3"}, {})
        assert 'data-audio="audio/word_abc.mp3"' in html

    def test_word_without_translation_not_clickable(self):
        tokens = self._tokens("xyz")
        html = render_story_html(tokens, {}, {})
        assert 'class="word"' in html
        assert 'clickable' not in html

    def test_special_chars_escaped_in_translation(self):
        tokens = self._tokens("gato")
        html = render_story_html(tokens, {}, {"gato": 'cat "meow"'})
        # Double-quotes inside attribute should be escaped
        assert '&quot;' in html
        assert 'cat &quot;meow&quot;' in html

    def test_html_injection_in_word_escaped(self):
        """A word that looks like HTML should be escaped."""
        # Manually create a malicious token
        tokens = [{"type": "word", "text": "<script>"}]
        # Our regex won't produce this, but defence in depth
        html = render_story_html(tokens, {}, {"<script>": "bad"})
        assert "<script>" not in html

    def test_punctuation_preserved(self):
        tokens = self._tokens("Olá, mundo!")
        html = render_story_html(tokens, {}, {"olá": "hello", "mundo": "world"})
        assert "," in html
        assert "!" in html


# ---------------------------------------------------------------------------
# build_html_page + validate_html_page
# ---------------------------------------------------------------------------

SAMPLE_STORY = {
    "date": "2026-07-04",
    "date_formatted": "July 04, 2026",
    "topic_en": "Independence Day",
    "topic_pt": "Dia da Independência",
    "title_pt": "A Bandeira das Estrelas",
    "story_en": "Once upon a time there was a flag.",
    "story_pt": "Era uma vez uma bandeira com estrelas e riscas coloridas.",
    "fun_fact_en": "The US flag has 50 stars.",
    "fun_fact_pt": "A bandeira dos EUA tem 50 estrelas.",
    "word_translations": {
        "era": "was", "uma": "a", "vez": "time", "bandeira": "flag",
        "com": "with", "estrelas": "stars", "e": "and", "riscas": "stripes",
        "coloridas": "colourful",
    },
    "validation": {},
}


class TestBuildHtmlPage:

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "docs" / "index.html"
            build_html_page(SAMPLE_STORY, {"bandeira": "word_abc.mp3"}, out)
            assert out.exists()

    def test_file_is_non_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            assert out.stat().st_size > 5000

    def test_title_in_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            content = out.read_text(encoding="utf-8")
            assert "A Bandeira das Estrelas" in content

    def test_portuguese_story_in_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            content = out.read_text(encoding="utf-8")
            assert "bandeira" in content

    def test_fun_fact_in_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            content = out.read_text(encoding="utf-8")
            assert "50 estrelas" in content

    def test_clickable_words_in_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            content = out.read_text(encoding="utf-8")
            assert 'class="word clickable"' in content

    def test_audio_refs_when_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {"bandeira": "word_abc.mp3"}, out)
            content = out.read_text(encoding="utf-8")
            assert 'data-audio="audio/word_abc.mp3"' in content

    def test_valid_html_lang_attribute(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            content = out.read_text(encoding="utf-8")
            assert 'lang="pt-PT"' in content

    def test_mobile_viewport_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            content = out.read_text(encoding="utf-8")
            assert "viewport" in content


class TestValidateHtmlPage:

    def test_valid_page_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            build_html_page(SAMPLE_STORY, {}, out)
            result = validate_html_page(out)
            assert result["all_passed"], f"Unexpected failures: {result}"

    def test_missing_file_fails(self):
        result = validate_html_page(Path("/nonexistent/path/index.html"))
        assert not result["all_passed"]
        assert "error" in result

    def test_empty_file_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "index.html"
            out.write_text("")
            result = validate_html_page(out)
            assert not result["all_passed"]
