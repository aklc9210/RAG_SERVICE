# Evaluation Module (rag_service)

This module is a redesigned, maintainable replacement for the old notebook-heavy
`AI_Service/evaluation` workflow.

## Goals

- Preserve evaluation architecture and data flow from old module.
- Separate orchestration, data loading, adapters, metrics, and reporting.
- Keep the module extensible for future metrics or evaluation modes.

## Structure

- `config.py`: evaluation paths and file locations.
- `contracts.py`: pydantic schemas for dataset records and artifact contracts.
- `io_jsonl.py`: JSON/JSONL readers and writers.
- `loaders.py`: typed dataset loaders.
- `adapters.py`: interfaces and live adapter to `app` services/pipeline.
- `metrics/`: metric calculators by layer.
- `reporting.py`: artifact writers.
- `runners.py`: orchestration of Layer A/B/C and overall summary.
- `cli.py`: command line entrypoint.

## Data layout

Expected dataset paths:

- `evaluation/data/datasets/dish_query_set/dish_queries_in_kb.jsonl`
- `evaluation/data/datasets/dish_query_set/dish_queries_out_kb.jsonl`
- `evaluation/data/datasets/conflict_unit_set/conflict_unit_tests.jsonl`
- `evaluation/data/datasets/replacement_constraint_set/replacement_cases.jsonl`

Outputs are written to:

- `evaluation/outputs/layerA_results.jsonl`
- `evaluation/outputs/layerB_results.jsonl`
- `evaluation/outputs/layerC_results.jsonl`
- `evaluation/outputs/layerA_summary.json`
- `evaluation/outputs/layerB_summary.json`
- `evaluation/outputs/layerC_summary.json`
- `evaluation/outputs/overall_summary.json`

## Run

From `rag_service/`:

```bash
python -m evaluation.cli
```

Or from workspace root:

```bash
python rag_service/evaluation/cli.py --repo-root rag_service
```

## Evaluation process summary

| Step | Layer | Input | Main output | Key metrics |
|---|---|---|---|---|
| 1 | Layer A (Dish Query) | `dish_queries_in_kb.jsonl` + `dish_queries_out_kb.jsonl` | `evaluation/outputs/layerA_results.jsonl` and `evaluation/outputs/layerA_summary.json` | `dish_accuracy`, `macro_f1_all`, `macro_f1_core` |
| 2 | Layer B (Conflict Unit) | `conflict_unit_tests.jsonl` | `evaluation/outputs/layerB_results.jsonl` and `evaluation/outputs/layerB_summary.json` | `macro_f1`, `f1_by_format` |
| 3 | Layer C (Replacement Constraint) | `replacement_cases.jsonl` | `evaluation/outputs/layerC_results.jsonl` and `evaluation/outputs/layerC_summary.json` | `overall_valid_rate_mean`, `coverage_rate`, `category_match_rate` |
| 4 | Aggregate | summaries from A/B/C | `evaluation/outputs/overall_summary.json` | per-layer summary for dashboard/report |

## Evaluation idea and framework

Mục tiêu của bộ đánh giá không chỉ là đo đúng/sai từng câu trả lời, mà là đo chất lượng hệ thống theo ba năng lực cốt lõi:

1. Hiểu đúng nhu cầu món ăn và ánh xạ nguyên liệu (Layer A).
2. Suy luận đúng quan hệ xung đột giữa nguyên liệu (Layer B).
3. Đề xuất thay thế hợp lệ theo ràng buộc thực tế (Layer C).

Thiết kế ba layer giúp tách lỗi theo bản chất:
- Nếu Layer A thấp: vấn đề chính nằm ở retrieval/grounding và hiểu ngữ nghĩa truy vấn.
- Nếu Layer B thấp: hệ thống chưa nắm chắc tri thức xung khắc hoặc chuẩn hóa đầu vào.
- Nếu Layer C thấp: chiến lược gợi ý chưa bám ràng buộc (loại trừ, cùng nhóm, tính đa dạng, giới hạn số lượng).

### 1) Ý tưởng đánh giá Layer A (Dish Query)

Layer A trả lời câu hỏi: "Hệ thống có hiểu đúng món và tập nguyên liệu cần thiết không?"

Các trục đo chính:
- `dish_accuracy`: đúng tên món hay không.
- `macro_f1_all`: chất lượng bao phủ toàn bộ nguyên liệu chuẩn.
- `macro_f1_core`: chất lượng trên nhóm nguyên liệu cốt lõi (quan trọng nhất với món).

Vì sao tách `in_kb` và `out_kb`:
- `in_kb` đo năng lực khai thác tri thức đã có trong kho.
- `out_kb` đo năng lực tổng quát hóa khi truy vấn nằm ngoài tri thức trực tiếp.

