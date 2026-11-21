"""Unify + power the GPQA grid arm: full test set (drop limit=200), single hf
backend, and multiple seeds (more cells for the underpowered benchmark).

Mirrors the MMLU rerun (rerun_mmlu_hf.py): standard log-likelihood GPQA
(gpqa_main_zeroshot for 0-shot, gpqa_main_n_shot for 5-shot), format applied via
system_instruction + apply_chat_template, seeds {42,123,7}, limit=None. One model
per Colab session. GPQA (Idavidrein/gpqa) is a GATED dataset, so the online
prefetch authenticates with HF_TOKEN; the offline eval needs no token.
Llama-3.1 uses the NousResearch mirror (see rerun_mmlu_hf.py caveat).

    python rerun_gpqa_hf.py                                   # the run as published
    python rerun_gpqa_hf.py --dry-run                         # list its cells, load nothing
    python rerun_gpqa_hf.py --model ORG/NAME@8 --seeds 1 2 3 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common import lm_eval_runs as runs  # noqa: E402

MODELS = [("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct", 16)]
N_SHOTS = [0, 5]
SEEDS = [42, 123, 7]


def task_for(n_shot):
    return "gpqa_main_zeroshot" if n_shot == 0 else "gpqa_main_n_shot"


def cells(models, formats, seeds, n_shots=N_SHOTS):
    """The cells of the run, in the order they are run."""
    for eval_id, model_id, batch in models:
        for fmt in formats:
            for n in n_shots:
                for seed in seeds:
                    yield dict(eval_id=eval_id, model_id=model_id, batch_size=batch, task=task_for(n),
                               prompt_format=fmt, n_shot=n, seed=seed)


def extract(results):
    for k, m in results["results"].items():
        if k.startswith("gpqa"):
            v = m.get("acc,none", m.get("acc_norm,none", m.get("acc")))
            if v is not None:
                return round(float(v) * 100.0, 4)
    return None


def setup(models):
    token = runs.offline_session()             # gated GPQA dataset (and gated models)
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    print("[prefetch] caching model + Idavidrein/gpqa (online) ...", flush=True)
    runs.prefetch_online(runs.snapshot_lines(e for e, _, _ in models)
                         + "# GPQA main config (gated)\n"
                           'retry(datasets.load_dataset, "Idavidrein/gpqa", "gpqa_main")\n'
                           'print("SNAP_OK gpqa", flush=True)\n', token=token)
    print("[prefetch] done; running lm-eval OFFLINE", flush=True)


def main(argv=None):
    args = runs.parse(runs.grid_parser(__doc__, MODELS, seeds=SEEDS), argv)
    plan = list(cells(args.models, args.formats, args.seeds))
    if args.dry_run:
        return runs.dry_run(plan)
    setup(args.models)
    for (eval_id, model_id, batch), model_cells in runs.by_model(plan):
        lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size=batch)
        for c in model_cells:
            fmt, n, seed, task = c["prompt_format"], c["n_shot"], c["seed"], c["task"]
            rec = dict(model_id=model_id, benchmark="gpqa_main", task_name=task,
                       temperature=0.0, prompt_format=fmt, n_shot=n, random_seed=seed,
                       score=None, timestamp=runs.timestamp(),
                       eval_library_version=runs.lm_eval_version(), limit=None, backend="hf")
            runs.run_cell(rec, lambda: runs.evaluate(
                lm, tasks=[task], num_fewshot=n, gen_kwargs=f"seed={seed}", limit=None,
                system_instruction=runs.FORMAT_TEMPLATES[fmt], apply_chat_template=True,
                fewshot_as_multiturn=False, **runs.seeded(seed), **runs.QUIET),
                extract, note=f"{model_id} {fmt} n{n} s{seed}")
        runs.release(lm)
    print("[done] session complete", flush=True)


if __name__ == "__main__":
    main()
