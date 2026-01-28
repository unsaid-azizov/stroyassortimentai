#!/usr/bin/env python3
"""
Dynamic product search with BM25 ranking and LangChain tool integration.
Catalog is loaded from Redis (synced from 1C API).
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
import os
import json
import logging
import pandas as pd
from rank_bm25 import BM25Okapi
from langchain.tools import tool
import redis

logger = logging.getLogger(__name__)


@dataclass
class ProductSearchParams:
    """Dynamic product search parameters."""

    # Text search
    query: Optional[str] = None

    # Categorical filters (validated dynamically against CSV)
    material_type: Optional[str] = None  # Видпиломатериала
    wood_species: Optional[str] = None  # Порода
    grade: Optional[str] = None  # Сорт
    moisture: Optional[str] = None  # Влажность
    treatment: Optional[str] = None  # Типобработки
    group_name: Optional[str] = None  # group_name

    # Dimensions (in mm)
    thickness_min: Optional[float] = None
    thickness_max: Optional[float] = None
    width_min: Optional[float] = None
    width_max: Optional[float] = None
    length_min: Optional[float] = None
    length_max: Optional[float] = None

    # Commercial filters
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    in_stock_only: Optional[bool] = None

    # Search options
    limit: int = 20
    offset: int = 0


def normalize_dimension(value: Any) -> float:
    """Normalize dimension to float (handles '1 250' -> 1250.0)."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    normalized = str(value).replace(' ', '').replace(',', '.')
    return float(normalized)


def load_catalog() -> pd.DataFrame:
    """
    Load catalog from Redis.

    Redis содержит JSON массив объектов с полной структурой каталога
    (синхронизируется из 1C API каждый час).

    Returns:
        DataFrame с каталогом товаров
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")  # localhost для локальной разработки, переопределяется на redis:6379 в Docker
    redis_key = "catalog:products"

    try:
        # Подключаемся к Redis
        r = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

        # Получаем каталог
        catalog_json = r.get(redis_key)

        if not catalog_json:
            logger.warning("⚠️  Catalog not found in Redis, returning empty DataFrame")
            return pd.DataFrame()

        # Парсим JSON в список объектов
        catalog_data = json.loads(catalog_json)

        # Создаем DataFrame
        df = pd.DataFrame(catalog_data)

        logger.info(f"✅ Loaded {len(df)} items from Redis")
        return df

    except Exception as e:
        logger.error(f"❌ Error loading catalog from Redis: {e}")
        # Возвращаем пустой DataFrame в случае ошибки
        return pd.DataFrame()
    finally:
        try:
            r.close()
        except:
            pass


def get_available_categories(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Extract all unique categories from catalog."""
    return {
        'material_types': sorted(df['Видпиломатериала'].dropna().unique().tolist()),
        'wood_species': sorted(df['Порода'].dropna().unique().tolist()),
        'grades': sorted(df['Сорт'].dropna().unique().tolist()),
        'moisture': sorted(df['Влажность'].dropna().unique().tolist()),
        'treatment': sorted(df['Типобработки'].dropna().unique().tolist()),
        'group_names': sorted(df['group_name'].dropna().unique().tolist()),
    }


def tokenize(text: str) -> List[str]:
    """Simple tokenization for BM25."""
    return str(text).lower().split()


