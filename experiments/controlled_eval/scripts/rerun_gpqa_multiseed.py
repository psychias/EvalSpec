"""Powered, full-set, single-backend (hf) GPQA rerun -- the GPQA half of the
"beyond GSM8K" fix. GPQA (Idavidrein/gpqa) is small (448 items) so full-set x
multi-seed is cheap; the only obstacle was datasets 3.x dropping loading-script
support (GPQA ships as a loading script). We pin datasets<3, which still runs the
script, and load with an access-granted token. Seeds 42/123/7, three prompt
formats, n=12/format. One model per Colab session; set HF_TOKEN (with GPQA access).

    python rerun_gpqa_multiseed.py                                   # the run as published
    python rerun_gpqa_multiseed.py --dry-run                         # list its cells, load nothing
    python rerun_gpqa_multiseed.py --model ORG/NAME@8 --seeds 1 2 3 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common import lm_eval_runs as runs  # noqa: E402

MODELS = [("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct", 16)]
# GPQA is deterministic under fixed few-shot (seed changes nothing), so power the
# format ANOVA across MODELS: single seed, 8 diverse models -> n=8 per format.
SEEDS = [42]
N_SHOT = 5
TASK = "gpqa_main_n_shot"   # lm-eval GPQA main task (multiple-choice log-likelihood), respects num_fewshot


def cells(models, formats, seeds):
    """The cells of the run, in the order they are run."""
    for eval_id, model_id, batch in models:
        for fmt in formats:
            for seed in seeds:
                yield dict(eval_id=eval_id, model_id=model_id, batch_size=batch, task=TASK,
                           prompt_format=fmt, n_shot=N_SHOT, seed=seed)


def extract(results, task):
    return runs.percent(results["results"].get(task, {}), "acc_norm,none", "acc,none", "exact_match,none")


def setup():
    os.environ["HF_DATASETS_TRUST_REMOTE_CODE"] = "1"
    token = runs.online_session()
    print("[setup] installing lm-eval==0.4.11 + datasets<3 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    # datasets 3.x removed loading-script support that GPQA needs; pin back to 2.x.
    runs.pip_install("datasets==2.21.0")

    import datasets
    print(f"[setup] datasets {datasets.__version__}", flush=True)
    # The gated GPQA loading script's internal file download does not pick up the env
    # token; an explicit login authenticates the whole huggingface_hub session so the
    # script's downloads carry the (access-granted) token.
    if token:
        from huggingface_hub import login
        login(token=token, add_to_git_credential=False)
        print("[setup] hf login done", flush=True)
    # sanity: confirm GPQA is now loadable with the granted token
    try:
        datasets.load_dataset("Idavidrein/gpqa", "gpqa_main", trust_remote_code=True, token=token or None)
        print("[gpqa] dataset loads OK", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[gpqa] STILL FAILING: {str(e)[:160]}", flush=True)


def main(argv=None):
    args = runs.parse(runs.grid_parser(__doc__, MODELS, seeds=SEEDS), argv)
    plan = list(cells(args.models, args.formats, args.seeds))
    if args.dry_run:
        return runs.dry_run(plan)
    setup()
    for (eval_id, model_id, batch), model_cells in runs.by_model(plan):
        lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size="auto",
                                max_batch_size=batch, trust_remote_code=True)
        for c in model_cells:
            fmt, seed = c["prompt_format"], c["seed"]
            rec = dict(model_id=model_id, benchmark="GPQA", task_name=TASK,
                       temperature=0.0, prompt_format=fmt, n_shot=N_SHOT, random_seed=seed,
                       score=None, timestamp=runs.timestamp(),
                       eval_library_version=runs.lm_eval_version(), limit=None, backend="hf")
            runs.run_cell(rec, lambda: runs.evaluate(
                lm, attempts=3, wait=15, note=f"seed{seed}", message_width=90,
                tasks=[TASK], num_fewshot=N_SHOT, gen_kwargs=f"seed={seed}", limit=None,
                system_instruction=runs.FORMAT_TEMPLATES[fmt], apply_chat_template=True,
                fewshot_as_multiturn=False, **runs.seeded(seed, fewshot=True), **runs.QUIET),
                lambda r: extract(r, TASK), note=f"{model_id} {fmt} seed{seed}")
        runs.release(lm)
    print("[done] session complete", flush=True)


if __name__ == "__main__":
    main()
