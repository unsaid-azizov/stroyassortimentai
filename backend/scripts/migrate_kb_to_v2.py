"""
Скрипт для миграции KB из старого формата в новый v2 с метаданными и источниками.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Загружает JSON файл."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Файл {file_path} не найден")
        return {}
    except json.JSONDecodeError as e:
        print(f"Ошибка парсинга JSON в {file_path}: {e}")
        return {}

def migrate_kb_to_v2(
    company_info_path: Path,
    info_json_path: Path,
    crawl_manifest_path: Path,
    output_path: Path
) -> Dict[str, Any]:
    """
    Мигрирует данные из старых файлов в новую структуру KB v2.
    """
    company_info = load_json_file(company_info_path)
    info_json = load_json_file(info_json_path)
    crawl_manifest = load_json_file(crawl_manifest_path)
    
    # Создаем маппинг разделов к URL из crawl_manifest
    source_mapping = {}
    if "sources" in crawl_manifest:
        for source in crawl_manifest["sources"]:
            source_id = source.get("id", "")
            source_url = source.get("url", "")
            source_type = source.get("type", "")
            
            # Маппинг типов к разделам
            if source_type == "general_info" or source_id == "home":
                source_mapping["company"] = source_url
            elif source_type == "contacts":
                source_mapping["contacts"] = source_url
            elif source_type == "delivery_payment":
                source_mapping["delivery"] = source_url
                source_mapping["payment"] = source_url
            elif source_type == "product_category" or source_id == "catalog":
                source_mapping["product_categories"] = source_url
                source_mapping["product_groups"] = source_url
            elif source_type == "services":
                source_mapping["services"] = source_url
            elif source_type == "promotions":
                source_mapping["special_offers"] = source_url
    
    base_url = crawl_manifest.get("site", "https://stroyassortiment.ru")
    now = datetime.utcnow().isoformat() + "Z"
    
    # Создаем новую структуру
    kb_v2 = {
        "metadata": {
            "version": "2.0",
            "schema_version": "2.0",
            "updated_at": now,
            "base_url": base_url
        },
        "sections": {}
    }
    
    # Мигрируем разделы из company_info.json
    if "company" in company_info:
        kb_v2["sections"]["company"] = {
            "title": "О компании",
            "content": company_info["company"],
            "source_url": source_mapping.get("company", f"{base_url}/"),
            "keywords": ["компания", "о нас", "производство", "описание"],
            "last_updated": now
        }
    
    if "contacts" in company_info:
        kb_v2["sections"]["contacts"] = {
            "title": "Контакты",
            "content": company_info["contacts"],
            "source_url": source_mapping.get("contacts", f"{base_url}/kontakty/"),
            "keywords": ["адрес", "телефон", "склад", "проезд", "контакты", "карта", "видео", "как добраться"],
            "last_updated": now
        }
    
    if "delivery" in company_info:
        kb_v2["sections"]["delivery"] = {
            "title": "Доставка и самовывоз",
            "content": company_info["delivery"],
            "source_url": source_mapping.get("delivery", f"{base_url}/dostavka-i-oplata/"),
            "keywords": ["доставка", "самовывоз", "транспорт", "автопарк", "стоимость доставки", "логистика"],
            "last_updated": now
        }
    
    if "product_categories" in company_info:
        kb_v2["sections"]["product_categories"] = {
            "title": "Категории товаров",
            "content": company_info["product_categories"],
            "source_url": source_mapping.get("product_categories", f"{base_url}/catalog/"),
            "keywords": ["категории", "товары", "пиломатериалы", "дерево", "материалы"],
            "last_updated": now
        }
    
    if "services" in company_info:
        kb_v2["sections"]["services"] = {
            "title": "Услуги компании",
            "content": company_info["services"],
            "source_url": source_mapping.get("services", f"{base_url}/uslugi/"),
            "keywords": ["услуги", "производство", "распил", "индивидуальные заказы", "консультации"],
            "last_updated": now
        }
    
    if "payment" in company_info:
        kb_v2["sections"]["payment"] = {
            "title": "Способы оплаты",
            "content": company_info["payment"],
            "source_url": source_mapping.get("payment", f"{base_url}/dostavka-i-oplata/"),
            "keywords": ["оплата", "способы оплаты", "наличные", "безналичный расчет"],
            "last_updated": now
        }
    
    if "warranty_and_return" in company_info:
        kb_v2["sections"]["warranty_and_return"] = {
            "title": "Гарантия и возврат",
            "content": company_info["warranty_and_return"],
            "source_url": f"{base_url}/garantiya-i-vozvrat/",
            "keywords": ["гарантия", "возврат", "условия"],
            "last_updated": now
        }
    
    if "special_offers" in company_info:
        kb_v2["sections"]["special_offers"] = {
            "title": "Акции и спецпредложения",
            "content": company_info["special_offers"],
            "source_url": source_mapping.get("special_offers", f"{base_url}/akcii/"),
            "keywords": ["акции", "скидки", "спецпредложения", "бонусы"],
            "last_updated": now
        }
    
    if "faq" in company_info:
        kb_v2["sections"]["faq"] = {
            "title": "Часто задаваемые вопросы",
            "content": company_info["faq"],
            "source_url": f"{base_url}/faq/",
            "keywords": ["faq", "вопросы", "ответы", "помощь"],
            "last_updated": now
        }
    
    # Добавляем раздел product_groups из info.json
    if "items" in info_json:
        groups = []
        for item in info_json["items"]:
            code = item.get("code", "")
            descr = item.get("descr", "")
            
            # Извлекаем keywords из описания
            keywords = []
            descr_lower = descr.lower()
            if "брус" in descr_lower:
                keywords.append("брус")
            if "доска" in descr_lower:
                keywords.append("доска")
            if "хвоя" in descr_lower or "сосна" in descr_lower or "ель" in descr_lower:
                keywords.append("хвоя")
            if "лиственница" in descr_lower:
                keywords.append("лиственница")
            if "липа" in descr_lower:
                keywords.append("липа")
            if "осина" in descr_lower:
                keywords.append("осина")
            if "строганный" in descr_lower:
                keywords.append("строганный")
            if "сухой" in descr_lower:
                keywords.append("сухой")
            if "гост" in descr_lower:
                keywords.append("гост")
            if "вагонка" in descr_lower:
                keywords.append("вагонка")
            if "имитация бруса" in descr_lower:
                keywords.append("имитация бруса")
            
            groups.append({
                "code": code,
                "description": descr,
                "keywords": list(set(keywords))  # Убираем дубликаты
            })
        
        kb_v2["sections"]["product_groups"] = {
            "title": "Коды групп товаров для поиска в 1С",
            "content": {
                "description": "Список кодов групп товаров для использования в инструменте search_1c_products. Используй эти коды для поиска товаров в системе 1С.",
                "groups": groups
            },
            "source_url": source_mapping.get("product_groups", f"{base_url}/catalog/"),
            "keywords": ["товары", "каталог", "группы", "коды", "1с"],
            "last_updated": now
        }
    
    return kb_v2

def main():
    """Основная функция миграции."""
    data_dir = Path(__file__).parent.parent / "data"
    
    company_info_path = data_dir / "company_info.json"
    info_json_path = data_dir / "info.json"
    crawl_manifest_path = data_dir / "crawl_manifest.json"
    output_path = data_dir / "kb_v2.json"
    
    print("Начинаем миграцию KB в формат v2...")
    
    kb_v2 = migrate_kb_to_v2(
        company_info_path,
        info_json_path,
        crawl_manifest_path,
        output_path
    )
    
    # Сохраняем результат
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kb_v2, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Миграция завершена! Результат сохранен в {output_path}")
    print(f"📊 Создано разделов: {len(kb_v2['sections'])}")
    
    # Выводим список разделов
    print("\nДоступные разделы:")
    for section_key, section_data in kb_v2["sections"].items():
        print(f"  - {section_key}: {section_data['title']} (source: {section_data.get('source_url', 'N/A')})")

if __name__ == "__main__":
    main()

