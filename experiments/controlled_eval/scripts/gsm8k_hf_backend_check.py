"""Backend control: verify the GSM8K prompt-format effect replicates on the hf
backend, disentangling inference backend from prompt format.

The main grid scores GSM8K under vLLM (generation is slow on hf, which is why the
grid uses vLLM there). To check the format effect is not a vLLM artefact, we re-run
Qwen2.5-7B-Instruct on GSM8K, all three formats (plain/instruct/cot), 5-shot,
greedy, full test set, on the hf backend and compare the plain/instruct/cot gap to
the vLLM grid's. Format applied via system_instruction + apply_chat_template; GSM8K
exact_match strict-match (the #### parser).

    python gsm8k_hf_backend_check.py                                   # the run as published
    python gsm8k_hf_backend_check.py --dry-run                         # list its cells, load nothing
    python gsm8k_hf_backend_check.py --model ORG/NAME@8 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common import lm_eval_runs as runs  # noqa: E402

MODELS = [("Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-7B-Instruct", 16)]
SEED = 42
N_SHOT = 5


def cells(models, formats, seeds):
    """The cells of the run, in the order they are run."""
    for eval_id, model_id, batch in models:
        for fmt in formats:
            for seed in seeds:
                yield dict(eval_id=eval_id, model_id=model_id, batch_size=batch, task="gsm8k",
                           prompt_format=fmt, n_shot=N_SHOT, seed=seed)


def extract(results):
    m = results["results"]["gsm8k"]
    return round(100 * m.get("exact_match,strict-match", m.get("exact_match,flexible-extract")), 4)


def main(argv=None):
    args = runs.parse(runs.grid_parser(__doc__, MODELS, seeds=[SEED]), argv)
    plan = list(cells(args.models, args.formats, args.seeds))
    if args.dry_run:
        return runs.dry_run(plan)
    runs.online_session(pass_token_as=())
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    for (eval_id, model_id, batch), model_cells in runs.by_model(plan):
        lm = runs.load_hf_model(pretrained=eval_id, dtype="bfloat16", batch_size=batch)
        for c in model_cells:
            fmt, seed = c["prompt_format"], c["seed"]
            rec = dict(model_id=model_id, benchmark="gsm8k", backend="hf", prompt_format=fmt,
                       n_shot=N_SHOT, temperature=0.0, random_seed=seed, limit=None,
                       timestamp=runs.timestamp(),
                       eval_library_version=runs.lm_eval_version())
            runs.run_cell(rec, lambda: runs.evaluate(
                lm, tasks=["gsm8k"], num_fewshot=N_SHOT, gen_kwargs="do_sample=False", limit=None,
                system_instruction=runs.FORMAT_TEMPLATES[fmt], apply_chat_template=True,
                fewshot_as_multiturn=False, **runs.seeded(seed), **runs.QUIET),
                extract, note=fmt, message_width=120)
        runs.release(lm)
    print("[done]", flush=True)


if __name__ == "__main__":
    main()
