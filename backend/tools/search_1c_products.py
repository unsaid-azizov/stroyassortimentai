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
from pydantic import BaseModel, Field, ValidationError

from .c1_schemas import (
    C1DetailedItem,
    C1ShortItem,
    parse_get_detailed_items_payload,
    parse_get_items_payload,
)

logger = logging.getLogger(__name__)

# URL API 1С (можно переопределить через переменную окружения)
C1_API_URL = os.getenv("C1_API_URL", "http://172.16.77.34/stroyast_copy_itspec_38601/hs/AiBot/GetItems")
C1_DETAILED_API_URL = os.getenv("C1_DETAILED_API_URL", "http://172.16.77.34/stroyast_copy_itspec_38601/hs/AiBot/GetDetailedItems")
C1_API_USER = os.getenv("C1_API_USER", "Администратор")
C1_API_PASSWORD = os.getenv("C1_API_PASSWORD", "159753")
#
# Network tuning (to reduce flakiness / timeouts on heavy queries)
C1_API_TIMEOUT_SECONDS = float(os.getenv("C1_API_TIMEOUT_SECONDS", "30"))
# If the model passes too many group codes at once, 1C may respond slowly; we chunk requests.
C1_MAX_GROUP_CODES_PER_REQUEST = int(os.getenv("C1_MAX_GROUP_CODES_PER_REQUEST", "7"))

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


class Search1CProductsRequest(BaseModel):
    """Параметры запроса для поиска списка товаров по группам."""
    group_codes: List[str] = Field(description="Список кодов групп товаров из info.json (например, ['00-00022304', '00-00020587'])")
    filters: Optional[ProductFilters] = Field(None, description="Опциональные фильтры для поиска внутри группы")


class GetProductDetailsRequest(BaseModel):
    """Параметры запроса для получения детальной информации о конкретных товарах."""
    product_codes: List[str] = Field(
        description="Список кодов конкретных товаров (например, ['00-00003162', '00-00004340'])"
    )


