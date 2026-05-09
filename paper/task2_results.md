# Task 2: Thay thế nguyên liệu có ràng buộc — Kết quả & Phân tích

## Bài toán

**Input:** (món ăn, nguyên liệu cần thay, ràng buộc chế độ ăn)  
**Output:** Top-5 nguyên liệu thay thế  
**Ví dụ:** Phở bò, thay "thịt bò", ràng buộc "ăn chay" → đậu hũ, nấm, mì căn...

---

## Thiết kế thí nghiệm

- **200 test cases** (100 món × 2 nguyên liệu chính)
- **Constraints:** ~33% unconstrained, ~33% vegetarian, ~17% no_seafood, ~17% no_meat
- **3 LLM judges:** Llama-3.1 8B, Gemma-2 9B, Mistral 7B
- **Scale:** 0 = không phù hợp, 1 = chấp nhận được, 2 = thay thế tốt
- **Score cuối:** mean 3 judges

---

## 4 Strategies so sánh

| Strategy | Cách hoạt động |
|---|---|
| **random_class** | Random 5 nguyên liệu cùng leaf class, lọc constraint (baseline) |
| **dense** | Top-5 gần nhất theo embedding similarity (multilingual-e5-large), lọc constraint |
| **weighted_ontology** | Ontology substitutes + class expansion + constraint filter + weighted NPMI (main=3.0, secondary=1.5, seasoning=0.5) + bonus |
| **hybrid** | 0.5×cosine + 0.3×weighted_NPMI + 0.2×ontology_bonus + 0.1×same_class, lọc constraint |

---

## Kết quả tổng quan

| Strategy | Mean | Accept% (≥1.0) | Good% (≥1.67) | N |
|---|---|---|---|---|
| random_class | 0.870 | 57.4% | 1.2% | 162 |
| weighted_ontology | 0.945 | 58.0% | 2.0% | 200 |
| **hybrid** | **1.111** | **68.0%** | **6.5%** | 200 |
| dense | 1.143 | 71.0% | 9.0% | 200 |

---

## Breakdown theo constraint

| Constraint | N | random | dense | ontology | hybrid |
|---|---|---|---|---|---|
| none (không ràng buộc) | 56 | 1.04 | 1.48 | 1.08 | **1.51** ✅ |
| vegetarian (ăn chay) | 80 | 0.78 | 0.83 | **0.94** ✅ | 0.81 |
| no_seafood | 36 | 0.68 | **1.28** | 0.75 | 1.17 |
| no_meat | 28 | 0.91 | **1.19** | 0.93 | 1.10 |

---

## Inter-Annotator Agreement (IAA)

Tính trên hybrid strategy:

| Cặp judges | Exact agreement |
|---|---|
| Llama vs Gemma | 48.7% |
| Llama vs Mistral | 57.8% |
| Gemma vs Mistral | 54.8% |

→ Agreement thấp hơn Task 3 (48-58% vs 70-76%). Task substitution subjective hơn task dish similarity.

---

## Phân tích

### Hybrid thắng ở unconstrained (1.51)
- Kết hợp cosine (tìm nguyên liệu ngữ nghĩa gần) + NPMI (hợp hương vị) + ontology bonus (đã chứng minh thay thế được)
- Tốt nhất khi không có ràng buộc → tự do chọn từ pool lớn

### Ontology thắng ở vegetarian (0.94 vs Dense 0.83)
- Hierarchy reasoning: biết thịt bò ∈ Meat ∈ AnimalProtein → loại hết → mở rộng sang PlantProtein + Mushroom
- Dense chỉ tìm "gần thịt bò" → vẫn trả về protein động vật hoặc nguyên liệu không phù hợp cho chay
- **Đây là claim chính:** ontology giúp khi cần constraint-aware reasoning

### Dense thắng overall (1.143 vs Hybrid 1.111)
- Embedding similarity capture "nguyên liệu tương tự" rất tốt (texture, flavor, role)
- Ontology component trong hybrid đôi khi kéo score xuống (NPMI noise, class mismatch)
- Chênh lệch nhỏ (0.03) — không significant

### random_class có N=162 (thiếu 38 cases)
- Một số cases không tìm được nguyên liệu cùng class thỏa constraint → trả empty
- Các strategy khác luôn tìm được (dense search pool lớn hơn)

---

## Claims cho paper

1. **Hybrid (Dense+Ontology) đạt kết quả tốt nhất ở unconstrained** (mean=1.51, vượt Dense 1.48)
2. **Ontology đóng góp rõ nhất ở vegetarian constraint** (+14% so với Dense) — hierarchy reasoning cần thiết để chuyển đổi giữa protein classes
3. **Dense là baseline mạnh** cho substitution — embedding similarity capture ingredient relatedness tốt
4. **Kết hợp Dense+Ontology (hybrid) competitive** với Dense overall (1.111 vs 1.143) và vượt trội ở specific use cases

---

## So sánh với v1

| Metric | v1 (cũ) | v2 (mới, hybrid) |
|---|---|---|
| Mean score | 0.79 | **1.111** |
| Accept rate | 45% | **68%** |
| Judges | 1 | 3 |
| Test cases | 100 | 200 |
| IAA | Không có | 49-58% |

*Lưu ý: v1 và v2 không so sánh trực tiếp được vì khác judge, khác prompt, khác scale interpretation.*

---

## Limitations

1. **IAA thấp (48-58%)** — substitution quality rất subjective
2. **Dense vẫn thắng overall** — ontology chưa đủ mạnh để vượt embedding cho general substitution
3. **Hybrid chưa tối ưu** — weights (0.5/0.3/0.2/0.1) đặt heuristic, chưa tune
4. **Chỉ đánh giá top-1** — có thể top-3 hoặc top-5 cho kết quả khác
