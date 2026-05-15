# TASK 2: CONSTRAINED INGREDIENT SUBSTITUTION
## Giải thích chi tiết Methodology + Results

---

## 📋 BÀI TOÁN

**Mục tiêu:** Thay thế một nguyên liệu trong món ăn với ràng buộc chế độ ăn

**Input:**
- Món ăn (ví dụ: Phở bò)
- Nguyên liệu cần thay (ví dụ: thịt bò)
- Ràng buộc (ví dụ: vegetarian, no_seafood, no_meat, hoặc không ràng buộc)

**Output:**
- Top-5 nguyên liệu thay thế phù hợp

**Ví dụ cụ thể:**
```
Món: Phở bò = {bánh phở, thịt bò, hành, giá, rau thơm, nước mắm}
Thay: thịt bò
Constraint: vegetarian (ăn chay)
→ Output: đậu hũ, nấm đông cô, tempeh, mì căn, đậu nành...
```

---

## 🔄 PHƯƠNG PHÁP: SO SÁNH 4 STRATEGIES

### 1️⃣ **random_class** (Baseline)
**Cách hoạt động:**
- Lấy class của nguyên liệu gốc (thịt bò → Meat)
- Random 5 nguyên liệu cùng leaf class
- Lọc theo constraint (loại AnimalProtein nếu vegetarian)

**Ưu điểm:** Đơn giản, đảm bảo cùng nhóm ngữ nghĩa
**Nhược điểm:** 
- Không xét compatibility với món
- Có thể không tìm được đủ 5 ứng viên (N=162/200 cases)

---

### 2️⃣ **dense** (Embedding-only)
**Cách hoạt động:**
- Dùng embedding multilingual-e5-large (1024-dim)
- Tìm top-30 nguyên liệu gần nhất với nguyên liệu gốc theo cosine similarity
- Lọc constraint
- Chọn top-5

**Ưu điểm:** 
- Capture semantic similarity tốt (texture, flavor, role)
- Pool candidates rộng (2,112 nguyên liệu)

**Nhược điểm:**
- Không hiểu constraint reasoning (ví dụ: vegetarian cần loại toàn bộ AnimalProtein subtree)
- Không xét compatibility với nguyên liệu khác trong món

---

### 3️⃣ **weighted_ontology** (Ontology-enhanced)
**Cách hoạt động:**

**Bước 1: Tìm candidates**
```
thịt bò → class "Meat" 
       → lấy cùng class + sibling classes (Poultry, Seafood)
       → Constraint "vegetarian" → loại hết AnimalProtein
       → Mở rộng sang PlantProtein + Mushroom
       → Candidates: đậu hũ, tempeh, nấm đông cô, mì căn...
```

**Bước 2: Scoring với Weighted NPMI**
```
Score(đậu hũ) = NPMI_weighted(đậu hũ, món còn lại)
              + 0.3 (nếu ontology có relation "substitutes")
              + 0.2 (nếu cùng leaf class)

NPMI_weighted = Σ(w_i × NPMI(đậu hũ, ingredient_i)) / Σ(w_i)

Weights theo role:
- main ingredient (bánh phở): w = 3.0
- secondary (hành, giá): w = 1.5  
- seasoning (nước mắm): w = 0.5
```

**Ưu điểm:**
- Hierarchy reasoning cho constraint (vegetarian → loại AnimalProtein subtree)
- Weighted NPMI ưu tiên compatibility với main ingredients
- Ontology bonus cho substitutes đã được chứng minh

**Nhược điểm:**
- Pool candidates nhỏ hơn dense
- NPMI có thể noisy với rare ingredients

---

### 4️⃣ **hybrid** (Dense + Ontology)
**Cách hoạt động:**

**Bước 1: Union candidates**
```
Embedding top-30 (như dense)
∪
Ontology candidates (như weighted_ontology)
→ Pool ~100-200 ứng viên
```

**Bước 2: Hybrid scoring**
```
Score(c) = 0.5 × cosine(embed_c, embed_original)     ← "giống nguyên liệu gốc?"
         + 0.3 × NPMI_weighted(c, món còn lại)       ← "hợp với món?"
         + 0.2 × ontology_bonus                       ← "đã chứng minh thay được?"
         + 0.1 × same_class_bonus                     ← "cùng nhóm?"
```

**Ưu điểm:**
- Kết hợp semantic similarity (embedding) + compatibility (NPMI) + structured knowledge (ontology)
- Pool candidates rộng nhất

**Nhược điểm:**
- Weights (0.5/0.3/0.2/0.1) đặt heuristic, chưa tune
- Phức tạp hơn

---

## 📊 KẾT QUẢ THÍ NGHIỆM

### Setup
- **200 test cases** (100 món × 2 nguyên liệu chính)
- **Constraints:** 
  - 56 cases: none (không ràng buộc)
  - 80 cases: vegetarian
  - 36 cases: no_seafood
  - 28 cases: no_meat
