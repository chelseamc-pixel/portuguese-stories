"""
build_page.py
-------------
Builds the self-contained HTML page from story data and audio file map.

The page:
  - Is mobile-first and works without a server (pure HTML/CSS/JS)
  - Wraps every Portuguese word (including the title) in a clickable <span>
  - On tap: shows a bottom-sheet popup with the word + English translation
  - Tapping the speaker button in the popup plays the word's MP3 audio
  - EN/PT toggle button swaps the full story to the English version
"""

import re
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Regex for Portuguese words (same across all modules)
PT_WORD_RE = re.compile(r'([a-zA-ZáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]+)')


# ---------------------------------------------------------------------------
# Tokenisation
# ---------------------------------------------------------------------------

def tokenize_story(text: str) -> list[dict]:
    """
    Split story text into alternating word / non-word tokens.
    Each token: {'type': 'word'|'other', 'text': str}
    """
    tokens = []
    last_end = 0
    for m in PT_WORD_RE.finditer(text):
        if m.start() > last_end:
            tokens.append({"type": "other", "text": text[last_end:m.start()]})
        tokens.append({"type": "word", "text": m.group()})
        last_end = m.end()
    if last_end < len(text):
        tokens.append({"type": "other", "text": text[last_end:]})
    return tokens


def _escape(text: str) -> str:
    """Minimal HTML escaping for text nodes."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attr_escape(text: str) -> str:
    """Escape for use inside HTML attribute values (double-quoted)."""
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


# ---------------------------------------------------------------------------
# HTML story renderer
# ---------------------------------------------------------------------------

def render_story_html(tokens: list[dict], word_to_audio: dict, word_translations: dict) -> str:
    """
    Build the inner HTML of the story div.
    Words with translations/audio get class="word clickable" and data attributes.
    Other words get class="word" only.
    """
    parts = []
    for token in tokens:
        if token["type"] != "word":
            parts.append(_escape(token["text"]))
            continue

        word = token["text"]
        wl = word.lower()
        translation = word_translations.get(wl)
        audio_file = word_to_audio.get(wl)

        attrs = ['class="word' + (' clickable' if (translation or audio_file) else '') + '"']
        if translation:
            attrs.append(f'data-translation="{_attr_escape(translation)}"')
        if audio_file:
            attrs.append(f'data-audio="audio/{audio_file}"')

        parts.append(f'<span {" ".join(attrs)}>{_escape(word)}</span>')

    return "".join(parts)


# ---------------------------------------------------------------------------
# Full page builder
# ---------------------------------------------------------------------------

def build_html_page(
    story_data: dict,
    word_to_audio: dict,
    output_path: Path,
) -> None:
    """
    Write the complete mobile-optimised story page to output_path.

    Args:
        story_data:    dict from run_story_pipeline()
        word_to_audio: {word: filename} from generate_all_audio()
        output_path:   where to write the .html file (usually docs/index.html)
    """
    translations = story_data["word_translations"]

    # Story body
    story_tokens = tokenize_story(story_data["story_pt"])
    story_html = render_story_html(story_tokens, word_to_audio, translations)

    # Title (same clickable treatment — words in the title that also appear
    # in the story will have translations and audio)
    title_tokens = tokenize_story(story_data["title_pt"])
    title_html = render_story_html(title_tokens, word_to_audio, translations)

    # Metadata embedded as JSON for JavaScript to read
    meta_json = json.dumps({
        "date": story_data["date"],
        "date_formatted": story_data["date_formatted"],
        "topic_en": story_data["topic_en"],
        "topic_pt": story_data["topic_pt"],
        "title_pt": story_data["title_pt"],
        "story_en": story_data.get("story_en", ""),
    }, ensure_ascii=False)

    topic_en_escaped = _escape(story_data["topic_en"])
    date_escaped = _escape(story_data["date_formatted"])
    fun_fact_escaped = _escape(story_data["fun_fact_pt"])
    narrator = story_data.get("narrator", "")
    narrator_html = f" &middot; {_escape(narrator)}" if narrator else ""

    html = f"""<!DOCTYPE html>
