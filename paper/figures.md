# Figure 1: Ontology Structure — T-box (Schema) and A-box (Instances)

```mermaid
graph TD
    subgraph TBOX["<b>T-box (Schema): Class Hierarchy &amp; Relation Types</b>"]
        direction TB

        Ingredient["<b>Ingredient</b>"]

        Protein["Protein"]
        Produce["Produce"]
        Seasoning["Seasoning"]
        Staple["Staple"]
        DairyEtc["Dairy | Beverage | Sweet | Processed | Other"]

        Ingredient -->|subClassOf| Protein
        Ingredient -->|subClassOf| Produce
        Ingredient -->|subClassOf| Seasoning
        Ingredient -->|subClassOf| Staple
        Ingredient -->|subClassOf| DairyEtc

        AnimalProtein["AnimalProtein"]
        PlantProtein["PlantProtein"]
        Protein -->|subClassOf| AnimalProtein
        Protein -->|subClassOf| PlantProtein

        Seafood["Seafood"]
        Meat["Meat"]
        Poultry["Poultry"]
        Egg["Egg"]
        AnimalProtein -->|subClassOf| Seafood
        AnimalProtein -->|subClassOf| Meat
        AnimalProtein -->|subClassOf| Poultry
        AnimalProtein -->|subClassOf| Egg

        Herb["Herb"]
        Vegetable["Vegetable"]
        Mushroom["Mushroom"]
        Produce -->|subClassOf| Herb
        Produce -->|subClassOf| Vegetable
        Produce -->|subClassOf| Mushroom

        Dish["<b>Dish</b>"]
        ByType["byType: MonNuoc, MonKho, MonXao, ..."]
        ByMethod["byMethod: Boil, Fry, Grill, Steam, ..."]
        Dish -->|classified by| ByType
        Dish -->|classified by| ByMethod

        %% Relation type signatures
        R1["<i>substitutes</i>(ing × ing × ctx)"]
        R2["<i>flavorComplements</i>(ing × ing)"]
        R3["<i>conflictsWith</i>(ing × ing)"]
        R4["<i>cookedBy</i>(dish × method)"]
        R5["<i>hasIngredient</i>(dish × ing)"]
    end

    subgraph ABOX["<b>A-box (Instances): Assertions</b>"]
        direction TB

        %% Ingredient instances
        i1["🥩 thịt bò<br/><i>instanceOf</i> Meat"]
        i2["🐔 thịt gà<br/><i>instanceOf</i> Poultry"]
        i3["🧈 đậu hũ<br/><i>instanceOf</i> PlantProtein"]
        i4["🦐 tôm<br/><i>instanceOf</i> Seafood"]
        i5["🌿 húng quế<br/><i>instanceOf</i> Herb"]

        %% Dish instances
        d1["🍜 Phở bò<br/><i>instanceOf</i> Dish"]
        d2["🍜 Phở gà<br/><i>instanceOf</i> Dish"]

        %% Relation assertions
        i1 ---|"substitutes(ctx=phở)"| i2
        i1 ---|"substitutes(ctx=phở)"| i3
        i1 ---|"flavorComplements"| i5
        d1 ---|"hasIngredient"| i1
        d2 ---|"hasIngredient"| i2
        d1 ---|"cookedBy: Boil"| d1b["  "]
        d2 ---|"cookedBy: Boil"| d2b["  "]
    end

    %% Link A-box to T-box
    i1 -.->|instanceOf| Meat
    i2 -.->|instanceOf| Poultry
    i3 -.->|instanceOf| PlantProtein
    i4 -.->|instanceOf| Seafood
    i5 -.->|instanceOf| Herb

    style TBOX fill:#fdf2e9,stroke:#e67e22,stroke-width:2px
    style ABOX fill:#eaf2f8,stroke:#2980b9,stroke-width:2px
    style Ingredient fill:#2c3e50,color:#fff
    style Dish fill:#2c3e50,color:#fff
    style Protein fill:#e74c3c,color:#fff
    style Produce fill:#27ae60,color:#fff
    style Seasoning fill:#f39c12,color:#fff
    style Staple fill:#8e44ad,color:#fff
    style AnimalProtein fill:#e74c3c,color:#fff
    style PlantProtein fill:#e74c3c,color:#fff
    style Seafood fill:#e74c3c,color:#fff
    style Meat fill:#e74c3c,color:#fff
    style Poultry fill:#e74c3c,color:#fff
    style Egg fill:#e74c3c,color:#fff
    style Herb fill:#27ae60,color:#fff
    style Vegetable fill:#27ae60,color:#fff
    style Mushroom fill:#27ae60,color:#fff
    style DairyEtc fill:#3498db,color:#fff
    style R1 fill:#fff,stroke:#e67e22,stroke-dasharray: 5 5
    style R2 fill:#fff,stroke:#e67e22,stroke-dasharray: 5 5
    style R3 fill:#fff,stroke:#e67e22,stroke-dasharray: 5 5
    style R4 fill:#fff,stroke:#e67e22,stroke-dasharray: 5 5
    style R5 fill:#fff,stroke:#e67e22,stroke-dasharray: 5 5
    style d1b fill:none,stroke:none
    style d2b fill:none,stroke:none
```

---

# Figure 1b: A-box (Instances & Assertions) — Standalone

> Scenario: User hỏi *"Nấu bún bò Huế mà hết giò heo thì thay bằng gì?"*

