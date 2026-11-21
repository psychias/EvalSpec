"""Generalize the factorial grid: add three more benchmarks on a single common
backend (hf), full test set (no limit=200), to test whether the prompt-format
effect and the scoring-mode diagnostic (§5.1) hold beyond the original
benchmarks.

New benchmarks (all open, small, log-likelihood multiple-choice, fit the
MMLU-style format x n-shot design): ARC-Challenge, WinoGrande, OpenBookQA. The
diagnostic predicts a small prompt-format effect on these (answer recovered by
ranking), in contrast to the large effect on the generation benchmarks GSM8K/BBH.
(HellaSwag was considered but its full 10k-item set makes each cell ~25 min; the
three chosen benchmarks are all <2k items so the full-set sweep stays tractable.)

Format applied via system_instruction + apply_chat_template; seed 42; limit=None.
Runs ONLINE (these datasets are small and stable, unlike the flaky cais/mmlu, so
no offline-prefetch dance is needed); a retry wraps transient dataset fetches.
One model per Colab session. Mistral is gated: set HF_TOKEN in the environment
(injected for the run); Llama-3.1 uses the NousResearch mirror.

    python rerun_generalization_hf.py                                   # the run as published
    python rerun_generalization_hf.py --dry-run                         # list its cells, load nothing
    python rerun_generalization_hf.py --model ORG/NAME@8 --seeds 1 2 3 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common import lm_eval_runs as runs  # noqa: E402

MODELS = [("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct", 16)]
# (lm-eval task, benchmark name in the record)
BENCHES = [("arc_challenge", "ARC-Challenge"),
           ("winogrande", "WinoGrande"),
           ("openbookqa", "OpenBookQA")]
N_SHOTS = [0, 5]
SEEDS = [42]


def cells(models, formats, seeds, benches=BENCHES, n_shots=N_SHOTS):
    """The cells of the run, in the order they are run."""
    for eval_id, model_id, batch in models:
        for task, label in benches:
            for fmt in formats:
                for n in n_shots:
                    for seed in seeds:
                        yield dict(eval_id=eval_id, model_id=model_id, batch_size=batch, task=task, benchmark=label,
                                   prompt_format=fmt, n_shot=n, seed=seed)


def extract(results, task):
    m = results["results"].get(task, {})
    v = m.get("acc_norm,none", m.get("acc,none", m.get("acc")))
    return round(float(v) * 100.0, 4) if v is not None else None


def setup():
    runs.online_session(pass_token_as=("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"))
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")


def main(argv=None):
    args = runs.parse(runs.grid_parser(__doc__, MODELS, seeds=SEEDS), argv)
    plan = list(cells(args.models, args.formats, args.seeds))
    if args.dry_run:
        return runs.dry_run(plan)
    setup()
    for (eval_id, model_id, batch), model_cells in runs.by_model(plan):
        lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size=batch)
        for c in model_cells:
            task, label, fmt, n, seed = c["task"], c["benchmark"], c["prompt_format"], c["n_shot"], c["seed"]
            rec = dict(model_id=model_id, benchmark=label, task_name=task,
                       temperature=0.0, prompt_format=fmt, n_shot=n, random_seed=seed,
                       score=None, timestamp=runs.timestamp(),
                       eval_library_version=runs.lm_eval_version(), limit=None, backend="hf")
            runs.run_cell(rec, lambda: runs.evaluate(
                lm, attempts=4, wait=20, note=f"{task} n{n}",
                tasks=[task], num_fewshot=n, gen_kwargs=f"seed={seed}", limit=None,
                system_instruction=runs.FORMAT_TEMPLATES[fmt], apply_chat_template=True,
                fewshot_as_multiturn=False, **runs.seeded(seed), **runs.QUIET),
                lambda r: extract(r, task), note=f"{model_id} {label} {fmt} n{n}")
        runs.release(lm)
    print("[done] session complete", flush=True)


if __name__ == "__main__":
    main()