def validate_group_codes(codes: List[str]) -> tuple[List[str], List[str]]:
    """
    Валидирует коды групп товаров.
    Возвращает (валидные_коды, невалидные_коды).
    
    ВАЖНО: Если переданные коды не найдены в группах, но выглядят как коды товаров (например, из предыдущего ответа),
    функция вернет их как невалидные. Агент должен использовать только коды ГРУПП из info.json!
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
            # Логируем предупреждение, если код похож на код товара
            if len(code) > 8 and code.startswith("00-"):
                logger.warning(f"Код '{code}' не найден в группах. Возможно, это код товара, а не группы. "
                             f"Используй коды ГРУПП из info.json для search_1c_products, а коды ТОВАРОВ - для get_product_details!")
    
    return valid_codes, invalid_codes


def filter_products(products: List[Any], filters: Optional[ProductFilters]) -> List[Any]:
    """
    Фильтрует список товаров по заданным критериям.
    Поддерживает ключи 'Наименование', 'Цена', 'Код' от 1С.
    """
    if not filters:
        return products
    
    filtered = products
    
    # Фильтр по названию
    if filters.name_contains:
        name_lower = filters.name_contains.lower()
        new_filtered = []
        for p in filtered:
            if isinstance(p, dict):
                # Пробуем русские и английские ключи
                name = (p.get("Наименование") or p.get("name") or "").lower()
            else:
                name = str(p).lower()
            
            if name_lower in name:
                new_filtered.append(p)
        filtered = new_filtered
    
    # Фильтры по цене
    if filters.min_price is not None:
        filtered = [
            p for p in filtered
            if isinstance(p, dict) and (p.get("Цена") or p.get("price") or 0) >= filters.min_price
        ]
    
    if filters.max_price is not None:
        filtered = [
            p for p in filtered
            if isinstance(p, dict) and (p.get("Цена") or p.get("price") or 0) <= filters.max_price
        ]
    
    return filtered


def _dedupe_products_by_code(products: List[Any]) -> List[Any]:
    """Deduplicate list of product dicts by 'Код' / 'code' while preserving order."""
    seen: set[str] = set()
    out: List[Any] = []
    for p in products:
        if isinstance(p, dict):
            code = p.get("Код") or p.get("code")
            if isinstance(code, str) and code:
                if code in seen:
                    continue
                seen.add(code)
        out.append(p)
    return out


def _chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        return [items]
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def format_products_response(products: List[Any]) -> str:
    """
    Форматирует краткий список товаров для ответа клиенту (результат GetItems).
    """
    if not products:
        return "К сожалению, товары по вашему запросу не найдены."

    MISSING = "не найдено"
    PRICE_MISSING = "уточним у менеджера"
    
    result_lines = [f"Найдено товаров: {len(products)}", "Выберите интересующие позиции для получения подробностей (цены, остатки, характеристики):\n"]
    
    for i, product in enumerate(products[:30], 1):  # Увеличим лимит для краткого списка
        if not isinstance(product, dict):
            result_lines.append(f"{i}. {product}")
            continue

        try:
            parsed = C1ShortItem.model_validate(product)
        except ValidationError:
            parsed = C1ShortItem()

        name = parsed.name or MISSING
        code = parsed.code or MISSING

        line = f"{i}. {name}"
        if parsed.price is None:
            line += f" — цена: {PRICE_MISSING}"
        else:
            # keep compact (avoid trailing .0)
            price_txt = str(int(parsed.price)) if float(parsed.price).is_integer() else str(parsed.price)
            line += f" — {price_txt} руб."

        # Show stock only if present (otherwise keep list compact)
        if parsed.stock.kind != "unknown":
            line += f" — остатки: {parsed.stock.display}"

        line += f" (Код: {code})"
        
        result_lines.append(line)
    
    if len(products) > 30:
        result_lines.append(f"\n... и еще {len(products) - 30} товаров")
    
    return "\n".join(result_lines)


def format_detailed_products_response(products: List[Dict[str, Any]]) -> str:
    """
    Форматирует детальную информацию о товарах (результат GetDetailedItems).
    """
    if not products:
        return "Детальная информация о выбранных товарах не найдена."

    MISSING = "не найдено"
    PRICE_MISSING = "уточним у менеджера"
    
    result_lines = ["Детальная информация по выбранным товарам:\n"]
    
    for i, p in enumerate(products, 1):
        try:
            parsed = C1DetailedItem.model_validate(p)
        except ValidationError:
            parsed = C1DetailedItem()

        def show(val: Any) -> str:
            if val is None:
                return MISSING
            if isinstance(val, str) and not val.strip():
                return MISSING
            s = str(val).strip()
            if s in ("0", "0.0", "0,0"):
                return MISSING
            return s

        name = parsed.name or parsed.site_name or MISSING
        price = show(parsed.price)
        if price == MISSING:
            price = PRICE_MISSING

        details = [
            f"- Остатки: {parsed.stock.display if parsed.stock.kind != 'unknown' else MISSING}",
            f"- Обработка: {show(parsed.treatment_type)}",
            f"- Порода: {show(parsed.species)}",
            f"- Толщина (мм): {show(parsed.thickness_mm)}",
            f"- Ширина (мм): {show(parsed.width_mm)}",
            f"- Длина (мм): {show(parsed.length_mm)}",
            f"- Влажность: {show(parsed.humidity)}",
            f"- Сорт: {show(parsed.sort)}",
            f"- Вид: {show(parsed.lumber_type)}",
            f"- В упаковке (шт): {show(parsed.qty_in_pack_common)}",
            f"- В 1 м³ (шт): {show(parsed.quantity_m3_common)}",
            f"- В 1 м² (шт): {show(parsed.quantity_m2_common)}",
            f"- Срок производства (дней): {show(parsed.production_days_common)}",
            f"- Плотность (кг/м³): {show(parsed.density_kg_m3_common)}",
        ]
        
        product_block = [
            f"{i}. {name}",
            f"   Цена: {price} руб."
        ]
        
        # Примечание по остаткам:
        # В нашем 1C API иногда приходит поле "Остатки" (может быть числом или строкой "По предзаказу",
        # а иногда отсутствует). Если поля нет/непонятно — говорим "точное наличие подтвердит менеджер".
        product_block.extend([f"   {d}" for d in details])
        
        result_lines.append("\n".join(product_block))
        result_lines.append("-" * 20)
    
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
    ШАГ 1: Поиск списка товаров по кодам ГРУПП (API: GetItems).
    
    ИНСТРУКЦИЯ ОТ 1С ПРОГРАММИСТА:
    - GetItems принимает коды ГРУПП из info.json (например, ['00-00022304', '00-00003956'])
    - GetItems возвращает список товаров с их КОДАМИ (например, '00-00003162', '00-00004340')
    - Эти коды товаров потом используются в GetDetailedItems для получения детальной информации
    
    ИСПОЛЬЗУЙ ЭТОТ ИНСТРУМЕНТ СРАЗУ, когда клиент просит:
    - "проверь наличие", "какие товары есть", "посмотри на складе"
    - "какая цена на...", "есть ли в наличии..."
    - "покажи товары", "что есть из..."
    
    КРИТИЧЕСКИ ВАЖНО: 
    - На вход принимает КОДЫ ГРУПП из info.json (например, ['00-00022304', '00-00020587']), НЕ коды товаров!
    - Если клиент упоминает товар (например, "брус 150x150"), найди релевантные ГРУППЫ в info.json:
      * Ищи в поле "descr" групп слова, связанные с товаром (брус, доска, вагонка и т.д.)
      * Используй коды найденных групп, НЕ коды товаров из предыдущих ответов!
    
    Возвращает список товаров с названиями, ценами и КОДАМИ ТОВАРОВ (например, '00-00003162').
    Эти коды товаров потом используй в get_product_details для получения детальной информации!
    
    Агент должен:
    1. Определить релевантные коды ГРУПП из info.json на основе запроса клиента.
       Например, если клиент говорит "брус 150x150" - найди группы, где в descr есть "брус" или "брусы".
    2. СРАЗУ вызвать этот tool с кодами ГРУПП, не задавая дополнительных вопросов!
    3. После получения ответа АВТОМАТИЧЕСКИ вызвать get_product_details с кодами ТОВАРОВ из ответа!
    
    ОШИБКА: Если получил ошибку "коды групп не найдены" - значит использовал коды ТОВАРОВ вместо кодов ГРУПП!
    Решение: найди правильные коды ГРУПП в info.json по описанию товара.
    """
    # Валидация кодов
    valid_codes, invalid_codes = validate_group_codes(request.group_codes)
    
    if not valid_codes:
        if invalid_codes:
            # Пытаемся найти релевантные группы по описанию, если переданные коды невалидны
            error_msg = f"Ошибка: указанные коды не найдены в группах: {', '.join(invalid_codes)}"
            error_msg += "\n\n⚠️ ВАЖНО: Возможно, ты использовал коды ТОВАРОВ вместо кодов ГРУПП!"
            error_msg += "\nДля search_1c_products нужны коды ГРУПП из info.json (например, '00-00022304'), а не коды товаров!"
            error_msg += "\nНайди релевантные группы в info.json по описанию товара (брус, доска и т.д.) и используй их коды."
            return error_msg
        return "Ошибка: не указаны коды групп товаров."
    
    if not C1_API_ENABLED:
        return get_fallback_info(valid_codes, request.filters)
    
    api_url = C1_API_URL
    auth = (C1_API_USER, C1_API_PASSWORD)
    
    chunks = _chunk_list(valid_codes, C1_MAX_GROUP_CODES_PER_REQUEST)
    if len(chunks) > 1:
        logger.info(
            f"GetItems: много кодов групп ({len(valid_codes)}), разбиваем на {len(chunks)} запрос(а/ов) "
            f"по {C1_MAX_GROUP_CODES_PER_REQUEST} кодов."
        )
    
    try:
        timeout = httpx.Timeout(C1_API_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            aggregated: List[Any] = []
            for group_codes_chunk in chunks:
                payload = {"items": group_codes_chunk}
                logger.info(f"Запрос к GetItems (search_1c_products): URL={api_url}, Payload={payload}")
                response = await client.post(api_url, json=payload, auth=auth)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Ответ GetItems: {str(data)[:500]}...")  # Логируем начало ответа

                # Validate shape and normalize with Pydantic (tolerant; still keep raw dicts below).
                try:
                    parsed_items = parse_get_items_payload(data)
                    safe_codes = {it.code for it in parsed_items if it.code}
                except ValidationError as e:
                    logger.warning(f"Pydantic validation failed for GetItems payload: {e}")
                    safe_codes = set()

                if isinstance(data, dict):
                    items_raw = data.get("items", []) or []
                elif isinstance(data, list):
                    items_raw = data
                else:
                    items_raw = []

                # Keep only dict items and (if available) only those with codes we could parse.
                for it in items_raw:
                    if not isinstance(it, dict):
                        continue
                    code = it.get("Код") or it.get("code")
                    if not code:
                        continue
                    if safe_codes and code not in safe_codes:
                        continue
                    aggregated.append(it)

            products = _dedupe_products_by_code(aggregated)
    except httpx.HTTPStatusError as e:
        # Log server response excerpt to help debug 1C-side errors
        status = getattr(e.response, "status_code", None)
        text = ""
        try:
            text = (e.response.text or "")[:800]
        except Exception:
            text = ""
        logger.warning(f"Ошибка HTTP при запросе к GetItems: status={status}, err={repr(e)}, body={text}")
        return get_fallback_info(valid_codes, request.filters)
    except httpx.TimeoutException as e:
        logger.warning(f"Таймаут при запросе к GetItems: timeout={C1_API_TIMEOUT_SECONDS}s, err={repr(e)}")
        return get_fallback_info(valid_codes, request.filters)
    except httpx.RequestError as e:
        logger.warning(f"Сетевая ошибка при запросе к GetItems: err={repr(e)}")
        return get_fallback_info(valid_codes, request.filters)
    except Exception as e:
        logger.warning(f"Неожиданная ошибка при запросе к GetItems: {repr(e)}")
        return get_fallback_info(valid_codes, request.filters)

    if not products:
        return "Товары по указанным группам не найдены."
    
    filtered_products = filter_products(products, request.filters)
    return format_products_response(filtered_products)


@tool
async def get_product_details(request: GetProductDetailsRequest) -> str:
    """
    ШАГ 2: Получение подробной информации о конкретных товарах (API: GetDetailedItems).
    
    ИНСТРУКЦИЯ ОТ 1С ПРОГРАММИСТА:
    - GetDetailedItems принимает коды ТОВАРОВ, которые получили из GetItems
    - Например, если GetItems вернул товары с кодами '00-00003162', '00-00004340' - используй эти коды здесь
    - GetDetailedItems возвращает детальную информацию по каждому товару
    
    ОБЯЗАТЕЛЬНО используй этот инструмент ПОСЛЕ search_1c_products, чтобы показать детали товара!
    
    На вход принимает список КОДОВ ТОВАРОВ (не групп!), которые получил из ответа search_1c_products.
    Например, если search_1c_products вернул товар с кодом '00-00003162', используй этот код здесь.
    
    Возвращает детальную информацию: порода, сорт, влажность, размеры, цена, срок производства и т.д.
    
    ВАЖНО про наличие/остатки:
    - В API 1С может приходить поле "Остатки" (иногда число, иногда текст вроде "По предзаказу", иногда отсутствует).
    - Это поле не всегда означает "N штук на складе" (единица измерения зависит от настройки 1С).
    - Если "Остатки" нет или оно неочевидно — говори "точное наличие подтвердит менеджер" и при необходимости зови call_manager.
    
    Агент должен:
    1. После получения списка товаров из search_1c_products АВТОМАТИЧЕСКИ вызвать этот tool с кодами товаров из ответа.
    2. Показать клиенту детальную информацию (порода, сорт, влажность, цена, размеры, срок производства).
    3. Спросить детали заказа: количество, сорт (если есть варианты), телефон.
    4. Перед оформлением заказа уточнить наличие нужного количества (через менеджера, если нужно).
    """
    if not request.product_codes:
        return "Ошибка: не указаны коды товаров для получения деталей."
    
    if not C1_API_ENABLED:
        return "Детальная информация временно недоступна (API отключен)."
    
    api_url = C1_DETAILED_API_URL
    payload = {"items": request.product_codes}
    auth = (C1_API_USER, C1_API_PASSWORD)
    
    logger.info(f"Запрос к GetDetailedItems: URL={api_url}, Payload={payload}")
    
    try:
        timeout = httpx.Timeout(C1_API_TIMEOUT_SECONDS)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(api_url, json=payload, auth=auth)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Ответ GetDetailedItems: {str(data)[:500]}...") # Логируем начало ответа
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        text = ""
        try:
            text = (e.response.text or "")[:800]
        except Exception:
            text = ""
        logger.error(f"Ошибка HTTP при запросе к GetDetailedItems: status={status}, err={repr(e)}, body={text}")
        return "Не удалось получить детальную информацию (ошибка сервера)."
    except httpx.TimeoutException as e:
        logger.error(f"Таймаут при запросе к GetDetailedItems: timeout={C1_API_TIMEOUT_SECONDS}s, err={repr(e)}")
        return "Не удалось получить детальную информацию (таймаут)."
    except httpx.RequestError as e:
        logger.error(f"Сетевая ошибка при запросе к GetDetailedItems: err={repr(e)}")
        return "Не удалось получить детальную информацию (сетевая ошибка)."
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запросе к GetDetailedItems: {repr(e)}")
        return "Не удалось получить детальную информацию (неизвестная ошибка)."

    # Validate with Pydantic (does not change behavior; helps catch shape changes early)
    try:
        _ = parse_get_detailed_items_payload(data)
    except ValidationError as e:
        logger.warning(f"Pydantic validation failed for GetDetailedItems payload: {e}")
    
    if isinstance(data, dict):
        products = data.get("items", [])
    elif isinstance(data, list):
        products = data
    else:
        products = []
    
    if not products:
        return "Детальная информация по указанным кодам не найдена."
    
    return format_detailed_products_response(products)

