# Annotation Guide — Task 2: Flavor-enhancing Ingredients

## Nhiệm vụ

Với mỗi dòng trong file `annotation_template.csv`, đánh giá:

> **Nguyên liệu [{candidate_name}] tăng hương vị cho món [{dish_name}] ở mức nào?**

Điền vào cột `annotator_1` (hoặc `annotator_2`):
- `0` = Không phù hợp — nguyên liệu này không giúp tăng hương vị
- `1` = Phù hợp — cải thiện hương vị ở mức vừa phải
- `2` = Rất phù hợp — nguyên liệu đặc trưng, tăng hương vị rõ rệt

## Ví dụ

| Món | Candidate | Score | Lý do |
|---|---|---|---|
| Phở bò | quế | **2** | Gia vị đặc trưng của phở, tăng hương vị rõ rệt |
| Phở bò | hành lá | **1** | Phù hợp, thêm hương nhưng không đặc trưng |
| Phở bò | bột mì | **0** | Không liên quan đến hương vị phở |
| Cá kho | gừng | **2** | Khử tanh, tăng hương — đặc trưng cho cá kho |
| Cá kho | đường | **1** | Cần thiết cho vị kho nhưng không nổi bật |
| Cá kho | sữa tươi | **0** | Không phù hợp |

## Lưu ý

- Đánh giá theo hiểu biết ẩm thực thực tế, không cần tra cứu công thức
- Hai annotator làm **ĐỘC LẬP**
- Nếu không chắc, ghi lý do vào cột `notes`
- Ước tính: ~1654 judgements · ~28–38 phút

## Files

- `annotation_template.csv` — file cần điền
- Gửi lại file sau khi hoàn thành
