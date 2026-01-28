"""
Tools для агента продаж.
Универсальный tool для поиска информации в статичной базе данных компании.
А также инструменты для активных продаж и вызова менеджера.
Интеграция с системой 1С для поиска товаров.
"""
from .search_company_info import search_company_info
from .sales_tools import call_manager, collect_order_info
from .product_search_bm25 import search_products_tool
from .get_product_live_details import get_product_live_details
from .calculator_tool import calculate

# Список всех доступных tools
__all__ = [
    "search_company_info",
    "call_manager",
    "collect_order_info",
    "search_products_tool",  # BM25 product search (offline CSV)
    "get_product_live_details",  # Live data from 1C API
    "calculate",  # Calculator for volume/area/price calculations
]

