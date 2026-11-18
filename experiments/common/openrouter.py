"""Calling models through OpenRouter, and the small file helpers that go with it.

Shared by the judge-model and temperature experiments, which generate answers with
one set of models and score them with another, all through the same chat endpoint.

The API key is read from `.env` at the repository root or from the environment
variable OPENROUTER_API_KEY, and only when a model is called: analysing saved
results needs no key.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BASE = "https://openrouter.ai/api/v1/chat/completions"
ERROR_PREFIX = "__ERROR__"


def load_key() -> str:
    """The OpenRouter key from `.env` at the repository root, else from the environment."""
    env = os.path.join(REPO_ROOT, ".env")
    if os.path.exists(env):
        with open(env, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("OPENROUTER_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY not found in .env or environment")
    return key


def headers() -> dict:
    return {"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"}


def chat(model: str, messages: list[dict], temperature: float = 0.0, max_tokens: int = 512,
         retries: int = 4, timeout: int = 120) -> str:
    """One chat completion. Returns the text, or a string starting with ERROR_PREFIX
    after `retries` failed attempts (HTTP error, empty answer, or network error)."""
    payload = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(BASE, headers=headers(), json=payload, timeout=timeout)
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"].get("content")
                if content:
                    return content
                last = "empty content"                 # retried, then reported as an error
            else:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:  # noqa: BLE001  any failure of one call is retried
            last = str(e)
        time.sleep(2 * (attempt + 1))
    return f"{ERROR_PREFIX} {last}"


def read_jsonl(path) -> list[dict]:
    """The records of a JSONL file; an empty list when the file does not exist."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def append_jsonl(path, obj) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def parse_rating(text: str) -> float | None:
    """The 1 to 10 rating in a judge's answer: `[[7]]` first, else `Rating: 7`. None when there is none."""
    m = re.search(r"\[\[\s*(\d+(?:\.\d+)?)\s*\]\]", text) or re.search(r"[Rr]ating:?\s*(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    value = float(m.group(1))
    return value if 1 <= value <= 10 else None
