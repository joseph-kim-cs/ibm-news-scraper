# IBM Headline Linker

A small Python app that **scrapes IBM press releases and IBM Research blog posts
from the last 7 days every Monday**, filters for eye-catching, business-relevant
headlines, and **drafts a LinkedIn post** in your signature storytelling style.

## What it does

1. **Scrape** — pulls the last 7 days of headlines from:
   - IBM Newsroom RSS feed: `https://newsroom.ibm.com/rss`
   - IBM Research "latest" blog cards (HTML fallback)
2. **Filter** — keeps only headlines containing keywords like `AI`, `watsonx`,
   `moon`, `NASA`, `US Open`, `tennis`, `open-source`, `quantum`, `cloud`, etc.
   Drops financial/boilerplate noise (quarterly earnings, dividends, board
   appointments).
3. **Draft** — generates drafts for the top 10 headlines (customizable with `--count N`) and maps each headline to storytelling templates that mirror your voice.

## Quick start

```bash
cd ibm-news-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # add your BOB_API_KEY in .env
python main.py --dry-run             # print top 10 drafts to stdout
python main.py --dry-run --count 5   # print top 5 drafts
python main.py                       # save all 10 drafts to ./drafts/ & trigger macOS notification
```

## LLM Configuration (.env)

The scraper dynamically generates personalized drafts under 250 tokens in your signature voice, using the built-in templates as few-shot style references.

Configure your `.env` file based on your provider:

### Option 1: OpenAI-compatible / Proxy / Custom Endpoint
```dotenv
BOB_API_KEY=your-api-key-here
BOB_API_URL=https://your-endpoint-host/v1/chat/completions
LLM_MODEL=ibm/granite-3-8b-instruct
```

### Option 2: IBM watsonx.ai
```dotenv
WATSONX_API_KEY=your-ibm-cloud-iam-api-key
WATSONX_PROJECT_ID=your-watsonx-project-id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-3-8b-instruct
```

*(If no endpoint or API key is provided, the scraper automatically falls back to the deterministic local storytelling templates).*

## Scheduling it

### Option A — macOS LaunchAgent (Recommended for macOS)

On macOS, `cron` jobs will **not run or catch up** if your laptop/desktop is asleep at 8:00 AM. Using a macOS `LaunchAgent` is the Apple-native solution: it schedules the job for Monday 8:00 AM and **automatically triggers it the moment your Mac wakes up** if the machine was asleep.

To install or update the LaunchAgent:
```bash
./install_schedule.sh
```

### Option B — Traditional Crontab

If you prefer crontab:
```bash
./install_cron.sh
```

### What happens on Monday morning?
1. At 8:00 AM on Monday (or as soon as you wake/open your Mac), the script runs seamlessly in the background.
2. It scrapes and filters the last 7 days of IBM news.
3. It generates LinkedIn drafts using Bob AI and saves them to `ibm-news-scraper/drafts/linkedin_draft_YYYY-MM-DD_HHMM.md`.
4. A **native macOS desktop notification** alerts you that your drafts are ready.
5. You can open the generated markdown file, pick your favorite draft, and post.

### Option B — GitHub Actions (serverless, no machine left on)

Fork / clone, push to a repo, and the workflow in
`.github/workflows/monday_ibm_scrape.yml` will run every Monday at 8 AM UTC.
It posts the draft as a **workflow artifact** you can download from the Actions
tab — or it can auto-post to LinkedIn via the `linkedin-api` package if you add
`LINKEDIN_USERNAME` / `LINKEDIN_PASSWORD` repo secrets.
