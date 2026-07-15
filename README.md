# 🇵🇹 Portuguese Daily Story

A mobile-first web app that delivers a new 150-200 word children's story in **continental (European) Portuguese** every evening — generated from date-inspired topics, translated by Gemini, and narrated word-by-word via ElevenLabs.

**Live URL:** `https://chelseamc-pixel.github.io/portuguese-stories/`

---

## How it works

1. **GitHub Action** fires at 6:00 PM PDT (01:00 UTC)
2. **Gemini** fetches 5 notable events/people for that calendar date; one is picked at random as the story topic
3. **Gemini** writes a 150-200 word English children's story from that topic, translates it to continental Portuguese, and provides per-word English translations
4. **ElevenLabs** generates an MP3 audio clip for each unique word, narrated by a voice from the rotating continental Portuguese roster
5. A **self-contained HTML page** is built and deployed to GitHub Pages
6. A **Gmail email** is sent with a preview and link

---

## Story page features

- Tap any word (including title words) to see its English translation in a popup
- Tap the speaker icon in the popup to hear the word pronounced
- **EN** button at the top toggles the full story to English and back
- A Portuguese fun fact appears at the bottom of every story

---

## Voice roster

Seven continental (European) Portuguese voices rotate daily — the same date always gets the same voice, so re-runs are reproducible. The narrator's name appears in the page header.

| Name | Gender | Notes |
|---|---|---|
| Maria | Female | Friendly, clear — ideal for storytelling |
| Joana | Female | Steady, warm, comforting |
| Marta | Female | Middle-aged, warm, self-assured |
| Mariza | Female | Clear, calm, friendly |
| Benedita | Female | Bright, inviting, welcoming |
| Paulo PT | Male | Lisbon accent |
| Lourenço | Male | Man from Lisbon |

To override the voice for a specific run, set `ELEVENLABS_VOICE_ID` in GitHub Secrets to any ElevenLabs voice ID. Leave it blank to use the daily rotation.

---

## Setup (one-time)

### 1. Regenerate your Gemini API key

If you shared your old key anywhere, regenerate it at:
**https://aistudio.google.com/app/apikey**

### 2. Create an ElevenLabs account

1. Go to **https://elevenlabs.io** → Sign up (free)
2. ⚠️ **You'll need the Starter plan ($5/month)** — the free tier allows 10,000 chars/month but this app uses ~14,000/month (one story/day × ~80 words × ~6 chars each)
3. After signing up, go to your **Profile → API Keys → Create API Key**
4. Copy your key — you'll need it in Step 4

### 3. Set up Gmail App Password

You need an App Password (not your regular Gmail password):

1. Go to your Google Account → **Security**
2. Make sure **2-Step Verification** is turned on
3. Search for **"App passwords"** (or go to https://myaccount.google.com/apppasswords)
4. Create a new app password: name it "Portuguese Stories"
5. Copy the 16-character password — you'll need it in Step 4

### 4. Create the GitHub repo

1. Go to **https://github.com/new**
2. Name it `portuguese-stories`
3. Set to **Private**
4. Don't initialise with README (you'll push these files)
5. Click **Create repository**

### 5. Enable GitHub Pages

1. In your new repo → **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `gh-pages` / `/ (root)`
4. Click **Save**

(The `gh-pages` branch will be created automatically on first run.)

### 6. Add GitHub Secrets

In your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add each of these:

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | Leave blank to use daily voice rotation |
| `GMAIL_USER` | `chelseamc@gmail.com` |
| `GMAIL_APP_PASSWORD` | Your 16-char Gmail App Password |
| `RECIPIENT_EMAIL` | `chelseamc@gmail.com` |

### 7. Push the code

```bash
cd portuguese-stories
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/chelseamc-pixel/portuguese-stories.git
git push -u origin main
```

### 8. Test the workflow manually

1. Go to your repo → **Actions → Generate Daily Portuguese Story**
2. Click **Run workflow**
3. Check "Dry run" to skip API calls and just test the HTML structure
4. Watch the logs — everything should go green

To test with real API calls but skip the email:
- Uncheck Dry run, check "Skip email", click Run workflow

---

## Local development

```bash
# Clone and install
git clone https://github.com/chelseamc-pixel/portuguese-stories.git
cd portuguese-stories
pip install -r requirements.txt

# Copy and fill in your .env
cp .env.example .env
# Edit .env with your API keys

# Run unit tests (no API calls)
pytest scripts/tests/ -v -m "not integration"

# Dry run (builds HTML without API calls)
python scripts/run_pipeline.py --dry-run --no-email
# → Open docs/index.html in your browser to preview

# Test SMTP credentials only
python scripts/run_pipeline.py --test-email

# Full run for a specific date
python scripts/run_pipeline.py --date 2026-07-04 --no-email
```

---

## Project structure

```
portuguese-stories/
├── .github/
│   └── workflows/
│       ├── generate_story.yml       # Nightly cron + manual trigger
│       └── test_elevenlabs.yml      # Isolated ElevenLabs audio test
├── scripts/
│   ├── generate_story.py            # Gemini: story generation + translation
│   ├── generate_audio.py            # ElevenLabs: per-word audio + voice roster
│   ├── build_page.py                # HTML page builder
│   ├── send_email.py                # Gmail SMTP
│   ├── run_pipeline.py              # Orchestrator (entry point)
│   └── tests/
│       ├── test_story.py            # Story generation unit + integration tests
│       ├── test_build_page.py       # HTML builder tests
│       ├── test_pipeline_dryrun.py  # End-to-end dry-run test
│       └── test_elevenlabs.py       # Isolated ElevenLabs audio test
├── docs/
│   └── index.html                   # Generated daily (served by GitHub Pages)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Scheduling notes

- The cron `0 1 * * *` fires at **01:00 UTC = 6:00 PM PDT** (summer) / **5:00 PM PST** (winter)
- GitHub Actions scheduled triggers are best-effort — delays of 15-30 minutes are normal
- GitHub Pages deployment takes 1-3 minutes after the action completes
- The email is sent after deployment, so the link is live when you receive it

To adjust timing, change the cron expression in `.github/workflows/generate_story.yml`.

---

## Costs

| Service | Plan | Monthly cost | Usage |
|---|---|---|---|
| Google Gemini | Free tier | $0 | ~90 API calls/month |
| ElevenLabs | Starter | $5/month | ~14,000 chars/month |
| GitHub Actions | Free | $0 | Well within free minutes |
| Gmail | Free | $0 | 30 emails/month |

**Total: ~$5/month**
