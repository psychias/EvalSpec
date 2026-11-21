"""Rerun the factorial-grid MMLU cells on the hf backend (all 4 models, replacing the
mixed vLLM set of which 6 cells failed). Faithful to the original vLLM notebook
(Cell 3/6): standard log-likelihood `mmlu` task, format applied via system_instruction
+ apply_chat_template=True, num_fewshot in {0,5}, limit=200 (per subject), temp 0,
seed 42. MMLU is log-likelihood => backend-independent, so hf reproduces the vLLM
numbers and fills the failed cells; the per-benchmark ANOVA only needs MMLU internally
consistent, which an all-hf sweep guarantees.

One model per Colab session (each cell is ~8-35 min; 24 cells > one session). Set
MODELS to the session's model(s). Results print as `RESULT {json}` lines (captured
locally and appended to controlled_eval_results.jsonl). Same prefetch-then-offline
pattern; gated Mistral needs HF_TOKEN injected; Llama uses the ungated NousResearch
mirror but is recorded under its canonical meta-llama id.

    python rerun_mmlu_hf.py                                   # the run as published
    python rerun_mmlu_hf.py --dry-run                         # list its cells, load nothing
    python rerun_mmlu_hf.py --model ORG/NAME@8 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common import lm_eval_runs as runs  # noqa: E402

# (repository to load, model id written to the record, batch size). Run ONE model per
# Colab session (each cell is ~2-16 min; 24 cells exceed one session). The grid models:
#   mistralai/Mistral-7B-Instruct-v0.3@8     gated: set HF_TOKEN
#   Qwen/Qwen2.5-7B-Instruct@8
#   Qwen/Qwen2.5-14B-Instruct@4              14B -> batch 4
# Llama-3.1-8B is NOT re-scored here: apply_chat_template=True makes the score
# depend on the chat template, and the only ungated weights (NousResearch mirror)
# ship a different template (diverges up to ~13 pp), so Llama keeps its original
# vLLM grid values (backend-independence holds for the other three: hf vs vLLM
# agree within 0.5 pp, so the hf cells pool with the vLLM Llama cells unbiased).
MODELS = [("Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-14B-Instruct", 4)]
N_SHOTS = [0, 5]
LIMIT = 200
SEED = 42


def cells(models, formats, seeds, n_shots=N_SHOTS):
    """The cells of the run, in the order they are run."""
    for eval_id, model_id, batch in models:
        for fmt in formats:
            for n in n_shots:
                for seed in seeds:
                    yield dict(eval_id=eval_id, model_id=model_id, batch_size=batch, task="mmlu",
                               prompt_format=fmt, n_shot=n, seed=seed)


def extract(results):
    m = results["results"]["mmlu"]
    v = m.get("acc,none", m.get("acc"))
    return round(float(v) * 100.0, 4)


def setup(models):
    token = runs.offline_session()             # only needed for gated Mistral
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    print("[prefetch] caching models + cais/mmlu (online subprocess) ...", flush=True)
    runs.prefetch_online(runs.snapshot_lines(e for e, _, _ in models) + runs.MMLU_LINES
                         + 'print("SNAP_OK mmlu", len(cfgs), "configs", flush=True)\n', token=token)
    print("[prefetch] done; running lm-eval OFFLINE", flush=True)


def main(argv=None):
    ap = runs.grid_parser(__doc__, MODELS, seeds=[SEED])
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"questions per subject (default: {LIMIT})")
    args = runs.parse(ap, argv)
    plan = list(cells(args.models, args.formats, args.seeds))
    if args.dry_run:
        return runs.dry_run(plan)
    setup(args.models)
    for (eval_id, model_id, batch), model_cells in runs.by_model(plan):
        lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size=batch)
        for c in model_cells:
            fmt, n, seed = c["prompt_format"], c["n_shot"], c["seed"]
            rec = dict(model_id=model_id, benchmark="mmlu", temperature=0.0,
                       prompt_format=fmt, n_shot=n, random_seed=seed, score=None,
                       timestamp=runs.timestamp(),
                       eval_library_version=runs.lm_eval_version(), limit=args.limit,
                       backend="hf")
            runs.run_cell(rec, lambda: runs.evaluate(
                lm, tasks=["mmlu"], num_fewshot=n, gen_kwargs=f"seed={seed}", limit=args.limit,
                system_instruction=runs.FORMAT_TEMPLATES[fmt], apply_chat_template=True,
                fewshot_as_multiturn=False, **runs.seeded(seed), **runs.QUIET),
                extract, note=f"{model_id} {fmt} n{n}", message_width=120)
        runs.release(lm)
    print("[done] session complete", flush=True)


if __name__ == "__main__":
    main()
