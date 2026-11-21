#!/usr/bin/env python3
"""Writes the bundled datastore sample into ../../datastore/data.

The full corpus of the paper (46,559 records) lives in the Hugging Face datastore.
This sample holds the records that the paper and its code repository quote in full:
the case studies of Section 5, the cross-source pairs shipped with the repository,
and the authors' own controlled runs. Every file says where its numbers come from
(source_metadata.additional_details.sample_origin). Nothing here is invented.

Run it again only to change the sample:  python source/snapshot/build_snapshot.py

The address of the code repository, which the provenance links point into, is links.code
in config.json. The sample itself is the three functions leaderboards(), papers() and
controlled_runs(): a record is added to the sample by adding it to one of them.
"""
import json
import pathlib
import shutil
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "datastore"
RETRIEVED = "1794873600"            # 2026-11-17T00:00:00Z, when the sample was assembled
CODE = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["links"]["code"].rstrip("/")
REPO = CODE + "/tree/main/"


def uid(key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "evalspec-sample/" + key))


def result(bench, score, lo=0.0, hi=100.0, metric=None, shots=None, details=None, raw=None, judges=None, ts=None, temperature=None):
    metric_config = {"lower_is_better": False, "score_type": "continuous", "min_score": lo, "max_score": hi}
    if metric:
        metric_config = {"metric_name": metric, **metric_config}
    if judges:
        metric_config["llm_scoring"] = {"judges": [{"model_info": {"name": j.split("/")[-1], "id": j}, "temperature": 0.0} for j in judges],
                                        "input_prompt": "MT-Bench single-answer grading prompt; see the code repository"}
    args = {k: v for k, v in (("shots", shots), ("temperature", temperature)) if v is not None}
    out = {"evaluation_name": bench,
           "source_data": {"dataset_name": bench, "source_type": "other"},
           "metric_config": metric_config,
           "score_details": {"score": score, **({"details": {"raw_score": str(raw)}} if raw is not None else {})},
           "generation_config": {"generation_args": args, "additional_details": details or {}}}
    if ts:
        out["evaluation_timestamp"] = ts
    return out


def write(folder, doc, name):
    path = OUT / "data" / folder / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def document(eval_id, source, model, library, results, origin, tag, extra=None, relationship="third_party", kind="documentation"):
    name, org, url = source
    model_id, model_name, developer = model
    details = {"evidence_source": tag, "sample_origin": origin, **(extra or {})}
    return {"schema_version": "0.2.1", "evaluation_id": eval_id, "retrieved_timestamp": RETRIEVED,
            "source_metadata": {"source_name": name, "source_type": kind, "source_organization_name": org,
                                "source_organization_url": url, "evaluator_relationship": relationship,
                                "additional_details": details},
            "eval_library": {"name": library[0], "version": library[1]},
            "model_info": {"name": model_name, "id": model_id, "developer": developer},
            "evaluation_results": results}


# ------------------------------------------------------------------ predicted: leaderboards and repositories

