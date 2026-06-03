# BẢN DỊCH TIẾNG VIỆT — TOÀN BỘ PAPER
*(Cập nhật theo phiên bản paper mới nhất)*

---

## TÓM TẮT (Abstract)

Các hệ thống truy xuất dày đặc (dense retrieval) dựa vào embedding để so khớp ngữ nghĩa. Tuy nhiên, trong lĩnh vực ẩm thực, sự liên quan thường phụ thuộc vào kiến thức nấu ăn có cấu trúc mà chỉ dùng embedding thì không nắm bắt được. Các truy vấn theo nhóm nguyên liệu và tìm món tương tự theo phân cấp — cả hai đều cần suy luận trên các nhóm nguyên liệu và các mối quan hệ có tên gọi.

Bài báo này đề xuất một framework truy xuất tăng cường bằng ontology cho truy xuất thông tin ẩm thực Việt Nam. Chúng tôi xây dựng cây phân cấp nguyên liệu 4 tầng (2.112 nguyên liệu, 49 nhóm, 24 nhóm lá), hệ phân loại món ăn theo 2 trục, và 6 quan hệ có tên gọi trên tập dữ liệu 10.741 món ăn Việt Nam. Ontology được tích hợp vào hệ thống truy xuất tại 2 điểm: (1) mở rộng truy vấn và (2) tính độ tương tự món ăn bằng hàm 5 thành phần (Jaccard có trọng số, trùng nhóm nguyên liệu, trùng cách nấu, tương tự ngữ nghĩa, tương thích hương vị).

Đánh giá trên 2 nhiệm vụ cho thấy cải thiện nhất quán so với cả baseline từ khóa lẫn truy xuất dày đặc: truy xuất theo nhóm cải thiện +50% NDCG@5 so với Dense; gợi ý món liên quan cho thấy các thành phần ontology chiếm 66% tín hiệu tương tự (trọng số tối ưu). Kết quả chứng minh kiến thức có cấu trúc bổ sung cho truy xuất nơ-ron khi sự liên quan phụ thuộc vào suy luận theo thành phần và theo nhóm.

---

## 1. GIỚI THIỆU (Introduction)

Truy xuất thông tin trong lĩnh vực ẩm thực đặt ra những thách thức vượt xa việc so khớp văn bản thông thường, bởi vì sự liên quan phụ thuộc vào thành phần nguyên liệu, ngữ cảnh chế biến, và nhiều sở thích tương tác của người dùng. Khó khăn này càng lớn hơn trong ẩm thực Việt Nam, nơi có sự biến đổi tên gọi theo vùng miền, phiên âm không chính thức, và đặt tên song ngữ tạo ra sự không khớp giữa truy vấn và công thức đã lập chỉ mục.

Các hệ thống truy xuất dày đặc cải thiện so khớp ngữ nghĩa so với phương pháp từ khóa bằng cách mã hóa truy vấn và tài liệu trong cùng không gian embedding, nhưng chỉ dùng truy xuất dày đặc thì gặp **2 lỗi lặp đi lặp lại** trong lĩnh vực ẩm thực:

1. **Truy vấn theo nhóm nguyên liệu**: Ví dụ "món protein thực vật" — không thể giải quyết nếu không có cơ chế phân cấp để mở rộng truy vấn thành danh sách các nguyên liệu con.
2. **Gợi ý món liên quan**: Tính trùng nguyên liệu bằng Jaccard phẳng không phân biệt thay thế cùng nhóm (bò → gà, cùng Protein Động Vật) với thay thế khác nhóm (bò → đậu hũ).

Ontology giải quyết các hạn chế này bằng cách mã hóa quan hệ cha-con (subClassOf), các quan hệ có tên (flavorComplements, conflictsWith, cookedBy), và quy tắc suy luận cho phép giải quyết truy vấn theo nhóm bằng cách duyệt cây tổ tiên-hậu duệ.

**Đóng góp của bài báo gồm 4 phần:**

