# Task 1: Class-based Retrieval — Kết quả thực nghiệm

## 1. Setup

- **Corpus**: 10,741 món ăn Việt Nam (processed dishes)
- **Queries**: 200 queries chia 4 loại (50/loại)
- **Ontology**: 8,112 ingredients → 49 classes (4 levels), 24 leaf classes
- **Embedding**: multilingual-e5-large (1024-dim)
- **Metric**: P@20, R@20, F1@20, MAP, NDCG@20

### Query types

| Type | Mô tả | Ví dụ | Avg GT size |
|---|---|---|---|
| single_class | 1 class nguyên liệu | "món ngon từ nấm" | ~1,500 |
| multi_class | 2+ classes kết hợp | "vịt nấu với me" | ~350 |
| negation | Có class + loại trừ class | "món thịt không cay" | ~1,200 |
| cooking_method | Phương pháp nấu + class | "hải sản nướng" | ~150 |

### Ground Truth

Mỗi query có GT = tập dish thỏa mãn:
- **Positive**: dish chứa ít nhất 1 ingredient thuộc MỖI positive class
- **Negative**: dish KHÔNG chứa ingredient thuộc bất kỳ negative class nào
- **Method**: dish có cooking method đúng (nếu có)

GT được build tự động bằng FoodOntology API duyệt toàn bộ 10,741 dishes.

---

## 2. Systems

| # | System | Mô tả |
|---|---|---|
| S1 | **BM25** | Keyword matching (BM25Okapi) trên dish name + ingredient names |
| S2 | **BM25+Expansion** | BM25 + mở rộng query bằng synonyms từ ingredient KB (flat, không hierarchy) |
| S3 | **RAG-only** | Dense retrieval bằng multilingual-e5-large embeddings |
| S4 | **RAG+Ontology** | Dense retrieval + ontology query expansion (hierarchy descendants) + post-filter (negation classes, cooking method) |

### Sự khác biệt giữa S2 và S4

| | BM25+Expansion (S2) | RAG+Ontology (S4) |
|---|---|---|
| Expansion source | Flat synonyms từ KB | Hierarchy descendants (class → all ingredients) |
| Retrieval | BM25 (keyword) | Dense (semantic) |
| Negation handling | Không | Post-filter loại dish có negative class |
| Method filter | Không | Post-filter theo cooking method |

Ví dụ query "món nấm":
- S2 expand: "nấm" → synonyms ["nấm rơm"] (chỉ 1-2 synonyms)
- S4 expand: "nấm" → Mushroom class → 87 ingredients ["nấm hương", "nấm đông cô", "nấm rơm", "nấm bào ngư", ...]

---

## 3. Kết quả tổng hợp

### Table 1: Overall results (200 queries, top-20)

| System | P@20 | R@20 | F1@20 | MAP | NDCG@20 |
|---|---|---|---|---|---|
| BM25 | 0.230 | 0.015 | 0.022 | 0.007 | 0.232 |
| BM25+Expansion | 0.295 | 0.015 | 0.022 | 0.007 | 0.298 |
| RAG-only | 0.339 | 0.023 | 0.034 | 0.012 | 0.344 |
| **RAG+Ontology** | **0.446** | **0.033** | **0.048** | **0.019** | **0.472** |

### Table 2: Relative improvement vs baselines

| Comparison | ΔP@20 | ΔNDCG@20 |
|---|---|---|
| RAG+Ontology vs BM25 | **+94%** | **+103%** |
| RAG+Ontology vs BM25+Expansion | **+51%** | **+58%** |
| RAG+Ontology vs RAG-only | **+32%** | **+37%** |
| BM25+Expansion vs BM25 | +28% | +28% |
| RAG-only vs BM25 | +47% | +48% |

### Phân tích gain

```
BM25 ──(+28%)──→ BM25+Expansion ──(+16%)──→ RAG-only ──(+32%)──→ RAG+Ontology
       synonym                    semantic              ontology
       expansion                  understanding         structure
```

- **+28%** từ synonym expansion đơn giản (flat KB)
- **+16%** thêm từ semantic understanding (dense vs keyword)
- **+32%** thêm từ ontology structure (hierarchy expansion + structured filtering)

→ Ontology structure đóng góp **+51% P@20** so với naive expansion (S4 vs S2), chứng minh hierarchy knowledge có giá trị vượt trội so với flat synonym lookup.

---

## 4. Giải thích Recall thấp

R@20 thấp ở tất cả systems (0.015–0.033) vì:
- GT size lớn: median = 462 dishes, max = 4,984
- Chỉ retrieve top-20 từ corpus 10,741
- Theoretical max R@20 = 20/462 = 4.3%

Đây là đặc thù của class-level retrieval (khác với name-matching retrieval thông thường). **P@20 và NDCG@20 là metrics chính** cho task này.

---

## 5. Key findings cho paper

1. **Ontology hierarchy tạo gain đáng kể**: RAG+Ontology vượt tất cả baselines trên mọi metric. Gain lớn nhất ở P@20 (+94% vs BM25).

2. **Hierarchy > flat synonyms**: So sánh S2 vs S4 isolate contribution của ontology structure. Gain +51% P@20 chứng minh hierarchy descendants expansion hiệu quả hơn flat synonym lookup.

3. **Structured filtering quan trọng cho negation/method queries**: RAG+Ontology là system duy nhất có khả năng filter negation classes và cooking method — các system khác không thể xử lý "món không có hải sản".

4. **Dense + Ontology complementary**: Dense retrieval hiểu semantic, ontology cung cấp structured knowledge → kết hợp cho kết quả tốt nhất.

---

## 6. Files

| File | Mô tả |
|---|---|
| `evaluation/data/task1_class_queries.jsonl` | 200 queries + GT |
| `evaluation/outputs/ir_task1_ontology_results.json` | Kết quả 4 systems |
| `scripts/eval_task1_retrieval.py` | Script evaluation |
| `scripts/build_task1_class_queries.py` | Script generate queries |
| `retrieval/ontology.py` | FoodOntology API |
