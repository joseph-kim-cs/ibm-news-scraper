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
3. **Draft** — generates drafts for the top 4 headlines (customizable with `--count N`) and maps each headline to storytelling templates that mirror your voice.

## Quick start

```bash
cd ibm-news-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --dry-run             # print top 4 drafts to stdout
python main.py --dry-run --count 2   # print top 2 drafts
python main.py                       # save all 4 drafts to ./drafts/
```

## Scheduling it

### Option A — Local cron (run every Monday at 8 AM)

Using the virtual environment Python interpreter:

```bash
crontab -e
# Add this line (adjust the path to match your repo location):
0 8 * * 1 /Users/josephkim/ibm-news-scraper/.venv/bin/python /Users/josephkim/ibm-news-scraper/main.py >> $HOME/ibm_linkedin.log 2>&1
```

Or run the helper script which auto-detects `.venv/bin/python`:
```bash
./install_cron.sh
```

The app saves each draft to `ibm-news-scraper/drafts/linkedin_draft_YYYY-MM-DD_HHMM.md`.
Review Monday morning, fire off the LinkedIn post manually.

### Option B — GitHub Actions (serverless, no machine left on)

Fork / clone, push to a repo, and the workflow in
`.github/workflows/monday_ibm_scrape.yml` will run every Monday at 8 AM UTC.
It posts the draft as a **workflow artifact** you can download from the Actions
tab — or it can auto-post to LinkedIn via the `linkedin-api` package if you add
`LINKEDIN_USERNAME` / `LINKEDIN_PASSWORD` repo secrets.
