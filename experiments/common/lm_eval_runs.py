"""What the GPU run scripts share: the prompt formats, the set-up of a session, one
evaluation with retries, and the result line of a run.

A run script is a list of cells (model, task, prompt format, shots, seed) and a `main`
that walks it. This module holds the parts that do not depend on the cells, so a new
run is a new list:

    from common import lm_eval_runs as runs

    def main(argv=None):
        args = runs.grid_parser(__doc__, MODELS, seeds=SEEDS).parse_args(argv)
        runs.pip_install("lm-eval==0.4.11", "accelerate")
        for eval_id, model_id, batch in args.models:
            lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size=batch)
            for fmt in args.formats:
                for seed in args.seeds:
                    record = dict(model_id=model_id, benchmark="gsm8k", prompt_format=fmt, random_seed=seed)
                    runs.run_cell(record,
                                  lambda: runs.evaluate(lm, tasks=["gsm8k"], num_fewshot=5,
                                                        system_instruction=runs.FORMAT_TEMPLATES[fmt],
                                                        apply_chat_template=True, **runs.seeded(seed), **runs.QUIET),
                                  lambda r: runs.percent(r["results"]["gsm8k"], "exact_match,strict-match"),
                                  note=f"{model_id} {fmt} s{seed}")
            runs.release(lm)

Nothing here imports lm_eval, torch or the Hugging Face libraries until a function that
needs them is called: a script sets its environment variables first, and importing a
script (or asking it for --help or --dry-run) starts nothing.

Every run prints one line per cell, `RESULT {json}`, which is what the result files in
experiments/*/results/ were collected from.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

# The system prompts of the three prompt formats (experiments/controlled_eval/prompt_templates.md).
FORMAT_TEMPLATES = {
    "plain": None,
    "instruct": "You are an expert problem solver. Answer each question carefully and directly.",
    "cot": "You are an expert problem solver. Before answering, think step by step and show your reasoning. Then state the final answer.",
}
# simple_evaluate arguments that keep a run from writing samples and logs.
QUIET = {"write_out": False, "log_samples": False, "verbosity": "ERROR"}


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #
def model_spec(text: str) -> tuple[str, str, int]:
    """`EVAL_ID[=RECORDED_ID][@BATCH]` -> (repository to load, model id written to the record, batch size).

    The two ids differ when the weights come from a mirror: the run loads the mirror and
    the record carries the canonical name.
    """
    text, _, batch = text.partition("@")
    eval_id, _, recorded = text.partition("=")
    return eval_id, recorded or eval_id, int(batch) if batch else 8


def grid_parser(description: str, models, seeds=None, formats=FORMAT_TEMPLATES) -> argparse.ArgumentParser:
    """The options of a grid run, with the settings of the published run as defaults."""
    ap = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", dest="models", action="append", type=model_spec, metavar="EVAL_ID[=RECORDED_ID][@BATCH]",
                    help="model to run; may be given several times (default: " +
                         ", ".join(f"{e}@{b}" if e == c else f"{e}={c}@{b}" for e, c, b in models) + ")")
    if seeds is not None:
        ap.add_argument("--seeds", type=int, nargs="+", default=list(seeds), help=f"random seeds (default: {' '.join(map(str, seeds))})")
    if formats:
        ap.add_argument("--formats", nargs="+", choices=list(formats), default=list(formats),
                        help=f"prompt formats (default: {' '.join(formats)})")
    ap.add_argument("--dry-run", action="store_true", help="print the cells of the run and stop, without loading anything")
    ap.set_defaults(default_models=list(models))
    return ap


def parse(ap: argparse.ArgumentParser, argv=None) -> argparse.Namespace:
    args = ap.parse_args(argv)
    if not args.models:
        args.models = args.default_models
    return args


def timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def dry_run(cells) -> None:
    """Print one line per cell of a run."""
    cells = list(cells)
    for cell in cells:
        print("CELL " + json.dumps(cell))
    print(f"{len(cells)} cells; nothing was run")


# --------------------------------------------------------------------------- #
# Session set-up
# --------------------------------------------------------------------------- #
def online_session(pass_token_as=("HUGGING_FACE_HUB_TOKEN",)) -> str:
    """Environment of a run that downloads as it goes. Returns $HF_TOKEN ("" when unset),
    copied to the variables in `pass_token_as` so that every library finds it."""
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    token = os.environ.get("HF_TOKEN", "")
    if token:
        for name in pass_token_as:
            os.environ[name] = token
    return token


def offline_session() -> str:
    """Environment of a run that reads models and datasets from the local cache only
    (fill the cache first with `prefetch_online`). Returns $HF_TOKEN ("" when unset)."""
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    return os.environ.get("HF_TOKEN", "")


def pip_install(*packages: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *packages], check=True)


_PREFETCH_HEAD = '''
import time
from huggingface_hub import snapshot_download
import datasets
def retry(fn, *a, **k):
    for i in range(15):
        try:
            return fn(*a, **k)
        except Exception as e:
            print("retry", getattr(fn, "__name__", "fn"), i, str(e)[:%d], flush=True)
            time.sleep(20)
    %s
'''


def prefetch_online(body: str, token: str | None = None, must_succeed: bool = False, message_width: int = 80) -> None:
    """Download models and datasets in a separate, online Python process.

    A run that sets HF_HUB_OFFLINE=1 cannot download, and the Hub's dataset API fails
    often enough that an evaluation should not depend on it. `body` is Python that uses
    `retry(fn, *args)` (15 attempts, 20 s apart), `snapshot_download` and `datasets`.
    With `must_succeed` a download that fails 15 times stops the run; otherwise it is
    reported and the run goes on. `token` is passed on for gated repositories.
    """
    failed = 'raise SystemExit("prefetch failed")' if must_succeed else "return None"
    env = {**os.environ, "HF_HUB_OFFLINE": "0", "HF_DATASETS_OFFLINE": "0"}
    if token is not None:
        env.update(HF_TOKEN=token, HUGGING_FACE_HUB_TOKEN=token)
    snippet = _PREFETCH_HEAD % (message_width, failed) + body
    if must_succeed:
        subprocess.run([sys.executable, "-c", snippet], env=env, check=True)
    else:
        subprocess.run([sys.executable, "-c", snippet], env=env)


def snapshot_lines(repos) -> str:
    """Prefetch body that downloads the given model repositories."""
    return (f"REPOS = {list(repos)!r}\n"
            "for repo in REPOS:\n"
            '    print("SNAP_OK" if retry(snapshot_download, repo) else "SNAP_FAIL", repo, flush=True)\n')


MMLU_LINES = ('cfgs = [c for c in retry(datasets.get_dataset_config_names, "cais/mmlu")\n'
              '        if c not in ("all", "auxiliary_train")]\n'
              "for c in cfgs:\n"
              '    retry(datasets.load_dataset, "cais/mmlu", c)\n')


# --------------------------------------------------------------------------- #
# Models and evaluations
# --------------------------------------------------------------------------- #
def load_hf_model(**kwargs):
    """An lm-eval HFLM model (transformers backend)."""
    from lm_eval.models.huggingface import HFLM
    return HFLM(**kwargs)


def load_vllm_model(**kwargs):
    """An lm-eval VLLM model (vLLM backend)."""
    from lm_eval.models.vllm_causallms import VLLM
    return VLLM(**kwargs)


def by_model(cells):
    """Group the cells of a run by model: yields ((eval_id, model_id, batch_size), [cells]).
    A model is loaded once and all its cells are run before the next one is loaded."""
    import itertools
    yield from ((key, list(group)) for key, group in
                itertools.groupby(cells, key=lambda c: (c["eval_id"], c["model_id"], c["batch_size"])))


def release(lm) -> None:
    """Free the GPU memory of a model that is no longer used."""
    import gc

    import torch
    del lm
    gc.collect()
    torch.cuda.empty_cache()


def lm_eval_version() -> str:
    import lm_eval
    return lm_eval.__version__


def seeded(seed: int, fewshot: bool = False) -> dict:
    """The seed arguments of simple_evaluate. `fewshot` also fixes the choice of few-shot examples."""
    seeds = {"random_seed": seed, "numpy_random_seed": seed, "torch_random_seed": seed}
    if fewshot:
        seeds["fewshot_random_seed"] = seed
    return seeds


def evaluate(lm, attempts: int = 1, wait: int = 0, note: str = "", message_width: int = 80, **kwargs) -> dict:
    """`lm_eval.simple_evaluate(model=lm, **kwargs)`, tried up to `attempts` times, `wait` seconds apart."""
    from lm_eval import simple_evaluate
    if attempts <= 1:
        return simple_evaluate(model=lm, **kwargs)
    last = None
    for attempt in range(attempts):
        try:
            return simple_evaluate(model=lm, **kwargs)
        except Exception as e:  # noqa: BLE001  any failure of one evaluation is retried
            last = e
            print(f"  [retry {attempt}] {note}: {str(e)[:message_width]}", flush=True)
            time.sleep(wait)
    raise last


def percent(metrics: dict, *keys: str, digits: int = 4):
    """The first of `keys` that `metrics` has, as a percentage; None when it has none of them."""
    for key in keys:
        if metrics.get(key) is not None:
            return round(float(metrics[key]) * 100.0, digits)
    return None


def run_cell(record: dict, evaluate_cell, score, note: str = "", message_width: int = 100) -> dict:
    """Run one cell and print its `RESULT {json}` line.

    `evaluate_cell()` returns the lm-eval results and `score(results)` the number that
    goes into `record["score"]`. A cell that fails is recorded with status "error" and
    the start of the message, and the run goes on with the next cell.
    """
    try:
        record["score"] = score(evaluate_cell())
        record["status"] = "ok"
        print("RESULT " + json.dumps(record), flush=True)
    except Exception as exc:  # noqa: BLE001  one failed cell must not end the session
        record["status"] = "error"
        record["reason"] = str(exc)[:200]
        print("RESULT " + json.dumps(record), flush=True)
        print(f"[cell-error] {note}: {str(exc)[:message_width]}", flush=True)
    return record
