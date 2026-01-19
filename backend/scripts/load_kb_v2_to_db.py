"""
Скрипт для загрузки KB v2 в базу данных.
"""
import asyncio
import json
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent.parent))

from db.session import async_session_factory
from db.repository import upsert_settings


async def load_kb_v2_to_db():
    """Загружает KB v2 из файла в базу данных."""
    data_dir = Path(__file__).parent.parent / "data"
    kb_v2_path = data_dir / "kb_v2.json"
    
    if not kb_v2_path.exists():
        print(f"❌ Файл {kb_v2_path} не найден!")
        print("Сначала запустите migrate_kb_to_v2.py для создания kb_v2.json")
        return
    
    print(f"Загружаем KB v2 из {kb_v2_path}...")
    
    try:
        with open(kb_v2_path, "r", encoding="utf-8") as f:
            kb_v2 = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return
    
    print(f"✅ KB v2 загружена из файла")
    print(f"📊 Разделов: {len(kb_v2.get('sections', {}))}")
    
    # Загружаем в БД
    async with async_session_factory() as session:
        try:
            await upsert_settings(session, "knowledge_base", kb_v2)
            await session.commit()
            print("✅ KB v2 успешно сохранена в базу данных!")
            
            # Выводим список разделов
            print("\nДоступные разделы в БД:")
            for section_key, section_data in kb_v2.get("sections", {}).items():
                title = section_data.get("title", section_key)
                source_url = section_data.get("source_url", "N/A")
                print(f"  - {section_key}: {title} (source: {source_url})")
                
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка сохранения в БД: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(load_kb_v2_to_db())