OLV2 = ("Open LLM Leaderboard v2", "HuggingFace", "https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard")
OLV2_SHOTS = {"IFEval": 0, "BBH": 3, "MATH Lvl 5": 4, "GPQA": 0, "MuSR": 0, "MMLU-Pro": 5}
OLV2_METRIC = {"IFEval": "prompt_level_strict_acc", "GPQA": "acc_norm"}
CSV = "experiments/harness_reeval/all_harness_pairs.csv in the code repository"
OLV2_ROWS = [   # model id, {benchmark: (displayed, raw or None)}, uuid if the real file name is known, origin
    ("google/gemma-2-9b", {"IFEval": (20.4, 20.4), "BBH": (34.1, 53.77), "MATH Lvl 5": (13.44, 13.44), "GPQA": (10.51, 32.89),
                           "MuSR": (14.3, 44.61), "MMLU-Pro": (34.48, 41.03)}, None,
     "Appendix E of the paper: the leaderboard's API row for google/gemma-2-9b, retrieved 2026-07-30"),
    ("google/gemma-7b", {"BBH": (21.12, 43.62)}, None, "Section 5.1 and Appendix G of the paper"),
    ("google/gemma-2-2b", {"BBH": (11.76, 36.56)}, "75bba401-bec5-4285-9fd9-5f20c5547c85", "Section 5.1 of the paper"),
    ("TIGER-Lab/MAmmoTH2-7B-Plus", {"BBH": (18.93, 42.35)}, None, "Section 5.1 of the paper"),
    ("allenai/Llama-3.1-Tulu-3-70B-SFT", {"IFEval": (80.51, None), "BBH": (42.02, None), "GPQA": (12.64, None), "MuSR": (24.49, None),
                                          "MMLU-Pro": (40.27, None)}, "f718ae88-5c2c-4ba2-8de1-0c925f0c92b4", CSV),
    ("allenai/Llama-3.1-Tulu-3-8B", {"IFEval": (82.67, None), "BBH": (16.67, None), "GPQA": (6.49, None), "MuSR": (10.45, None),
                                     "MMLU-Pro": (20.3, None)}, "87e746b0-6548-4248-b1ad-97128afad515", CSV),
    ("Qwen/Qwen2.5-72B-Instruct", {"GPQA": (16.67, None)}, "c9325daa-7e4d-4e5a-8d1f-e978a510a68f", CSV),
]

CARD = ("HuggingFace Model Card", "HuggingFace", "https://huggingface.co")
CARD_ROWS = [   # model id, harness named on the card, [(benchmark as the card names it, score, metric, shots)], uuid, origin
    ("allenai/Llama-3.1-Tulu-3-70B-SFT", "vllm", [("IFEval", 80.51, "strict accuracy", 0), ("BBH", 42.02, "normalized accuracy", 3),
     ("GPQA", 12.64, "acc_norm", 0), ("MuSR", 24.49, "acc_norm", 0), ("MMLU-Pro", 40.27, "accuracy", 5)],
     "35173779-c8ac-4928-8011-f46000bd8fec", CSV),
    ("allenai/Llama-3.1-Tulu-3-8B", "vllm", [("IFEval (0-Shot)", 82.55, "averaged accuracy", 0), ("BBH (3-Shot)", 16.86, "normalized accuracy", 3),
     ("MATH Lvl 5 (4-Shot)", 18.88, None, 4), ("GPQA (0-shot)", 6.26, "acc_norm", 0), ("MuSR (0-shot)", 10.52, "acc_norm", 0),
     ("MMLU-PRO (5-shot)", 20.23, "accuracy", 5)],
     "66306650-e0a6-47ac-a073-d7ce41b40907", CSV + "; experiments/evalspec_worked_example/records"),
    ("bigcode/StarCoder2-15B", "transformers", [("HumanEval+", 37.8, "pass@1", None)], "177bab07-99da-465d-b6ae-94dcf376e57f", CSV),
    ("bigcode/starcoder2-15B-instruct-v0.1", "transformers", [("HumanEval+", 63.4, "pass@1", None), ("MBPP+", 61.2, "pass@1", None)],
     "0fe3e3d7-c176-40e1-a15b-a259e0229d9e", CSV),
    ("bigcode/StarCoder2-3B", "transformers", [("HumanEval+", 27.4, "pass@1", None)], None, CSV),
    ("bigcode/StarCoder2-7B", "transformers", [("HumanEval+", 29.9, "pass@1", None)], None, CSV),
]

EVALPLUS = ("EvalPlus Leaderboard", "EvalPlus", "https://evalplus.github.io/leaderboard.html")
EVALPLUS_ROWS = [
    ("bigcode/StarCoder2-15B", [("HumanEval+", 37.8, 0)], "9e6b55f6-03b1-474a-8dbc-defe1dd27423"),
    ("bigcode/starcoder2-15B-instruct-v0.1", [("HumanEval+", 60.4, 0), ("MBPP+", 65.1, 3)], "1f5d8592-8536-4a83-b875-27f3a23c3f97"),
    ("bigcode/StarCoder2-3B", [("HumanEval+", 27.4, 0)], None),
    ("bigcode/StarCoder2-7B", [("HumanEval+", 29.9, 0)], None),
]

