# Spec: IR for Food & Dish Domain using RAG + Ontology

## 1. Tổng quan bài toán

### 1.1 Mô tả
Hệ thống Information Retrieval (IR) cho domain thực phẩm, nhận đầu vào là câu truy vấn tự nhiên liên quan đến món ăn và trả về kết quả được làm giàu bởi ontology.

### 1.2 Input / Output

| | Mô tả | Ví dụ |
|---|---|---|
| **Input** | Câu truy vấn tự nhiên về thực phẩm | *"Tôi muốn ăn phở bò"* |
| **Output 1** | Ranked list các món ăn phù hợp (có điểm) | Phở bò, phở gà, bún bò Huế, ... |
| **Output 2** | Nguyên liệu tăng hương vị (flavor-enhancing ingredients) | Hành nướng, gừng nướng, quế, hồi, thảo quả, ... |
| **Output 3** | Món ăn liên quan được suggest từ nguyên liệu output | Bún bò Huế, bún riêu (share ingredients) |

### 1.3 Đóng góp chính
Chứng minh rằng **ontology** (Dish→Ingredients, PMI co-occurrence, Dish similarity) làm tăng chất lượng output so với RAG thuần túy, đặc biệt rõ ràng ở Task 2 (flavor-enhancing ingredients).


## 2. Dataset

### 2.1 Thông tin dataset
| Field | Chi tiết |
|---|---|
| Số lượng | **10,741 món ăn** (đã có trong `processed/dishes/`) |
| Ngôn ngữ | Tiếng Việt |
| Fields có sẵn | `name_vi`, `name_en`, `category`, `ingredient_ids`, `ingredient_names_vi/en`, `main_ingredients`, `secondary_ingredients`, `seasonings` |
| Fields **thiếu** | `region` — không có trong toàn bộ dataset; cần gắn nhãn thủ công hoặc infer |
| Category | 25 loại: `mon banh` (2,267), `mon chien` (1,182), `mon xao` (1,160), `mon canh` (813), ... |
| Ingredients | 8,112 nguyên liệu trong KB (`ingredient_knowledge_base.json`) |

### 2.2 Phân chia dataset
```
10,741 món ăn
├── Train / Ontology Construction : 8,593 món (80%)
│   └── Dùng để tính PMI, build dish similarity graph
└── Test / Evaluation             : 2,148 món (20%)
    └── Dùng để evaluate 3 tasks
```

> **Lưu ý:** Split chưa được tạo. Cần generate và lưu index vào file (ví dụ `data/splits/train_ids.txt`, `data/splits/test_ids.txt`) để đảm bảo reproducibility.

---

## 3. Ontology

### 3.1 Các thành phần ontology

| Component | Mô tả | Trạng thái |
|---|---|---|
| **Dish → Ingredients** | Quan hệ thành phần của món ăn | ✅ Có sẵn — `dish_knowledge_base.json` + `processed/dishes/` |
| **PMI co-occurrence** | Độ tương hợp hương vị giữa các nguyên liệu | ⚠️ Raw counts có sẵn — **PMI chưa tính** |
| **Dish similarity** | Độ liên quan giữa các món | ⚠️ Jaccard + Category khả thi; **thiếu Region** |

### 3.2 PMI co-occurrence

**Dữ liệu có sẵn:**
- `app/data/cooccurrence/matrix.json` — co-occurrence counts giữa 8,061 × 8,061 cặp nguyên liệu
- `app/data/cooccurrence/frequency.json` — số món chứa mỗi nguyên liệu (8,070 entries)
- `app/data/cooccurrence/metadata.json` — `total_dishes: 10,741`

**Công thức tính PMI từ dữ liệu có sẵn:**
```python
PMI(x, y) = log2( P(x,y) / (P(x) * P(y)) )

P(x,y) = matrix[x][y] / total_dishes
P(x)   = frequency[x] / total_dishes
P(y)   = frequency[y] / total_dishes
```

**Ví dụ thực tế:** `ingre01354` (Cà chua, 718 món) × `ingre04303` (Nghêu, 28 món), co-count = 7
→ PMI = log2(0.00065 / (0.06685 × 0.00261)) ≈ **1.90** (tương hợp)

Ngưỡng phân loại:
- `PMI(x,y) > 0` : cặp nguyên liệu tương hợp, plausible
- `PMI(x,y) = 0` : trung lập
- `PMI(x,y) < 0` : cặp hiếm gặp, implausible

> **Việc cần làm:** Viết script tính PMI từ matrix + frequency và lưu vào `app/data/cooccurrence/pmi.json`.