<html lang="pt-PT">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta name="theme-color" content="#f7f4ee">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <title>{_escape(story_data["title_pt"])}</title>
  <style>
    *, *::before, *::after {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      -webkit-tap-highlight-color: transparent;
    }}

    :root {{
      --green: #2c5f2e;
      --green-light: #e8f5e9;
      --green-mid: #3d7a3f;
      --bg: #f7f4ee;
      --surface: #ffffff;
      --text: #1c1c1e;
      --text-muted: #6e6e73;
      --popup-bg: #1c1c1e;
      --popup-text: #f5f5f7;
      --popup-sub: #aeaeb2;
      --radius: 16px;
    }}

    html, body {{
      height: 100%;
      background: var(--bg);
      color: var(--text);
      font-family: 'Georgia', 'Times New Roman', serif;
      -webkit-font-smoothing: antialiased;
    }}

    /* ---- Header ---- */
    .header {{
      position: sticky;
      top: 0;
      z-index: 200;
      background: var(--green);
      color: #fff;
      padding: 14px 20px 16px;
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }}
    .header-main {{ flex: 1; min-width: 0; }}
    .header-eyebrow {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.6px;
      text-transform: uppercase;
      opacity: 0.75;
    }}
    .header-title {{
      font-size: 19px;
      font-weight: 700;
      margin-top: 5px;
      line-height: 1.3;
    }}

    /* Clickable words inside the title (white text context) */
    .header-title .word.clickable {{
      cursor: pointer;
      border-radius: 4px;
      padding: 1px 0;
      transition: background 0.12s;
    }}
    .header-title .word.clickable:active {{
      background: rgba(255,255,255,0.18);
    }}
    .header-title .word.active {{
      background: rgba(255,255,255,0.22);
    }}

    /* EN/PT toggle button */
    .toggle-btn {{
      flex-shrink: 0;
      background: transparent;
      border: 1.5px solid rgba(255,255,255,0.55);
      color: rgba(255,255,255,0.9);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.5px;
      padding: 5px 11px;
      border-radius: 20px;
      cursor: pointer;
      transition: background 0.15s, color 0.15s, border-color 0.15s;
      margin-top: 2px;
    }}
    .toggle-btn.en-active {{
      background: rgba(255,255,255,0.9);
      color: var(--green);
      border-color: transparent;
    }}

    /* ---- Story ---- */
    .story-wrap {{
      padding: 26px 22px 140px;
      max-width: 640px;
      margin: 0 auto;
    }}
    .story-body {{
      font-size: 21px;
      line-height: 1.9;
      letter-spacing: 0.01em;
      color: var(--text);
    }}

    /* ---- Word spans ---- */
    .word {{ display: inline; }}
    .word.clickable {{
      cursor: pointer;
      border-radius: 4px;
      padding: 1px 0;
      transition: background 0.12s;
    }}
    .word.clickable:active {{ background: rgba(44, 95, 46, 0.18); }}
    .word.active {{ background: rgba(44, 95, 46, 0.22); }}

    /* ---- Fun fact ---- */
    .fun-fact {{
      margin-top: 32px;
      background: var(--green-light);
      border-left: 4px solid var(--green);
      border-radius: 0 10px 10px 0;
      padding: 14px 18px;
    }}
    .fun-fact-label {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      color: var(--green);
      margin-bottom: 6px;
    }}
    .fun-fact-text {{
      font-size: 15px;
      line-height: 1.65;
      color: var(--text);
    }}

    /* ---- Overlay ---- */
    .overlay {{
      display: none;
      position: fixed;
      inset: 0;
      z-index: 300;
    }}
    .overlay.visible {{ display: block; }}

    /* ---- Popup card ---- */
    .popup {{
      display: none;
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 400;
      padding: 12px 16px max(24px, env(safe-area-inset-bottom));
    }}
    .popup.visible {{ display: block; }}

    .popup-card {{
      background: var(--popup-bg);
      border-radius: var(--radius);
      padding: 18px 20px 20px;
      max-width: 480px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 12px 48px rgba(0,0,0,0.35);
    }}

    .popup-info {{ flex: 1; min-width: 0; }}
    .popup-word {{
      font-size: 28px;
      font-weight: 700;
      color: var(--popup-text);
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .popup-translation {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 15px;
      color: var(--popup-sub);
      margin-top: 5px;
    }}

    /* Speaker button */
    .replay-btn {{
      flex-shrink: 0;
      width: 46px;
      height: 46px;
      border-radius: 50%;
      border: none;
      background: var(--green);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: background 0.15s, transform 0.1s;
    }}
    .replay-btn:active {{ transform: scale(0.92); }}
    .replay-btn:disabled {{ background: #3a3a3c; opacity: 0.5; cursor: default; }}
    .replay-btn.playing {{ background: var(--green-mid); }}
    .replay-btn svg {{ width: 22px; height: 22px; fill: white; }}
  </style>
</head>
<body>

  <header class="header">
    <div class="header-main">
      <div class="header-eyebrow">{date_escaped} &middot; {topic_en_escaped}{narrator_html}</div>
      <div class="header-title" id="header-title">{title_html}</div>
    </div>
    <button class="toggle-btn" id="toggle-lang" title="See in English" aria-label="Toggle language">EN</button>
  </header>

  <div class="story-wrap">
    <div class="story-body" id="story-body">{story_html}</div>

    <div class="fun-fact">
      <div class="fun-fact-label">Sabia que&hellip;</div>
      <div class="fun-fact-text">{fun_fact_escaped}</div>
    </div>
  </div>

  <!-- Click-away overlay -->
  <div class="overlay" id="overlay"></div>

  <!-- Bottom popup -->
  <div class="popup" id="popup" role="dialog" aria-modal="true">
    <div class="popup-card">
      <div class="popup-info">
        <div class="popup-word" id="popup-word"></div>
        <div class="popup-translation" id="popup-translation"></div>
      </div>
      <button class="replay-btn" id="replay-btn" aria-label="Ouvir" disabled>
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05
                   c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71
                   s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
        </svg>
      </button>
    </div>
  </div>

  <script>
    const META = {meta_json};

    // ---- State ----
    let activeEl     = null;
    let currentAudio = null;
    let showingEN    = false;

    // Cache the Portuguese HTML so we can restore it after toggling to EN
    const PT_HTML = document.getElementById('story-body').innerHTML;

    // ---- DOM refs ----
    const popup      = document.getElementById('popup');
    const overlay    = document.getElementById('overlay');
    const popupWord  = document.getElementById('popup-word');
    const popupTrans = document.getElementById('popup-translation');
    const replayBtn  = document.getElementById('replay-btn');
    const storyBody  = document.getElementById('story-body');
    const headerTitle = document.getElementById('header-title');
    const toggleBtn  = document.getElementById('toggle-lang');

    // ---- Audio ----
    function stopAudio() {{
      if (currentAudio) {{
        currentAudio.pause();
        currentAudio.src = '';
        currentAudio = null;
        replayBtn.classList.remove('playing');
      }}
    }}

    function playAudio(src) {{
      stopAudio();
      const audio = new Audio(src);
      currentAudio = audio;
      replayBtn.classList.add('playing');
      audio.play().catch(() => {{}});
      audio.onended = () => {{ replayBtn.classList.remove('playing'); currentAudio = null; }};
      audio.onerror = () => {{ replayBtn.classList.remove('playing'); currentAudio = null; }};
    }}

    // ---- Popup ----
    function showPopup(el) {{
      if (activeEl === el) {{ hidePopup(); return; }}
      if (activeEl) activeEl.classList.remove('active');
      stopAudio();

      activeEl = el;
      el.classList.add('active');

      popupWord.textContent  = el.textContent;
      popupTrans.textContent = el.dataset.translation || '—';

      const audioSrc = el.dataset.audio || '';
      replayBtn.disabled = !audioSrc;
      replayBtn.dataset.src = audioSrc;

      popup.classList.add('visible');
      overlay.classList.add('visible');
      // No auto-play — user taps the speaker button to hear audio
    }}

    function hidePopup() {{
      popup.classList.remove('visible');
      overlay.classList.remove('visible');
      if (activeEl) {{ activeEl.classList.remove('active'); activeEl = null; }}
      stopAudio();
    }}

    // ---- EN/PT toggle ----
    function toggleLanguage() {{
      hidePopup();
      showingEN = !showingEN;
      if (showingEN) {{
        storyBody.textContent = META.story_en;
        toggleBtn.textContent = 'PT';
        toggleBtn.classList.add('en-active');
      }} else {{
        storyBody.innerHTML = PT_HTML;
        toggleBtn.textContent = 'EN';
        toggleBtn.classList.remove('en-active');
      }}
    }}

    // ---- Event listeners ----
    function onWordTap(e) {{
      const el = e.target.closest('.word.clickable');
      el ? showPopup(el) : hidePopup();
    }}

    storyBody.addEventListener('click', onWordTap);
    headerTitle.addEventListener('click', onWordTap);

    overlay.addEventListener('click', hidePopup);

    replayBtn.addEventListener('click', e => {{
      e.stopPropagation();
      const src = replayBtn.dataset.src;
      if (src) playAudio(src);
    }});

    toggleBtn.addEventListener('click', toggleLanguage);

    document.addEventListener('keydown', e => {{ if (e.key === 'Escape') hidePopup(); }});
  </script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info(f"Wrote HTML page: {output_path} ({len(html.encode('utf-8')):,} bytes)")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_html_page(html_path: Path) -> dict:
    """Quick sanity checks on the generated HTML file."""
    if not html_path.exists():
        return {"all_passed": False, "error": "File not found"}

    content = html_path.read_text(encoding="utf-8")
    size = len(content.encode("utf-8"))

    checks = {
        "file_exists":         True,
        "size_bytes":          size,
        "size_ok":             size > 5_000,
        "has_story_body":      'id="story-body"' in content,
        "has_popup":           'id="popup"' in content,
        "has_clickable_words": 'class="word clickable"' in content,
        "has_audio_refs":      'data-audio=' in content,
        "has_translations":    'data-translation=' in content,
        "has_fun_fact":        'fun-fact' in content,
        "has_toggle":          'id="toggle-lang"' in content,
    }
    checks["all_passed"] = all([
        checks["size_ok"],
        checks["has_story_body"],
        checks["has_popup"],
        checks["has_clickable_words"],
    ])

    if checks["all_passed"]:
        logger.info(f"HTML validation passed ({size:,} bytes, clickable words present)")
    else:
        failed = [k for k, v in checks.items() if k != "all_passed" and v is False]
        logger.error(f"HTML validation FAILED: {failed}")

    return checks
