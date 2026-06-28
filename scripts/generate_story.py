"""
generate_story.py
-----------------
Handles all Gemini API calls:
  1. Get date-based inspiration (notable events/people for the date)
  2. Generate a 150-200 word English story at a 5-year-old level
  3. Validate the story (word count, reading level)
  4. Translate to continental (European) Portuguese
  5. Get per-word English translations for the popup tooltips

Debug tip: Set LOG_LEVEL=DEBUG in your environment to see full API responses.
"""

import os
import re
import json
import logging
from datetime import date

from google import genai
import textstat

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

_client: genai.Client | None = None


def configure_gemini(api_key: str) -> None:
    """Configure the Gemini API client. Call once before any other functions."""
    global _client
    _client = genai.Client(api_key=api_key)
    logger.info("Gemini API configured")


def _get_client() -> genai.Client:
    if _client is None:
        raise RuntimeError("Call configure_gemini(api_key) before using story functions.")
    return _client


def _call_gemini(prompt: str, expect_json: bool = False, model_name: str = "gemini-2.0-flash") -> str:
    """
    Make a Gemini API call with basic error handling.
    If expect_json=True, strips markdown code fences before returning.
    """
    client = _get_client()
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        text = response.text.strip()
        logger.debug(f"Gemini raw response ({len(text)} chars): {text[:300]}{'...' if len(text) > 300 else ''}")

        if expect_json:
            # Strip ```json ... ``` or ``` ... ``` fences if present
            text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
            text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
            text = text.strip()

        return text
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Step 1: Date inspiration
# ---------------------------------------------------------------------------

def get_date_inspiration(story_date: date) -> str:
    """
    Ask Gemini for notable events/people associated with this calendar date.
    Returns a plain-text list we can pass to the story generator.
    """
    prompt = f"""List 5 notable historical events, famous people's birthdays, or cultural
celebrations associated with {story_date.strftime('%B %d')} (any year).

Focus on topics that make great stories for 5-year-olds: scientists, artists,
athletes, explorers, inventors, cultural festivals, space missions, etc.
Avoid violent events or complex political topics.

Format as a simple numbered list. Keep each item to one sentence."""

    result = _call_gemini(prompt)
    logger.info(f"Got date inspiration for {story_date.strftime('%B %d')}")
    logger.debug(f"Inspiration:\n{result}")
    return result


# ---------------------------------------------------------------------------
# Step 2: Generate English story
# ---------------------------------------------------------------------------

def generate_english_story(story_date: date, inspiration: str) -> dict:
    """
    Generate a 150-200 word English children's story based on the date inspiration.
    Returns a dict with keys: topic, story, word_count, fun_fact
    """
    prompt = f"""Write a short story for a 5-year-old child based on the inspiration below for {story_date.strftime('%B %d')}.

INSPIRATION:
{inspiration}

REQUIREMENTS:
- Pick ONE topic from above that makes the most engaging story for a small child
- The story must be between 150 and 200 words — count carefully
- Use simple vocabulary and short sentences (5-year-old level)
- Structure: clear beginning, middle, and end
- Tone: warm, positive, educational, age-appropriate
- No violence, scary content, or complex political ideas

Return ONLY a JSON object (no markdown fences) with exactly these fields:
{{
  "topic": "brief description of chosen topic (e.g. 'Neil Armstrong walks on the Moon')",
  "story": "the complete story text",
  "word_count": <integer count of words in story>,
  "fun_fact": "one simple fun fact a 5-year-old would love, related to the story"
}}"""

    raw = _call_gemini(prompt, expect_json=True)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed. Raw response:\n{raw}")
        raise ValueError(f"Gemini returned invalid JSON: {e}") from e

    # Recount words ourselves — don't trust the model's count
    actual_count = len(data["story"].split())
    data["word_count"] = actual_count
    logger.info(f"English story generated: '{data['topic']}' — {actual_count} words")
    return data


# ---------------------------------------------------------------------------
# Step 3: Validate English story
# ---------------------------------------------------------------------------