- **3 LLM judges:** Llama-3.1 8B, Gemma-2 9B, Mistral 7B
- **Scale:** 0 = không phù hợp, 1 = chấp nhận được, 2 = thay thế tốt
- **Metric:** Mean score của 3 judges

---

### Kết quả tổng quan

| Strategy | Mean Score | Accept% (≥1.0) | Good% (≥1.67) | N cases |
|----------|-----------|----------------|---------------|---------|
| random_class | 0.870 | 57.4% | 1.2% | 162 ⚠️ |
| weighted_ontology | 0.945 | 58.0% | 2.0% | 200 |
| **hybrid** | **1.111** | **68.0%** | **6.5%** | 200 |
| **dense** | **1.143** ✅ | **71.0%** | **9.0%** | 200 |

**Quan sát chính:**
1. **Dense thắng overall** (1.143) — embedding similarity rất mạnh cho substitution
2. **Hybrid đứng thứ 2** (1.111) — chênh lệch nhỏ (0.03), không significant
3. **Ontology cải thiện so với random** (+8.6% mean score)
4. **random_class thiếu 38 cases** — không tìm được ứng viên thỏa constraint

---

### Breakdown theo constraint (Mean Score)

| Constraint | N | random | dense | weighted_ontology | hybrid |
|-----------|---|--------|-------|-------------------|--------|
| **none** | 56 | 1.04 | 1.48 | 1.08 | **1.51** ✅ |
| **vegetarian** | 80 | 0.78 | 0.83 | **0.94** ✅ | 0.81 |
| **no_seafood** | 36 | 0.68 | **1.28** ✅ | 0.75 | 1.17 |
| **no_meat** | 28 | 0.91 | **1.19** ✅ | 0.93 | 1.10 |

---

## 🔍 PHÂN TÍCH CHI TIẾT

### 1. Hybrid thắng ở unconstrained (1.51 vs Dense 1.48)

**Tại sao?**
- Không có ràng buộc → pool candidates rộng nhất
- Cosine similarity tìm nguyên liệu "giống" về ngữ nghĩa
- Weighted NPMI đảm bảo hợp với món
- Ontology bonus cho substitutes đã được chứng minh

**Ví dụ:**
```
Món: Bún bò Huế, thay "thịt bò", no constraint
Dense: thịt heo, thịt gà, thịt cừu (chỉ dựa embedding)
Hybrid: thịt heo, thịt gà, chả bò (embedding + NPMI biết chả bò hay xuất hiện với bún)
```

---

### 2. Ontology thắng ở vegetarian (0.94 vs Dense 0.83) ⭐

**Đây là claim chính của paper!**

**Tại sao ontology quan trọng?**

**Ví dụ cụ thể:**
```
Món: Phở bò, thay "thịt bò", constraint: vegetarian

Dense approach:
  embedding(thịt bò) → top-30 gần nhất
  → thịt heo (0.92), thịt gà (0.89), cá (0.85), đậu hũ (0.78)...
  → Lọc vegetarian → loại thịt heo, thịt gà, cá
  → Còn: đậu hũ, nấm, nhưng có thể bỏ sót protein thực vật khác

Ontology approach:
  thịt bò ∈ Meat ∈ AnimalProtein
  → Constraint vegetarian → loại toàn bộ AnimalProtein subtree
  → Mở rộng sang PlantProtein + Mushroom classes
  → Candidates: đậu hũ, tempeh, đậu nành, nấm đông cô, mì căn, seitan...
  → Rank bằng weighted NPMI
```

**Kết quả:**
- Ontology: 0.94 (tốt hơn 13% so với Dense 0.83)
- Hierarchy reasoning giúp chuyển đổi giữa protein classes một cách có cấu trúc
- Dense chỉ tìm "gần" nhưng không hiểu "loại bỏ toàn bộ động vật"

---

### 3. Dense thắng ở no_seafood và no_meat

**Tại sao?**
- Constraints này đơn giản hơn vegetarian (chỉ loại 1 class, không cần chuyển đổi subtree)
- Embedding similarity đủ mạnh để tìm alternatives
- Ontology không có lợi thế đặc biệt

**Ví dụ:**
```
Món: Bún riêu, thay "cua", constraint: no_seafood
Dense: tìm embedding gần "cua" → tôm (loại), mực (loại), thịt heo (giữ) ✅
Ontology: cua ∈ Seafood → loại Seafood → mở rộng sang Meat → thịt heo ✅
→ Kết quả tương đương, nhưng Dense đơn giản hơn
```

---

### 4. random_class có N=162 (thiếu 38 cases)

**Tại sao?**
- Một số cases không tìm được nguyên liệu cùng class thỏa constraint
- Ví dụ: thay "tôm" (Seafood), constraint vegetarian → không có nguyên liệu nào trong Seafood class thỏa vegetarian
- Dense và hybrid luôn tìm được vì search pool lớn hơn (toàn bộ 2,112 nguyên liệu)

---

## 📈 INTER-ANNOTATOR AGREEMENT (IAA)

Tính trên hybrid strategy:

