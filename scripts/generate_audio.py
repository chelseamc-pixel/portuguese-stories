"""
generate_audio.py
-----------------
Generates MP3 audio files for each unique Portuguese word using ElevenLabs.

Key decisions:
- Uses eleven_multilingual_v2 model (best quality for European Portuguese)
- Generates one file per unique word (not per occurrence)
- File names are MD5 hashes of the word to avoid special-character issues
- Old audio files are deleted before generating new ones (keeps repo lean)
- Rate-limits calls to avoid hitting ElevenLabs concurrency limits

Debug tip: Set LOG_LEVEL=DEBUG to see per-word timing.
"""

import os
import re
import time
import random
import hashlib
import logging
from datetime import date
from pathlib import Path

from elevenlabs import ElevenLabs, VoiceSettings

logger = logging.getLogger(__name__)

# Regex matching Portuguese words (same as generate_story.py)
PT_WORD_RE = re.compile(r'\b[a-zA-ZáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]+\b')

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

# Use multilingual v2 for best European Portuguese quality
MODEL_ID = "eleven_multilingual_v2"

# ---------------------------------------------------------------------------
# European Portuguese voice roster (continental / Portugal accent only)
# Each entry: {"name": str, "id": str}
# One is picked per story date (deterministic seed = same day always = same voice).
# Override any day with ELEVENLABS_VOICE_ID env var (used in testing).
# ---------------------------------------------------------------------------

EUROPEAN_PT_VOICES = [
    {"name": "Maria",    "id": "iLelOQ6m5mpSeNH8fRob"},  # female — friendly, clear, storytelling
    {"name": "Joana",    "id": "nJ5NFqyKb8kn9JBPmo6i"},  # female — steady, warm, comforting
    {"name": "Marta",    "id": "bBNhdwrIjl4fcVYiRbT2"},  # female — middle-aged, warm, self-assured
    {"name": "Mariza",   "id": "zKjRewuiqTkXNUVAMwat"},  # female — clear, calm, friendly
    {"name": "Benedita", "id": "NkpT2jezTenCDRKHkWiX"},  # female — bright, inviting, welcoming
    {"name": "Paulo PT", "id": "aLFUti4k8YKvtQGXv0UO"},  # male   — Lisbon accent
    {"name": "Lourenço", "id": "Fij0Q07RV232HQv4oaiV"},  # male   — man from Lisbon
]

def pick_daily_voice(story_date: date | None = None) -> dict:
    """
    Pick a European Portuguese voice for the given date.
    Uses the date's ordinal as an RNG seed so the same date always returns
    the same voice (re-runs are reproducible), but it rotates every day.

    If ELEVENLABS_VOICE_ID env var is set, that ID is used instead (for testing).

    Returns {"name": str, "id": str}.
    """
    override_id = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if override_id:
        # Find the name in our roster if possible, else label it "Custom"
        match = next((v for v in EUROPEAN_PT_VOICES if v["id"] == override_id), None)
        return match or {"name": "Custom", "id": override_id}

    seed = story_date.toordinal() if story_date else None
    rng = random.Random(seed)
    return rng.choice(EUROPEAN_PT_VOICES)


# Used as the default parameter value in generate_word_audio / generate_all_audio
DEFAULT_VOICE_ID = EUROPEAN_PT_VOICES[0]["id"]

# Delay between ElevenLabs calls (seconds) to stay within rate limits
CALL_DELAY = 0.4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def word_to_filename(word: str) -> str:
    """
    Map a Portuguese word → safe, unique MP3 filename.
    Uses MD5 hash to handle accented chars and collisions.
    Example: "coração" → "word_a3f9c2.mp3"
    """
    h = hashlib.md5(word.lower().encode("utf-8")).hexdigest()[:10]
    return f"word_{h}.mp3"


def extract_unique_words(portuguese_story: str) -> list[str]:
    """Return sorted list of unique lowercase words in the story."""
    return sorted(set(w.lower() for w in PT_WORD_RE.findall(portuguese_story)))


