# Flow BM25+Expansion trong 2 Task

## Tổng quan

**BM25+Expansion** là một baseline system sử dụng BM25 (Okapi BM25) kết hợp với **flat synonym expansion** (mở rộng từ đồng nghĩa phẳng) từ ingredient knowledge base, **không sử dụng phân cấp ontology**.

Đây là hệ thống trung gian giữa:
- **BM25 thuần túy**: chỉ khớp từ khóa
- **Dense+Ontology**: sử dụng embedding + ontology hierarchy

---

## Task 1: Class-Based Dish Retrieval

### Mục đích
Truy xuất món ăn dựa trên truy vấn cấp lớp (class-level queries) như:
- "món nấm" (mushroom dishes)
- "món thịt không cay" (meat dishes without spice)

### Flow BM25+Expansion cho Task 1

#### 1. **Input**
```python
query = "món protein thực vật"  # Ví dụ: plant protein dishes
```

#### 2. **Xây dựng Synonym Map** (một lần, khi khởi tạo)
```python
# Load ingredient KB
ikb = json.loads("ingredient_knowledge_base.json")

# Tạo map: keyword → list of synonyms
keyword_to_names = {}
for entry in ikb:
    name = entry["name_vi"].lower().strip()      # "đậu hũ"
    syns = [s.lower() for s in entry["synonyms"]] # ["tàu hũ", "đậu phụ"]
    
    # Map name → synonyms
    keyword_to_names[name] = syns + [name]
    
    # Map mỗi synonym → name (để tra ngược)
    for s in syns:
        keyword_to_names[s].append(name)
```

**Kết quả:**
```python
keyword_to_names = {
    "đậu hũ": ["đậu hũ", "tàu hũ", "đậu phụ"],
    "tàu hũ": ["đậu hũ"],
    "đậu phụ": ["đậu hũ"],
    "thịt bò": ["thịt bò", "bò"],
    ...
}
```

#### 3. **Query Expansion** (mỗi lần search)
```python
def search(query: str, top_k: int):
    # Tokenize query
    tokens = query.lower().split()  # ["món", "protein", "thực", "vật"]
    
    # Tìm synonyms cho mỗi token
    expanded_terms = []
    for tok in tokens:
        if tok in keyword_to_names:
            # Lấy tối đa 5 synonyms
            expanded_terms.extend(keyword_to_names[tok][:5])
    
    # Tạo expanded query
    if expanded_terms:
        expanded_query = query + " " + " ".join(set(expanded_terms))
    else:
        expanded_query = query
    
    # BM25 search với expanded query
    results = bm25.search(expanded_query, top_k=top_k)
    return [r["dish_id"] for r in results]
```

#### 4. **Ví dụ cụ thể**

**Input:**
```python
query = "món đậu hũ"
```

**Expansion:**
```python
tokens = ["món", "đậu", "hũ"]
# "đậu hũ" match trong keyword_to_names
expanded_terms = ["đậu hũ", "tàu hũ", "đậu phụ"]
expanded_query = "món đậu hũ tàu hũ đậu phụ"
```

**BM25 Search:**
```python
# BM25 tìm kiếm trên corpus:
# - Dish name: "Đậu hũ sốt cà chua"
# - Ingredients: "đậu hũ, cà chua, tỏi, ..."

# Expanded query giúp match cả:
# - "đậu hũ" (exact match)
# - "tàu hũ" (synonym trong một số món)
# - "đậu phụ" (synonym khác)
```

**Output:**
```python
[
    "dish_0123",  # Đậu hũ sốt cà chua
    "dish_0456",  # Tàu hũ chiên giòn
    "dish_0789",  # Đậu phụ nhồi thịt
    ...
]
```

### Hạn chế của BM25+Expansion trong Task 1

❌ **Không hiểu phân cấp (hierarchy):**
- Query "món protein" → không tự động expand sang "thịt bò", "thịt gà", "đậu hũ"
- Chỉ expand nếu có synonym trực tiếp trong KB

❌ **Không xử lý negation:**
- Query "món không hải sản" → không filter được

❌ **Không xử lý cooking method:**
- Query "món xào" → không match được với cooking method

### Kết quả Task 1

| System | P@20 | NDCG@20 | MRR@20 |
|--------|------|---------|--------|
| BM25 | 0.230 | 0.232 | 0.397 |
| **BM25+Expansion** | **0.295** | **0.298** | **0.428** |
| Dense | 0.339 | 0.344 | 0.511 |
| Dense+Ontology | 0.446 | 0.472 | 0.711 |

**Cải thiện:** +28% so với BM25 thuần túy (nhờ synonym expansion)

---

## Task 2: Related-Dish Recommendation

### Mục đích
Tìm các món ăn liên quan (similar dishes) cho một món ăn cho trước.

### Flow BM25+Expansion cho Task 2

#### 1. **Input**
```python
anchor_dish_id = "dish_0123"  # Bún bò Huế
```

