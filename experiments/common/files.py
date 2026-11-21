"""Writing analysis results so that the file is the same on every machine."""
from __future__ import annotations

import json


def stable(value):
    """Floats rounded to 12 significant digits, in nested dicts and lists as well.

    The last digits of a p-value depend on the platform's maths library; rounded like
    this, a statistics file is byte-identical wherever it is computed.
    """
    if isinstance(value, float):
        return float(f"{value:.12g}")
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [stable(v) for v in value]
    return value


def write_stable_json(path, value, **dump_options) -> None:
    """`json.dump` of `stable(value)`; `dump_options` go to json.dump (indent and so on)."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(stable(value), fh, **dump_options)
