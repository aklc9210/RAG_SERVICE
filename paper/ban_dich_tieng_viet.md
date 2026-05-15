# BẢN DỊCH TIẾNG VIỆT — TOÀN BỘ PAPER

---

## TÓM TẮT (Abstract)

Các hệ thống truy xuất dày đặc (dense retrieval) dựa vào embedding (biểu diễn vector) để so khớp ngữ nghĩa. Tuy nhiên, trong lĩnh vực ẩm thực, sự liên quan thường phụ thuộc vào kiến thức nấu ăn có cấu trúc mà chỉ dùng embedding thì không nắm bắt được. Các truy vấn theo nhóm nguyên liệu và tìm món tương tự theo phân cấp — cả hai đều cần suy luận trên các nhóm nguyên liệu và các mối quan hệ có tên gọi.

Bài báo này đề xuất một framework truy xuất tăng cường bằng ontology (hệ thống phân loại tri thức) cho truy xuất thông tin ẩm thực Việt Nam. Chúng tôi xây dựng:
- Cây phân cấp nguyên liệu 4 tầng (2.112 nguyên liệu, 49 nhóm)
- Hệ phân loại món ăn theo 2 trục
- 7 loại quan hệ có tên gọi, trên tập dữ liệu 10.741 món ăn Việt Nam

Ontology được tích hợp vào hệ thống truy xuất tại 2 điểm:
1. **Mở rộng truy vấn** bằng cách lấy tất cả nguyên liệu con của một nhóm
2. **Tính độ tương tự món ăn** bằng hàm 4 thành phần: trùng nguyên liệu (Jaccard), trùng nhóm nguyên liệu, trùng cách nấu, và tương tự ngữ nghĩa

Đánh giá trên 2 nhiệm vụ cho thấy cải thiện nhất quán:
- Truy xuất theo nhóm: cải thiện +37% NDCG@20 so với chỉ dùng truy xuất dày đặc
- Gợi ý món liên quan: đạt Spearman ρ = 0.70, trong đó các thành phần ontology chiếm 60% tín hiệu tương tự

Kết quả chứng minh rằng kiến thức có cấu trúc (ontology) bổ sung cho truy xuất bằng mạng nơ-ron khi sự liên quan phụ thuộc vào suy luận theo thành phần và theo nhóm.

---

## 1. GIỚI THIỆU (Introduction)

Truy xuất thông tin trong lĩnh vực ẩm thực đặt ra những thách thức vượt xa việc so khớp văn bản thông thường, bởi vì sự liên quan phụ thuộc vào kiến thức nấu ăn có cấu trúc — thành phần nguyên liệu, phân cấp nhóm, cách chế biến, và sự tương hợp hương vị — chứ không chỉ là trùng từ ngữ. Khó khăn này càng lớn hơn trong ẩm thực Việt Nam, nơi có sự biến đổi dấu thanh, đặt tên song ngữ, và đa dạng vùng miền kết hợp với vốn từ vựng nguyên liệu rất lớn.

Các hệ thống truy xuất dày đặc cải thiện so khớp ngữ nghĩa so với phương pháp từ khóa bằng cách mã hóa truy vấn và tài liệu trong cùng không gian embedding, nhưng chỉ dùng truy xuất dày đặc thì gặp **2 lỗi lặp đi lặp lại** trong lĩnh vực ẩm thực:

1. **Truy vấn theo nhóm nguyên liệu**: Ví dụ "món protein thực vật" — không thể giải quyết nếu không có cơ chế phân cấp để mở rộng truy vấn thành danh sách các nguyên liệu con. Hệ thống tìm kiếm thông thường không hiểu "protein thực vật" bao gồm đậu hũ, đậu nành, nấm, v.v.

2. **Gợi ý món liên quan**: Tính trùng nguyên liệu bằng Jaccard thông thường không phân biệt được thay thế cùng nhóm (bò → gà, cùng nhóm Protein Động Vật) với thay thế khác nhóm (bò → đậu hũ).

Ontology (hệ thống phân loại tri thức) giải quyết các hạn chế này bằng cách mã hóa:
- Quan hệ **cha-con** giữa các nhóm (ví dụ: Hải Sản là con của Protein Động Vật)
- Các **quan hệ có tên** (thay thế được, bổ sung hương vị, nấu bằng cách nào)
- **Quy tắc suy luận** cho phép giải quyết truy vấn theo nhóm bằng cách duyệt cây tổ tiên-hậu duệ

**Đóng góp của bài báo gồm 4 phần:**

1. Xây dựng ontology ẩm thực Việt Nam trên ~10.000 món, gồm cây phân cấp nguyên liệu 4 tầng, hệ phân loại món ăn theo 2 trục (loại món × cách nấu), và 7 quan hệ có tên.

