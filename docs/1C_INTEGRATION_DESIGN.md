# 1C Integration Design - Tool Calling Pipeline

## Обзор

Система интеграции AI-агента с 1C для автоматизации продаж строительных материалов. Агент использует ReAct (Reasoning + Acting) паттерн с набором инструментов (tools) для работы с каталогом товаров в реальном времени.

## 1C API Endpoints

### Базовый URL
```
http://172.16.77.34/stroyast_test/hs/Ai
```

### Аутентификация
```python
HTTPBasicAuth('Admin', '789654')
```

### 1. GET /GetGroups - Каталог товарных групп

**Назначение**: Получение структуры каталога - всех групп и номенклатуры в них (без остатков и цен)

**Метод**: `GET`

**Заголовки**:
```json
{
  "Content-Type": "application/json",
  "Accept": "application/json"
}
```

**Response**:
```json
{
  "groups": [
    {
      "название": "C класс",
      "номенклатура": "00-00023614",  // код группы
      "items": [
        {
          "номенклатура": "00-00010232",  // код товара
          "название": "Блок Хаус стр. сух. хв. 28х140х3000 класс С"
        }
      ]
    }
  ]
}
```

**Статистика**: ~30 групп, в каждой от 10 до 100+ товаров

---

### 2. POST /GetItems - Товары группы с ценами и остатками

**Назначение**: Получение списка товаров по кодам ГРУПП с ценами и доступностью (без детальных характеристик)

**Метод**: `POST`

**Заголовки**:
```json
{
  "Content-Type": "application/json; charset=utf-8"
}
```

**Request Body**:
```json
{
  "items": ["00-00023614", "00-00023605"]  // массив кодов ГРУПП
}
```

**Response**:
```json
{
  "items": [
    {
      "Наименование": "Блок Хаус стр. сух. хв. 28х140х3000 класс С",
      "Цена": 22000,
      "Код": "00-00010232",
      "Остаток": "По предзаказу"  // или конкретное число
    }
  ]
}
```

**Использование**: Быстрый просмотр товаров категории для фильтрации по цене/доступности

---

### 3. POST /GetDetailedItems - Детальная информация по товарам

**Назначение**: Получение полной информации по кодам НОМЕНКЛАТУРЫ (технические характеристики, упаковка, сроки)

**Метод**: `POST`

**Заголовки**:
```json
{
  "Content-Type": "application/json; charset=utf-8"
}
```

**Request Body**:
```json
{
  "items": ["00-00010232", "00-00009818"]  // массив кодов НОМЕНКЛАТУРЫ
}
```

**Response**:
```json
{
  "items": [
    {
      "Наименование": "Блок Хаус стр. сух. хв. 28х140х3000 класс С",
      "Цена": 22000,
      "Код": "",
      "Остаток": "По предзаказу",
      "Дополнительнаяедизмерения1": "м2",
      "Коэфдополнительнаяедизмерения1": "0,42",
      "Дополнительнаяедизмерения2": "м3",
      "Коэфдополнительнаяедизмерения2": "0,0118",
      "Толщина": "28",
      "Ширина": "140",
      "Длина": "3 000",
      "Сорт": "класс С",
      "Порода": "хвоя",
      "Видпиломатериала": "Блок Хаус",
      "Влажность": "сухой 12-14%",
      "Типобработки": "строганый",
      "Наименованиедлясайта": "Блок Хаус строганый сухой хвоя 28х140х3000 класс С",
      "Плотностькгм3Общие": "450",
      "Количествовм2Общие": "2,38",
      "Количествовм3Общие": "21,258",
      "СрокпроизводстваднОбщие": "7"
    }
  ]
}
```

**Использование**: Когда клиент интересуется конкретным товаром и нужны технические детали

---

## Tool Calling Pipeline для ReAct Agent

### Архитектура

```
Вопрос клиента
      ↓
┌─────────────────────────────────────────────────────────────┐
│  LangChain ReAct Agent (GPT-5-mini / Gemini 2.5-flash)      │
│  - Анализирует запрос                                        │
│  - Планирует последовательность вызовов tools               │
│  - Делает reasoning перед каждым action                     │
└─────────────────────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────────────────┐
│  Tool Selection & Execution                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │ search_     │  │ get_category │  │ get_product_       │ │
│  │ product_    │  │ _items       │  │ details            │ │
│  │ groups      │  │              │  │                    │ │
│  └─────────────┘  └──────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
      ↓
  1C API calls
      ↓
Структурированный ответ клиенту
```

