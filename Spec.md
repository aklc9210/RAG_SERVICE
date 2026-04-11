# Spec: IR Evaluation for Vietnamese Food Domain (RAG + Ontology)

## 1. Mục tiêu

Chứng minh rằng **ontology** cải thiện chất lượng output so với RAG thuần túy trên 3 tasks:

| Task | Input | Output | Ontology contribution |
|---|---|---|---|
| **Task 1** | Query tên/category món | Ranked dish list | Reranking bằng Dish Relatedness |
| **Task 2** | Tên món + core ingredients | Top-5 flavor-enhancing ingredients | NPMI ranking + category prior |
| **Task 3** | Tên món | Top-5 related dishes | IDF-weighted Jaccard + same_category |

---

## 2. Dataset

- **10,741 món ăn**, split 80/20 (seed=42): 8,593 train / 2,148 test
- Split files: `data/splits/train_ids.txt`, `data/splits/test_ids.txt`
- Pinecone index `vn-food-rag`: đã ingest toàn bộ 10,741 món
- Embedding: `intfloat/multilingual-e5-large`
- LLM: Ollama (default `qwen2.5:7b`)

---

## 3. Ontology

| Component | Nguồn | Trạng thái |
|---|---|---|
| Dish → Ingredients | `processed/dishes/*.json` (có `main/secondary/seasonings`) | ✅ |
| NPMI co-occurrence | `app/data/cooccurrence/npmi.json` | ✅ |
| IDF weights | Tính từ `frequency.json`: `log(N/df(i))` | ✅ |
| Ingredient category | `ingredient_knowledge_base.json` — 20 categories | ✅ |
| Region | Không có trong dataset | ❌ bỏ qua |

### Công thức

**NPMI** (thay PMI chuẩn — loại bỏ frequency bias):
```
NPMI(x,y) = PMI(x,y) / -log2(P(x,y))    range [-1, 1]
```

**Dish Relatedness** (Task 3):
```
Relatedness(A,B) = 0.7 × IDF-Jaccard(A,B) + 0.3 × same_category(A,B)

IDF-Jaccard(A,B) = Σ_{i∈A∩B} idf(i)  /  Σ_{i∈A∪B} idf(i)
idf(i) = log(N / df(i))
```

**Flavor-enhancing score** (Task 2):
```
score(cand) = mean_NPMI(cand, core_ingredients)
            × 1.15  if category(cand) == "seasonings"
```

---

## 4. Evaluation Design

### 4.1 Task 1 — Dish Retrieval ✅ DONE

**Ground truth:** `evaluation/data/datasets/task1_queries.jsonl` — 675 queries, relevance 0/1/2

**Metrics:** nDCG@10, MRR@10, Recall@10

| System | Mô tả |
|---|---|
| BM25 | Keyword search trên tên món |
| RAG-only | Pinecone cosine similarity |
| RAG+Ontology | RAG → rerank bằng Dish Relatedness |

**Kết quả** (`evaluation/outputs/ir_task1_results.json`):

| System | nDCG@10 | MRR@10 | Recall@10 |
|---|---|---|---|
| BM25 | 0.3614 | 0.8074 | 0.0179 |
| RAG-only | **0.4359** | **0.8227** | **0.0238** |
| RAG+Ontology | 0.4083 | 0.6828 | 0.0238 |

---

### 4.2 Task 2 — Flavor-enhancing Ingredients ⏳ BLOCKED

**Ground truth:** `evaluation/data/datasets/task2_flavor_gt.jsonl` — 2,092 dishes

> ⚠️ **Circular evaluation:** GT build bằng NPMI, RAG+Ontology cũng dùng NPMI.
> P@5/F1@5 chỉ có ý nghĩa sau khi có **annotation GT độc lập** (50 dishes, 2 annotators).
> **Avg NPMI là metric hợp lệ ngay bây giờ** — không phụ thuộc annotation.

**Metrics:** Precision@5, F1@5, Avg NPMI

| System | Mô tả |
|---|---|
| BM25 | Non-core ingredients từ chính món (listing, lower bound) |
| RAG+LLM (qwen2.5:7b) | Retrieve similar dishes → LLM suggest ingredients |
| RAG+LLM (llama3.1:8b) | Như trên, model khác |
| RAG+Ontology | Non-core ingredients ranked by NPMI + category prior |

**Script:** `python scripts/run_task2_rag_llm.py --models qwen2.5:7b llama3.1:8b`

---

### 4.3 Task 3 — Related Dishes ⏳ READY TO RUN

**Ground truth:** `evaluation/data/datasets/task3_related_gt.jsonl` — 2,148 dishes

> ⚠️ **Circular evaluation:** GT build bằng Jaccard+Category, RAG+Ontology cũng dùng Jaccard+Category.
> Tuy nhiên RAG-only (cosine sim) là baseline **độc lập** nên so sánh vẫn có giá trị.

**Metrics:** Precision@5, Recall@5

| System | Mô tả |
|---|---|
| BM25 | BM25 search bằng tên món |
| RAG-only | Pinecone cosine similarity, loại self |
| RAG+Ontology | IDF-weighted Jaccard + same_category |

**Script:** `python scripts/run_evaluation.py --tasks 3`

---

## 5. Scripts

| Script | Công dụng |
|---|---|
| `scripts/run_evaluation.py --tasks 1 2 3` | Chạy Task 1/2/3 (BM25, RAG, RAG+Ont) |
| `scripts/run_task2_rag_llm.py --models ...` | RAG+LLM baseline cho Task 2, multi-model |
| `scripts/build_pmi.py` | Build PMI + NPMI từ co-occurrence matrix |
| `scripts/build_task1_gt.py` | Build GT Task 1 |
| `scripts/build_task2_gt.py` | Build GT Task 2 (NPMI-based) |
| `scripts/build_task3_gt.py` | Build GT Task 3 (IDF-Jaccard-based) |
| `scripts/export_annotation_template.py` | Export CSV annotation cho 50 dishes |

---

## 6. Trạng thái

| Hạng mục | Status |
|---|---|
| Task 1: full evaluation | ✅ Done |
| NPMI + IDF-Jaccard + category prior | ✅ Done |
| Task 3: RAG-only baseline | ⏳ Cần chạy |
| Task 2: RAG+LLM baseline (multi-model) | ⏳ Cần chạy |
| Task 2: annotation GT độc lập | ⏳ Đang chờ (50 dishes × 2 annotators) |
| Paper writing | ❌ Chưa bắt đầu |

---

## 7. Expected narrative

- **Task 1:** RAG > BM25 (+20% nDCG). Ontology reranking không cải thiện Task 1 (trade-off MRR).
- **Task 2:** NPMI+prior > RAG+LLM về Avg NPMI → ontology nắm bắt flavor pairing tốt hơn LLM reasoning. Kết quả nhất quán trên nhiều models.
- **Task 3:** RAG+Ontology (IDF-Jaccard) >> RAG-only (cosine) >> BM25 → ingredient-based similarity tốt hơn semantic similarity cho related dish suggestion.