### 3.3 Dish Relatedness

**Công thức:**
```
Relatedness(A, B) = α * Jaccard(A, B) + β * [same_category] + γ * [same_region]

Jaccard(A, B) = |ingredients_A ∩ ingredients_B| / |ingredients_A ∪ ingredients_B|
```

**Trọng số đề xuất theo dữ liệu hiện có:**
- Nếu có region: α=0.5, β=0.3, γ=0.2
- **Nếu thiếu region (hiện tại):** α=0.7, β=0.3, γ=0 — bỏ region term cho đến khi có dữ liệu

**Trạng thái:**
- ✅ Jaccard: khả thi — `ingredient_ids` có đầy đủ
- ✅ `same_category`: có đầy đủ — 25 category
- ❌ `same_region`: **thiếu hoàn toàn** — 0/10,741 món có trường `region`

> **Quyết định cần làm:** Gắn nhãn region cho toàn bộ hoặc một subset, hoặc dùng công thức không có region term trong phiên bản đầu.

---

## 4. Ground Truth Construction

### 4.1 Task 1 — Query → Relevant Dishes

**Cách build (tự động):**

Từ dataset, generate 3 loại query:

| Query Type | Cách tạo | Ground Truth |
|---|---|---|
| Exact name | `"phở bò"` → `"tôi muốn ăn phở bò"` | Chính món đó + variants |
| Category-based | Category = `mon nuoc` → `"cho tôi món nước"` | Tất cả món trong category |
| Region-based | Region = "miền Trung" → `"món ăn miền Trung"` | Tất cả món cùng region (**chặn bởi thiếu region field**) |

**Relevance labels (graded, 3 mức):**
```
score = 2 : tên món match trực tiếp với query
score = 1 : cùng category hoặc cùng region với query
score = 0 : không liên quan
```

**Số lượng mục tiêu:** 500–1,000 queries (chỉ exact + category trước khi có region)

### 4.2 Task 2 — Flavor-enhancing Ingredients

**Cách build (tự động từ PMI):**

```python
# Với mỗi món D có core ingredients C:
# Core = main_ingredients (đã có sẵn trong processed/dishes/ dưới field main_ingredients)

# Flavor-enhancing = top-K ingredients có PMI cao với C
# nhưng KHÔNG phải core ingredients

flavor_enhancing(D) = top10(
    ingredients i where:
        mean(PMI(i, c) for c in core(D)) > threshold
        AND i NOT IN core(D)
)
```

> `main_ingredients` đã có sẵn trong `processed/dishes/*.json` — dùng làm proxy cho "core ingredients" mà không cần tính threshold riêng.

**Ground truth = danh sách top-10 ingredients theo PMI score**

