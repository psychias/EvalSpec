"""
Rerun the two cells that were missing from the tables of Appendix M.4 and M.5, with lm-eval 0.4.11 (hf).

  Exp3 (harness version): Qwen2.5-7B-Instruct, GSM8K full, 5-shot, seed 123, 0.4.11
     -> the previously omitted 0.4.11 / 7B / seed-123 cell. Result: 78.32.
  Exp2 (scoring mode) :    Qwen2.5-14B-Instruct, MMLU, 5-shot, log-likelihood, full set
     -> the missing 14B log-likelihood cell (table previously had generation only,
        79.79). Result: 79.97  (|Delta| vs generation@full = 0.18 pp). The 14B is
        scored on the FULL set under both modes: its log-likelihood score is
        sample-sensitive (limit=100->80.32, limit=500->81.72, full->79.97), so only
        the full-set ll-vs-gen comparison is free of a sampling confound.

Backend = hf: vLLM's current wheel is CUDA-13 vs Colab's CUDA-12 image; Exp3 already
uses the hf backend, and MMLU log-likelihood is a deterministic multiple-choice
ranking that is backend-independent.

Two infrastructure issues, both handled by the prefetch-then-offline pattern below:
  1. Memory: the 14B model + MMLU log-likelihood does not fit a 40 GB GPU at the
     batch_size=8 used for the smaller models. The OOM is driven by batch size, NOT
     by the limit (peak memory = batch x seq-len, independent of #examples), so the
     14B cell simply drops to batch_size=4 and keeps limit=500 -- directly comparable
     to the other three Exp2 cells, just ~2x longer (~20 min for ~49k requests).
  2. HF's cais/mmlu tree API intermittently returns 504s. A successful download is
     not enough on its own, because datasets in ONLINE mode re-validates each subject
     against that same flaky API. Fix: in an ONLINE subprocess, snapshot the models
     and *build* every dataset config (load_dataset, with retries); then run lm-eval
     fully OFFLINE so nothing touches the HF API during the eval.

Run on a Colab A100. Prints each result as it completes.

    python rerun_missing_cells.py
    python rerun_missing_cells.py --dry-run     # list the two cells, load nothing

The two cells are the entries of CELLS; another cell is another entry.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import lm_eval_runs as runs  # noqa: E402

# One entry per cell: what it fills, the model, and how it is scored.
CELLS = [
    # Exp3: Qwen2.5-7B-Instruct, GSM8K full, 5-shot, lm-eval 0.4.11, seed 123
    dict(key="E3_7B_gsm8k_0411_seed123", model="Qwen/Qwen2.5-7B-Instruct", batch_size=48, task="gsm8k", seed=123,
         metrics=("exact_match,strict-match", "exact_match,flexible-extract"),
         label="[Exp3] Qwen2.5-7B-Instruct GSM8K 5-shot, 0.4.11, seed 123 (full 1319)"),
    # Exp2: Qwen2.5-14B-Instruct, MMLU 5-shot, log-likelihood, full test set.
    # batch_size=4 so the 14B bf16 model fits a 40 GB GPU; limit=None (full 14042) for an
    # exact same-sample comparison to generation@full (the ll score is sample-sensitive).
    dict(key="E2_14B_mmlu_loglikelihood_full", model="Qwen/Qwen2.5-14B-Instruct", batch_size=4, task="mmlu", seed=42,
         metrics=("acc,none", "acc"),
         label="[Exp2] Qwen2.5-14B-Instruct MMLU 5-shot log-likelihood (full 14042)"),
]
# Datasets must be *built* (load_dataset), not just downloaded: snapshot_download
# only caches raw files, whereas datasets in offline mode needs a built arrow cache.
PREFETCH = '''retry(snapshot_download, "Qwen/Qwen2.5-7B-Instruct")
retry(snapshot_download, "Qwen/Qwen2.5-14B-Instruct")
print("SNAP_OK models", flush=True)
retry(datasets.load_dataset, "gsm8k", "main")
''' + runs.MMLU_LINES + '''print("SNAP_OK datasets", len(cfgs), "mmlu configs", flush=True)
'''


def run(cell):
    """Score one cell on the full test set, 5-shot, and print it."""
    lm = runs.load_hf_model(pretrained=cell["model"], dtype="bfloat16", batch_size=cell["batch_size"])
    r = runs.evaluate(lm, tasks=[cell["task"]], num_fewshot=5, limit=None, **runs.seeded(cell["seed"], fewshot=True))
    m = r["results"][cell["task"]]
    first, second = cell["metrics"]
    value = round(100 * m.get(first, m.get(second)), 2)
    print(f"{cell['label']}: {value}", flush=True)
    runs.release(lm)
    return value


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the cells and stop, without loading anything")
    args = ap.parse_args(argv)
    if args.dry_run:
        return runs.dry_run({k: v for k, v in c.items() if k != "label"} for c in CELLS)
    # Parent runs OFFLINE: transformers + datasets read only from the local cache that
    # the online subprocess below populates, so the flaky cais/mmlu API is never hit
    # and the (already-cached) models load without a network round-trip.
    runs.offline_session()
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    # Prefetch models + datasets in an ONLINE subprocess (retries past the 504s).
    print("[prefetch] caching models + gsm8k + cais/mmlu (online subprocess) ...", flush=True)
    runs.prefetch_online(PREFETCH, must_succeed=True, message_width=70)
    print("[prefetch] done; running lm-eval OFFLINE", flush=True)
    values = {cell["key"]: run(cell) for cell in CELLS}
    print("\nRESULT  " + "  ".join(f"{key}={value}" for key, value in values.items()), flush=True)


if __name__ == "__main__":
    main()
