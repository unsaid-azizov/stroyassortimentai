"""
Tool для поиска товаров в системе 1С через API.
Агент определяет релевантные коды групп товаров из info.json и запрашивает товары из 1С.
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# URL API 1С (можно переопределить через переменную окружения)
C1_API_URL = os.getenv("C1_API_URL", "http://localhost:8080/api")
# Если установлено в "false" или "0", API будет полностью отключен и всегда используется fallback
C1_API_ENABLED = os.getenv("C1_API_ENABLED", "true").lower() not in ("false", "0", "off")


def load_product_groups() -> Dict:
    """Загружает информацию о группах товаров из info.json."""
    info_path = Path(__file__).parent.parent / "data" / "info.json"
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Файл {info_path} не найден")
        return {"items": []}


class ProductFilters(BaseModel):
    """Фильтры для поиска товаров."""
    name_contains: Optional[str] = Field(None, description="Товары, название которых содержит эту строку (например, 'Брус', 'Доска')")
    min_price: Optional[float] = Field(None, description="Минимальная цена")
    max_price: Optional[float] = Field(None, description="Максимальная цена")
    size: Optional[str] = Field(None, description="Размер товара (например, '100x100')")


class Search1CProductsRequest(BaseModel):
    """Параметры запроса для поиска товаров в 1С."""
    group_codes: List[str] = Field(description="Список кодов групп товаров из info.json (например, ['00-00022304', '00-00020587'])")
    filters: Optional[ProductFilters] = Field(None, description="Опциональные фильтры для товаров")


def validate_group_codes(codes: List[str]) -> tuple[List[str], List[str]]:
    """
    Валидирует коды групп товаров.
    Возвращает (валидные_коды, невалидные_коды).
    """
    groups_data = load_product_groups()
    valid_codes = []
    invalid_codes = []
    
    available_codes = {item["code"] for item in groups_data.get("items", [])}
    
    for code in codes:
        if code in available_codes:
            valid_codes.append(code)
        else:
            invalid_codes.append(code)
    
    return valid_codes, invalid_codes


def filter_products(products: List[Dict[str, Any]], filters: Optional[ProductFilters]) -> List[Dict[str, Any]]:
    """
    Фильтрует список товаров по заданным критериям.
    """
    if not filters:
        return products
    
    filtered = products
    
    # Фильтр по названию
    if filters.name_contains:
        name_lower = filters.name_contains.lower()
        filtered = [
            p for p in filtered
            if name_lower in p.get("name", "").lower()
        ]
    
    # Фильтр по цене
    if filters.min_price is not None:
        filtered = [
            p for p in filtered
            if p.get("price") is not None and p.get("price", 0) >= filters.min_price
        ]
    
    if filters.max_price is not None:
        filtered = [
            p for p in filtered
            if p.get("price") is not None and p.get("price", 0) <= filters.max_price
        ]
    
    # Фильтр по размеру
    if filters.size:
        size_lower = filters.size.lower()
        filtered = [
            p for p in filtered
            if size_lower in str(p.get("size", "")).lower()
        ]
    
    return filtered


def format_products_response(products: List[Dict[str, Any]]) -> str:
    """
    Форматирует список товаров для ответа клиенту.
    """
    if not products:
        return "К сожалению, товары по вашему запросу не найдены."
    
    result_lines = [f"Найдено товаров: {len(products)}\n"]
    
    for i, product in enumerate(products[:20], 1):  # Ограничиваем 20 товарами
        name = product.get("name", "Без названия")
        price = product.get("price")
        size = product.get("size")
        quantity = product.get("quantity")
        unit = product.get("unit", "шт")
        
        line = f"{i}. {name}"
        
        if size:
            line += f", размер: {size}"
        if price:
            line += f", цена: {price} руб."
        if quantity is not None:
            line += f", в наличии: {quantity} {unit}"
        
        result_lines.append(line)
    
    if len(products) > 20:
        result_lines.append(f"\n... и еще {len(products) - 20} товаров")
    
    return "\n".join(result_lines)


def get_fallback_info(codes: List[str], filters: Optional[ProductFilters]) -> str:
    """
    Возвращает информацию о группах товаров из info.json как fallback,
    когда API 1С недоступен.
    """
    groups_data = load_product_groups()
    items = groups_data.get("items", [])
    
    # Фильтруем по кодам
    matching_items = [item for item in items if item.get("code") in codes]
    
    if not matching_items:
        return "К сожалению, информация о товарах временно недоступна. Пожалуйста, свяжитесь с менеджером для уточнения наличия и цен."
    
    # Дополнительная фильтрация по названию, если указан фильтр
    if filters and filters.name_contains:
        name_lower = filters.name_contains.lower()
        matching_items = [
            item for item in matching_items
            if name_lower in item.get("descr", "").lower()
        ]
    
    if not matching_items:
        return f"В указанных группах товары с названием '{filters.name_contains}' не найдены."
    
    result_lines = [
        "Информация о группах товаров (система 1С временно недоступна, данные из каталога):\n"
    ]
    
    for i, item in enumerate(matching_items[:10], 1):  # Ограничиваем 10 группами
        code = item.get("code", "")
        descr = item.get("descr", "Без описания")
        result_lines.append(f"{i}. Группа {code}: {descr}")
    
    if len(matching_items) > 10:
        result_lines.append(f"\n... и еще {len(matching_items) - 10} групп товаров")
    
    result_lines.append(
        "\n⚠️ Для получения актуальных цен и наличия товаров, пожалуйста, свяжитесь с менеджером."
    )
    
    return "\n".join(result_lines)


@tool
async def search_1c_products(request: Search1CProductsRequest) -> str:
    """
    Ищет товары в системе 1С по кодам групп товаров.
    
    Используй этот инструмент, когда клиент спрашивает про:
    - наличие конкретных товаров (брус, доски, вагонка и т.д.)
    - цены на товары
    - размеры и характеристики товаров
    
    Агент должен:
    1. Определить релевантные коды групп из info.json на основе запроса клиента
    2. Вызвать этот tool с массивом кодов
    3. При необходимости указать фильтры (например, name_contains="Брус" для поиска только бруса)
    
    Args:
        request: Параметры запроса с кодами групп и опциональными фильтрами
    """
    # Валидация кодов
    valid_codes, invalid_codes = validate_group_codes(request.group_codes)
    
    if not valid_codes:
        if invalid_codes:
            return f"Ошибка: указанные коды групп не найдены в базе: {', '.join(invalid_codes)}"
        return "Ошибка: не указаны коды групп товаров."
    
    if invalid_codes:
        logger.warning(f"Некоторые коды не найдены: {invalid_codes}")
    
    # Проверяем, включен ли API 1С
    if not C1_API_ENABLED:
        logger.info("API 1С отключен через C1_API_ENABLED, используем fallback из info.json")
        return get_fallback_info(valid_codes, request.filters)
    
    # Подготовка запроса к API 1С
    api_url = f"{C1_API_URL}/products"
    payload = {"codes": valid_codes}
    
    try:
        # Отправка запроса к API 1С
        async with httpx.AsyncClient(timeout=5.0) as client:  # Уменьшили таймаут для быстрого fallback
            response = await client.post(api_url, json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
        # API недоступен - используем fallback из info.json
        logger.warning(f"API 1С недоступен ({type(e).__name__}), используем fallback из info.json")
        return get_fallback_info(valid_codes, request.filters)
    except httpx.HTTPStatusError as e:
        # Если сервер отвечает, но с ошибкой - тоже используем fallback
        logger.warning(f"Ошибка HTTP при запросе к API 1С: {e.response.status_code}, используем fallback")
        return get_fallback_info(valid_codes, request.filters)
    except Exception as e:
        # Любая другая ошибка - fallback
        logger.warning(f"Ошибка при запросе к API 1С: {e}, используем fallback")
        return get_fallback_info(valid_codes, request.filters)
    
    # Парсинг ответа
    products = data.get("products", [])
    
    if not products:
        return "Товары по указанным группам не найдены в системе 1С."
    
    # Применение фильтров
    filtered_products = filter_products(products, request.filters)
    
    # Форматирование ответа
    return format_products_response(filtered_products)

