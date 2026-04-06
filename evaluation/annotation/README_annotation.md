# Annotation Guide — Flavor-enhancing Ingredients

## Nhiệm vụ

Với mỗi dòng trong file `annotation_template.csv`, đánh giá:

> **Nguyên liệu [candidate_name] có làm TĂNG HƯƠNG VỊ của món [dish_name] không?**

Điền vào cột `annotator_1` (hoặc `annotator_2`):
- `1` = Có — nguyên liệu này thực sự bổ sung/tăng hương vị cho món
- `0` = Không — nguyên liệu này không liên quan hoặc không phù hợp

## Hướng dẫn chi tiết

**Flavor-enhancing** là những nguyên liệu:
- Thêm vào để tăng mùi thơm, vị đặc trưng (ví dụ: thì là với cá, quế với phở)
- Thường là gia vị phụ, rau thơm, nước chấm kèm
- KHÔNG phải thành phần chính đã có trong cột `core_ingredients`

**Ví dụ:**
- Món: Phở bò | Core: thịt bò, bánh phở, hành | Candidate: quế → **1** (tăng hương vị đặc trưng)
- Món: Phở bò | Core: thịt bò, bánh phở, hành | Candidate: đường → **0** (không thêm hương vị)
- Món: Cá kho | Core: cá, nước mắm | Candidate: gừng → **1** (khử tanh, tăng hương)
- Món: Cá kho | Core: cá, nước mắm | Candidate: bột mì → **0** (không liên quan)

## Lưu ý

- Không cần tra cứu công thức — đánh giá theo hiểu biết ẩm thực thực tế
- Nếu không chắc, để trống cột `notes` để ghi lý do
- Mỗi dish_id có thể xuất hiện nhiều lần (nhiều candidate khác nhau)
- Hai annotator làm ĐỘC LẬP, không trao đổi kết quả cho đến khi xong

## File

- `annotation_template.csv` — file cần điền
- Gửi lại file sau khi hoàn thành
