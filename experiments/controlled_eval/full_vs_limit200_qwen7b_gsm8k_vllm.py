"""
Full-set vs limit=200 robustness check — vLLM backend (like-for-like with the grid).

Same cell as full_vs_limit200_qwen7b_gsm8k.py (Qwen2.5-7B-Instruct, GSM8K, 5-shot,
plain vs cot, temp 0.0) but on the *vLLM* backend the factorial grid used, so the
absolute numbers are directly comparable to the paper's vLLM limit=200 values
(plain ~40.2, cot ~27.7) rather than the hf-backend variant.

vLLM is pinned to 0.6.6.post1 because the current vLLM wheel is built against
CUDA 13 (libcudart.so.13), which Colab's CUDA-12 image cannot load; 0.6.6.post1
ships CUDA-12.1 wheels and pins torch 2.5.1 (pip downgrades torch to match).

Run on a Colab A100 GPU runtime. Reference (paper, vLLM, limit=200, 3 seeds):
plain ~40.2, cot ~27.7.

    python full_vs_limit200_qwen7b_gsm8k_vllm.py                          # the cell of the paper
    python full_vs_limit200_qwen7b_gsm8k_vllm.py --model ORG/NAME --limit 100
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common import lm_eval_runs as runs  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import full_vs_limit200_qwen7b_gsm8k as hf_check  # noqa: E402  the comparison itself, shared with the hf variant

GEN = "do_sample=False,temperature=0,seed=42"   # the grid's exact gen settings


def main(argv=None):
    args = hf_check.options(__doc__).parse_args(argv)
    # Pin a CUDA-12 vLLM (+ ray, which lm-eval 0.4.11's vLLM wrapper imports). This
    # downgrades torch to 2.5.1+cu121 to match the vLLM wheel.
    print("[setup] installing lm-eval==0.4.11 + vllm==0.6.6.post1 + ray ...", flush=True)
    runs.pip_install("lm-eval==0.4.11", "vllm==0.6.6.post1", "ray")
    lm = runs.load_vllm_model(pretrained=args.model, dtype="bfloat16",
                              gpu_memory_utilization=0.90, max_model_len=4096)
    hf_check.compare(lm, GEN, args.limit)       # reference: paper (vLLM), mean over 3 seeds


if __name__ == "__main__":
    main()
