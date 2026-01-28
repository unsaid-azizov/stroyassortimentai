"""
Tool для получения актуальной информации о товаре через API.
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
    Получить актуальную информацию о товарах через ERP API.

    Args:
        item_codes: Список кодов товаров (из каталога или из предыдущего поиска)

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
    Получить актуальную информацию о конкретном товаре (цена, остаток на складе).

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
        return f"Товары с кодами {item_codes} не найдены или временно недоступны."

    # Format response
    response_lines = [f"Актуальная информация о {len(items)} товаре(ах):", ""]

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
        klass = item.get("Класс")
        thickness = item.get("Толщина")
        width = item.get("Ширина")
        length = item.get("Длина")
        moisture = item.get("Влажность")
        treatment = item.get("Типобработки")
        density = item.get("Плотностькгм3Общие")
        extra_property = item.get("Допсвойство")
        popularity = item.get("ПопулярностьОбщие")

        response_lines.append("   ")
        response_lines.append("   📋 Характеристики:")

        if material_type:
            response_lines.append(f"      Вид: {material_type}")
        if wood:
            response_lines.append(f"      Порода: {wood}")

        # Сорт или Класс
        if grade and klass:
            response_lines.append(f"      Сорт/Класс: {grade} ({klass})")
        elif grade:
            response_lines.append(f"      Сорт: {grade}")
        elif klass:
            response_lines.append(f"      Класс: {klass}")

        # Размеры
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
        if density:
            response_lines.append(f"      Плотность: {density} кг/м³")
        if extra_property:
            response_lines.append(f"      Доп. свойство: {extra_property}")
        if popularity and float(popularity) > 0:
            response_lines.append(f"      ⭐ Популярность: {popularity}")

        # Дополнительная информация
        production_days = item.get("СрокпроизводстваднОбщие")
        qty_m2 = item.get("Количествовм2Общие")
        qty_m3 = item.get("Количествовм3Общие")
        qty_pack = item.get("КоличествовупаковкеОбщие")
        extra_unit1 = item.get("Дополнительнаяедизмерения1")
        extra_unit2 = item.get("Дополнительнаяедизмерения2")
        extra_unit3 = item.get("Дополнительнаяедизмерения3Общие")

        additional_info = []
        if production_days:
            additional_info.append(f"⏱️ Срок производства: {production_days} дней")
        if qty_m2:
            additional_info.append(f"📐 В 1 шт: {qty_m2} м²")
        if qty_m3:
            additional_info.append(f"📦 В 1 шт: {qty_m3} м³")
        if qty_pack:
            additional_info.append(f"📦 В упаковке: {qty_pack} шт")
        if extra_unit1:
            additional_info.append(f"Ед.изм.1: {extra_unit1}")
        if extra_unit2:
            additional_info.append(f"Ед.изм.2: {extra_unit2}")
        if extra_unit3:
            additional_info.append(f"Ед.изм.3: {extra_unit3}")

        if additional_info:
            response_lines.append("   ")
            for info in additional_info:
                response_lines.append(f"   {info}")

        response_lines.append("")

    return "\n".join(response_lines)