| Cặp judges | Exact agreement |
|-----------|-----------------|
| Llama vs Gemma | 48.7% |
| Llama vs Mistral | 57.8% |
| Gemma vs Mistral | 54.8% |

**So sánh với Task 3:**
- Task 3 (dish similarity): 70-76% agreement
- Task 2 (substitution): 48-58% agreement

**Giải thích:**
- Substitution quality rất subjective
- Phụ thuộc vào cultural acceptability, texture, flavor profile
- Không có ground truth rõ ràng như dish similarity

---

## 🎯 CLAIMS CHO PAPER

### Claim 1: Hybrid competitive với Dense overall
```
Hybrid: 1.111 (68% accept rate)
Dense:  1.143 (71% accept rate)
Chênh lệch: 0.03 (2.8%) — không significant
```
→ Ontology không làm giảm performance, đồng thời mang lại lợi ích ở specific constraints

---

### Claim 2: Ontology đóng góp rõ nhất ở vegetarian constraint ⭐
```
weighted_ontology: 0.94
dense:             0.83
Improvement:       +13%
```
→ **Hierarchy reasoning cần thiết** để chuyển đổi giữa protein classes

---

### Claim 3: Hybrid thắng ở unconstrained
```
hybrid: 1.51
dense:  1.48
Improvement: +2%
```
→ Kết hợp embedding + NPMI + ontology bonus tối ưu khi không có ràng buộc

---

### Claim 4: Dense là baseline mạnh
```
Dense thắng overall (1.143)
Dense thắng ở no_seafood (1.28) và no_meat (1.19)
```
→ Embedding similarity capture ingredient relatedness rất tốt

---

## 📊 SO SÁNH VỚI VERSION CŨ (v1)

| Metric | v1 (paper cũ) | v2 (hiện tại, hybrid) |
|--------|---------------|----------------------|
| Mean score | 0.79 | **1.111** (+40%) |
| Accept rate | 45% | **68%** (+51%) |
| Good rate | 34% | **6.5%** ⚠️ |
| Judges | 1 (Qwen-2.5 7B) | 3 (Llama, Gemma, Mistral) |
| Test cases | 100 | 200 |
| IAA | Không có | 49-58% |

**Lưu ý quan trọng:**
- **Không so sánh trực tiếp được** vì:
  - Khác judge (1 vs 3)
  - Khác prompt
  - Khác scale interpretation (v1: 2=good, v2: ≥1.67=good)
- Good rate giảm (34% → 6.5%) vì threshold khác nhau

---

## ⚠️ LIMITATIONS

### 1. IAA thấp (48-58%)
- Substitution quality rất subjective
- Judges không đồng ý về "thay thế tốt" vs "chấp nhận được"
- Cần human annotation để validate

### 2. Dense vẫn thắng overall
- Ontology chưa đủ mạnh để vượt embedding cho general substitution
- Chỉ có lợi thế ở vegetarian constraint

### 3. Hybrid weights chưa tối ưu
- Weights (0.5/0.3/0.2/0.1) đặt heuristic
- Chưa tune trên dev set
- Có thể cải thiện bằng grid search hoặc learning

### 4. Chỉ đánh giá top-1
- Judges chỉ score top-1 substitute
- Có thể top-3 hoặc top-5 cho kết quả khác
- Không đánh giá diversity của top-5

### 5. Constraint coverage không đều
- vegetarian: 80 cases (40%)
- no_seafood: 36 cases (18%)
- no_meat: 28 cases (14%)
- none: 56 cases (28%)
→ Kết quả vegetarian đáng tin hơn

---

## 💡 TAKEAWAYS

1. **Embedding similarity rất mạnh** cho ingredient substitution — Dense là baseline khó vượt

2. **Ontology có giá trị ở constraint reasoning** — đặc biệt vegetarian (+13%)

3. **Hybrid approach competitive** — không thua Dense overall, thắng ở unconstrained

4. **Weighted NPMI quan trọng** — ưu tiên compatibility với main ingredients

5. **Cần human validation** — IAA thấp cho thấy LLM judges chưa đủ reliable

---

## 📝 TÓM TẮT SO SÁNH 4 STRATEGIES

| Aspect | random_class | dense | weighted_ontology | hybrid |
|--------|-------------|-------|-------------------|--------|
| **Candidates** | Cùng class | Embedding top-30 | Ontology + siblings | Union cả hai |
| **Scoring** | Random | Cosine | Weighted NPMI + bonus | 0.5×cosine + 0.3×NPMI + bonus |
| **Constraint** | Filter sau | Filter sau | Hierarchy reasoning | Hierarchy reasoning |
| **Pool size** | Nhỏ (~20-50) | Lớn (2,112) | Trung bình (~50-100) | Rất lớn (~100-200) |
| **Mean score** | 0.870 | **1.143** ✅ | 0.945 | 1.111 |
| **Best at** | — | Overall, no_seafood, no_meat | **vegetarian** ✅ | **unconstrained** ✅ |
| **Weakness** | Thiếu cases | Không hiểu hierarchy | Pool nhỏ | Weights chưa tune |