2. Tích hợp ontology vào hệ thống truy xuất dày đặc tại 2 điểm: mở rộng truy vấn và tính điểm tương tự theo phân cấp.

3. Hai nhiệm vụ đánh giá tách biệt đóng góp của ontology: truy xuất theo nhóm (200 truy vấn) và gợi ý món liên quan (2.148 món, ~4.000 cặp có nhãn LLM judge), có báo cáo độ đồng thuận giữa người chấm.

4. So sánh 4 hệ thống với kiểm định thống kê ghép cặp, cung cấp bằng chứng trực tiếp cho đóng góp độc lập của phân cấp, quan hệ có kiểu, và quy tắc suy luận.

---

## 2. CÔNG TRÌNH LIÊN QUAN (Related Work)

### 2.1. Truy xuất dựa trên ontology và ontology thực phẩm

Truy xuất dựa trên ontology truyền thống làm giàu biểu diễn tài liệu và truy vấn bằng cấu trúc ngữ nghĩa rõ ràng. Các nghiên cứu trước đây cho thấy biểu diễn ở mức khái niệm giảm sự không khớp từ vựng và cải thiện độ chính xác truy xuất.

Trong lĩnh vực thực phẩm:
- **FoodOn** cung cấp ontology thực phẩm lớn cho truy xuất nguồn gốc và tích hợp dữ liệu
- **FoodKG** liên kết công thức, nguyên liệu, và dinh dưỡng trong đồ thị tri thức dùng cho gợi ý có giải thích
- Chen và cộng sự xây dựng hệ gợi ý thực phẩm cá nhân hóa dưới dạng hỏi đáp có ràng buộc trên đồ thị tri thức

Tuy nhiên, các nghiên cứu về thực phẩm nhắm vào gợi ý hoặc hỏi đáp chứ không phải truy xuất xếp hạng, và các nghiên cứu ontology-IR truyền thống ra đời trước truy xuất dày đặc. Không nghiên cứu nào tích hợp ontology với hệ thống truy xuất nơ-ron hiện đại, đặc biệt cho ngôn ngữ ít tài nguyên như tiếng Việt.

### 2.2. Truy xuất thực phẩm trong framework nơ-ron

Các nghiên cứu gần đây coi tìm kiếm thực phẩm là bài toán truy xuất trong hệ thống nơ-ron:
- **Recipe-MPR** đánh giá truy xuất công thức theo nhiều khía cạnh sở thích
- Hu và cộng sự đề xuất framework truy xuất công thức xuyên văn hóa
- **KERL** tích hợp đồ thị tri thức thực phẩm với mô hình ngôn ngữ lớn (LLM)

Trong khi đó, các hệ thống truy xuất dày đặc đã trở thành mô hình chủ đạo cho các tác vụ cần nhiều kiến thức, nhưng phân tích các lỗi của truy xuất dày đặc cho thấy nó gặp khó khăn với truy vấn theo nhóm và truy vấn kết hợp cần suy luận có cấu trúc. Không nghiên cứu nào đặt ontology làm trung tâm của hệ thống truy xuất như cơ chế làm giàu trước khi embedding cho truy vấn thực phẩm.

### 2.3. Độ tương tự món ăn

Độ tương tự món ăn thường tính bằng Jaccard phẳng trên túi nguyên liệu mà không phân biệt khác biệt cùng nhóm với khác nhóm. **FlavorGraph** xây dựng đồ thị thực phẩm-hóa học quy mô lớn nắm bắt sự tương hợp hương vị, nhưng vẫn chưa tích hợp phân cấp nhóm vào hàm tính tương tự.

### 2.4. Vị trí của nghiên cứu này

Nghiên cứu của chúng tôi kết nối các hướng trên bằng cách: (1) xây dựng ontology đặc thù cho Việt Nam từ tập 10K món, (2) tích hợp vào hệ thống truy xuất dày đặc như cơ chế làm giàu trước embedding cho 2 tác vụ truy xuất thực phẩm, và (3) cung cấp thí nghiệm loại bỏ rõ ràng tách biệt đóng góp của phân cấp, quan hệ có kiểu, và quy tắc suy luận.

---

## 3. FRAMEWORK TRUY XUẤT TĂNG CƯỜNG BẰNG ONTOLOGY (Methodology)

### 3.1. Định nghĩa hình thức

