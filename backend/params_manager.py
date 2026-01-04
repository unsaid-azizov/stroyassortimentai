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
        """Format KB content dict to text."""
        if not kb_content:
            return ""
        try:
            s = json.dumps(kb_content, ensure_ascii=False, indent=2)
        except Exception:
            s = str(kb_content)
        max_chars = 20000
        if len(s) > max_chars:
            return s[:max_chars] + "\n\n...[KB truncated]..."
        return s
    
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
        info_path = Path(__file__).parent / "data" / "company_info.json"
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                return self._format_kb_text(json.load(f))
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

