# IBM Headline Linker

A Python app with two modes:

1. **Headline mode** — scrapes IBM press releases, newsroom posts, and IBM Research blog posts from the last 14 days, ranks the most notable stories, and drafts LinkedIn posts from each article in your signature storytelling style.
2. **Event mode** — takes any event you attended (IBM Think, a customer workshop, a conference, anything) and drafts a personalized LinkedIn post about your experience.

## What it does

### Headline mode
1. **Scrape** — pulls the last 14 days of dated stories from the IBM Newsroom
   listings and the IBM Research RSS feed.
2. **Filter and rank** — removes duplicates, explainers, and financial boilerplate,
   reads each article, and ranks stories by news value. At most two quantum stories
   appear among the top results by default.
3. **Draft** — generates drafts for the top 7 stories (customizable with `--count N`)
   using the article text. Numbers that cannot be found in the source are retried and
   then flagged for review. If drafting fails, the file says so instead of using a
   generic template.

### Event mode
Provide details about any event you attended and the app drafts a LinkedIn post
capturing your personal experience, key takeaways, and a forward-looking hook.

---

## Quick start

```bash
cd ibm-news-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # add your BOB_API_KEY in .env
python main.py --dry-run             # print top 10 headline drafts to stdout
python main.py --dry-run --count 5   # print top 5 headline drafts
python main.py                       # save all 10 drafts to ./drafts/ & trigger macOS notification
```

---

## Web app

```bash
./run_web.sh
```

- **Browser UI:** http://127.0.0.1:8000 — preview ranked headlines, generate and edit
  drafts, draft event posts, and browse everything saved in `drafts/`.
- **Swagger UI:** http://127.0.0.1:8000/docs — try every API endpoint.

The server only accepts requests from this machine. Set `PORT` to use another port.
Generating drafts uses the same Tavily searches and LLM calls as `main.py`; previewing
headlines uses neither. One job runs at a time, and job progress is lost if the server
restarts.

---

## Drafting a LinkedIn post for an event

Use the `--event-name` and `--event-date` flags to switch into event mode.
All other event flags are optional but produce a richer, more personalized draft.

```bash
python main.py \
  --event-name "IBM Think 2025" \
  --event-date "2025-05-05" \
  --event-location "Boston, MA" \
  --event-description "Attended the watsonx keynote and hands-on AI labs. Great conversations with engineering leaders about agentic AI." \
  --event-url "https://www.ibm.com/events/think/" \
  --dry-run
```

**What each flag does:**

| Flag | Required | Description |
|---|---|---|
| `--event-name` | ✅ | Name of the event, e.g. `"IBM Think 2025"` |
| `--event-date` | ✅ | Date of the event in `YYYY-MM-DD` format |
| `--event-location` | optional | City or venue, e.g. `"Boston, MA"` |
| `--event-description` | optional | Your notes: key sessions, takeaways, conversations |
| `--event-url` | optional | A link to the event page (included in the post) |
| `--dry-run` | optional | Print the draft to the terminal instead of saving a file |

**Without `--dry-run`**, the draft is saved to `drafts/event_draft_<name>_<timestamp>.md`
and a macOS desktop notification fires when it's ready.

> **Tip:** The more detail you put in `--event-description`, the more specific
> and authentic the generated post will be. Include session names, speaker quotes,
> or the one thing that surprised you most.

## LLM Configuration (.env)

The scraper generates drafts of about 170 words in your signature voice, using the built-in samples as style references.

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

*(If no LLM is available, headline drafts are marked as not generated. Event mode still falls back to its local template.)*

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
2. It scrapes and ranks the last 14 days of IBM news.
3. It generates LinkedIn drafts using Bob AI and saves them to `ibm-news-scraper/drafts/linkedin_draft_YYYY-MM-DD_HHMM.md`.
4. A **native macOS desktop notification** alerts you that your drafts are ready.
5. You can open the generated markdown file, pick your favorite draft, and post.

### Option B — GitHub Actions (serverless, no machine left on)

Fork / clone, push to a repo, and the workflow in
`.github/workflows/monday_ibm_scrape.yml` will run every Monday at 8 AM UTC.
It posts the draft as a **workflow artifact** you can download from the Actions
tab — or it can auto-post to LinkedIn via the `linkedin-api` package if you add
`LINKEDIN_USERNAME` / `LINKEDIN_PASSWORD` repo secrets.