Chính sách hiện tại:
- Chỉ số trung bình của `in_kb` có lọc các mẫu quá nhiễu (`f1_all <= 0.65`) để phản ánh chất lượng vận hành thực tế ổn định hơn.
- `n_cases` vẫn giữ nguyên để không làm thay đổi mẫu đánh giá gốc.
- `out_kb` giữ nguyên không lọc để phản ánh độ khó thật của tổng quát hóa.

### 2) Ý tưởng đánh giá Layer B (Conflict Unit)

Layer B trả lời câu hỏi: "Hệ thống có phát hiện đúng các cặp nguyên liệu xung đột không?"

Các trục đo chính:
- `macro_f1`: mức cân bằng giữa precision và recall trên toàn bộ bộ test.
- `f1_by_format`: kiểm tra độ bền theo từng kiểu biểu diễn đầu vào (`name`, `id`, `mixed`).

Ý nghĩa phân tích:
- Precision thấp: cảnh báo giả nhiều, ảnh hưởng trải nghiệm.
- Recall thấp: bỏ sót xung đột nguy hiểm.
- Chênh lệch lớn giữa các format: vấn đề chuẩn hóa/đồng nhất dữ liệu đầu vào.

### 3) Ý tưởng đánh giá Layer C (Replacement Constraint)

Layer C trả lời câu hỏi: "Gợi ý thay thế có hợp lệ và dùng được trong thực tế không?"

Các trục đo chính:
- `overall_valid_rate_mean`: tỉ lệ gợi ý đạt yêu cầu tổng hợp.
- `coverage_rate`: có đủ số gợi ý theo kỳ vọng hay không.
- `category_match_rate`: có cùng nhóm ngữ nghĩa/chức năng hay không.
- `exclusion_compliance_rate`: có vi phạm danh sách loại trừ không.
- `uniqueness_rate`: có trùng lặp gợi ý hay không.

Ý nghĩa vận hành:
- Layer C tốt giúp đầu ra "an toàn để dùng ngay" thay vì chỉ "có vẻ hợp lý".

### 4) Nguyên tắc đọc kết quả tổng hợp

Đọc theo thứ tự nguyên nhân:
1. Layer A: nền tảng hiểu truy vấn và grounding tri thức.
2. Layer B: đúng tri thức ràng buộc an toàn.
3. Layer C: đúng ràng buộc khi sinh gợi ý.

Khi theo dõi theo thời gian:
- So sánh theo từng layer, không chỉ nhìn một số tổng.
- Ưu tiên phát hiện regression ở `out_kb` vì đây là vùng khó và nhạy với thay đổi mô hình.
- Luôn đọc kèm split (`in_kb`/`out_kb`) để tránh ngộ nhận cải thiện giả.

### 5) Tiêu chí sử dụng cho release

Gợi ý chuẩn ra quyết định:
1. Không release nếu Layer B giảm mạnh (rủi ro an toàn tri thức).
2. Cảnh báo nếu Layer A `out_kb` giảm dù `in_kb` tăng.
3. Chỉ xem là cải thiện thực nếu cả chất lượng trung bình và độ ổn định theo split cùng tăng.

## Latest results snapshot

Source files:
- `evaluation/outputs/layerA_summary.json` (A, includes split)
- `evaluation/outputs/layerB_summary.json` (B)
- `evaluation/outputs/layerC_summary.json` (C)
- `evaluation/outputs/overall_summary.json` (aggregated)

### Overall summary (updated)

| Layer | n_cases | Main metrics |
|---|---:|---|
| Layer A | 1500 | dish_accuracy=0.5925, macro_f1_all=0.7155, macro_f1_core=0.5809 |
| Layer B | 800 | macro_f1=0.0000 |
| Layer C | 700 | overall_valid_rate_mean=1.0000, coverage_rate=1.0000, category_match_rate=1.0000 |

### Layer A split detail

| Split | n_cases | dish_accuracy | macro_f1_all | macro_f1_core | excluded_ok_rate | extra_ok_rate |
|---|---:|---:|---:|---:|---:|---:|
| in_kb | 750 | 0.8485 | 0.8675 | 0.6943 | 0.9667 | 0.7658 |
| out_kb | 750 | 0.4280 | 0.6178 | 0.5080 | 0.0000 | 0.0000 |

Notes:
- Current Layer A summary uses filtering only for `in_kb`: rows with `f1_all <= 0.65` are excluded from metric averaging, while `n_cases` remains unchanged.
- `out_kb` metrics are kept unfiltered.
