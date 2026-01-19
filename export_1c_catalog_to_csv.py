"""
Экспорт полного каталога 1С в CSV для анализа.

Получает:
1. Все группы и товары из GET /GetGroups
2. Детальную информацию по ВСЕМ товарам из POST /GetDetailedItems
3. Сохраняет в CSV с полной структурой полей
"""
import requests
from requests.auth import HTTPBasicAuth
import csv
import json
from typing import List, Dict
from datetime import datetime
import time


# Конфигурация API
BASE_URL = "http://172.16.77.34/stroyast_test/hs/Ai"
AUTH = HTTPBasicAuth('Admin', '789654')
HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}


def get_all_groups() -> Dict:
    """
    Получить все группы и товары из GetGroups.

    Returns:
        {"groups": [{"название": "...", "номенклатура": "...", "items": [...]}, ...]}
    """
    print("📦 Получение каталога из GET /GetGroups...")

    try:
        response = requests.get(
            f"{BASE_URL}/GetGroups",
            auth=AUTH,
            headers=HEADERS,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        groups_count = len(data.get('groups', []))
        items_count = sum(len(g.get('items', [])) for g in data.get('groups', []))

        print(f"   ✅ Получено {groups_count} групп, {items_count} товаров")
        return data

    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return {"groups": []}


def get_detailed_items(item_codes: List[str], batch_num: int = 0, total_batches: int = 0) -> List[Dict]:
    """
    Получить детальную информацию по списку товаров.

    Args:
        item_codes: Список кодов товаров
        batch_num: Номер текущего батча
        total_batches: Общее количество батчей

    Returns:
        Список товаров с детальной информацией
    """
    if not item_codes:
        return []

    batch_info = f"[Батч {batch_num}/{total_batches}]" if total_batches > 0 else ""
    print(f"   🔍 {batch_info} Получение деталей для {len(item_codes)} товаров...")

    try:
        response = requests.post(
            f"{BASE_URL}/GetDetailedItems",
            json={"items": item_codes},
            auth=AUTH,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            timeout=60
        )
        response.encoding = response.apparent_encoding or 'utf-8'
        response.raise_for_status()

        data = response.json()
        items = data.get('items', [])

        print(f"      ✅ Получено {len(items)} деталей")
        return items

    except Exception as e:
        print(f"      ❌ Ошибка: {e}")
        return []


def get_all_detailed_items(item_codes: List[str], batch_size: int = 50) -> List[Dict]:
    """
    Получить детальную информацию по всем товарам (батчами).

    Args:
        item_codes: Список всех кодов товаров
        batch_size: Размер батча (по умолчанию 50)

    Returns:
        Список всех товаров с детальной информацией
    """
    print(f"\n📋 Получение детальной информации по {len(item_codes)} товарам...")
    print(f"   Размер батча: {batch_size}")

    all_items = []
    total_batches = (len(item_codes) + batch_size - 1) // batch_size

    for i in range(0, len(item_codes), batch_size):
        batch = item_codes[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        items = get_detailed_items(batch, batch_num, total_batches)
        all_items.extend(items)

        # Небольшая задержка между запросами
        if i + batch_size < len(item_codes):
            time.sleep(0.5)

    print(f"\n   ✅ Всего получено деталей: {len(all_items)}/{len(item_codes)}")
    return all_items


def flatten_catalog(catalog: Dict) -> List[Dict]:
    """
    Преобразует структуру каталога в flat список товаров.

    Args:
        catalog: {"groups": [...]}

    Returns:
        [{"group_name": "...", "group_code": "...", "item_code": "...", "item_name": "..."}, ...]
    """
    print("\n🔄 Преобразование в flat структуру...")

    flat_items = []
    for group in catalog.get('groups', []):
        group_name = group.get('название', '')
        group_code = group.get('номенклатура', '')

        for item in group.get('items', []):
            flat_items.append({
                'group_name': group_name,
                'group_code': group_code,
                'item_code': item.get('номенклатура', ''),
                'item_name': item.get('название', '')
            })

    print(f"   ✅ Создано {len(flat_items)} записей")
    return flat_items


def merge_data(flat_items: List[Dict], detailed_items: List[Dict]) -> List[Dict]:
    """
    Объединяет flat список с детальной информацией.

    Args:
        flat_items: Базовая информация (группа, название)
        detailed_items: Детальная информация (размеры, цены, характеристики)

    Returns:
        Полный список товаров со всеми полями
    """
    print("\n🔗 Объединение данных...")

    # Создаем индекс для быстрого поиска
    detailed_map = {}
    for item in detailed_items:
        # Иногда код пустой, используем название как ключ
        code = item.get('Код', '') or item.get('Наименование', '')
        if code:
            detailed_map[code] = item

    # Объединяем
    merged = []
    matched = 0

    for flat in flat_items:
        item_code = flat['item_code']
        item_name = flat['item_name']

        # Ищем детали по коду или по названию
        detailed = detailed_map.get(item_code) or detailed_map.get(item_name)

        if detailed:
            matched += 1
            # Объединяем все поля
            merged_item = {
                **flat,  # group_name, group_code, item_code, item_name
                **detailed  # все поля из API
            }
            merged.append(merged_item)
        else:
            # Если деталей нет - добавляем базовую информацию
            merged.append(flat)

    print(f"   ✅ Сопоставлено: {matched}/{len(flat_items)} товаров")
    return merged


def save_to_csv(data: List[Dict], filename: str = "1c_catalog_full.csv"):
    """
    Сохраняет данные в CSV файл.

    Args:
        data: Список товаров
        filename: Имя файла
    """
    if not data:
        print("   ⚠️  Нет данных для сохранения")
        return

    print(f"\n💾 Сохранение в {filename}...")

    # Собираем все уникальные поля
    all_fields = set()
    for item in data:
        all_fields.update(item.keys())

    # Упорядочиваем поля (важные первыми)
    priority_fields = [
        'group_name', 'group_code',
        'item_code', 'item_name',
        'Наименование', 'Наименованиедлясайта',
        'Цена', 'Остаток',
        'Видпиломатериала', 'Порода', 'Сорт',
        'Толщина', 'Ширина', 'Длина',
        'Влажность', 'Типобработки',
        'СрокпроизводстваднОбщие', 'ПопулярностьОбщие'
    ]

    # Сначала priority поля, потом остальные
    fieldnames = [f for f in priority_fields if f in all_fields]
    remaining = sorted(all_fields - set(fieldnames))
    fieldnames.extend(remaining)

    try:
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)

        print(f"   ✅ Сохранено {len(data)} записей")
        print(f"   📊 Колонок: {len(fieldnames)}")
        print(f"\n   Основные поля:")
        for i, field in enumerate(fieldnames[:15], 1):
            print(f"      {i}. {field}")
        if len(fieldnames) > 15:
            print(f"      ... и еще {len(fieldnames) - 15} полей")

    except Exception as e:
        print(f"   ❌ Ошибка сохранения: {e}")


def print_summary(data: List[Dict]):
    """Выводит статистику по данным."""
    if not data:
        return

    print(f"\n" + "=" * 80)
    print("📊 СТАТИСТИКА КАТАЛОГА")
    print("=" * 80)

    # Общее
    print(f"\n🔢 Общее:")
    print(f"   Всего товаров: {len(data)}")

    # Группы
    unique_groups = set(item.get('group_name', '') for item in data)
    print(f"   Уникальных групп: {len(unique_groups)}")

    # Виды пиломатериалов
    types = set(item.get('Видпиломатериала', '') for item in data if item.get('Видпиломатериала'))
    print(f"\n🪵 Виды пиломатериалов ({len(types)}):")
    for t in sorted(types):
        count = sum(1 for item in data if item.get('Видпиломатериала') == t)
        print(f"   - {t}: {count} шт")

    # Породы
    species = set(item.get('Порода', '') for item in data if item.get('Порода'))
    print(f"\n🌲 Породы ({len(species)}):")
    for s in sorted(species):
        count = sum(1 for item in data if item.get('Порода') == s)
        print(f"   - {s}: {count} шт")

    # Сорта
    grades = set(item.get('Сорт', '') for item in data if item.get('Сорт'))
    print(f"\n⭐ Сорта/Классы ({len(grades)}):")
    for g in sorted(grades):
        count = sum(1 for item in data if item.get('Сорт') == g)
        print(f"   - {g}: {count} шт")

    # Цены
    prices = [float(item.get('Цена', 0)) for item in data if item.get('Цена') and item.get('Цена') != '0']
    if prices:
        print(f"\n💰 Цены:")
        print(f"   Мин: {min(prices):,.0f} ₽")
        print(f"   Макс: {max(prices):,.0f} ₽")
        print(f"   Средняя: {sum(prices)/len(prices):,.0f} ₽")
        print(f"   Товаров с ценами: {len(prices)}/{len(data)}")

    # Размеры
    lengths = set(item.get('Длина', '') for item in data if item.get('Длина') and item.get('Длина') != '0')
    print(f"\n📏 Длины ({len(lengths)}):")
    for l in sorted(lengths):
        count = sum(1 for item in data if item.get('Длина') == l)
        print(f"   - {l}мм: {count} шт")

    print("\n" + "=" * 80)


def main():
    """Основная функция."""
    print("\n" + "=" * 80)
    print("🚀 ЭКСПОРТ КАТАЛОГА 1С В CSV")
    print("=" * 80)
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 1. Получаем каталог
    catalog = get_all_groups()

    if not catalog.get('groups'):
        print("\n❌ Не удалось получить каталог. Завершение.")
        return

    # 2. Преобразуем в flat список
    flat_items = flatten_catalog(catalog)

    # 3. Получаем все коды товаров
    all_codes = list(set(item['item_code'] for item in flat_items if item['item_code']))
    print(f"\n   Уникальных кодов товаров: {len(all_codes)}")

    # 4. Получаем детали (батчами)
    detailed_items = get_all_detailed_items(all_codes, batch_size=50)

    # 5. Объединяем данные
    merged_data = merge_data(flat_items, detailed_items)

    # 6. Сохраняем в CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"1c_catalog_full_{timestamp}.csv"
    save_to_csv(merged_data, filename)

    # 7. Выводим статистику
    print_summary(merged_data)

    print(f"\n✅ ГОТОВО!")
    print(f"   Файл: {filename}")
    print(f"   Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
