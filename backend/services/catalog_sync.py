"""
Сервис синхронизации каталога товаров из 1C в Redis.

Логика аналогична export_1c_catalog_to_csv.py:
1. Получаем все группы и товары из GET /GetGroups
2. Flatten в список с group_name, group_code, item_code, item_name
3. Получаем детальную информацию по ВСЕМ товарам из POST /GetDetailedItems (батчами)
4. Merge данных
5. Сохраняем в Redis как JSON массив объектов

Запускается:
- При старте приложения (первая синхронизация)
- Каждый час через планировщик
- Вручную через API endpoint
"""
import os
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx
from httpx import HTTPStatusError, RequestError
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Конфигурация 1C API (используем существующие переменные C1_*)
ONEC_BASE_URL = "http://172.16.77.34/stroyast_test/hs/Ai"  # Базовый URL без endpoint
ONEC_USERNAME = os.getenv("C1_API_USER", "Admin")
ONEC_PASSWORD = os.getenv("C1_API_PASSWORD", "789654")
ONEC_TIMEOUT = int(os.getenv("C1_API_TIMEOUT_SECONDS", "60"))

# Конфигурация Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")  # localhost для локальной разработки, переопределяется на redis:6379 в Docker
REDIS_CATALOG_KEY = "catalog:products"
REDIS_CATALOG_METADATA_KEY = "catalog:metadata"
REDIS_TTL = 7200  # 2 часа

# Размер батча для GetDetailedItems
BATCH_SIZE = 50


