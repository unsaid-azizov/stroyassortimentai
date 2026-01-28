"""
Утилиты для расчета цен и количеств с учетом разных единиц измерения.

Поддерживаемые единицы измерения из 1C:
- м³ (кубометры) - основная для пиломатериалов
- м² (квадратные метры) - для листовых материалов
- шт (штуки) - поштучная продажа
- м (погонные метры) - для некоторых материалов

Товар может иметь:
- Базовую цену (Цена) в основной ЕИ (обычно м³ или м²)
- Коэффициент для пересчета в доп. ЕИ (Коэфдополнительнаяедизмерения)
"""

import logging
from typing import Optional, Tuple, Dict
import re

logger = logging.getLogger(__name__)


def parse_unit(unit_str: str) -> Tuple[str, Optional[float]]:
    """
    Парсит строку единицы измерения из 1C.

    Примеры:
        "м3" → ("м3", None)
        "м3 (33.333333 шт)" → ("м3", 33.333333)
        "м2 (2.777778 шт)" → ("м2", 2.777778)
        "шт" → ("шт", None)

    Returns:
        (базовая_ЕИ, количество_штук_в_ЕИ)
    """
    if not unit_str:
        return ("шт", None)

    # Парсим формат "м3 (33.33 шт)"
    match = re.match(r'(\S+)\s*\(([0-9.]+)\s*шт\)', unit_str.strip())
    if match:
        base_unit = match.group(1)
        qty_per_unit = float(match.group(2))
        return (base_unit, qty_per_unit)

    # Просто единица без скобок
    return (unit_str.strip(), None)


def calculate_price_per_piece(
    base_price: float,
    base_unit: str,
    pieces_per_unit: Optional[float] = None
) -> Optional[float]:
    """
    Рассчитывает цену за штуку.

    Args:
        base_price: Цена в базовой ЕИ (например, за м³)
        base_unit: Базовая единица измерения (м3, м2, шт)
        pieces_per_unit: Количество штук в базовой ЕИ

    Returns:
        Цена за 1 штуку или None если невозможно рассчитать
    """
    if base_unit == "шт":
        return base_price

    if pieces_per_unit and pieces_per_unit > 0:
        return base_price / pieces_per_unit

    return None


def calculate_total_price(
    base_price: float,
    quantity: float,
    requested_unit: str,
    base_unit: str,
    pieces_per_unit: Optional[float] = None,
    additional_unit_coefficient: Optional[float] = None
) -> Tuple[float, str]:
    """
    Рассчитывает итоговую стоимость с учетом единиц измерения.

    Args:
        base_price: Цена в базовой ЕИ из 1C (Цена)
        quantity: Запрошенное количество
        requested_unit: В какой ЕИ клиент просит (шт, м3, м2)
        base_unit: Базовая ЕИ товара из 1C (ЕдИзмерения)
        pieces_per_unit: Сколько штук в базовой ЕИ
        additional_unit_coefficient: Коэффициент для доп. ЕИ (Коэфдополнительнаяедизмерения)

    Returns:
        (итоговая_цена, пояснение)
    """
    # Нормализуем единицы
    req_unit = requested_unit.lower().strip()
    base_unit_normalized = base_unit.lower().strip().split()[0]  # "м3 (33 шт)" → "м3"

    # Случай 1: Клиент просит в той же ЕИ что и базовая
    if req_unit == base_unit_normalized or req_unit == base_unit.lower():
        total = base_price * quantity
        explanation = f"{quantity} {requested_unit} × {base_price:,.0f} ₽/{base_unit_normalized} = {total:,.0f} ₽"
        return (total, explanation)

    # Случай 2: Клиент просит в штуках, а цена в м³/м²
    if req_unit in ["шт", "штук", "штука", "шт."]:
        if pieces_per_unit and pieces_per_unit > 0:
            price_per_piece = base_price / pieces_per_unit
            total = price_per_piece * quantity
            explanation = f"{quantity} шт × {price_per_piece:,.0f} ₽/шт = {total:,.0f} ₽"
            return (total, explanation)
        else:
            # Невозможно рассчитать цену за штуку
            total = base_price * quantity  # Fallback - умножаем на кол-во
            explanation = f"⚠️ Цена указана в {base_unit_normalized}, а не в штуках. Для точного расчета нужен коэффициент."
            return (total, explanation)

    # Случай 3: Клиент просит в м², а цена в м³ (или наоборот)
    if additional_unit_coefficient and additional_unit_coefficient > 0:
        # Используем коэффициент для пересчета
        converted_quantity = quantity * additional_unit_coefficient
        total = base_price * converted_quantity
        explanation = f"{quantity} {requested_unit} (= {converted_quantity:.2f} {base_unit_normalized}) × {base_price:,.0f} ₽/{base_unit_normalized} = {total:,.0f} ₽"
        return (total, explanation)

    # Случай 4: Прямой расчет без коэффициентов
    total = base_price * quantity
    explanation = f"{quantity} {requested_unit} × {base_price:,.0f} ₽/{base_unit_normalized} = {total:,.0f} ₽"
    return (total, explanation)


