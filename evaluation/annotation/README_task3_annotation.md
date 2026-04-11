# Annotation Guide — Task 3: Related Dishes

## Nhiệm vụ

Với mỗi dòng trong file `task3_annotation_template.csv`, đánh giá:

> **Món [{candidate_dish_name}] có LIÊN QUAN đến món [{query_dish_name}] không?**

Điền vào cột `annotator_1` (hoặc `annotator_2`):
- `1` = Có — hai món này liên quan (nguyên liệu tương tự, cùng phong cách, có thể thay thế nhau)
- `0` = Không — hai món không liên quan hoặc rất khác nhau

## Hướng dẫn chi tiết

**Hai món LIÊN QUAN khi:**
- Dùng nhiều nguyên liệu chính giống nhau (VD: gà + sả + nước dừa)
- Cùng phong cách chế biến (VD: cả hai đều là lẩu/canh/kho)
- Có thể thay thế cho nhau trong một bữa ăn

**Hai món KHÔNG LIÊN QUAN khi:**
- Nguyên liệu chính hoàn toàn khác
- Phong cách ẩm thực khác nhau (VD: một món miền Bắc, một món Tây)
- Không có điểm chung về nguyên liệu hoặc cách nấu

## Ví dụ

| Query | Candidate | Label | Lý do |
|---|---|---|---|
| Lẩu gà nước dừa | Lẩu gà lá giang | **1** | Cùng là lẩu gà, nhiều nguyên liệu chung |
| Lẩu gà nước dừa | Gà hầm sả | **1** | Cùng dùng gà + sả, phong cách gần |
| Lẩu gà nước dừa | Bún bò Huế | **0** | Khác nguyên liệu chính (bò vs gà), khác phong cách |
| Phở bò | Bún bò Huế | **1** | Cùng dùng bò, cùng là món nước |
| Phở bò | Bánh mì | **0** | Khác hoàn toàn |

## Cột `query_ingredients_preview` và `candidate_ingredients_preview`

Cột này hiển thị 5 nguyên liệu đầu tiên của món — giúp bạn đánh giá nhanh mức độ tương đồng.
Không cần phải biết công thức đầy đủ.

## Lưu ý

- Hai annotator làm **ĐỘC LẬP**, không trao đổi kết quả cho đến khi xong
- Nếu không chắc, ghi lý do vào cột `notes`
- Ước tính: 400 judgements · ~6–16 phút

## Files

- `task3_annotation_template.csv` — file cần điền
- Gửi lại file sau khi hoàn thành