#### 2. **Xây dựng Query từ Anchor Dish**
```python
def search(anchor_dish_id: str, top_k: int):
    # Load dish metadata
    dish = dish_kb[anchor_dish_id]
    
    # Bắt đầu với tên món
    query_parts = [dish["name_vi"]]  # ["Bún bò Huế"]
    
    # Thêm tên nguyên liệu
    for ing in dish["ingredients"]:
        ing_name = ing["name_vi"].lower().strip()
        if ing_name:
            query_parts.append(ing_name)
            
            # Thêm synonyms (max 3 per ingredient)
            syns = keyword_to_names.get(ing_name, [])
            query_parts.extend(syns[:3])
    
    # Tạo expanded query
    expanded_query = " ".join(query_parts)
    
    # BM25 search
    results = bm25.search(expanded_query, top_k=200)
    
    # Tạo ranking scores
    rankings = {r["dish_id"]: 1.0 / (idx + 1) 
                for idx, r in enumerate(results)}
    
    return rankings
```

#### 3. **Ví dụ cụ thể**

**Input:**
```python
anchor_dish = {
    "id": "dish_0123",
    "name_vi": "Bún bò Huế",
    "ingredients": [
        {"name_vi": "thịt bò", "importance": 3},
        {"name_vi": "bún", "importance": 3},
        {"name_vi": "sả", "importance": 2},
        {"name_vi": "mắm ruốc", "importance": 2},
        {"name_vi": "ớt", "importance": 1}
    ]
}
```

**Query Construction:**
```python
query_parts = [
    "Bún bò Huế",           # Dish name
    "thịt bò",              # Main ingredient
    "bò",                   # Synonym 1
    "thịt bò tươi",         # Synonym 2
    "bún",                  # Main ingredient
    "bánh canh",            # Synonym 1
    "sả",                   # Secondary ingredient
    "sả tươi", "sả khô",    # Synonyms
    "mắm ruốc",             # Secondary ingredient
    "ớt"                    # Seasoning
]

expanded_query = "Bún bò Huế thịt bò bò thịt bò tươi bún bánh canh sả sả tươi sả khô mắm ruốc ớt"
```

**BM25 Search:**
```python
# BM25 tính score dựa trên:
# - Term frequency (TF): số lần xuất hiện của term trong document
# - Inverse document frequency (IDF): độ hiếm của term trong corpus
# - Document length normalization

# Dishes có nhiều nguyên liệu trùng khớp → score cao
```

**Output Rankings:**
```python
{
    "dish_0124": 1.0,      # Bún bò Nam Bộ (rank 1)
    "dish_0125": 0.5,      # Bún bò giò heo (rank 2)
    "dish_0126": 0.333,    # Phở bò (rank 3)
    "dish_0127": 0.25,     # Bún riêu (rank 4)
    ...
}
```

#### 4. **Evaluation**

Sau khi có rankings, so sánh với ground truth (LLM judge scores):

```python
def compute_metrics(rankings, ground_truth):
    # Sort candidates by BM25 score
    sorted_cands = sorted(candidates, 
                         key=lambda x: rankings.get(x[0], 0), 
                         reverse=True)
    
    # Top 5
    top5 = sorted_cands[:5]
    
    # Relevance labels (1 if judge score >= 1.0, else 0)
    rels = [1 if gt_score >= 1.0 else 0 
            for _, gt_score in top5]
    
    # P@5
    p5 = sum(rels) / 5
    
    # NDCG@5
    dcg = sum(rel / log2(i + 2) for i, rel in enumerate(rels))
    ideal = sum(1 / log2(i + 2) for i in range(min(n_positive, 5)))
    ndcg5 = dcg / ideal if ideal > 0 else 0.0
    
    # MRR@5
    mrr = 0.0
    for i, rel in enumerate(rels):
        if rel:
            mrr = 1.0 / (i + 1)
            break
    
    return {"P@5": p5, "NDCG@5": ndcg5, "MRR@5": mrr}
```

### Hạn chế của BM25+Expansion trong Task 2

❌ **Không hiểu structural similarity:**
- Chỉ dựa vào lexical matching (từ khóa)
- Không biết "thịt bò" và "thịt gà" cùng là AnimalProtein

❌ **Không xét cooking method:**
- "Bún bò Huế" (boil) vs "Bò xào" (stir-fry) → không phân biệt

❌ **Không xét flavor compatibility:**
- Không biết "sả + thịt bò" là cặp flavor complement

❌ **Không weight ingredients by importance:**
- "Muối" (seasoning) và "Thịt bò" (main) được treat như nhau

### Kết quả Task 2

| System | P@5 | NDCG@5 | MRR@5 |
|--------|-----|--------|-------|
| BM25 | 0.784 | 0.812 | 0.913 |
| **BM25+Expansion** | **0.792** | **0.818** | **0.920** |
| Dense | 0.814 | 0.834 | 0.930 |
| Dense+Ontology | 0.825 | 0.849 | 0.937 |