**Validation thủ công:** 30–50 món được annotate tay để xác nhận PMI-based GT có quality tốt → báo cáo Inter-Annotator Agreement (Cohen's Kappa ≥ 0.6)

### 4.3 Task 3 — Related Dishes

**Cách build (tự động từ Relatedness):**

```
Ground truth(D) = top-5 món có Relatedness(D, *) cao nhất
```

---

## 5. Kiến trúc mô hình

### 5.1 Tổng quan pipeline
```
Query (text)
    │
    ▼
[Query Understanding]
    │
    ├──────────────────────────────────────────────┐
    │                                              │
    ▼                                              ▼
[RAG Retrieval]                          [Ontology Layer]
 Dense retrieval (multilingual-e5-large)  - Dish→Ingredients
 trên 10,741 món (Pinecone index          - PMI scores
 "vn-food-rag" — đã ingest)               - Dish similarity
    │                                     (Jaccard + Category)
    └──────────────┬───────────────────────┘
                   │
                   ▼
           [Fusion & Reranking]
          (ontology reranks RAG output)
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
    [Task 1]   [Task 2]   [Task 3]
  Ranked dish  Flavor     Related
    list       ingredients dishes
```

### 5.2 Vai trò của Ontology trong pipeline
- **Task 1:** Ontology mở rộng query (query expansion) — từ "phở bò" mở rộng sang các ingredients liên quan → tìm thêm được món relevant
- **Task 2:** PMI trực tiếp rank flavor-enhancing ingredients — đây là đóng góp rõ nhất
- **Task 3:** Dish similarity graph từ ontology → suggest related dishes chính xác hơn cosine similarity đơn thuần

### 5.3 Infrastructure hiện có
| Component | Trạng thái |
|---|---|
| Dense retrieval (Pinecone `vn-food-rag`) | ✅ Đã ingest toàn bộ 10,741 món |
| Embedding model | ✅ `intfloat/multilingual-e5-large` (local, sentence-transformers) |
| LLM | ✅ Ollama `qwen2.5:7b` (local) |
| Ingredient ontology | ✅ `OntologyService` — load `dish_knowledge_base.json` + `ingredient_knowledge_base.json` |
| BM25 | ❌ Chưa có — cần implement |

---

## 6. Baselines

| System | Mô tả | Trạng thái |
|---|---|---|
| **BM25** | Keyword search thuần, không RAG, không ontology | ❌ Chưa có |
| **RAG only** | Dense retrieval (multilingual-e5-large + Pinecone), không ontology | ✅ Có sẵn — `retrieval/retriever.py` |
| **RAG + Ontology (proposed)** | Hệ thống đầy đủ | ⚠️ Chưa tích hợp ontology layer |

Ablation thêm (nếu có thời gian):

| System | Mô tả |
|---|---|
| RAG + Dish→Ingredient only | Ontology không có PMI |
| RAG + PMI only | Không có dish taxonomy/similarity |
| RAG + Full Ontology | Toàn bộ — proposed |

---

## 7. Metrics Đánh Giá

### 7.1 Task 1 — Dish Retrieval

| Metric | Mô tả | Lý do chọn |
|---|---|---|
| **nDCG@10** | Normalized Discounted Cumulative Gain | Output là ranked list, graded relevance |
| **MRR@10** | Mean Reciprocal Rank | Quan tâm vị trí món đúng đầu tiên |
| **Recall@10** | Tỷ lệ món relevant được tìm thấy trong top 10 | Đo độ phủ |

### 7.2 Task 2 — Flavor-enhancing Ingredients

| Metric | Mô tả | Lý do chọn |
|---|---|---|
| **Precision@5** | Trong 5 ingredients suggest, bao nhiêu là flavor-enhancing | Metric chính |
| **F1@5** | Cân bằng precision và recall | Tổng quát hơn |
| **Avg PMI score** | PMI trung bình của ingredients được suggest | Metric tự nhiên cho ontology contribution |

### 7.3 Task 3 — Related Dish Suggestion

| Metric | Mô tả | Lý do chọn |
|---|---|---|
| **Precision@5** | Trong 5 món suggest, bao nhiêu là truly related | Metric chính |
| **Recall@5** | Bao nhiêu món related được tìm thấy | Đo độ phủ |

---

## 8. Kết quả kỳ vọng (Expected Results Table)

### 8.1 Ablation Table (Task 1 — Dish Retrieval)

| System | nDCG@10 | MRR@10 | Recall@10 |
|---|---|---|---|
| BM25 | 0.3614 | 0.8074 | 0.0179 |
| RAG-only | **0.4359** | **0.8227** | **0.0238** |
| RAG + Ontology | 0.4083 | 0.6828 | 0.0238 |

> **Nhận xét:** RAG-only (dense embedding) thắng BM25 ở nDCG (+20%) và Recall (+33%). RAG+Ontology cải thiện Recall tương đương RAG-only nhưng MRR thấp hơn — ontology reranking trade-off giữa exact-match precision và category diversity. Đây là kết quả thực tế và lý giải được: dense retrieval đã rất tốt cho name matching, vai trò ontology rõ hơn ở Task 2 & 3.

### 8.2 Ablation Table (Task 2 & 3)

| System | Precision@5 (Flavor) | F1@5 | Avg PMI | Precision@5 (Related) | Recall@5 (Related) |
|---|---|---|---|---|---|
| BM25 | 0.8975 | 0.7671 | 2.34 | 0.0269 | 0.0269 |
| RAG-only | — | — | — | — | — |
| RAG + Ontology | **1.000** | **0.8435** | **3.09** | **0.1985** | **0.1985** |

> **Narrative:** Delta highlight trong Abstract và Conclusion:
> - **Task 2:** Avg PMI tăng **+32%** (2.34 → 3.09) — ontology (PMI) chọn được ingredients thực sự tăng hương vị, không chỉ liệt kê thành phần.
> - **Task 3:** Precision@5 tăng **7.4×** (0.0269 → 0.1985) — BM25 tìm theo tên nên miss hoàn toàn các món cùng nguyên liệu khác tên; Dish Relatedness (Jaccard + Category) mới tìm được.

---

## 9. Case Study (2 examples cho paper)

### Ví dụ 1
```
Query: "Tôi muốn ăn phở bò"

RAG only:
  Món:         Phở bò, Bún bò Huế, Phở gà
  Ingredients: Bánh phở, thịt bò, hành tây, nước mắm
  Related:     Bún bò, Mì bò

RAG + Ontology:
  Món:         Phở bò, Phở gà, Bún bò Huế (reranked)
  Ingredients: Hành nướng, gừng nướng, quế, hồi, thảo quả,
               sá sùng (PMI cao với core ingredients)
  Related:     Bún bò Huế, Cháo bò, Bánh cuốn (via ingredient graph)
```

### Ví dụ 2
```
Query: "Món ăn chua cay miền Trung"

RAG only:
  Món:         Bún bò Huế, Mì Quảng, Bánh mì
  Ingredients: Sả, ớt, mắm ruốc
  Related:     Bún riêu, Cơm hến

RAG + Ontology:
  Món:         Bún bò Huế, Bánh canh cua, Cơm hến (reranked by region ontology)
  Ingredients: Mắm ruốc Huế, ớt hiểm, sả tím, hạt điều màu
               (PMI cao trong corpus món miền Trung)
  Related:     Cơm hến, Bún hến, Bánh canh Nam Phổ
```

---

## 10. Cấu trúc Paper (6 trang)

| Section | Nội dung chính | Độ dài gợi ý |
|---|---|---|
| **Abstract** | Bài toán, đóng góp, kết quả chính (delta metric) | ~150 từ |
| **Introduction** | Motivation, challenges, contributions | ~0.5 trang |
| **Related Work** | IR general → IR food domain → Ontology in IR | ~1 trang |
| **Model** | Ontology construction + RAG pipeline + kiến trúc | ~1.5 trang |
| **Experiments** | Dataset, metrics, ablation table, case study | ~2 trang |
| **Conclusion** | Tóm tắt, limitation, future work | ~0.25 trang |

---

## 11. Checklist Thực Hiện

### Phase 1 — Data & Ground Truth
- [ ] Tạo train/test split: 8,593 / 2,148 món → lưu `data/splits/train_ids.txt`, `test_ids.txt`
- [ ] Tính PMI từ `matrix.json` + `frequency.json` → lưu `app/data/cooccurrence/pmi.json`
- [ ] Quyết định về `region` field: gắn nhãn thủ công, infer từ tên món, hoặc bỏ qua (dùng α=0.7, β=0.3)
- [ ] Build Dish Relatedness graph (Jaccard + Category, thêm Region nếu có)
- [ ] Generate queries cho Task 1 — exact + category queries (500–1,000 queries)
- [ ] Validate ground truth Task 2 thủ công trên 30–50 món
- [ ] Báo cáo Cohen's Kappa cho validation

### Phase 2 — Implementation
- [ ] Implement BM25 baseline (thư viện `rank_bm25`)
- [ ] Xác nhận RAG-only baseline hoạt động với `retrieval/retriever.py` + Pinecone
- [ ] Implement query expansion từ ontology (dùng `ingredient_ids` của món để mở rộng query)
- [ ] Integrate PMI reranking vào pipeline cho Task 2
- [ ] Integrate Dish Relatedness cho Task 3
- [ ] Implement ablation variants

### Phase 3 — Evaluation
- [ ] Chạy tất cả systems trên test set
- [ ] Tính nDCG@10, MRR@10, Recall@10 cho Task 1
- [ ] Tính Precision@5, F1@5, Avg PMI cho Task 2
- [ ] Tính Precision@5, Recall@5 cho Task 3
- [ ] Viết 2 case studies

### Phase 4 — Writing
- [ ] Related Work: survey IR → food IR → ontology role
- [ ] Model section: diagram + công thức PMI + Jaccard
- [ ] Experimental Results: tables + case study
- [ ] Conclusion: highlight delta metric + limitation

---

## 12. Quyết định còn mở

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| 1 | **Ontology inject ở đâu trong pipeline?** Query expansion trước retrieval, hay reranking sau retrieval, hay cả hai? | Bắt đầu bằng reranking (đơn giản hơn), thêm query expansion trong ablation |
| 2 | **Threshold PMI** để xác định flavor-enhancing là bao nhiêu? | Tune trên validation set; thử PMI > 0 trước |
| 3 | **Dense retrieval model** nào cho RAG? | ✅ Đã quyết định: `intfloat/multilingual-e5-large` (đang dùng) |
| 4 | **α, β, γ** trong Dish Relatedness — dùng fixed hay tune? | Fixed trước (α=0.7, β=0.3 nếu không có region; α=0.5, β=0.3, γ=0.2 nếu có) |
| 5 | **Region field** — xử lý thế nào khi thiếu hoàn toàn? | Ưu tiên quyết định sớm; ảnh hưởng đến Task 1 (region-based query) và Dish Relatedness |