PWC = ("Papers With Code", "Papers With Code", "https://paperswithcode.com")


def leaderboards():
    for model_id, scores, name, origin in OLV2_ROWS:
        org, tail = model_id.split("/")
        results = [result(b, shown, metric=OLV2_METRIC.get(b, "accuracy"), shots=OLV2_SHOTS[b],
                          details={"source": "open_llm_leaderboard_v2"}, raw=raw) for b, (shown, raw) in scores.items()]
        doc = document(f"open_llm_leaderboard_v2/{model_id.replace('/', '_')}/{RETRIEVED}", OLV2, (model_id, tail, org),
                       ("lm_eval", "unknown"), results, origin, "documentation-inferred")
        write(f"open_llm_leaderboard_v2/{org}/{tail}", doc, name or uid("olv2/" + model_id))
    for model_id, harness, rows, name, origin in CARD_ROWS:
        org, tail = model_id.split("/")
        results = [result(b, s, metric=m, shots=n, details={"source": "hf_model_card", "harness": harness}) for b, s, m, n in rows]
        doc = document(f"hf_model_card/{model_id.replace('/', '_')}/{RETRIEVED}", CARD, (model_id, tail, org),
                       (harness, "unknown"), results, origin, "documentation-inferred", relationship="first_party")
        write(f"hf_model_card/{org}/{tail}", doc, name or uid("card/" + model_id))
    for model_id, rows, name in EVALPLUS_ROWS:
        org, tail = model_id.split("/")
        results = [result(b, s, metric="pass@1", shots=n, details={"source": "evalplus"}) for b, s, n in rows]
        doc = document(f"evalplus/{model_id.replace('/', '_')}/{RETRIEVED}", EVALPLUS, (model_id, tail, org),
                       ("evalplus", "unknown"), results, CSV, "documentation-inferred")
        write(f"evalplus/{org}/{tail}", doc, name or uid("evalplus/" + model_id))
    doc = document(f"papers_with_code/Qwen_Qwen2.5-72B-Instruct/{RETRIEVED}", PWC, ("Qwen/Qwen2.5-72B-Instruct", "Qwen2.5-72B-Instruct", "Qwen"),
                   ("unknown", "unknown"), [result("GPQA", 49.0, metric="Accuracy", details={"source": "papers_with_code"})],
                   CSV, "documentation-inferred")
    write("papers_with_code/Qwen/Qwen2.5-72B-Instruct", doc, "79f27555-6c60-458a-8e3a-2ccaf5305af8")


# ------------------------------------------------------------------ predicted: results read from papers by an LLM

