"""Where the pipeline reads and writes, in one place.

    ROOT          the repository
    DATA_DIR      the record tree, one folder per source ($EVALSPEC_DATA, else ROOT/data)
    SCHEMA_PATH   the EEE JSON Schema
    ENV_FILE      the optional .env file with API keys

Every module of the package takes its folders from here, so the whole pipeline is pointed
at another data folder by setting EVALSPEC_DATA before it starts. The reproduction
scripts in scripts/ read the same variable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_ENV = "EVALSPEC_DATA"
DATA_DIR = Path(os.environ.get(DATA_ENV) or ROOT / "data").expanduser()
SCHEMA_PATH = ROOT / "eval.schema.json"
ENV_FILE = ROOT / ".env"


def load_dotenv(needed: str | None = None, extra_files: tuple[Path, ...] = (), announce=None) -> None:
    """Copy the variables of the .env file into the environment, without replacing any.

    Does nothing when `needed` is already set. python-dotenv is used when it is installed;
    otherwise the file is read as KEY=value lines (quotes around a value are removed, blank
    lines and # comments are skipped). `announce(message)` is called when `needed` was found.
    """
    if needed and os.environ.get(needed):
        return
    for env_path in (ENV_FILE, *extra_files):
        if not env_path.exists():
            continue
        try:
            from dotenv import load_dotenv as _load
            _load(dotenv_path=str(env_path), override=False)
            if needed and os.environ.get(needed):
                if announce:
                    announce(f"{needed} loaded via python-dotenv from {env_path}")
                return
        except ImportError:
            pass
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] in ('"', "'") and value[0] == value[-1]:
                    value = value[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = value
            if needed and os.environ.get(needed):
                if announce:
                    announce(f"{needed} loaded from {env_path}")
                return
        except Exception as exc:  # noqa: BLE001  an unreadable .env must not stop the pipeline
            print(f"  [env] could not parse {env_path}: {exc}", file=sys.stderr)
