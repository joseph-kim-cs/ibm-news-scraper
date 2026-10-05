"""Shared LLM call logic: resolves the right backend and executes a prompt.

Priority order:
  1. Direct HTTP endpoint  (BOB_API_URL / LLM_API_URL)
  2. Watsonx.ai direct     (WATSONX_PROJECT_ID + WATSONX_API_KEY)
  3. Bob CLI headless      (bob binary on PATH + BOB_API_KEY / BOBSHELL_API_KEY)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

# ── optional dep ──────────────────────────────────────────────────────────
try:
    import requests  # type: ignore
except ImportError:
    requests = None


def resolve_api_key() -> Optional[str]:
    """Return the first available API key from the environment, or None."""
    return (
        os.getenv("BOB_API_KEY")
        or os.getenv("BOBSHELL_API_KEY")
        or os.getenv("WATSONX_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or None
    )


def call_llm(prompt: str, max_tokens: int = 280, temperature: float = 0.7) -> Optional[str]:
    """Send *prompt* to the best available LLM backend.

    Returns the generated text, or ``None`` when no backend is configured.
    """
    api_key = resolve_api_key()
    if not api_key:
        return None

    result = (
        _call_http_endpoint(prompt, api_key, max_tokens, temperature)
        or _call_watsonx(prompt, api_key, max_tokens, temperature)
        or _call_bob_cli(prompt, api_key)
    )
    return result


# ── private backends ──────────────────────────────────────────────────────

def _call_http_endpoint(
    prompt: str, api_key: str, max_tokens: int, temperature: float
) -> Optional[str]:
    """Try the direct HTTP endpoint (BOB_API_URL / LLM_API_URL)."""
    if requests is None:
        return None

    endpoint = os.getenv("BOB_API_URL") or os.getenv("LLM_API_URL")
    if not endpoint or "your-endpoint" in endpoint or "example.com" in endpoint:
        return None

    try:
        headers: dict = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        team_id = os.getenv("BOB_TEAM_ID")
        if team_id:
            headers["X-Team-Id"] = team_id

        payload = {
            "model": os.getenv("LLM_MODEL", "ibm/granite-3-8b-instruct"),
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and data["choices"]:
                return data["choices"][0]["message"]["content"].strip()
            if "results" in data and data["results"]:
                return data["results"][0].get("generated_text", "").strip()
        else:
            print(
                f"[warn] LLM endpoint ({endpoint}) returned HTTP {resp.status_code}: "
                f"{resp.text[:180]}",
                file=sys.stderr,
            )
    except Exception as exc:
        print(f"[warn] LLM request to {endpoint} failed: {exc}", file=sys.stderr)

    return None


def _call_watsonx(
    prompt: str, api_key: str, max_tokens: int, temperature: float
) -> Optional[str]:
    """Try Watsonx.ai direct generation endpoint."""
    if requests is None:
        return None

    project_id = os.getenv("WATSONX_PROJECT_ID")
    if not project_id:
        return None

    try:
        iam_resp = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if iam_resp.status_code != 200:
            print(
                f"[warn] watsonx.ai IAM token request failed HTTP {iam_resp.status_code}",
                file=sys.stderr,
            )
            return None

        token = iam_resp.json().get("access_token")
        wx_base = (os.getenv("WATSONX_URL") or "https://us-south.ml.cloud.ibm.com").rstrip("/")
        wx_url = f"{wx_base}/ml/v1/text/generation?version=2024-05-01"
        wx_payload = {
            "input": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "decoding_method": "sample",
            },
            "model_id": os.getenv("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct"),
            "project_id": project_id,
        }
        wx_resp = requests.post(
            wx_url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=wx_payload,
            timeout=20,
        )
        if wx_resp.status_code == 200:
            results = wx_resp.json().get("results", [])
            if results:
                return results[0].get("generated_text", "").strip()
        else:
            print(
                f"[warn] watsonx.ai returned HTTP {wx_resp.status_code}: {wx_resp.text[:180]}",
                file=sys.stderr,
            )
    except Exception as exc:
        print(f"[warn] watsonx.ai generation request failed: {exc}", file=sys.stderr)

    return None


def _call_bob_cli(prompt: str, api_key: str) -> Optional[str]:
    """Try the Bob CLI in headless mode (works natively with a Bob API key)."""
    bob_bin = shutil.which("bob")
    if not bob_bin:
        return None

    try:
        env = dict(os.environ)
        env["BOBSHELL_API_KEY"] = api_key
        env["BOB_API_KEY"] = api_key

        cmd = [
            bob_bin, "run",
            "--accept-license",
            "--disable-mcp",
            "--disable-subagents",
            "--format", "pretty",
            "--max-turns", "1",
            "--log-level", "error",
            prompt,
        ]
        team_id = os.getenv("BOB_TEAM_ID")
        if team_id:
            cmd.extend(["--team-id", team_id])

        result = subprocess.run(
            cmd, env=env, capture_output=True, text=True, timeout=45, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        if result.stderr.strip():
            print(
                f"[warn] Bob CLI returned code {result.returncode}: {result.stderr[:200]}",
                file=sys.stderr,
            )
    except Exception as exc:
        print(f"[warn] Bob CLI execution failed: {exc}", file=sys.stderr)

    return None