def search_products(params: ProductSearchParams) -> List[Dict[str, Any]]:
    """
    Search products with BM25 ranking and filtering.

    Algorithm:
    1. Load catalog
    2. Apply categorical filters
    3. Apply BM25 text search if query provided
    4. Apply dimension/price filters
    5. Return top-K results
    """
    df = load_catalog()
    results = df.copy()

    # Apply categorical filters
    if params.material_type:
        results = results[results['Видпиломатериала'] == params.material_type]

    if params.wood_species:
        results = results[results['Порода'] == params.wood_species]

    if params.grade:
        results = results[results['Сорт'] == params.grade]

    if params.moisture:
        results = results[results['Влажность'] == params.moisture]

    if params.treatment:
        results = results[results['Типобработки'] == params.treatment]

    if params.group_name:
        results = results[results['group_name'] == params.group_name]

    # Apply BM25 text search
    if params.query and len(results) > 0:
        # Build searchable corpus from multiple fields
        corpus = []
        for _, row in results.iterrows():
            text_parts = []
            for col in ['item_name', 'Наименование', 'Наименованиедлясайта']:
                if col in row and pd.notna(row[col]):
                    text_parts.append(str(row[col]))
            corpus.append(' '.join(text_parts))

        # Tokenize corpus
        tokenized_corpus = [tokenize(doc) for doc in corpus]

        # Build BM25 index
        bm25 = BM25Okapi(tokenized_corpus)

        # Get scores
        tokenized_query = tokenize(params.query)
        scores = bm25.get_scores(tokenized_query)

        # Add scores to results
        results = results.copy()
        results['bm25_score'] = scores

        # Sort by BM25 score descending
        results = results.sort_values('bm25_score', ascending=False)

    # Apply dimension filters
    if params.thickness_min is not None or params.thickness_max is not None:
        results['Толщина_float'] = results['Толщина'].apply(normalize_dimension)
        if params.thickness_min is not None:
            results = results[results['Толщина_float'] >= params.thickness_min]
        if params.thickness_max is not None:
            results = results[results['Толщина_float'] <= params.thickness_max]

    if params.width_min is not None or params.width_max is not None:
        results['Ширина_float'] = results['Ширина'].apply(normalize_dimension)
        if params.width_min is not None:
            results = results[results['Ширина_float'] >= params.width_min]
        if params.width_max is not None:
            results = results[results['Ширина_float'] <= params.width_max]

    if params.length_min is not None or params.length_max is not None:
        results['Длина_float'] = results['Длина'].apply(normalize_dimension)
        if params.length_min is not None:
            results = results[results['Длина_float'] >= params.length_min]
        if params.length_max is not None:
            results = results[results['Длина_float'] <= params.length_max]

    # Apply price filters
    if params.price_min is not None:
        results['Цена_float'] = pd.to_numeric(results['Цена'], errors='coerce')
        results = results[results['Цена_float'] >= params.price_min]
    if params.price_max is not None:
        if 'Цена_float' not in results.columns:
            results['Цена_float'] = pd.to_numeric(results['Цена'], errors='coerce')
        results = results[results['Цена_float'] <= params.price_max]

    # Apply stock filter
    if params.in_stock_only:
        def has_stock(value):
            if pd.isna(value):
                return False
            val_str = str(value).strip()
            if val_str == 'По предзаказу':
                return False
            stock_val = normalize_dimension(val_str)
            return stock_val > 0

        results = results[results['Остаток'].apply(has_stock)]

    # Apply limit and offset
    results = results.iloc[params.offset:params.offset + params.limit]

    # Convert to list of dicts
    return results.to_dict('records')


