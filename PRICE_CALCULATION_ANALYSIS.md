# Комплексный анализ системы расчета цен

## Текущая архитектура (с ошибкой)

### 1. Поток данных от клиента до расчета

```
Клиент → Агент → search_products → get_product_live_details → collect_order_info → 1C API → Расчет
```

#### Шаг 1: Клиент делает запрос
```
Пример: "Хочу купить 10 штук вагонки штиль 13×115×6000 класс АВ"
```

#### Шаг 2: Агент ищет товар
- Инструмент: `search_products_tool` (BM25 поиск)
- Результат: Код товара, например "00-00010232"

#### Шаг 3: Агент получает актуальную цену
- Инструмент: `get_product_live_details`
- API: `GetDetailedItems` → 1C
- Получаем:
  ```json
  {
    "Код": "00-00010232",
    "Наименование": "Вагонка штиль 13×115×6000 класс АВ",
    "Цена": 500,
    "ЕдИзмерения": "м2 (1.449275 шт)",
    "Остаток": "В наличии"
  }
  ```

#### Шаг 4: Агент формирует заказ
- Инструмент: `collect_order_info`
- Данные:
  ```python
  OrderLineItem(
    product_code="00-00010232",
    product_name="Вагонка штиль 13×115×6000 класс АВ",
    quantity=10,
    unit="шт",
    unit_price=None,  # Заполнится из 1C
    line_total=None   # Посчитается
  )
  ```

#### Шаг 5: Обогащение данными из 1C
- Функция: `enrich_and_calculate_order_sync()`
- Вызывает: `_fetch_products_from_1c_sync()`
- Получает из 1C:
  ```python
  {
    "Цена": 500,           # ₽/м²
    "Остаток": "В наличии"
  }
  ```
- ❌ **ПРОБЛЕМА:** Не получает поле `ЕдИзмерения`!

#### Шаг 6: Расчет итога (НЕПРАВИЛЬНО)
- Функция: `_calculate_order_totals()`
- Формула:
  ```python
  line_total = quantity × unit_price
  line_total = 10 × 500 = 5000 ₽  # ❌ НЕПРАВИЛЬНО!
  ```

### 2. ПРАВИЛЬНЫЙ расчет (как должно быть)

```python
# Данные из 1C:
price = 500           # ₽/м²
unit = "м2 (1.449275 шт)"  # В 1 м² = 1.449 штук

# Клиент заказал:
quantity = 10         # штук

# Парсим единицу:
base_unit, pieces_per_unit = parse_unit(unit)
# base_unit = "м2"
# pieces_per_unit = 1.449275

# Считаем цену за штуку:
price_per_piece = price / pieces_per_unit
# price_per_piece = 500 / 1.449275 = 345 ₽/шт

# Итого:
line_total = quantity × price_per_piece
# line_total = 10 × 345 = 3450 ₽  # ✅ ПРАВИЛЬНО!
```

**Разница:** 5000 ₽ vs 3450 ₽ = **переплата 45%**

---

## Проблемы в текущей реализации

### Проблема 1: `_fetch_products_from_1c_sync()` не получает `ЕдИзмерения`

**Файл:** `backend/tools/sales_tools.py:163-196`

```python
def _fetch_products_from_1c_sync(product_codes: List[str]) -> Dict[str, dict]:
    items = fetch_live_product_details(product_codes)
    out: Dict[str, dict] = {}

    for item in items:
        code = item.get("Код")
        price = item.get("Цена")
        stock = item.get("Остаток")

        out[code] = {
            "price": float(price) if price else None,
            "stock": str(stock) if stock else None,
            # ❌ НЕТ ПОЛЯ "unit"!
        }

    return out
```

**Решение:** Добавить получение `ЕдИзмерения`:
```python
out[code] = {
    "price": float(price) if price else None,
    "stock": str(stock) if stock else None,
    "unit": item.get("ЕдИзмерения"),  # ✅ Добавляем
}
```

### Проблема 2: `enrich_and_calculate_order_sync()` не использует единицы

**Файл:** `backend/tools/sales_tools.py:231-271`

```python
for it in order.items:
    p = products.get(it.product_code)

    # Заполняем только цену
    if it.unit_price is None and p.get("price"):
        it.unit_price = p["price"]  # ❌ Берем цену как есть

    if p.get("stock"):
        it.availability = f"{p['stock']}"

    # ❌ НЕ ПРОВЕРЯЕМ единицы измерения!
```

