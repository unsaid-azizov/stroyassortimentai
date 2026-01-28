"""
ParamsManager - Singleton class for managing runtime configuration.
Loads prompt and knowledge base from DB, tracks changes, and provides sync getters for middleware.
"""
import asyncio
import hashlib
import json
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ParamsManager:
    """
    Singleton class for managing runtime configuration (prompt, KB, etc.).
    Updates occur only when FastAPI endpoints are triggered (no TTL).
    """
    _instance: Optional['ParamsManager'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return

        # Cache storage
        self._prompt_text: Optional[str] = None
        self._kb_text: Optional[str] = None  # Raw text from DB
        self._kb_parsed: Optional[dict] = None  # Parsed dict for BM25

        # Change tracking
        self._prompt_id: Optional[str] = None
        self._prompt_version: Optional[int] = None
        self._kb_hash: Optional[str] = None

        self._initialized = True
    
    def _format_kb_for_prompt(self, kb_parsed: Optional[dict]) -> str:
        """
        Форматирует parsed KB в компактный формат для system prompt.
        Включает только список доступных разделов.
        """
        if not kb_parsed or "sections" not in kb_parsed:
            return ""

        sections = kb_parsed.get("sections", {})
        if not sections:
            return ""

        lines = [
            "ДОСТУПНЫЕ РАЗДЕЛЫ БАЗЫ ЗНАНИЙ (используй search_company_info для получения детальной информации):"
        ]

        # Список разделов с ключевыми словами
        for section_key, section_data in sections.items():
            title = section_data.get("title", section_key)
            keywords = section_data.get("keywords", [])
            keywords_str = ", ".join(keywords[:5])  # Первые 5 keywords
            lines.append(f"  - {section_key}: {title} (ключевые слова: {keywords_str})")

        return "\n".join(lines)
    
    def get_available_sections(self) -> list[str]:
        """Возвращает список доступных разделов KB."""
        if not self._kb_parsed or "sections" not in self._kb_parsed:
            return []

        return list(self._kb_parsed["sections"].keys())

    def get_section_metadata(self, section: str) -> Optional[dict]:
        """Возвращает метаданные раздела (title, keywords)."""
        if not self._kb_parsed or "sections" not in self._kb_parsed:
            return None

        section_data = self._kb_parsed["sections"].get(section)
        if section_data:
            return {
                "title": section_data.get("title"),
                "keywords": section_data.get("keywords", []),
            }

        return None

    def get_section_content(self, section: str) -> Optional[str]:
        """Возвращает текстовое содержимое раздела."""
        if not self._kb_parsed or "sections" not in self._kb_parsed:
            return None

        section_data = self._kb_parsed["sections"].get(section)
        if section_data:
            return section_data.get("content")

        return None
    
    def _compute_kb_hash(self, kb_text: Optional[str]) -> str:
        """Compute hash of KB text for change detection."""
        if not kb_text:
            return ""
        try:
            return hashlib.md5(kb_text.encode('utf-8')).hexdigest()
        except Exception:
            return ""
    
    
    async def load_prompt(self, force: bool = False) -> None:
        """
        Load prompt from DB. Updates cache only if changed or force=True.
        """
        try:
            from db.session import async_session_factory
            from db.repository import get_active_prompt_config
        except Exception as e:
            logger.warning(f"Could not import DB helpers: {e}")
            return
        
        async with self._lock:
            async with async_session_factory() as session:
                prompt = await get_active_prompt_config(session)
                
                if prompt:
                    prompt_id = str(prompt.id)
                    prompt_version = prompt.version
                    
                    # Check if prompt changed
                    prompt_changed = (
                        force or
                        not self._prompt_text or
                        self._prompt_id != prompt_id or
                        self._prompt_version != prompt_version
                    )
                    
                    if prompt_changed and prompt.content:
                        self._prompt_text = prompt.content
                        self._prompt_id = prompt_id
                        self._prompt_version = prompt_version
                        logger.info(f"Промпт обновлен (ID: {prompt_id}, версия: {prompt_version})")
                else:
                    # No active prompt in DB, clear cache
                    if self._prompt_text:
                        logger.warning("Активный промпт не найден в БД, очищаем кеш")
                        self._prompt_text = None
                        self._prompt_id = None
                        self._prompt_version = None
    
    async def load_knowledge_base(self, force: bool = False) -> None:
        """
        Load knowledge base from DB (as text). Updates cache only if changed or force=True.
        """
        try:
            from db.session import async_session_factory
            from db.repository import get_settings
            from utils.kb_parser import parse_text_kb
        except Exception as e:
            logger.warning(f"Could not import DB helpers: {e}")
            return

        async with self._lock:
            async with async_session_factory() as session:
                kb_settings = await get_settings(session, "knowledge_base")

                if kb_settings and kb_settings.value:
                    # KB хранится как текст (строка) в БД
                    kb_text = kb_settings.value

                    # Если в БД еще старый JSON формат, конвертируем
                    if isinstance(kb_text, dict):
                        from utils.kb_parser import kb_dict_to_text
                        kb_text = kb_dict_to_text(kb_text)
                        logger.info("Конвертирован старый JSON формат KB в текст")

                    if not isinstance(kb_text, str):
                        kb_text = str(kb_text)

                    kb_hash = self._compute_kb_hash(kb_text)

                    # Check if KB changed
                    kb_changed = (
                        force or
                        not self._kb_text or
                        self._kb_hash != kb_hash
                    )

                    if kb_changed:
                        self._kb_text = kb_text
                        # Парсим текст в dict для BM25
                        self._kb_parsed = parse_text_kb(kb_text)
                        self._kb_hash = kb_hash
                        logger.info("База знаний обновлена")
                else:
                    # No KB in DB, clear cache
                    if self._kb_text:
                        logger.warning("База знаний не найдена в БД, очищаем кеш")
                        self._kb_text = None
                        self._kb_parsed = None
                        self._kb_hash = None
    
    async def load_all(self, force: bool = False) -> None:
        """Load all params from DB."""
        await self.load_prompt(force=force)
        await self.load_knowledge_base(force=force)
    
    async def refresh_if_needed(self) -> None:
        """
        Check versions/IDs and refresh only if changed (no TTL logic).
        Called on every /chat request.
        """
        try:
            from db.session import async_session_factory
            from db.repository import get_active_prompt_config, get_settings
        except Exception as e:
            logger.warning(f"Could not import DB helpers: {e}")
            return
        
        async with self._lock:
            async with async_session_factory() as session:
                # Check prompt
                prompt = await get_active_prompt_config(session)
                if prompt:
                    prompt_id = str(prompt.id)
                    prompt_version = prompt.version
                    
                    if (not self._prompt_text or
                        self._prompt_id != prompt_id or
                        self._prompt_version != prompt_version):
                        # Prompt changed, update cache
                        if prompt.content:
                            self._prompt_text = prompt.content
                            self._prompt_id = prompt_id
                            self._prompt_version = prompt_version
                            logger.info(f"Промпт обновлен (ID: {prompt_id}, версия: {prompt_version})")
                else:
                    # No active prompt, clear if we had one
                    if self._prompt_text:
                        self._prompt_text = None
                        self._prompt_id = None
                        self._prompt_version = None
                
                # Check KB
                kb_settings = await get_settings(session, "knowledge_base")
                if kb_settings and kb_settings.value:
                    # KB хранится как текст в БД
                    kb_text = kb_settings.value

                    # Конвертируем старый JSON формат если нужно
                    if isinstance(kb_text, dict):
                        try:
                            from utils.kb_parser import kb_dict_to_text
                            kb_text = kb_dict_to_text(kb_text)
                        except Exception:
                            kb_text = ""

                    if not isinstance(kb_text, str):
                        kb_text = str(kb_text)

                    kb_hash = self._compute_kb_hash(kb_text)

                    if not self._kb_text or self._kb_hash != kb_hash:
                        # KB changed, update cache
                        try:
                            from utils.kb_parser import parse_text_kb
                            self._kb_text = kb_text
                            self._kb_parsed = parse_text_kb(kb_text)
                            self._kb_hash = kb_hash
                            logger.info("База знаний обновлена")
                        except Exception as e:
                            logger.error(f"Ошибка парсинга KB: {e}")
                else:
                    # No KB, clear if we had one
                    if self._kb_text:
                        self._kb_text = None
                        self._kb_parsed = None
                        self._kb_hash = None
    
    def get_prompt(self) -> str:
        """
        Get current prompt from cache (sync getter for middleware).
        Returns fallback if cache is empty.
        """
        if self._prompt_text:
            return self._prompt_text
        return "Ты — Саид, менеджер по продажам «СтройАссортимент». Отвечай только по товарам/ценам/наличию/доставке/оплате и контактам компании."
    
    def get_knowledge_base_text(self) -> str:
        """
        Get raw KB text from cache (sync getter).
        Returns empty string if cache is empty.
        """
        if self._kb_text:
            return self._kb_text
        return ""

    def get_knowledge_base_dict(self) -> dict:
        """
        Get parsed KB dict from cache (sync getter for BM25).
        Returns empty dict if cache is empty.
        """
        if self._kb_parsed:
            return self._kb_parsed
        return {"metadata": {}, "sections": {}}

    def get_knowledge_base_for_prompt(self) -> str:
        """
        Get formatted KB summary for system prompt.
        Returns compact summary of available sections.
        """
        if self._kb_parsed:
            return self._format_kb_for_prompt(self._kb_parsed)
        return ""

