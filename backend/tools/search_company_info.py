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
    Search company knowledge base using natural language query with BM25 ranking.

    Use this tool when customer asks about:
    - адрес, контакты, склад, проезд, карту, видео-инструкцию
    - доставку, самовывоз, транспорт, автопарк
    - услуги, производство, распил, индивидуальные заказы
    - способы оплаты, наличные, безналичный расчет
    - возврат, гарантию, условия
    - акции, скидки, спецпредложения
    - часто задаваемые вопросы
    - общую информацию о компании

    Args:
        query: Natural language search query (e.g. "как добраться до склада", "способы оплаты")

    Returns:
        Top-3 relevant sections with content
    """
    if not query or not query.strip():
        from params_manager import ParamsManager
        params_manager = ParamsManager()
        available_sections = params_manager.get_available_sections()
        sections_list = ", ".join([f"'{s}'" for s in available_sections])
        return f"Укажите поисковый запрос. Доступные разделы: {sections_list}"

    results = search_knowledge_base_bm25(query, top_k=3)

    if not results:
        return "Информация не найдена. Телефон: +7 (499) 302-55-01"

    # Format response
    response_lines = [f"Найдено {len(results)} раздела(ов) по запросу '{query}':", ""]

    for i, result in enumerate(results, 1):
        response_lines.append(f"### {i}. {result['title']} (релевантность: {result['score']:.2f})")
        response_lines.append("")

        # Format content
        content = result.get("content", {})
        content_str = json.dumps(content, indent=2, ensure_ascii=False)
        response_lines.append(content_str)

        # Add source
        if result.get("source_url"):
            response_lines.append(f"\nИсточник: {result['source_url']}")

        response_lines.append("")

    return "\n".join(response_lines)