PAPERS = {      # folder name in the datastore, title, arXiv id
    "jamba": ("Jamba__Hybrid_Transformer-Mamba_Language_Model", "Jamba: Hybrid Transformer-Mamba Language Model", "2403.19887"),
    "recurrentgemma": ("RecurrentGemma__Moving_Past_Transformers_for_Efficient_Open_LMs", "RecurrentGemma: Moving Past Transformers for Efficient Open LMs", "2404.07839"),
    "mammoth2": ("MAmmoTH2__Scaling_Instructions_from_the_Web", "MAmmoTH2: Scaling Instructions from the Web", "2405.03548"),
    "instella": ("Instella__Fully_Open_Language_Models_with_Stellar_Performance", "Instella: Fully Open Language Models with Stellar Performance", "2511.10628"),
    "codellama": ("Code_Llama__Open_Foundation_Models_for_Code", "Code Llama: Open Foundation Models for Code", "2308.12950"),
    "olmo": ("OLMo__Accelerating_the_Science_of_Language_Models", "OLMo: Accelerating the Science of Language Models", "2402.00838"),
    "reka": ("Reka_Core__Flash__and_Edge__Powerful_Multimodal_Language_Models", "Reka Core, Flash, and Edge: A Series of Powerful Multimodal Language Models", "2404.12387"),
    "falcon2": ("Falcon2-11B_Technical_Report", "Falcon2-11B Technical Report", "2407.14885"),
    "phi3": ("Phi-3_Technical_Report__A_Small_Language_Model", "Phi-3 Technical Report: A Highly Capable Language Model Locally on Your Phone", "2404.14219"),
    "sealion": ("SEA-LION__Southeast_Asian_Languages_in_One_Network", "SEA-LION: Southeast Asian Languages in One Network", "2504.05747"),
    "gemma2": ("Gemma_2__Improving_Open_Language_Models_at_a_Practical_Size", "Gemma 2: Improving Open Language Models at a Practical Size", "2408.00118"),
    "gemma3": ("Gemma_3_Technical_Report", "Gemma 3 Technical Report", "2503.19786"),
}
PAPER_ROWS = [  # paper, model as the paper names it, developer, benchmark, score, metric, shots, own model?, uuid, note
    ("jamba", "Gemma-7B", "Google", "BBH", 55.10, None, None, False, "be0e2a07-3fa8-4ca2-9913-ca1ef4d430bc", "The paper's case study describes this score as chain-of-thought generation."),
    ("recurrentgemma", "Gemma-7B", "Google", "BBH", 55.10, "exact_match", 3, True, "546463f1-f907-4f3d-b473-361a9272f45e", "The paper's case study describes this score as chain-of-thought generation."),
    ("mammoth2", "Gemma-7B", "Google", "BBH", 57.40, None, None, False, "9889a234-be7c-4bde-ac71-c0e34975f4d6", "The paper's case study describes this score as chain-of-thought generation."),
    ("instella", "Gemma-2-2B", "Google", "BBH", 40.80, None, None, False, "64693042-ed44-4da0-8307-fbaff0d0d5c5", "The paper's case study describes this score as chain-of-thought generation."),
    ("mammoth2", "MAmmoTH2-7B-Plus", "TIGER-Lab", "BBH", 63.10, None, None, True, "1e625eba-4e98-477a-b21e-e41f3df2d15f", "The paper's case study describes this score as chain-of-thought generation."),
    ("codellama", "Llama_2_Chat_7B", "Meta", "TruthfulQA", 57.04, None, 6, True, "e5f8bff6-1002-4ebf-8ca4-332ae1396242", "The paper's case study: scored by a GPT-3 based judge. The record has no field for the judge."),
    ("olmo", "Llama-2-Chat-7B", "Meta", "TruthfulQA", 26.30, None, 0, False, "9831c296-bdf6-4c46-bdd0-9771ed963580", "The paper's case study: scored by a fine-tuned Llama-2-7B judge. The record has no field for the judge."),
    ("reka", "Mistral_7B", "Mistral AI", "Belebele", 32.80, None, 0, False, "351d6ef2-f1be-4750-b72a-fb333bcb2dad", "The paper's case study: an average over 150 language variants. The record has no field for the language scope."),
    ("falcon2", "Mistral-7B", "Mistral AI", "Belebele", 79.42, None, 5, False, "6b60d80a-7b8c-4131-a7a0-986b87837e65", "The paper's case study: English only. The record has no field for the language scope."),
    ("falcon2", "Mistral-7B", "Mistral AI", "Belebele", 32.48, None, 0, False, None, "The paper's case study: English only, the same report's zero-shot score."),
    ("phi3", "Gemma-7B", "Google", "HellaSwag", 49.80, "accuracy", 5, False, "7407b6ae-a6bd-4fc4-a31e-96bfca859ab6", None),
    ("recurrentgemma", "Gemma-7B", "Google", "HellaSwag", 81.20, "acc_norm", 0, True, "52a8f508-6950-4946-9647-c52ced5c3774", "The value of the Gemma report's own zero-shot evaluation (arXiv:2403.08295), as quoted in this paper."),
    ("sealion", "Gemma-2-9B", "Google", "BBH", 34.10, None, None, False, "937f8a74-e28d-4657-ac41-cbf676f12a7f", "The paper states that its English results come from the Open LLM Leaderboard."),
    ("gemma2", "Gemma-2-9B", "Google", "BBH", 68.20, None, None, True, None, "The paper's case study describes this score as 3-shot chain-of-thought generation."),
    ("gemma3", "Gemma-2-9B", "Google", "BBH", 69.00, None, None, True, None, "The paper's case study describes this score as 0-shot chain-of-thought generation."),
    ("gemma3", "Gemma-2-9B", "Google", "BBH", 69.40, None, None, True, None, "The paper's case study describes this score as chain-of-thought generation."),
]