def format_product_info(product_data: Dict) -> str:
    """
    Форматирует информацию о товаре для отображения клиенту.

    Args:
        product_data: Словарь с данными товара из Redis/1C

    Returns:
        Отформатированная строка с информацией о товаре
    """
    # Используем Наименованиедлясайта если есть, иначе обычное Наименование
    name = product_data.get('Наименованиедлясайта') or product_data.get('Наименование') or product_data.get('item_name', 'Без названия')

    price = product_data.get('Цена')
    unit = product_data.get('ЕдИзмерения', 'шт')
    stock = product_data.get('Остаток', 'Не указан')

    # Парсим базовую ЕИ
    base_unit, pieces_per_unit = parse_unit(unit)

    # Формируем строку
    info_parts = [name]

    # Цена
    if price:
        info_parts.append(f"Цена: {price:,.0f} ₽/{base_unit}".replace(",", " "))

        # Если есть цена за штуку - добавим её
        if pieces_per_unit and pieces_per_unit > 0:
            price_per_piece = price / pieces_per_unit
            info_parts.append(f"({price_per_piece:,.0f} ₽/шт)".replace(",", " "))

    # Остаток
    info_parts.append(f"Остаток: {stock}")

    # Дополнительная информация
    additional_info = []
    if product_data.get('Порода'):
        additional_info.append(f"Порода: {product_data['Порода']}")
    if product_data.get('Влажность'):
        additional_info.append(f"Влажность: {product_data['Влажность']}")
    if product_data.get('Сорт'):
        additional_info.append(f"Сорт: {product_data['Сорт']}")

    if additional_info:
        info_parts.append(" | ".join(additional_info))

    return "\n".join(info_parts)


def calculate_volume_from_dimensions(
    thickness_mm: float,
    width_mm: float,
    length_mm: float,
    quantity: int
) -> float:
    """
    Рассчитывает объем в м³ по размерам.

    Args:
        thickness_mm: Толщина в миллиметрах
        width_mm: Ширина в миллиметрах
        length_mm: Длина в миллиметрах
        quantity: Количество штук

    Returns:
        Объем в кубометрах
    """
    # Переводим мм в метры и считаем объем
    volume_one_piece = (thickness_mm / 1000) * (width_mm / 1000) * (length_mm / 1000)
    total_volume = volume_one_piece * quantity
    return total_volume


def calculate_area_from_dimensions(
    width_mm: float,
    length_mm: float,
    quantity: int
) -> float:
    """
    Рассчитывает площадь в м² по размерам.

    Args:
        width_mm: Ширина в миллиметрах
        length_mm: Длина в миллиметрах
        quantity: Количество штук

    Returns:
        Площадь в квадратных метрах
    """
    # Переводим мм в метры и считаем площадь
    area_one_piece = (width_mm / 1000) * (length_mm / 1000)
    total_area = area_one_piece * quantity
    return total_area
