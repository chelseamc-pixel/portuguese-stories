"""
test_elevenlabs.py
------------------
Isolated test for ElevenLabs audio generation.

Uses the dry-run placeholder story (no Gemini calls needed) to generate
audio for every unique Portuguese word and validates each file.

Run locally:
    ELEVENLABS_API_KEY=your_key python scripts/tests/test_elevenlabs.py

Run via GitHub Actions:
    Actions → Test ElevenLabs Audio → Run workflow
"""

import os
import sys
import logging
import tempfile
from pathlib import Path

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_audio import (
    generate_all_audio,
    validate_audio_files,
    extract_unique_words,
    DEFAULT_VOICE_ID,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("test_elevenlabs")

# ---------------------------------------------------------------------------
# The dry-run Portuguese story — same words as the placeholder page
# ---------------------------------------------------------------------------
DRY_RUN_PT_STORY = (
    "Era uma vez um pequeno gato chamado Mimi que vivia num jardim encantado. "
    "O jardim estava cheio de flores coloridas e borboletas a voar. "
    "Todos os dias, Mimi brincava entre as flores e saltava atrás das borboletas. "
    "Um dia, Mimi encontrou uma borboleta azul muito especial. "
    "A borboleta disse: — Olá, Mimi! Queres voar comigo? "
    "O gato ficou muito contente e os dois tornaram-se grandes amigos. "
    "E viveram felizes para sempre no jardim encantado."
)

STORY_DATA = {"story_pt": DRY_RUN_PT_STORY}


def run_elevenlabs_test(api_key: str, voice_id: str) -> bool:
    """
    Generate audio for all words in the dry-run story and validate results.
    Returns True if all words have valid audio, False otherwise.
    """
    unique_words = extract_unique_words(DRY_RUN_PT_STORY)

    logger.info("=" * 56)
    logger.info("  ELEVENLABS AUDIO TEST")
    logger.info("=" * 56)
    logger.info(f"Story    : dry-run placeholder ({len(DRY_RUN_PT_STORY.split())} words)")
    logger.info(f"Unique   : {len(unique_words)} unique words to generate audio for")
    logger.info(f"Voice ID : {voice_id}")
    logger.info(f"Words    : {', '.join(sorted(unique_words))}")
    logger.info("=" * 56)

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_dir = Path(tmpdir) / "audio"

        # Generate audio
        logger.info("Generating audio files...")
        word_to_audio = generate_all_audio(
            STORY_DATA,
            audio_dir,
            api_key,
            voice_id=voice_id,
            call_delay=0.3,
        )

        # Validate
        logger.info("Validating audio files...")
        validation = validate_audio_files(word_to_audio, audio_dir)

        # Report
        logger.info("=" * 56)
        logger.info("RESULTS")
        logger.info("=" * 56)
        logger.info(f"Total words  : {validation['total']}")
        logger.info(f"Generated OK : {validation['ok']}")
        logger.info(f"Missing files: {validation['missing_files'] or 'none'}")
        logger.info(f"Too small    : {validation['too_small'] or 'none'}")

        if validation["all_passed"]:
            logger.info("✓ ALL WORDS HAVE VALID AUDIO — ElevenLabs integration working!")
        else:
            logger.error("✗ SOME WORDS FAILED — see above for details")

        # Show file sizes for a sample
        sample = list(word_to_audio.items())[:5]
        logger.info("\nSample file sizes:")
        for word, filename in sample:
            filepath = audio_dir / filename
            if filepath.exists():
                logger.info(f"  '{word}' → {filepath.stat().st_size:,} bytes")

        logger.info("=" * 56)
        return validation["all_passed"]


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        logger.error("ELEVENLABS_API_KEY is not set. Export it or add it to .env")
        sys.exit(1)

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID).strip()

    success = run_elevenlabs_test(api_key, voice_id)
    sys.exit(0 if success else 1)
