"""
Инструмент калькулятора для расчета объемов, площадей и стоимости пиломатериалов.

Агент может использовать этот инструмент для точных расчетов при общении с клиентом.
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field
from langchain.tools import tool

logger = logging.getLogger(__name__)


class CalculationRequest(BaseModel):
    """Запрос на расчет."""

    calculation_type: str = Field(
        description="Тип расчета: 'volume' (объем в м³), 'area' (площадь в м²), 'price' (стоимость), 'pieces' (количество штук)"
    )
    thickness_mm: Optional[float] = Field(None, description="Толщина в миллиметрах (для объема)")
    width_mm: Optional[float] = Field(None, description="Ширина в миллиметрах")
    length_mm: Optional[float] = Field(None, description="Длина в миллиметрах")
    quantity: Optional[int] = Field(None, description="Количество штук")
    volume_m3: Optional[float] = Field(None, description="Объем в кубометрах (для расчета кол-ва штук)")
    area_m2: Optional[float] = Field(None, description="Площадь в квадратных метрах")
    price_per_unit: Optional[float] = Field(None, description="Цена за единицу (м³, м², шт)")
    unit: Optional[str] = Field(None, description="Единица измерения цены (м3, м2, шт)")


@tool
def calculate(request: CalculationRequest) -> str:
    """
    Калькулятор для строительных расчетов.

    Может рассчитать:
    1. Объем в м³ по размерам: thickness_mm × width_mm × length_mm × quantity
    2. Площадь в м² по размерам: width_mm × length_mm × quantity
    3. Стоимость: количество × цена_за_единицу
    4. Количество штук в объеме: volume_m3 / (объем_одной_штуки)

    Примеры использования:
    - Сколько будет м³ в 100 досках 50×150×6000?
      → calculate(calculation_type="volume", thickness_mm=50, width_mm=150, length_mm=6000, quantity=100)

    - Какая площадь у 50 листов ОСБ 1250×2500?
      → calculate(calculation_type="area", width_mm=1250, length_mm=2500, quantity=50)

    - Сколько стоит 2.5 м³ доски по 20500₽/м³?
      → calculate(calculation_type="price", volume_m3=2.5, price_per_unit=20500, unit="м3")

    - Сколько досок 50×150×6000 в 1 м³?
      → calculate(calculation_type="pieces", thickness_mm=50, width_mm=150, length_mm=6000, volume_m3=1)
    """
    calc_type = request.calculation_type.lower()

    try:
        if calc_type == "volume":
            # Расчет объема в м³
            if not all([request.thickness_mm, request.width_mm, request.length_mm, request.quantity]):
                return "❌ Для расчета объема нужны: thickness_mm, width_mm, length_mm, quantity"

            # Переводим мм в метры
            volume_one = (request.thickness_mm / 1000) * (request.width_mm / 1000) * (request.length_mm / 1000)
            total_volume = volume_one * request.quantity

            result = f"""📐 Расчет объема:
Размеры: {request.thickness_mm}×{request.width_mm}×{request.length_mm} мм
Количество: {request.quantity} шт
Объем 1 шт: {volume_one:.6f} м³ ({volume_one * 1000:.2f} л)
Итого: {total_volume:.4f} м³

В 1 м³: {1/volume_one:.1f} шт"""
            return result

        elif calc_type == "area":
            # Расчет площади в м²
            if not all([request.width_mm, request.length_mm, request.quantity]):
                return "❌ Для расчета площади нужны: width_mm, length_mm, quantity"

            # Переводим мм в метры
            area_one = (request.width_mm / 1000) * (request.length_mm / 1000)
            total_area = area_one * request.quantity

            result = f"""📐 Расчет площади:
Размеры: {request.width_mm}×{request.length_mm} мм
Количество: {request.quantity} шт
Площадь 1 шт: {area_one:.4f} м²
Итого: {total_area:.2f} м²

В 1 м²: {1/area_one:.2f} шт"""
            return result

        elif calc_type == "price":
            # Расчет стоимости
            if not request.price_per_unit:
                return "❌ Для расчета стоимости нужна цена (price_per_unit)"

            # Определяем количество
            if request.volume_m3:
                qty = request.volume_m3
                qty_str = f"{qty:.2f} м³"
            elif request.area_m2:
                qty = request.area_m2
                qty_str = f"{qty:.2f} м²"
            elif request.quantity:
                qty = request.quantity
                qty_str = f"{qty} шт"
            else:
                return "❌ Укажите количество (volume_m3, area_m2 или quantity)"

            total = qty * request.price_per_unit
            unit = request.unit or "ед"

            result = f"""💰 Расчет стоимости:
Количество: {qty_str}
Цена: {request.price_per_unit:,.0f} ₽/{unit}
Итого: {total:,.0f} ₽""".replace(",", " ")
            return result

        elif calc_type == "pieces":
            # Расчет количества штук
            if not all([request.thickness_mm, request.width_mm, request.length_mm]):
                return "❌ Для расчета штук нужны размеры: thickness_mm, width_mm, length_mm"

            if not (request.volume_m3 or request.area_m2):
                return "❌ Укажите объем (volume_m3) или площадь (area_m2)"

            if request.volume_m3:
                # Расчет по объему
                volume_one = (request.thickness_mm / 1000) * (request.width_mm / 1000) * (request.length_mm / 1000)
                pieces = request.volume_m3 / volume_one

                result = f"""📏 Расчет количества штук:
Размеры 1 шт: {request.thickness_mm}×{request.width_mm}×{request.length_mm} мм
Объем 1 шт: {volume_one:.6f} м³
В {request.volume_m3:.2f} м³: {pieces:.1f} шт"""
                return result

            elif request.area_m2:
                # Расчет по площади
                area_one = (request.width_mm / 1000) * (request.length_mm / 1000)
                pieces = request.area_m2 / area_one

                result = f"""📏 Расчет количества штук:
Размеры 1 шт: {request.width_mm}×{request.length_mm} мм
Площадь 1 шт: {area_one:.4f} м²
В {request.area_m2:.2f} м²: {pieces:.1f} шт"""
                return result

        else:
            return f"❌ Неизвестный тип расчета: {calc_type}. Доступны: volume, area, price, pieces"

    except Exception as e:
        logger.error(f"Ошибка в калькуляторе: {e}")
        return f"❌ Ошибка расчета: {str(e)}"
