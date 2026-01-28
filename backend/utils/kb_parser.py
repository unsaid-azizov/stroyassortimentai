"""
Knowledge Base Text Parser - Simplified version

Максимально простой парсер для пользовательского текста.
Клиент просто пишет разделы через разделитель "---".

Формат:
```
Контакты и адрес

Адрес склада: г. Мытищи, ул. Промышленная, д. 15
Телефон: +7 (495) 123-45-67
Время работы: Пн-Пт 9:00-18:00

---

Доставка

Доставляем по всей Московской области.
Стоимость от 2000 руб в зависимости от расстояния.

---
```
"""
import re
from typing import Dict, Any, List


def parse_text_kb(text: str) -> Dict[str, Any]:
    """
    Парсит текстовую базу знаний в структурированный формат для BM25.

    Простой формат:
    - Разделы разделяются "---"
    - Первая непустая строка = заголовок
    - Остальное = содержимое

    Args:
        text: Текстовое содержимое базы знаний

    Returns:
        Словарь с разделами в формате для BM25:
        {
            "metadata": {"format": "text", "version": "1.0"},
            "sections": {
                "section_key": {
                    "title": "Заголовок",
                    "keywords": ["автоматические", "ключевые", "слова"],
                    "content": "Текстовое содержимое"
                }
            }
        }
    """
    if not text or not text.strip():
        return {
            "metadata": {"format": "text", "version": "1.0"},
            "sections": {}
        }

    # Разбиваем на разделы по разделителю ---
    raw_sections = re.split(r'\n---+\n', text.strip())

    sections = {}

    for i, raw_section in enumerate(raw_sections):
        if not raw_section.strip():
            continue

        section_data = parse_section(raw_section, index=i)
        if section_data:
            section_key = section_data["section_key"]
            sections[section_key] = section_data

    return {
        "metadata": {
            "format": "text",
            "version": "1.0"
        },
        "sections": sections
    }


def parse_section(text: str, index: int = 0) -> Dict[str, Any]:
    """
    Парсит один раздел.

    Логика:
    - Первая непустая строка = заголовок
    - Остальное = содержимое
    - Keywords извлекаются автоматически из заголовка
    """
    lines = [line for line in text.strip().split('\n')]
    if not lines:
        return None

    # Находим первую непустую строку - это заголовок
    title = None
    content_start_idx = 0

    for i, line in enumerate(lines):
        if line.strip():
            title = line.strip()
            content_start_idx = i + 1
            break

    if not title:
        # Если нет заголовка, используем первые слова содержимого
        title = f"Раздел {index + 1}"
        content_start_idx = 0

    # Генерируем ключ раздела из заголовка
    section_key = generate_section_key(title)

    # Извлекаем содержимое (все строки после заголовка)
    content_lines = lines[content_start_idx:]
    content = '\n'.join(content_lines).strip()

    # Автоматически извлекаем keywords из заголовка
    keywords = extract_keywords(title)

    return {
        "section_key": section_key,
        "title": title,
        "keywords": keywords,
        "content": content
    }


def extract_keywords(text: str) -> List[str]:
    """
    Извлекает ключевые слова из текста.

    Правила:
    - Убираем стоп-слова (и, в, на, для, с, по, о)
    - Берем слова длиной >= 3 символа
    - Приводим к нижнему регистру
    """
    # Стоп-слова на русском
    stop_words = {
        'и', 'в', 'на', 'для', 'с', 'по', 'о', 'об', 'из', 'к', 'от', 'до',
        'при', 'про', 'под', 'над', 'между', 'через', 'за', 'без', 'у', 'а',
        'но', 'или', 'же', 'ли', 'бы', 'не', 'то', 'это', 'весь', 'всё',
        'как', 'так', 'где', 'что', 'кто', 'чем', 'тем', 'этот', 'эта', 'это',
        'тот', 'та', 'те', 'наш', 'ваш', 'их', 'его', 'её', 'свой'
    }

    # Разбиваем на слова и очищаем
    words = re.findall(r'\w+', text.lower())

    # Фильтруем: длина >= 3, не стоп-слово
    keywords = [
        word for word in words
        if len(word) >= 3 and word not in stop_words
    ]

    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_keywords = []
    for word in keywords:
        if word not in seen:
            seen.add(word)
            unique_keywords.append(word)

    return unique_keywords[:10]  # Максимум 10 ключевых слов


def generate_section_key(title: str) -> str:
    """
    Генерирует ключ раздела из заголовка.

    Примеры:
        "Контакты и адрес" -> "contacts_and_address"
        "Доставка" -> "delivery"
    """
    # Транслитерация русских букв
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    # Приводим к нижнему регистру
    key = title.lower()

    # Транслитерируем
    result = []
    for char in key:
        if char in translit_map:
            result.append(translit_map[char])
        elif char.isalnum():
            result.append(char)
        elif char in ' -_':
            result.append('_')

    # Убираем повторяющиеся подчеркивания и очищаем края
    key = '_'.join(filter(None, ''.join(result).split('_')))

    return key or 'section'


def kb_dict_to_text(kb_dict: Dict[str, Any]) -> str:
    """
    Конвертирует словарь базы знаний обратно в текстовый формат.

    Args:
        kb_dict: Словарь с метаданными и разделами

    Returns:
        Текстовое представление базы знаний
    """
    if not kb_dict or "sections" not in kb_dict:
        return ""

    sections = kb_dict.get("sections", {})
    if not sections:
        return ""

    result_lines = []

    for section_key, section_data in sections.items():
        # Заголовок раздела (первая строка)
        title = section_data.get("title", section_key)
        result_lines.append(title)
        result_lines.append("")  # Пустая строка после заголовка

        # Содержимое раздела
        content = section_data.get("content", "")
        if isinstance(content, dict):
            # Если content - словарь (конвертация из старого JSON), форматируем
            content = format_dict_content(content)
        elif isinstance(content, str):
            content = content.strip()
        else:
            content = str(content)

        result_lines.append(content)

        # Разделитель между разделами
        result_lines.append("")
        result_lines.append("---")
        result_lines.append("")

    # Убираем последний разделитель
    while result_lines and result_lines[-1] in ("", "---"):
        result_lines.pop()

    return "\n".join(result_lines).strip()


def format_dict_content(content: Dict[str, Any], indent: int = 0) -> str:
    """
    Форматирует словарь в читаемый текст (для конвертации из JSON).
    """
    lines = []
    indent_str = "  " * indent

    for key, value in content.items():
        if key in ("metadata", "last_updated"):
            continue

        header = key.replace("_", " ").capitalize()

        if isinstance(value, dict):
            lines.append(f"{indent_str}{header}:")
            lines.append(format_dict_content(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{indent_str}{header}:")
            for item in value:
                if isinstance(item, dict):
                    item_lines = []
                    for k, v in item.items():
                        if v:
                            item_lines.append(f"{k}: {v}")
                    if item_lines:
                        lines.append(f"{indent_str}  - {', '.join(item_lines)}")
                else:
                    lines.append(f"{indent_str}  - {item}")
        else:
            lines.append(f"{indent_str}{header}: {value}")

    return "\n".join(lines)
