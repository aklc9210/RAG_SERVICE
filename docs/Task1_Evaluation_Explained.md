# Task 1 — Giải thích cách đánh giá Class-based Retrieval

## Tổng quan

Đánh giá khả năng tìm kiếm món ăn theo class nguyên liệu. Ví dụ: user hỏi "món nấm" → system phải trả về các dish có chứa nguyên liệu thuộc class Mushroom.

## Dữ liệu đầu vào

### 200 queries (`task1_class_queries.jsonl`)

Mỗi query gồm:
```json
{
  "query": "vịt nấu với me",
  "type": "multi_class",
  "classes_positive": ["Poultry", "SourSeasoning"],
  "classes_negative": [],
  "cooking_method": null,
  "gt_dish_ids": ["dish0123", "dish0456", ...],
  "gt_count": 136
}
```

### Ground Truth (GT) được build thế nào?

Dùng FoodOntology API duyệt toàn bộ 10,741 dishes:

```
Với query "vịt nấu với me" (pos=[Poultry, SourSeasoning]):

Dish "Vịt nấu chao" có ingredients: [vịt, chao, sả, gừng, me, ...]
  → vịt ∈ Poultry? ✅ (ingre07930 → Poultry)
  → me ∈ SourSeasoning? ✅ (ingre04xxx → SourSeasoning)
  → Dish này thuộc GT ✅

Dish "Phở bò" có ingredients: [thịt bò, bánh phở, hành, ...]
  → Không có ingredient ∈ Poultry → Loại ❌
```

Tương tự cho negation: "món thịt không cay" → dish phải có Meat VÀ không có Spicy.

## 3 Systems được so sánh

### 1. BM25 (keyword baseline)

Cách hoạt động:
- Index mỗi dish = `tên món × 3 + category + tên nguyên liệu`
- Query "món nấm" → match keyword "nấm" trong index
- Xếp hạng bằng BM25 score (TF-IDF variant)

Hạn chế: chỉ match đúng từ "nấm", bỏ sót "nấm hương", "nấm đông cô", "nấm rơm"...

### 2. RAG-only (dense retrieval)

Cách hoạt động:
- Embed mỗi dish thành vector 1024-dim (multilingual-e5-large)
- Embed query thành vector
- Tính cosine similarity, lấy top-k gần nhất

Ưu điểm: hiểu semantic ("món nấm" gần với "nấm hương xào" dù không match keyword)
Hạn chế: không hiểu class hierarchy, không filter được negation/cooking method

### 3. RAG+Ontology

Cách hoạt động:
1. **Query expansion**: "món nấm" → ontology biết Mushroom class có 87 ingredients → thêm "nấm hương", "nấm đông cô", "nấm rơm"... vào query
2. **Dense retrieval**: embed expanded query → tìm top-k
3. **Post-filter**: loại dish vi phạm negation class hoặc sai cooking method

Ưu điểm: kết hợp semantic + ontology knowledge + structured filtering

## Metrics — Cách tính

Giả sử top-20 kết quả trả về cho 1 query:

```
Vị trí:  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20
Đúng?    ✅ ✅ ❌ ✅ ❌ ❌ ✅ ❌ ❌ ✅  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌  ❌
```

GT có 500 dishes đúng tổng cộng.

### Precision@20 (P@20)

> Trong 20 kết quả trả về, bao nhiêu % đúng?

```
P@20 = số đúng / 20 = 5 / 20 = 0.25
```

### Recall@20 (R@20)

> Trong tổng số GT, đã tìm được bao nhiêu %?

```
R@20 = số đúng / |GT| = 5 / 500 = 0.01
```

→ Recall thấp vì GT = 500 mà chỉ lấy top-20. Đây là expected.

### F1@20

> Trung bình điều hòa của P và R

```
F1 = 2 × P × R / (P + R) = 2 × 0.25 × 0.01 / 0.26 = 0.019
```

### MAP (Mean Average Precision)

> Đo chất lượng xếp hạng — kết quả đúng ở vị trí cao hơn được thưởng nhiều hơn

Tính AP cho 1 query:
```
Vị trí 1: đúng → precision tại đây = 1/1 = 1.0
Vị trí 2: đúng → precision tại đây = 2/2 = 1.0
Vị trí 3: sai  → bỏ qua
Vị trí 4: đúng → precision tại đây = 3/4 = 0.75
Vị trí 7: đúng → precision tại đây = 4/7 = 0.571
Vị trí 10: đúng → precision tại đây = 5/10 = 0.5

AP = (1.0 + 1.0 + 0.75 + 0.571 + 0.5) / 500 = 0.00764
```

Chia cho |GT|=500 (không phải 5) vì AP phạt khi recall thấp.

MAP = trung bình AP trên 200 queries.

### NDCG@20 (Normalized Discounted Cumulative Gain)

> Tương tự MAP nhưng dùng log discount — vị trí càng thấp càng bị giảm giá trị

```
DCG = 1/log₂(2) + 1/log₂(3) + 0 + 1/log₂(5) + 0 + 0 + 1/log₂(8) + ... + 1/log₂(11)
    = 1.0 + 0.63 + 0.43 + 0.36 + 0.29 = 2.71

Ideal DCG (nếu 5 kết quả đúng đều ở top-5):
    = 1/log₂(2) + 1/log₂(3) + 1/log₂(4) + 1/log₂(5) + 1/log₂(6)
    = 1.0 + 0.63 + 0.5 + 0.43 + 0.39 = 2.95

NDCG = DCG / Ideal = 2.71 / 2.95 = 0.92
```

NDCG cao = kết quả đúng nằm ở vị trí đầu.

## Kết quả

```
System               P@20     R@20     F1@20    MAP      NDCG@20
─────────────────────────────────────────────────────────────────
BM25                 0.2298   0.0152   0.0223   0.0065   0.2322
RAG-only             0.3385   0.0232   0.0343   0.0119   0.3443
RAG+Ontology         0.4475   0.0335   0.0494   0.0202   0.4772
```

### Đọc kết quả thế nào?

- **P@20 = 0.45** (RAG+Ontology): trung bình 9/20 kết quả đúng class
- **R@20 thấp ở cả 3**: do GT lớn (median 462 dishes) mà chỉ retrieve 20 → expected
- **NDCG@20 = 0.48**: kết quả đúng có xu hướng nằm ở vị trí cao (top-5 thay vì top-20)

### Tại sao RAG+Ontology thắng?

| Ví dụ query | BM25 | RAG-only | RAG+Ontology |
|---|---|---|---|
| "món nấm" | Chỉ match "nấm" | Hiểu semantic nhưng không biết "nấm hương" = Mushroom | Expand → "nấm hương nấm đông cô nấm rơm..." |
| "món thịt không cay" | Không hiểu "không" | Không filter được | Post-filter loại dish có Spicy |
| "món hấp hải sản" | Match "hấp" + "hải sản" | Hiểu semantic | Expand hải sản + filter method=Steam |

### Per-type breakdown (RAG+Ontology)

| Query type | P@20 | Giải thích |
|---|---|---|
| single_class | ~0.83 | Dễ nhất — chỉ cần match 1 class |
| negation | ~0.61 | Post-filter giúp loại dish sai |
| multi_class | ~0.30 | Khó — cần match 2+ class cùng lúc |
| cooking_method | ~0.06 | Khó nhất — BM25 backbone không filter method tốt |
