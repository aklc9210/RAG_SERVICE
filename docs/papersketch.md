Paper Skeleton — IEEE Conference Format (6 pages)
Format giả định: IEEE conference template, 2-column, 10pt Times, ~900 words/page → ~5,400 words tổng. Trừ refs + figures → ~4,200 words cho body.
Tựa đề (gợi ý)

"Ontology-Augmented Retrieval for Vietnamese Culinary Knowledge: A Hierarchy-Aware Approach to Dish Retrieval, Ingredient Substitution, and Related-Dish Recommendation"

Thay thế nếu muốn ngắn hơn: "Ontology-Augmented RAG for Vietnamese Food Information Retrieval"

Abstract (~180 words, trước Section I)
4 moves:

Gap — RAG hoạt động ở lexical/embedding level, không khai thác được semantic hierarchy và typed relations giữa ingredients/dishes, đặc biệt khó với class-level queries tiếng Việt ("món protein thực vật", "món không hải sản").
Contribution — Đề xuất ontology 4 tầng (ingredients) + 2 trục (dishes) với 7 named relations, tích hợp vào RAG qua query expansion, substitution reasoning, và hierarchy-aware similarity.
Evaluation — 3 tasks trên ~10K Vietnamese dishes: class-based retrieval (200 queries), constrained substitution (100 cases, LLM-judge GT), related-dish recommendation (200 dishes). 5-variant ablation isolating ontology components.
Results — Placeholder numbers: "RAG+Ontology đạt nDCG@10 = X.XX vs RAG-only X.XX (+Δ%, p<0.05)". Ablation cho thấy hierarchy và relations đóng góp độc lập.


I. Introduction (~450 words, ~0.5 trang)
Mục tiêu narrative: dẫn từ vấn đề thực tế → hạn chế của RAG thuần → ontology là câu trả lời.
Paragraph 1 — Motivation (~120w). Vietnamese culinary domain: ~10K dishes, ingredient diversity cao, nhiều class-level queries tự nhiên mà user hay hỏi ("món chay", "món không hải sản cho bé"). RAG thuần dựa vào lexical/embedding similarity không hiểu được "đậu hũ là protein thực vật".
Paragraph 2 — Limitations of plain RAG (~100w). Ba failure modes cụ thể sẽ lặp lại xuyên suốt paper:

(i) Class-level queries → RAG không expand "protein thực vật" → {đậu hũ, đậu phộng, ...}
(ii) Substitution dưới constraint → cần typed relation substitutes(A, B, context) + filter theo hierarchy
(iii) Related-dish → Jaccard trên bag-of-ingredients không phân biệt "thay thịt bò bằng thịt gà" (cùng AnimalProtein) với "thay thịt bò bằng đậu hũ" (khác nhánh).

Paragraph 3 — Our approach (~120w). Xây ontology từ chính dataset (bottom-up curation + automated relation derivation), tích hợp vào pipeline tại 3 điểm: query expansion, substitution reasoning, similarity scoring.
Paragraph 4 — Contributions (bullet list ~110w).

Ontology tiếng Việt cho food domain: 4-level ingredient hierarchy, 2-axis dish taxonomy, 7 named relations (Table I placeholder).
3 evaluation tasks được thiết kế để isolate ontology contribution (không chỉ test retrieval tổng thể).
5-variant ablation (V0–V4) chứng minh hierarchy, relations, inference rules có đóng góp độc lập.
Public release: ontology JSON + benchmark queries + GT.

Cuối intro: "The remainder is organized as follows: §II reviews related work; §III describes ontology construction; §IV defines the three tasks; §V details experimental setup; §VI presents results; §VII discusses limitations."

II. Related Work (~400 words, ~0.4 trang)
Chia làm 3 sub-paragraphs (không cần subsection headers để tiết kiệm chỗ):
A. RAG for domain-specific retrieval (~130w). Lewis et al. 2020 (RAG gốc), các work về RAG cho legal/medical. Gap: ít work xử lý class-level/constraint queries.
B. Ontology-based IR and food ontologies (~150w). FoodOn, AGROVOC, Hummel et al. Recipe1M. Gap: hầu hết là English, ít work tích hợp ontology với neural retrieval trong low-resource language như Vietnamese.
C. Ingredient substitution and similarity (~120w). Flavor Network (Ahn et al. 2011) — PMI-based; Recipe substitution work (Shirai et al.). Gap: substitution thường không có constraint-aware filtering; dish similarity thường flat Jaccard.
Kết luận mini-section: "Our work differs in three ways: (1) Vietnamese-specific ontology curated from a 10K-dish dataset, (2) unified framework covering retrieval/substitution/similarity, (3) explicit ablation isolating hierarchy vs relations vs inference."

