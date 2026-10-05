#!/usr/bin/env bash
# run_scraper.sh — wrapper script for scheduled execution on macOS
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure common PATHs are available (node, npm-global, brew, python)
export PATH="/Users/josephkim/.opencode/bin:/Users/josephkim/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

LOG_FILE="${LOG_FILE:-$HOME/ibm_linkedin.log}"

echo "=== IBM News Scraper run started at $(date) ===" >> "$LOG_FILE"
"$PYTHON_BIN" "$SCRIPT_DIR/main.py" >> "$LOG_FILE" 2>&1
echo "=== IBM News Scraper run finished at $(date) ===" >> "$LOG_FILE"