class CatalogSyncService:
    """Сервис синхронизации каталога."""

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.is_syncing = False
        self.last_sync_time: Optional[datetime] = None
        self.last_sync_success = False
        self.last_error: Optional[str] = None

    async def init_redis(self):
        """Инициализация Redis клиента."""
        if not self.redis_client:
            self.redis_client = await redis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info(f"✅ Redis client initialized: {REDIS_URL}")

    async def close_redis(self):
        """Закрытие Redis клиента."""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Redis client closed")

    async def get_all_groups(self) -> Dict[str, Any]:
        """
        Получить все группы и товары из GetGroups.

        Returns:
            {"groups": [{"название": "...", "номенклатура": "...", "items": [{"название": "...", "номенклатура": "..."}]}, ...]}
        """
        logger.info("📦 Fetching catalog from 1C GetGroups API...")

        async with httpx.AsyncClient(timeout=ONEC_TIMEOUT) as client:
            try:
                response = await client.get(
                    f"{ONEC_BASE_URL}/GetGroups",
                    auth=(ONEC_USERNAME, ONEC_PASSWORD),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()
                data = response.json()

                groups_count = len(data.get('groups', []))
                items_count = sum(len(g.get('items', [])) for g in data.get('groups', []))

                logger.info(f"   ✅ Received {groups_count} groups, {items_count} items")
                return data

            except (HTTPStatusError, RequestError) as e:
                logger.error(f"   ❌ Error fetching groups: {e}")
                return {"groups": []}

    async def get_detailed_items_batch(
        self,
        item_codes: List[str],
        batch_num: int = 0,
        total_batches: int = 0
    ) -> List[Dict[str, Any]]:
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

        batch_info = f"[Batch {batch_num}/{total_batches}]" if total_batches > 0 else ""
        logger.info(f"   🔍 {batch_info} Fetching details for {len(item_codes)} items...")

        async with httpx.AsyncClient(timeout=ONEC_TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{ONEC_BASE_URL}/GetDetailedItems",
                    json={"items": item_codes},
                    auth=(ONEC_USERNAME, ONEC_PASSWORD),
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Accept": "application/json"
                    }
                )
                response.raise_for_status()

                data = response.json()
                items = data.get('items', [])

                logger.info(f"      ✅ Received {len(items)} detailed items")
                return items

            except (HTTPStatusError, RequestError) as e:
                logger.error(f"      ❌ Error fetching batch: {e}")
                return []

    async def get_all_detailed_items(self, item_codes: List[str]) -> List[Dict[str, Any]]:
        """
        Получить детальную информацию по всем товарам (батчами).

        Args:
            item_codes: Список всех кодов товаров

        Returns:
            Список всех товаров с детальной информацией
        """
        logger.info(f"\n📋 Fetching detailed info for {len(item_codes)} items...")
        logger.info(f"   Batch size: {BATCH_SIZE}")

        all_items = []
        total_batches = (len(item_codes) + BATCH_SIZE - 1) // BATCH_SIZE

        for i in range(0, len(item_codes), BATCH_SIZE):
            batch = item_codes[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1

            items = await self.get_detailed_items_batch(batch, batch_num, total_batches)
            all_items.extend(items)

            # Небольшая задержка между запросами
            if i + BATCH_SIZE < len(item_codes):
                await asyncio.sleep(0.5)

        logger.info(f"\n   ✅ Total detailed items received: {len(all_items)}/{len(item_codes)}")
        return all_items

    def flatten_catalog(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Преобразует структуру каталога в flat список товаров.

        Args:
            catalog: {"groups": [...]}

        Returns:
            [{"group_name": "...", "group_code": "...", "item_code": "...", "item_name": "..."}, ...]
        """
        logger.info("\n🔄 Flattening catalog structure...")

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

        logger.info(f"   ✅ Created {len(flat_items)} flat records")
        return flat_items

    def clean_numeric_fields(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Очищает числовые поля от неразрывных пробелов.
        
        1C API возвращает числа с неразрывными пробелами (\xa0): "1 250", "2 500"
        Очищаем их для корректной работы парсинга.
        """
        # Поля которые могут содержать числа с пробелами
        numeric_fields = [
            'Толщина', 'Ширина', 'Длина',  # Размеры в мм
            'Остаток',  # Остаток на складе
            'ПлотностькгмОбщие',  # кг/м³
            'СрокпроизводстваднОбщие',  # Срок производства в днях
            'ПопулярностьОбщие',  # Популярность (рейтинг)
        ]

        cleaned = item.copy()

        for field in numeric_fields:
            if field in cleaned and cleaned[field]:
                value = cleaned[field]
                if isinstance(value, str):
                    # Удаляем все пробелы (включая неразрывные \xa0)
                    cleaned[field] = value.replace(' ', '').replace('\xa0', '')

        return cleaned

    def merge_data(
        self,
        flat_items: List[Dict[str, Any]],
        detailed_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Объединяет flat список с детальной информацией.

        Логика как в export_1c_catalog_to_csv.py:
        - Создаем индекс detailed_map по коду или названию
        - Для каждого flat item ищем детали
        - Merge всех полей: {...flat, ...detailed}

        Args:
            flat_items: Базовая информация (группа, название)
            detailed_items: Детальная информация (размеры, цены, характеристики)

        Returns:
            Полный список товаров со всеми полями (аналог CSV)
        """
        logger.info("\n🔗 Merging data...")

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
                # Объединяем все поля (как в CSV)
                merged_item = {
                    **flat,  # group_name, group_code, item_code, item_name
                    **detailed  # все поля из API
                }
                # Очищаем числовые поля от неразрывных пробелов
                merged_item = self.clean_numeric_fields(merged_item)
                merged.append(merged_item)
            else:
                # Если деталей нет - добавляем базовую информацию
                merged.append(flat)

        logger.info(f"   ✅ Matched: {matched}/{len(flat_items)} items")
        return merged

    async def save_to_redis(self, data: List[Dict[str, Any]]) -> bool:
        """
        Сохраняет каталог в Redis как JSON массив объектов.

        Args:
            data: Список товаров (структура аналогична CSV)

        Returns:
            True если успешно сохранено
        """
        if not data:
            logger.warning("⚠️  No data to save to Redis")
            return False

        logger.info(f"\n💾 Saving {len(data)} items to Redis...")

        try:
            await self.init_redis()

            # Сохраняем каталог в JSON
            catalog_json = json.dumps(data, ensure_ascii=False)
            await self.redis_client.set(
                REDIS_CATALOG_KEY,
                catalog_json,
                ex=REDIS_TTL
            )

            # Сохраняем метаданные
            metadata = {
                "items_count": len(data),
                "last_sync": datetime.utcnow().isoformat(),
                "ttl_seconds": REDIS_TTL
            }
            metadata_json = json.dumps(metadata, ensure_ascii=False)
            await self.redis_client.set(
                REDIS_CATALOG_METADATA_KEY,
                metadata_json,
                ex=REDIS_TTL
            )

            logger.info(f"   ✅ Saved to Redis: {len(data)} items")
            logger.info(f"   🕐 TTL: {REDIS_TTL} seconds ({REDIS_TTL // 3600} hours)")
            return True

        except Exception as e:
            logger.error(f"   ❌ Error saving to Redis: {e}")
            return False

    async def sync_catalog(self) -> Dict[str, Any]:
        """
        Полная синхронизация каталога.

        Алгоритм (аналогичен export_1c_catalog_to_csv.py):
        1. Получаем каталог из GetGroups
        2. Flatten в список
        3. Получаем все коды товаров
        4. Получаем детали батчами из GetDetailedItems
        5. Merge данных
        6. Сохраняем в Redis

        Returns:
            Статистика синхронизации
        """
        if self.is_syncing:
            logger.warning("⚠️  Sync already in progress, skipping...")
            return {
                "status": "skipped",
                "reason": "sync_in_progress"
            }

        self.is_syncing = True
        sync_start = datetime.utcnow()

        logger.info("\n" + "=" * 80)
        logger.info("🚀 CATALOG SYNC STARTED")
        logger.info("=" * 80)
        logger.info(f"Start time: {sync_start.isoformat()}")

        try:
            # 1. Получаем каталог
            catalog = await self.get_all_groups()

            if not catalog.get('groups'):
                raise Exception("Failed to fetch catalog from 1C API")

            # 2. Преобразуем в flat список
            flat_items = self.flatten_catalog(catalog)

            # 3. Получаем все коды товаров
            all_codes = list(set(item['item_code'] for item in flat_items if item['item_code']))
            logger.info(f"\n   Unique item codes: {len(all_codes)}")

            # 4. Получаем детали (батчами)
            detailed_items = await self.get_all_detailed_items(all_codes)

            # 5. Объединяем данные
            merged_data = self.merge_data(flat_items, detailed_items)

            # 6. Сохраняем в Redis
            success = await self.save_to_redis(merged_data)

            if not success:
                raise Exception("Failed to save catalog to Redis")

            # Статистика
            sync_end = datetime.utcnow()
            duration = (sync_end - sync_start).total_seconds()

            self.last_sync_time = sync_end
            self.last_sync_success = True
            self.last_error = None

            stats = {
                "status": "success",
                "items_count": len(merged_data),
                "groups_count": len(catalog.get('groups', [])),
                "start_time": sync_start.isoformat(),
                "end_time": sync_end.isoformat(),
                "duration_seconds": duration
            }

            logger.info("\n" + "=" * 80)
            logger.info("✅ CATALOG SYNC COMPLETED")
            logger.info(f"   Items: {stats['items_count']}")
            logger.info(f"   Duration: {duration:.2f}s")
            logger.info("=" * 80 + "\n")

            return stats

        except Exception as e:
            self.last_sync_success = False
            self.last_error = str(e)

            logger.error("\n" + "=" * 80)
            logger.error("❌ CATALOG SYNC FAILED")
            logger.error(f"   Error: {e}")
            logger.error("=" * 80 + "\n")

            return {
                "status": "error",
                "error": str(e),
                "start_time": sync_start.isoformat()
            }

        finally:
            self.is_syncing = False

    async def get_catalog_from_redis(self) -> Optional[List[Dict[str, Any]]]:
        """
        Получить каталог из Redis.

        Returns:
            Список товаров или None если не найдено
        """
        try:
            await self.init_redis()

            catalog_json = await self.redis_client.get(REDIS_CATALOG_KEY)
            if not catalog_json:
                logger.warning("⚠️  Catalog not found in Redis")
                return None

            catalog = json.loads(catalog_json)
            logger.info(f"✅ Loaded {len(catalog)} items from Redis")
            return catalog

        except Exception as e:
            logger.error(f"❌ Error loading catalog from Redis: {e}")
            return None

    async def get_sync_status(self) -> Dict[str, Any]:
        """
        Получить статус синхронизации.

        Returns:
            Информация о последней синхронизации
        """
        await self.init_redis()

        # Получаем метаданные из Redis
        metadata_json = await self.redis_client.get(REDIS_CATALOG_METADATA_KEY)
        metadata = json.loads(metadata_json) if metadata_json else None

        return {
            "is_syncing": self.is_syncing,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_sync_success": self.last_sync_success,
            "last_error": self.last_error,
            "redis_metadata": metadata
        }


# Глобальный экземпляр сервиса
catalog_sync_service = CatalogSyncService()
