"""
Скрипт для аудита расчета цен.
Проверяет корректность ценообразования с учетом разных единиц измерения.
"""
import asyncio
import json
from typing import List, Dict
from services.catalog_sync import CatalogSyncService


async def audit_price_calculations():
    """Аудит расчета цен из Redis/1C."""

    print("=" * 80)
    print("АУДИТ РАСЧЕТА ЦЕН")
    print("=" * 80)

    # Инициализируем сервис
    catalog_service = CatalogSyncService()

    # Получаем каталог из Redis
    catalog = await catalog_service.get_catalog_from_redis()

    if not catalog:
        print("❌ Каталог пуст или недоступен")
        return

    print(f"\n✓ Загружено {len(catalog)} товаров из Redis\n")

    # Анализируем единицы измерения и цены
    units_stats = {}
    price_issues = []
    unit_format_examples = {}

    for item in catalog:
        code = item.get("Код", "N/A")
        name = item.get("Наименование", "N/A")
        price = item.get("Цена")
        unit = item.get("ЕдИзмерения", "")

        # Собираем статистику по единицам
        if unit:
            if unit not in units_stats:
                units_stats[unit] = 0
                unit_format_examples[unit] = {
                    "code": code,
                    "name": name[:50],
                    "price": price
                }
            units_stats[unit] += 1

        # Проверяем потенциальные проблемы
        if price is None or price == 0:
            price_issues.append({
                "code": code,
                "name": name[:60],
                "issue": "Отсутствует цена",
                "unit": unit
            })

        # Проверяем формат единицы измерения
        if unit and "шт" in unit.lower() and "(" in unit:
            # Это формат типа "м3 (33.333 шт)" - проверим корректность
            try:
                # Парсим формат
                import re
                match = re.match(r'(\S+)\s*\(([0-9.]+)\s*шт\)', unit.strip())
                if match:
                    base_unit = match.group(1)
                    pieces_per_unit = float(match.group(2))

                    # Рассчитываем цену за штуку
                    if price and pieces_per_unit > 0:
                        price_per_piece = price / pieces_per_unit

                        # Сохраняем пример для демонстрации
                        if base_unit not in ["примеры_конверсии"]:
                            if "примеры_конверсии" not in unit_format_examples:
                                unit_format_examples["примеры_конверсии"] = []

                            if len(unit_format_examples["примеры_конверсии"]) < 5:
                                unit_format_examples["примеры_конверсии"].append({
                                    "code": code,
                                    "name": name[:50],
                                    "base_unit": base_unit,
                                    "pieces_per_unit": pieces_per_unit,
                                    "price_base": price,
                                    "price_per_piece": round(price_per_piece, 2)
                                })
            except Exception as e:
                price_issues.append({
                    "code": code,
                    "name": name[:60],
                    "issue": f"Ошибка парсинга единицы: {unit}",
                    "unit": unit
                })

    # Выводим статистику по единицам измерения
    print("\n" + "=" * 80)
    print("СТАТИСТИКА ПО ЕДИНИЦАМ ИЗМЕРЕНИЯ")
    print("=" * 80)

    sorted_units = sorted(units_stats.items(), key=lambda x: x[1], reverse=True)
    for unit, count in sorted_units[:20]:  # Топ 20
        print(f"{unit:30} - {count:5} товаров")
        if unit in unit_format_examples:
            ex = unit_format_examples[unit]
            print(f"  Пример: {ex['code']} | {ex['name']} | {ex['price']} ₽")

    # Примеры конверсии единиц
    if "примеры_конверсии" in unit_format_examples:
        print("\n" + "=" * 80)
        print("ПРИМЕРЫ КОНВЕРСИИ ЕДИНИЦ (м³/м² → шт)")
        print("=" * 80)

        for ex in unit_format_examples["примеры_конверсии"]:
            print(f"\n{ex['code']} | {ex['name']}")
            print(f"  Базовая ЕИ: {ex['base_unit']}")
            print(f"  В 1 {ex['base_unit']}: {ex['pieces_per_unit']} шт")
            print(f"  Цена за {ex['base_unit']}: {ex['price_base']:,.0f} ₽".replace(",", " "))
            print(f"  ➡️  Цена за 1 шт: {ex['price_per_piece']:,.2f} ₽".replace(",", " "))

    # Выводим проблемы
    if price_issues:
        print("\n" + "=" * 80)
        print(f"НАЙДЕНО ПРОБЛЕМ: {len(price_issues)}")
        print("=" * 80)

        # Группируем по типу проблемы
        issues_by_type = {}
        for issue in price_issues:
            issue_type = issue["issue"]
            if issue_type not in issues_by_type:
                issues_by_type[issue_type] = []
            issues_by_type[issue_type].append(issue)

        for issue_type, issues in issues_by_type.items():
            print(f"\n{issue_type}: {len(issues)} случаев")
            for issue in issues[:5]:  # Показываем первые 5
                print(f"  • {issue['code']} | {issue['name']} | ЕИ: {issue.get('unit', 'N/A')}")
            if len(issues) > 5:
                print(f"  ... и ещё {len(issues) - 5}")

    # Проверяем, используется ли price_calculator.py
    print("\n" + "=" * 80)
    print("ПРОВЕРКА ИСПОЛЬЗОВАНИЯ МОДУЛЯ price_calculator.py")
    print("=" * 80)

    # Проверяем импорты в sales_tools.py
    try:
        with open("/home/astex/agency/1/consultant/backend/tools/sales_tools.py", "r") as f:
            sales_tools_content = f.read()

        if "price_calculator" in sales_tools_content:
            print("✓ price_calculator импортирован в sales_tools.py")
        else:
            print("❌ КРИТИЧНО: price_calculator НЕ импортирован в sales_tools.py")
            print("   Расчёт цен происходит через простое умножение quantity × unit_price")
            print("   БЕЗ учета конверсии единиц измерения!")

        # Проверяем как считается line_total
        if "line_total = round(float(item.quantity) * float(item.unit_price), 2)" in sales_tools_content:
            print("\n⚠️  НАЙДЕНА УПРОЩЕННАЯ ФОРМУЛА расчета:")
            print("   line_total = quantity × unit_price")
            print("   Эта формула НЕ учитывает разницу между:")
            print("   - Заказ в 'шт', а цена в 'м³'")
            print("   - Заказ в 'м²', а цена в 'м³'")
            print("   - Коэффициенты конверсии из поля 'ЕдИзмерения'")
    except Exception as e:
        print(f"Ошибка при проверке: {e}")

    print("\n" + "=" * 80)
    print("РЕКОМЕНДАЦИИ")
    print("=" * 80)

    print("""
1. ❌ Модуль utils/price_calculator.py СОЗДАН, но НЕ ИСПОЛЬЗУЕТСЯ
   - Функции parse_unit(), calculate_price_per_piece(), calculate_total_price()
   - Эти функции умеют парсить "м3 (33.33 шт)" и конвертировать единицы

2. ⚠️  В sales_tools.py используется УПРОЩЕННАЯ формула:
   - line_total = quantity × unit_price
   - БЕЗ проверки единиц измерения

3. 🔴 ПОТЕНЦИАЛЬНАЯ ОШИБКА:
   - Если клиент заказывает "10 шт", а товар в 1C имеет цену "20000 ₽/м³"
   - Система посчитает: 10 × 20000 = 200 000 ₽
   - НО ПРАВИЛЬНО: нужно узнать сколько штук в 1 м³, и пересчитать цену за штуку

4. ✅ РЕШЕНИЕ:
   - Интегрировать price_calculator.py в sales_tools.py
   - Использовать calculate_total_price() вместо простого умножения
   - Парсить unit из данных 1C через parse_unit()
   - Учитывать конверсионные коэффициенты
    """)

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(audit_price_calculations())