### Набор Tools

#### Tool 1: `search_product_groups`

**Описание для агента**:
```
Ищет группы товаров и номенклатуру внутри них по ключевым словам.
Используй для начального поиска когда клиент спрашивает о категории товаров или конкретном виде материала.

Входные параметры:
- keywords: str - ключевые слова для поиска (например: "вагонка", "блок хаус", "евровагонка")
- exact_match: bool = False - точное совпадение или частичное

Возвращает:
- List[Group] где Group = { group_name, group_code, matching_items: [{ item_code, item_name }] }
```

**Реализация**:
```python
async def search_product_groups(keywords: str, exact_match: bool = False) -> List[Dict]:
    """
    1. Вызывает GET /GetGroups
    2. Фильтрует группы и товары по keywords (группа подходит если keywords в названии группы ИЛИ в названии хотя бы одного товара)
    3. Возвращает релевантные группы с отфильтрованным списком товаров
    """
    pass
```

**Пример использования**:
```
Client: "Какая у вас есть вагонка?"
Agent Thought: Клиент спрашивает о категории товаров "вагонка"
Agent Action: search_product_groups(keywords="вагонка")
Observation: Найдено 3 группы: "C класс" (12 товаров), "АВ класс" (8 товаров), ...
```

---

#### Tool 2: `get_category_items`

**Описание для агента**:
```
Получает товары из указанных групп с ценами и остатками.
Используй когда клиент уже выбрал категорию и хочет увидеть цены или наличие.

Входные параметры:
- group_codes: List[str] - коды групп из search_product_groups
- filter_available_only: bool = False - показать только доступные товары
- max_price: Optional[float] = None - максимальная цена

Возвращает:
- List[Product] где Product = { code, name, price, availability }
```

**Реализация**:
```python
async def get_category_items(
    group_codes: List[str],
    filter_available_only: bool = False,
    max_price: Optional[float] = None
) -> List[Dict]:
    """
    1. Вызывает POST /GetItems с group_codes
    2. Применяет фильтры (availability, price)
    3. Сортирует по цене
    4. Возвращает список товаров
    """
    pass
```

**Пример использования**:
```
Client: "Покажите вагонку класса С до 15000 рублей что есть в наличии"
Agent Thought: Нужна вагонка класса С, с фильтрами по цене и наличию
Agent Action: search_product_groups(keywords="вагонка класс С")
Observation: Группа "C класс" code=00-00023614
Agent Action: get_category_items(group_codes=["00-00023614"], filter_available_only=True, max_price=15000)
Observation: Найдено 5 товаров...
```

---

#### Tool 3: `get_product_details`

**Описание для агента**:
```
Получает детальную техническую информацию по конкретным товарам.
Используй когда клиент спрашивает о характеристиках, размерах, сроках производства.

Входные параметры:
- item_codes: List[str] - коды номенклатуры

Возвращает:
- List[DetailedProduct] с полями: code, name, price, availability, dimensions (толщина, ширина, длина), материал, влажность, сорт, срок_производства, коэффициенты_пересчета_единиц
```

**Реализация**:
```python
async def get_product_details(item_codes: List[str]) -> List[Dict]:
    """
    1. Вызывает POST /GetDetailedItems с item_codes
    2. Форматирует ответ в читаемый вид
    3. Возвращает детальную информацию
    """
    pass
```

**Пример использования**:
```
Client: "Какие характеристики у Блок Хаус 28х140х3000?"
Agent Thought: Клиент спрашивает о конкретных характеристиках товара
Agent Action: search_product_groups(keywords="Блок Хаус 28х140х3000")
Observation: Найден товар code=00-00010232
Agent Action: get_product_details(item_codes=["00-00010232"])
Observation: Толщина: 28мм, Ширина: 140мм, Длина: 3000мм, Влажность: сухой 12-14%, Срок производства: 7 дней...
```

---

### Decision Tree: Когда использовать какой tool

