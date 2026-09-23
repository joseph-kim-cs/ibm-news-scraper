#!/usr/bin/env bash
# install_cron.sh — install the Monday 8 AM cron job for ibm-news-scraper
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi
LOG_FILE="${LOG_FILE:-$HOME/ibm_linkedin.log}"
CRON_LINE="0 8 * * 1 $PYTHON_BIN $SCRIPT_DIR/main.py >> $LOG_FILE 2>&1"

# Remove any existing entry to avoid duplicates
( crontab -l 2>/dev/null | grep -v "main.py" ; echo "$CRON_LINE" ) | crontab -
echo "✓ Cron installed: $CRON_LINE"
echo "  Logs → $LOG_FILE"
echo "  Drafts saved to → $SCRIPT_DIR/drafts/"
