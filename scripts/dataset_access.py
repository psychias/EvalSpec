"""Where the dataset lives on disk, for the reproduction scripts.

Two layouts are supported:

* the published dataset, as ``scripts/fetch_data.py`` lays it out::

      data/aggregated/all_results.csv     one row per result
      data/records/<source>.jsonl         the full records, one per line
      data/annotations/*.csv              the hand-checked audit sets

* the working tree of the extraction pipeline, with one JSON file per record
  (``data/open_llm_leaderboard_v2/<org>/<model>/<uuid>.json`` and so on).

The case-study scripts were written against the second layout and name single
record files. ``RecordPath`` lets that code run unchanged on the first layout: it
behaves like the ``pathlib.Path`` of a record file, and when the file is not on
disk it finds the same record in the JSONL file by paper, model and benchmark.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
AGGREGATE_CSV = DATA / "aggregated" / "all_results.csv"
RECORDS = DATA / "records"
FETCH_HINT = "The dataset is not in data/. Run: python scripts/fetch_data.py"

# record source -> (per-record tree used by the pipeline, JSONL file of the published dataset)
_SOURCES = {
    "arxiv": ([DATA / "archiv_paper_extraction" / "llm", DATA / "arxiv_extraction_general" / "llm"],
              RECORDS / "arxiv_extraction.jsonl"),
    "olv2": ([DATA / "open_llm_leaderboard_v2"], RECORDS / "open_llm_leaderboard.jsonl"),
}
_ANNOTATION_DIRS = [DATA / "annotations", DATA / "archiv_paper_extraction" / "samples",
                    DATA / "arxiv_extraction_general" / "samples"]
_cache: dict[pathlib.Path, list[dict]] = {}


def flat(text) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _title_match(folder: str, title: str) -> float:
    """How well a folder name of the pipeline tree matches a paper title: the share of the
    folder's words found in the title, 0 unless the first word agrees and most words do.
    Folder names are titles with punctuation turned into underscores, sometimes shortened."""
    want = [w for w in re.split(r"[^a-z0-9]+", folder.lower()) if w]
    have = [w for w in re.split(r"[^a-z0-9]+", title.lower()) if w]
    if not want or not have or want[0] != have[0]:
        return 0.0
    share = sum(w in have for w in want) / len(want)
    return share if share >= 0.6 else 0.0


def _same_model(folder: str, name: str) -> bool:
    """The same model name, allowing its parts in another order (Llama-2-Chat-7B, Llama-2-7B-Chat)."""
    def words(s):
        return sorted(w for w in re.split(r"[^a-z0-9]+", s.lower()) if w)
    return flat(folder) == flat(name) or words(folder) == words(name)


def read_jsonl(path: pathlib.Path) -> list[dict]:
    """The records of a JSONL file; an empty list when the file is not there."""
    if path not in _cache:
        _cache[path] = ([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
                        if path.exists() else [])
    return _cache[path]


def annotation_file(name: str) -> pathlib.Path:
    """The audit CSV of that name, wherever it is; the first candidate when it is nowhere."""
    for folder in _ANNOTATION_DIRS:
        if (folder / name).exists():
            return folder / name
    return _ANNOTATION_DIRS[0] / name


def arxiv_records() -> list[dict]:
    """Every record read from an arXiv paper, from the tree when it exists, else from the JSONL file."""
    trees, jsonl = _SOURCES["arxiv"]
    for tree in trees:
        if tree.is_dir():
            out = []
            for f in tree.rglob("*.json"):
                if f.name in ("summary.json", "metric_configs_from_llm.json", "extraction_results.json"):
                    continue
                try:
                    doc = json.loads(f.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if isinstance(doc, dict):
                    out.append(doc)
            return out
    return read_jsonl(jsonl)


def _shown(path: pathlib.Path) -> str:
    """The path relative to the repository, where it is inside it."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


class RecordPath:
    """A record file of the pipeline tree, or the same record in the published JSONL file."""

    def __init__(self, source: str, parts: tuple[str, ...] = ()):
        self.source, self.parts = source, parts
        self._doc = None

    def __truediv__(self, part: str) -> RecordPath:
        return RecordPath(self.source, self.parts + (str(part),))

    # -- the file on disk, when the pipeline tree is present
    def _real(self) -> pathlib.Path | None:
        for tree in _SOURCES[self.source][0]:
            path = tree.joinpath(*self.parts)
            if path.exists():
                return path
        return None

    # -- the record in the JSONL file
    def _find(self) -> dict | None:
        if self._doc is None and len(self.parts) >= 2:
            docs = read_jsonl(_SOURCES[self.source][1])
            if self.source == "arxiv":                       # <paper title>/<model>/<benchmark>/<uuid>.json
                bench = flat(self.parts[2]) if len(self.parts) > 2 and not self.parts[2].endswith(".json") else ""
                best = 0.0
                for doc in docs:
                    details = (doc.get("source_metadata") or {}).get("additional_details") or {}
                    if not _same_model(self.parts[1], (doc.get("model_info") or {}).get("name", "")):
                        continue
                    close = _title_match(self.parts[0], details.get("paper_title", ""))
                    if close <= best:
                        continue
                    results = [r for r in doc.get("evaluation_results") or [] if not bench or flat(r.get("evaluation_name", "")) == bench]
                    results = results or [r for r in doc.get("evaluation_results") or [] if flat(r.get("evaluation_name", "")).startswith(bench)]
                    if results:
                        best, self._doc = close, {**doc, "evaluation_results": results}
            else:                                            # <organisation>/<model>/<uuid>.json
                wanted = flat(self.parts[0]) + flat(self.parts[1])
                self._doc = next((d for d in docs if flat((d.get("model_info") or {}).get("id", "")) == wanted), None)
        return self._doc

    # -- the part of pathlib.Path the scripts use
    def exists(self) -> bool:
        return self._real() is not None or self._find() is not None

    def read_text(self, **kwargs) -> str:
        real = self._real()
        if real is not None:
            return real.read_text(**kwargs)
        doc = self._find()
        if doc is None:
            raise FileNotFoundError(str(self))
        return json.dumps(doc)

    def read_bytes(self) -> bytes:
        return self.read_text(encoding="utf-8").encode("utf-8")

    def rglob(self, pattern: str):
        real = self._real()
        if real is not None:
            yield from real.rglob(pattern)
            return
        for doc in read_jsonl(_SOURCES[self.source][1]):
            path = RecordPath(self.source, ("record",))
            path._doc = doc
            yield path

    def relative_to(self, _other) -> RecordPath:
        return self

    def __str__(self) -> str:
        real = self._real()
        if real is not None:
            return _shown(real)
        doc = self._doc if self._doc is not None else self._find()
        if doc:
            return f"{_shown(_SOURCES[self.source][1])} :: {doc.get('evaluation_id')}"
        return _shown(_SOURCES[self.source][0][0].joinpath(*self.parts))


ARXIV_DIR = RecordPath("arxiv")
OLV2_DIR = RecordPath("olv2")