III. Methodology — Ontology Construction & Integration (~900 words, ~1.0 trang)
Đây là section dài nhất và quan trọng nhất. Chia 3 subsections.
A. Formal Definition (~200w)
Định nghĩa T-box / A-box theo chuẩn description logic (ngắn gọn):

T-box (schema): classes C = {Protein, Produce, Seasoning, Staple, ...}, relation signatures.
A-box (instances): ingredient instances, dish instances, assertions.
Ontology O = (C, R, I, A) với C = classes, R = relations, I = instances, A = assertions.
Liệt kê 7 relations trong Table I (copy từ Appendix plan của bạn).

Table I placement: Đặt ngay đầu Section III. Columns: Relation | Signature | Derivation | Source.
B. Ingredient Hierarchy & Dish Taxonomy (~300w)

4-level ingredient hierarchy (mô tả bằng prose + Fig. 1 tree diagram).
Curation process: manual top 500 ingredients → spot-check 50 random → fallback Other_<category> cho tail.
Dish taxonomy 2 axes: byType (MonNuoc, MonKho, ...) × byMethod (Boil, Fry, ...). 25 categories.
Fig. 1 placement: Ontology structure (hierarchy tree, simplified to top 3 levels để fit column width).

C. Relation Derivation (~200w)
Mỗi relation 1-2 câu:

substitutes(A, B, context) — dish-name token-diff heuristic.
flavorComplements(A, B) — NPMI > 0.3 trong same parent class.
conflictsWith — reuse existing rules.
cookedBy(dish, method) — pattern match trên dish name.

D. Ontology Integration with RAG (~200w)
Mô tả 3 injection points (quan trọng — đây là novelty):

Query expansion (Task 1): "món X" → descendants(X) ∪ synonyms.
Substitution reasoning (Task 2): lookup substitutes → filter by constraint via hierarchy → rank by flavorComplements với rest-of-dish.
Hierarchy-aware similarity (Task 3): Sim(A,B) = α·IDF-Jaccard + β·ClassOverlap + γ·CookingMethodMatch.

Fig. 2 placement: Pipeline diagram showing RAG + Ontology fusion, với 3 điểm injection.

IV. Task Definitions (~500 words, ~0.55 trang)
Mỗi task 1 paragraph theo cùng template: (a) motivation, (b) input/output, (c) GT construction, (d) metrics.
A. Task 1: Class-Based Dish Retrieval (~170w)

Input: NL query có class reference ("món protein thực vật", "món không hải sản").
Output: ranked list of dish IDs.
GT: 200 queries (50 multi-class + 50 negation + 50 cooking-method + 50 region-like); dish được label positive nếu main_ingredient ∈ descendants(target_class).
Validation: manual check 20 random queries.
Metrics: nDCG@10, MRR@10, Recall@10.

B. Task 2: Constrained Ingredient Substitution (~170w)
sửa đim
Input: (dish, target_ingredient, constraint) — ví dụ (Phở bò, thịt bò, vegetarian).
Output: top-k candidate substitutes, ranked.
GT: 100 cases via LLM-judge (mean score across 4 judges: qwen/llama/gemma/mistral) với rubric 0/1/2.
Metrics: Precision@5, F1@5, Avg LLM-judge score.
Phải đề cập IAA giữa các judges (Fleiss' κ hoặc Krippendorff's α).

C. Task 3: Related Dish Recommendation (~160w)

Input: dish ID.
Output: ranked list of related dishes.
GT: extend existing 200-dish LLM-judge subset với hierarchy-aware relevance labels.
Metrics: Precision@5, Recall@5, và có thể thêm nDCG@5.