**Cải thiện:** +1.0% P@5 so với BM25 thuần túy

**Lưu ý:** Cải thiện nhỏ hơn nhiều so với Task 1 (+28%) vì:
- Task 2 query là dish-specific (tên món cụ thể)
- Synonym expansion chỉ giúp match ingredient terms
- Không capture được structural relationships

---

## So sánh BM25+Expansion vs Dense+Ontology

### Task 1: Class-Based Retrieval

| Aspect | BM25+Expansion | Dense+Ontology |
|--------|----------------|----------------|
| **Query expansion** | Flat synonyms only | Hierarchical class expansion |
| **Negation** | ❌ Not supported | ✅ Post-filter by negative classes |
| **Cooking method** | ❌ Not supported | ✅ Filter by cooking method |
| **Semantic understanding** | ❌ Lexical only | ✅ Dense embeddings |
| **P@20** | 0.295 | **0.446** (+51%) |

### Task 2: Related-Dish Recommendation

| Aspect | BM25+Expansion | Dense+Ontology |
|--------|----------------|----------------|
| **Ingredient matching** | Lexical + synonyms | Weighted Jaccard + ClassOverlap |
| **Cooking method** | ❌ Not considered | ✅ MethodMatch component |
| **Flavor compatibility** | ❌ Not considered | ✅ FlavorComplement (NPMI) |
| **Semantic similarity** | ❌ Not considered | ✅ SemanticSim component |
| **Importance weighting** | ❌ All equal | ✅ Main=3.0, Secondary=1.5, Seasoning=0.5 |
| **P@5** | 0.792 | **0.825** (+4.2%) |

---

## Code Implementation Summary

### Task 1: `eval_task1_retrieval.py`

```python
def build_bm25_expansion_system():
    bm25 = BM25Retriever()
    
    # Load ingredient KB
    ikb = json.loads("ingredient_knowledge_base.json")
    
    # Build synonym map
    keyword_to_names = {}
    for e in ikb:
        name = e["name_vi"].lower().strip()
        syns = [s.lower() for s in e.get("synonyms", [])]
        keyword_to_names[name] = syns + [name]
        for s in syns:
            keyword_to_names.setdefault(s, []).append(name)
    
    def search(query: str, top_k: int):
        # Expand query
        tokens = query.lower().split()
        expanded_terms = []
        for tok in tokens:
            if tok in keyword_to_names:
                expanded_terms.extend(keyword_to_names[tok][:5])
        
        expanded_query = query
        if expanded_terms:
            expanded_query = query + " " + " ".join(set(expanded_terms))
        
        # BM25 search
        results = bm25.search(expanded_query, top_k=top_k)
        return [r["dish_id"] for r in results]
    
    return search
```

### Task 2: `task3_bm25_expansion_only.py`

```python
# Build synonym map (same as Task 1)
_keyword_to_names = {}
for entry in ikb:
    name = entry["name_vi"].lower().strip()
    syns = [s.lower() for s in entry.get("synonyms", [])]
    _keyword_to_names[name] = syns + [name]
    for s in syns:
        _keyword_to_names.setdefault(s, []).append(name)

# For each anchor dish
for anchor in anchors:
    dish = dish_kb[anchor]
    
    # Build expanded query
    query_parts = [dish["name_vi"]]
    for ing in dish["ingredients"]:
        ing_name = ing["name_vi"].lower().strip()
        if ing_name:
            query_parts.append(ing_name)
            # Add synonyms (max 3 per ingredient)
            syns = _keyword_to_names.get(ing_name, [])
            query_parts.extend(syns[:3])
    
    expanded_query = " ".join(query_parts)
    
    # BM25 search
    results = bm25.search(expanded_query, top_k=200)
    
    # Create rankings
    rankings[anchor] = {
        r["dish_id"]: 1.0 / (idx + 1) 
        for idx, r in enumerate(results)
    }
```

---

## Kết luận

### Ưu điểm của BM25+Expansion
✅ Đơn giản, dễ implement  
✅ Nhanh (không cần embedding)  
✅ Cải thiện đáng kể so với BM25 thuần túy (+28% Task 1, +1% Task 2)  
✅ Không cần training data  

### Nhược điểm
❌ Không hiểu phân cấp (hierarchy)  
❌ Không xử lý negation, constraints  
❌ Không xét structural similarity  
❌ Không weight ingredients by importance  
❌ Không capture flavor compatibility  

### Vai trò trong Paper
BM25+Expansion là **baseline trung gian** để chứng minh:
1. Flat synonym expansion có giúp ích (so với BM25)
2. Nhưng không đủ mạnh như hierarchical ontology expansion (Dense+Ontology)
3. Structured knowledge (ontology) > Flat knowledge (synonyms)