1. Ontology ẩm thực Việt Nam trên ~10.000 món: cây phân cấp nguyên liệu 4 tầng, hệ phân loại món ăn theo 2 trục (byType × byMethod), và 6 quan hệ có tên.
2. Tích hợp ontology vào hệ thống truy xuất dày đặc tại 2 điểm: mở rộng truy vấn và tính điểm tương tự theo phân cấp.
3. Hai nhiệm vụ đánh giá tách biệt đóng góp của ontology: truy xuất theo nhóm (1.000 truy vấn) và gợi ý món liên quan (200 anchors với tập ứng viên đa dạng dùng cho tối ưu trọng số và ablation thành phần, đánh giá cuối trên tập test 25 anchors đã kiểm duyệt human), có báo cáo độ đồng thuận giữa người chấm cho cả hai nhiệm vụ.
4. So sánh 4 hệ thống với kiểm định thống kê, cung cấp bằng chứng trực tiếp cho đóng góp độc lập của phân cấp, quan hệ có kiểu, và quy tắc suy luận.

---

## 2. CÔNG TRÌNH LIÊN QUAN (Related Work)

### 2.1. Truy xuất dựa trên ontology và ontology thực phẩm

Truy xuất dựa trên ontology truyền thống làm giàu biểu diễn tài liệu và truy vấn bằng cấu trúc ngữ nghĩa rõ ràng, giảm sự không khớp từ vựng và cải thiện độ chính xác truy xuất. Trong lĩnh vực thực phẩm, FoodOn cung cấp ontology thực phẩm lớn cho truy xuất nguồn gốc và tích hợp dữ liệu; FoodKG liên kết công thức, nguyên liệu, và dinh dưỡng trong đồ thị tri thức dùng cho gợi ý có giải thích. Tuy nhiên, không nghiên cứu nào tích hợp ontology với hệ thống truy xuất nơ-ron hiện đại cho ngôn ngữ ít tài nguyên như tiếng Việt — đây là khoảng trống mà nghiên cứu này lấp đầy.

### 2.2. Truy xuất thực phẩm trong framework nơ-ron

Các benchmark gần đây như Recipe-MPR nêu bật khó khăn của truy xuất dựa trên nhiều thuộc tính sở thích. KERL cho thấy kiến thức thực phẩm có cấu trúc vẫn hữu ích ngay cả trong các pipeline có LLM hỗ trợ. Framework truy xuất nhận biết đồ thị gần đây chứng minh rằng cấu trúc quan hệ rõ ràng có thể bổ sung cho truy xuất thuần embedding trên các truy vấn tổ hợp.

### 2.3. Thay thế nguyên liệu và độ tương tự món ăn

Thay thế nguyên liệu đã được nghiên cứu qua cả đồ thị tri thức lẫn phương pháp học. Các baseline nhẹ thường tính tương tự từ trùng nguyên liệu phẳng, không phân biệt thay thế trong cùng nhóm ngữ nghĩa với khác biệt xuyên nhóm. Bài báo này vượt qua giới hạn đó bằng hàm tương tự nhận biết phân cấp kết hợp nhiều tín hiệu có cấu trúc.

### 2.4. Vị trí của nghiên cứu này

Nghiên cứu của chúng tôi kết nối ba hướng trên bằng cách: (1) xây dựng ontology đặc thù cho Việt Nam từ tập 10K món, (2) tích hợp vào hệ thống truy xuất dày đặc như cơ chế làm giàu trước embedding cho 2 tác vụ truy xuất thực phẩm, và (3) cung cấp ablation rõ ràng tách biệt đóng góp của phân cấp, quan hệ có kiểu, và quy tắc suy luận.

---

## 3. FRAMEWORK TRUY XUẤT TĂNG CƯỜNG BẰNG ONTOLOGY

### 3.1. Định nghĩa hình thức

Ontology thực phẩm được định nghĩa là bộ bốn O = (C, R, I, A), trong đó C là tập các nhóm (class) tổ chức thành cây có gốc (T-box), R là tập các loại quan hệ có tên, I là tập các thực thể cụ thể (nguyên liệu và món ăn — A-box), và A là tập các khẳng định liên kết thực thể với nhóm và với nhau. Phân cấp nhóm hỗ trợ quan hệ subClassOf: nếu c₁ ⊑ c₂ thì mọi thực thể của c₁ cũng là thực thể của c₂.

