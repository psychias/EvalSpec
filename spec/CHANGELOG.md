# EvalSpec versions

A released version does not change. A revision gets a new number, a new entry here
and its own schema file (`evalspec-<version>.schema.json`).

## 1.0

The field set of Table 2 and Appendix J of "LLM Evaluation Discrepancies And How To
Prevent Them" (Findings of EACL 2027): 13 Required, 5 Recommended and 3 Full fields,
four scoring modes and five provenance tags. EvalSpec 1.0 is a conformance profile
over Every Eval Ever (EEE) 0.2.1 with the eight additional fields used in the paper.

The paper defines the fields. To check a record by machine, this version also fixes
the following. Each point is a reading of the paper, not a change to it.

- **Names.** The benchmark is named in `benchmark_id` and the run time in
  `evaluation_timestamp`. The released hook writes `benchmark`, and the worked
  example in the paper's appendix writes `eval_timestamp`; the tools accept
  `benchmark` and report it.
- **Hashes.** `sha256:` followed by all 64 hexadecimal digits.
- **Missing values.** The literal `unknown`, an empty text and `null` mean "not on
  record". For `judge_model`, `null` states that no judge was involved, and it is
  implied when `scoring_mode` is `log-likelihood`, `generation` or `execution`.
- **Conditional fields.** `answer_parser_version` applies when `scoring_mode` is
  `generation`. `judge_prompt_hash` and `judge_score_rule` apply when `scoring_mode`
  is `preference` or `judge_model` names a scorer.
- **Score and scale.** The score is not one of the 21 fields. A flat record states its
  range in `min_score` and `max_score`, as EEE requires for a continuous score.
- **Provenance.** One tag per record in `evidence_source`, with per-field overrides.
  A record whose tag is `source-reported` is listed as author-reported; any other
  record is listed as predicted.
- **EEE paths.** The paper fixes the path of `judge_model` and states that
  `scoring_mode` has none. The other paths in `fields.json` are this version's
  reading. Fields without an EEE slot are written as text in
  `evaluation_results[].generation_config.additional_details`.
- **Other keys of a flat record.** `fields.json` lists them under `record_keys`
  (score, metric, source, extractor and so on), each with its EEE path.

### Open questions

- Whether the EEE paths chosen here are the ones the EEE maintainers would choose.
- A dedicated field for "raw or rescaled". Today this is free text in
  `metric_config.evaluation_description`, with the measured value in
  `score_details.details.raw_score`.
- The canonical form of the text that `prompt_template_hash` covers. The released
  hook hashes the task template only; the field is defined over the task template,
  the system instruction and the chat template together.
- Restating the profile over a later EEE version.
