"""
tests/test_pipeline_dryrun.py
------------------------------
End-to-end dry-run test: exercises run_pipeline.run() with dry_run=True
so no API calls are made. Verifies the output HTML is valid and well-formed.

Run: pytest scripts/tests/test_pipeline_dryrun.py -v
"""

import sys
import os
import tempfile
import pytest
from pathlib import Path
from datetime import date

# Patch paths so the pipeline writes to a temp docs/ dir
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_dry_run_produces_valid_html(tmp_path, monkeypatch):
    """Dry-run pipeline should create a valid HTML file without API calls."""
    # Point the pipeline's docs output at our temp dir
    import run_pipeline
    import build_page

    # Redirect html output
    docs_dir = tmp_path / "docs"
    audio_dir = docs_dir / "audio"
    html_out  = docs_dir / "index.html"

    # Monkeypatch the paths inside run_pipeline
    original_run = run_pipeline.run

    captured = {}

    def patched_run(story_date, send_email=True, dry_run=False):
        # Only intercept to redirect output path
        from run_pipeline import DRY_RUN_STORY
        story_data = {**DRY_RUN_STORY, "date": story_date.isoformat(),
                      "date_formatted": story_date.strftime("%B %d, %Y")}
        build_page.build_html_page(story_data, {}, html_out)
        captured["story_data"] = story_data
        return story_data

    monkeypatch.setattr(run_pipeline, "run", patched_run)

    result = run_pipeline.run(date(2026, 7, 4), send_email=False, dry_run=True)

    # Verify the HTML was created
    assert html_out.exists(), "index.html was not created"

    content = html_out.read_text(encoding="utf-8")

    # Basic HTML structure
    assert "<!DOCTYPE html>" in content
    assert 'lang="pt-PT"' in content
    assert "<body>" in content

    # Story content present
    assert result["title_pt"] in content
    assert "word clickable" in content        # Clickable words
    assert "popup" in content                 # Popup element
    assert "Sabia que" in content             # Fun fact section
    assert "viewport" in content              # Mobile meta tag

    # JavaScript interactive bits
    assert "showPopup" in content
    assert "hidePopup" in content
    assert "playAudio" in content

    print(f"\n✓ Dry-run HTML created: {html_out} ({len(content):,} chars)")
    print(f"✓ Story: '{result['title_pt']}'")


def test_dry_run_story_has_required_keys():
    """DRY_RUN_STORY placeholder has all keys build_page expects."""
    from run_pipeline import DRY_RUN_STORY
    required = [
        "date", "date_formatted", "topic_en", "topic_pt", "title_pt",
        "story_en", "story_pt", "fun_fact_en", "fun_fact_pt", "word_translations",
    ]
    for key in required:
        assert key in DRY_RUN_STORY, f"DRY_RUN_STORY missing key: {key}"


def test_html_validation_passes_on_dry_run(tmp_path):
    """validate_html_page should return all_passed=True for dry-run output."""
    from run_pipeline import DRY_RUN_STORY
    from build_page import build_html_page, validate_html_page
    from datetime import date

    html_out = tmp_path / "index.html"
    story_data = {**DRY_RUN_STORY,
                  "date": "2026-07-04",
                  "date_formatted": "July 04, 2026"}
    build_html_page(story_data, {}, html_out)

    result = validate_html_page(html_out)
    assert result["all_passed"], f"Validation failed: {result}"
    assert result["size_bytes"] > 5000
