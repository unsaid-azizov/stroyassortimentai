"""
Тестовый скрипт для проверки всех tools.
Запуск: uv run python tools/test_tools.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from tools.search_company_info import search_company_info
from tools.search_1c_products import search_1c_products, get_product_details, Search1CProductsRequest, ProductFilters, GetProductDetailsRequest
from params_manager import ParamsManager


async def test_search_company_info():
    """Тест search_company_info."""
    print("\n" + "="*60)
    print("ТЕСТ: search_company_info")
    print("="*60)
    
    # Загружаем KB в ParamsManager из файла (без БД)
    params_manager = ParamsManager()
    try:
        # Пробуем загрузить из БД, но не падаем если БД недоступна
        await params_manager.load_all(force=True)
    except Exception as e:
        print(f"БД недоступна, используем fallback из файла: {e}")
        # Загружаем напрямую из файла для теста
        import json
        kb_path = Path(__file__).parent.parent / "data" / "kb.json"
        if kb_path.exists():
            with open(kb_path, "r", encoding="utf-8") as f:
                kb_content = json.load(f)
            params_manager._kb_content = kb_content
            params_manager._kb_text = params_manager._format_kb_text(kb_content)
    
    # Тест 1: Получение раздела contacts
    print("\n1. Тест получения раздела 'contacts':")
    result = await search_company_info.ainvoke({"section": "contacts"})
    print(f"Результат (первые 500 символов):\n{result[:500]}...")
    
    # Тест 2: Получение раздела product_groups
    print("\n2. Тест получения раздела 'product_groups':")
    result = await search_company_info.ainvoke({"section": "product_groups"})
    print(f"Результат (первые 500 символов):\n{result[:500]}...")
    
    # Тест 3: Несуществующий раздел
    print("\n3. Тест несуществующего раздела 'nonexistent':")
    result = await search_company_info.ainvoke({"section": "nonexistent"})
    print(f"Результат:\n{result}")


async def test_search_1c_products():
    """Тест search_1c_products."""
    print("\n" + "="*60)
    print("ТЕСТ: search_1c_products")
    print("="*60)
    
    # Загружаем группы товаров
    from tools.search_1c_products import load_product_groups
    groups_data = load_product_groups()
    available_groups = [item["code"] for item in groups_data.get("items", [])[:3]]
    
    if not available_groups:
        print("ОШИБКА: Не найдены группы товаров в базе знаний")
        return
    
    print(f"\nИспользуем группы: {available_groups}")
    
    # Тест 1: Поиск по группам
    print("\n1. Тест поиска товаров по группам:")
    request = Search1CProductsRequest(group_codes=available_groups)
    result = await search_1c_products(request)
    print(f"Результат (первые 1000 символов):\n{result[:1000]}...")
    
    # Тест 2: С фильтром по названию
    print("\n2. Тест поиска с фильтром 'брус':")
    request = Search1CProductsRequest(
        group_codes=available_groups,
        filters=ProductFilters(name_contains="брус")
    )
    result = await search_1c_products(request)
    print(f"Результат (первые 1000 символов):\n{result[:1000]}...")
    
    # Тест 3: Невалидные коды
    print("\n3. Тест с невалидными кодами:")
    request = Search1CProductsRequest(group_codes=["invalid-code-123"])
    result = await search_1c_products(request)
    print(f"Результат:\n{result}")


async def test_get_product_details():
    """Тест get_product_details."""
    print("\n" + "="*60)
    print("ТЕСТ: get_product_details")
    print("="*60)
    
    # Тест с примерными кодами товаров
    print("\n1. Тест получения деталей товаров (примерные коды):")
    test_codes = ["00-00003162", "00-00004340"]
    request = GetProductDetailsRequest(product_codes=test_codes)
    result = await get_product_details(request)
    print(f"Результат (первые 1000 символов):\n{result[:1000]}...")


async def test_all():
    """Запуск всех тестов."""
    print("\n" + "="*60)
    print("ЗАПУСК ТЕСТОВ ВСЕХ TOOLS")
    print("="*60)
    
    try:
        await test_search_company_info()
        await test_search_1c_products()
        await test_get_product_details()
        
        print("\n" + "="*60)
        print("ТЕСТЫ ЗАВЕРШЕНЫ")
        print("="*60)
    except Exception as e:
        print(f"\nОШИБКА ПРИ ТЕСТИРОВАНИИ: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_all())

