"""
Тестовый скрипт для проверки синхронизации каталога из 1C в Redis.

Запуск:
    python test_catalog_sync.py
"""
import asyncio
import sys
from pathlib import Path

# Добавляем backend в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from services.catalog_sync import catalog_sync_service


async def main():
    """Тестирование синхронизации каталога."""
    print("\n" + "=" * 80)
    print("ТЕСТ СИНХРОНИЗАЦИИ КАТАЛОГА ИЗ 1C В REDIS")
    print("=" * 80)

    # 1. Запускаем синхронизацию
    print("\n1️⃣ Запуск синхронизации...")
    stats = await catalog_sync_service.sync_catalog()

    print("\n📊 Результат синхронизации:")
    print(f"   Статус: {stats.get('status')}")
    if stats.get('status') == 'success':
        print(f"   Товаров: {stats.get('items_count')}")
        print(f"   Групп: {stats.get('groups_count')}")
        print(f"   Время: {stats.get('duration_seconds'):.2f}с")
    elif stats.get('status') == 'error':
        print(f"   Ошибка: {stats.get('error')}")

    # 2. Проверяем чтение из Redis
    print("\n2️⃣ Проверка чтения из Redis...")
    catalog = await catalog_sync_service.get_catalog_from_redis()

    if catalog:
        print(f"   ✅ Каталог загружен из Redis: {len(catalog)} товаров")

        # Показываем пример товара
        if len(catalog) > 0:
            print("\n   Пример товара:")
            item = catalog[0]
            print(f"   - Название: {item.get('Наименованиедлясайта', item.get('item_name'))}")
            print(f"   - Код: {item.get('item_code')}")
            print(f"   - Группа: {item.get('group_name')}")
            print(f"   - Цена: {item.get('Цена')} руб.")
            print(f"   - Остаток: {item.get('Остаток')}")
    else:
        print("   ❌ Каталог не найден в Redis")

    # 3. Проверяем статус
    print("\n3️⃣ Проверка статуса синхронизации...")
    status = await catalog_sync_service.get_sync_status()

    print(f"   Синхронизация в процессе: {status.get('is_syncing')}")
    print(f"   Последняя синхронизация: {status.get('last_sync_time')}")
    print(f"   Успешна: {status.get('last_sync_success')}")
    if status.get('last_error'):
        print(f"   Последняя ошибка: {status.get('last_error')}")

    if status.get('redis_metadata'):
        meta = status['redis_metadata']
        print(f"\n   Redis метаданные:")
        print(f"   - Товаров в кеше: {meta.get('items_count')}")
        print(f"   - Время кеша: {meta.get('last_sync')}")
        print(f"   - TTL: {meta.get('ttl_seconds')}с ({meta.get('ttl_seconds') // 3600}ч)")

    # 4. Тест чтения через product_search_bm25
    print("\n4️⃣ Тест чтения через product_search_bm25...")
    try:
        from tools.product_search_bm25 import load_catalog
        df = load_catalog()

        if not df.empty:
            print(f"   ✅ DataFrame загружен: {len(df)} товаров")
            print(f"   Колонки: {', '.join(df.columns[:10].tolist())}...")
        else:
            print("   ⚠️  DataFrame пустой")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки DataFrame: {e}")

    # Закрываем Redis соединение
    await catalog_sync_service.close_redis()

    print("\n" + "=" * 80)
    print("ТЕСТ ЗАВЕРШЕН")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
