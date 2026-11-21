"""Powered, full-set, single-backend (hf) reruns on MMLU and GPQA so the factorial
grid's format claims are as strong there as on GSM8K. Addresses "the strongest
conclusions are limited to GSM8K": full MMLU test set (no limit=200) and full GPQA,
three prompt formats, seeds 123 and 7 (added to the existing seed-42 grid cells to
give n=12 per format), all on the hf backend.

MMLU uses a prefetch-then-offline dance: cais/mmlu intermittently 504s under load,
so we snapshot every config online first, then run lm-eval with HF_HUB_OFFLINE=1.
GPQA (Idavidrein/gpqa) is gated; we attempt it online with the token and report
cleanly if access is denied rather than aborting the MMLU run.

One model per Colab session (swap MODELS). Mistral gated -> set HF_TOKEN.

    python rerun_mmlu_gpqa_multiseed.py                                   # the run as published
    python rerun_mmlu_gpqa_multiseed.py --dry-run                         # list its cells, load nothing
    python rerun_mmlu_gpqa_multiseed.py --model ORG/NAME@8 --seeds 1 2 3 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import time  # noqa: E402

from common import lm_eval_runs as runs  # noqa: E402

MODELS = [("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct", 16)]
# MMLU/GPQA are deterministic under fixed-dev few-shot (seed changes nothing), so we
# power the format ANOVA across MODELS instead: 8 diverse models, single seed, gives
# n=8 per format. (Random-few-shot benchmarks like ARC/WinoGrande/OpenBookQA are
# powered by seeds separately; MMLU/GPQA cannot be.)
SEEDS = [42]
N_SHOT = 5
# Full-set MMLU (14k items) x multi-seed is ~50 min/cell (impractical). MMLU is a
# GROUP of 57 subjects, so an integer `limit` applies per-subject and doesn't subset
# (each subject has <2000 items). A FRACTIONAL limit does: 0.15 -> 15% of each
# subject (~2100 items total, stratified across all subjects), ~7 min/cell. The
# multi-seed design (n=12/format) is what actually powers the format ANOVA.
MMLU_LIMIT = 0.15
# (lm-eval task, benchmark name in the record)
BENCHES = [("mmlu", "MMLU"), ("gpqa_main_zeroshot", "GPQA")]


def cells(models, formats, seeds, benches=BENCHES):
    """The cells of the run, in the order they are run. MMLU is read from the local cache."""
    for eval_id, model_id, batch in models:
        for task, label in benches:
            for fmt in formats:
                for seed in seeds:
                    yield dict(eval_id=eval_id, model_id=model_id, batch_size=batch, task=task, benchmark=label,
                               prompt_format=fmt, n_shot=N_SHOT, seed=seed,
                               limit=MMLU_LIMIT if label == "MMLU" else None, offline=label == "MMLU")


def prefetch_mmlu():
    """Snapshot the MMLU model-agnostic dataset online (retry) so the eval can run
    fully offline afterwards, dodging the cais/mmlu 504s."""
    import datasets
    for attempt in range(5):
        try:
            datasets.load_dataset("cais/mmlu", "all", trust_remote_code=True)
            print("[prefetch] cais/mmlu 'all' cached", flush=True)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[prefetch retry {attempt}] {str(e)[:90]}", flush=True)
            time.sleep(30)
    print("[prefetch] FAILED to cache MMLU; will still try online", flush=True)
    return False


def gpqa_available():
    try:
        import datasets
        datasets.load_dataset("Idavidrein/gpqa", "gpqa_main", trust_remote_code=True)
        print("[gpqa] gated dataset accessible", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[gpqa] UNAVAILABLE (gated): {str(e)[:120]}", flush=True)
        return False


def extract(results, task):
    m = results["results"].get(task, {})
    score = runs.percent(m, "acc_norm,none", "acc,none", "exact_match,none")
    return score if score is not None else runs.percent(m, "acc")


def evaluate_cell(lm, cell):
    """One evaluation, offline for the cells that ask for it; the environment is put back afterwards."""
    seed = cell["seed"]
    env_bak = dict(os.environ)
    if cell["offline"]:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"
    try:
        return runs.evaluate(
            lm, attempts=3, wait=15, note=f"{cell['task']} seed{seed}",
            tasks=[cell["task"]], num_fewshot=cell["n_shot"], gen_kwargs=f"seed={seed}", limit=cell["limit"],
            system_instruction=runs.FORMAT_TEMPLATES[cell["prompt_format"]], apply_chat_template=True,
            fewshot_as_multiturn=False, **runs.seeded(seed, fewshot=True), **runs.QUIET)
    finally:
        os.environ.clear()
        os.environ.update(env_bak)


def main(argv=None):
    args = runs.parse(runs.grid_parser(__doc__, MODELS, seeds=SEEDS), argv)
    plan = list(cells(args.models, args.formats, args.seeds))
    if args.dry_run:
        return runs.dry_run(plan)
    runs.online_session()
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    prefetch_mmlu()
    have_gpqa = gpqa_available()
    for (eval_id, model_id, batch), model_cells in runs.by_model(plan):
        # full-set MMLU with 5-shot chat-template contexts OOMs at large fixed batch;
        # "auto" finds the largest batch that fits.
        lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size="auto",
                                max_batch_size=batch, trust_remote_code=True)
        skipped = False
        for c in model_cells:
            task, label, fmt, seed = c["task"], c["benchmark"], c["prompt_format"], c["seed"]
            if label == "GPQA" and not have_gpqa:
                if not skipped:
                    print(f"[skip] GPQA unavailable for {model_id}", flush=True)
                    skipped = True
                continue
            rec = dict(model_id=model_id, benchmark=label, task_name=task,
                       temperature=0.0, prompt_format=fmt, n_shot=N_SHOT, random_seed=seed,
                       score=None, timestamp=runs.timestamp(),
                       eval_library_version=runs.lm_eval_version(), limit=c["limit"], backend="hf")
            runs.run_cell(rec, lambda: evaluate_cell(lm, c), lambda r: extract(r, task),
                          note=f"{model_id} {label} {fmt} seed{seed}")
        runs.release(lm)
    print("[done] session complete", flush=True)


if __name__ == "__main__":
    main()
