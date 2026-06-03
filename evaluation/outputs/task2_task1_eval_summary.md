# Evaluation Summary

## Task 2 (Related-Dish) Final Eval on LLM-Judge GT

Ground truth: `llm_mean_score` from `evaluation/annotation/task2_human_annotation_v2.csv`
(human annotation columns disabled; LLM-judge mean used as sole ground truth)

Source files:
- evaluation/outputs/task2_llm_eval_results_k5.json
- evaluation/outputs/task2_llm_eval_results_k10.json
- evaluation/outputs/task2_llm_eval_results_k20.json

### K=5

Weights: alpha=0.3379, beta=0.1661, gamma=0.1234, delta=0.1900, epsilon=0.1825

**Ablation (LLM-tuned, 5-fold CV on 200 anchors / 3997 pairs)**

| Config | P@5 | NDCG@5 | MRR@5 |
| --- | --- | --- | --- |
| A: Jaccard only | 0.741±0.061 | 0.755±0.053 | 0.855±0.042 |
| B: +ClassOverlap | 0.796±0.051 | 0.816±0.038 | 0.905±0.028 |
| C: +MethodMatch | 0.819±0.054 | 0.844±0.044 | 0.944±0.032 |
| D: +SemanticSim | 0.819±0.054 | 0.845±0.043 | 0.948±0.029 |
| E: Full (all 5) | **0.825±0.047** | **0.849±0.040** | 0.937±0.029 |
| F: No Jaccard | 0.815±0.041 | 0.835±0.033 | 0.923±0.023 |
| G: No ClassOverlap | 0.812±0.043 | 0.830±0.038 | 0.913±0.028 |
| H: No MethodMatch | 0.794±0.045 | 0.811±0.036 | 0.903±0.036 |
| I: No SemanticSim | **0.825±0.047** | 0.848±0.040 | 0.936±0.030 |
| J: No Flavor | 0.819±0.054 | 0.845±0.043 | **0.948±0.029** |

**System comparison (LLM GT, 25 anchors / 500 pairs)**

| System | P@5 | NDCG@5 | MRR@5 |
| --- | --- | --- | --- |
| BM25 | 0.792 | 0.827 | 0.920 |
| BM25+Expansion | 0.744 | 0.783 | 0.920 |
| Dense | 0.848 | 0.863 | 0.913 |
| **Dense+Ontology** | **0.872** | **0.901** | **0.980** |

### K=10

Weights: alpha=0.3379, beta=0.1661, gamma=0.1234, delta=0.1900, epsilon=0.1825

**System comparison (LLM GT, 25 anchors / 500 pairs)**

| System | P@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- |
| BM25 | 0.696 | 0.764 | 0.924 |
| BM25+Expansion | 0.660 | 0.724 | 0.924 |
| Dense | 0.756 | 0.823 | 0.920 |
| **Dense+Ontology** | **0.788** | **0.877** | **0.980** |

### K=20

Weights: alpha=0.3932, beta=0.1780, gamma=0.1124, delta=0.3164, epsilon=0.0

**System comparison (LLM GT, 25 anchors / 500 pairs)**

| System | P@20 | NDCG@20 | MRR@20 |
| --- | --- | --- | --- |
| BM25 | 0.608 | 0.903 | 0.928 |
| BM25+Expansion | 0.608 | 0.887 | 0.928 |
| Dense | 0.608 | 0.919 | 0.920 |
| **Dense+Ontology** | **0.608** | **0.950** | **1.000** |

## Task 1 (Query Expansion) Final Eval

Existing results in evaluation/outputs:
- evaluation/outputs/ir_task1_ontology_results.json (P@20, NDCG@20, MRR@20)
- evaluation/outputs/ir_task1_ontology_results_k5.json (P@5, NDCG@5, MRR@5)
- evaluation/outputs/ir_task1_ontology_results_k10.json (P@10, NDCG@10, MRR@10)
- evaluation/outputs/ir_task1_results.json (nDCG@10, MRR@10, Recall@10; no P@10)

### P@20, NDCG@20, MRR@20

| System | P@20 | NDCG@20 | MRR@20 | n_queries |
| --- | --- | --- | --- | --- |
| BM25 | 0.227 | 0.2302 | 0.39 | 1000 |
| BM25+Expansion | 0.2865 | 0.2879 | 0.413 | 1000 |
| RAG-only | 0.3488 | 0.3549 | 0.514 | 1000 |
| RAG+Ontology | 0.4694 | 0.4997 | 0.7301 | 1000 |

### P@5, NDCG@5, MRR@5

| System | P@5 | NDCG@5 | MRR@5 | n_queries |
| --- | --- | --- | --- | --- |
| BM25 | 0.2238 | 0.2333 | 0.3618 | 1000 |
| BM25+Expansion | 0.288 | 0.2875 | 0.3926 | 1000 |
| RAG-only | 0.3658 | 0.366 | 0.4948 | 1000 |
| RAG+Ontology | 0.534 | 0.5492 | 0.6955 | 1000 |

### P@10, NDCG@10, MRR@10

| System | P@10 | NDCG@10 | MRR@10 | n_queries |
| --- | --- | --- | --- | --- |
| BM25 | 0.218 | 0.2261 | 0.3807 | 1000 |
| BM25+Expansion | 0.2896 | 0.2891 | 0.4081 | 1000 |
| RAG-only | 0.3591 | 0.3618 | 0.5084 | 1000 |
| RAG+Ontology | 0.4991 | 0.5243 | 0.7172 | 1000 |

### NDCG@10, MRR@10, Recall@10 (no P@10 in this output)

| System | NDCG@10 | MRR@10 | Recall@10 | n_queries |
| --- | --- | --- | --- | --- |
| BM25 | 0.2472 | 0.4878 | 0.0581 | 530 |
| RAG-only | 0.2932 | 0.477 | 0.0588 | 530 |
| RAG+Ontology | 0.2805 | 0.4115 | 0.0588 | 530 |

## Note

- evaluation/outputs/ir_task1_results.json still does not include P@10, so use the k10 ontology results above for P@10.