**Bảng: 6 quan hệ có tên trong ontology thực phẩm**

| Quan hệ | Chữ ký | Cách tạo | Số lượng |
|---|---|---|---|
| hasIngredient | món × nguyên liệu | Trực tiếp từ KB | 10.741 |
| mainIngredient | món × nguyên liệu | Độ quan trọng ≥ 3 | 10.741 |
| subClassOf | nhóm × nhóm | Thiết kế thủ công | 48 |
| flavorComplements | nguyên liệu × nguyên liệu | NPMI > 0.3 | 15.119 |
| conflictsWith | nguyên liệu × nguyên liệu | Quy tắc đã kiểm duyệt | 139 |
| cookedBy | món × phương pháp | Mẫu từ danh mục | 10.741 |

### 3.2. Cây phân cấp nguyên liệu và phân loại món ăn

**Cây phân cấp nguyên liệu:** 4 tầng, 49 nhóm (**39 nhóm lá**), bao phủ 2.112 nguyên liệu. Tầng 0: Ingredient (gốc). Tầng 1: 9 nhóm lớn (Protein, Produce, Seasoning, Staple, Dairy, Beverage, Sweet, Processed, Other). Tầng 2–3: phân biệt chi tiết hơn, ví dụ Protein → AnimalProtein → Seafood.

Cách xây dựng: (1) thiết kế thủ công cây nhóm dựa trên quy ước ẩm thực Việt Nam; (2) phân loại tự động mỗi nguyên liệu vào nhóm lá bằng LLM (Qwen-2.5 7B, temperature 0, batch 25), sau đó kiểm tra thủ công 100 nguyên liệu phổ biến nhất và kiểm tra ngẫu nhiên 50 mẫu. Nguyên liệu không phân loại được xếp vào nhóm "Other".

**Phân loại món ăn:** 2 trục vuông góc — byType (25 danh mục, ví dụ mon_canh, mon_kho, mon_xao) và byMethod (24 nhãn cách nấu, ví dụ Boil, Stew, StirFry, Grill). Tất cả 10.741 món đều được gán nhãn cách nấu.

### 3.3. Cách tạo các quan hệ

**flavorComplements (15.119 cặp):** Tính NPMI trên đồng xuất hiện nguyên liệu trong toàn bộ 10.741 món. Giữ tất cả cặp có NPMI > 0.3.

> NPMI(A, B) = log[P(A,B) / (P(A)·P(B))] / [-log P(A,B)]