```
┌─ Клиент НЕ знает что хочет / спрашивает категорию?
│  └─> search_product_groups(keywords) → показать категории
│
├─ Клиент выбрал категорию / спрашивает цены/наличие?
│  └─> get_category_items(group_codes, фильтры) → список с ценами
│
├─ Клиент спрашивает о характеристиках конкретного товара?
│  └─> get_product_details(item_codes) → детальная информация
│
└─ Сложный запрос (например "вагонка 3м в наличии до 10к")?
   └─> CHAIN:
       1. search_product_groups(keywords="вагонка 3м")
       2. get_category_items(group_codes, filter_available_only=True, max_price=10000)
       3. (опционально) get_product_details для топ-3 вариантов
```

---

## Оптимизация производительности

### Кэширование GetGroups

**Проблема**: GET /GetGroups возвращает ~30 групп с сотнями товаров (большой JSON ~90KB)

**Решение**:
1. Кэшировать результат GET /GetGroups в Redis с TTL 1 час
2. `search_product_groups` работает по кэшу
3. Инвалидация кэша:
   - По истечению TTL (автоматически)
   - По webhook от 1C при изменении структуры каталога (будущее)
   - Ручная кнопка в CRM админке

```python
# backend/tools/catalog_cache.py
class CatalogCache:
    def __init__(self, redis_client, ttl=3600):
        self.redis = redis_client
        self.ttl = ttl
        self.cache_key = "1c:catalog:groups"

    async def get_groups(self) -> Dict:
        cached = await self.redis.get(self.cache_key)
        if cached:
            return json.loads(cached)

        # Fetch from 1C
        groups = await fetch_groups_from_1c()
        await self.redis.setex(self.cache_key, self.ttl, json.dumps(groups))
        return groups

    async def invalidate(self):
        await self.redis.delete(self.cache_key)
```

### Batch requests

Когда агент решает запросить детали по нескольким товарам - делать один запрос массивом, а не N запросов:

```python
# ✅ GOOD
get_product_details(item_codes=["00-00010232", "00-00009818", "00-00010223"])

# ❌ BAD
get_product_details(item_codes=["00-00010232"])
get_product_details(item_codes=["00-00009818"])
get_product_details(item_codes=["00-00010223"])
```

---

## Интеграция в существующий backend

### Файловая структура

```
backend/
├── tools/
│   ├── catalog_tools.py          # Новые 1C tools
│   ├── catalog_cache.py          # Кэш каталога
│   └── ...существующие tools...
├── services/
│   ├── onec_client.py            # HTTP клиент для 1C API
│   └── ...
├── agent.py                       # Обновить: добавить catalog_tools
└── ...
```

### 1. HTTP Client для 1C

```python
# backend/services/onec_client.py
import httpx
from typing import List, Dict
from requests.auth import HTTPBasicAuth

class OneCClient:
    def __init__(self):
        self.base_url = "http://172.16.77.34/stroyast_test/hs/Ai"
        self.auth = HTTPBasicAuth('Admin', '789654')
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    async def get_groups(self) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/GetGroups",
                auth=self.auth,
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def get_items(self, group_codes: List[str]) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/GetItems",
                json={"items": group_codes},
                auth=self.auth,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=30.0
            )
            response.encoding = response.charset_encoding or 'utf-8'
            response.raise_for_status()
            return response.json()

    async def get_detailed_items(self, item_codes: List[str]) -> Dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/GetDetailedItems",
                json={"items": item_codes},
                auth=self.auth,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                timeout=30.0
            )
            response.encoding = response.charset_encoding or 'utf-8'
            response.raise_for_status()
            return response.json()
```

### 2. Catalog Tools

