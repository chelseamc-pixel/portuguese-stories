# 🇵🇹 Portuguese Daily Story

A mobile-first web app that delivers a new 150-200 word children's story in **continental (European) Portuguese** every night at 9:30 PM — generated from date-inspired topics, translated by Gemini, and narrated word-by-word via ElevenLabs.

**Live URL:** `https://chelseamc-pixel.github.io/portuguese-stories/`

---

## How it works

1. **GitHub Action** fires at 9:30 PM PST (05:30 UTC)
2. **Gemini** generates a 150-200 word English story inspired by notable events for that date, then translates it to continental Portuguese and provides per-word English translations
3. **ElevenLabs** generates an MP3 audio clip for each unique word
4. A **self-contained HTML page** is built and deployed to GitHub Pages
5. A **Gmail email** is sent with a preview and link

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

**Choosing a voice (optional but recommended):**
- Go to **Voice Library** and filter by Language: Portuguese
- Look for a female European Portuguese voice (labelled "Portugal" or "European")
- Click it → **Add to my voices** → copy the Voice ID from your **My Voices** tab
- If you skip this, the default Rachel voice with the multilingual model still sounds natural

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
| `GEMINI_API_KEY` | Your new Gemini API key |
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key |
| `ELEVENLABS_VOICE_ID` | Voice ID from ElevenLabs (optional — leave blank to use default) |
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
│       └── generate_story.yml   # Nightly cron + manual trigger
├── scripts/
│   ├── generate_story.py        # Gemini: story generation + translation
│   ├── generate_audio.py        # ElevenLabs: per-word audio
│   ├── build_page.py            # HTML page builder
│   ├── send_email.py            # Gmail SMTP
│   ├── run_pipeline.py          # Orchestrator (entry point)
│   └── tests/
│       ├── test_story.py        # Story generation unit + integration tests
│       ├── test_build_page.py   # HTML builder tests
│       └── test_pipeline_dryrun.py  # End-to-end dry-run test
├── docs/
│   └── index.html               # Generated daily (served by GitHub Pages)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Scheduling notes

- The cron `30 5 * * *` fires at **05:30 UTC = 9:30 PM PST** (winter) / **10:30 PM PDT** (summer)
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
