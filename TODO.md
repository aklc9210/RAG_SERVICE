# TODO — RAG Service IR Evaluation

## Blocking (cần làm trước khi publish)

- [ ] **Manual annotation — Task 2**
  - Hai người annotation độc lập, điền `evaluation/annotation/annotation_template.csv` (410 judgements, ~30–45 phút/người)
  - Sau đó: tính Cohen's Kappa (cần ≥ 0.6), build independent Task 2 GT, re-evaluate PMI system
  - Script annotation guide: `evaluation/annotation/README_annotation.md`

- [ ] **Task 2: RAG-only baseline**
  - Lấy ingredient list từ Pinecone document (không dùng PMI), so sánh với PMI ranking
  - Mục tiêu: chứng minh PMI tốt hơn naive document listing

- [ ] **Task 3: RAG-only baseline**
  - Dùng cosine similarity giữa dish embeddings trong Pinecone để tìm related dishes
  - So sánh với Dish Relatedness (Jaccard + Category)
  - Cần: embed tất cả 2,148 test dishes, tính pairwise similarity

## Nice-to-have

- [ ] **Task 1: breakdown by query type**
  - Split kết quả thành exact_name vs category queries
  - Dự kiến: ontology reranking giúp category queries nhưng hurt exact-name queries

- [ ] **Region field**
  - Hiện tại 0/10,741 dishes có `region` metadata
  - Nếu thêm được → enable γ term trong Dish Relatedness + region-based Task 1 queries

## Done

- [x] Build PMI from co-occurrence matrix (`scripts/build_pmi.py`)
- [x] Train/test split 80/20 seed=42 (`scripts/build_split.py`)
- [x] Task 1 ground truth: 675 queries (`scripts/build_task1_gt.py`)
- [x] Task 2 ground truth: PMI-based flavor GT (`scripts/build_task2_gt.py`)
- [x] Task 3 ground truth: Jaccard+Category related dishes (`scripts/build_task3_gt.py`)
- [x] BM25 baseline (`retrieval/bm25_retriever.py`)
- [x] RAG + Ontology retriever (`retrieval/ontology_retriever.py`)
- [x] Live evaluation against Pinecone (`scripts/run_evaluation.py`)
- [x] Annotation template export — blind design (`scripts/export_annotation_template.py`)
- [x] IR evaluation report (`docs/IR_evaluation_report.md`)
- [x] Remove circular evaluation outputs (task2, task3 results)