def validate_english_story(story_data: dict) -> dict:
    """
    Validate word count and reading level.
    Returns a checks dict. Key 'all_passed' is True only if critical checks pass.
    """
    story = story_data.get("story", "")
    word_count = len(story.split())

    # Word count check (allow slight margin for model variation)
    count_ok = 140 <= word_count <= 220

    # Reading level (Flesch-Kincaid grade; ≤3 is good for 5-year-olds)
    try:
        grade = textstat.flesch_kincaid_grade(story)
    except Exception:
        grade = None

    checks = {
        "word_count": word_count,
        "word_count_ok": count_ok,
        "grade_level": grade,
        "reading_level_ok": (grade is None) or (grade <= 4.0),
        "has_topic": bool(story_data.get("topic", "").strip()),
        "has_fun_fact": bool(story_data.get("fun_fact", "").strip()),
    }
    checks["all_passed"] = checks["word_count_ok"] and checks["has_topic"] and checks["has_fun_fact"]

    if not count_ok:
        logger.warning(f"Word count {word_count} outside 140-220 range")
    if grade and grade > 4.0:
        logger.warning(f"Reading level grade {grade:.1f} may be high for a 5-year-old")

    logger.info(
        f"Story validation — words: {word_count}, grade: {grade}, passed: {checks['all_passed']}"
    )
    return checks


# ---------------------------------------------------------------------------
# Step 4: Translate to continental Portuguese
# ---------------------------------------------------------------------------

def translate_to_portuguese(story_data: dict) -> dict:
    """
    Translate the English story to continental (European) Portuguese.
    Returns dict with keys: story_pt, topic_pt, fun_fact_pt, title_pt
    """
    prompt = f"""Translate the following English children's story into continental Portuguese
(European Portuguese as spoken in Portugal — NOT Brazilian Portuguese).

Rules:
- Use European Portuguese vocabulary, spelling, and grammar (e.g. "autocarro" not "ônibus")
- Keep the vocabulary simple — suitable for a 5-year-old
- Maintain the warm, engaging tone
- Also translate the topic, fun fact, and create a short title

English story:
\"\"\"{story_data['story']}\"\"\"

Topic: {story_data['topic']}
Fun fact: {story_data['fun_fact']}

Return ONLY a JSON object (no markdown fences) with exactly these fields:
{{
  "story_pt": "complete story in continental Portuguese",
  "topic_pt": "topic in continental Portuguese",
  "fun_fact_pt": "fun fact in continental Portuguese",
  "title_pt": "a short engaging story title in continental Portuguese (5-8 words)"
}}"""

    raw = _call_gemini(prompt, expect_json=True)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Translation JSON parse failed. Raw:\n{raw}")
        raise ValueError(f"Gemini returned invalid JSON for translation: {e}") from e

    logger.info(f"Translated to Portuguese: '{data['title_pt']}'")
    logger.debug(f"PT story preview: {data['story_pt'][:100]}...")
    return data


# ---------------------------------------------------------------------------
# Step 5: Per-word translations
# ---------------------------------------------------------------------------

# Regex for Portuguese words (includes accented characters)
PT_WORD_RE = re.compile(r'\b[a-zA-ZáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]+\b')


def get_word_translations(portuguese_story: str) -> dict:
    """
    Get English translations for every unique word in the Portuguese story.
    Returns {word_lowercase: english_translation}.
    """
    unique_words = sorted(set(
        w.lower() for w in PT_WORD_RE.findall(portuguese_story)
    ))
    logger.info(f"Fetching translations for {len(unique_words)} unique words")

    # Batch them — Gemini handles 100+ words fine in one call
    prompt = f"""For each continental Portuguese word below, give a simple English translation
appropriate for a children's context.

Words: {', '.join(unique_words)}

Return ONLY a JSON object (no markdown fences) where:
- Keys are the exact words as given (lowercase)
- Values are their English translations (short, 1-3 words)

Example format:
{{
  "gato": "cat",
  "bonito": "beautiful",
  "e": "and"
}}"""

    raw = _call_gemini(prompt, expect_json=True)

    try:
        translations = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Word translations JSON parse failed. Raw:\n{raw}")
        raise ValueError(f"Gemini returned invalid JSON for word translations: {e}") from e

    # Normalise keys to lowercase
    translations = {k.lower(): v for k, v in translations.items()}
    logger.info(f"Received translations for {len(translations)}/{len(unique_words)} words")
    return translations


