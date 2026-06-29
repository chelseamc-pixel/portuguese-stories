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

To keep audio files after the run (e.g. for CI artifact upload), set:
    ELEVENLABS_TEST_OUTPUT_DIR=/path/to/dir
Otherwise files are written to a temp dir and deleted on exit.
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
    pick_daily_voice,
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


def run_elevenlabs_test(api_key: str, voice_id: str, voice_name: str = "",
                        audio_dir: Path | None = None) -> bool:
    """
    Generate audio for all words in the dry-run story and validate results.

    Args:
        api_key:    ElevenLabs API key
        voice_id:   ElevenLabs voice ID to use
        voice_name: Human-readable voice name (for logging)
        audio_dir:  Directory to write MP3s into. If None, uses a temp dir
                    that is deleted after this function returns.

    Returns True if all words have valid audio, False otherwise.
    """
    unique_words = extract_unique_words(DRY_RUN_PT_STORY)

    logger.info("=" * 56)
    logger.info("  ELEVENLABS AUDIO TEST")
    logger.info("=" * 56)
    logger.info(f"Story    : dry-run placeholder ({len(DRY_RUN_PT_STORY.split())} words)")
    logger.info(f"Unique   : {len(unique_words)} unique words to generate audio for")
    logger.info(f"Narrator : {voice_name} ({voice_id})")
    logger.info(f"Words    : {', '.join(sorted(unique_words))}")
    logger.info("=" * 56)

    def _run(out_dir: Path) -> bool:
        out_dir.mkdir(parents=True, exist_ok=True)

        # Generate audio
        logger.info("Generating audio files...")
        word_to_audio = generate_all_audio(
            STORY_DATA,
            out_dir,
            api_key,
            voice_id=voice_id,
            call_delay=0.3,
        )

        # Validate — must check expected count, not just the successful subset
        logger.info("Validating audio files...")
        validation = validate_audio_files(word_to_audio, out_dir)

        generated_count = len(word_to_audio)
        expected_count = len(unique_words)
        all_generated = generated_count == expected_count

        # Report
        logger.info("=" * 56)
        logger.info("RESULTS")
        logger.info("=" * 56)
        logger.info(f"Expected words : {expected_count}")
        logger.info(f"Generated OK   : {generated_count}")
        logger.info(f"Missing audio  : {expected_count - generated_count} words failed ElevenLabs call")
        logger.info(f"Missing files  : {validation['missing_files'] or 'none'}")
        logger.info(f"Too small      : {validation['too_small'] or 'none'}")

        if all_generated and validation["all_passed"]:
            logger.info("✓ ALL WORDS HAVE VALID AUDIO — ElevenLabs integration working!")
            if out_dir:
                logger.info(f"  Audio saved to: {out_dir}")
        else:
            if not all_generated:
                failed = [w for w in unique_words if w not in word_to_audio]
                logger.error(f"✗ {expected_count - generated_count} WORDS FAILED audio generation: {failed}")
            if not validation["all_passed"]:
                logger.error("✗ SOME GENERATED FILES ARE INVALID — see above for details")

        # Show file sizes for a sample
        sample = list(word_to_audio.items())[:5]
        if sample:
            logger.info("\nSample file sizes:")
            for word, filename in sample:
                filepath = out_dir / filename
                if filepath.exists():
                    logger.info(f"  '{word}' → {filepath.stat().st_size:,} bytes")

        logger.info("=" * 56)
        return all_generated and validation["all_passed"]

    if audio_dir is not None:
        return _run(audio_dir)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            return _run(Path(tmpdir) / "audio")


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

    # pick_daily_voice() handles the empty-string env var case correctly:
    # it uses ELEVENLABS_VOICE_ID only if non-empty, else picks from the roster.
    voice = pick_daily_voice()
    voice_id = voice["id"]
    voice_name = voice["name"]

    # If ELEVENLABS_TEST_OUTPUT_DIR is set, save audio there (for artifact upload).
    output_dir_env = os.environ.get("ELEVENLABS_TEST_OUTPUT_DIR", "").strip()
    audio_dir = Path(output_dir_env) if output_dir_env else None

    success = run_elevenlabs_test(api_key, voice_id, voice_name, audio_dir=audio_dir)
    sys.exit(0 if success else 1)
