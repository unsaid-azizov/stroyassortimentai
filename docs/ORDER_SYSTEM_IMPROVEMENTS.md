# Улучшения системы оформления заказов

**Дата:** 2026-01-20
**Версия:** 2.0

## Обзор изменений

Проведена полная переработка системы оформления заказов с автоматическим расчетом цен из 1С и улучшенным форматированием вывода информации.

---

## 1. Убран остаток из BM25 поиска

### Что изменилось:
- **До:** `search_products_tool` показывал код, цену И остаток из CSV
- **После:** Показывает только код и цену из CSV

### Почему:
Остатки в CSV могут быть устаревшими. Актуальные остатки получаются ТОЛЬКО через `get_product_live_details` из 1С API в реальном времени.

### Файлы:
- [backend/tools/product_search_bm25.py](../backend/tools/product_search_bm25.py#L262-L264)

```python
# Основная информация
output += f"   Код: {item.get('Код', 'N/A')}\n"
output += f"   Цена: {item.get('Цена', 'N/A')} руб.\n"
# Остаток удален - только через get_product_live_details!
```

---

## 2. Переработаны tools для заказов

### 2.1. `collect_order_info` - Оформление КОНКРЕТНОГО заказа

**Когда использовать:**
- Клиент ТОЧНО определился с товарами
- Есть конкретные позиции с кодами
- Клиент готов оформить заказ

**Что делает автоматически:**
1. Принимает структуру заказа с кодами товаров и количеством
2. **Запрашивает актуальные цены/остатки из 1С API**
3. **Считает итоги:** line_total (qty × price), subtotal, total
4. Отправляет HTML-письмо с полным расчетом
5. **Сохраняет в БД** (`order_submissions`) для дашборда

**Структура OrderInfo:**
```python
class OrderLineItem(BaseModel):
    product_code: str  # ОБЯЗАТЕЛЬНО - код из search_products_tool
    product_name: str
    quantity: float
    unit: Optional[str]  # "шт", "м³", "м²"
    unit_price: Optional[float]  # Заполнится автоматически из 1С
    line_total: Optional[float]  # Посчитается автоматически
    availability: Optional[str]  # Заполнится из 1С
    comment: Optional[str]  # Сорт, влажность, требования

class OrderInfo(BaseModel):
    client_name: str
    client_contact: str
    items: List[OrderLineItem]
    pricing: Optional[OrderPricing]  # Итоги посчитаются автоматически
    delivery_address: Optional[str]
    delivery_method: Optional[str]
    additional_comments: Optional[str]
    dialogue_summary: Optional[DialogueSummary]
```

**Workflow:**
```
1. Агент: search_products_tool("вагонка штиль")
   → получает код "00-00010232"

2. Агент: get_product_live_details("00-00010232")
   → проверяет актуальную цену и остаток

3. Агент: collect_order_info(
     client_name="Иван",
     client_contact="+7...",
     items=[{
       product_code: "00-00010232",
       product_name: "Вагонка штиль 13х115х6000",
       quantity: 50,
       unit: "шт"
     }]
   )

4. Система:
   - Запрашивает цену из 1С: 450 руб/шт
   - Считает: 50 × 450 = 22,500 руб
   - Отправляет письмо с расчетом
   - Сохраняет в order_submissions
```

**Обработка ошибок:**
```python
# Если нет product_code
→ Возвращает: "Чтобы оформить заказ, мне нужны коды номенклатуры..."

# Если 1С API недоступен
→ Заказ отправится, но без автоматического расчета

# Если email не отправился
→ Заказ все равно сохранится в БД со статусом FAILED
```

### 2.2. `call_manager` - Эскалация к человеку

**Когда использовать:**
- Клиент в раздумьях, нужна консультация
- Очень сложный технический вопрос
- Специфические условия (скидки, индивидуальный расчет)
- Клиент явно просит поговорить с человеком

**Отличия от `collect_order_info`:**
- Не требует обязательных кодов товаров
- Может содержать частичную информацию
- Фокус на саммари диалога и рекомендациях менеджеру
- Опциональное поле `order` - если есть черновик заказа

**Структура ManagerHandover:**
```python
class ManagerHandover(BaseModel):
    client_summary: str  # Краткое описание ситуации
    dialogue_summary: Optional[DialogueSummary]
    priority: str  # "низкий", "средний", "высокий"
    main_topic: str  # Тема 1-2 слова
    client_name: str
    client_contact: Optional[str]
    order: Optional[OrderInfo]  # Черновик заказа если есть
```

### 2.3. Удалены ссылки на несуществующие tools

**Было:**
```python
# В docstring collect_order_info
"- `search_1c_products` (для поиска по группам)"
"- `get_product_details` (для проверки конкретных товаров)"
```

**Стало:**
```python
# Правильные tools
"- `search_products_tool` (для поиска товаров с фильтрами)"
"- `get_product_live_details` (для проверки актуальной цены и остатков)"
```

**Файлы:**
- [backend/tools/sales_tools.py](../backend/tools/sales_tools.py) - полностью переписан

---

## 3. Улучшен `search_company_info`

### Что изменилось:
- **До:** Возвращал сырой JSON
- **После:** Рекурсивное форматирование в читаемый текст

### Новая функция форматирования:

```python
def format_section_content(content: Any, indent: int = 0) -> str:
    """
    Рекурсивно форматирует содержимое раздела:
    - dict → "**Заголовок:**\n  значение"
    - list → "- элемент1\n- элемент2"
    - str → чистый текст
    """
```

### Пример вывода:

**До:**
```json
{"address": "Мытищи, Осташковское шоссе 14", "phone": "+7 (499) 302-55-01"}
```

**После:**
```markdown
## Контакты

**Address:**
  Мытищи, Осташковское шоссе 14

**Phone:**
  +7 (499) 302-55-01

Подробнее: https://stroyassort.ru/contacts

---
```

### Фильтрация по релевантности:
- Первый результат: всегда показывается
- 2-3 результаты: только если score ≥ 0.5

### Файлы:
- [backend/tools/search_company_info.py](../backend/tools/search_company_info.py#L40-L88)

---

## 4. Интеграция с 1С API

### Функция `_fetch_products_from_1c_sync`

Переиспользует логику из `get_product_live_details`:

```python
def _fetch_products_from_1c_sync(product_codes: List[str]) -> Dict[str, dict]:
    """
    Синхронная версия получения данных из 1С.
    Returns: {code: {"price": float|None, "stock": str|None}}
    """
    from tools.get_product_live_details import fetch_live_product_details

    items = fetch_live_product_details(product_codes)
    # Парсим результат в нужный формат
```

### Функция `enrich_and_calculate_order_sync`

```python
def enrich_and_calculate_order_sync(order: OrderInfo) -> OrderInfo:
    """
    1. Проверяет что у всех позиций есть product_code
    2. Запрашивает данные из 1С
    3. Заполняет unit_price и availability
    4. Считает line_total, subtotal, total
    """
```

### Валидация:
```python
# Проверка наличия кодов
missing_codes = [it.product_name for it in order.items if not it.product_code]
if missing_codes:
    raise ValueError(
        "Для расчёта заказа нужны коды номенклатуры (product_code) "
        f"по каждой позиции. Нет кода у: {', '.join(missing_codes[:5])}"
    )
```

---

## 5. База данных - таблица `order_submissions`

### Схема:
```sql
CREATE TABLE order_submissions (
    id UUID PRIMARY KEY,
    client_name VARCHAR(255),
    client_contact VARCHAR(255),
    currency VARCHAR(10) DEFAULT 'RUB',
    subtotal FLOAT,
    total FLOAT,
    items_count INTEGER,
    status VARCHAR(32),  -- 'SENT' | 'FAILED'
    error TEXT,
    payload JSON,  -- Полная структура OrderInfo
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Сохранение:
```python
async def _persist_order_submission(order: OrderInfo, status: str, error: Optional[str] = None):
    """
    Сохраняет заказ в БД независимо от успеха отправки email.
    Используется для аналитики в дашборде.
    """
```

### Статусы:
- **SENT** - Email успешно отправлен
- **FAILED** - Ошибка отправки email (но заказ сохранен)

---

## 6. Корнер-кейсы

### 6.1. Агент вызвал `collect_order_info` без кодов

```python
# Ошибка валидации
return (
    "Чтобы оформить заказ, мне нужны коды номенклатуры по каждой позиции. "
    "Давай сначала подберём конкретные товары через search_products_tool..."
)
```

### 6.2. 1С API недоступен

```python
# Логируем ошибку, но не падаем
logger.warning(f"Failed to fetch prices from 1C: {repr(e)}")
return {}  # Пустой словарь, цены останутся None
```

Заказ все равно отправится, но без автоматического расчета.

### 6.3. Email не отправился

```python
try:
    await aiosmtplib.send(...)
    await _persist_order_submission(order, status="SENT")
    return "Благодарю, ваша заявка отправлена..."
except Exception as e:
    logger.error(f"Order error: {e}")
    await _persist_order_submission(order, status="FAILED", error=str(e))
    return "Заявка принята, менеджер увидит ваше сообщение в чате."
```

Заказ сохраняется в БД со статусом FAILED - менеджер увидит в дашборде.

### 6.4. Клиент в раздумьях

Агент должен использовать `call_manager` вместо `collect_order_info`:

```python
# Не готов оформить → эскалация
call_manager(
    client_summary="Клиент интересуется вагонкой, но еще думает...",
    priority="средний",
    main_topic="Вагонка",
    client_name="Иван",
    client_contact="+7..."
)
```

---

## 7. Изменения в промпте агента

Добавлены детальные инструкции в [backend/data/updated_prompt.txt](../backend/data/updated_prompt.txt):

### Секция "ДОСТУПНЫЕ ИНСТРУМЕНТЫ":
```text
- search_products_tool: УМНЫЙ ПОИСК товаров с фильтрами
- get_product_live_details: получение АКТУАЛЬНОЙ цены и остатка по коду
- collect_order_info: используй, когда клиент готов оставить заявку
- call_manager: позови человека, если вопрос слишком специфичный
```

### Новая секция "ДЕТАЛЬНОЕ ОПИСАНИЕ ПОИСКА ТОВАРОВ":
```text
ПАРАМЕТРЫ ПОИСКА:
1. query - название товара
2. material_type - Вид пиломатериала (Вагонка, Брус, Доска...)
3. wood_species - Порода дерева (хвоя, сосна, ель...)
4. grade - Сорт (А, АВ, В, С)
5. moisture - Влажность ("сухой 12-14%", "естественная влажность")
6. treatment - Тип обработки (строганый, нестроганый)
7. Размеры - thickness/width/length в миллиметрах
8. Коммерческие фильтры - price, in_stock_only

ИНФОРМАЦИЯ О ТОВАРЕ, КОТОРУЮ ТЫ ПОЛУЧИШЬ:
- Код, Цена (из CSV)
- Порода, Влажность, Сорт/Класс
- Размеры, Плотность
- Количество в м²/м³
- Срок производства
- Популярность
```

---

## 8. Текущие активные tools

Список tools доступных агенту ([backend/tools/__init__.py](../backend/tools/__init__.py)):

```python
__all__ = [
    "search_company_info",     # BM25 поиск по базе знаний
    "call_manager",            # Вызов менеджера (эскалация)
    "collect_order_info",      # Оформление конкретного заказа
    "search_products_tool",    # BM25 поиск товаров (CSV)
    "get_product_live_details",  # Актуальные цены из 1С API
]
```

**Удалены старые:**
- ~~search_1c_products~~
- ~~get_product_details~~

---

## 9. Тестирование

### End-to-end сценарий:

1. **Клиент:** "Нужна вагонка штиль сухая"
   ```
   Агент: search_products_tool(query="вагонка штиль", moisture="сухой 12-14%")
   → Находит 5 товаров с кодами
   ```

2. **Клиент:** "Сколько стоит первая позиция?"
   ```
   Агент: get_product_live_details("00-00010232")
   → Цена: 450 руб/шт, Остаток: 200 шт
   ```

3. **Клиент:** "Беру 50 штук"
   ```
   Агент: collect_order_info(
     client_name="...",
     client_contact="...",
     items=[{
       product_code: "00-00010232",
       quantity: 50,
       unit: "шт"
     }]
   )
   → Система запрашивает цену из 1С
   → Считает: 50 × 450 = 22,500 руб
   → Отправляет письмо
   → Сохраняет в БД
   ```

4. **Проверка в дашборде:**
   ```
   SELECT * FROM order_submissions ORDER BY created_at DESC LIMIT 1;

   | client_name | items_count | subtotal | total  | status |
   |-------------|-------------|----------|--------|--------|
   | Иван        | 1           | 22500.00 | 22500  | SENT   |
   ```

---

## 10. Применение изменений

### Пересборка контейнера:
```bash
docker compose up --build -d api
```

### Проверка логов:
```bash
docker logs api --tail 50
```

Должно быть:
```
Промпт обновлен (ID: ..., версия: 4)
База знаний обновлена
Application startup complete.
Uvicorn running on http://0.0.0.0:5537
```

### Проверка БД:
```bash
docker exec postgres psql -U said -d said_crm -c "\d order_submissions"
```

---

## Итоги

✅ **Убран** остаток из BM25 (только актуальные данные из 1С)
✅ **Переработаны** tools для заказов (автоматический расчет)
✅ **Удалены** ссылки на несуществующие функции
✅ **Улучшен** вывод search_company_info (форматированный текст)
✅ **Добавлена** интеграция с 1С для автоматического расчета цен
✅ **Реализовано** сохранение заказов в БД
✅ **Обработаны** корнер-кейсы и ошибки

**Следующий шаг:** End-to-end тестирование через Telegram бота.