```mermaid
graph LR
    subgraph MEAT["🥩 Meat / Poultry"]
        i1["🦴 giò heo\nMeat"]
        i2["🥩 thịt bò\nMeat"]
        i6["🐔 thịt gà\nPoultry"]
        i7["🐷 thịt heo\nMeat"]
    end

    subgraph SEAFOOD["🦐 Seafood"]
        i8["🦐 tôm\nSeafood"]
        i9["🦑 mực\nSeafood"]
    end

    subgraph HERB["🌿 Herb / Seasoning"]
        i3["🌿 sả\nHerb"]
        i4["🫙 mắm ruốc\nSeasoning"]
        i10["🧅 hành tím\nHerb"]
        i11["🌶️ ớt\nHerb"]
    end

    subgraph STAPLE["🍜 Staple"]
        i5["🍜 bún\nStaple"]
        i12["🍝 mì\nStaple"]
    end

    subgraph DISHES["🍲 Dish Instances"]
        d1["🍲 Bún bò Huế\nMonNuoc · Boil"]
        d2["🍜 Phở bò\nMonNuoc · Boil"]
        d3["🍜 Bún thịt nướng\nMonKho · Grill"]
    end

    %% hasIngredient — Bún bò Huế
    d1 -->|"hasIngredient"| i1
    d1 -->|"hasIngredient"| i2
    d1 -->|"hasIngredient"| i3
    d1 -->|"hasIngredient"| i4
    d1 -->|"hasIngredient"| i5
    d1 -->|"hasIngredient"| i10
    d1 -->|"hasIngredient"| i11

    %% hasIngredient — Phở bò
    d2 -->|"hasIngredient"| i2
    d2 -->|"hasIngredient"| i10
    d2 -->|"hasIngredient"| i12

    %% hasIngredient — Bún thịt nướng
    d3 -->|"hasIngredient"| i7
    d3 -->|"hasIngredient"| i5
    d3 -->|"hasIngredient"| i3

    %% substitutes
    i1 -->|"substitutes\n(ctx=bún bò Huế)"| i2
    i1 -->|"substitutes\n(ctx=bún bò Huế)"| i7
    i5 -->|"substitutes\n(ctx=general)"| i12

    %% flavorComplements
    i2 -->|"flavorComplements"| i3
    i2 -->|"flavorComplements"| i4
    i8 -->|"flavorComplements"| i11

    %% conflictsWith
    i4 ---|"conflictsWith"| i9

    %% relatedDish
    d1 -.->|"relatedDish\n(Meat+Staple+Boil)"| d2
    d1 -.->|"relatedDish\n(Meat+Bún)"| d3

    style MEAT fill:#fde8e8,stroke:#e74c3c,stroke-width:1.5px
    style SEAFOOD fill:#fde8e8,stroke:#e74c3c,stroke-width:1.5px
    style HERB fill:#e9f7ef,stroke:#27ae60,stroke-width:1.5px
    style STAPLE fill:#f3e8fd,stroke:#8e44ad,stroke-width:1.5px
    style DISHES fill:#e8f8f5,stroke:#27ae60,stroke-width:2px

    style i1 fill:#e74c3c,color:#fff
    style i2 fill:#e74c3c,color:#fff
    style i6 fill:#e74c3c,color:#fff
    style i7 fill:#e74c3c,color:#fff
    style i8 fill:#c0392b,color:#fff
    style i9 fill:#c0392b,color:#fff
    style i3 fill:#27ae60,color:#fff
    style i4 fill:#f39c12,color:#fff
    style i10 fill:#27ae60,color:#fff
    style i11 fill:#27ae60,color:#fff
    style i5 fill:#8e44ad,color:#fff
    style i12 fill:#8e44ad,color:#fff
    style d1 fill:#2c3e50,color:#fff
    style d2 fill:#2c3e50,color:#fff
    style d3 fill:#2c3e50,color:#fff
```

---

# Figure 2: RAG Pipeline with 3 Ontology Injection Points

```mermaid
flowchart LR
    subgraph INPUT["Input"]
        Q["User Query"]
    end

    subgraph ONTOLOGY["Food Ontology"]
        direction TB
        H["Class Hierarchy<br/>4 levels"]
        R["Named Relations<br/>substitutes, complements,<br/>conflicts, cookedBy"]
    end

    subgraph PIPELINE["RAG Pipeline"]
        direction TB

        subgraph IP1["① Query Expansion<br/><i>Task 1: Class-based Retrieval</i>"]
            QE["'món protein thực vật'<br/>→ get_descendants(PlantProtein)<br/>→ {đậu hũ, đậu phộng, ...}"]
        end

        DR["Dense Retrieval<br/>(multilingual embedding)"]

        subgraph IP2["② Substitution Reasoning<br/><i>Task 2: Constrained Substitution</i>"]
            SR["lookup_substitutes(ing, ctx)<br/>→ filter by constraint via hierarchy<br/>→ rank by NPMI with dish"]
        end

        subgraph IP3["③ Hierarchy-aware Similarity<br/><i>Task 3: Related-Dish Recommendation</i>"]
            HS["Sim = α·Jaccard + β·ClassOverlap + γ·MethodMatch"]
        end
    end

    subgraph OUTPUT["Output"]
        O1["Ranked Dishes"]
        O2["Ranked Substitutes"]
        O3["Related Dishes"]
    end

    Q --> IP1
    ONTOLOGY --> IP1
    IP1 --> DR
    DR --> O1

    Q --> IP2
    ONTOLOGY --> IP2
    IP2 --> O2

    DR --> IP3
    IP2 --> IP3
    ONTOLOGY --> IP3
    IP3 --> O3

    style INPUT fill:#ecf0f1,stroke:#bdc3c7
    style ONTOLOGY fill:#fdf2e9,stroke:#f39c12
    style PIPELINE fill:#eaf2f8,stroke:#3498db
    style OUTPUT fill:#e8f8f5,stroke:#27ae60
    style IP1 fill:#fadbd8,stroke:#e74c3c
    style IP2 fill:#fadbd8,stroke:#e74c3c
    style IP3 fill:#fadbd8,stroke:#e74c3c
```
