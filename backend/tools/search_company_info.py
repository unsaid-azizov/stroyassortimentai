"""
BM25-based search tool for company knowledge base.
Searches through sections using BM25 ranking on keywords and content.
"""
import json
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from langchain.tools import tool


def tokenize(text: str) -> List[str]:
    """Simple tokenization for BM25."""
    return str(text).lower().split()


def build_searchable_text(section_data: dict) -> str:
    """Build searchable text from section data (keywords + title + content)."""
    parts = []

    # Add title (high weight - repeat 3x)
    title = section_data.get("title", "")
    if title:
        parts.extend([title] * 3)

    # Add keywords (high weight - repeat 2x)
    keywords = section_data.get("keywords", [])
    if keywords:
        keyword_text = " ".join(keywords)
        parts.extend([keyword_text] * 2)

    # Add content (lower weight - 1x)
    content = section_data.get("content", {})
    if content:
        content_str = json.dumps(content, ensure_ascii=False)
        parts.append(content_str)

    return " ".join(parts)


def format_section_content(content: Any, indent: int = 0) -> str:
    """
    Рекурсивно форматирует содержимое раздела в читаемый текст.
    """
    if content is None:
        return ""

    indent_str = "  " * indent
    lines = []

    if isinstance(content, dict):
        for key, value in content.items():
            # Пропускаем служебные ключи
            if key in ("metadata", "last_updated"):
                continue

            # Форматируем заголовок
            header = key.replace("_", " ").capitalize()
            lines.append(f"{indent_str}**{header}:**")

            # Рекурсивно форматируем содержимое
            formatted_value = format_section_content(value, indent + 1)
            if formatted_value:
                lines.append(formatted_value)
            lines.append("")

    elif isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                # Если это объект, форматируем его поля
                item_lines = []
                for k, v in item.items():
                    if v:
                        item_lines.append(f"{k}: {v}")
                if item_lines:
                    lines.append(f"{indent_str}- {', '.join(item_lines)}")
            else:
                # Простой элемент списка
                lines.append(f"{indent_str}- {item}")

    elif isinstance(content, str):
        # Текстовое содержимое
        lines.append(f"{indent_str}{content}")

    else:
        # Другие типы (число, bool и т.д.)
        lines.append(f"{indent_str}{content}")

    return "\n".join(lines)


def search_knowledge_base_bm25(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Search knowledge base using BM25 ranking.
    Returns top-K sections with scores.
    """
    from params_manager import ParamsManager

    params_manager = ParamsManager()
    kb_content = params_manager.get_knowledge_base_dict()

    if not kb_content or "sections" not in kb_content:
        return []

    sections = kb_content["sections"]
    if not sections:
        return []

    # Build corpus for BM25
    section_keys = list(sections.keys())
    corpus = []

    for section_key in section_keys:
        section_data = sections[section_key]
        searchable_text = build_searchable_text(section_data)
        corpus.append(searchable_text)

    # Tokenize corpus
    tokenized_corpus = [tokenize(doc) for doc in corpus]

    # Build BM25 index
    bm25 = BM25Okapi(tokenized_corpus)

    # Get scores
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    # Create results with scores
    results = []
    for i, section_key in enumerate(section_keys):
        section_data = sections[section_key]
        results.append({
            "section_key": section_key,
            "title": section_data.get("title", section_key),
            "content": section_data.get("content"),
            "source_url": section_data.get("source_url"),
            "keywords": section_data.get("keywords", []),
            "score": scores[i]
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)

    # Return top-K
    return results[:top_k]


@tool
def search_company_info(query: str) -> str:
    """
    Поиск информации о компании через базу знаний с использованием BM25.

    Используй этот инструмент когда клиент спрашивает про:
    - АДРЕС, КОНТАКТЫ, СКЛАД, ПРОЕЗД - как добраться, где находится, телефон
    - ДОСТАВКУ - условия доставки, стоимость, зоны доставки, самовывоз
    - УСЛУГИ - производство, распил, индивидуальные заказы, антисептирование
    - ОПЛАТУ - способы оплаты, наличные, безналичный расчет
    - ВОЗВРАТ, ГАРАНТИЮ - условия возврата, гарантийные обязательства
    - АКЦИИ, СКИДКИ - текущие спецпредложения
    - ОБЩУЮ ИНФОРМАЦИЮ - о компании, время работы, FAQ

    Args:
        query: Поисковый запрос на естественном языке (например, "как добраться до склада", "способы оплаты")

    Returns:
        Топ-3 наиболее релевантных раздела с форматированным содержимым

    Примеры:
        - "адрес склада" → вернет контакты с адресом и картой проезда
        - "доставка в мытищи" → вернет условия доставки
        - "способы оплаты" → вернет информацию об оплате
    """
    if not query or not query.strip():
        from params_manager import ParamsManager
        params_manager = ParamsManager()
        available_sections = params_manager.get_available_sections()
        sections_list = ", ".join([f"'{s}'" for s in available_sections])
        return f"Укажите поисковый запрос. Доступные разделы: {sections_list}"

    results = search_knowledge_base_bm25(query, top_k=3)

    if not results:
        return "Информация не найдена в базе знаний. Для получения точной информации позовите менеджера через call_manager."

    # Format response
    response_lines = []

    for i, result in enumerate(results, 1):
        # Пропускаем результаты с очень низкой релевантностью
        if result['score'] < 0.5 and i > 1:
            continue

        response_lines.append(f"## {result['title']}")
        response_lines.append("")

        # Format content
        content = result.get("content", {})
        if content:
            formatted_content = format_section_content(content)
            response_lines.append(formatted_content)
        else:
            response_lines.append("(Информация не доступна)")

        # Add source
        if result.get("source_url"):
            response_lines.append("")
            response_lines.append(f"Подробнее: {result['source_url']}")

        response_lines.append("")
        response_lines.append("---")
        response_lines.append("")

    return "\n".join(response_lines).strip()
