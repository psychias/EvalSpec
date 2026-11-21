"""Reproduce OLv2's Gemma-2-9B BBH score (34.0968) under its exact config, to test
whether 34.10 is a deterministic fingerprint of the OLv2 pipeline (SEA-LION provenance
check, §5.3). OLv2 evaluated google/gemma-2-9b @ beb0c08e in bfloat16 on the
`leaderboard_bbh` task group (3-shot multiple-choice log-likelihood, acc_norm).

Determinism note: leaderboard_bbh is fixed-few-shot MC log-likelihood, so an exact
reproduction of 34.0968 confirms 34.10 is a reproducible fingerprint of this specific
(model_sha, dtype, harness, task) tuple -- i.e. SEA-LION's matching 34.1 reflects the
same OLv2 pipeline, not an independent measurement. It does NOT by itself separate
"imported the number" from "re-ran the identical pipeline" (both yield 34.0968).

Also runs the CoT-generation protocol arm (bbh_cot_fewshot) to re-confirm the ~34->~68
protocol swing: hitting exactly 34.10 requires OLv2's MC-log-likelihood protocol, so an
independent evaluator choosing a different (equally valid) BBH protocol would not.

Needs: google/gemma-2-9b license accepted on the token's HF account; set HF_TOKEN.
One Colab A100 session.

    python rerun_gemma2_9b_bbh.py
    python rerun_gemma2_9b_bbh.py --dry-run     # list the two arms, load nothing

The arms are the entries of ARMS; another protocol is another entry.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import json  # noqa: E402

from common import lm_eval_runs as runs  # noqa: E402

MODEL = "google/gemma-2-9b"
REVISION = "beb0c08e9eeb0548f3aca2ac870792825c357b7d"  # exact SHA OLv2 evaluated
# (lm-eval task, protocol written to the record, shots). OLv2 BBH = leaderboard_bbh, 3-shot MC log-likelihood
ARMS = [("leaderboard_bbh", "BBH-OLv2-protocol (MC log-lik)", 3),
        ("bbh_cot_fewshot", "BBH-CoT-generation", 3)]
SEED = 42


def extract(results, task):
    # group tasks aggregate under the group name; fall back to any *_norm mean
    return runs.percent(results["results"].get(task, {}), "acc_norm,none", "acc,none", "exact_match,none")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--revision", default=REVISION, help="commit of the model repository")
    ap.add_argument("--dry-run", action="store_true", help="print the arms and stop, without loading anything")
    args = ap.parse_args(argv)
    if args.dry_run:
        return runs.dry_run(dict(model=args.model, revision=args.revision, task=t, protocol=p, n_shot=n) for t, p, n in ARMS)
    token = runs.online_session()
    print("[setup] installing lm-eval==0.4.11 ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "accelerate")
    if token:
        from huggingface_hub import login
        login(token=token, add_to_git_credential=False)

    lm = runs.load_hf_model(pretrained=args.model, revision=args.revision, dtype="bfloat16",
                            batch_size="auto", max_batch_size=8)
    for task, label, nshot in ARMS:
        rec = dict(model_id=args.model, revision=args.revision, benchmark="BBH", task_name=task,
                   protocol=label, n_shot=nshot, backend="hf",
                   eval_library_version=runs.lm_eval_version(),
                   timestamp=runs.timestamp(), score=None)
        try:
            r = runs.evaluate(lm, tasks=[task], num_fewshot=nshot, **runs.seeded(SEED, fewshot=True), **runs.QUIET)
            rec["score"] = extract(r, task)
            rec["all_metrics"] = {k: v for k, v in r["results"].get(task, {}).items()
                                  if isinstance(v, (int, float))}
            rec["status"] = "ok"
        except Exception as exc:  # noqa: BLE001
            rec["status"] = "error"
            rec["reason"] = str(exc)[:200]
        print("RESULT " + json.dumps(rec), flush=True)
    print("[done] OLv2 raw BBH for google/gemma-2-9b @ beb0c08e was 34.0968; "
          "reproduce under leaderboard_bbh, compare to the CoT-generation arm.", flush=True)


if __name__ == "__main__":
    main()
