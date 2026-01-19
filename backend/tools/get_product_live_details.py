"""
Tool для получения актуальной информации о товаре из 1С API.
Используется после того, как клиент определился с конкретным товаром.
"""
import os
import requests
from requests.auth import HTTPBasicAuth
from typing import List, Dict, Any
from langchain.tools import tool
import json


def fetch_live_product_details(item_codes: List[str]) -> List[Dict[str, Any]]:
    """
    Получить актуальную информацию о товарах из 1С через API GetDetailedItems.

    Args:
        item_codes: Список кодов товаров (из CSV или из предыдущего поиска)

    Returns:
        Список товаров с актуальной информацией (цена, остаток, характеристики)
    """
    base_url = os.getenv("C1_DETAILED_API_URL", "http://172.16.77.34/stroyast_test/hs/Ai/GetDetailedItems")
    username = os.getenv("C1_API_USER", "Admin")
    password = os.getenv("C1_API_PASSWORD", "789654")
    timeout = int(os.getenv("C1_API_TIMEOUT_SECONDS", "30"))

    auth = HTTPBasicAuth(username, password)
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Accept': 'application/json'
    }

    payload = {"items": item_codes}

    response = requests.post(
        base_url,
        json=payload,
        auth=auth,
        headers=headers,
        timeout=timeout
    )
    response.encoding = response.apparent_encoding or 'utf-8'
    response.raise_for_status()

    data = response.json()
    return data.get('items', [])


@tool
def get_product_live_details(item_codes: str) -> str:
    """
    Получить актуальную информацию о конкретном товаре из 1С (цена, остаток на складе).

    ВАЖНО: Используй этот инструмент ПОСЛЕ того, как клиент определился с конкретным товаром
    и хочет узнать актуальную цену и наличие.

    Args:
        item_codes: Код товара или несколько кодов через запятую (например: "00-00010232" или "00-00010232,00-00010233")

    Returns:
        Актуальная информация о товарах с ценами и остатками

    Example:
        User: "Сколько сейчас стоит вагонка штиль 13х115х6000 класс АВ?"
        Assistant: [Сначала ищем через search_products_tool, получаем код товара]
        Assistant: [Используем get_product_live_details с кодом товара для актуальной цены]
    """
    if not item_codes or not item_codes.strip():
        return "Ошибка: необходимо указать код товара. Сначала найдите товар через search_products_tool."

    # Parse codes (поддержка нескольких кодов через запятую)
    codes = [code.strip() for code in item_codes.split(",") if code.strip()]

    if not codes:
        return "Ошибка: неверный формат кода товара."

    items = fetch_live_product_details(codes)

    if not items:
        return f"Товары с кодами {item_codes} не найдены в 1С или временно недоступны."

    # Format response
    response_lines = [f"Актуальная информация о {len(items)} товаре(ах) из 1С:", ""]

    for i, item in enumerate(items, 1):
        name = item.get("Наименованиедлясайта") or item.get("Наименование") or item.get("item_name", "N/A")
        price = item.get("Цена", "N/A")
        stock = item.get("Остаток", "N/A")
        code = item.get("Код", codes[i-1] if i <= len(codes) else "N/A")

        response_lines.append(f"### {i}. {name}")
        response_lines.append(f"   Код: {code}")
        response_lines.append(f"   💰 Цена: {price} руб.")
        response_lines.append(f"   📦 Остаток: {stock}")

        # Характеристики
        material_type = item.get("Видпиломатериала")
        wood = item.get("Порода")
        grade = item.get("Сорт")
        thickness = item.get("Толщина")
        width = item.get("Ширина")
        length = item.get("Длина")
        moisture = item.get("Влажность")
        treatment = item.get("Типобработки")

        if any([material_type, wood, grade, thickness, width, length]):
            response_lines.append("   ")
            response_lines.append("   📋 Характеристики:")
            if material_type:
                response_lines.append(f"      Вид: {material_type}")
            if wood:
                response_lines.append(f"      Порода: {wood}")
            if grade:
                response_lines.append(f"      Сорт/Класс: {grade}")
            if thickness and width and length:
                response_lines.append(f"      Размеры: {thickness}х{width}х{length} мм")
            elif any([thickness, width, length]):
                dims = []
                if thickness:
                    dims.append(f"толщина {thickness}")
                if width:
                    dims.append(f"ширина {width}")
                if length:
                    dims.append(f"длина {length}")
                response_lines.append(f"      Размеры: {', '.join(dims)}")
            if moisture:
                response_lines.append(f"      Влажность: {moisture}")
            if treatment:
                response_lines.append(f"      Обработка: {treatment}")

        # Дополнительно
        production_days = item.get("СрокпроизводстваднОбщие")
        if production_days:
            response_lines.append(f"   ⏱️ Срок производства: {production_days} дней")

        response_lines.append("")

    return "\n".join(response_lines)
