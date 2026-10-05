#!/usr/bin/env bash
# install_schedule.sh — install macOS LaunchAgent or Cron for ibm-news-scraper
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.ibm.news.scraper"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_FILE="$HOME/ibm_linkedin.log"

mkdir -p "$HOME/Library/LaunchAgents"

# Unload existing LaunchAgent if registered
launchctl bootout "gui/$(id -u)/${PLIST_NAME}" 2>/dev/null || launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Generate LaunchAgent plist
cat << EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${SCRIPT_DIR}/run_scraper.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>1</integer>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
EOF

# Load LaunchAgent
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || launchctl load "$PLIST_PATH" 2>/dev/null || true

echo "✓ macOS LaunchAgent installed & loaded: $PLIST_PATH"
echo "  Schedule: Every Monday at 8:00 AM (will run immediately upon waking if Mac was asleep)"
echo "  Logs: $LOG_FILE"
echo "  Drafts: $SCRIPT_DIR/drafts/"