@tool
def search_products_tool(
    query: Optional[str] = None,
    material_type: Optional[str] = None,
    wood_species: Optional[str] = None,
    grade: Optional[str] = None,
    moisture: Optional[str] = None,
    treatment: Optional[str] = None,
    group_name: Optional[str] = None,
    thickness_min: Optional[float] = None,
    thickness_max: Optional[float] = None,
    width_min: Optional[float] = None,
    width_max: Optional[float] = None,
    length_min: Optional[float] = None,
    length_max: Optional[float] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    in_stock_only: Optional[bool] = None,
    limit: int = 20,
) -> str:
    """
    Search for construction materials in the catalog with BM25 ranking.

    Use this tool when customer asks about products, prices, availability.

    Categories are validated dynamically - always load fresh catalog first.

    Examples:
    - "вагонка" -> query="вагонка"
    - "брус 150x150" -> query="брус", width_min=150, width_max=150
    - "доска сосна сухая" -> query="доска", wood_species="сосна", moisture="сухой 12-14%"
    """
    params = ProductSearchParams(
        query=query,
        material_type=material_type,
        wood_species=wood_species,
        grade=grade,
        moisture=moisture,
        treatment=treatment,
        group_name=group_name,
        thickness_min=thickness_min,
        thickness_max=thickness_max,
        width_min=width_min,
        width_max=width_max,
        length_min=length_min,
        length_max=length_max,
        price_min=price_min,
        price_max=price_max,
        in_stock_only=in_stock_only,
        limit=limit,
    )

    results = search_products(params)

    if not results:
        return "Товары не найдены. Попробуйте изменить параметры поиска."

    # Format results with full product details
    output = f"Найдено товаров: {len(results)}\n\n"
    for i, item in enumerate(results[:15], 1):
        output += f"{i}. {item.get('Наименованиедлясайта', item.get('item_name', 'N/A'))}\n"

        # Основная информация - используем group_code который работает с 1С API
        output += f"   Код: {item.get('group_code', 'N/A')}\n"
        output += f"   Цена: {item.get('Цена', 'N/A')} руб.\n"

        # Параметры материала
        if pd.notna(item.get('Порода')):
            output += f"   Порода: {item.get('Порода')}\n"
        if pd.notna(item.get('Влажность')):
            output += f"   Влажность: {item.get('Влажность')}\n"
        if pd.notna(item.get('Сорт')):
            output += f"   Сорт: {item.get('Сорт')}\n"
        if pd.notna(item.get('Класс')):
            output += f"   Класс: {item.get('Класс')}\n"
        if pd.notna(item.get('Видпиломатериала')):
            output += f"   Вид: {item.get('Видпиломатериала')}\n"
        if pd.notna(item.get('Типобработки')):
            output += f"   Обработка: {item.get('Типобработки')}\n"

        # Размеры
        dimensions = []
        if pd.notna(item.get('Толщина')):
            dimensions.append(f"{item.get('Толщина')}")
        if pd.notna(item.get('Ширина')):
            dimensions.append(f"{item.get('Ширина')}")
        if pd.notna(item.get('Длина')):
            dimensions.append(f"{item.get('Длина')}")
        if dimensions:
            output += f"   Размеры (мм): {' x '.join(dimensions)}\n"

        # Дополнительные параметры
        if pd.notna(item.get('Допсвойство')):
            output += f"   Доп. свойство: {item.get('Допсвойство')}\n"
        if pd.notna(item.get('Плотностькгм3Общие')):
            output += f"   Плотность: {item.get('Плотностькгм3Общие')} кг/м³\n"
        if pd.notna(item.get('Количествовм2Общие')):
            output += f"   В 1 шт: {item.get('Количествовм2Общие')} м²\n"
        if pd.notna(item.get('Количествовм3Общие')):
            output += f"   В 1 шт: {item.get('Количествовм3Общие')} м³\n"
        if pd.notna(item.get('СрокпроизводстваднОбщие')):
            output += f"   Срок производства: {item.get('СрокпроизводстваднОбщие')} дней\n"
        if pd.notna(item.get('ПопулярностьОбщие')) and float(item.get('ПопулярностьОбщие', 0)) > 0:
            output += f"   ⭐ Популярность: {item.get('ПопулярностьОбщие')}\n"

        # Релевантность (если есть)
        if 'bm25_score' in item:
            output += f"   Релевантность: {item['bm25_score']:.2f}\n"

        output += "\n"

    return output


if __name__ == '__main__':
    # Test dynamic category loading
    df = load_catalog()
    categories = get_available_categories(df)

    print("=== DYNAMIC CATEGORIES ===")
    for key, values in categories.items():
        print(f"\n{key} ({len(values)}):")
        for v in values[:5]:
            print(f"  - {v}")
        if len(values) > 5:
            print(f"  ... and {len(values) - 5} more")

    # Test BM25 search
    print("\n\n=== BM25 SEARCH TEST ===")
    params = ProductSearchParams(query="вагонка штиль", limit=5)
    results = search_products(params)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"- {r.get('Наименование')} (score: {r.get('bm25_score', 0):.2f})")