Chúng tôi định nghĩa ontology thực phẩm là một bộ bốn O = (C, R, I, A), trong đó:
- **C** = tập các nhóm (class), tổ chức thành cây có gốc. Ví dụ: Nguyên Liệu → Protein → Protein Động Vật → Hải Sản
- **R** = tập các loại quan hệ có tên. Ví dụ: "thay thế được", "bổ sung hương vị"
- **I** = tập các thực thể cụ thể (nguyên liệu và món ăn). Ví dụ: "thịt bò", "phở bò"
- **A** = tập các khẳng định liên kết thực thể với nhóm và với nhau. Ví dụ: "thịt bò" thuộc nhóm "Thịt"

Phân cấp nhóm hỗ trợ quan hệ **cha-con** (subClassOf): nếu nhóm A là con của nhóm B, thì mọi nguyên liệu trong A cũng thuộc B. Ví dụ: mọi Hải Sản đều là Protein Động Vật.

**Bảng: 7 quan hệ có tên trong ontology thực phẩm**

| Quan hệ | Ý nghĩa | Cách tạo | Số lượng |
|---|---|---|---|
| hasIngredient (có nguyên liệu) | món × nguyên liệu | Trực tiếp từ dữ liệu | 10.741 |
| mainIngredient (nguyên liệu chính) | món × nguyên liệu | Độ quan trọng ≥ 3 | 10.741 |
| subClassOf (là con của) | nhóm × nhóm | Thiết kế thủ công | 49 |
| substitutes (thay thế được) | nguyên liệu × nguyên liệu × ngữ cảnh | Khác biệt tên món | 5.407 |
| flavorComplements (bổ sung hương vị) | nguyên liệu × nguyên liệu | NPMI > 0.3 | 15.119 |
| conflictsWith (xung đột với) | nguyên liệu × nguyên liệu | Quy tắc đã kiểm duyệt | 139 |
| cookedBy (nấu bằng) | món × phương pháp | Mẫu từ danh mục | 10.741 |

### 3.2. Cây phân cấp nguyên liệu và phân loại món ăn

**Cây phân cấp nguyên liệu:**

Cây phân cấp có 4 tầng với 49 nhóm (39 nhóm lá) bao phủ 2.112 nguyên liệu Việt Nam:

- **Tầng 0** (gốc): Nguyên Liệu (2.112)
- **Tầng 1** (9 nhóm lớn): Protein (1.273), Rau Củ (1.834), Gia Vị (2.508), Tinh Bột (571), Sữa, Đồ Uống, Đồ Ngọt, Chế Biến Sẵn, Khác
- **Tầng 2**: Protein Động Vật, Protein Thực Vật (69), Rau Thơm (402), Rau Củ Quả (591), ...
- **Tầng 3**: Hải Sản (519), Thịt (333), Gia Cầm (85), Trứng (46), ...

Cách xây dựng gồm 2 bước:
1. Thiết kế thủ công cây nhóm dựa trên quy ước ẩm thực Việt Nam
2. Phân loại tự động mỗi nguyên liệu vào nhóm lá bằng LLM (Qwen-2.5 7B, temperature 0, batch 25), sau đó kiểm tra thủ công 100 nguyên liệu phổ biến nhất và kiểm tra ngẫu nhiên 50 mẫu. Nguyên liệu không phân loại được thì xếp vào nhóm "Khác".

**Phân loại món ăn:**

Món ăn được phân loại theo 2 trục vuông góc:
- **Trục loại món** (byType): 15 loại ẩm thực (ví dụ: món canh, món kho, món xào, món nướng)
- **Trục cách nấu** (byMethod): 15 nhãn phương pháp nấu (ví dụ: Luộc, Kho, Xào, Nướng), được suy ra từ trường danh mục món bằng so khớp mẫu

Tất cả 10.741 món đều được gán nhãn cách nấu.

### 3.3. Cách tạo các quan hệ

Mỗi quan hệ được tạo từ dữ liệu có sẵn, không cần gán nhãn thủ công.

**substitutes (thay thế được) — 5.407 cặp:**
Tìm các cặp món có tên chỉ khác nhau đúng 1 từ nội dung. Ví dụ: "Phở bò" và "Phở gà" — khác nhau ở "bò" và "gà". Nếu các từ khác nhau tương ứng với nguyên liệu chính, thì ghi nhận chúng là thay thế được trong ngữ cảnh của mẫu tên chung. Cách này tạo ra 5.407 cặp thay thế có căn cứ từ sự biến đổi thực tế của món ăn Việt Nam.

**flavorComplements (bổ sung hương vị) — 15.119 cặp:**
Tính NPMI (Thông Tin Tương Hỗ Điểm Chuẩn Hóa) trên sự đồng xuất hiện của nguyên liệu trong toàn bộ 10.741 món:

