# Annotation Guide — Task 3: Related Dishes

## Nhiệm vụ

Với mỗi dòng trong file `task3_annotation_template.csv`, đánh giá:

> **Món [{candidate_dish_name}] liên quan đến món [{query_dish_name}] ở mức nào?**

Điền vào cột `annotator_1` (hoặc `annotator_2`):
- `0` = Không liên quan — khác nguyên liệu chính, khác phong cách nấu
- `1` = Liên quan — có điểm chung về nguyên liệu hoặc phong cách
- `2` = Rất liên quan — nhiều nguyên liệu chung, cùng phong cách, có thể thay thế nhau

## Ví dụ

| Query | Candidate | Score | Lý do |
|---|---|---|---|
| Lẩu gà nước dừa | Lẩu gà lá giang | **2** | Cùng là lẩu gà, nhiều nguyên liệu chung, thay thế được |
| Lẩu gà nước dừa | Gà hầm sả | **1** | Cùng dùng gà + sả, nhưng khác kiểu nấu (lẩu vs hầm) |
| Lẩu gà nước dừa | Bún bò Huế | **0** | Khác nguyên liệu chính (bò vs gà), khác phong cách |
| Phở bò | Bún bò Huế | **1** | Cùng dùng bò, cùng là món nước, nhưng gia vị khác |
| Phở bò | Phở bò tái nạm | **2** | Gần như cùng món, nguyên liệu giống nhau |
| Phở bò | Bánh mì | **0** | Khác hoàn toàn |

## Cột `query_ingredients_preview` và `candidate_ingredients_preview`

Hiển thị 5 nguyên liệu đầu tiên — giúp đánh giá nhanh mức độ tương đồng.

## Lưu ý

- Hai annotator làm **ĐỘC LẬP**, không trao đổi kết quả cho đến khi xong
- Nếu không chắc, ghi lý do vào cột `notes`
- Ước tính: 1600 judgements · ~26–36 phút

## Files

- `task3_annotation_template.csv` — file cần điền
- Gửi lại file sau khi hoàn thành
