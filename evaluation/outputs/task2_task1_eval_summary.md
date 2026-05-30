# Evaluation Summary

## Task 2 (Related-Dish) Final Eval on Human GT

Source files:
- evaluation/outputs/task2_human_eval_results_k5.json
- evaluation/outputs/task2_human_eval_results_k10.json
- evaluation/outputs/task2_human_eval_results_k20.json

### K=5

======================================================================
Config                       P@20         NDCG@20      MRR@20      
----------------------------------------------------------------------
A: Jaccard only              0.6352±0.047  0.8811±0.027  0.8610±0.037
B: +ClassOverlap             0.6352±0.047  0.9075±0.020  0.9083±0.024
C: +MethodMatch              0.6352±0.047  0.9250±0.023  0.9439±0.032
D: +SemanticSim              0.6352±0.047  0.9261±0.022  0.9490±0.029
E: Full (all 5)              0.6352±0.047  0.9260±0.021  0.9385±0.028
F: No Jaccard                0.6352±0.047  0.9205±0.018  0.9229±0.023
G: No ClassOverlap           0.6352±0.047  0.9144±0.022  0.9141±0.029
H: No MethodMatch            0.6352±0.047  0.9056±0.020  0.9052±0.034
I: No SemanticSim            0.6352±0.047  0.9259±0.021  0.9373±0.029
J: No Flavor                 0.6352±0.047  0.9261±0.022  0.9490±0.029

Weights: alpha=0.3379249828392578, beta=0.16612468401453886, gamma=0.1234424284733664, delta=0.18999771812939792, epsilon=0.18251018654343898

| System | P@5 | NDCG@5 | MRR@5 |
| --- | --- | --- | --- |
| BM25 | 0.456 | 0.6455 | 0.82 |
| BM25+Expansion | 0.392 | 0.5428 | 0.688 |
| Dense | 0.392 | 0.543 | 0.7193 |
| Dense+Ontology | 0.432 | 0.5541 | 0.6767 |

### K=10

======================================================================
Config                       P@10         NDCG@10      MRR@10      
----------------------------------------------------------------------
A: Jaccard only              0.7150±0.046  0.7528±0.040  0.8594±0.039
B: +ClassOverlap             0.7425±0.044  0.7992±0.030  0.9080±0.024
C: +MethodMatch              0.7740±0.046  0.8359±0.033  0.9435±0.032
D: +SemanticSim              0.7735±0.046  0.8367±0.032  0.9485±0.029
E: Full (all 5)              0.7835±0.047  0.8441±0.032  0.9385±0.028
F: No Jaccard                0.7720±0.049  0.8307±0.032  0.9229±0.023
G: No ClassOverlap           0.7655±0.048  0.8218±0.035  0.9141±0.029
H: No MethodMatch            0.7465±0.048  0.7996±0.033  0.9049±0.034
I: No SemanticSim            0.7830±0.048  0.8436±0.034  0.9373±0.029
J: No Flavor                 0.7735±0.046  0.8367±0.032  0.9485±0.029

Weights: alpha=0.3379249828392578, beta=0.16612468401453886, gamma=0.1234424284733664, delta=0.18999771812939792, epsilon=0.18251018654343898

| System | P@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- |
| BM25 | 0.292 | 0.6916 | 0.825 |
| BM25+Expansion | 0.244 | 0.5772 | 0.693 |
| Dense | 0.308 | 0.6463 | 0.731 |
| Dense+Ontology | 0.32 | 0.6543 | 0.6868 |

### K=20

======================================================================
Config                       P@20         NDCG@20      MRR@20      
----------------------------------------------------------------------
A: Jaccard only              0.6352±0.047  0.8811±0.027  0.8610±0.037
B: +ClassOverlap             0.6352±0.047  0.9075±0.020  0.9083±0.024
C: +MethodMatch              0.6352±0.047  0.9250±0.023  0.9439±0.032
D: +SemanticSim              0.6352±0.047  0.9261±0.022  0.9490±0.029
E: Full (all 5)              0.6352±0.047  0.9260±0.021  0.9385±0.028
F: No Jaccard                0.6352±0.047  0.9205±0.018  0.9229±0.023
G: No ClassOverlap           0.6352±0.047  0.9144±0.022  0.9141±0.029
H: No MethodMatch            0.6352±0.047  0.9056±0.020  0.9052±0.034
I: No SemanticSim            0.6352±0.047  0.9259±0.021  0.9373±0.029
J: No Flavor                 0.6352±0.047  0.9261±0.022  0.9490±0.029

Weights: alpha=0.3932031384729294, beta=0.17798045688987107, gamma=0.11236717412900402, delta=0.3164492305081954, epsilon=0.0

| System | P@20 | NDCG@20 | MRR@20 |
| --- | --- | --- | --- |
| BM25 | 0.188 | 0.781 | 0.8306 |
| BM25+Expansion | 0.188 | 0.6977 | 0.6957 |
| Dense | 0.188 | 0.7146 | 0.7331 |
| Dense+Ontology | 0.188 | 0.7229 | 0.7278 |

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
