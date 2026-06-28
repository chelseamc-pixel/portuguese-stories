"""
run_pipeline.py
---------------
Main entry point. Chains all pipeline stages in order:
  1. Generate story (Gemini)
  2. Generate audio (ElevenLabs)
  3. Build HTML page
  4. Send email (Gmail SMTP)

Usage:
  python scripts/run_pipeline.py                    # Run for today
  python scripts/run_pipeline.py --date 2026-07-04  # Specific date
  python scripts/run_pipeline.py --no-email          # Skip email
  python scripts/run_pipeline.py --no-audio          # Skip ElevenLabs audio generation
  python scripts/run_pipeline.py --dry-run           # Skip all API calls (test structure)
  python scripts/run_pipeline.py --test-email        # Only test SMTP credentials
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import date

# ---------------------------------------------------------------------------
# Setup logging before any imports so module-level loggers are configured
# ---------------------------------------------------------------------------
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("run_pipeline")

# Add scripts/ to path so sibling modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from generate_story import run_story_pipeline
from generate_audio import generate_all_audio, validate_audio_files, DEFAULT_VOICE_ID
from build_page import build_html_page, validate_html_page
from send_email import send_story_email, test_smtp_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load .env for local development. Silently skip if dotenv not installed."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.debug("Loaded .env file")
    except ImportError:
        pass


def _require_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Add it to your .env file (local) or GitHub Secrets (CI)."
        )
    return val


def _divider(label: str = "") -> None:
    line = "=" * 56
    logger.info(line)
    if label:
        logger.info(f"  {label}")
        logger.info(line)


# ---------------------------------------------------------------------------
# Dry-run story (no API calls)
# ---------------------------------------------------------------------------

DRY_RUN_STORY = {
    "date": None,
    "date_formatted": None,
    "topic_en": "Dry Run Test",
    "topic_pt": "Execução de Teste",
    "title_pt": "O Gato e o Jardim Encantado",
    "story_en": "This is a dry-run story.",
    "story_pt": (
        "Era uma vez um pequeno gato chamado Mimi que vivia num jardim encantado. "
        "O jardim estava cheio de flores coloridas e borboletas a voar. "
        "Todos os dias, Mimi brincava entre as flores e saltava atrás das borboletas. "
        "Um dia, Mimi encontrou uma borboleta azul muito especial. "
        "A borboleta disse: — Olá, Mimi! Queres voar comigo? "
        "O gato ficou muito contente e os dois tornaram-se grandes amigos. "
        "E viveram felizes para sempre no jardim encantado."
    ),
    "fun_fact_en": "Cats can jump up to six times their body length!",
    "fun_fact_pt": "Os gatos conseguem saltar até seis vezes o comprimento do seu corpo!",
    "word_translations": {
        "era": "was", "uma": "a", "vez": "time", "um": "a", "pequeno": "small",
        "gato": "cat", "chamado": "called", "mimi": "Mimi", "que": "that",
        "vivia": "lived", "num": "in a", "jardim": "garden", "encantado": "enchanted",
        "o": "the", "estava": "was", "cheio": "full", "de": "of", "flores": "flowers",
        "coloridas": "colourful", "e": "and", "borboletas": "butterflies", "a": "to",
        "voar": "fly", "todos": "every", "os": "the", "dias": "days", "brincava": "played",
        "entre": "among", "saltava": "jumped", "atrás": "after", "das": "of the",
        "dia": "day", "encontrou": "found", "azul": "blue", "muito": "very",
        "especial": "special", "disse": "said", "olá": "hello", "queres": "do you want",
        "comigo": "with me", "ficou": "became", "contente": "happy", "dois": "two",
        "tornaram": "became", "se": "each other", "grandes": "great", "amigos": "friends",
        "viveram": "lived", "felizes": "happily", "para": "for", "sempre": "ever",
        "no": "in the",
    },
    "validation": {
        "english": {"word_count": 42, "word_count_ok": True, "all_passed": True},
        "translations": {"coverage_pct": 100.0, "all_passed": True},
    },
}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(story_date: date, send_email: bool = True, skip_audio: bool = False, dry_run: bool = False) -> dict:
    """
    Run the full pipeline for story_date.

    Args:
        story_date:  Date to generate story for
        send_email:  Whether to send the nightly email
        skip_audio:  If True, skip ElevenLabs audio generation (words won't have audio)
        dry_run:     If True, skip all API calls (uses placeholder story)

    Returns story_data dict (useful for tests / programmatic use).
    """
    _load_dotenv()

    # Paths
    repo_root = Path(__file__).parent.parent
    docs_dir  = repo_root / "docs"
    audio_dir = docs_dir / "audio"
    html_out  = docs_dir / "index.html"

    github_username = os.environ.get("GITHUB_USERNAME", "chelseamc-pixel")
    github_repo     = os.environ.get("GITHUB_REPO", "portuguese-stories")
    story_url       = f"https://{github_username}.github.io/{github_repo}/"

    _divider("PORTUGUESE STORY PIPELINE")
    logger.info(f"Date      : {story_date.isoformat()}")
    logger.info(f"Story URL : {story_url}")
    logger.info(f"Dry run   : {dry_run}")
    logger.info(f"Skip audio: {skip_audio}")
    _divider()

    # ---- STEP 1: Story generation ----
    if dry_run:
        logger.info("[STEP 1] DRY RUN — using placeholder story")
        story_data = {**DRY_RUN_STORY, "date": story_date.isoformat(),
                      "date_formatted": story_date.strftime("%B %d, %Y")}
        word_to_audio = {}
    else:
        logger.info("[STEP 1] Generating story via Gemini...")
        gemini_key = _require_env("GEMINI_API_KEY")
        story_data = run_story_pipeline(story_date, gemini_key)
        logger.info(f"         ✓ '{story_data['title_pt']}' | "
                    f"{story_data['validation']['english']['word_count']} words EN")

        # ---- STEP 2: Audio generation ----
        if skip_audio:
            logger.info("[STEP 2] Audio skipped (--no-audio)")
            word_to_audio = {}
        else:
            logger.info("[STEP 2] Generating audio via ElevenLabs...")
            el_key   = _require_env("ELEVENLABS_API_KEY")
            voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE_ID)
            word_to_audio = generate_all_audio(story_data, audio_dir, el_key, voice_id)

            audio_val = validate_audio_files(word_to_audio, audio_dir)
            logger.info(f"         ✓ {audio_val['ok']}/{audio_val['total']} audio files generated")
            if not audio_val["all_passed"]:
                logger.warning(f"         ⚠ Missing audio for: {audio_val['missing_files']}")

    # ---- STEP 3: Build HTML page ----
    logger.info("[STEP 3] Building HTML page...")
    build_html_page(story_data, word_to_audio, html_out)
    html_val = validate_html_page(html_out)
    if not html_val["all_passed"]:
        logger.error(f"HTML validation failed: {html_val}")
        sys.exit(1)
    logger.info(f"         ✓ {html_out} ({html_val['size_bytes']:,} bytes)")

    # ---- STEP 4: Send email ----
    if dry_run or not send_email:
        reason = "DRY RUN" if dry_run else "--no-email"
        logger.info(f"[STEP 4] Email skipped ({reason})")
    else:
        logger.info("[STEP 4] Sending email via Gmail SMTP...")
        gmail_user  = _require_env("GMAIL_USER")
        gmail_pass  = _require_env("GMAIL_APP_PASSWORD")
        recipient   = os.environ.get("RECIPIENT_EMAIL", gmail_user)
        send_story_email(gmail_user, gmail_pass, recipient, story_url, story_data)
        logger.info(f"         ✓ Email sent to {recipient}")

    _divider("PIPELINE COMPLETE ✓")
    logger.info(f"Open: {story_url}")
    _divider()

    return story_data


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and deliver today's Portuguese children's story."
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Override date (YYYY-MM-DD). Default: today."
    )
    parser.add_argument(
        "--no-email", action="store_true",
        help="Build page but skip sending the email."
    )
    parser.add_argument(
        "--no-audio", action="store_true",
        help="Skip ElevenLabs audio generation (words clickable but no sound)."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip all API calls; use a placeholder story (tests page structure)."
    )
    parser.add_argument(
        "--test-email", action="store_true",
        help="Only test Gmail SMTP credentials and exit."
    )
    args = parser.parse_args()

    _load_dotenv()

    if args.test_email:
        gmail_user = _require_env("GMAIL_USER")
        gmail_pass = _require_env("GMAIL_APP_PASSWORD")
        ok = test_smtp_connection(gmail_user, gmail_pass)
        sys.exit(0 if ok else 1)

    story_date = date.fromisoformat(args.date) if args.date else date.today()
    run(story_date, send_email=not args.no_email, skip_audio=args.no_audio, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