**Решение:** Добавить конвертацию:
```python
from utils.price_calculator import parse_unit, calculate_price_per_piece

for it in order.items:
    p = products.get(it.product_code)

    # Получаем единицу из 1C
    product_unit = p.get("unit", "шт")
    base_unit, pieces_per_unit = parse_unit(product_unit)

    # Заполняем правильную цену
    if it.unit_price is None and p.get("price"):
        base_price = p["price"]

        # Если клиент заказал в штуках, а цена в м3/м2
        if it.unit and it.unit.lower() in ["шт", "штук", "штука"]:
            if pieces_per_unit and pieces_per_unit > 0:
                it.unit_price = base_price / pieces_per_unit  # ✅ Цена за штуку
            else:
                it.unit_price = base_price
        else:
            it.unit_price = base_price
```

### Проблема 3: `price_calculator.py` не используется

**Факт:** Модуль создан, протестирован, но нигде не импортирован!

**Решение:** Интегрировать в `sales_tools.py`

---

## План исправления

### Этап 1: Обновить `_fetch_products_from_1c_sync()`
- ✅ Добавить получение `ЕдИзмерения` из API
- ✅ Вернуть поле `unit` в результате

### Этап 2: Интегрировать `price_calculator.py`
- ✅ Импортировать `parse_unit`, `calculate_price_per_piece`
- ✅ Использовать в `enrich_and_calculate_order_sync()`

### Этап 3: Обновить логику расчета
- ✅ Парсить единицу из 1C
- ✅ Конвертировать цену в нужную единицу
- ✅ Логировать расчеты для отладки

### Этап 4: Тестирование
- ✅ Создать тестовый скрипт
- ✅ Проверить на реальных данных
- ✅ Убедиться что конвертация работает

---

## Сценарии конвертации

### Сценарий 1: Клиент заказывает в ШТ, цена в М³
```
Товар: Доска обрезн. 50×200×6000
1C: Цена = 15000 ₽/м³, ЕдИзмерения = "м3 (16 шт)"
Клиент: 10 шт

Расчет:
- В 1 м³ = 16 штук
- Цена за 1 шт = 15000 / 16 = 937.50 ₽
- Итого = 10 × 937.50 = 9375 ₽
```

### Сценарий 2: Клиент заказывает в ШТ, цена в М²
```
Товар: Вагонка штиль 13×140×3000
1C: Цена = 500 ₽/м², ЕдИзмерения = "м2 (2.380952 шт)"
Клиент: 20 шт

Расчет:
- В 1 м² = 2.38 штук
- Цена за 1 шт = 500 / 2.38 = 210 ₽
- Итого = 20 × 210 = 4200 ₽
```

### Сценарий 3: Клиент заказывает в М³, цена в М³
```
Товар: Брус 100×100×6000
1C: Цена = 17300 ₽/м³, ЕдИзмерения = "м3 (16.666667 шт)"
Клиент: 2.5 м³

Расчет:
- Единицы совпадают
- Итого = 2.5 × 17300 = 43250 ₽
```

### Сценарий 4: Клиент заказывает в ШТ, цена просто в ШТ
```
Товар: Плита OSB-3 9×1250×2500
1C: Цена = 580 ₽, ЕдИзмерения = "шт"
Клиент: 50 шт

Расчет:
- Единицы совпадают
- Итого = 50 × 580 = 29000 ₽
```

---

## Дополнительные улучшения

### 1. Логирование расчетов
Добавить детальное логирование для отладки:
```python
logger.info(f"Price conversion: {it.product_name}")
logger.info(f"  Base price: {base_price} {base_unit}")
logger.info(f"  Pieces per unit: {pieces_per_unit}")
logger.info(f"  Client ordered: {it.quantity} {it.unit}")
logger.info(f"  Final unit price: {it.unit_price}")
```

### 2. Валидация единиц
Добавить проверку совместимости:
```python
compatible_units = {
    "м3": ["м3", "шт"],
    "м2": ["м2", "шт"],
    "шт": ["шт"],
}
```

### 3. Обработка ошибок
```python
if it.unit not in compatible_units.get(base_unit, []):
    logger.warning(f"Unit mismatch: client wants {it.unit}, product priced in {base_unit}")
```

---

## Заключение

Текущая система НЕ учитывает единицы измерения при расчете цен, что приводит к **критическим ошибкам в ценообразовании**.

Готовый модуль `price_calculator.py` решает эту проблему, но не интегрирован в основной код.

**Следующий шаг:** Интегрировать `price_calculator.py` в `sales_tools.py` по описанному выше плану.