def papers():
    for key, model, developer, bench, score, metric, shots, own, name, note in PAPER_ROWS:
        folder, title, arxiv = PAPERS[key]
        details = {"source": "arxiv_html_llm", **({"note": note} if note else {})}
        doc = document(f"arxiv_html_llm/{model}/{arxiv}/{bench}/{'x' if shots is None else shots}_{score}",
                       ("arxiv_html_llm", "arXiv", "https://arxiv.org"), (model, model.replace("_", " "), developer), ("unknown", "unknown"),
                       [result(bench, score, metric=metric, shots=shots, details=details)],
                       "Section 5 and Appendices G and H of the paper", "LLM-extracted",
                       extra={"paper_url": f"https://arxiv.org/abs/{arxiv}", "arxiv_id": arxiv, "paper_title": title,
                              "extraction_approach": "llm", "extractor_model": "anthropic/claude-haiku-4.5"},
                       relationship="first_party" if own else "third_party")
        doc["evaluation_results"][0]["source_data"] = {"dataset_name": bench, "source_type": "url", "url": [f"https://arxiv.org/abs/{arxiv}"]}
        write(f"archiv_paper_extraction/llm/{folder}/{model}/{bench}", doc, name or uid(f"{key}/{model}/{bench}/{score}"))


# ------------------------------------------------------------------ author-reported: the paper's own controlled runs

