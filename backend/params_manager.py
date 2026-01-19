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
        self._kb_content: Optional[dict] = None
        self._kb_text: Optional[str] = None
        
        # Change tracking
        self._prompt_id: Optional[str] = None
        self._prompt_version: Optional[int] = None
        self._kb_hash: Optional[str] = None
        
        self._initialized = True
    
    def _format_kb_text(self, kb_content: Optional[dict]) -> str:
        """
        Format KB content for system prompt - COMPACT version.
        Only includes minimal info: available sections and product groups summary.
        Full content is available via search_company_info tool.
        """
        if not kb_content:
            return ""
        
        if "metadata" not in kb_content or "sections" not in kb_content:
            return ""
        
        return self._format_kb_compact(kb_content)
    
    def _format_kb_compact(self, kb_content: dict) -> str:
        """
        Форматирует KB в компактный формат для system prompt.
        Включает только:
        - Список доступных разделов
        - Краткий список кодов групп товаров
        """
        sections = kb_content.get("sections", {})
        
        lines = [
            "ДОСТУПНЫЕ РАЗДЕЛЫ БАЗЫ ЗНАНИЙ (используй search_company_info для получения детальной информации):"
        ]
        
        # Список разделов с описанием
        for section_key, section_data in sections.items():
            title = section_data.get("title", section_key)
            keywords = section_data.get("keywords", [])
            keywords_str = ", ".join(keywords[:5])  # Первые 5 keywords
            lines.append(f"  - {section_key}: {title} (ключевые слова: {keywords_str})")
        
        # Компактный список кодов групп товаров
        if "product_groups" in sections:
            pg_content = sections["product_groups"].get("content", {})
            groups = pg_content.get("groups", [])
            
            lines.append("\nКОДЫ ГРУПП ТОВАРОВ (для search_1c_products):")
            lines.append("Используй эти коды для поиска товаров в 1С. Полный список доступен через search_company_info('product_groups').")
            
            # Показываем только первые 20 групп для компактности
            for group in groups[:20]:
                code = group.get("code", "")
                descr = group.get("description", "")[:60]  # Обрезаем описание
                lines.append(f"  {code} — {descr}")
            
            if len(groups) > 20:
                lines.append(f"  ... и еще {len(groups) - 20} групп (используй search_company_info('product_groups') для полного списка)")
        
        return "\n".join(lines)
    
    def get_available_sections(self) -> list[str]:
        """Возвращает список доступных разделов KB."""
        if not self._kb_content:
            return []
        
        if "metadata" not in self._kb_content or "sections" not in self._kb_content:
            return []
        
        return list(self._kb_content["sections"].keys())
    
    def get_section_metadata(self, section: str) -> Optional[dict]:
        """Возвращает метаданные раздела (title, source_url, keywords)."""
        if not self._kb_content:
            return None
        
        if "metadata" not in self._kb_content or "sections" not in self._kb_content:
            return None
        
        section_data = self._kb_content["sections"].get(section)
        if section_data:
            return {
                "title": section_data.get("title"),
                "source_url": section_data.get("source_url"),
                "keywords": section_data.get("keywords", []),
                "last_updated": section_data.get("last_updated")
            }
        
        return None
    
    def get_section_content(self, section: str) -> Optional[dict]:
        """Возвращает содержимое раздела."""
        if not self._kb_content:
            return None
        
        if "metadata" not in self._kb_content or "sections" not in self._kb_content:
            return None
        
        section_data = self._kb_content["sections"].get(section)
        if section_data:
            return section_data.get("content")
        
        return None
    
    def get_product_groups_summary(self) -> list[dict]:
        """Возвращает компактный список групп товаров (код + описание)."""
        if not self._kb_content:
            return []
        
        if "metadata" not in self._kb_content or "sections" not in self._kb_content:
            return []
        
        pg_section = self._kb_content["sections"].get("product_groups")
        if pg_section:
            groups = pg_section.get("content", {}).get("groups", [])
            return [{"code": g.get("code"), "description": g.get("description")} for g in groups]
        
        return []
    
    def _compute_kb_hash(self, kb_content: Optional[dict]) -> str:
        """Compute hash of KB content for change detection."""
        if not kb_content:
            return ""
        try:
            content_str = json.dumps(kb_content, sort_keys=True, ensure_ascii=False)
            return hashlib.md5(content_str.encode('utf-8')).hexdigest()
        except Exception:
            return ""
    
    def _fallback_kb_from_files(self) -> str:
        """Load KB from fallback file."""
        kb_path = Path(__file__).parent / "data" / "kb.json"
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                kb_content = json.load(f)
                return self._format_kb_text(kb_content)
        except FileNotFoundError:
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
        Load knowledge base from DB. Updates cache only if changed or force=True.
        """
        try:
            from db.session import async_session_factory
            from db.repository import get_settings
        except Exception as e:
            logger.warning(f"Could not import DB helpers: {e}")
            return
        
        async with self._lock:
            async with async_session_factory() as session:
                kb_settings = await get_settings(session, "knowledge_base")
                
                if kb_settings and kb_settings.value:
                    kb_content = kb_settings.value
                    kb_hash = self._compute_kb_hash(kb_content)
                    
                    # Check if KB changed
                    kb_changed = (
                        force or
                        not self._kb_content or
                        self._kb_hash != kb_hash
                    )
                    
                    if kb_changed:
                        self._kb_content = kb_content
                        self._kb_text = self._format_kb_text(kb_content)
                        self._kb_hash = kb_hash
                        logger.info("База знаний обновлена")
                else:
                    # No KB in DB, clear cache
                    if self._kb_content:
                        logger.warning("База знаний не найдена в БД, очищаем кеш")
                        self._kb_content = None
                        self._kb_text = None
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
                    kb_content = kb_settings.value
                    kb_hash = self._compute_kb_hash(kb_content)
                    
                    if not self._kb_content or self._kb_hash != kb_hash:
                        # KB changed, update cache
                        self._kb_content = kb_content
                        self._kb_text = self._format_kb_text(kb_content)
                        self._kb_hash = kb_hash
                        logger.info("База знаний обновлена")
                else:
                    # No KB, clear if we had one
                    if self._kb_content:
                        self._kb_content = None
                        self._kb_text = None
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
        Get formatted KB text from cache (sync getter for middleware).
        Returns fallback from file if cache is empty.
        """
        if self._kb_text:
            return self._kb_text
        return self._fallback_kb_from_files()
    
    def get_knowledge_base_dict(self) -> dict:
        """
        Get raw KB dict from cache (sync getter).
        Returns empty dict if cache is empty.
        """
        if self._kb_content:
            return self._kb_content
        return {}

