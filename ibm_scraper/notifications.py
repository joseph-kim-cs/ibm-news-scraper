"""macOS desktop notification helper."""

from __future__ import annotations

import subprocess
import sys


def send_macos_notification(title: str, message: str, sound: str = "default") -> None:
    """Send a native macOS desktop notification via AppleScript osascript.

    No-ops silently on non-macOS platforms.
    """
    if sys.platform != "darwin":
        return

    safe_title = title.replace('"', '\\"')
    safe_msg = message.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}" sound name "{sound}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
    except Exception:
        pass