V. Experimental Setup (~350 words, ~0.4 trang)
A. Dataset (~80w)
~10K Vietnamese dishes, fields: name, ingredient list, category, region. 80/20 train/test split. Size thống kê của ontology: X classes, Y relations, Z assertions (điền sau khi build xong).
B. Baselines & Ablation Variants (~140w)
Table II placement: Ablation design.
VariantComponentsV0RAG-only (dense retrieval, no ontology)V1+ flat KB (ingredient lookup, no hierarchy)V2+ hierarchy (query expansion via ancestors/descendants)V3+ typed relations (substitutes, complements)V4+ inference rules (full ontology)
Thêm baseline BM25 làm lower bound.
C. Implementation Details (~80w)

Dense retrieval model (cần pick — Vietnamese SBERT? multilingual-E5?).
RAG setup, top-k = 50, rerank to 10.
Hardware, runtime.

D. Statistical Testing (~50w)
Paired Wilcoxon V0 ↔ V4 per metric, bootstrap 95% CI với n=1000 resamples.

VI. Results & Discussion (~900 words, ~1.0 trang)
A. Main Results (~200w)
Table III placement: Main comparison table — 3 tasks × 3 systems (BM25 / RAG-only / RAG+Ontology-full). Một row per metric per task. Bold best, underline runner-up.
Narrative: "RAG+Ontology outperforms RAG-only on Task 1 by Δ nDCG@10 (p<0.05), với gain lớn nhất ở negation queries (Δ=X) và multi-class queries (Δ=Y)."
B. Ablation Study (~250w)
Table IV placement: Ablation 5 variants × 3 tasks.
Fig. 3 placement: Bar chart visualizing ablation (nDCG@10 cho Task 1, F1@5 cho Task 2, P@5 cho Task 3, grouped by variant).
Key claims structure:

V0→V1 (add flat KB): gain nhỏ, chứng minh ontology structure > flat lookup.
V1→V2 (add hierarchy): lớn nhất cho Task 1 (class expansion quan trọng).
V2→V3 (add relations): lớn nhất cho Task 2 (substitutes relation cần thiết).
V3→V4 (add inference): incremental, nhưng positive.

C. Error Analysis (~250w)
Từ 60 failure cases (20/task) trong plan Day 5:

Task 1: hierarchy miss (X%), expansion over-broad (Y%), region mismatch (Z%).
Task 2: constraint violation leak (X%), flavor rank sai (Y%).
Task 3: rare ingredient class chưa có trong hierarchy (X%).

Insight-driven: ví dụ cụ thể 1-2 case Vietnamese dish (Phở, Bún bò Huế hoặc 2 case study bạn đã chuẩn bị) để illustrate.
D. Qualitative Case Studies (~200w)
Nếu còn chỗ: 2 Vietnamese dish case studies bạn đã có sẵn. Mỗi case: query → RAG output → RAG+Ontology output → diff analysis.

VII. Limitations & Future Work (~200 words, ~0.2 trang)
Bắt buộc có để credible:

Ontology curation thủ công cho top 500 ingredients; tail coverage kém.
LLM-judge GT có bias; IAA κ = X (báo cáo con số thật).
Single language (Vietnamese); cross-lingual chưa test.
Dish taxonomy chỉ 2 axes; có thể mở rộng sang nutrition, origin, occasion.
Substitution context-awareness còn coarse (dish category level, không phải per-recipe).


VIII. Conclusion (~150 words, ~0.15 trang)
Recap 3 moves: (1) ontology construction, (2) 3-task evaluation, (3) ablation kết quả. Kết câu: "Ontology cung cấp structured semantics mà RAG thuần không có; contribution là isolated và reproducible."

References (~0.8 trang, ~20–25 refs)
Buckets gợi ý:

RAG & neural retrieval: 4-5 refs (Lewis 2020, DPR, ColBERT, E5).
Ontology & knowledge graphs: 4-5 refs (FoodOn, DBpedia, OWL spec).
Food computing: 4-5 refs (Flavor Network, Recipe1M, food substitution papers).
Vietnamese NLP: 3-4 refs (PhoBERT, ViSoBERT, Vietnamese IR work).
Evaluation methodology: 2-3 refs (nDCG, bootstrap CI, LLM-as-judge).