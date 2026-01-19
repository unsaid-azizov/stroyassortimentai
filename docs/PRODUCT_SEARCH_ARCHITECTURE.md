# Product Search Architecture - Полная система поиска товаров

## 📊 Исследование: Современные подходы к поиску в каталогах (2026)

### Гибридный поиск (Hybrid Search)

По данным [Elasticsearch Labs](https://www.elastic.co/search-labs/blog/hybrid-search-elasticsearch) и [исследований 2026 года](https://medium.com/@connect.hashblock/7-hybrid-search-recipes-bm25-vectors-without-lag-467189542bf0), **гибридный подход** является оптимальным для e-commerce каталогов:

```
Hybrid Search = BM25 (keyword) + Vector Search (semantic) + Reranking
```

**Почему это работает для e-commerce:**
- BM25 отлично находит **точные совпадения** ("вагонка 13х115х6000")
- Vector Search понимает **семантику** ("обшить баню" → липа/осина)
- Reranking (RRF) объединяет результаты без настройки весов

**Пример из практики** ([источник](https://www.elastic.co/search-labs/blog/hybrid-search-ecommerce)):
> "Nexlify Tech (5M пользователей, 10M товаров) снизили cart abandonment с 62% используя hybrid search. Pure BM25 пропускал синонимы ('sneakers' vs 'trainers'), vector-only игнорировал точные совпадения."

### Структурированные данные в 2026

[Google требует](https://developers.google.com/search/docs/specialty/ecommerce/include-structured-data-relevant-to-ecommerce) от e-commerce правильно размеченные структурированные данные:

> "If product data isn't structured for machines, it won't surface where shopping now begins — and that means lost revenue"

**Наши данные уже структурированы:**
```
"Вагонка штиль стр. сух. хв. 13х115х6000 класс С"
   ↓ parse ↓
{
  type: "вагонка штиль",
  treatment: "строганная",
  moisture: "сухая",
  species: "хвоя",
  dimensions: {width: 13, height: 115, length: 6000},
  grade: "С"
}
```

---

## 🎯 Наша архитектура поиска

### Phase 1: Keyword-based search (текущая реализация)

```mermaid
graph TD
    A[Клиент: вагонка 6м класс АВ] --> B[search_products tool]
    B --> C{Redis cache?}
    C -->|HIT| D[Flat catalog 861 items]
    C -->|MISS| E[GET /GetGroups]
    E --> F[Flatten + Cache 1h]
    F --> D

    D --> G[Normalize query]
    G --> H[Extract keywords]
    H --> I[BM25-like scoring]
    I --> J[Top-20 results]

    J --> K[Extract group_codes]
    K --> L[POST /GetItems prices]
    L --> M[Return items with prices]

    style B fill:#90EE90
    style D fill:#87CEEB
    style M fill:#FFD700
```

**Алгоритм scoring:**
```python
def score_item(item_name: str, keywords: List[str]) -> float:
    score = 0.0

    for kw in keywords:
        if exact_match(kw, item_name):      # целое слово
            score += 10
        elif partial_match(kw, item_name):  # подстрока
            score += 5

    if keywords_in_order(item_name, keywords):
        score += 3  # бонус за порядок слов

    # Краткие названия релевантнее
    score += (50 - len(item_name)) * 0.1

    return score
```

**Плюсы Phase 1:**
- ✅ Быстро (1-5ms in-memory)
- ✅ Дешево (без API calls для embeddings)
- ✅ Точно для размеров ("6000" exact match)
- ✅ Простая инфраструктура (только Redis)

**Минусы Phase 1:**
- ❌ Не понимает семантику ("баня" ≠ "липа")
- ❌ Не работает для синонимов (нужно добавлять вручную)
- ❌ Не учитывает опечатки

---

### Phase 2: Hybrid Search (будущее расширение)

```mermaid
graph TD
    A[Клиент: обшить баню внутри] --> B[search_products tool]
    B --> C[Parse query intent]

    C --> D1[BM25 Search Path]
    C --> D2[Vector Search Path]

    D1 --> E1[Keywords: баня внутри]
    E1 --> F1[BM25 scoring on flat catalog]
    F1 --> G1[Top-50 by BM25]

    D2 --> E2[Create embedding for query]
    E2 --> F2[ChromaDB vector search]
    F2 --> G2[Top-50 by cosine similarity]

    G1 --> H[Reciprocal Rank Fusion RRF]
    G2 --> H

    H --> I[Rerank with business rules]
    I --> J[Top-20 final results]

    J --> K[POST /GetItems prices]
    K --> L[Return items with prices]

    style D1 fill:#FFB6C1
    style D2 fill:#DDA0DD
    style H fill:#FF6347
    style L fill:#FFD700
```

**Reciprocal Rank Fusion (RRF):**
```python
def reciprocal_rank_fusion(bm25_results, vector_results, k=60):
    scores = defaultdict(float)

    for rank, item in enumerate(bm25_results, start=1):
        scores[item.id] += 1 / (k + rank)

    for rank, item in enumerate(vector_results, start=1):
        scores[item.id] += 1 / (k + rank)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

**Когда переходить на Phase 2:**
- Каталог > 5,000 товаров
- Появились длинные описания товаров
- Нужен semantic search ("чем обшить баню?")
- Много синонимов и опечаток от клиентов

---

## 🤖 ReAct Agent Flow - Как думает агент

```mermaid
sequenceDiagram
    participant C as Клиент
    participant A as ReAct Agent
    participant S as search_products
    participant D as get_product_details
    participant O as collect_order_info
    participant M as call_manager

    C->>A: "Есть ли вагонка 6 метров класс АВ?"

    Note over A: 🤔 Thought:<br/>Клиент ищет вагонку<br/>Нужны размеры и класс

    A->>S: search_products(query="вагонка 6000 АВ")
    S-->>A: 8 товаров найдено:<br/>1. Вагонка штиль 13х115х6000 АВ - 15,500₽<br/>2. Вагонка штиль 13х140х6000 АВ - 17,200₽...

    Note over A: 🤔 Thought:<br/>Нашел подходящие варианты<br/>Покажу топ-3 клиенту

    A->>C: "Да, у нас есть! Нашел 8 вариантов вагонки 6м класса АВ:<br/>1. 13х115мм - 15,500₽<br/>2. 13х140мм - 17,200₽<br/>3. 14х140мм - 18,000₽<br/>Какая ширина вас интересует?"

    C->>A: "Подойдет 13х140, покажи детали"

    Note over A: 🤔 Thought:<br/>Клиент выбрал товар<br/>Нужна детальная информация

    A->>D: get_product_details(codes=["00-00010177"])
    D-->>A: Детали:<br/>Влажность: 12-14%<br/>Порода: хвоя<br/>Срок производства: 7 дней<br/>В наличии: 15м³

    A->>C: "Вагонка штиль 13х140х6000 класс АВ:<br/>💰 Цена: 17,200₽/м³<br/>📦 В наличии: 15м³<br/>🌲 Хвоя, влажность 12-14%<br/>⏱ Срок производства: 7 дней<br/>Сколько вам нужно?"

    C->>A: "Нужно 10 кубов, есть доставка?"

    Note over A: 🤔 Thought:<br/>Клиент готов заказать<br/>Нужна информация о доставке<br/>Потом соберу заказ

    A->>C: "Доставка есть! Москва и МО,<br/>стоимость зависит от адреса.<br/>Давайте оформлю заказ?"

    C->>A: "Да, оформляй"

    A->>O: collect_order_info(...)
    O-->>A: Заказ собран

    A->>C: "Отлично! Заказ:<br/>- Вагонка 13х140х6000 АВ, 10м³<br/>- Сумма: 172,000₽<br/>- Ваш телефон для связи?"

    C->>A: "+7 999 123-45-67"

    Note over A: 🤔 Thought:<br/>Все данные собраны<br/>Передаю менеджеру

    A->>M: call_manager(reason="Заказ готов")

    A->>C: "Спасибо! Менеджер свяжется<br/>в течение 15 минут для<br/>подтверждения и расчета доставки 👍"
```

---

## 🧠 Decision Tree агента: Какой tool использовать?

```mermaid
graph TD
    Start[Сообщение клиента] --> Q1{Спрашивает<br/>о товаре?}

    Q1 -->|Да| Q2{Знает точное<br/>название?}
    Q1 -->|Нет| Q10{О компании?}

    Q2 -->|Да, с кодом| T1[get_product_details<br/>с кодом товара]
    Q2 -->|Нет| T2[search_products<br/>с описанием]

    Q10 -->|Да| T3[search_company_info<br/>доставка/оплата/контакты]
    Q10 -->|Нет| Q11{Готов<br/>заказать?}

    T2 --> Q3{Нашлись<br/>товары?}

    Q3 -->|Да| Q4{Клиент выбрал<br/>товар?}
    Q3 -->|Нет| Q5{Можно<br/>переформулировать?}

    Q4 -->|Да| T4[get_product_details<br/>для выбранного]
    Q4 -->|Нет| End1[Показать топ-5<br/>и спросить предпочтения]

    Q5 -->|Да| T5[search_products<br/>с новым запросом]
    Q5 -->|Нет| T6[call_manager<br/>товар не найден]

    T4 --> Q6{Клиент<br/>заинтересован?}

    Q6 -->|Да| Q7{Есть все<br/>данные для заказа?}
    Q6 -->|Нет| End2[Предложить альтернативы]

    Q7 -->|Да| T7[collect_order_info<br/>и call_manager]
    Q7 -->|Нет| End3[Спросить недостающие<br/>данные: количество, телефон]

    Q11 -->|Да| Q7
    Q11 -->|Нет| Q12{Общий<br/>вопрос?}

    Q12 -->|Да| End4[Ответить из KB<br/>илиググ]
    Q12 -->|Нет| End5[Off-topic<br/>вежливо отказать]

    style T1 fill:#90EE90
    style T2 fill:#90EE90
    style T3 fill:#87CEEB
    style T4 fill:#90EE90
    style T5 fill:#90EE90
    style T6 fill:#FFB6C1
    style T7 fill:#FFD700
```

---

## 📈 Алгоритм поиска: Deep Dive

### Структура названия товара

```
"Вагонка штиль стр. сух. хв. 13х115х6000 класс С"
   │        │      │    │    │     │      │      │
   │        │      │    │    │     │      │      └─ Класс качества
   │        │      │    │    │     │      └──────── Длина (мм)
   │        │      │    │    │     └─────────────── Ширина (мм)
   │        │      │    │    └───────────────────── Толщина (мм)
   │        │      │    └────────────────────────── Порода
   │        │      └─────────────────────────────── Влажность
   │        └────────────────────────────────────── Обработка
   └─────────────────────────────────────────────── Тип изделия
```

### Parse & Index Pipeline

```mermaid
graph LR
    A[Raw name] --> B[Parse regex]
    B --> C[Extract tokens]
    C --> D[Normalize]
    D --> E[Create searchable text]

    E --> F1[Original: вагонка штиль...]
    E --> F2[Tokens: вагонка, штиль, 13, 115, 6000...]
    E --> F3[Normalized: вагонка, 6000, с]
    E --> F4[Metadata: type, width, length, grade]

    F1 --> G[Index in Redis]
    F2 --> G
    F3 --> G
    F4 --> G

    style G fill:#FFD700
```

### Query Processing Pipeline

```python
def process_query(query: str) -> SearchQuery:
    """
    "вагонка 6 метров класс АВ"
    →
    {
      original: "вагонка 6 метров класс АВ",
      normalized: "вагонка 6000 ав",
      keywords: ["вагонка", "6000", "ав"],
      filters: {
        type: "вагонка",
        length: 6000,
        grade: "АВ"
      },
      intent: "product_search"
    }
    """

    # 1. Нормализация
    normalized = normalize_query(query)  # "6м" → "6000"

    # 2. Извлечение keywords
    keywords = extract_keywords(normalized)

    # 3. Распознавание фильтров (если есть)
    filters = extract_filters(keywords)

    # 4. Классификация intent
    intent = classify_intent(query)

    return SearchQuery(
        original=query,
        normalized=normalized,
        keywords=keywords,
        filters=filters,
        intent=intent
    )
```

### Scoring Algorithm (BM25-like)

```python
def bm25_score(doc: Document, query_terms: List[str], k1=1.5, b=0.75) -> float:
    """
    BM25 = ∑ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))

    где:
    - f(qi, D) = частота термина qi в документе D
    - |D| = длина документа D
    - avgdl = средняя длина документа в коллекции
    - IDF(qi) = log((N - n(qi) + 0.5) / (n(qi) + 0.5))
    """
    score = 0.0

    for term in query_terms:
        # Term frequency в документе
        tf = doc.count(term) / len(doc.tokens)

        # Inverse document frequency
        df = corpus.doc_count(term)  # сколько документов содержат term
        idf = math.log((corpus.total_docs - df + 0.5) / (df + 0.5))

        # Нормализация по длине документа
        norm = 1 - b + b * (len(doc.tokens) / corpus.avg_doc_length)

        # BM25 формула
        term_score = idf * (tf * (k1 + 1)) / (tf + k1 * norm)
        score += term_score

    return score
```

**Упрощенная версия (наша текущая):**
```python
def simple_score(item_name: str, keywords: List[str]) -> float:
    """Упрощенный BM25 без IDF расчетов (для малого каталога)."""
    score = 0.0

    for kw in keywords:
        # Exact match = высокий вес
        if f' {kw} ' in f' {item_name.lower()} ':
            score += 10
        # Partial match = средний вес
        elif kw in item_name.lower():
            score += 5

    # Бонусы
    if all(kw in item_name.lower() for kw in keywords):
        score += 3  # все keywords найдены

    # Penalty за длину (короткие названия лучше)
    score -= len(item_name) * 0.01

    return score
```

---

## 🚀 Roadmap развития поиска

### V1.0 - Keyword Search (ТЕКУЩАЯ)
- ✅ BM25-like scoring
- ✅ Нормализация запросов
- ✅ Кэширование в Redis
- ✅ Один tool вызов
- **Готовность**: 95%

### V1.1 - Enhanced Keyword Search
- [ ] Fuzzy matching (опечатки)
- [ ] Stemming (основа слова)
- [ ] Spell correction
- [ ] Query expansion (синонимы авто)
- **Срок**: 2 недели

### V2.0 - Hybrid Search
- [ ] Vector DB (ChromaDB)
- [ ] Embeddings для товаров
- [ ] Semantic search
- [ ] RRF fusion
- **Срок**: 1 месяц

### V2.1 - Personalization
- [ ] Учет истории поиска пользователя
- [ ] Популярные товары
- [ ] A/B тесты алгоритмов
- **Срок**: 2 месяца

---

## 📊 Метрики качества поиска

### Precision & Recall
```
Precision = relevant_found / total_found
Recall = relevant_found / total_relevant

F1 Score = 2 * (Precision * Recall) / (Precision + Recall)
```

### Mean Reciprocal Rank (MRR)
```
MRR = (1/|Q|) * ∑(1 / rank_i)

где rank_i = позиция первого релевантного результата
```

### Normalized Discounted Cumulative Gain (NDCG)
```
DCG@k = ∑(rel_i / log2(i + 1))

NDCG@k = DCG@k / IDCG@k
```

**Целевые метрики для V1.0:**
- Precision@5: > 80% (топ-5 релевантны)
- MRR: > 0.7 (первый релевантный в топ-3)
- Zero results rate: < 10% (не более 10% пустых ответов)

---

## 🔗 Sources

- [Elasticsearch Hybrid Search Guide](https://www.elastic.co/what-is/hybrid-search)
- [Semantic Product Search for E-Commerce (arXiv)](https://arxiv.org/abs/2008.08180)
- [Hybrid Search Recipes: BM25 + Vectors](https://medium.com/@connect.hashblock/7-hybrid-search-recipes-bm25-vectors-without-lag-467189542bf0)
- [Elasticsearch Labs: Hybrid Search for E-Commerce](https://www.elastic.co/search-labs/blog/hybrid-search-ecommerce)
- [Google Structured Data for E-Commerce](https://developers.google.com/search/docs/specialty/ecommerce/include-structured-data-relevant-to-ecommerce)
- [Optimizing RAG with Hybrid Search & Reranking](https://superlinked.com/vectorhub/articles/optimizing-rag-with-hybrid-search-reranking)

---

**Дата создания**: 2026-01-18
**Версия**: 1.0
**Статус**: Research Complete, Architecture Defined