```python
# backend/tools/catalog_tools.py
from langchain.tools import tool
from typing import List, Dict, Optional
from services.onec_client import OneCClient
from tools.catalog_cache import CatalogCache

onec = OneCClient()
cache = CatalogCache(redis_client)

@tool
async def search_product_groups(keywords: str, exact_match: bool = False) -> List[Dict]:
    """
    Ищет группы товаров и номенклатуру по ключевым словам.

    Args:
        keywords: Ключевые слова для поиска (например "вагонка", "блок хаус")
        exact_match: Точное совпадение (True) или частичное (False)

    Returns:
        Список групп с отфильтрованными товарами
    """
    # Получить из кэша или 1C
    catalog = await cache.get_groups()

    keywords_lower = keywords.lower()
    results = []

    for group in catalog.get('groups', []):
        matching_items = []
        group_matches = keywords_lower in group['название'].lower()

        # Ищем в товарах группы
        for item in group.get('items', []):
            item_name_lower = item['название'].lower()
            if exact_match:
                if keywords_lower == item_name_lower:
                    matching_items.append(item)
            else:
                if keywords_lower in item_name_lower:
                    matching_items.append(item)

        # Включаем группу если совпадение в названии ИЛИ есть подходящие товары
        if group_matches or matching_items:
            results.append({
                'group_name': group['название'],
                'group_code': group['номенклатура'],
                'matching_items': matching_items if matching_items else group['items'][:10]  # лимит 10 для краткости
            })

    return results

@tool
async def get_category_items(
    group_codes: List[str],
    filter_available_only: bool = False,
    max_price: Optional[float] = None
) -> List[Dict]:
    """
    Получает товары из групп с ценами и остатками.

    Args:
        group_codes: Список кодов групп
        filter_available_only: Только товары в наличии
        max_price: Максимальная цена

    Returns:
        Список товаров с ценами и остатками
    """
    data = await onec.get_items(group_codes)
    items = data.get('items', [])

    # Фильтрация
    if filter_available_only:
        items = [
            item for item in items
            if item.get('Остаток') and item['Остаток'] != 'По предзаказу'
        ]

    if max_price:
        items = [
            item for item in items
            if item.get('Цена') and float(item['Цена']) <= max_price
        ]

    # Сортировка по цене
    items.sort(key=lambda x: float(x.get('Цена', 0)))

    return items

@tool
async def get_product_details(item_codes: List[str]) -> List[Dict]:
    """
    Получает детальную информацию по товарам (характеристики, размеры, сроки).

    Args:
        item_codes: Список кодов номенклатуры

    Returns:
        Детальная информация по каждому товару
    """
    data = await onec.get_detailed_items(item_codes)
    return data.get('items', [])
```

### 3. Регистрация в Agent

```python
# backend/agent.py
from tools.catalog_tools import (
    search_product_groups,
    get_category_items,
    get_product_details
)

def create_agent():
    tools = [
        # ... существующие tools ...
        search_product_groups,
        get_category_items,
        get_product_details,
    ]

    # ... остальной код создания агента ...
```

---

## Примеры диалогов

### Пример 1: Простой поиск

```
User: Какая у вас есть вагонка?

Agent Thought: Клиент спрашивает о категории "вагонка", нужно найти все группы с вагонкой
Agent Action: search_product_groups(keywords="вагонка")
Observation: Найдено 2 группы:
  - "C класс" (код: 00-00023614) - 8 товаров с вагонкой
  - "АВ класс" (код: 00-00023569) - 4 товара с вагонкой

Agent: У нас есть вагонка в двух классах качества:
- Класс С - более экономичный вариант (8 позиций)
- Класс АВ - премиум качество (4 позиции)

Какой класс вас интересует?
```

### Пример 2: Поиск с фильтрами

```
User: Нужна евровагонка 6 метров в наличии до 12000

Agent Thought: Сложный запрос - ищем евровагонку 6м, с фильтрами по наличию и цене
Agent Action: search_product_groups(keywords="евровагонка 6000")
Observation: Найдено в группах "C класс" и "АВ класс"

Agent Action: get_category_items(
  group_codes=["00-00023614", "00-00023569"],
  filter_available_only=True,
  max_price=12000
)
Observation:
  - Евровагонка 12,5х90х6000 класс С, 11500₽, в наличии 15м³
  - Евровагонка 12,5х90х6000 класс АВ, 11800₽, в наличии 8м³

Agent: Нашел 2 варианта евровагонки 6 метров в вашем бюджете:

1. Класс С - 11 500₽ (в наличии 15м³)
2. Класс АВ - 11 800₽ (в наличии 8м³)

Класс АВ чуть дороже, но имеет меньше сучков и более равномерный цвет. Что выбираем?
```

### Пример 3: Технические характеристики