RUNS = ("LLM Evaluation Discrepancies: controlled runs", "University of Zurich", CODE)
HARNESS = ("lm-evaluation-harness", "0.4.11")
TULU_GRID = [   # experiments/controlled_eval/collision_model_results.jsonl: benchmark, task, prompt format, shots, scoring mode, score
    ("gpqa_main", "gpqa_main_zeroshot", "plain", 0, "log-likelihood", 31.0), ("gpqa_main", "gpqa_main_n_shot", "plain", 5, "log-likelihood", 23.5),
    ("gpqa_main", "gpqa_main_zeroshot", "instruct", 0, "log-likelihood", 30.5), ("gpqa_main", "gpqa_main_n_shot", "instruct", 5, "log-likelihood", 33.0),
    ("gpqa_main", "gpqa_main_zeroshot", "cot", 0, "log-likelihood", 25.0), ("gpqa_main", "gpqa_main_n_shot", "cot", 5, "log-likelihood", 30.0),
    ("gsm8k", "gsm8k", "plain", 0, "generation", 0.5), ("gsm8k", "gsm8k", "plain", 5, "generation", 82.0),
    ("gsm8k", "gsm8k", "instruct", 0, "generation", 0.0), ("gsm8k", "gsm8k", "instruct", 5, "generation", 86.5),
    ("gsm8k", "gsm8k", "cot", 0, "generation", 0.0), ("gsm8k", "gsm8k", "cot", 5, "generation", 83.0),
    ("bbh", "bbh", "plain", 0, "generation", 25.0424), ("bbh", "bbh", "plain", 3, "generation", 53.5492),
    ("bbh", "bbh", "instruct", 0, "generation", 17.492), ("bbh", "bbh", "instruct", 3, "generation", 45.7541),
    ("bbh", "bbh", "cot", 0, "generation", 13.4438), ("bbh", "bbh", "cot", 3, "generation", 52.1747),
    ("mmlu", "mmlu", "plain", 0, "log-likelihood", 64.4452), ("mmlu", "mmlu", "plain", 5, "log-likelihood", 66.4598),
    ("mmlu", "mmlu", "instruct", 0, "log-likelihood", 64.5432), ("mmlu", "mmlu", "instruct", 5, "log-likelihood", 66.6776),
    ("mmlu", "mmlu", "cot", 0, "log-likelihood", 63.0295), ("mmlu", "mmlu", "cot", 5, "log-likelihood", 66.2637),
]
E1 = [("plain", 58.5), ("instruct", 57.0), ("cot", 2.5)]      # Qwen2.5-14B-Instruct, GSM8K, 5-shot, temperature 0, 200 problems
E2 = [  # experiments/scoring_mode_eval/scoring_mode_results.jsonl, the full-test-set rows: model, scoring mode, score, timestamp
    ("mistralai/Mistral-7B-Instruct-v0.3", "generation", 61.6365, "2026-04-19T20:53:16.117791+00:00"),
    ("Qwen/Qwen2.5-7B-Instruct", "generation", 74.4267, "2026-04-19T20:55:22.184358+00:00"),
    ("meta-llama/Llama-3.1-8B-Instruct", "generation", 68.1598, "2026-04-19T20:57:37.002562+00:00"),
    ("Qwen/Qwen2.5-14B-Instruct", "generation", 79.7892, "2026-04-20T08:37:00.590464+00:00"),
    ("Qwen/Qwen2.5-14B-Instruct", "log-likelihood", 79.97, "2026-06-30"),
    ("mistralai/Mistral-7B-Instruct-v0.3", "log-likelihood", 61.85, "2026-07-01"),
    ("Qwen/Qwen2.5-7B-Instruct", "log-likelihood", 74.25, "2026-07-01"),
    ("meta-llama/Llama-3.1-8B-Instruct", "log-likelihood", 68.19, "2026-07-01"),
]
E3 = [  # experiments/harness_reeval/version_compare/version_pairs.csv (last row: README of the code repository): model, seed, 0.4.3, 0.4.11
    ("Qwen/Qwen2.5-1.5B-Instruct", 42, 32.8279, 33.0553), ("Qwen/Qwen2.5-1.5B-Instruct", 123, 33.7377, 33.3586),
    ("Qwen/Qwen2.5-7B-Instruct", 42, 75.0569, 75.5118), ("Qwen/Qwen2.5-7B-Instruct", 123, 76.35, 78.32),
]
JUDGES = ["openai/gpt-4o-mini", "google/gemini-3.5-flash", "meta-llama/llama-3.1-70b-instruct", "anthropic/claude-haiku-4.5"]
JUDGED = {  # experiments/judge_sensitivity/judge_sensitivity_report.txt: contestant -> mean rating under each judge
    "google/gemma-3-4b-it": (8.24, 7.96, 8.31, 7.26), "qwen/qwen-2.5-7b-instruct": (7.86, 8.02, 7.96, 6.97),
    "meta-llama/llama-3.1-8b-instruct": (8.04, 7.61, 8.22, 6.87), "mistralai/ministral-8b-2512": (8.44, 7.54, 8.62, 7.51),
    "qwen/qwen-2.5-72b-instruct": (8.32, 8.59, 8.38, 7.74),
}


def run(key, model_id, res, origin, library=HARNESS):
    org, tail = model_id.split("/")
    doc = document(f"evalspec_controlled_runs/{model_id.replace('/', '_')}/{key}", RUNS, (model_id, tail, org), library, [res],
                   origin, "source-reported", kind="evaluation_run")
    write(f"evalspec_controlled_runs/{org}/{tail}", doc, uid(f"run/{model_id}/{key}"))


