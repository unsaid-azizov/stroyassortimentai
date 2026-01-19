import time
from typing import Any, Dict, Optional

from db.session import async_session_factory
from db.repository import get_settings
from utils.secrets import decrypt_secret

# Cache
_SYSTEM: Dict[str, Any] = {}
_SECRETS_ENC: Dict[str, str] = {}
_UPDATED_AT_SYSTEM: Optional[float] = None
_UPDATED_AT_SECRETS: Optional[float] = None
_LAST_REFRESH_TS: float = 0.0


def _dt_to_ts(dt) -> Optional[float]:
    try:
        return float(dt.timestamp())
    except Exception:
        return None


async def refresh_runtime_config(force: bool = False, ttl_seconds: int = 15) -> None:
    """
    Refresh cached settings+secrets from DB. Uses TTL to limit DB traffic.
    """
    global _SYSTEM, _SECRETS_ENC, _UPDATED_AT_SYSTEM, _UPDATED_AT_SECRETS, _LAST_REFRESH_TS

    now = time.time()
    if (not force) and _LAST_REFRESH_TS and (now - _LAST_REFRESH_TS) < ttl_seconds:
        return

    async with async_session_factory() as session:
        system_obj = await get_settings(session, "system")
        secrets_obj = await get_settings(session, "secrets")

        if system_obj:
            _SYSTEM = system_obj.value or {}
            _UPDATED_AT_SYSTEM = _dt_to_ts(system_obj.updated_at)
        else:
            _SYSTEM = {}
            _UPDATED_AT_SYSTEM = None

        if secrets_obj:
            _SECRETS_ENC = secrets_obj.value or {}
            _UPDATED_AT_SECRETS = _dt_to_ts(secrets_obj.updated_at)
        else:
            _SECRETS_ENC = {}
            _UPDATED_AT_SECRETS = None

    _LAST_REFRESH_TS = now


def get_public_settings_cached() -> Dict[str, Any]:
    return dict(_SYSTEM)


def get_secret_ciphertext_cached(name: str) -> Optional[str]:
    v = _SECRETS_ENC.get(name)
    if not v:
        return None
    return str(v)


def get_secret_cached(name: str) -> Optional[str]:
    ct = get_secret_ciphertext_cached(name)
    if not ct:
        return None
    return decrypt_secret(ct)


def get_cache_snapshot() -> Dict[str, Any]:
    return {
        "system_keys": sorted(list(_SYSTEM.keys())),
        "secrets_keys": sorted(list(_SECRETS_ENC.keys())),
        "updated_at_system": _UPDATED_AT_SYSTEM,
        "updated_at_secrets": _UPDATED_AT_SECRETS,
        "last_refresh_ts": _LAST_REFRESH_TS,
    }