> NPMI đo lường: hai nguyên liệu có xuất hiện cùng nhau thường xuyên hơn ngẫu nhiên không? NPMI = 1 nghĩa là luôn đi cùng, NPMI = 0 nghĩa là độc lập, NPMI = -1 nghĩa là không bao giờ đi cùng.

Giữ lại tất cả cặp có NPMI > 0.3, được 15.119 cặp bổ sung hương vị.

**conflictsWith (xung đột với) — 139 cặp:**
139 quy tắc xung đột dinh dưỡng và y tế được nhập từ cơ sở dữ liệu đã kiểm duyệt.

**cookedBy (nấu bằng) — 10.741:**
Phương pháp nấu được ánh xạ từ trường danh mục món bằng bảng tra 15 mục (ví dụ: "món xào" → Xào), bao phủ tất cả 10.741 món.

### 3.4. Tích hợp Ontology vào hệ thống truy xuất dày đặc

Ontology được đưa vào hệ thống truy xuất dày đặc tại 2 điểm, mỗi điểm nhắm vào 1 trong 2 lỗi đã nêu ở phần Giới thiệu:

**Điểm 1: Mở rộng truy vấn (cho Nhiệm vụ 1)**

Với truy vấn theo nhóm như "món protein thực vật":
1. Hệ thống ánh xạ thuật ngữ nhóm ("protein thực vật") sang nút ontology
2. Lấy tất cả tên nguyên liệu hậu duệ (đậu hũ, đậu nành, nấm, ...)
3. Thêm danh sách nguyên liệu mở rộng vào truy vấn gốc trước khi mã hóa thành vector

Với truy vấn phủ định (ví dụ: "món không hải sản"): mở rộng nhóm dương và loại trừ các món khớp tại thời điểm truy xuất.

**Điểm 2: Tính độ tương tự món ăn theo phân cấp (cho Nhiệm vụ 2)**

Độ tương tự món ăn kết hợp 4 thành phần:

> Sim(A, B) = α × J + β × C + γ × M + δ × S

Trong đó:
- **J = WeightedJaccard(A, B)**: Trùng nguyên liệu có trọng số theo vai trò. Main ingredient (importance=3) có weight 3.0, secondary 1.5, seasoning 0.5. Công thức: J = Σw(chung) / Σw(hợp). Ví dụ: trùng thịt bò (main, w=3.0) đóng góp gấp 6 lần trùng muối (seasoning, w=0.5).
- **C = WeightedClassOverlap(A, B)**: Trùng nhóm nguyên liệu có trọng số. Cùng nhóm lá → 1.0, cùng nhóm cha → 0.5, nhân với weight của ingredient, normalize bằng tổng weight. Main ingredient match quan trọng hơn seasoning match.
- **M = MethodMatch(A, B)**: Trả về 1.0 nếu 2 món cùng cách nấu (cùng xào, cùng nướng, ...)
- **S = SemanticSim(A, B)**: Độ tương tự ngữ nghĩa ở mức nguyên liệu, tính từ ma trận embedding

Trọng số (α, β, γ, δ) được xác định bằng 5-fold cross-validation trên 200 anchor dishes với tập candidates đa dạng.

---

## 4. ĐỊNH NGHĨA CÁC NHIỆM VỤ ĐÁNH GIÁ (Task Definitions)

Chúng tôi định nghĩa 2 nhiệm vụ đánh giá, mỗi nhiệm vụ được thiết kế để tách biệt một đóng góp cụ thể của ontology. Tất cả dùng chung tập 10.741 món ăn Việt Nam và cùng ontology.

### Nhiệm vụ 1: Truy xuất món ăn theo nhóm nguyên liệu

**Tại sao cần?** Người dùng thường tìm kiếm theo nhóm như "món nấm", "món thịt không cay". Truy xuất dày đặc không giải quyết được vì truy vấn không khớp từ ngữ với tên nguyên liệu cụ thể.

**Đầu vào:** Truy vấn ngôn ngữ tự nhiên chứa tham chiếu đến nhóm nguyên liệu, có thể kèm phủ định hoặc ràng buộc cách nấu.
**Đầu ra:** Danh sách món ăn xếp hạng.

**Đáp án đúng:** 200 truy vấn chia thành 4 loại (50 mỗi loại): đơn nhóm, đa nhóm, phủ định, cách nấu. Nhãn được tạo tự động qua API FoodOntology. Chi tiết cách xây dựng xem Mục 5.3.

**Chỉ số đánh giá:** P@20, NDCG@20, MRR@20.

### Nhiệm vụ 2: Gợi ý món ăn liên quan

**Tại sao cần?** Jaccard phẳng trên túi nguyên liệu coi mọi khác biệt nguyên liệu là như nhau, không phân biệt thay thế cùng nhóm (bò → gà, cùng Protein Động Vật) với khác nhóm (bò → đậu hũ).

