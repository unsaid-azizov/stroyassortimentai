"""
Универсальный tool для получения информации из базы знаний компании.
Агент просто выбирает нужный раздел и получает полные данные.
"""
from pathlib import Path
import json
from typing import Dict, Optional

try:
    from langchain.tools import tool
except ImportError:
    def tool(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


def load_company_info() -> Dict:
    """Load company information from JSON file."""
    info_path = Path(__file__).parent.parent / "data" / "company_info.json"
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


@tool
def search_company_info(section: str) -> str:
    """
    Получить полную информацию о компании из базы знаний по указанному разделу.
    
    ОБЯЗАТЕЛЬНО используй этот инструмент, если клиент спрашивает про:
    - адрес, контакты, склад, проезд -> раздел 'contacts'
    - доставку, самовывоз, транспорт -> раздел 'delivery'
    - виды дерева, категории товаров, наличие материалов -> раздел 'product_categories'
    - услуги, производство, распил -> раздел 'services'
    - способы оплаты -> раздел 'payment'
    - возврат, гарантию -> раздел 'warranty_and_return'
    - акции, скидки -> раздел 'special_offers'
    - любые другие вопросы -> раздел 'faq' или 'company'
    
    Args:
        section: Название раздела ('company', 'contacts', 'delivery', 'product_categories', 'services', 'payment', 'warranty_and_return', 'special_offers', 'faq')
    """
    company_info = load_company_info()
    
    if not company_info:
        return "Информация временно недоступна. Телефон: +7 (499) 302-55-01"

    section = section.lower().strip()
    
    # Прямое получение раздела
    data = company_info.get(section)
    
    if not data:
        # Если агент ошибся в названии, даем список доступных
        available = ", ".join(company_info.keys())
        return f"Раздел '{section}' не найден. Доступные разделы: {available}"

    # Возвращаем JSON - модели его обожают и отлично в нем ориентируются
    return json.dumps(data, indent=2, ensure_ascii=False)