**conflictsWith (139 cặp):** 139 quy tắc xung đột dinh dưỡng/y tế nhập từ cơ sở dữ liệu đã kiểm duyệt (nguồn: [aklc9210/RAG_SERVICE, ingredient_conflict.json](https://github.com/aklc9210/RAG_SERVICE/blob/main/app/data/conflict/ingredient_conflict.json)). Quan hệ này không đưa vào công thức tương tự món ăn (xung đột nguyên liệu trong một món không phản ánh sự khác biệt giữa hai món), phục vụ cho ứng dụng hạ nguồn như lập kế hoạch bữa ăn và kiểm tra an toàn công thức.

**cookedBy (10.741):** Ánh xạ từ trường danh mục món bằng bảng tra 25 mục.

### 3.4. Tích hợp Ontology vào hệ thống truy xuất dày đặc

Ontology được đưa vào pipeline tại 2 điểm:

**Điểm 1 — Mở rộng truy vấn (Nhiệm vụ 1):** Với truy vấn theo nhóm như "món protein thực vật", hệ thống ánh xạ thuật ngữ nhóm sang nút ontology, lấy tất cả tên nguyên liệu hậu duệ qua get_descendants, rồi thêm vào truy vấn gốc trước khi mã hóa thành vector. Truy vấn phủ định mở rộng nhóm dương và loại trừ các món khớp tại thời điểm truy xuất.

**Điểm 2 — Tính độ tương tự món ăn theo phân cấp (Nhiệm vụ 2):**

> Sim(A, B) = α·J + β·C + γ·M + δ·S + ε·F

Trong đó α, β, γ, δ, ε là trọng số (tổng = 1.0) xác định bằng 5-fold cross-validation:

- **J = WeightedJaccard(A, B):** Trùng nguyên liệu có trọng số vai trò (chính=3.0, phụ=1.5, gia vị=0.5). J = Σw(chung) / Σw(hợp).
- **C = WeightedClassOverlap(A, B):** Ghép cặp tham lam hai phía trên nhóm ontology. Mỗi cặp khớp được 1.0 (cùng nhóm lá) hoặc 0.5 (cùng nhóm cha), nhân trọng số vai trò, chuẩn hóa bằng tổng trọng số.
- **M = MethodMatch(A, B):** 1.0 nếu 2 món cùng cách nấu, 0.0 nếu khác.
- **S = SemanticSim(A, B):** Trung bình độ tương tự ngữ nghĩa theo cặp giữa nguyên liệu của A và B, từ ma trận embedding đã huấn luyện trước.
- **F = FlavorComplement(A, B):** Trung bình NPMI của các cặp nguyên liệu xuyên món có quan hệ flavorComplements. Trả về 0 nếu không có cặp complement nào.

---

## 4. ĐỊNH NGHĨA CÁC NHIỆM VỤ ĐÁNH GIÁ

Hai nhiệm vụ đánh giá dùng chung tập 10.741 món ăn Việt Nam và cùng ontology.

### Nhiệm vụ 1: Truy xuất món ăn theo nhóm (Class-Based Dish Retrieval)

**Tại sao cần?** Người dùng thường tìm theo nhóm như "tìm các món gỏi cá không cay" — ví dụ có nhóm (gỏi cá), phủ định (không cay). Truy xuất dày đặc không giải quyết được vì truy vấn không khớp từ ngữ với tên nguyên liệu cụ thể.

**Đầu vào/Đầu ra:** Đầu vào là truy vấn ngôn ngữ tự nhiên chứa tham chiếu nhóm nguyên liệu, có thể kèm phủ định hoặc ràng buộc cách nấu. Đầu ra là danh sách món xếp hạng.

### Nhiệm vụ 2: Gợi ý món ăn liên quan (Related-Dish Recommendation)

**Tại sao cần?** Jaccard phẳng coi mọi khác biệt nguyên liệu là như nhau, không phân biệt thay thế cùng nhóm (bò → gà, cùng AnimalProtein) với khác nhóm (bò → đậu hũ).

**Đầu vào/Đầu ra:** Đầu vào là mã món ăn (dish ID). Đầu ra là danh sách món liên quan xếp hạng.

---

## 5. THÍ NGHIỆM (Experiments)

### 5.1. Dữ liệu và ground truth

- **Tập dữ liệu:** 10.741 món ăn Việt Nam với các trường có cấu trúc.
- **Ontology:** 2.112 nguyên liệu, 49 nhóm (4 tầng, 39 nhóm lá), 6 quan hệ có tên.

**Nhiệm vụ 1:** 1.000 truy vấn, chia đều 4 loại (250 mỗi loại: đơn nhóm, đa nhóm, phủ định, cách nấu). Truy vấn sinh tự động từ 10 mẫu tiếng Việt, lấy mẫu ngẫu nhiên trên 24 nhóm lá và 10 cách nấu (seed 42). Nhãn sinh tự động qua API FoodOntology: món dương khi chứa ≥1 nguyên liệu từ mỗi nhóm dương, 0 nguyên liệu từ nhóm âm, và khớp cách nấu.

**Nhiệm vụ 2:** 200 món anchor, chọn phân tầng theo 25 danh mục. Mỗi anchor có 20 ứng viên từ 4 nguồn đa dạng: (1) top-5 Jaccard có trọng số IDF; (2) 5 từ khoảng giữa Jaccard (rank 10–20); (3) 5 cùng danh mục, Jaccard < 0.2; (4) 5 ngẫu nhiên. Tổng ~4.000 cặp.

### 5.2. Các hệ thống so sánh

Bốn hệ thống theo chuẩn sparse–dense:
1. **BM25:** So khớp từ khóa Okapi BM25.
2. **BM25+Expansion:** BM25 với mở rộng từ đồng nghĩa phẳng từ KB nguyên liệu (không dùng phân cấp).
3. **Dense:** Truy xuất dày đặc, embedding multilingual-e5-large (1024 chiều), Pinecone làm kho vector. Lập chỉ mục: tên_món (lặp 3×) + danh_mục + tên_nguyên_liệu (tiếng Việt).
4. **Dense+Ontology:** Framework đề xuất — tăng cường Dense bằng kiến thức có cấu trúc.

Nhiệm vụ 2 bổ sung ablation study 10 cấu hình để tách biệt đóng góp từng tín hiệu ontology.

### 5.3. Quy trình đánh giá

**Nhiệm vụ 1 — Kiểm chứng nhãn rule:**
Hai người gán nhãn độc lập đánh giá 500 cặp (truy vấn, món) ngẫu nhiên. Độ đồng thuận giữa hai người: Cohen's κ = 0.62 (đáng kể), đồng thuận chính xác 83.4%. Nhãn rule so với đồng thuận đa số của người: κ = 0.50 (F1 = 0.72, recall = 0.81). Bất đồng chủ yếu ở truy vấn đa nhóm (κ = 0.31); cách nấu (κ = 0.63) và phủ định (κ = 0.57) có đồng thuận cao.

**Nhiệm vụ 2 — Tạo ground truth hai bước:**

*Bước 1 — Chấm điểm LLM ban đầu:* Điểm trung bình từ 3 LLM judges (Llama-3.1 8B, Gemma-2 9B, Mistral 7B) trên thang 0/1/2. Panel đạt Fleiss' κ = 0.336 (đồng thuận khá), đồng thuận cặp 70–76%.

*Bước 2 — Kiểm tra và chỉnh sửa của human dựa trên ontology:* Toàn bộ nhãn LLM được kiểm tra thủ công theo 5 tiêu chí ontology rõ ràng: (1) cùng nhóm lá trong phân cấp; (2) trùng nhóm sibling ở tầng cha; (3) đồng thuận cách nấu (quan hệ cookedBy); (4) quan hệ bổ trợ hương vị (flavorComplements NPMI); (5) trọng số tầm quan trọng nguyên liệu. Điểm không nhất quán với các tín hiệu ontology — ví dụ LLM chấm 2 cho cặp chỉ chia sẻ gia vị ngẫu nhiên, hoặc chấm 0 cho cặp có protein cùng nhóm mạnh — bị đánh dấu và chỉnh sửa. Ngưỡng dương: mean ≥ 1.0.

*Kiểm chứng LLM bằng người:* Hai người gán nhãn độc lập chấm 504 cặp (84 anchors × 6 candidates). Độ đồng thuận giữa hai người: κ_linear = 0.50, đồng thuận chính xác 67.3%, đồng thuận lân cận 97.2%. Tương quan Spearman giữa đồng thuận người và điểm trung bình LLM: ρ = 0.56 (p < 10⁻⁴³). LLM có xu hướng cao hơn người +0.38. Khi nhị phân hóa tại ngưỡng ≥1, LLM đạt recall 95.9% các cặp mà người đánh giá là liên quan.

**Tối ưu hóa trọng số:**
Trọng số (α, β, γ, δ, ε) xác định bằng 5-fold cross-validation trên 200 anchors: mỗi fold tối ưu trên 160 anchors (Nelder-Mead, maximize Spearman), đánh giá trên 40 anchors. Trọng số cuối là trung bình 5 folds. Nhiệm vụ 1 không có siêu tham số cần điều chỉnh.

### 5.4. Kết quả

**Nhiệm vụ 1: Truy xuất theo nhóm** (1.000 truy vấn, top-5)

| Hệ thống | P@5 | NDCG@5 | MRR@5 |
|---|---|---|---|
| BM25 | 0.224 | 0.233 | 0.362 |
| BM25+Expansion | 0.288 | 0.288 | 0.393 |
| Dense | 0.366 | 0.366 | 0.495 |
| **Dense+Ontology** | **0.534** | **0.549** | **0.696** |

Dense+Ontology đạt P@5 = 0.534 và NDCG@5 = 0.549, vượt Dense +46% và +50%, vượt BM25 +139% và +136%. Cải thiện từ phân cấp ontology (+46% so với Dense) lớn hơn đáng kể so với mở rộng từ đồng nghĩa phẳng (+29% BM25+Expansion so với BM25), xác nhận mở rộng theo cấu trúc nhóm hiệu quả hơn rõ rệt so với tra cứu phẳng.

**Nhiệm vụ 2: Gợi ý món liên quan** (200 anchors, ~4.000 cặp, ground truth kiểm duyệt human)

*Ablation study — 10 cấu hình (5-fold CV, 200 anchors):*

| Cấu hình | P@5 | NDCG@5 | MRR@5 |
|---|---|---|---|
| A: Chỉ Jaccard | 0.741±.061 | 0.755±.053 | 0.855±.042 |
| B: +ClassOverlap | 0.796±.051 | 0.816±.038 | 0.905±.028 |
| C: +MethodMatch | 0.819±.054 | 0.844±.044 | 0.944±.032 |
| D: +SemanticSim | 0.819±.054 | 0.845±.043 | **0.948±.029** |
| **E: Đầy đủ (cả 5)** | **0.825±.047** | **0.849±.040** | 0.937±.029 |
| F: Không Jaccard | 0.815±.041 | 0.835±.033 | 0.923±.023 |
| G: Không ClassOverlap | 0.812±.043 | 0.830±.038 | 0.913±.028 |
| H: Không MethodMatch | 0.794±.045 | 0.811±.036 | 0.903±.036 |
| I: Không SemanticSim | **0.825±.047** | 0.848±.040 | 0.936±.030 |
| J: Không Flavor | 0.819±.054 | 0.845±.043 | **0.948±.029** |

**Trọng số tối ưu:** α=0.34, β=0.17, γ=0.12, δ=0.19, ε=0.18. Các thành phần ontology (β+γ+δ+ε = 0.66) chiếm **66%** tín hiệu tương tự.

*So sánh hệ thống (25 anchors, 500 cặp, ground truth kiểm duyệt human):*

| Hệ thống | P@5 | NDCG@5 | MRR@5 |
|---|---|---|---|
| BM25 | 0.792 | 0.827 | 0.920 |
| BM25+Expansion | 0.744 | 0.783 | 0.920 |
| Dense | 0.848 | 0.863 | 0.913 |
| **Dense+Ontology** | **0.872** | **0.901** | **0.980** |

Dense+Ontology đạt P@5=0.872, NDCG@5=0.901, MRR@5=0.980. BM25+Expansion thấp hơn BM25 (−6.1% P@5) — mở rộng từ đồng nghĩa phẳng gây nhiễu khi truy vấn là tên món cụ thể. Dense cải thiện +7.1% P@5 so với BM25. Dense+Ontology thêm +2.8% P@5 và +4.4% NDCG@5 so với Dense. MRR@5 đạt 0.980 (+6.7% so với Dense) xác nhận hệ thống đặt món liên quan nhất vào đầu bảng xếp hạng đáng tin cậy hơn.

### 5.5. Phân tích

**Nhiệm vụ 1:** Dense+Ontology cải thiện NDCG@5 +50% và MRR@5 +41% so với Dense. Mở rộng phân cấp đóng góp nhiều hơn đáng kể so với mở rộng từ đồng nghĩa phẳng (+29%).

**Nhiệm vụ 2:** Ablation cho thấy đóng góp rõ ràng từng thành phần. Từ Jaccard-only (P@5=0.741): thêm ClassOverlap +7.4%, MethodMatch +2.9%, FlavorComplement +0.7% P@5. Config F (Không Jaccard) vẫn đạt P@5=0.815 — tín hiệu ontology đủ mạnh ngay cả không cần ingredient matching trực tiếp. Bỏ MethodMatch gây giảm lớn nhất (−3.1% P@5) — đồng thuận cách nấu là tín hiệu phân biệt nhất cho độ liên quan.

FlavorComplement từ thống kê NPMI nắm bắt hồ sơ hương vị bổ sung mà trùng nguyên liệu thuần túy bỏ sót. Hơn 51% cặp món có ít nhất một quan hệ complement, bộ tối ưu gán trọng số có ý nghĩa (ε = 0.18).

---

## 6. KẾT LUẬN (Conclusion)

Bài báo trình bày framework truy xuất tăng cường bằng ontology cho truy xuất thông tin ẩm thực Việt Nam. Chúng tôi xây dựng cây phân cấp nguyên liệu 4 tầng (2.112 nguyên liệu, 49 nhóm), hệ phân loại món ăn theo 2 trục, và 6 quan hệ có tên từ tập 10.741 món. Ontology được tích hợp tại 2 điểm: mở rộng truy vấn và tính tương tự món ăn theo phân cấp.

Đánh giá trên 2 nhiệm vụ cho thấy cấu trúc ontology mang lại cải thiện nhất quán:
- **Truy xuất theo nhóm:** Dense+Ontology cải thiện NDCG@5 +50% và MRR@5 +41% so với Dense, mở rộng phân cấp đóng góp nhiều hơn tra cứu từ đồng nghĩa phẳng.
- **Gợi ý món liên quan:** Ablation trên tập test đa dạng xác định đóng góp độc lập: ClassOverlap (+7.4% P@5), MethodMatch (+2.9%), FlavorComplement (+0.7%), trọng số tối ưu gán 66% cho các thành phần ontology.

Kết quả chứng minh kiến thức ngữ nghĩa có cấu trúc, được mã hóa dưới dạng ontology với quan hệ có kiểu và phân cấp nhóm, bổ sung cho truy xuất nơ-ron trong lĩnh vực mà sự liên quan phụ thuộc vào suy luận theo thành phần và theo nhóm chứ không chỉ trùng từ ngữ.

---

## BẢNG THUẬT NGỮ

| Thuật ngữ tiếng Anh | Tiếng Việt | Giải thích |
|---|---|---|
| Dense retrieval | Truy xuất dày đặc | Tìm kiếm bằng so sánh vector embedding |
| Ontology | Hệ thống phân loại tri thức | Cấu trúc tổ chức kiến thức theo nhóm, quan hệ cha-con, mối liên hệ có tên |
| subClassOf | Là con của | Quan hệ phân cấp: mọi thực thể của lớp con cũng là thực thể của lớp cha |
| flavorComplements | Bổ trợ hương vị | Hai nguyên liệu thường xuất hiện cùng nhau (NPMI > 0.3) |
| conflictsWith | Xung đột với | Hai nguyên liệu không nên dùng chung (quy tắc dinh dưỡng/y tế) |
| cookedBy | Nấu bằng | Quan hệ món ăn — phương pháp nấu (StirFry, Boil, Grill, v.v.) |
| Jaccard | Trùng tập hợp Jaccard | Số phần tử chung / tổng số phần tử |
| NPMI | Thông tin tương hỗ điểm chuẩn hóa | Đo mức độ đồng xuất hiện (1=luôn cùng, 0=độc lập) |
| NDCG | Độ lợi tích lũy chiết khấu chuẩn hóa | Chỉ số xếp hạng, ưu tiên kết quả đúng ở vị trí cao |
| P@k | Precision tại top k | Tỷ lệ kết quả đúng trong k kết quả đầu |
| MRR | Hạng nghịch đảo trung bình | Trung bình 1/vị_trí_kết_quả_đúng_đầu_tiên |
| Ablation study | Thí nghiệm loại bỏ thành phần | Tắt từng phần để đo đóng góp của mỗi thành phần |
| Ground truth | Đáp án đúng | Tập nhãn chuẩn dùng để đánh giá hệ thống |
| Human-reviewed GT | Đáp án đúng có kiểm duyệt người | Nhãn LLM đã qua kiểm tra và chỉnh sửa thủ công theo tiêu chí ontology |
| Cohen's κ | Hệ số đồng thuận Cohen | Đo mức độ 2 người chấm đồng ý (0=ngẫu nhiên, 1=hoàn toàn đồng ý) |
| Fleiss' κ | Hệ số đồng thuận Fleiss | Đo mức độ ≥3 người chấm đồng ý |
| Spearman ρ | Tương quan xếp hạng Spearman | Mức độ 2 bảng xếp hạng giống nhau |
| Nelder-Mead | Nelder-Mead | Thuật toán tối ưu không gradient |
| 5-fold CV | Cross-validation 5 fold | Đánh giá chéo 5 lần để ước lượng hiệu năng tổng quát |
