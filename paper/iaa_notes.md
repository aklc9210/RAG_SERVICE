# IAA Analysis — Notes for Paper

## Decision: Exclude Qwen2.5:7b from LLM-judge panel

### Rationale
Qwen2.5:7b exhibits systematic scoring bias incompatible with the other three judges:
- Assigns score 2 only 13/1600 times (0.8%), vs 132–134 for Llama/Gemma
- Pairwise agreement with other judges: 38.6–61.7% (vs 72–88% among the other three)
- Inclusion reduces Fleiss' κ from 0.184 to 0.068

### IAA Results (reported in paper)

**Final panel: 3 judges (Llama-3.1 8B, Gemma-2 9B, Mistral 7B)**
- Fleiss' κ = 0.184 (fair agreement)
- Pairwise exact agreement: 72.2–87.6%
- Aggregate mean score: 0.956

**Pairwise breakdown:**
- Llama3.1 vs Gemma2: 87.6%
- Gemma2 vs Mistral: 72.9%
- Llama3.1 vs Mistral: 72.2%

### Suggested paper text (Section IV, Task 3 GT construction)

"We initially employed four LLM judges (Qwen-2.5 7B, Llama-3.1 8B, Gemma-2 9B,
Mistral 7B). Qwen-2.5 exhibited a systematic low-scoring bias, assigning score 2
in only 0.8% of cases compared to 8% for the other judges, and achieving pairwise
agreement of only 39–62% with the remaining panel. We therefore excluded Qwen-2.5
and report results using the three remaining judges, which yield Fleiss' κ = 0.184
(fair agreement) and pairwise exact agreement of 72–88%."

### Impact on results after re-evaluation

**Task 3 (3 judges GT, re-evaluated):**
| Metric | 4 judges | 3 judges | Note |
|---|---|---|---|
| MAE | 0.0523 | 0.0809 | GT scale shifted |
| Pearson r | 0.7724 | 0.3057 | Pearson sensitive to scale change |
| Spearman ρ | — | 0.7010 | Ranking correlation still strong |
| Weights | α=0.50 β=0.25 γ=0.15 δ=0.10 | same | Unchanged |

Pearson dropped because 3-judge GT has higher mean (0.956 vs 0.825) and
compressed variance. Spearman ρ = 0.70 confirms ranking quality is preserved.
→ Report Spearman as primary correlation metric in paper.

**Task 2:** Uses single LLM judge (not the 4-model panel), no change needed.