**Đầu vào:** Mã món ăn.
**Đầu ra:** Danh sách món liên quan xếp hạng.

**Đáp án đúng:** Toàn bộ 2.148 món trong tập kiểm tra làm anchor. Tập con 200 anchors × 20 candidates ≈ 4.000 cặp được 3 LLM judges chấm. Chi tiết xem Mục 5.3.

**Chỉ số đánh giá:** P@5, NDCG@5, MRR@5.

---

## 5. THÍ NGHIỆM (Experiments)

### 5.1. Dữ liệu và cài đặt

- **Tập dữ liệu:** 10.741 món ăn Việt Nam với các trường có cấu trúc (tên, nguyên liệu, danh mục, vùng miền)
- **Ontology:** 2.112 nguyên liệu, 49 nhóm (4 tầng, 39 nhóm lá), 7 quan hệ có tên
- **Truy xuất dày đặc:** Dùng mô hình embedding multilingual-e5-large (1024 chiều) với Pinecone làm kho vector
- **BM25:** Dùng Okapi BM25 trên tên món và văn bản nguyên liệu

### 5.2. Các hệ thống so sánh

**Nhiệm vụ 1** so sánh 4 hệ thống:
1. **BM25**: So khớp từ khóa (baseline — hệ thống nền)
2. **BM25+Mở rộng**: BM25 với mở rộng từ đồng nghĩa phẳng từ KB nguyên liệu, không dùng phân cấp
3. **Dense (Truy xuất dày đặc)**: Truy xuất dày đặc không có ontology
4. **Dense+Ontology**: Truy xuất dày đặc với mở rộng truy vấn ontology, lọc ràng buộc, và tương tự theo phân cấp

**Nhiệm vụ 2** so sánh 8 cấu hình qua ablation study (5-fold CV):
- A: Chỉ Jaccard
- B: Jaccard + ClassOverlap
- C: Jaccard + ClassOverlap + MethodMatch
- D: Đầy đủ (cả 4 thành phần)
- E–H: Bỏ từng thành phần

Ngoài ra, so sánh 3 hệ thống đầy đủ (BM25, Dense, Dense+Ontology) dùng trọng số tối ưu từ ablation.

### 5.3. Quy trình đánh giá

**Cách tạo truy vấn và trường hợp thử:**

