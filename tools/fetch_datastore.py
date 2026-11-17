#!/usr/bin/env python3
"""Copies the datastore from Hugging Face into a local folder, for the site build.

    python tools/fetch_datastore.py              into datastore_cache/
    python tools/fetch_datastore.py --to PATH
    python source/build.py --datastore datastore_cache

Which dataset to copy is set in config.json (datastore.hf_repo, revision, data_dir).
Uses the huggingface_hub package when it is installed, and git otherwise.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def with_hub(repo: str, revision: str, data_dir: str, target: pathlib.Path) -> bool:
    """Download the JSON files with huggingface_hub. False when the package is not installed."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return False
    snapshot_download(repo_id=repo, repo_type="dataset", revision=revision, local_dir=str(target),
                      allow_patterns=[f"{data_dir}/**/*.json", "*.md"])
    return True


def with_git(url: str, revision: str, target: pathlib.Path) -> None:
    """Clone the dataset, or update a clone made earlier."""
    if (target / ".git").is_dir():
        subprocess.run(["git", "-C", str(target), "pull", "--ff-only"], check=True)
    else:
        subprocess.run(["git", "clone", "--depth", "1", "--branch", revision, url, str(target)], check=True)


def lfs_pointers(files: list[pathlib.Path]) -> bool:
    """True when the files are Git LFS pointers and not the records themselves."""
    return any(f.read_bytes()[:40].startswith(b"version https://git-lfs") for f in files[:20])


def main(argv=None) -> int:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["datastore"]
    ap = argparse.ArgumentParser(description="Copy the EvalSpec datastore into a local folder.")
    ap.add_argument("--to", type=pathlib.Path, default=ROOT / "datastore_cache", help="target folder (default: datastore_cache/)")
    ap.add_argument("--git", action="store_true", help="use git even when huggingface_hub is installed")
    ap.add_argument("--url", help="clone from this address instead of Hugging Face (implies --git)")
    args = ap.parse_args(argv)
    repo, revision, data_dir = cfg["hf_repo"], cfg["revision"], cfg["data_dir"]
    url = args.url or f"https://huggingface.co/datasets/{repo}"

    print(f"copying {url} ({revision}) into {args.to}")
    try:
        if args.git or args.url or not with_hub(repo, revision, data_dir, args.to):
            with_git(url, revision, args.to)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        print(f"could not copy the datastore: {e}\nCheck datastore.hf_repo in config.json and the network connection.", file=sys.stderr)
        return 1
    except Exception as e:                       # huggingface_hub raises its own error types
        print(f"could not copy the datastore: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    base = args.to / data_dir if (args.to / data_dir).is_dir() else args.to
    files = sorted(base.rglob("*.json"))
    if not files:
        print(f"no JSON files under {base}", file=sys.stderr)
        return 1
    if lfs_pointers(files):
        print("the files are Git LFS pointers, not the records. Either install huggingface_hub (pip install huggingface_hub)\n"
              f"and run this script again, or run: git lfs install && git -C {args.to} lfs pull", file=sys.stderr)
        return 1
    print(f"{len(files):,} JSON files. Next: python source/build.py --datastore {args.to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
