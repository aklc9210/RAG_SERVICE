# Task 2: Phương thức — Giải thích chi tiết

## Bài toán

**Input:** (món ăn, nguyên liệu cần thay, ràng buộc chế độ ăn)  
**Output:** Top-5 nguyên liệu thay thế  

---

## Ví dụ: Thay "thịt bò" trong "Phở bò", ràng buộc "ăn chay"

Phở bò có: {bánh phở, thịt bò, hành, giá, rau thơm, nước mắm}

---

## Bước 1: Tìm ứng viên (candidates)

**Cũ:** Chỉ nhìn trong ontology
```
thịt bò → class "Meat" → lấy cùng class + sibling (Poultry, Seafood...)
→ Constraint "ăn chay" → loại hết AnimalProtein
→ Mở rộng sang PlantProtein + Mushroom
→ Candidates: đậu hũ, tempeh, nấm đông cô, mì căn, đậu nành...
```
Pool nhỏ, chỉ ~50-100 ứng viên từ ontology.

**Mới:** Nhìn cả embedding
```
Embedding "thịt bò" → tìm 30 nguyên liệu gần nhất trong 2,112 nguyên liệu
→ Lọc constraint → giữ: đậu hũ, nấm portobello, protein đậu nành, seitan...

UNION với ontology candidates (như cũ)
→ Pool lớn hơn, ~100-200 ứng viên
```

---

## Bước 2: Chấm điểm (scoring)

**Cũ:** Chỉ dùng NPMI
```
Score(đậu hũ) = NPMI_avg(đậu hũ, [bánh phở, hành, giá, rau thơm, nước mắm])
              + 0.3 (nếu ontology nói đậu hũ thay được thịt bò)
              + 0.2 (nếu cùng class)

Vấn đề: NPMI(đậu hũ, nước mắm) và NPMI(đậu hũ, bánh phở) 
         được coi NGANG NHAU — nhưng bánh phở quan trọng hơn nước mắm!
```

**Mới:** Weighted NPMI + Cosine
```
Score(đậu hũ) = 0.5 × cosine(embed_đậu_hũ, embed_thịt_bò)     ← "giống thịt bò không?"
              + 0.3 × NPMI_weighted                              ← "hợp với món không?"
              + 0.2 × ontology_bonus                             ← "đã chứng minh thay được?"
              + 0.1 × same_class_bonus

NPMI_weighted = (3.0×NPMI(đậu hũ, bánh phở) + 0.5×NPMI(đậu hũ, nước mắm) + ...) 
              / (3.0 + 0.5 + ...)
              
              ↑ bánh phở (main, w=3.0) quan trọng gấp 6 lần nước mắm (seasoning, w=0.5)
```

---

## Tóm lại sự khác biệt

```
CŨ:  Ontology candidates → NPMI flat → rank
MỚI: (Ontology + Embedding) candidates → (Cosine + Weighted NPMI + Ontology bonus) → rank
```

| | Cũ | Mới |
|---|---|---|
| Candidates | Chỉ từ ontology (class + siblings) | Union: embedding top-30 + ontology |
| NPMI | Flat (mọi ingredient ngang nhau) | Weighted (main=3.0 > secondary=1.5 > seasoning=0.5) |
| Scoring | NPMI + bonus | 0.5×cosine + 0.3×NPMI + bonus |
| Embedding | Không dùng | Dùng (multilingual-e5-large) |

---

## Tại sao thay đổi?

1. **Thêm embedding** → tìm ứng viên "giống" nguyên liệu gốc về ngữ nghĩa (texture, role trong món). Ontology chỉ biết "cùng nhóm" nhưng không biết "giống về kết cấu".

2. **Weighted NPMI** → đảm bảo ứng viên hợp với nguyên liệu **chính** của món, không chỉ hợp với gia vị. Đậu hũ hợp với bánh phở (main) quan trọng hơn đậu hũ hợp với nước mắm (seasoning).

3. **Pool candidates rộng hơn** → embedding tìm được nguyên liệu mà ontology bỏ sót (ví dụ: seitan, protein đậu nành — có thể không nằm trong cùng class nhưng embedding biết chúng "giống thịt").