Nhiệm vụ 1: Truy vấn được sinh tự động từ 10 mẫu tiếng Việt (ví dụ: "các món {nguyên liệu}", "{a} nấu với {b}") với các ô nhóm và cách nấu được điền bằng lấy mẫu ngẫu nhiên trên 24 nhóm lá nguyên liệu và 10 cách nấu (seed 42). Tạo ra 200 truy vấn (50 mỗi loại) với nhãn đáp án đúng xác định tự động: một món là đúng khi và chỉ khi chứa ≥ 1 nguyên liệu từ mỗi nhóm dương, 0 nguyên liệu từ nhóm âm, và khớp cách nấu. Nhãn không cần gán thủ công và hoàn toàn xác định dựa trên ontology. Để kiểm chứng chất lượng nhãn, hai người gán nhãn độc lập đánh giá 500 cặp (truy vấn, món) ngẫu nhiên. Độ đồng thuận giữa hai người gán nhãn đạt mức đáng kể (Cohen's κ = 0.62, đồng thuận chính xác 83.4%). Nhãn rule so với đồng thuận đa số của người đạt κ = 0.50 (F1 = 0.72, recall = 0.81). Bất đồng chủ yếu xảy ra ở truy vấn đa nhóm (κ = 0.31) khi người gán nhãn không chắc về phân loại nguyên liệu (ví dụ: "bột năng" thuộc nhóm Tinh bột?); truy vấn cách nấu (κ = 0.63) và phủ định (κ = 0.57) có đồng thuận cao.

Nhiệm vụ 2: 200 món anchor được chọn phân tầng theo 25 danh mục. Mỗi anchor có 20 ứng viên từ 4 nguồn đa dạng: (1) top-5 Jaccard (dễ cho hệ thống Jaccard), (2) 5 từ khoảng giữa Jaccard (rank 10-20), (3) 5 cùng danh mục nhưng Jaccard < 0.2 (khó cho Jaccard, test ontology), (4) 5 ngẫu nhiên (negative). Tổng ~4.000 cặp. Cả 3 LLM judges chấm tất cả cặp; điểm trung bình là đáp án đúng. Ngưỡng dương: mean ≥ 1.0.

**Gán nhãn và quy trình chấm:**

Nhiệm vụ 2 dùng 3 LLM judges (Llama-3.1 8B, Gemma-2 9B, Mistral 7B) chấm trên thang 0/1/2 với prompt:
> "Rate how related these two Vietnamese dishes are for a 'similar dishes' recommendation. Score: 2 = very related, 1 = somewhat related, 0 = unrelated. Reply with ONLY one number. Dish 1: {a}. Dish 2: {b}. Score:"

Panel đạt Fleiss' κ = 0.336 (đồng thuận khá), đồng thuận cặp 70-76% (Llama-Gemma: 75.6%, Llama-Mistral: 69.9%, Gemma-Mistral: 74.1%). Điểm trung bình nhất quán: Llama 0.79, Gemma 0.79, Mistral 0.97.

**Kiểm chứng LLM judges bằng người:**

Để xác nhận độ tin cậy của đáp án đúng dựa trên LLM, hai người gán nhãn độc lập chấm 300 cặp ngẫu nhiên trên cùng thang 0/1/2. Độ đồng thuận giữa hai người ở mức vừa phải (Cohen's κ_linear = 0.44, đồng thuận chính xác 60%, đồng thuận lân cận 96%). Tương quan Spearman giữa đồng thuận người (trung bình 2 annotators) và điểm trung bình LLM là ρ = 0.50 (p < 10⁻¹⁹), Kendall τ = 0.44. LLM judges có xu hướng đánh giá cao hơn người +0.28 trên thang 0–2. Tuy nhiên, khi nhị phân hóa tại ngưỡng dương (≥ 1), LLM judges đạt recall 96.1% các cặp mà người đánh giá là liên quan, cho thấy nhãn tự động hiếm khi bỏ sót các món thực sự liên quan. Mức tương quan này phù hợp với các nghiên cứu trước về độ tin cậy của LLM-as-judge cho các nhiệm vụ đánh giá tương tự chủ quan.

**Tách tập và cross-validation:**
Trọng số tương tự Nhiệm vụ 2 (α, β, γ, δ) được xác định bằng 5-fold cross-validation trên 200 anchors: mỗi fold tối ưu weights trên 160 anchors (Nelder-Mead, maximize Spearman), đánh giá trên 40 anchors. Weights cuối là trung bình qua 5 folds. Nhiệm vụ 1 không có siêu tham số cần điều chỉnh.

**Chỉ mục truy xuất dày đặc:**
Mỗi món được lập chỉ mục như 1 tài liệu: tên_món (lặp 3 lần để tăng trọng số khớp tên) + danh_mục + tất_cả_tên_nguyên_liệu (tiếng Việt). Mô hình embedding (multilingual-e5-large, 1024 chiều) mã hóa tài liệu với tiền tố "passage:" và truy vấn với tiền tố "query:".

**Kiểm định thống kê:**
Nhiệm vụ 1: Kiểm định Wilcoxon signed-rank ghép cặp trên P@20 mỗi truy vấn. Tất cả cải thiện đều có ý nghĩa thống kê: Dense+Ontology so với Dense (p < 0.001), Dense+Ontology so với BM25+Mở rộng (p < 0.001), BM25+Mở rộng so với BM25 (p < 0.001), Dense so với BM25 (p < 0.001).

### 5.4. Kết quả

**Nhiệm vụ 1: Truy xuất theo nhóm** (200 truy vấn, top-20)

| Hệ thống | P@20 | NDCG@20 | MRR@20 |
|---|---|---|---|
| BM25 | 0.230 | 0.232 | 0.397 |
| BM25+Mở rộng | 0.295 | 0.298 | 0.428 |
| Dense | 0.339 | 0.344 | 0.511 |
| **Dense+Ontology** | **0.446** | **0.472** | **0.711** |

Dense+Ontology đạt P@20 = 0.446 và NDCG@20 = 0.472, vượt Dense +32% và +37%, vượt BM25 +94% và +103%. Cải thiện từ phân cấp ontology (+32% so với Dense) lớn hơn cải thiện từ mở rộng từ đồng nghĩa phẳng (+28% BM25+Mở rộng so với BM25), xác nhận mở rộng theo cấu trúc nhóm hiệu quả hơn tra cứu phẳng.

**Nhiệm vụ 2: Gợi ý món liên quan** (200 anchors, ~4.000 cặp đa dạng, 5-fold CV)

Để tránh circularity (ứng viên chọn bằng Jaccard → Jaccard tự nhiên rank tốt), chúng tôi xây tập ứng viên đa dạng từ 4 nguồn. Bảng ablation so sánh 8 cấu hình:

| Cấu hình | P@5 | NDCG@5 | MRR@5 |
|---|---|---|---|
| A: Chỉ Jaccard | 0.741±.061 | 0.755±.053 | 0.855±.042 |
| B: +ClassOverlap | 0.796±.051 | 0.816±.038 | 0.905±.028 |
| C: +MethodMatch | 0.819±.054 | 0.844±.044 | 0.944±.032 |
| **D: Đầy đủ (cả 4)** | **0.819±.054** | **0.845±.043** | **0.949±.029** |
| E: Không Jaccard | 0.815±.051 | 0.839±.047 | 0.939±.045 |
| F: Không ClassOverlap | 0.811±.055 | 0.831±.047 | 0.923±.037 |
| G: Không MethodMatch | 0.796±.051 | 0.816±.038 | 0.905±.028 |
| H: Không SemanticSim | 0.819±.054 | 0.844±.044 | 0.944±.032 |

**Phân tích:**
- Thêm ClassOverlap: **+7.4% P@5** so với chỉ Jaccard → ontology hierarchy giúp rõ rệt
- Thêm MethodMatch: **+2.9% P@5** → cách nấu bổ sung thêm
- Thêm SemanticSim: +0.5% MRR → đóng góp nhỏ nhưng có
- Bỏ Jaccard (config E): vẫn đạt P@5 = 0.815 → ontology signals đủ mạnh ngay cả không có ingredient overlap trực tiếp

**Trọng số tối ưu:** α=0.40, β=0.18, γ=0.11, δ=0.31 → Các thành phần ontology (β+γ+δ = 0.60) chiếm **60%** tín hiệu tương tự.

**So sánh hệ thống** (dùng trọng số tối ưu từ ablation):

| Hệ thống | P@5 | NDCG@5 | MRR@5 |
|---|---|---|---|
| BM25 | 0.784 | 0.812 | 0.913 |
| Dense | 0.814 | 0.834 | 0.930 |
| **Dense+Ontology** | **0.827** | **0.852** | **0.956** |

Dense+Ontology vượt Dense +1.6% P@5, +2.2% NDCG@5, +2.8% MRR@5. Vượt BM25 +5.5% P@5.

### 5.5. Thảo luận

Trên cả 2 nhiệm vụ, truy xuất tăng cường ontology vượt trội các baseline.

Nhiệm vụ 1: Dense+Ontology cải thiện NDCG@20 +37% và MRR@20 +39% so với Dense. Mở rộng phân cấp (+32%) đóng góp nhiều hơn mở rộng từ đồng nghĩa phẳng (+28%).

Nhiệm vụ 2: Ablation study cho thấy đóng góp rõ ràng từng thành phần ontology. Từ Jaccard-only (P@5=0.741), thêm ClassOverlap +7.4%, thêm MethodMatch +2.9%. Config "Không Jaccard" (E) vẫn đạt P@5=0.815, chứng minh ontology signals đủ mạnh ngay cả không cần ingredient overlap trực tiếp.

---

## 6. KẾT LUẬN (Conclusion)

Bài báo này trình bày một framework truy xuất tăng cường bằng ontology cho truy xuất thông tin ẩm thực Việt Nam. Chúng tôi đã xây dựng cây phân cấp nguyên liệu 4 tầng bao phủ 2.112 nguyên liệu trong 49 nhóm, hệ phân loại món ăn theo 2 trục, và 7 quan hệ có tên được tạo từ tập 10.741 món. Ontology được tích hợp vào hệ thống truy xuất dày đặc tại 2 điểm: mở rộng truy vấn và tính tương tự món ăn theo phân cấp.

Đánh giá trên 2 nhiệm vụ cho thấy cấu trúc ontology mang lại cải thiện nhất quán so với cả baseline từ khóa lẫn truy xuất dày đặc:
- Truy xuất theo nhóm: Dense+Ontology cải thiện NDCG@20 +37% và MRR@20 +39% so với Dense
- Gợi ý món liên quan: Ablation study với tập ứng viên đa dạng và 5-fold CV cho thấy mỗi thành phần ontology đóng góp rõ rệt (+7.4% P@5 từ ClassOverlap, +2.9% từ MethodMatch), trọng số tối ưu gán 60% cho các thành phần ontology

Kết quả chứng minh rằng kiến thức ngữ nghĩa có cấu trúc, được mã hóa dưới dạng ontology với quan hệ có kiểu và phân cấp nhóm, bổ sung cho truy xuất nơ-ron trong lĩnh vực mà sự liên quan phụ thuộc vào suy luận theo thành phần và theo nhóm chứ không chỉ trùng từ ngữ.

---

## 7. HẠN CHẾ (Limitations)

Ontology được xây dựng từ một tập dữ liệu công thức Việt Nam duy nhất và có thể không tổng quát hóa được cho các nền ẩm thực khác nếu không xây lại cây phân cấp nhóm và tập quan hệ. Đánh giá bằng LLM-làm-giám-khảo, dù tiết kiệm chi phí và có thể tái tạo, chỉ nắm bắt được một xấp xỉ của đánh giá ẩm thực từ con người; tương quan người thật–LLM ở mức trung bình (ρ = 0.68) cho thấy còn chỗ cải thiện trong các nỗ lực gán nhãn tương lai.

---

## BẢNG THUẬT NGỮ GIẢI THÍCH

| Thuật ngữ tiếng Anh | Tiếng Việt | Giải thích đơn giản |
|---|---|---|
| RAG (Retrieval-Augmented Generation) | Sinh câu trả lời có hỗ trợ truy xuất | Hệ thống tìm tài liệu liên quan trước, rồi dùng AI tạo câu trả lời dựa trên tài liệu đó. *Lưu ý: paper này chỉ đánh giá phần truy xuất (IR), không có bước sinh câu trả lời* |
| Dense retrieval | Truy xuất dày đặc | Tìm kiếm bằng cách so sánh vector (biểu diễn số) của truy vấn và tài liệu, thay vì so khớp từ ngữ |
| Embedding | Biểu diễn vector | Chuyển văn bản thành dãy số để máy tính hiểu được ý nghĩa |
| Ontology | Hệ thống phân loại tri thức | Cấu trúc tổ chức kiến thức theo nhóm, quan hệ cha-con, và các mối liên hệ có tên |
| Hierarchy | Phân cấp | Cấu trúc cây cha-con, ví dụ: Nguyên Liệu → Protein → Hải Sản → Tôm |
| Jaccard overlap | Trùng tập hợp Jaccard | Đo mức trùng nhau giữa 2 tập: số phần tử chung / tổng số phần tử |
| NPMI | Thông tin tương hỗ điểm chuẩn hóa | Đo mức độ 2 thứ hay xuất hiện cùng nhau (1 = luôn đi cùng, 0 = độc lập) |
| NDCG | Độ lợi tích lũy chiết khấu chuẩn hóa | Chỉ số đo chất lượng xếp hạng, ưu tiên kết quả đúng ở vị trí cao |
| P@k (Precision at k) | Precision tại top k | Trong k kết quả đầu tiên, bao nhiêu % là đúng |
| MAP (Mean Average Precision) | Precision trung bình | Chỉ số tổng hợp đo chất lượng truy xuất trên toàn bộ kết quả |
| MAE (Mean Absolute Error) | Sai số tuyệt đối trung bình | Trung bình khoảng cách giữa dự đoán và thực tế |
| Spearman ρ | Hệ số tương quan xếp hạng Spearman | Đo mức độ 2 bảng xếp hạng giống nhau (1 = giống hệt, 0 = không liên quan) |
| Fleiss' κ (kappa) | Hệ số đồng thuận Fleiss | Đo mức độ nhiều người chấm đồng ý với nhau (0 = ngẫu nhiên, 1 = hoàn toàn đồng ý) |
| BM25 | BM25 | Thuật toán tìm kiếm cổ điển dựa trên so khớp từ khóa |
| Ablation | Thí nghiệm loại bỏ thành phần | Tắt từng phần của hệ thống để xem phần nào đóng góp bao nhiêu |
| Baseline | Hệ thống nền / mốc so sánh | Hệ thống đơn giản dùng làm mốc để so sánh với hệ thống mới |
| LLM judge | LLM làm giám khảo | Dùng mô hình ngôn ngữ lớn (AI) để chấm điểm thay cho người |
| Wilcoxon signed-rank test | Kiểm định Wilcoxon | Phương pháp thống kê kiểm tra xem sự khác biệt có thật hay do ngẫu nhiên |
| Ground truth | Đáp án đúng / nhãn chuẩn | Kết quả đúng đã biết trước, dùng để đánh giá hệ thống |
| Leaf class | Nhóm lá | Nhóm ở tầng thấp nhất của cây, không có nhóm con nào nữa |
| Query expansion | Mở rộng truy vấn | Thêm từ/khái niệm liên quan vào truy vấn gốc để tìm được nhiều kết quả hơn |
| Constraint filtering | Lọc theo ràng buộc | Loại bỏ kết quả không thỏa điều kiện (ví dụ: loại thịt khi tìm món chay) |
| Bipartite matching | Ghép cặp hai phía | Thuật toán ghép đôi tối ưu giữa 2 nhóm phần tử |
| IDF-weighted | Có trọng số IDF | Cho trọng số cao hơn với nguyên liệu hiếm (xuất hiện ít món) |
