# Hướng dẫn gán nhãn — Human Annotation Validation

Mục đích: **Xác nhận chất lượng ground truth** cho Task 1 (rule-based labels) và Task 2 (LLM-judge labels) bằng con người. Kết quả dùng để báo cáo agreement giữa human và hệ thống tự động trong paper.

---

## Task 1 — Class-Based Dish Retrieval

**File:** `task1_human_annotation.csv`  (500 dòng, ~2 annotators × 500 = 1000 judgements)
**Thời gian ước tính:** 40–60 phút / annotator

### Câu hỏi gán nhãn

Với mỗi dòng: **Món `{candidate_dish_name}` có khớp với truy vấn `{query}` không?**

- `1` = Có khớp (món chứa đúng nhóm nguyên liệu / phương pháp nấu được yêu cầu)
- `0` = Không khớp

### Cột tham khảo

- `query`: truy vấn người dùng (VD: "món nấm ngon", "các món không hải sản")
- `query_type`: single_class / multi_class / negation / cooking_method
- `classes_positive`: nhóm nguyên liệu phải có (VD: Mushroom)
- `classes_negative`: nhóm nguyên liệu không được có (VD: Seafood)
- `cooking_method`: phương pháp nấu bắt buộc (nếu có)
- `candidate_dish_name`, `candidate_ingredients_preview`: thông tin món ứng viên

### Điền vào cột `annotator_1` (annotator 1) hoặc `annotator_2` (annotator 2)

### Ví dụ

| Query | Candidate | Label | Lý do |
|---|---|---|---|
| món nấm ngon | Nấm đùi gà xào tỏi | **1** | Có nấm (nhóm Mushroom) |
| món nấm ngon | Phở bò | **0** | Không có nấm |
| món không hải sản | Thịt kho tàu | **1** | Không chứa hải sản |
| món không hải sản | Canh chua cá | **0** | Có cá (Seafood) — vi phạm negation |
| món xào | Rau muống xào tỏi | **1** | Đúng phương pháp xào |
| món xào | Canh bí đỏ | **0** | Phương pháp nấu (canh), không phải xào |

---

## Task 2 — Related-Dish Recommendation (trước đây là Task 3)

**File:** `task2_human_annotation.csv`  (300 dòng, ~2 annotators × 300 = 600 judgements)
**Thời gian ước tính:** 30–45 phút / annotator

### Câu hỏi gán nhãn

Với mỗi dòng: **Món `{candidate_dish_name}` liên quan đến món `{anchor_dish_name}` ở mức nào?**

- `0` = Không liên quan — khác nguyên liệu chính, khác phong cách nấu
- `1` = Liên quan — có điểm chung về nguyên liệu hoặc phong cách
- `2` = Rất liên quan — nhiều nguyên liệu chung, cùng phong cách, có thể thay thế nhau

(Thang điểm này giống với LLM judges dùng trong paper để có thể so sánh trực tiếp.)

### Ví dụ

| Anchor | Candidate | Score | Lý do |
|---|---|---|---|
| Lẩu gà nước dừa | Lẩu gà lá giang | **2** | Cùng là lẩu gà, nhiều nguyên liệu chung |
| Lẩu gà nước dừa | Gà hầm sả | **1** | Cùng dùng gà+sả, nhưng khác kiểu nấu (lẩu vs hầm) |
| Lẩu gà nước dừa | Bún bò Huế | **0** | Khác nguyên liệu chính, khác phong cách |
| Phở bò | Bún bò Huế | **1** | Cùng dùng bò, cùng món nước, nhưng gia vị khác |
| Phở bò | Phở bò tái nạm | **2** | Gần như cùng món |
| Phở bò | Bánh mì | **0** | Khác hoàn toàn |

### Điền vào cột `annotator_1` hoặc `annotator_2`

---

## Quy trình & Nguyên tắc

1. **Hai annotators làm độc lập**, không trao đổi cho đến khi xong cả 2 files
2. **Không nhìn cột `rule_label` / `llm_mean_score`** — đó là answer key ẩn, dùng để so sánh sau
3. Nếu không chắc, viết lý do vào cột `notes`
4. **Không được dùng công cụ bên ngoài** (Google, ChatGPT) — chỉ dựa trên kiến thức ẩm thực Việt Nam của bạn

## Output sau khi gán nhãn

Sau khi cả 2 annotators hoàn thành, sẽ chạy script thống kê để tính:

- **Human-vs-system agreement** (% trùng khớp nhãn)
- **Cohen's kappa** giữa 2 annotators (độ tin cậy internal)
- **Spearman correlation** giữa human score và LLM-judge mean (Task 2)
- **Precision/Recall** của rule-based labels so với human (Task 1)

Kết quả sẽ được thêm vào Section 5.3 (Evaluation Protocol) của paper để tăng độ thuyết phục.
