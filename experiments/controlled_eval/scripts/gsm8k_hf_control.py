"""Backend control at matched n: score GSM8K on the hf backend for the same four
models, three prompt formats, single seed, and full test set as the generalization
arm (ARC-Challenge/WinoGrande/OpenBookQA), so the GSM8K format effect can be read on
the SAME backend and the SAME n=4-per-format design as the log-likelihood benchmarks.

This disentangles inference backend from prompt format: the main grid scores GSM8K
under vLLM (generation is slow on hf), and this control confirms the format effect
is not a vLLM artefact. GSM8K is generation, exact_match strict-match (#### parser);
format via system_instruction + apply_chat_template; greedy (temperature 0); 5-shot.

One model per Colab session (swap MODELS). Mistral is gated: set HF_TOKEN in the
environment. Llama-3.1 uses the NousResearch mirror.

    python gsm8k_hf_control.py                                   # the run as published
    python gsm8k_hf_control.py --dry-run                         # list its cells, load nothing
    python gsm8k_hf_control.py --model ORG/NAME@8 --formats plain cot
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from common import lm_eval_runs as runs  # noqa: E402

# (repository to load, model id written to the record, batch size): one per session.
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
    runs.online_session()
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
                extract, note=f"{model_id} {fmt}", message_width=120)
        runs.release(lm)
    print("[done] session complete", flush=True)


if __name__ == "__main__":
    main()
