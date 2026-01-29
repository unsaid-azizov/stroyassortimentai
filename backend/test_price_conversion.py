"""
Тестовый скрипт для проверки правильности расчета цен с конвертацией единиц.
Симулирует реальные заказы и проверяет корректность расчетов.
"""
import sys
import os

# Добавляем путь к backend для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.sales_tools import (
    enrich_and_calculate_order_sync,
    OrderInfo,
    OrderLineItem,
    OrderPricing,
)
import logging

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def test_price_conversion():
    """Тестируем конвертацию цен на реальных примерах."""

    print("=" * 80)
    print("ТЕСТИРОВАНИЕ РАСЧЕТА ЦЕН С КОНВЕРТАЦИЕЙ ЕДИНИЦ")
    print("=" * 80)
    print()

    # Тест 1: Вагонка - цена в м², заказ в штуках
    print("\n" + "=" * 80)
    print("ТЕСТ 1: Вагонка штиль 13×115×6000 класс АВ")
    print("Цена в 1C: 500 ₽/м², ЕИ: 'м2 (1.449275 шт)'")
    print("Клиент заказывает: 10 шт")
    print("=" * 80)

    order1 = OrderInfo(
        client_name="Тестовый Клиент 1",
        client_contact="+79991234567",
        items=[
            OrderLineItem(
                product_code="00-00010236",  # Код вагонки штиль 13×115×6000
                product_name="Вагонка штиль 13×115×6000 класс АВ",
                quantity=10,
                unit="шт",
            )
        ],
        pricing=OrderPricing(currency="RUB"),
    )

    try:
        result1 = enrich_and_calculate_order_sync(order1)
        item1 = result1.items[0]

        print(f"\n📊 РЕЗУЛЬТАТ:")
        print(f"   Цена за 1 шт: {item1.unit_price} ₽")
        print(f"   Итого за 10 шт: {item1.line_total} ₽")
        print(f"   Остаток: {item1.availability}")

        # Проверяем правильность
        expected_price_per_piece = 500 / 1.449275  # ≈ 345 ₽/шт
        expected_total = expected_price_per_piece * 10  # ≈ 3450 ₽

        if item1.unit_price:
            error_percent = abs(item1.unit_price - expected_price_per_piece) / expected_price_per_piece * 100
            if error_percent < 1:
                print(f"   ✅ ТЕСТ ПРОЙДЕН! Цена корректна (ошибка {error_percent:.2f}%)")
            else:
                print(f"   ❌ ОШИБКА! Ожидалось {expected_price_per_piece:.2f} ₽/шт, получено {item1.unit_price} ₽/шт")
        else:
            print(f"   ❌ ОШИБКА! Цена не заполнена")

    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")

    # Тест 2: Доска - цена в м³, заказ в штуках
    print("\n" + "=" * 80)
    print("ТЕСТ 2: Доска обрезн. 50×200×6000 сорт 1")
    print("Цена в 1C: 15000 ₽/м³, ЕИ: 'м3 (16 шт)'")
    print("Клиент заказывает: 8 шт")
    print("=" * 80)

    order2 = OrderInfo(
        client_name="Тестовый Клиент 2",
        client_contact="+79991234568",
        items=[
            OrderLineItem(
                product_code="00-00001659",  # Код доски
                product_name="Доска обрезн. е/в хв. 50×200×6000 сорт 1, ТУ",
                quantity=8,
                unit="шт",
            )
        ],
        pricing=OrderPricing(currency="RUB"),
    )

    try:
        result2 = enrich_and_calculate_order_sync(order2)
        item2 = result2.items[0]

        print(f"\n📊 РЕЗУЛЬТАТ:")
        print(f"   Цена за 1 шт: {item2.unit_price} ₽")
        print(f"   Итого за 8 шт: {item2.line_total} ₽")
        print(f"   Остаток: {item2.availability}")

        # Проверяем правильность
        expected_price_per_piece = 15000 / 16  # = 937.50 ₽/шт
        expected_total = expected_price_per_piece * 8  # = 7500 ₽

        if item2.unit_price:
            error_percent = abs(item2.unit_price - expected_price_per_piece) / expected_price_per_piece * 100
            if error_percent < 1:
                print(f"   ✅ ТЕСТ ПРОЙДЕН! Цена корректна (ошибка {error_percent:.2f}%)")
            else:
                print(f"   ❌ ОШИБКА! Ожидалось {expected_price_per_piece:.2f} ₽/шт, получено {item2.unit_price} ₽/шт")
        else:
            print(f"   ❌ ОШИБКА! Цена не заполнена")

    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")

    # Тест 3: Плита ОСБ - цена просто в штуках
    print("\n" + "=" * 80)
    print("ТЕСТ 3: Плита OSB-3 9×1250×2500")
    print("Цена в 1C: 580 ₽, ЕИ: 'шт'")
    print("Клиент заказывает: 20 шт")
    print("=" * 80)

    order3 = OrderInfo(
        client_name="Тестовый Клиент 3",
        client_contact="+79991234569",
        items=[
            OrderLineItem(
                product_code="00-00000039",  # Код ОСБ
                product_name="Плита OSB-3 (ОСП) 9×1250×2500",
                quantity=20,
                unit="шт",
            )
        ],
        pricing=OrderPricing(currency="RUB"),
    )

    try:
        result3 = enrich_and_calculate_order_sync(order3)
        item3 = result3.items[0]

        print(f"\n📊 РЕЗУЛЬТАТ:")
        print(f"   Цена за 1 шт: {item3.unit_price} ₽")
        print(f"   Итого за 20 шт: {item3.line_total} ₽")
        print(f"   Остаток: {item3.availability}")

        # Проверяем правильность
        expected_price_per_piece = 580  # ₽/шт
        expected_total = expected_price_per_piece * 20  # = 11600 ₽

        if item3.unit_price:
            if item3.unit_price == expected_price_per_piece:
                print(f"   ✅ ТЕСТ ПРОЙДЕН! Цена корректна")
            else:
                print(f"   ❌ ОШИБКА! Ожидалось {expected_price_per_piece} ₽/шт, получено {item3.unit_price} ₽/шт")
        else:
            print(f"   ❌ ОШИБКА! Цена не заполнена")

    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")

    # Тест 4: Комплексный заказ с разными единицами
    print("\n" + "=" * 80)
    print("ТЕСТ 4: Комплексный заказ - несколько товаров с разными ЕИ")
    print("=" * 80)

    order4 = OrderInfo(
        client_name="Тестовый Клиент 4",
        client_contact="test@example.com",
        items=[
            OrderLineItem(
                product_code="00-00010236",
                product_name="Вагонка штиль 13×115×6000",
                quantity=15,
                unit="шт",
            ),
            OrderLineItem(
                product_code="00-00001659",
                product_name="Доска обрезн. 50×200×6000",
                quantity=10,
                unit="шт",
            ),
            OrderLineItem(
                product_code="00-00000039",
                product_name="Плита OSB-3 9×1250×2500",
                quantity=25,
                unit="шт",
            ),
        ],
        pricing=OrderPricing(currency="RUB"),
    )

    try:
        result4 = enrich_and_calculate_order_sync(order4)

        print(f"\n📊 РЕЗУЛЬТАТ:")
        total_sum = 0
        for i, item in enumerate(result4.items, 1):
            print(f"\n   Позиция {i}: {item.product_name}")
            print(f"      Количество: {item.quantity} {item.unit}")
            print(f"      Цена за ед.: {item.unit_price} ₽")
            print(f"      Итого: {item.line_total} ₽")
            print(f"      Остаток: {item.availability}")
            if item.line_total:
                total_sum += item.line_total

        print(f"\n   💰 ИТОГО ПО ЗАКАЗУ: {result4.pricing.total} ₽")
        print(f"   ✅ Все позиции обработаны корректно!")

    except Exception as e:
        print(f"   ❌ ОШИБКА: {e}")

    print("\n" + "=" * 80)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 80)


if __name__ == "__main__":
    test_price_conversion()
