#!/usr/bin/env bash
# run_web.sh — start the local web app at http://127.0.0.1:8000
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Make the Bob CLI findable, as run_scraper.sh does for scheduled runs.
export PATH="$HOME/.opencode/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

# Bound to this machine only. Access logs are off because the page polls job status.
exec "$PYTHON_BIN" -m uvicorn ibm_scraper.web.app:app \
  --host 127.0.0.1 --port "${PORT:-8000}" --no-access-log "$@"