def validate_translations(portuguese_story: str, translations: dict) -> dict:
    """
    Check that every word in the story has a translation entry.
    """
    story_words = {w.lower() for w in PT_WORD_RE.findall(portuguese_story)}
    missing = sorted(story_words - set(translations.keys()))
    coverage = len(story_words - set(missing)) / len(story_words) * 100 if story_words else 100

    checks = {
        "total_unique_words": len(story_words),
        "words_translated": len(story_words) - len(missing),
        "missing": missing,
        "coverage_pct": round(coverage, 1),
        "all_passed": len(missing) == 0,
    }

    if missing:
        logger.warning(f"Missing translations ({len(missing)}): {missing}")
    else:
        logger.info(f"All {len(story_words)} words have translations")

    return checks


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_story_pipeline(story_date: date, gemini_api_key: str, max_retries: int = 3) -> dict:
    """
    Run the full story generation pipeline for a given date.

    Returns a dict with all data needed by build_page.py:
      date, date_formatted, topic_en, topic_pt, title_pt,
      story_en, story_pt, fun_fact_en, fun_fact_pt,
      word_translations, validation
    """
    configure_gemini(gemini_api_key)

    logger.info(f"{'='*50}")
    logger.info(f"Story pipeline starting for {story_date.isoformat()}")
    logger.info(f"{'='*50}")

    # 1. Date inspiration
    logger.info("[1/5] Getting date inspiration...")
    inspiration = get_date_inspiration(story_date)

    # 2. Generate English story (retry if word count is off)
    logger.info("[2/5] Generating English story...")
    story_data = None
    validation = None
    for attempt in range(1, max_retries + 1):
        story_data = generate_english_story(story_date, inspiration)
        validation = validate_english_story(story_data)
        if validation["word_count_ok"]:
            break
        logger.warning(
            f"Attempt {attempt}/{max_retries}: word count {validation['word_count']} "
            f"outside range — retrying..."
        )
    else:
        raise RuntimeError(
            f"Failed to get correct word count after {max_retries} attempts. "
            f"Last count: {validation['word_count']}"
        )

    # 3. Translate
    logger.info("[3/5] Translating to continental Portuguese...")
    pt_data = translate_to_portuguese(story_data)

    # 4. Word-level translations
    logger.info("[4/5] Getting per-word translations...")
    word_translations = get_word_translations(pt_data["story_pt"])
    translation_validation = validate_translations(pt_data["story_pt"], word_translations)

    # If coverage is below 90%, try fetching just the missing words
    if translation_validation["missing"] and translation_validation["coverage_pct"] < 90:
        logger.info(f"[4/5] Fetching {len(translation_validation['missing'])} missing translations...")
        missing_prompt = f"""Translate these continental Portuguese words to English (children's context):

Words: {', '.join(translation_validation['missing'])}

Return ONLY a JSON object (no markdown fences): {{"word": "translation", ...}}"""
        try:
            raw_missing = _call_gemini(missing_prompt, expect_json=True)
            extra = {k.lower(): v for k, v in json.loads(raw_missing).items()}
            word_translations.update(extra)
            translation_validation = validate_translations(pt_data["story_pt"], word_translations)
        except Exception as e:
            logger.warning(f"Could not fetch missing translations: {e}")

    # 5. Compile result
    logger.info("[5/5] Compiling result...")
    result = {
        "date": story_date.isoformat(),
        "date_formatted": story_date.strftime("%B %d, %Y"),
        "topic_en": story_data["topic"],
        "topic_pt": pt_data["topic_pt"],
        "title_pt": pt_data["title_pt"],
        "story_en": story_data["story"],
        "story_pt": pt_data["story_pt"],
        "fun_fact_en": story_data["fun_fact"],
        "fun_fact_pt": pt_data["fun_fact_pt"],
        "word_translations": word_translations,
        "validation": {
            "english": validation,
            "translations": translation_validation,
        },
    }

    logger.info(f"Pipeline complete: '{result['title_pt']}' | "
                f"{validation['word_count']} words EN | "
                f"{translation_validation['coverage_pct']}% words translated")
    return result