```
User: Расскажи подробнее про Блок Хаус 28х140х6000

Agent Thought: Запрос о характеристиках конкретного товара
Agent Action: search_product_groups(keywords="Блок Хаус 28х140х6000")
Observation: Найден код: 00-00009817

Agent Action: get_product_details(item_codes=["00-00009817"])
Observation: {
  "Наименование": "Блок Хаус стр. сух. хв. 28х140х6000 класс АВ",
  "Цена": 32000,
  "Остаток": "В наличии",
  "Толщина": "28",
  "Ширина": "140",
  "Длина": "6 000",
  "Влажность": "сухой 12-14%",
  "Порода": "хвоя",
  "Сорт": "класс АВ",
  "СрокпроизводстваднОбщие": "7",
  "Количествовм2Общие": "2,38",
  "Дополнительнаяедизмерения1": "м2",
  "Коэфдополнительнаяедизмерения1": "0,84"
}

Agent: Блок Хаус 28х140х6000 класс АВ:

**Характеристики:**
- Размеры: 28мм (толщина) × 140мм (ширина) × 6000мм (длина)
- Порода: хвоя
- Влажность: 12-14% (сухой строганый)
- Класс качества: АВ (премиум)

**Цена и наличие:**
- 32 000₽ за м³
- В наличии
- Срок производства под заказ: 7 дней

**Упаковка:**
- В 1м³ примерно 2,38 м² покрытия
- Коэффициент пересчета в м²: 0,84

Сколько вам нужно?
```

---

## TODO List для реализации

### Phase 1: Core Integration (1-2 дня)
- [ ] Создать `OneCClient` в `backend/services/onec_client.py`
- [ ] Написать unit тесты для OneCClient
- [ ] Создать `CatalogCache` в `backend/tools/catalog_cache.py`
- [ ] Создать три tool функции в `backend/tools/catalog_tools.py`
- [ ] Интегрировать tools в `agent.py`
- [ ] Добавить переменные окружения для 1C (URL, credentials) в `.env`

### Phase 2: Testing & Refinement (1 день)
- [ ] E2E тесты с реальными запросами к 1C
- [ ] Тестирование ReAct цепочек (логирование reasoning агента)
- [ ] Оптимизация промптов для tools (чтобы агент правильно выбирал инструменты)
- [ ] Обработка ошибок (таймауты 1C, недоступность API)

### Phase 3: Admin UI & Monitoring (1 день)
- [ ] Кнопка "Сбросить кэш каталога" в CRM админке (`frontend/app/sales-manager`)
- [ ] Метрики в dashboard: количество запросов к 1C, cache hit rate
- [ ] Логирование всех tool calls в БД для аналитики
- [ ] Rate limiting для 1C API (если нужно)

### Phase 4: Advanced Features (опционально)
- [ ] Webhook от 1C для автоматической инвалидации кэша при изменении каталога
- [ ] Интеграция остатков в реальном времени (если 1C поддерживает)
- [ ] Создание корзины и формирование заказа через 1C API
- [ ] История просмотренных товаров клиента (персонализация)

---

## Безопасность и ограничения

### Rate Limiting
1C может не выдержать большую нагрузку:
- Кэширование GET /GetGroups (обязательно)
- Ограничение: max 100 запросов/минуту к POST endpoints
- Использовать async + semaphore для контроля параллелизма

### Аутентификация
Текущие креды (`Admin/789654`) захардкожены в примере - переместить в environment variables:

```bash
# .env
ONEC_BASE_URL=http://172.16.77.34/stroyast_test/hs/Ai
ONEC_USERNAME=Admin
ONEC_PASSWORD=789654
```

### Обработка ошибок
```python
try:
    data = await onec.get_items(group_codes)
except httpx.TimeoutException:
    return {"error": "1C временно недоступна, попробуйте позже"}
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        return {"error": "Ошибка аутентификации с 1C"}
    raise
```

---

## Метрики успеха

1. **Точность ответов**: агент дает корректную информацию из 1C в 95%+ случаев
2. **Скорость ответа**: средний ответ на запрос < 3 секунд
3. **Cache Hit Rate**: 80%+ запросов используют кэш (только 20% идут в 1C)
4. **Конверсия**: % диалогов, которые приводят к созданию лида
5. **Уменьшение нагрузки на менеджеров**: % запросов, обработанных AI без эскалации

---

## Дальнейшее развитие

### Расширение функционала 1C API
- **POST /CreateOrder** - создание заказа напрямую из чата
- **GET /CheckAvailability** - проверка актуальных остатков в реальном времени
- **POST /ReserveItems** - резервирование товара на N часов

### Улучшение AI агента
- Fine-tuning на исторических диалогах менеджеров
- Multimodal: клиент присылает фото - агент определяет тип материала
- Проактивные предложения: "Вы смотрели вагонку, возможно вам понадобятся крепежи?"

---

**Дата создания**: 2026-01-18
**Версия**: 1.0
**Автор**: AI Integration Team
