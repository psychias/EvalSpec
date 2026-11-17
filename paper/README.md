# Paper sources

| Path | What it is |
|---|---|
| `latex/` | LaTeX sources (`acl_latex.tex`), bibliography and ACL style files |
| `figures/` | Figures as PDF and PNG |
| `figures/scripts/` | The scripts that draw them |
| `LLM_Evaluation_Report-6.pdf` | The draft these sources build |
| `notes/` | Revision logs and the ACL formatting instructions |

These sources are an earlier draft than the accepted paper, "LLM Evaluation
Discrepancies And How To Prevent Them" (Findings of EACL 2027). Title, section
numbering and some figures differ. The numbers in the repository's README and in
`experiments/README.md` follow the accepted paper.

Regenerating the figures:

```bash
python paper/figures/scripts/coverage_bars.py   # metadata coverage bars
python paper/figures/scripts/unified.py         # case-study panels
python paper/figures/scripts/case1.py           # GSM8K answer-parser flow
```
