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
python main.py --dry-run             # print top 10 drafts to stdout
python main.py --dry-run --count 5   # print top 5 drafts
python main.py                       # save all 10 drafts to ./drafts/ & trigger macOS notification
```

## Scheduling it

### Option A — Local cron (run every Monday at 8 AM)

Run the helper script which auto-detects `.venv/bin/python` and configures your crontab:
```bash
./install_cron.sh
```

Or configure manually via `crontab -e`:
```bash
0 8 * * 1 /Users/josephkim/ibm-news-scraper/.venv/bin/python /Users/josephkim/ibm-news-scraper/main.py >> $HOME/ibm_linkedin.log 2>&1
```

### What happens on Monday morning?
1. At 8:00 AM on Monday, the script runs in the background.
2. It scrapes and filters the last 7 days of IBM news.
3. It saves the 10 draft options into `ibm-news-scraper/drafts/linkedin_draft_YYYY-MM-DD_HHMM.md`.
4. A **native macOS desktop notification** pops up ("*IBM Headline Linker: Generated 10 Monday LinkedIn drafts ready for review!*").
5. You can open the generated markdown file, choose your favorite draft, and publish to LinkedIn.

### Option B — GitHub Actions (serverless, no machine left on)

Fork / clone, push to a repo, and the workflow in
`.github/workflows/monday_ibm_scrape.yml` will run every Monday at 8 AM UTC.
It posts the draft as a **workflow artifact** you can download from the Actions
tab — or it can auto-post to LinkedIn via the `linkedin-api` package if you add
`LINKEDIN_USERNAME` / `LINKEDIN_PASSWORD` repo secrets.
