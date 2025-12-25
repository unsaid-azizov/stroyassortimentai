"""
Tools для агента продаж.
Универсальный tool для поиска информации в статичной базе данных компании.
А также инструменты для активных продаж и вызова менеджера.
Интеграция с системой 1С для поиска товаров.
"""
from .search_company_info import search_company_info
from .sales_tools import call_manager, collect_order_info
from .search_1c_products import search_1c_products

# Список всех доступных tools
__all__ = [
    "search_company_info",
    "call_manager",
    "collect_order_info",
    "search_1c_products",
]