def controlled_runs():
    for bench, task, fmt, shots, mode, score in TULU_GRID:
        where = "experiments/controlled_eval/collision_model_results.jsonl"
        details = {"scoring_mode": mode, "benchmark_variant": f"{task}, {fmt} prompt, first 200 items", "random_seed": "42",
                   "hardware": "NVIDIA RTX PRO 6000 Blackwell Server Edition", "provenance_url": REPO + "experiments/controlled_eval"}
        run(f"grid/{task}/{fmt}/{shots}", "allenai/Llama-3.1-Tulu-3-8B",
            result(bench, score, shots=shots, details=details, temperature=0.0), where + " in the code repository")
    for fmt, score in E1:
        details = {"scoring_mode": "generation", "benchmark_variant": f"gsm8k, {fmt} prompt, first 200 problems", "random_seed": "[42, 123, 7]",
                   "provenance_url": REPO + "experiments/controlled_eval/5-shot-GSM8K"}
        run(f"e1/{fmt}", "Qwen/Qwen2.5-14B-Instruct", result("gsm8k", score, metric="exact_match", shots=5, details=details, temperature=0.0),
            "Section 4 and Appendix M of the paper (experiment E1)")
    for model_id, mode, score, ts in E2:
        details = {"scoring_mode": mode, "benchmark_variant": "mmlu, plain prompt, full test set (14,042 items)", "random_seed": "42",
                   "provenance_url": REPO + "experiments/scoring_mode_eval"}
        if model_id.startswith("meta-llama") and mode == "log-likelihood":
            details["note"] = "Run on the NousResearch re-upload of the same weights; the meta-llama repository is gated."
        run(f"e2/{mode}", model_id, result("mmlu", score, shots=5, details=details, ts=ts, temperature=0.0),
            "experiments/scoring_mode_eval/scoring_mode_results.jsonl in the code repository (experiment E2)")
    for model_id, seed, old, new in E3:
        for version, score in (("0.4.3", old), ("0.4.11", new)):
            details = {"scoring_mode": "generation", "benchmark_variant": "gsm8k, full test set, hf backend", "random_seed": str(seed),
                       "provenance_url": REPO + "experiments/harness_reeval/version_compare"}
            run(f"e3/{version}/{seed}", model_id, result("gsm8k", score, metric="exact_match,strict-match", shots=5, details=details),
                "experiments/harness_reeval/version_compare/version_pairs.csv and the README of the code repository (experiment E3)",
                library=("lm-evaluation-harness", version))
    details = {"scoring_mode": "log-likelihood", "benchmark_variant": "leaderboard_bbh",
               "provenance_url": REPO + "experiments/bbh_protocol/sealion_provenance",
               "note": "A re-run of the leaderboard's configuration on revision beb0c08e. The leaderboard's own value before rescaling is 53.77."}
    run("rerun/leaderboard_bbh", "google/gemma-2-9b", result("bbh", 53.8795, metric="acc_norm", shots=3, details=details),
        "experiments/bbh_protocol/sealion_provenance/olv2_gemma2_9b_bbh.json in the code repository")
    for model_id, ratings in JUDGED.items():
        for judge, rating in zip(JUDGES, ratings):
            details = {"scoring_mode": "preference", "benchmark_variant": "MT-Bench, 80 turn-1 questions, single-answer grading",
                       "judge_score_rule": "rating parsed from the [[rating]] marker of the judge's reply; mean over the rated questions",
                       "provenance_url": REPO + "experiments/judge_sensitivity"}
            run(f"judge/{judge}", model_id, result("mt-bench", rating, lo=1.0, hi=10.0, metric="mean judge rating", shots=0,
                                                   details=details, judges=[judge], temperature=0.0),
                "experiments/judge_sensitivity/judge_sensitivity_report.txt in the code repository",
                library=("run_judge_sensitivity.py", "unknown"))


def main():
    shutil.rmtree(OUT / "data", ignore_errors=True)
    leaderboards()
    papers()
    controlled_runs()
    files = sorted((OUT / "data").rglob("*.json"))
    results = sum(len(json.loads(p.read_text(encoding="utf-8"))["evaluation_results"]) for p in files)
    (OUT / "snapshot.json").write_text(json.dumps({
        "name": "EvalSpec datastore, bundled sample",
        "kind": "sample",
        "assembled": "2026-11-17",
        "files": len(files), "records": results,
        "description": "The records that the paper and its code repository quote in full: the case studies of Section 5, "
                       "the cross-source pairs shipped with the repository, and the authors' own controlled runs. "
                       "The full corpus of the paper has 46,559 records and lives in the Hugging Face datastore.",
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(files)} files, {results} records, into {OUT / 'data'}")


if __name__ == "__main__":
    main()
