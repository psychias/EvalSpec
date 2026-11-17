#!/usr/bin/env python3
"""Looks up the titles of papers that the datastore names only by their arXiv id.

    python tools/paper_titles.py --datastore datastore_cache
    python tools/paper_titles.py --datastore datastore_cache --fix 2403.04652,2601.02346

Writes source/paper_titles.json (arXiv id -> title). The build shows a title from this file
in place of "arXiv:<id>", and in place of the title a record carries when the id is listed
with --fix. Titles already in the file are kept, so only new ids are asked for.
Asks the public arXiv API, 80 ids per request.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "source"))
import ingest  # noqa: E402

TARGET = ROOT / "source" / "paper_titles.json"
API = "https://export.arxiv.org/api/query?"
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def context() -> ssl.SSLContext:
    """The system certificates, or those of the certifi package where Python has none of its own."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def untitled(root: pathlib.Path, data_dir: str) -> set[str]:
    """arXiv ids of records that carry no paper title."""
    ids, titled = set(), set()
    for _, doc in ingest.read(root, data_dir)[0]:
        details = (doc.get("source_metadata") or {}).get("additional_details") or {}
        if details.get("arxiv_id"):
            (titled if details.get("paper_title") else ids).add(str(details["arxiv_id"]))
    return ids - titled


def lookup(ids: list[str]) -> dict[str, str]:
    found, ctx = {}, context()
    for start in range(0, len(ids), 80):
        chunk = ids[start:start + 80]
        url = API + urllib.parse.urlencode({"id_list": ",".join(chunk), "max_results": len(chunk)})
        request = urllib.request.Request(url, headers={"User-Agent": "paper-title-lookup/1.0"})
        with urllib.request.urlopen(request, timeout=60, context=ctx) as response:
            feed = ET.fromstring(response.read())
        for entry in feed.findall("a:entry", ATOM):
            match = re.search(r"abs/([0-9]{4}\.[0-9]{4,5})", entry.findtext("a:id", "", ATOM))
            title = re.sub(r"\s+", " ", entry.findtext("a:title", "", ATOM)).strip()
            if match and title:
                found[match.group(1)] = title
        if start + 80 < len(ids):
            time.sleep(3)                               # the API asks for a pause between requests
    return found


def main(argv=None) -> int:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["datastore"]
    ap = argparse.ArgumentParser(description="Look up the titles of papers named only by arXiv id.")
    ap.add_argument("--datastore", type=pathlib.Path, default=ROOT / "datastore_cache", help="folder holding a copy of the datastore")
    ap.add_argument("--fix", default="", help="comma-separated arXiv ids whose title in the datastore is wrong and should be replaced")
    args = ap.parse_args(argv)
    titles = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {}
    wanted = sorted((untitled(args.datastore.resolve(), cfg["data_dir"]) | {i.strip() for i in args.fix.split(",") if i.strip()}) - set(titles))
    if wanted:
        try:
            titles.update(lookup(wanted))
        except OSError as e:
            print(f"could not reach the arXiv API: {e}", file=sys.stderr)
            return 1
    TARGET.write_text(json.dumps(dict(sorted(titles.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    missing = [i for i in wanted if i not in titles]
    print(f"{len(titles)} titles in {TARGET.relative_to(ROOT)}; {len(wanted) - len(missing)} new" + (f"; not found: {', '.join(missing)}" if missing else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
