"""
Тестовый скрипт для проверки нового search_products tool.

Проверяет:
1. Кэширование flat-каталога из GetGroups
2. Keyword search с нормализацией
3. Scoring по релевантности
4. Обогащение ценами из GetItems
"""
import asyncio
import sys
from pathlib import Path

# Добавляем backend в путь
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from tools.search_products import (
    normalize_query,
    extract_keywords,
    score_item,
    search_in_flat_catalog,
    get_flat_catalog,
    SearchProductsRequest,
    search_products
)


async def test_normalize_query():
    """Тест нормализации запросов."""
    print("=" * 80)
    print("1. ТЕСТ НОРМАЛИЗАЦИИ ЗАПРОСОВ")
    print("=" * 80)

    test_cases = [
        ("вагонка 6м", "вагонка 6000"),
        ("брус 150x150", "брус 150 150"),
        ("евровагонка 3 метра", "вагонка 3000"),
        ("блокхаус класс АВ", "блок хаус класс ав"),
    ]

    for input_query, expected in test_cases:
        result = normalize_query(input_query)
        status = "✅" if expected in result else "❌"
        print(f"{status} '{input_query}' → '{result}'")
        if expected not in result:
            print(f"   Ожидалось: '{expected}'")
    print()


async def test_extract_keywords():
    """Тест извлечения ключевых слов."""
    print("=" * 80)
    print("2. ТЕСТ ИЗВЛЕЧЕНИЯ КЛЮЧЕВЫХ СЛОВ")
    print("=" * 80)

    test_cases = [
        "вагонка 6 метров класс АВ",
        "есть ли брус 150x150?",
        "какая цена на евровагонку",
    ]

    for query in test_cases:
        keywords = extract_keywords(query)
        print(f"'{query}'")
        print(f"  → {keywords}")
    print()


async def test_scoring():
    """Тест scoring алгоритма."""
    print("=" * 80)
    print("3. ТЕСТ SCORING АЛГОРИТМА")
    print("=" * 80)

    keywords = ["вагонка", "6000", "ав"]

    items = [
        "Вагонка штиль стр. сух. хв. 13х115х6000 класс АВ",  # Полное совпадение
        "Вагонка штиль стр. сух. хв. 13х115х6000 класс С",   # Нет "АВ"
        "Вагонка штиль стр. сух. хв. 13х115х3000 класс АВ",  # Нет "6000"
        "Евровагонка стр. сух. хв. 12,5х90х6000 класс АВ",   # Частичное "вагонка"
        "Брус клееный стр. сух. хв. 150х150х6000 класс АВ",  # Нет "вагонка"
    ]

    scored = []
    for item_name in items:
        score = score_item(item_name, keywords)
        scored.append((score, item_name))

    scored.sort(reverse=True)

    print(f"Запрос: {keywords}\n")
    for score, name in scored:
        print(f"Score {score:5.1f}: {name}")
    print()


async def test_get_flat_catalog():
    """Тест получения flat-каталога."""
    print("=" * 80)
    print("4. ТЕСТ ПОЛУЧЕНИЯ FLAT-КАТАЛОГА")
    print("=" * 80)

    try:
        catalog = await get_flat_catalog()

        if catalog:
            print(f"✅ Каталог загружен: {len(catalog)} товаров")
            print(f"\nПример первого товара:")
            if catalog:
                first = catalog[0]
                print(f"  Код товара: {first.get('item_code')}")
                print(f"  Название: {first.get('item_name')}")
                print(f"  Группа: {first.get('group_name')} ({first.get('group_code')})")
        else:
            print("❌ Каталог пуст (возможно 1C недоступна)")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    print()


async def test_search_in_catalog():
    """Тест поиска в каталоге."""
    print("=" * 80)
    print("5. ТЕСТ ПОИСКА В КАТАЛОГЕ")
    print("=" * 80)

    queries = [
        "вагонка 6 метров",
        "брус 150x150",
        "блок хаус класс АВ",
    ]

    for query in queries:
        print(f"Запрос: '{query}'")
        try:
            results = await search_in_flat_catalog(query, limit=5)
            print(f"  Найдено: {len(results)} товаров")

            for i, item in enumerate(results[:3], 1):
                score = item.get('score', 0)
                name = item.get('item_name', '')
                print(f"  {i}. [{score:.1f}] {name[:60]}...")
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
        print()


async def test_search_products_tool():
    """Тест полного tool с ценами."""
    print("=" * 80)
    print("6. ТЕСТ SEARCH_PRODUCTS (ПОЛНЫЙ TOOL)")
    print("=" * 80)

    queries = [
        SearchProductsRequest(query="вагонка 6 метров", limit=5, include_prices=True),
        SearchProductsRequest(query="брус 150", limit=5, include_prices=False),
    ]

    for req in queries:
        print(f"Запрос: '{req.query}' (с ценами: {req.include_prices})")
        print("-" * 80)
        try:
            result = await search_products(req)
            print(result)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
        print()


async def main():
    """Запуск всех тестов."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "ТЕСТИРОВАНИЕ SEARCH_PRODUCTS" + " " * 30 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # Тесты без async
    await test_normalize_query()
    await test_extract_keywords()
    await test_scoring()

    # Тесты с async (требуют Redis и 1C)
    print("=" * 80)
    print("ТЕСТЫ С РЕАЛЬНЫМИ ДАННЫМИ (требуют Redis и 1C)")
    print("=" * 80)
    print()

    await test_get_flat_catalog()
    await test_search_in_catalog()
    await test_search_products_tool()

    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