# ---------------------------------------------------------------------------
# Core audio generation
# ---------------------------------------------------------------------------

def generate_word_audio(
    client: ElevenLabs,
    word: str,
    output_path: Path,
    voice_id: str = DEFAULT_VOICE_ID,
) -> bool:
    """
    Generate audio for a single word and save to output_path.
    Returns True on success, False on failure (logs the error).
    """
    try:
        audio_stream = client.text_to_speech.convert(
            text=word,
            voice_id=voice_id,
            model_id=MODEL_ID,
            voice_settings=VoiceSettings(
                stability=0.65,
                similarity_boost=0.80,
                style=0.0,
                use_speaker_boost=True,
            ),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in audio_stream:
                if chunk:
                    f.write(chunk)

        size = output_path.stat().st_size
        if size < 200:
            logger.warning(f"Audio for '{word}' suspiciously small ({size} bytes) — may be corrupt")
            return False

        logger.debug(f"  '{word}' → {output_path.name} ({size:,} bytes)")
        return True

    except Exception as e:
        logger.error(f"ElevenLabs error for '{word}': {e}")
        # Don't raise — let the caller decide whether to abort
        return False


def generate_all_audio(
    story_data: dict,
    audio_output_dir: Path,
    elevenlabs_api_key: str,
    voice_id: str = DEFAULT_VOICE_ID,
    call_delay: float = CALL_DELAY,
) -> dict:
    """
    Generate audio for all unique words in story_data['story_pt'].

    Cleans up old audio files first, then generates fresh ones.

    Returns:
        word_to_audio: {word_lowercase: "word_HASH.mp3"} for successfully generated words
    """
    client = ElevenLabs(api_key=elevenlabs_api_key)
    audio_output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Clean up old audio files ----
    old_files = list(audio_output_dir.glob("word_*.mp3"))
    if old_files:
        for f in old_files:
            f.unlink()
        logger.info(f"Removed {len(old_files)} old audio files")

    # ---- Extract words ----
    unique_words = extract_unique_words(story_data["story_pt"])
    total = len(unique_words)
    logger.info(f"Generating audio for {total} unique words with voice '{voice_id}'...")

    word_to_audio: dict[str, str] = {}
    success = 0
    failures: list[str] = []

    for i, word in enumerate(unique_words, 1):
        filename = word_to_filename(word)
        output_path = audio_output_dir / filename

        ok = generate_word_audio(client, word, output_path, voice_id)

        if ok:
            word_to_audio[word] = filename
            success += 1
        else:
            failures.append(word)

        # Progress log every 10 words
        if i % 10 == 0 or i == total:
            logger.info(f"  Progress: {i}/{total} | ✓ {success} | ✗ {len(failures)}")

        # Rate limit (skip delay after last word)
        if i < total:
            time.sleep(call_delay)

    logger.info(
        f"Audio generation complete: {success}/{total} succeeded"
        + (f" | Failed: {failures}" if failures else "")
    )
    return word_to_audio


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_audio_files(word_to_audio: dict, audio_dir: Path) -> dict:
    """
    Verify that every entry in word_to_audio has a corresponding file on disk
    with non-trivial size.
    """
    missing = []
    too_small = []
    ok_count = 0

    for word, filename in word_to_audio.items():
        path = audio_dir / filename
        if not path.exists():
            missing.append(word)
        elif path.stat().st_size < 200:
            too_small.append(word)
        else:
            ok_count += 1

    result = {
        "total": len(word_to_audio),
        "ok": ok_count,
        "missing_files": missing,
        "too_small": too_small,
        "all_passed": len(missing) == 0 and len(too_small) == 0,
    }

    if missing or too_small:
        logger.warning(f"Audio validation issues — missing: {missing}, too small: {too_small}")
    else:
        logger.info(f"Audio validation passed: {ok_count}/{len(word_to_audio)} files OK")

    return result
